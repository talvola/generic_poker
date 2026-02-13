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
from online_poker.services.websocket_manager import init_websocket_manager
from online_poker.services.user_manager import UserManager
from online_poker.services.table_manager import TableManager
from online_poker.services.table_access_manager import TableAccessManager
from online_poker.services.game_orchestrator import game_orchestrator
from online_poker.services.disconnect_manager import disconnect_manager
from online_poker.models.table_config import TableConfig
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game_state import GameState


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
        """When a player leaves during a game, they are removed from the game session."""
        sio1, sio2, table_id = _setup_two_player_game(
            app, socketio, player1, player2, holdem_table
        )

        session = game_orchestrator.get_session(table_id)
        assert player1.id in session.connected_players
        assert player2.id in session.connected_players

        # Player 1 leaves
        sio1.emit('leave_table', {'table_id': table_id})
        sio1.get_received()

        # Player 1 should be removed from game session
        assert player1.id not in session.connected_players, \
            "Player 1 should be removed from game session after leaving"
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
