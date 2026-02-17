"""Socket.IO integration tests for 2-player Texas Hold'em.

Layer 2 tests: Use flask_socketio.test_client to test WebSocket events
without a browser. Tests the full flow:
  join_table -> connect_to_table_room -> set_ready -> game_state_update ->
  player_action -> game progression -> showdown
"""

import pytest
import uuid
from flask import Flask, g
from flask_socketio import SocketIO
from sqlalchemy.pool import StaticPool

from online_poker.database import db
from online_poker.auth import init_login_manager
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.lobby_routes import lobby_bp, register_lobby_socket_events
from online_poker.routes.game_routes import game_bp
from online_poker.services.websocket_manager import init_websocket_manager
from online_poker.services.user_manager import UserManager
from online_poker.services.table_manager import TableManager
from online_poker.services.table_access_manager import TableAccessManager
from online_poker.services.game_orchestrator import game_orchestrator
from online_poker.services.disconnect_manager import disconnect_manager
from online_poker.models.table_config import TableConfig
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.core.card import Card


def _patch_socketio_user_loading(socketio_instance):
    """Fix Flask-Login user caching with multiple SocketIO test clients.

    Flask-Login caches current_user in flask.g._login_user, which persists
    across request contexts within the same app context. This causes all
    SocketIO handlers to see the user from the most recently connected client
    instead of the user associated with the current request's session.

    This patch clears the cached user before each event handler so Flask-Login
    reloads it from the correct session.
    """
    original = socketio_instance._handle_event

    def patched_handle_event(handler, message, namespace, sid, *args):
        # Wrap the handler to clear cached user before it runs
        original_handler = handler

        def clearing_handler(*a, **kw):
            g.pop('_login_user', None)
            return original_handler(*a, **kw)

        return original(clearing_handler, message, namespace, sid, *args)

    socketio_instance._handle_event = patched_handle_event


# ── Fixtures ──────────────────────────────────────────────────────────────────
# All fixtures operate within the app_and_socketio context (no nested app.app_context()).

@pytest.fixture
def app_and_socketio():
    """Create test Flask app with SocketIO. Yields (app, socketio) inside an app context."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False

    # Set up database manually (don't use init_database which overwrites URI).
    # StaticPool ensures all connections share the same in-memory DB so
    # HTTP client and SocketIO handlers see the same data.
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }
    db.init_app(app)

    init_login_manager(app)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(lobby_bp)
    app.register_blueprint(game_bp, url_prefix='/game')

    socketio = SocketIO(app, logger=False, engineio_logger=False)
    init_websocket_manager(socketio)
    register_lobby_socket_events(socketio)
    _patch_socketio_user_loading(socketio)

    with app.app_context():
        db.create_all()
        yield app, socketio
        # Cancel any disconnect timers to prevent hanging on exit
        for dp in disconnect_manager.disconnected_players.values():
            dp.cancel_timers()
        disconnect_manager.disconnected_players.clear()
        disconnect_manager.table_disconnects.clear()
        game_orchestrator.sessions.clear()
        db.drop_all()


@pytest.fixture
def app(app_and_socketio):
    return app_and_socketio[0]


@pytest.fixture
def socketio(app_and_socketio):
    return app_and_socketio[1]


@pytest.fixture
def player1(app):
    """Create first test player (already in app context from app_and_socketio)."""
    uid = str(uuid.uuid4())[:8]
    user = UserManager.create_user(f"alice_{uid}", f"alice_{uid}@test.com", "password123")
    UserManager.update_user_bankroll(user.id, 1000)
    user._test_username = f"alice_{uid}"
    return user


@pytest.fixture
def player2(app):
    """Create second test player."""
    uid = str(uuid.uuid4())[:8]
    user = UserManager.create_user(f"bob_{uid}", f"bob_{uid}@test.com", "password123")
    UserManager.update_user_bankroll(user.id, 1000)
    user._test_username = f"bob_{uid}"
    return user


@pytest.fixture
def holdem_table(app, player1):
    """Create a Texas Hold'em table."""
    table_manager = TableManager()
    config = TableConfig(
        name="Test Hold'em",
        variant="hold_em",
        betting_structure=BettingStructure.NO_LIMIT,
        stakes={'small_blind': 1, 'big_blind': 2},
        max_players=6,
        is_private=False,
        allow_bots=False
    )
    return table_manager.create_table(player1.id, config)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login_and_connect(app, socketio, user):
    """Log in via HTTP and create a SocketIO test client.

    Returns (flask_test_client, socketio_test_client).
    """
    http_client = app.test_client()
    http_client.post('/auth/api/login', json={
        'username': user._test_username,
        'password': 'password123'
    })
    sio_client = socketio.test_client(app, flask_test_client=http_client)
    return http_client, sio_client


def _get_events(sio_client, event_name=None):
    """Get received events, optionally filtered by name."""
    received = sio_client.get_received()
    if event_name:
        return [msg for msg in received if msg['name'] == event_name]
    return received


def _get_last_game_state(sio_client):
    """Get the most recent game_state_update from received events."""
    events = _get_events(sio_client, 'game_state_update')
    if events:
        return events[-1]['args'][0]
    return None


def _action_names(actions):
    """Convert game engine actions to string names.

    get_valid_actions returns tuples of (PlayerAction, min, max).
    PlayerAction is an enum with .value = 'fold', 'check', etc.
    """
    return [a[0].value if hasattr(a[0], 'value') else str(a[0]) for a in actions]


def _find_action(actions, name):
    """Find an action tuple by name string."""
    for a in actions:
        val = a[0].value if hasattr(a[0], 'value') else str(a[0])
        if val == name:
            return a
    return None


def _setup_two_player_game(app, socketio, player1, player2, holdem_table):
    """Join both players, connect to room, set ready, start hand.

    Returns (sio1, sio2, table_id).
    """
    table_id = str(holdem_table.id)

    # Join via HTTP
    http1, sio1 = _login_and_connect(app, socketio, player1)
    http1.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': 100, 'seat_number': 1
    })

    http2, sio2 = _login_and_connect(app, socketio, player2)
    http2.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': 100, 'seat_number': 2
    })

    # Connect to table room
    sio1.get_received()
    sio2.get_received()
    sio1.emit('connect_to_table_room', {'table_id': table_id})
    sio2.emit('connect_to_table_room', {'table_id': table_id})
    sio1.get_received()
    sio2.get_received()

    # Both players set ready → hand starts automatically
    sio1.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    return sio1, sio2, table_id


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSocketIOConnection:
    """Test basic Socket.IO connection and authentication."""

    def test_authenticated_connect(self, app, socketio, player1):
        """Authenticated user connects and receives confirmation."""
        _, sio_client = _login_and_connect(app, socketio, player1)
        assert sio_client.is_connected()

        events = _get_events(sio_client, 'connected')
        assert len(events) >= 1
        assert events[0]['args'][0]['user_id'] == player1.id

        sio_client.disconnect()

    def test_join_table_room(self, app, socketio, player1, holdem_table):
        """Player joins table room and receives table_joined event."""
        table_id = str(holdem_table.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 1
        })
        sio1.get_received()  # Clear connect events

        sio1.emit('connect_to_table_room', {'table_id': table_id})
        events = _get_events(sio1, 'table_joined')
        assert len(events) >= 1
        assert events[0]['args'][0]['table_id'] == table_id

        sio1.disconnect()


class TestReadyAndHandStart:
    """Test the ready system and hand starting via SocketIO."""

    def test_both_players_ready_starts_hand(self, app, socketio, player1, player2, holdem_table):
        """When both players set ready, a hand starts automatically."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        # Verify game session was created
        session = game_orchestrator.get_session(table_id)
        assert session is not None
        assert session.game is not None
        assert session.game.state in [GameState.BETTING, GameState.DEALING]

        sio1.disconnect()
        sio2.disconnect()

    def test_game_state_sent_after_hand_start(self, app, socketio, player1, player2, holdem_table):
        """After hand starts, players can request and receive game state."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        # Request game state
        sio1.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(sio1)

        assert state is not None
        assert state['game_phase'] != 'waiting'
        assert len(state['players']) == 2
        assert state['current_player'] is not None

        sio1.disconnect()
        sio2.disconnect()


class TestPlayerActions:
    """Test player actions via SocketIO."""

    def test_fold_ends_hand(self, app, socketio, player1, player2, holdem_table):
        """Folding ends the hand immediately."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game
        current_player = game.current_player

        # Determine which sio is current player
        cp_sio = sio1 if current_player.id == player1.id else sio2
        cp_sio.get_received()

        cp_sio.emit('player_action', {
            'table_id': table_id,
            'action': 'fold',
            'amount': 0
        })

        events = cp_sio.get_received()
        action_results = [e for e in events if e['name'] == 'action_result']
        assert len(action_results) >= 1
        assert action_results[0]['args'][0]['success'] is True

        assert game.state == GameState.COMPLETE

        sio1.disconnect()
        sio2.disconnect()

    def test_call_and_check_via_socketio(self, app, socketio, player1, player2, holdem_table):
        """Call and check actions work via SocketIO and produce action_result."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # Play through preflop: each player calls or checks
        for _ in range(2):
            if game.state != GameState.BETTING or not game.current_player:
                break

            cp = game.current_player
            cp_sio = sio1 if cp.id == player1.id else sio2
            actions = game.get_valid_actions(cp.id)
            names = _action_names(actions)

            cp_sio.get_received()
            if 'check' in names:
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'check', 'amount': 0
                })
            elif 'call' in names:
                call_info = _find_action(actions, 'call')
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'call', 'amount': call_info[1]
                })

            events = cp_sio.get_received()
            results = [e for e in events if e['name'] == 'action_result']
            assert len(results) >= 1, f"No action_result, got: {[e['name'] for e in events]}"
            assert results[0]['args'][0]['success'] is True

        sio1.disconnect()
        sio2.disconnect()

    def test_full_hand_to_showdown(self, app, socketio, player1, player2, holdem_table):
        """Play a complete hand to showdown via check/call."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        max_actions = 50
        action_count = 0

        while game.state not in [GameState.COMPLETE, GameState.SHOWDOWN] and action_count < max_actions:
            current_player = game.current_player
            if not current_player:
                break

            actions = game.get_valid_actions(current_player.id)
            if not actions:
                break

            names = _action_names(actions)
            cp_sio = sio1 if current_player.id == player1.id else sio2
            cp_sio.get_received()

            if 'check' in names:
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'check', 'amount': 0
                })
            elif 'call' in names:
                call_info = _find_action(actions, 'call')
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'call', 'amount': call_info[1]
                })
            else:
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'fold', 'amount': 0
                })

            events = cp_sio.get_received()
            action_results = [e for e in events if e['name'] == 'action_result']
            if action_results:
                assert action_results[0]['args'][0]['success'] is True, \
                    f"Action failed: {action_results[0]['args'][0]}"

            action_count += 1

        assert game.state in [GameState.COMPLETE, GameState.SHOWDOWN], \
            f"Game didn't complete after {action_count} actions, state: {game.state}"

        # Verify hand results
        hand_results = game.get_hand_results()
        assert hand_results is not None
        assert len(hand_results.pots) > 0
        assert hand_results.total_pot > 0

        sio1.disconnect()
        sio2.disconnect()


class TestGameStateUpdates:
    """Test that game state updates are broadcast correctly."""

    def test_opponent_receives_action_broadcast(self, app, socketio, player1, player2, holdem_table):
        """When one player acts, the other receives the broadcast."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game
        current_player = game.current_player

        cp_sio = sio1 if current_player.id == player1.id else sio2
        other_sio = sio2 if current_player.id == player1.id else sio1

        cp_sio.get_received()
        other_sio.get_received()

        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'fold', 'amount': 0
        })

        other_events = other_sio.get_received()
        other_names = [e['name'] for e in other_events]

        assert 'player_action' in other_names, \
            f"Other player didn't get player_action, got: {other_names}"
        assert 'game_state_update' in other_names, \
            f"Other player didn't get game_state_update, got: {other_names}"

        sio1.disconnect()
        sio2.disconnect()

    def test_game_state_hides_opponent_cards(self, app, socketio, player1, player2, holdem_table):
        """Game state doesn't reveal opponent's hole cards during play."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        sio1.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(sio1)

        assert state is not None
        for p in state.get('players', []):
            if p['user_id'] == player1.id:
                # Own cards visible
                assert len(p.get('cards', [])) > 0 or p.get('card_count', 0) > 0
            else:
                # Opponent cards hidden
                assert len(p.get('cards', [])) == 0, \
                    f"Opponent cards should be hidden, got: {p.get('cards')}"

        sio1.disconnect()
        sio2.disconnect()

    def test_blinds_reflected_in_game_state(self, app, socketio, player1, player2, holdem_table):
        """After hand starts, pot shows blind total and stacks are reduced."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        # Request game state and check pot/stacks
        sio1.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(sio1)

        assert state is not None

        # Pot should be 3 (SB 1 + BB 2)
        pot = state.get('pot_info', {})
        assert pot.get('total_pot', 0) == 3, \
            f"Expected pot=3 (1+2 blinds), got {pot.get('total_pot', 0)}"

        # Both player stacks should be reduced from buy-in of 100
        stacks = {p['user_id']: p['chip_stack'] for p in state.get('players', [])}
        total_stacks = sum(stacks.values())
        assert total_stacks == 197, \
            f"Expected total stacks=197 (200-3 blinds), got {total_stacks}: {stacks}"

        # At least one player should have a current_bet > 0
        bets = {p['user_id']: p.get('current_bet', 0) for p in state.get('players', [])}
        assert any(b > 0 for b in bets.values()), \
            f"Expected at least one player with current_bet > 0, got {bets}"

        sio1.disconnect()
        sio2.disconnect()

    def test_phase_detection_preflop(self, app, socketio, player1, player2, holdem_table):
        """Game phase is PREFLOP when no community cards dealt."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        sio1.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(sio1)

        assert state is not None
        assert state.get('game_phase') == 'preflop', \
            f"Expected phase=preflop, got {state.get('game_phase')}"

        sio1.disconnect()
        sio2.disconnect()

    def test_phase_transitions_through_streets(self, app, socketio, player1, player2, holdem_table):
        """Phase transitions correctly through preflop -> flop -> turn -> river."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        phases_seen = set()
        max_actions = 50
        action_count = 0

        while game.state not in [GameState.COMPLETE, GameState.SHOWDOWN] and action_count < max_actions:
            # Check current phase
            sio1.emit('request_game_state', {'table_id': table_id})
            state = _get_last_game_state(sio1)
            if state:
                phases_seen.add(state.get('game_phase'))

            cp = game.current_player
            if not cp:
                break

            actions = game.get_valid_actions(cp.id)
            if not actions:
                break

            names = _action_names(actions)
            cp_sio = sio1 if cp.id == player1.id else sio2
            cp_sio.get_received()

            if 'check' in names:
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'check', 'amount': 0
                })
            elif 'call' in names:
                call_info = _find_action(actions, 'call')
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'call', 'amount': call_info[1]
                })
            else:
                break

            cp_sio.get_received()
            action_count += 1

        # Should have seen at least preflop and flop
        assert 'preflop' in phases_seen, \
            f"Expected preflop phase, phases seen: {phases_seen}"
        # If game reached flop, check it was detected
        if action_count > 2:
            assert len(phases_seen) > 1, \
                f"Expected phase transitions, only saw: {phases_seen}"

        sio1.disconnect()
        sio2.disconnect()

    def test_hand_complete_broadcasts_results(self, app, socketio, player1, player2, holdem_table):
        """When hand completes, hand_complete event has winners and pot info."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game
        max_actions = 50
        action_count = 0

        # Clear all events before playing, accumulate during loop
        sio1.get_received()
        sio2.get_received()
        all_events = []

        while game.state not in [GameState.COMPLETE, GameState.SHOWDOWN] and action_count < max_actions:
            cp = game.current_player
            if not cp:
                break

            actions = game.get_valid_actions(cp.id)
            if not actions:
                break

            names = _action_names(actions)
            cp_sio = sio1 if cp.id == player1.id else sio2

            if 'check' in names:
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'check', 'amount': 0
                })
            elif 'call' in names:
                call_info = _find_action(actions, 'call')
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'call', 'amount': call_info[1]
                })
            else:
                cp_sio.emit('player_action', {
                    'table_id': table_id, 'action': 'fold', 'amount': 0
                })

            # Collect all events from both clients
            all_events.extend(sio1.get_received())
            all_events.extend(sio2.get_received())
            action_count += 1

        # Collect any final events
        all_events.extend(sio1.get_received())
        all_events.extend(sio2.get_received())

        assert game.state in [GameState.COMPLETE, GameState.SHOWDOWN]

        # Check hand_complete event was broadcast
        hand_complete_events = [e for e in all_events if e['name'] == 'hand_complete']

        assert len(hand_complete_events) >= 1, \
            f"Expected hand_complete event, got events: {set(e['name'] for e in all_events)}"

        hc_data = hand_complete_events[0]['args'][0]
        results = hc_data.get('hand_results', {})
        assert results.get('total_pot', 0) > 0, \
            f"Expected total_pot > 0, got {results}"
        assert len(results.get('pots', [])) > 0, \
            f"Expected at least one pot result, got {results}"

        sio1.disconnect()
        sio2.disconnect()


def _play_hand_to_completion(game, sio1, sio2, player1_id, table_id, max_actions=50):
    """Play a hand to completion using check/call. Returns all events collected."""
    all_events = []
    action_count = 0

    while game.state not in [GameState.COMPLETE, GameState.SHOWDOWN] and action_count < max_actions:
        cp = game.current_player
        if not cp:
            break

        actions = game.get_valid_actions(cp.id)
        if not actions:
            break

        names = _action_names(actions)
        cp_sio = sio1 if cp.id == player1_id else sio2

        if 'check' in names:
            cp_sio.emit('player_action', {
                'table_id': table_id, 'action': 'check', 'amount': 0
            })
        elif 'call' in names:
            call_info = _find_action(actions, 'call')
            cp_sio.emit('player_action', {
                'table_id': table_id, 'action': 'call', 'amount': call_info[1]
            })
        else:
            cp_sio.emit('player_action', {
                'table_id': table_id, 'action': 'fold', 'amount': 0
            })

        all_events.extend(sio1.get_received())
        all_events.extend(sio2.get_received())
        action_count += 1

    all_events.extend(sio1.get_received())
    all_events.extend(sio2.get_received())
    return all_events


class TestFullHandCycle:
    """Test complete hand lifecycle: deal -> play -> showdown -> next hand."""

    def test_full_hand_then_second_hand(self, app, socketio, player1, player2, holdem_table):
        """Play a complete hand, then start a second hand."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # -- Hand 1 --
        events = _play_hand_to_completion(game, sio1, sio2, player1.id, table_id)

        assert game.state in [GameState.COMPLETE, GameState.SHOWDOWN], \
            f"Hand 1 didn't complete, state: {game.state}"

        # Verify hand_complete event was sent
        hc_events = [e for e in events if e['name'] == 'hand_complete']
        assert len(hc_events) >= 1, "No hand_complete event for hand 1"

        # Record stacks after hand 1
        sio1.emit('request_game_state', {'table_id': table_id})
        state1 = _get_last_game_state(sio1)
        stacks_after_h1 = {p['user_id']: p['chip_stack'] for p in state1['players']}
        total_after_h1 = sum(stacks_after_h1.values())

        # Stacks should still sum to total buy-in (conservation of chips)
        assert total_after_h1 == 200, \
            f"Expected 200 total chips after hand 1, got {total_after_h1}: {stacks_after_h1}"

        # -- Set Ready for Hand 2 --
        sio1.get_received()
        sio2.get_received()

        sio1.emit('set_ready', {'table_id': table_id, 'ready': True})
        sio1.get_received()
        sio2.get_received()

        sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
        sio1.get_received()
        sio2.get_received()

        # -- Hand 2 --
        # Verify game started again
        assert game.state in [GameState.BETTING, GameState.DEALING], \
            f"Hand 2 didn't start, state: {game.state}"
        assert game.current_player is not None, "No current player in hand 2"

        # Play hand 2
        events2 = _play_hand_to_completion(game, sio1, sio2, player1.id, table_id)

        assert game.state in [GameState.COMPLETE, GameState.SHOWDOWN], \
            f"Hand 2 didn't complete, state: {game.state}"

        # Verify stacks still conserved
        sio1.emit('request_game_state', {'table_id': table_id})
        state2 = _get_last_game_state(sio1)
        stacks_after_h2 = {p['user_id']: p['chip_stack'] for p in state2['players']}
        total_after_h2 = sum(stacks_after_h2.values())
        assert total_after_h2 == 200, \
            f"Expected 200 total chips after hand 2, got {total_after_h2}: {stacks_after_h2}"

        sio1.disconnect()
        sio2.disconnect()

    def test_winner_gets_pot_and_stacks_update(self, app, socketio, player1, player2, holdem_table):
        """After a fold, winner gets pot and stacks are updated."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # Current player folds
        cp = game.current_player
        cp_sio = sio1 if cp.id == player1.id else sio2
        other_id = player2.id if cp.id == player1.id else player1.id

        cp_sio.get_received()
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'fold', 'amount': 0
        })
        sio1.get_received()
        sio2.get_received()

        # Get stacks after
        sio1.emit('request_game_state', {'table_id': table_id})
        state_after = _get_last_game_state(sio1)
        stacks_after = {p['user_id']: p['chip_stack'] for p in state_after['players']}

        # Total should still be 200
        total = sum(stacks_after.values())
        assert total == 200, f"Expected 200 total chips, got {total}: {stacks_after}"

        # Winner (other player) should have gained the pot
        assert stacks_after[other_id] > 100, \
            f"Expected winner to have >100 chips, got {stacks_after[other_id]}"

        sio1.disconnect()
        sio2.disconnect()


class TestLeaveAndRejoin:
    """Test leaving a table and rejoining."""

    def test_leave_table_cleans_up_access_record(self, app, socketio, player1, player2, holdem_table):
        """When a player leaves via SocketIO, their access record is deactivated."""
        table_id = str(holdem_table.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 1
        })

        http2, sio2 = _login_and_connect(app, socketio, player2)
        http2.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 2
        })

        sio1.get_received()
        sio2.get_received()
        sio1.emit('connect_to_table_room', {'table_id': table_id})
        sio2.emit('connect_to_table_room', {'table_id': table_id})
        sio1.get_received()
        sio2.get_received()

        # Verify both players are active
        p1_access = TableAccessManager.get_user_access(player1.id, table_id)
        p2_access = TableAccessManager.get_user_access(player2.id, table_id)
        assert p1_access is not None, "Player 1 should have active access"
        assert p2_access is not None, "Player 2 should have active access"

        # Player 1 leaves
        sio1.emit('leave_table', {'table_id': table_id})
        sio1.get_received()

        # Player 1's access should be deactivated
        p1_after = TableAccessManager.get_user_access(player1.id, table_id)
        assert p1_after is None, "Player 1's access should be deactivated after leaving"

        # Player 2 should still be active
        p2_after = TableAccessManager.get_user_access(player2.id, table_id)
        assert p2_after is not None, "Player 2 should still have active access"

        sio1.disconnect()
        sio2.disconnect()

    def test_leave_removes_player_from_game_session(self, app, socketio, player1, player2, holdem_table):
        """When a player leaves during a game, they are auto-folded and removed after hand completes."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        assert player1.id in session.connected_players
        assert player2.id in session.connected_players

        # Player 1 leaves mid-hand — should be auto-folded and removed after hand
        sio1.emit('leave_table', {'table_id': table_id})
        sio1.get_received()
        sio2.get_received()

        # Player 1 should be removed from game session after hand completion
        assert player1.id not in session.connected_players, \
            "Player 1 should be removed from game session after leaving mid-hand"
        assert player2.id in session.connected_players, \
            "Player 2 should still be in game session"

        sio1.disconnect()
        sio2.disconnect()

    def test_rejoin_after_leaving(self, app, socketio, player1, player2, holdem_table):
        """A player can rejoin a table after leaving and play another hand."""
        table_id = str(holdem_table.id)

        # Both players join and connect
        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 1
        })

        http2, sio2 = _login_and_connect(app, socketio, player2)
        http2.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 2
        })

        sio1.get_received()
        sio2.get_received()
        sio1.emit('connect_to_table_room', {'table_id': table_id})
        sio2.emit('connect_to_table_room', {'table_id': table_id})
        sio1.get_received()
        sio2.get_received()

        # Player 1 leaves
        sio1.emit('leave_table', {'table_id': table_id})
        sio1.get_received()
        sio1.disconnect()

        # Verify player 1's seat is freed
        p1_access = TableAccessManager.get_user_access(player1.id, table_id)
        assert p1_access is None, "Player 1's access should be deactivated"

        # Player 1 rejoins with a new connection
        http1_new, sio1_new = _login_and_connect(app, socketio, player1)
        resp = http1_new.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 1
        })
        assert resp.status_code == 200, f"Rejoin failed: {resp.get_json()}"
        data = resp.get_json()
        assert data.get('success'), f"Rejoin not successful: {data}"

        # Connect to table room
        sio1_new.get_received()
        sio1_new.emit('connect_to_table_room', {'table_id': table_id})
        sio1_new.get_received()
        sio2.get_received()

        # Verify player 1 is back at the table
        p1_rejoin = TableAccessManager.get_user_access(player1.id, table_id)
        assert p1_rejoin is not None, "Player 1 should have active access after rejoin"
        assert p1_rejoin.seat_number == 1, "Player 1 should be back in seat 1"

        # Both set ready → hand starts
        sio1_new.emit('set_ready', {'table_id': table_id, 'ready': True})
        sio1_new.get_received()
        sio2.get_received()

        sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
        sio1_new.get_received()
        sio2.get_received()

        # A game session should exist with both players
        session = game_orchestrator.get_session(table_id)
        assert session is not None, "Game session should exist"
        assert player1.id in session.connected_players, "Player 1 should be in game"
        assert player2.id in session.connected_players, "Player 2 should be in game"

        # Game should be active
        game = session.game
        assert game.current_player is not None, "Game should have a current player"

        sio1_new.disconnect()
        sio2.disconnect()

    def test_leave_mid_hand_awards_pot_to_remaining_player(self, app, socketio, player1, player2, holdem_table):
        """Leave mid-hand folds the leaving player and awards pot to remaining player."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # Record player 2's stack before leave (after blinds posted)
        p2_stack_before = game.table.players[player2.id].stack

        # Player 1 leaves mid-hand
        sio1.emit('leave_table', {'table_id': table_id})
        sio1.get_received()
        sio2.get_received()

        # After leave-fold + player removal, game goes to WAITING (only 1 player left)
        assert game.state in (GameState.COMPLETE, GameState.WAITING), \
            f"Game should be COMPLETE or WAITING after leave-fold, got {game.state}"

        # Player 2 should have won the pot (gained chips)
        p2_stack_after = game.table.players[player2.id].stack
        assert p2_stack_after > p2_stack_before, \
            f"Winner should have more chips than {p2_stack_before}, got {p2_stack_after}"

        # Player 1 should be removed from the game
        assert player1.id not in session.connected_players, \
            "Leaving player should be removed from session"

        sio1.disconnect()
        sio2.disconnect()

    def test_leave_when_not_in_hand_removes_immediately(self, app, socketio, player1, player2, holdem_table):
        """Leave when no hand is active removes player immediately (no pending)."""
        table_id = str(holdem_table.id)

        # Both join but don't start a hand (no ready)
        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 1
        })

        http2, sio2 = _login_and_connect(app, socketio, player2)
        http2.post(f'/api/tables/{table_id}/join', json={
            'buy_in_amount': 100, 'seat_number': 2
        })

        sio1.get_received()
        sio2.get_received()
        sio1.emit('connect_to_table_room', {'table_id': table_id})
        sio2.emit('connect_to_table_room', {'table_id': table_id})
        sio1.get_received()
        sio2.get_received()

        # Player 1 leaves (no hand active)
        sio1.emit('leave_table', {'table_id': table_id})
        sio1.get_received()

        # Player 1's access should be deactivated immediately
        p1_access = TableAccessManager.get_user_access(player1.id, table_id)
        assert p1_access is None, "Player 1 access should be cleared immediately"

        sio1.disconnect()
        sio2.disconnect()

    def test_both_leave_deactivates_session(self, app, socketio, player1, player2, holdem_table):
        """When both players leave, the session is deactivated."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        assert session.is_active, "Session should be active initially"

        # Player 1 leaves (folds, hand completes, removed)
        sio1.emit('leave_table', {'table_id': table_id})
        sio1.get_received()
        sio2.get_received()

        # Player 2 leaves (no hand active now)
        sio2.emit('leave_table', {'table_id': table_id})
        sio2.get_received()

        # Session should be deactivated
        session = game_orchestrator.get_session(table_id)
        if session:
            assert not session.is_active, "Session should be deactivated when all players leave"
            assert len(session.connected_players) == 0, "No connected players should remain"

        sio1.disconnect()
        sio2.disconnect()

    def test_leave_mid_hand_preserves_disconnect_behavior(self, app, socketio, player1, player2, holdem_table):
        """Disconnect mid-hand should NOT immediately fold (unlike intentional leave)."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)

        # Simulate disconnect (not intentional leave)
        # Disconnect should go through disconnect_manager, not mark_player_leaving
        assert player1.id in session.connected_players

        # The disconnect handler gives a 30s grace period for reconnect
        # Verify the disconnect manager tracks disconnected players separately
        from online_poker.services.disconnect_manager import disconnect_manager as dm
        is_current = (session.game.current_player and
                      session.game.current_player.id == player1.id)

        dm.handle_player_disconnect(player1.id, table_id, is_current)

        # Player should be tracked as disconnected
        assert dm.is_player_disconnected(player1.id), \
            "Disconnected player should be tracked by disconnect manager"

        # Player should NOT be in pending_leaves (that's for intentional leave)
        assert player1.id not in session.pending_leaves, \
            "Disconnected player should NOT be in pending_leaves"

        # Clean up disconnect tracking
        info = dm.disconnected_players.get(player1.id)
        if info:
            info.cancel_timers()
        dm._cleanup_disconnected_player(player1.id)

        sio1.disconnect()
        sio2.disconnect()


# ── Helpers for edge case tests ──────────────────────────────────────────────

def _setup_two_player_game_custom(app, socketio, player1, player2, holdem_table,
                                   buy_in1=100, buy_in2=100):
    """Like _setup_two_player_game but with custom buy-in amounts.

    Returns (http1, sio1, http2, sio2, table_id).
    """
    table_id = str(holdem_table.id)

    http1, sio1 = _login_and_connect(app, socketio, player1)
    http1.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': buy_in1, 'seat_number': 1
    })

    http2, sio2 = _login_and_connect(app, socketio, player2)
    http2.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': buy_in2, 'seat_number': 2
    })

    sio1.get_received()
    sio2.get_received()
    sio1.emit('connect_to_table_room', {'table_id': table_id})
    sio2.emit('connect_to_table_room', {'table_id': table_id})
    sio1.get_received()
    sio2.get_received()

    sio1.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    return http1, sio1, http2, sio2, table_id


def _collect_events_through_hand(game, sio1, sio2, player1_id, table_id, max_actions=50):
    """Play a hand to completion via SocketIO using check/call/all-in.

    Handles all-in players (who have no actions) by only acting for
    players who have valid actions.

    Returns all collected events.
    """
    all_events = []
    action_count = 0

    while game.state not in [GameState.COMPLETE, GameState.SHOWDOWN] and action_count < max_actions:
        cp = game.current_player
        if not cp:
            break

        actions = game.get_valid_actions(cp.id)
        if not actions:
            break

        names = _action_names(actions)
        cp_sio = sio1 if cp.id == player1_id else sio2

        if 'check' in names:
            cp_sio.emit('player_action', {
                'table_id': table_id, 'action': 'check', 'amount': 0
            })
        elif 'call' in names:
            call_info = _find_action(actions, 'call')
            cp_sio.emit('player_action', {
                'table_id': table_id, 'action': 'call', 'amount': call_info[1]
            })
        else:
            cp_sio.emit('player_action', {
                'table_id': table_id, 'action': 'fold', 'amount': 0
            })

        all_events.extend(sio1.get_received())
        all_events.extend(sio2.get_received())
        action_count += 1

    all_events.extend(sio1.get_received())
    all_events.extend(sio2.get_received())
    return all_events


# ── Edge Case SocketIO Tests ────────────────────────────────────────────────

class TestAllInViaSocketIO:
    """Test all-in scenarios through the SocketIO layer."""

    def test_all_in_preflop_completes_hand(self, app, socketio, player1, player2, holdem_table):
        """Short stack goes all-in pre-flop via SocketIO, hand completes."""
        # Min buy-in is 40 (20 * BB), max is 400 (200 * BB)
        _, sio1, _, sio2, table_id = _setup_two_player_game_custom(
            app, socketio, player1, player2, holdem_table,
            buy_in1=40, buy_in2=200
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # p1 (SB) should be current player pre-flop
        assert game.current_player is not None
        cp = game.current_player
        cp_sio = sio1 if cp.id == player1.id else sio2
        other_sio = sio2 if cp.id == player1.id else sio1
        other_id = player2.id if cp.id == player1.id else player1.id

        # Current player goes all-in
        cp_stack = game.table.players[cp.id].stack
        cp_sio.get_received()
        other_sio.get_received()
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'raise', 'amount': cp_stack + game.betting.current_bets.get(cp.id, type('', (), {'amount': 0})).amount
        })
        all_events = list(sio1.get_received()) + list(sio2.get_received())

        # Other player calls
        other_sio.emit('player_action', {
            'table_id': table_id, 'action': 'call',
            'amount': game.betting.current_bet
        })
        all_events.extend(sio1.get_received())
        all_events.extend(sio2.get_received())

        # Play through remaining streets (game should handle all-in progression)
        remaining_events = _collect_events_through_hand(
            game, sio1, sio2, player1.id, table_id
        )
        all_events.extend(remaining_events)

        # Hand should be complete
        assert game.state in [GameState.COMPLETE, GameState.SHOWDOWN], \
            f"Expected hand complete, got state: {game.state}"

        # Should have hand_complete event
        hc_events = [e for e in all_events if e['name'] == 'hand_complete']
        assert len(hc_events) >= 1, \
            f"No hand_complete event. Events: {set(e['name'] for e in all_events)}"

        hc_data = hc_events[0]['args'][0]
        results = hc_data.get('hand_results', {})
        assert results.get('total_pot', 0) > 0

        # Chip conservation
        p1_stack = game.table.players[player1.id].stack
        p2_stack = game.table.players[player2.id].stack
        assert p1_stack + p2_stack == 240, \
            f"Expected 240 total chips, got {p1_stack + p2_stack}"

        sio1.disconnect()
        sio2.disconnect()

    def test_all_in_shows_zero_stack_in_game_state(self, app, socketio, player1, player2, holdem_table):
        """After going all-in, game_state_update shows chip_stack=0."""
        _, sio1, _, sio2, table_id = _setup_two_player_game_custom(
            app, socketio, player1, player2, holdem_table,
            buy_in1=40, buy_in2=200
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        cp = game.current_player
        cp_sio = sio1 if cp.id == player1.id else sio2
        other_sio = sio2 if cp.id == player1.id else sio1
        cp_id = cp.id

        # Go all-in
        cp_total = game.table.players[cp_id].stack + game.betting.current_bets.get(cp_id, type('', (), {'amount': 0})).amount
        sio1.get_received()
        sio2.get_received()
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'raise', 'amount': cp_total
        })
        sio1.get_received()
        sio2.get_received()

        # Request game state to check the all-in player's stack
        cp_sio.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(cp_sio)
        assert state is not None, "Should receive game state"

        # Find the all-in player in state
        player_states = {p['user_id']: p for p in state['players']}
        assert player_states[cp_id]['chip_stack'] == 0, \
            f"Expected 0 chips after all-in, got {player_states[cp_id]['chip_stack']}"

        sio1.disconnect()
        sio2.disconnect()

    def test_both_all_in_game_completes(self, app, socketio, player1, player2, holdem_table):
        """Both players all-in pre-flop, hand runs to showdown automatically."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        cp = game.current_player
        cp_sio = sio1 if cp.id == player1.id else sio2
        other_id = player2.id if cp.id == player1.id else player1.id
        other_sio = sio2 if cp.id == player1.id else sio1

        sio1.get_received()
        sio2.get_received()

        # Current player raises all-in (100 total)
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'raise', 'amount': 100
        })
        sio1.get_received()
        sio2.get_received()

        # Other player calls all-in
        other_sio.emit('player_action', {
            'table_id': table_id, 'action': 'call', 'amount': 100
        })
        all_events = list(sio1.get_received()) + list(sio2.get_received())

        # Both are all-in, hand should auto-complete through remaining streets
        remaining = _collect_events_through_hand(
            game, sio1, sio2, player1.id, table_id
        )
        all_events.extend(remaining)

        assert game.state in [GameState.COMPLETE, GameState.SHOWDOWN], \
            f"Expected complete, got {game.state}"

        hc_events = [e for e in all_events if e['name'] == 'hand_complete']
        assert len(hc_events) >= 1, "Should have hand_complete event"

        results = hc_events[0]['args'][0].get('hand_results', {})
        assert results.get('total_pot') == 200, \
            f"Expected pot of 200, got {results.get('total_pot')}"

        # Chip conservation
        total = game.table.players[player1.id].stack + game.table.players[player2.id].stack
        assert total == 200

        sio1.disconnect()
        sio2.disconnect()


class TestSplitPotViaSocketIO:
    """Test split pot scenarios through the SocketIO layer."""

    def test_split_pot_hand_complete_event(self, app, socketio, player1, player2, holdem_table):
        """When the board plays (both players tie), hand_complete shows split."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # Inject a board that guarantees a split: a straight on board
        # that both players will play regardless of hole cards.
        # First, find what cards are already dealt to avoid duplicates.
        from generic_poker.core.card import Card, Rank, Suit
        dealt = set()
        for p in game.table.players.values():
            for c in p.hand.cards:
                dealt.add((c.rank, c.suit))

        # Pick 5 board cards forming a straight (AKQJT) using suits not in dealt
        target = [
            (Rank.ACE, [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]),
            (Rank.KING, [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]),
            (Rank.QUEEN, [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]),
            (Rank.JACK, [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]),
            (Rank.TEN, [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]),
        ]
        board_cards = []
        suits_used = set()
        for rank, suit_options in target:
            for suit in suit_options:
                if (rank, suit) not in dealt and suit not in suits_used:
                    board_cards.append(Card(rank, suit))
                    suits_used.add(suit)  # Different suit per card to avoid flush
                    break
            else:
                # Fallback: use any non-dealt suit
                for suit in suit_options:
                    if (rank, suit) not in dealt:
                        board_cards.append(Card(rank, suit))
                        break

        assert len(board_cards) == 5, f"Could not build board, got {len(board_cards)}"

        # Replace the top 5 cards of the remaining deck
        remaining = game.table.deck.cards
        for i in range(5):
            remaining[-(i+1)] = board_cards[i]

        # Play the hand check/call through to showdown
        all_events = _collect_events_through_hand(
            game, sio1, sio2, player1.id, table_id
        )

        assert game.state in [GameState.COMPLETE, GameState.SHOWDOWN]

        hc_events = [e for e in all_events if e['name'] == 'hand_complete']
        assert len(hc_events) >= 1, "Should have hand_complete event"

        results = hc_events[0]['args'][0].get('hand_results', {})
        pots = results.get('pots', [])
        assert len(pots) >= 1, f"Expected at least 1 pot, got {pots}"

        # The pot should be split between both players
        main_pot = pots[0]
        winners = main_pot.get('winners', [])
        assert len(winners) == 2, \
            f"Expected 2 winners (split), got {len(winners)}: {winners}"

        # Chip conservation
        total = game.table.players[player1.id].stack + game.table.players[player2.id].stack
        assert total == 200, f"Expected 200 total, got {total}"

        sio1.disconnect()
        sio2.disconnect()


class TestRaiseViaSocketIO:
    """Test raise/re-raise sequences through the SocketIO layer."""

    def test_raise_and_call_via_socketio(self, app, socketio, player1, player2, holdem_table):
        """Raise then call via SocketIO events, verify pot and stacks."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        cp = game.current_player
        cp_sio = sio1 if cp.id == player1.id else sio2
        other_id = player2.id if cp.id == player1.id else player1.id
        other_sio = sio2 if cp.id == player1.id else sio1

        sio1.get_received()
        sio2.get_received()

        # Current player raises to 10
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'raise', 'amount': 10
        })
        sio1.get_received()
        sio2.get_received()

        # Other player calls
        other_sio.emit('player_action', {
            'table_id': table_id, 'action': 'call', 'amount': 10
        })
        sio1.get_received()
        sio2.get_received()

        # Verify pot via game state
        cp_sio.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(cp_sio)
        assert state is not None

        pot = state.get('pot_info', {}).get('total_pot', 0)
        assert pot == 20, f"Expected pot of 20 after raise + call, got {pot}"

        # Stacks: each put in 10
        player_stacks = {p['user_id']: p['chip_stack'] for p in state['players']}
        for uid, stack in player_stacks.items():
            assert stack == 90, f"Expected 90 chips for {uid}, got {stack}"

        sio1.disconnect()
        sio2.disconnect()

    def test_raise_reraise_call_via_socketio(self, app, socketio, player1, player2, holdem_table):
        """Raise, re-raise, call sequence via SocketIO."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        cp = game.current_player
        cp_sio = sio1 if cp.id == player1.id else sio2
        other_id = player2.id if cp.id == player1.id else player1.id
        other_sio = sio2 if cp.id == player1.id else sio1

        sio1.get_received()
        sio2.get_received()

        # p1 raises to 6
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'raise', 'amount': 6
        })
        sio1.get_received()
        sio2.get_received()

        # p2 3-bets to 18
        other_sio.emit('player_action', {
            'table_id': table_id, 'action': 'raise', 'amount': 18
        })
        sio1.get_received()
        sio2.get_received()

        # p1 calls the 3-bet
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'call', 'amount': 18
        })
        sio1.get_received()
        sio2.get_received()

        # Verify pot = 36
        cp_sio.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(cp_sio)
        pot = state.get('pot_info', {}).get('total_pot', 0)
        assert pot == 36, f"Expected pot of 36 after raise/3-bet/call, got {pot}"

        sio1.disconnect()
        sio2.disconnect()

    def test_post_flop_bet_raise_via_socketio(self, app, socketio, player1, player2, holdem_table):
        """Post-flop bet and raise via SocketIO."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # Play through pre-flop: SB calls, BB checks
        cp = game.current_player
        cp_sio = sio1 if cp.id == player1.id else sio2
        other_sio = sio2 if cp.id == player1.id else sio1

        sio1.get_received()
        sio2.get_received()

        # SB calls
        cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'call', 'amount': 2
        })
        sio1.get_received()
        sio2.get_received()

        # BB checks
        other_sio.emit('player_action', {
            'table_id': table_id, 'action': 'check', 'amount': 0
        })
        sio1.get_received()
        sio2.get_received()

        # Now on flop - find who acts first (BB acts first post-flop in heads up)
        assert game.state == GameState.BETTING, f"Expected BETTING, got {game.state}"
        flop_cp = game.current_player
        assert flop_cp is not None, "Should have a current player on flop"

        flop_cp_sio = sio1 if flop_cp.id == player1.id else sio2
        flop_other_sio = sio2 if flop_cp.id == player1.id else sio1

        # First player bets 10
        flop_cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'bet', 'amount': 10
        })
        sio1.get_received()
        sio2.get_received()

        # Other player raises to 30
        flop_other_sio.emit('player_action', {
            'table_id': table_id, 'action': 'raise', 'amount': 30
        })
        sio1.get_received()
        sio2.get_received()

        # First player calls
        flop_cp_sio.emit('player_action', {
            'table_id': table_id, 'action': 'call', 'amount': 30
        })
        sio1.get_received()
        sio2.get_received()

        # Pot should be 4 (preflop) + 60 (flop: 30 each) = 64
        flop_cp_sio.emit('request_game_state', {'table_id': table_id})
        state = _get_last_game_state(flop_cp_sio)
        pot = state.get('pot_info', {}).get('total_pot', 0)
        assert pot == 64, f"Expected pot of 64, got {pot}"

        sio1.disconnect()
        sio2.disconnect()


# ── Draw Game Fixtures & Helpers ─────────────────────────────────────────────

@pytest.fixture
def draw_table(app, player1):
    """Create a 5-Card Draw table."""
    table_manager = TableManager()
    config = TableConfig(
        name="Test 5-Card Draw",
        variant="5_card_draw",
        betting_structure=BettingStructure.LIMIT,
        stakes={'small_blind': 1, 'big_blind': 2, 'small_bet': 2, 'big_bet': 4},
        max_players=6,
        is_private=False,
        allow_bots=False
    )
    return table_manager.create_table(player1.id, config)


def _setup_draw_game(app, socketio, player1, player2, draw_table):
    """Join both players, connect to room, set ready, start hand for draw game.

    Returns (sio1, sio2, table_id).
    """
    table_id = str(draw_table.id)

    http1, sio1 = _login_and_connect(app, socketio, player1)
    http1.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': 100, 'seat_number': 1
    })

    http2, sio2 = _login_and_connect(app, socketio, player2)
    http2.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': 100, 'seat_number': 2
    })

    sio1.get_received()
    sio2.get_received()
    sio1.emit('connect_to_table_room', {'table_id': table_id})
    sio2.emit('connect_to_table_room', {'table_id': table_id})
    sio1.get_received()
    sio2.get_received()

    sio1.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    return sio1, sio2, table_id


def _advance_through_betting(game):
    """Advance through a betting round (all players check/call).

    Handles auto_progress=False by manually calling _next_step() after
    the round completes (advance_step=True).
    """
    for _ in range(20):
        if game.state != GameState.BETTING:
            break
        cp = game.current_player
        if not cp:
            break
        actions = game.get_valid_actions(cp.id)
        action_names = [a[0].value for a in actions]
        if 'call' in action_names:
            call_action = [a for a in actions if a[0] == PlayerAction.CALL][0]
            result = game.player_action(cp.id, PlayerAction.CALL, call_action[1])
        elif 'check' in action_names:
            result = game.player_action(cp.id, PlayerAction.CHECK, 0)
        else:
            break
        # With auto_progress=False, manually advance when round completes
        if result.advance_step and not game.auto_progress and game.state != GameState.COMPLETE:
            game._next_step()
            _advance_through_non_player_steps(game)


def _advance_through_non_player_steps(game):
    """Auto-advance through dealing and other non-player-input steps."""
    for _ in range(20):
        if game.state == GameState.COMPLETE:
            break
        if game.current_step >= len(game.rules.gameplay):
            break
        if game.state == GameState.DEALING:
            game._next_step()
        elif game.state == GameState.BETTING and game.current_player is None:
            game._next_step()
        else:
            break


class TestDrawGameplay:
    """Test draw game support through the online platform."""

    def test_draw_game_phase_appears_in_state(self, app, socketio, player1, player2, draw_table):
        """5-Card Draw shows drawing phase and draw actions after initial bet."""
        sio1, sio2, table_id = _setup_draw_game(app, socketio, player1, player2, draw_table)

        session = game_orchestrator.get_session(table_id)
        assert session is not None
        game = session.game
        assert game is not None

        # Game starts with blinds posted, then deal, then initial bet round
        assert game.state == GameState.BETTING, f"Expected BETTING, got {game.state}"

        # Advance through initial betting (handles auto_progress=False)
        _advance_through_betting(game)

        assert game.state == GameState.DRAWING, f"Expected DRAWING after betting, got {game.state}"

        # Verify game state view shows drawing phase
        from online_poker.services.game_state_manager import GameStateManager
        state_view = GameStateManager.generate_game_state_view(table_id, player1.id)
        assert state_view is not None
        assert state_view.game_phase.value == "drawing"

        # Check valid actions include draw for the current player
        current_id = game.current_player.id
        draw_state = GameStateManager.generate_game_state_view(table_id, current_id)
        assert draw_state is not None
        action_types = [a.action_type.value for a in draw_state.valid_actions]
        assert 'draw' in action_types, f"Expected 'draw' in actions, got {action_types}"

        # Verify draw action has correct min/max
        draw_action = [a for a in draw_state.valid_actions if a.action_type.value == 'draw'][0]
        assert draw_action.min_amount == 0, "Draw min should be 0 (stand pat allowed)"
        assert draw_action.max_amount == 5, "Draw max should be 5"

        sio1.disconnect()
        sio2.disconnect()

    def test_draw_action_replaces_cards(self, app, socketio, player1, player2, draw_table):
        """Player submits draw action and cards are replaced."""
        sio1, sio2, table_id = _setup_draw_game(app, socketio, player1, player2, draw_table)

        session = game_orchestrator.get_session(table_id)
        game = session.game

        _advance_through_betting(game)
        assert game.state == GameState.DRAWING

        # Get current player and their cards
        cp = game.current_player
        assert cp is not None
        original_cards = list(cp.hand.cards)
        assert len(original_cards) == 5, f"Expected 5 cards, got {len(original_cards)}"

        # Select 2 cards to discard
        cards_to_discard = original_cards[:2]

        # Submit draw action
        result = game.player_action(cp.id, PlayerAction.DRAW, 0, cards=cards_to_discard)
        assert result.success, f"Draw action failed: {result.error}"

        # Verify player still has 5 cards but 2 are different
        new_cards = list(cp.hand.cards)
        assert len(new_cards) == 5, f"Expected 5 cards after draw, got {len(new_cards)}"

        # The cards that weren't discarded should still be there
        kept_cards = original_cards[2:]
        for card in kept_cards:
            assert card in new_cards, f"Kept card {card} missing from hand after draw"

        sio1.disconnect()
        sio2.disconnect()

    def test_full_five_card_draw_hand(self, app, socketio, player1, player2, draw_table):
        """Complete hand: deal -> bet -> draw -> bet -> showdown."""
        sio1, sio2, table_id = _setup_draw_game(app, socketio, player1, player2, draw_table)

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # Phase 1: Initial betting round
        assert game.state == GameState.BETTING
        _advance_through_betting(game)

        # Phase 2: Draw round
        assert game.state == GameState.DRAWING, f"Expected DRAWING, got {game.state}"

        # First player discards 2 cards
        cp1 = game.current_player
        cards_to_discard = list(cp1.hand.cards)[:2]
        result1 = game.player_action(cp1.id, PlayerAction.DRAW, 0, cards=cards_to_discard)
        assert result1.success, f"First player draw failed: {result1.error}"
        # With auto_progress=False, manually advance if round complete
        if result1.advance_step and not game.auto_progress:
            game._next_step()
            _advance_through_non_player_steps(game)

        # Second player stands pat (discard 0 cards)
        if game.state == GameState.DRAWING and game.current_player:
            cp2 = game.current_player
            result2 = game.player_action(cp2.id, PlayerAction.DRAW, 0, cards=[])
            assert result2.success, f"Second player draw failed: {result2.error}"
            if result2.advance_step and not game.auto_progress:
                game._next_step()
                _advance_through_non_player_steps(game)

        # Phase 3: Final betting round
        assert game.state == GameState.BETTING, f"Expected BETTING after draw, got {game.state}"
        _advance_through_betting(game)

        # Phase 4: Game should be complete
        assert game.state in (GameState.SHOWDOWN, GameState.COMPLETE), \
            f"Expected SHOWDOWN or COMPLETE, got {game.state}"

        # Verify hand results
        results = game.get_hand_results()
        assert results is not None
        assert results.is_complete
        assert len(results.pots) > 0

        sio1.disconnect()
        sio2.disconnect()

    def test_draw_action_via_http_api(self, app, socketio, player1, player2, draw_table):
        """Draw action works through the HTTP API with cards parameter."""
        sio1, sio2, table_id = _setup_draw_game(app, socketio, player1, player2, draw_table)

        session = game_orchestrator.get_session(table_id)
        game = session.game

        _advance_through_betting(game)
        assert game.state == GameState.DRAWING

        # Get current player and their cards as strings
        cp = game.current_player
        cards_to_discard = [str(c) for c in list(cp.hand.cards)[:1]]  # Discard 1 card

        # Log in as the current player via HTTP
        if cp.id == player1.id:
            test_username = player1._test_username
        else:
            test_username = player2._test_username

        http_client = app.test_client()
        http_client.post('/auth/api/login', json={
            'username': test_username, 'password': 'password123'
        })

        # Send draw action via HTTP API
        resp = http_client.post(f'/game/sessions/{table_id}/action', json={
            'action': 'draw',
            'cards': cards_to_discard
        })

        assert resp.status_code == 200, f"HTTP draw action failed: {resp.get_json()}"
        result = resp.get_json()
        assert result['success'], f"Draw action not successful: {result}"

        sio1.disconnect()
        sio2.disconnect()


# ── Pass Game Fixtures & Helpers ─────────────────────────────────────────────

@pytest.fixture
def player3(app):
    """Create third test player."""
    uid = str(uuid.uuid4())[:8]
    user = UserManager.create_user(f"charlie_{uid}", f"charlie_{uid}@test.com", "password123")
    UserManager.update_user_bankroll(user.id, 1000)
    user._test_username = f"charlie_{uid}"
    return user


@pytest.fixture
def pass_table(app, player1):
    """Create a Pass the Pineapple table."""
    table_manager = TableManager()
    config = TableConfig(
        name="Test Pass the Pineapple",
        variant="pass_the_pineapple",
        betting_structure=BettingStructure.LIMIT,
        stakes={'small_blind': 5, 'big_blind': 10, 'small_bet': 10, 'big_bet': 20},
        max_players=9,
        is_private=False,
        allow_bots=False
    )
    return table_manager.create_table(player1.id, config)


def _setup_pass_game(app, socketio, player1, player2, player3, pass_table):
    """Join 3 players, connect, set ready, start hand for pass game.

    Returns (sio1, sio2, sio3, table_id).
    """
    table_id = str(pass_table.id)

    http1, sio1 = _login_and_connect(app, socketio, player1)
    http1.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': 200, 'seat_number': 1
    })

    http2, sio2 = _login_and_connect(app, socketio, player2)
    http2.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': 200, 'seat_number': 2
    })

    http3, sio3 = _login_and_connect(app, socketio, player3)
    http3.post(f'/api/tables/{table_id}/join', json={
        'buy_in_amount': 200, 'seat_number': 3
    })

    # Drain events
    sio1.get_received()
    sio2.get_received()
    sio3.get_received()

    sio1.emit('connect_to_table_room', {'table_id': table_id})
    sio2.emit('connect_to_table_room', {'table_id': table_id})
    sio3.emit('connect_to_table_room', {'table_id': table_id})
    sio1.get_received()
    sio2.get_received()
    sio3.get_received()

    sio1.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()
    sio3.get_received()

    sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()
    sio3.get_received()

    sio3.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()
    sio3.get_received()

    return sio1, sio2, sio3, table_id


class TestPassGameplay:
    """Test pass (card passing) game support through the online platform."""

    def test_pass_phase_appears_in_state(self, app, socketio, player1, player2, player3, pass_table):
        """Pass the Pineapple shows drawing phase with pass actions after flop bet."""
        sio1, sio2, sio3, table_id = _setup_pass_game(
            app, socketio, player1, player2, player3, pass_table
        )

        session = game_orchestrator.get_session(table_id)
        assert session is not None
        game = session.game
        assert game is not None

        # Game starts with blinds posted, then deal, then pre-flop bet
        assert game.state == GameState.BETTING, f"Expected BETTING, got {game.state}"

        # Advance through pre-flop betting
        _advance_through_betting(game)

        # Should be dealing flop
        _advance_through_non_player_steps(game)

        # Post-flop betting
        if game.state == GameState.BETTING:
            _advance_through_betting(game)

        # Should now be in DRAWING state (pass phase)
        assert game.state == GameState.DRAWING, f"Expected DRAWING for pass phase, got {game.state}"

        # Verify game state view shows drawing phase
        from online_poker.services.game_state_manager import GameStateManager
        current_id = game.current_player.id
        state_view = GameStateManager.generate_game_state_view(table_id, current_id)
        assert state_view is not None
        assert state_view.game_phase.value == "drawing"

        # Check valid actions include pass for the current player
        action_types = [a.action_type.value for a in state_view.valid_actions]
        assert 'pass' in action_types, f"Expected 'pass' in actions, got {action_types}"

        # Verify pass action has correct min/max (1 card)
        pass_action = [a for a in state_view.valid_actions if a.action_type.value == 'pass'][0]
        assert pass_action.min_amount == 1, f"Pass min should be 1, got {pass_action.min_amount}"
        assert pass_action.max_amount == 1, f"Pass max should be 1, got {pass_action.max_amount}"

        sio1.disconnect()
        sio2.disconnect()
        sio3.disconnect()

    def test_full_pass_the_pineapple_hand(self, app, socketio, player1, player2, player3, pass_table):
        """Complete hand: deal -> bet -> flop -> bet -> pass -> deal turn -> bet -> river -> bet -> showdown."""
        sio1, sio2, sio3, table_id = _setup_pass_game(
            app, socketio, player1, player2, player3, pass_table
        )

        session = game_orchestrator.get_session(table_id)
        game = session.game

        # Phase 1: Pre-flop betting
        assert game.state == GameState.BETTING
        _advance_through_betting(game)
        _advance_through_non_player_steps(game)

        # Phase 2: Post-flop betting
        if game.state == GameState.BETTING:
            _advance_through_betting(game)

        # Phase 3: Pass round
        assert game.state == GameState.DRAWING, f"Expected DRAWING for pass, got {game.state}"

        # Each player passes 1 card
        for _ in range(3):
            cp = game.current_player
            assert cp is not None, "Expected current player for pass action"
            cards_to_pass = [cp.hand.cards[0]]  # Pass first card
            result = game.player_action(cp.id, PlayerAction.PASS, cards=cards_to_pass)
            assert result.success, f"Pass action failed: {result.error}"
            if result.advance_step and not game.auto_progress and game.state != GameState.COMPLETE:
                game._next_step()
                _advance_through_non_player_steps(game)

        # Phase 4: Turn betting
        if game.state == GameState.BETTING:
            _advance_through_betting(game)
            _advance_through_non_player_steps(game)

        # Phase 5: River betting
        if game.state == GameState.BETTING:
            _advance_through_betting(game)

        # Phase 6: Game should be complete
        assert game.state in (GameState.SHOWDOWN, GameState.COMPLETE), \
            f"Expected SHOWDOWN or COMPLETE, got {game.state}"

        # Verify hand results
        results = game.get_hand_results()
        assert results is not None
        assert results.is_complete
        assert len(results.pots) > 0

        sio1.disconnect()
        sio2.disconnect()
        sio3.disconnect()


# ── Expose Game Tests ─────────────────────────────────────────────────────────

@pytest.fixture
def expose_table(app, player1):
    """Create a Showmaha table (expose 2 of 4 hole cards after flop)."""
    table_manager = TableManager()
    config = TableConfig(
        name="Test Showmaha",
        variant="showmaha",
        betting_structure=BettingStructure.LIMIT,
        stakes={'small_blind': 5, 'big_blind': 10, 'small_bet': 10, 'big_bet': 20},
        max_players=9,
        is_private=False,
        allow_bots=False
    )
    return table_manager.create_table(player1.id, config)


def _setup_expose_game(app, socketio, player1, player2, expose_table):
    """Join both players, connect, set ready for expose game."""
    table_id = str(expose_table.id)

    http1, sio1 = _login_and_connect(app, socketio, player1)
    http1.post(f'/api/tables/{table_id}/join', json={'buy_in_amount': 500, 'seat_number': 1})

    http2, sio2 = _login_and_connect(app, socketio, player2)
    http2.post(f'/api/tables/{table_id}/join', json={'buy_in_amount': 500, 'seat_number': 2})

    sio1.get_received()
    sio2.get_received()
    sio1.emit('connect_to_table_room', {'table_id': table_id})
    sio2.emit('connect_to_table_room', {'table_id': table_id})
    sio1.get_received()
    sio2.get_received()

    sio1.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    return sio1, sio2, table_id


class TestExposeGameplay:
    """Test expose action through the online platform."""

    def test_expose_action_completes_hand(self, app, socketio, player1, player2, expose_table):
        """Showmaha game: deal 4 cards, bet, flop, expose 2, bet through to completion."""
        sio1, sio2, table_id = _setup_expose_game(app, socketio, player1, player2, expose_table)

        session = game_orchestrator.get_session(table_id)
        assert session is not None
        game = session.game
        assert game is not None

        # Advance through initial deal and pre-flop betting
        _advance_through_non_player_steps(game)
        if game.state == GameState.BETTING:
            _advance_through_betting(game)
            _advance_through_non_player_steps(game)

        # Should reach flop deal, then expose phase
        if game.state == GameState.BETTING:
            _advance_through_betting(game)
            _advance_through_non_player_steps(game)

        # Now should be in DRAWING state for expose
        if game.state == GameState.DRAWING:
            from generic_poker.core.card import Visibility
            for _ in range(10):
                if game.state != GameState.DRAWING:
                    break
                cp = game.current_player
                if not cp:
                    break
                actions = game.get_valid_actions(cp.id)
                expose_actions = [a for a in actions if a[0] == PlayerAction.EXPOSE]
                if not expose_actions:
                    break
                _, min_expose, max_expose = expose_actions[0]
                hand_cards = list(cp.hand.cards)
                face_down = [c for c in hand_cards if c.visibility == Visibility.FACE_DOWN]
                to_expose = face_down[:max_expose]
                result = game.player_action(cp.id, PlayerAction.EXPOSE, cards=to_expose)
                if result.advance_step and not game.auto_progress and game.state != GameState.COMPLETE:
                    game._next_step()
                    _advance_through_non_player_steps(game)

        # Continue through remaining betting rounds
        for _ in range(10):
            if game.state == GameState.COMPLETE:
                break
            if game.state == GameState.BETTING:
                _advance_through_betting(game)
                _advance_through_non_player_steps(game)
            elif game.state == GameState.DRAWING:
                break  # Shouldn't happen again
            elif game.state in (GameState.DEALING, GameState.SHOWDOWN):
                game._next_step()
                _advance_through_non_player_steps(game)

        assert game.state in (GameState.SHOWDOWN, GameState.COMPLETE), \
            f"Expected SHOWDOWN or COMPLETE, got {game.state} at step {game.current_step}"

        results = game.get_hand_results()
        assert results is not None
        assert results.is_complete

        sio1.disconnect()
        sio2.disconnect()


# ── Separate Game Tests ───────────────────────────────────────────────────────

@pytest.fixture
def separate_table(app, player1):
    """Create a Double Hold'em table (separate 3 cards into Point/Left/Right)."""
    table_manager = TableManager()
    config = TableConfig(
        name="Test Double Hold'em",
        variant="double_hold_em",
        betting_structure=BettingStructure.LIMIT,
        stakes={'small_blind': 5, 'big_blind': 10, 'small_bet': 10, 'big_bet': 20},
        max_players=7,
        is_private=False,
        allow_bots=False
    )
    return table_manager.create_table(player1.id, config)


def _setup_separate_game(app, socketio, player1, player2, separate_table):
    """Join both players, connect, set ready for separate game."""
    table_id = str(separate_table.id)

    http1, sio1 = _login_and_connect(app, socketio, player1)
    http1.post(f'/api/tables/{table_id}/join', json={'buy_in_amount': 500, 'seat_number': 1})

    http2, sio2 = _login_and_connect(app, socketio, player2)
    http2.post(f'/api/tables/{table_id}/join', json={'buy_in_amount': 500, 'seat_number': 2})

    sio1.get_received()
    sio2.get_received()
    sio1.emit('connect_to_table_room', {'table_id': table_id})
    sio2.emit('connect_to_table_room', {'table_id': table_id})
    sio1.get_received()
    sio2.get_received()

    sio1.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    sio2.emit('set_ready', {'table_id': table_id, 'ready': True})
    sio1.get_received()
    sio2.get_received()

    return sio1, sio2, table_id


class TestSeparateGameplay:
    """Test separate action through the online platform."""

    def test_separate_action_completes_hand(self, app, socketio, player1, player2, separate_table):
        """Double Hold'em: deal 3 cards, separate into subsets, play to completion."""
        sio1, sio2, table_id = _setup_separate_game(app, socketio, player1, player2, separate_table)

        session = game_orchestrator.get_session(table_id)
        assert session is not None
        game = session.game
        assert game is not None

        # Advance through initial steps
        _advance_through_non_player_steps(game)

        # Play through all phases
        for _ in range(50):
            if game.state == GameState.COMPLETE:
                break
            if game.state == GameState.BETTING:
                _advance_through_betting(game)
                _advance_through_non_player_steps(game)
            elif game.state == GameState.DRAWING:
                # Separate phase
                cp = game.current_player
                if not cp:
                    game._next_step()
                    _advance_through_non_player_steps(game)
                    continue
                actions = game.get_valid_actions(cp.id)
                sep_actions = [a for a in actions if a[0] == PlayerAction.SEPARATE]
                if sep_actions:
                    _, total, _ = sep_actions[0]
                    hand_cards = list(cp.hand.cards)
                    result = game.player_action(cp.id, PlayerAction.SEPARATE, cards=hand_cards[:total])
                    if result.advance_step and not game.auto_progress and game.state != GameState.COMPLETE:
                        game._next_step()
                        _advance_through_non_player_steps(game)
                else:
                    break
            elif game.state in (GameState.DEALING, GameState.SHOWDOWN):
                game._next_step()
                _advance_through_non_player_steps(game)

        assert game.state in (GameState.SHOWDOWN, GameState.COMPLETE), \
            f"Expected SHOWDOWN or COMPLETE, got {game.state} at step {game.current_step}"

        results = game.get_hand_results()
        assert results is not None
        assert results.is_complete

        sio1.disconnect()
        sio2.disconnect()
