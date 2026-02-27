"""Integration tests for bot support in the online platform.

Tests the fill_bots flow, game state rendering with bots, seat assignment,
and ready status with mixed human+bot players.

Layer 2 tests: Use flask_socketio.test_client (no browser).
"""

import uuid

import pytest
from flask import Flask, g
from flask_socketio import SocketIO
from sqlalchemy.pool import StaticPool

from generic_poker.game.betting import BettingStructure
from online_poker.auth import init_login_manager
from online_poker.database import db
from online_poker.models.table_config import TableConfig
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.game_routes import game_bp
from online_poker.routes.lobby_routes import lobby_bp, register_lobby_socket_events
from online_poker.services.disconnect_manager import disconnect_manager
from online_poker.services.game_orchestrator import game_orchestrator
from online_poker.services.table_manager import TableManager
from online_poker.services.user_manager import UserManager
from online_poker.services.websocket_manager import init_websocket_manager


def _patch_socketio_user_loading(socketio_instance):
    """Fix Flask-Login user caching with multiple SocketIO test clients."""
    original = socketio_instance._handle_event

    def patched_handle_event(handler, message, namespace, sid, *args):
        original_handler = handler

        def clearing_handler(*a, **kw):
            g.pop("_login_user", None)
            return original_handler(*a, **kw)

        return original(clearing_handler, message, namespace, sid, *args)

    socketio_instance._handle_event = patched_handle_event


@pytest.fixture
def app_and_socketio():
    """Create test Flask app with SocketIO."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    db.init_app(app)

    init_login_manager(app)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(lobby_bp)
    app.register_blueprint(game_bp, url_prefix="/game")

    socketio = SocketIO(app, logger=False, engineio_logger=False)
    init_websocket_manager(socketio)
    register_lobby_socket_events(socketio)
    _patch_socketio_user_loading(socketio)

    with app.app_context():
        db.create_all()
        yield app, socketio
        for dp in disconnect_manager.disconnected_players.values():
            dp.cancel_timers()
        disconnect_manager.disconnected_players.clear()
        disconnect_manager.table_disconnects.clear()
        game_orchestrator.sessions.clear()
        # Clean up bot manager
        from online_poker.services.simple_bot import bot_manager

        bot_manager.bots.clear()
        db.drop_all()


@pytest.fixture
def app(app_and_socketio):
    return app_and_socketio[0]


@pytest.fixture
def socketio(app_and_socketio):
    return app_and_socketio[1]


@pytest.fixture
def player1(app):
    uid = str(uuid.uuid4())[:8]
    user = UserManager.create_user(f"human_{uid}", f"human_{uid}@test.com", "password123")
    UserManager.update_user_bankroll(user.id, 1000)
    user._test_username = f"human_{uid}"
    return user


@pytest.fixture
def bot_table(app, player1):
    """Create a table with allow_bots=True."""
    table_manager = TableManager()
    config = TableConfig(
        name="Bot Test Table",
        variant="hold_em",
        betting_structure=BettingStructure.NO_LIMIT,
        stakes={"small_blind": 1, "big_blind": 2},
        max_players=6,
        is_private=False,
        allow_bots=True,
    )
    return table_manager.create_table(player1.id, config)


@pytest.fixture
def bot_table_2seat(app, player1):
    """Create a 2-seat table with allow_bots=True."""
    table_manager = TableManager()
    config = TableConfig(
        name="Bot Test 2-Seat",
        variant="hold_em",
        betting_structure=BettingStructure.NO_LIMIT,
        stakes={"small_blind": 1, "big_blind": 2},
        max_players=2,
        is_private=False,
        allow_bots=True,
    )
    return table_manager.create_table(player1.id, config)


def _login_and_connect(app, socketio, user):
    """Log in via HTTP and create a SocketIO test client."""
    http_client = app.test_client()
    http_client.post("/auth/api/login", json={"username": user._test_username, "password": "password123"})
    sio_client = socketio.test_client(app, flask_test_client=http_client)
    return http_client, sio_client


def _get_events(sio_client, event_name=None):
    """Get received events, optionally filtered by name."""
    received = sio_client.get_received()
    if event_name:
        return [msg for msg in received if msg["name"] == event_name]
    return received


def _get_last_event(sio_client, event_name):
    """Get the most recent event of a given type."""
    events = _get_events(sio_client, event_name)
    if events:
        return events[-1]["args"][0]
    return None


class TestFillBotsFlow:
    """Test the fill_bots WebSocket event handler."""

    def test_fill_bots_adds_bots_to_empty_seats(self, app, socketio, player1, bot_table):
        """fill_bots should add bots to all seats except the human's."""
        table_id = str(bot_table.id)

        # Human joins via HTTP
        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        # Connect to table room
        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        # Fill bots
        sio1.emit("fill_bots", {"table_id": table_id})
        received = sio1.get_received()

        # Check fill_bots_result
        fill_results = [msg for msg in received if msg["name"] == "fill_bots_result"]
        assert len(fill_results) == 1
        result = fill_results[0]["args"][0]
        assert result["success"] is True
        assert result["bots_added"] == 5  # 6 seats - 1 human = 5 bots

    def test_fill_bots_no_seat_conflict(self, app, socketio, player1, bot_table):
        """Bots should not be placed in the human's seat."""
        table_id = str(bot_table.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 3})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        # Verify no bot is at seat 3
        session = game_orchestrator.get_session(table_id)
        assert session is not None
        assert session.game is not None

        # Human should be at seat 3
        human_seat = session.game.table.layout.get_player_seat(player1.id)
        assert human_seat == 3

        # All occupied seats
        occupied = session.game.table.layout.get_occupied_seats()
        assert len(occupied) == 6  # 1 human + 5 bots
        assert 3 in occupied  # Human's seat

        # Verify bot IDs at other seats
        from online_poker.services.simple_bot import SimpleBot

        for pid, _player in session.game.table.players.items():
            seat = session.game.table.layout.get_player_seat(pid)
            if SimpleBot.is_bot_player(pid):
                assert seat != 3, f"Bot {pid} is at human's seat 3"

    def test_fill_bots_2seat_table(self, app, socketio, player1, bot_table_2seat):
        """On a 2-seat table, fill_bots should add exactly 1 bot."""
        table_id = str(bot_table_2seat.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        received = sio1.get_received()

        fill_results = [msg for msg in received if msg["name"] == "fill_bots_result"]
        assert len(fill_results) == 1
        assert fill_results[0]["args"][0]["bots_added"] == 1

    def test_fill_bots_not_allowed(self, app, socketio, player1):
        """fill_bots should fail if table doesn't allow bots."""
        table_manager = TableManager()
        config = TableConfig(
            name="No Bots Table",
            variant="hold_em",
            betting_structure=BettingStructure.NO_LIMIT,
            stakes={"small_blind": 1, "big_blind": 2},
            max_players=6,
            is_private=False,
            allow_bots=False,
        )
        table = table_manager.create_table(player1.id, config)
        table_id = str(table.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        received = sio1.get_received()

        error_events = [msg for msg in received if msg["name"] == "error"]
        assert len(error_events) >= 1
        assert "does not allow bots" in error_events[0]["args"][0]["message"]


class TestGameStateWithBots:
    """Test that game state correctly includes bot players."""

    def test_bots_appear_in_game_state(self, app, socketio, player1, bot_table_2seat):
        """After fill_bots, requesting game state should show both human and bot."""
        table_id = str(bot_table_2seat.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        # Request fresh game state
        sio1.emit("request_game_state", {"table_id": table_id})
        game_state = _get_last_event(sio1, "game_state_update")

        assert game_state is not None
        players = game_state["players"]
        assert len(players) == 2, f"Expected 2 players, got {len(players)}: {[p['username'] for p in players]}"

        # One human, one bot
        human_players = [p for p in players if not p["is_bot"]]
        bot_players = [p for p in players if p["is_bot"]]
        assert len(human_players) == 1
        assert len(bot_players) == 1

        # Human at seat 1, bot at seat 2
        assert human_players[0]["seat_number"] == 1
        assert bot_players[0]["seat_number"] == 2

    def test_bot_has_correct_properties(self, app, socketio, player1, bot_table_2seat):
        """Bot player in game state should have correct properties."""
        table_id = str(bot_table_2seat.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("request_game_state", {"table_id": table_id})
        game_state = _get_last_event(sio1, "game_state_update")

        bot_players = [p for p in game_state["players"] if p["is_bot"]]
        assert len(bot_players) == 1

        bot = bot_players[0]
        assert bot["is_bot"] is True
        assert bot["user_id"].startswith("bot_")
        assert bot["chip_stack"] > 0
        assert bot["username"]  # Has a name
        assert bot["seat_number"] == 2

    def test_6player_game_state_shows_all(self, app, socketio, player1, bot_table):
        """6-player table should show 1 human + 5 bots in game state."""
        table_id = str(bot_table.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("request_game_state", {"table_id": table_id})
        game_state = _get_last_event(sio1, "game_state_update")

        players = game_state["players"]
        assert len(players) == 6

        bot_players = [p for p in players if p["is_bot"]]
        assert len(bot_players) == 5

        # All should have unique seats
        seats = {p["seat_number"] for p in players}
        assert seats == {1, 2, 3, 4, 5, 6}


class TestReadyStatusWithBots:
    """Test ready status tracking with mixed human+bot players."""

    def test_bots_show_as_ready(self, app, socketio, player1, bot_table_2seat):
        """Bots should appear as ready in ready_status_update."""
        table_id = str(bot_table_2seat.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        received = sio1.get_received()

        # Find the ready_status_update after fill_bots
        ready_events = [msg for msg in received if msg["name"] == "ready_status_update"]
        assert len(ready_events) >= 1

        ready_status = ready_events[-1]["args"][0]["ready_status"]
        players = ready_status["players"]

        # Human not ready, bot ready
        human = [p for p in players if p["user_id"] == player1.id]
        bots = [p for p in players if p["user_id"].startswith("bot_")]

        assert len(human) == 1
        assert human[0]["is_ready"] is False

        assert len(bots) == 1
        assert bots[0]["is_ready"] is True

    def test_all_ready_when_human_readies(self, app, socketio, player1, bot_table_2seat):
        """When human clicks Ready and bots are present, all_ready should be True."""
        table_id = str(bot_table_2seat.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        # Human sets ready
        sio1.emit("set_ready", {"table_id": table_id, "ready": True})
        received = sio1.get_received()

        # Should get hand_starting or ready_status with all_ready=True
        hand_starting = [msg for msg in received if msg["name"] == "hand_starting"]
        ready_events = [msg for msg in received if msg["name"] == "ready_status_update"]

        # Either a hand started (all_ready triggered it) or ready status shows all_ready
        started = len(hand_starting) > 0
        all_ready = any(r["args"][0]["ready_status"].get("all_ready") for r in ready_events) if ready_events else False

        assert started or all_ready, "Expected hand to start or all_ready=True after human readied up"


class TestBotSeatAssignment:
    """Test that bots get assigned to correct seats."""

    def test_human_at_middle_seat(self, app, socketio, player1, bot_table):
        """Human at seat 4 of 6 — bots should fill seats 1,2,3,5,6."""
        table_id = str(bot_table.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 4})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        session = game_orchestrator.get_session(table_id)
        occupied = sorted(session.game.table.layout.get_occupied_seats())
        assert occupied == [1, 2, 3, 4, 5, 6]

        human_seat = session.game.table.layout.get_player_seat(player1.id)
        assert human_seat == 4

        from online_poker.services.simple_bot import SimpleBot

        bot_seats = sorted(
            session.game.table.layout.get_player_seat(pid)
            for pid in session.game.table.players
            if SimpleBot.is_bot_player(pid)
        )
        assert bot_seats == [1, 2, 3, 5, 6]


class TestPlayerActionWithBots:
    """Test that player actions work correctly in bot games."""

    def test_action_works_after_disconnect_reconnect(self, app, socketio, player1, bot_table_2seat):
        """Player dropped from connected_players should still be able to act
        if they are in game.table.players (e.g., after a brief disconnect)."""
        table_id = str(bot_table_2seat.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        session = game_orchestrator.get_session(table_id)
        assert session is not None

        # Verify human is in both connected_players and game.table.players
        assert player1.id in session.connected_players
        assert player1.id in session.game.table.players

        # Simulate disconnect: remove from connected_players (like handle_player_disconnect does)
        session.connected_players.discard(player1.id)
        session.disconnected_players[player1.id] = __import__("datetime").datetime.utcnow()
        assert player1.id not in session.connected_players
        assert player1.id in session.game.table.players

        # process_player_action should re-add to connected_players and succeed
        from generic_poker.game.game_state import PlayerAction

        # Start a hand first so we can test actions
        session.game.table.move_button()
        session.game.start_hand(shuffle_deck=True)

        # Advance through dealing steps
        while session.game.current_player is None and session.game.state.name != "COMPLETE":
            session.game._next_step()
            if session.game.current_step >= len(session.game.rules.gameplay):
                break

        # Try to fold (should work even though player was removed from connected_players)
        if session.game.current_player and session.game.current_player.id == player1.id:
            success, message, result = session.process_player_action(player1.id, PlayerAction.FOLD, 0)
            assert success, f"Action should succeed but failed: {message}"
            assert player1.id in session.connected_players, "Player should be re-added to connected_players"

    def test_action_fails_for_truly_absent_player(self, app, socketio, player1, bot_table_2seat):
        """Player not in connected_players AND not in game.table.players should fail."""
        table_id = str(bot_table_2seat.id)

        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        session = game_orchestrator.get_session(table_id)

        # Action from a non-existent player should fail
        from generic_poker.game.game_state import PlayerAction

        success, message, _result = session.process_player_action("nonexistent_player", PlayerAction.FOLD, 0)
        assert not success
        assert "not in game" in message.lower()


class TestBotGameplayFlow:
    """Test full hand gameplay with bots: start → play → showdown → next hand."""

    def _setup_and_start_hand(self, app, socketio, player1, bot_table_2seat):
        """Helper: join table, fill bots, start hand."""
        from generic_poker.game.game_state import GameState

        table_id = str(bot_table_2seat.id)
        http1, sio1 = _login_and_connect(app, socketio, player1)
        http1.post(f"/api/tables/{table_id}/join", json={"buy_in_amount": 100, "seat_number": 1})

        sio1.get_received()
        sio1.emit("connect_to_table_room", {"table_id": table_id})
        sio1.get_received()

        sio1.emit("fill_bots", {"table_id": table_id})
        sio1.get_received()

        session = game_orchestrator.get_session(table_id)
        assert len(session.game.table.players) == 2

        # Start hand directly (bypass ready panel for test simplicity)
        session.game.table.move_button()
        session.game.start_hand(shuffle_deck=True)

        # Advance through dealing steps until a player needs to act
        while session.game.current_player is None and session.game.state != GameState.COMPLETE:
            session.game._next_step()
            if session.game.current_step >= len(session.game.rules.gameplay):
                break

        assert session.game.current_player is not None, "Should have a current player after dealing"
        return table_id, session, sio1

    def test_full_hand_fold_win(self, app, socketio, player1, bot_table_2seat):
        """Play a hand where human folds → bot wins → hand completes."""
        from generic_poker.game.game_state import GameState, PlayerAction
        from online_poker.services.simple_bot import SimpleBot, bot_manager

        table_id, session, sio1 = self._setup_and_start_hand(app, socketio, player1, bot_table_2seat)
        game = session.game

        # Play through the hand: each player either folds (human) or calls/checks (bot)
        max_actions = 20
        for _ in range(max_actions):
            if game.state == GameState.COMPLETE:
                break

            cp = game.current_player
            if cp is None:
                # Advance through non-player steps
                if game.current_step < len(game.rules.gameplay):
                    game._next_step()
                    from online_poker.services.game_orchestrator import GameOrchestrator

                    GameOrchestrator.advance_through_non_player_steps(game)
                continue

            if cp.id == player1.id:
                # Human folds
                success, msg, result = session.process_player_action(player1.id, PlayerAction.FOLD, 0)
                assert success, f"Human fold failed: {msg}"
            elif SimpleBot.is_bot_player(cp.id):
                bot = bot_manager.get_bot(cp.id)
                valid_actions = game.get_valid_actions(cp.id)
                decision = bot.choose_action_full(valid_actions, game, cp.id)
                success, msg, result = session.process_player_action(
                    cp.id, decision.action, decision.amount or 0, cards=decision.cards
                )
                assert success, f"Bot action failed: {msg}"

            # Advance if needed
            if result and hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    from online_poker.services.game_orchestrator import GameOrchestrator

                    GameOrchestrator.advance_through_non_player_steps(game)

        # Hand should be complete
        assert game.state == GameState.COMPLETE, f"Hand should be COMPLETE but is {game.state}"

        # Hand results should exist
        hand_results = game.get_hand_results()
        assert hand_results is not None
        assert hand_results.is_complete

    def test_full_hand_to_showdown(self, app, socketio, player1, bot_table_2seat):
        """Play a hand all the way to showdown (nobody folds)."""
        from generic_poker.game.game_state import GameState, PlayerAction

        table_id, session, sio1 = self._setup_and_start_hand(app, socketio, player1, bot_table_2seat)
        game = session.game

        # Play through the entire hand: everyone checks/calls (no folding)
        max_actions = 50
        for _ in range(max_actions):
            if game.state == GameState.COMPLETE:
                break

            cp = game.current_player
            if cp is None:
                if game.current_step < len(game.rules.gameplay):
                    game._next_step()
                    from online_poker.services.game_orchestrator import GameOrchestrator

                    GameOrchestrator.advance_through_non_player_steps(game)
                else:
                    break
                continue

            # Both human and bot play passively (check or call)
            valid_actions = game.get_valid_actions(cp.id)
            action, amount = None, 0
            for va in valid_actions:
                if va[0] == PlayerAction.CHECK:
                    action = PlayerAction.CHECK
                    break
                elif va[0] == PlayerAction.CALL:
                    action = PlayerAction.CALL
                    amount = va[1] if len(va) > 1 and va[1] else 0
                    break
            if action is None:
                # Fallback to first valid action
                action = valid_actions[0][0]
                amount = valid_actions[0][1] if len(valid_actions[0]) > 1 else 0

            success, msg, result = session.process_player_action(cp.id, action, amount or 0)
            assert success, f"Action {action.value} failed for {cp.name}: {msg}"

            if result and hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    from online_poker.services.game_orchestrator import GameOrchestrator

                    GameOrchestrator.advance_through_non_player_steps(game)

        assert game.state == GameState.COMPLETE, f"Hand should reach COMPLETE but is {game.state}"

        # Verify showdown results
        hand_results = game.get_hand_results()
        assert hand_results is not None
        assert hand_results.is_complete
        assert len(hand_results.pots) > 0
        assert hand_results.total_pot > 0

        # Verify both players have hands evaluated
        assert len(hand_results.hands) >= 1  # At least one player has evaluated hands
        assert len(hand_results.winning_hands) >= 1

    def test_second_hand_starts_with_bots(self, app, socketio, player1, bot_table_2seat):
        """After first hand completes, bots should still be present for the next hand."""
        from generic_poker.game.game_state import GameState, PlayerAction
        from online_poker.services.simple_bot import SimpleBot, bot_manager

        table_id, session, sio1 = self._setup_and_start_hand(app, socketio, player1, bot_table_2seat)
        game = session.game

        # Quick fold to end hand 1
        max_actions = 20
        for _ in range(max_actions):
            if game.state == GameState.COMPLETE:
                break
            cp = game.current_player
            if cp is None:
                if game.current_step < len(game.rules.gameplay):
                    game._next_step()
                    from online_poker.services.game_orchestrator import GameOrchestrator

                    GameOrchestrator.advance_through_non_player_steps(game)
                continue

            if cp.id == player1.id:
                success, msg, result = session.process_player_action(player1.id, PlayerAction.FOLD, 0)
            else:
                bot = bot_manager.get_bot(cp.id)
                valid_actions = game.get_valid_actions(cp.id)
                decision = bot.choose_action_full(valid_actions, game, cp.id)
                success, msg, result = session.process_player_action(
                    cp.id, decision.action, decision.amount or 0, cards=decision.cards
                )
            assert success, f"Action failed: {msg}"
            if result and hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    from online_poker.services.game_orchestrator import GameOrchestrator

                    GameOrchestrator.advance_through_non_player_steps(game)

        assert game.state == GameState.COMPLETE, "Hand 1 should be complete"

        # Verify both players still in session
        assert len(session.game.table.players) == 2
        assert player1.id in session.connected_players

        # Both players should have non-zero stacks (one won, one lost blind)
        for _pid, player in game.table.players.items():
            assert player.stack >= 0, f"Player {player.name} has negative stack"

        # Start hand 2
        game.table.move_button()
        game.start_hand(shuffle_deck=True)

        # Advance through dealing
        while game.current_player is None and game.state != GameState.COMPLETE:
            game._next_step()
            if game.current_step >= len(game.rules.gameplay):
                break

        # Hand 2 should have started successfully with same players
        assert game.current_player is not None, "Hand 2 should have a current player"
        assert len(game.table.players) == 2, "Hand 2 should still have 2 players"

        # Verify bot is still functional
        bot_id = [pid for pid in game.table.players if SimpleBot.is_bot_player(pid)][0]
        assert bot_id in session.connected_players
        bot = bot_manager.get_bot(bot_id)
        assert bot is not None

    def test_ready_status_after_hand_complete(self, app, socketio, player1, bot_table_2seat):
        """After hand completes, bots should show as ready in ready_status."""
        from generic_poker.game.game_state import GameState, PlayerAction
        from online_poker.services.table_access_manager import TableAccessManager

        table_id, session, sio1 = self._setup_and_start_hand(app, socketio, player1, bot_table_2seat)
        game = session.game

        # Fold to end hand quickly
        cp = game.current_player
        if cp.id == player1.id:
            session.process_player_action(player1.id, PlayerAction.FOLD, 0)
        else:
            session.process_player_action(cp.id, PlayerAction.FOLD, 0)

        # The fold should end the hand (2 players, 1 folds)
        if game.state != GameState.COMPLETE:
            # Advance if needed
            while game.current_player is None and game.state != GameState.COMPLETE:
                game._next_step()
                if game.current_step >= len(game.rules.gameplay):
                    break

        # Reset ready status (as _start_hand_when_ready does)
        TableAccessManager.reset_all_ready(table_id)

        # Check ready status
        ready_status = TableAccessManager.get_ready_status(table_id)

        # Bot should be ready, human should not
        bot_players = [p for p in ready_status["players"] if p["user_id"].startswith("bot_")]
        human_players = [p for p in ready_status["players"] if p["user_id"] == player1.id]

        assert len(bot_players) == 1, f"Should have 1 bot in ready status, got {len(bot_players)}"
        assert bot_players[0]["is_ready"] is True

        assert len(human_players) == 1, f"Should have 1 human in ready status, got {len(human_players)}"
        assert human_players[0]["is_ready"] is False

        # all_ready should be False (human not ready)
        assert ready_status["all_ready"] is False

        # After human clicks ready, all_ready should be True
        TableAccessManager.set_player_ready(player1.id, table_id, True)
        ready_status = TableAccessManager.get_ready_status(table_id)
        assert ready_status["all_ready"] is True
