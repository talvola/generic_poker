"""Unit tests for game orchestration system."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from src.online_poker.database import db
from src.online_poker.models.table import PokerTable
from src.online_poker.services.game_orchestrator import GameOrchestrator, GameSession

from generic_poker.config.loader import GameRules
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game_state import PlayerAction


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        db.init_app(app)
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def app_context(app):
    """Create app context for tests."""
    with app.app_context():
        yield


@pytest.fixture
def test_user(app_context):
    """Create a test user."""
    from src.online_poker.services.user_manager import UserManager

    user = UserManager.create_user("testuser", "test@example.com", "password123", 1000)
    return user


@pytest.fixture
def test_table(app_context, test_user):
    """Create a test table."""
    table = PokerTable(
        name="Test Game Table",
        variant="hold_em",
        betting_structure=BettingStructure.NO_LIMIT.value,
        stakes={"small_blind": 1, "big_blind": 2},
        max_players=6,
        creator_id=test_user.id,
        is_private=False,
    )
    db.session.add(table)
    db.session.commit()
    return table


@pytest.fixture
def mock_game_rules():
    """Create mock game rules."""
    rules = MagicMock(spec=GameRules)
    rules.game = "Hold'em"
    rules.min_players = 2
    rules.max_players = 9
    rules.betting_structures = [BettingStructure.NO_LIMIT]
    return rules


class TestGameSession:
    """Test GameSession functionality."""

    def test_game_session_creation(self, app_context, test_table, mock_game_rules):
        """Test creating a game session."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)

            assert session.table == test_table
            assert session.game_rules == mock_game_rules
            assert session.game == mock_game
            assert session.is_active is True
            assert session.is_paused is False
            assert len(session.connected_players) == 0
            assert len(session.spectators) == 0

    def test_add_player_success(self, app_context, test_table, mock_game_rules):
        """Test successfully adding a player."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)

            success, message = session.add_player("user123", "TestUser", 500)

            assert success is True
            assert "user123" in session.connected_players
            mock_game.add_player.assert_called_once_with("user123", "TestUser", 500, preferred_seat=None)

    def test_add_player_already_in_game(self, app_context, test_table, mock_game_rules):
        """Test adding a player who is already in the game."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.add("user123")

            success, message = session.add_player("user123", "TestUser", 500)

            assert success is False
            assert "already in game" in message

    def test_add_player_game_paused(self, app_context, test_table, mock_game_rules):
        """Test adding a player when game is paused."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.is_paused = True
            session.pause_reason = "Test pause"

            success, message = session.add_player("user123", "TestUser", 500)

            assert success is False
            assert "paused" in message

    def test_remove_player_success(self, app_context, test_table, mock_game_rules):
        """Test successfully removing a player."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.add("user123")

            success, message = session.remove_player("user123", "Test removal")

            assert success is True
            assert "user123" not in session.connected_players
            mock_game.remove_player.assert_called_once_with("user123")

    def test_remove_player_not_in_game(self, app_context, test_table, mock_game_rules):
        """Test removing a player who is not in the game."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)

            success, message = session.remove_player("user123", "Test removal")

            assert success is False
            assert "not in game" in message

    def test_handle_player_disconnect(self, app_context, test_table, mock_game_rules):
        """Test handling player disconnection."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.add("user123")

            session.handle_player_disconnect("user123")

            assert "user123" not in session.connected_players
            assert "user123" in session.disconnected_players

    def test_handle_player_reconnect_success(self, app_context, test_table, mock_game_rules):
        """Test successful player reconnection."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.disconnected_players["user123"] = datetime.utcnow()

            success, message = session.handle_player_reconnect("user123")

            assert success is True
            assert "user123" in session.connected_players
            assert "user123" not in session.disconnected_players

    def test_handle_player_reconnect_too_long(self, app_context, test_table, mock_game_rules):
        """Test reconnection after being disconnected too long."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            # Set disconnect time to 15 minutes ago
            session.disconnected_players["user123"] = datetime.utcnow() - timedelta(minutes=15)

            success, message = session.handle_player_reconnect("user123")

            assert success is False
            assert "too long" in message

    def test_add_spectator(self, app_context, test_table, mock_game_rules):
        """Test adding a spectator."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)

            success, message = session.add_spectator("spectator123")

            assert success is True
            assert "spectator123" in session.spectators

    def test_add_spectator_already_player(self, app_context, test_table, mock_game_rules):
        """Test adding a spectator who is already a player."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.add("user123")

            success, message = session.add_spectator("user123")

            assert success is False
            assert "already a player" in message

    def test_remove_spectator(self, app_context, test_table, mock_game_rules):
        """Test removing a spectator."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.spectators.add("spectator123")

            session.remove_spectator("spectator123")

            assert "spectator123" not in session.spectators

    def test_process_player_action_success(self, app_context, test_table, mock_game_rules):
        """Test processing a successful player action."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.message = "Action processed"
            mock_game.player_action.return_value = mock_result
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.add("user123")

            success, message, result = session.process_player_action("user123", PlayerAction.CALL, 100)

            assert success is True
            assert result == mock_result
            mock_game.player_action.assert_called_once_with(
                "user123", PlayerAction.CALL, 100, cards=None, declaration_data=None
            )

    def test_process_player_action_not_in_game(self, app_context, test_table, mock_game_rules):
        """Test processing action for player not in game."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)

            success, message, result = session.process_player_action("user123", PlayerAction.CALL, 100)

            assert success is False
            assert "not in game" in message

    def test_process_player_action_game_paused(self, app_context, test_table, mock_game_rules):
        """Test processing action when game is paused."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.add("user123")
            session.is_paused = True

            success, message, result = session.process_player_action("user123", PlayerAction.CALL, 100)

            assert success is False
            assert "not active" in message

    def test_pause_conditions_insufficient_players(self, app_context, test_table, mock_game_rules):
        """Test game pausing with insufficient players."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.add("user123")

            session._check_pause_conditions()

            assert session.is_paused is True
            assert "Insufficient players" in session.pause_reason

    def test_unpause_conditions_sufficient_players(self, app_context, test_table, mock_game_rules):
        """Test game unpausing with sufficient players."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.is_paused = True
            session.pause_reason = "Test pause"
            session.connected_players.update(["user123", "user456"])

            session._check_unpause_conditions()

            assert session.is_paused is False
            assert session.pause_reason is None

    def test_is_inactive_recent_activity(self, app_context, test_table, mock_game_rules):
        """Test inactivity check with recent activity."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.last_activity = datetime.utcnow()

            assert session.is_inactive(30) is False

    def test_is_inactive_old_activity(self, app_context, test_table, mock_game_rules):
        """Test inactivity check with old activity."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.last_activity = datetime.utcnow() - timedelta(minutes=45)

            assert session.is_inactive(30) is True

    def test_get_session_info(self, app_context, test_table, mock_game_rules):
        """Test getting session information."""
        with patch.object(test_table, "create_game_instance") as mock_create_game:
            mock_game = MagicMock()
            mock_game.state.value = "WAITING"
            mock_create_game.return_value = mock_game

            session = GameSession(test_table, mock_game_rules)
            session.connected_players.update(["user123", "user456"])
            session.spectators.add("spectator123")

            info = session.get_session_info()

            assert info["session_id"] == session.session_id
            assert info["table_id"] == test_table.id
            assert info["connected_players"] == 2
            assert info["spectators"] == 1
            assert info["is_active"] is True
            assert info["game_state"] == "WAITING"


class TestGameOrchestrator:
    """Test GameOrchestrator functionality."""

    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = GameOrchestrator()

        assert len(orchestrator.sessions) == 0
        assert orchestrator.session_lock is not None

    @patch("src.online_poker.services.game_orchestrator.TableManager.get_table_by_id")
    @patch("src.online_poker.services.game_orchestrator.TableManager.get_variant_rules")
    def test_create_session_success(self, mock_get_rules, mock_get_table, app_context, test_table, mock_game_rules):
        """Test successful session creation."""
        mock_get_table.return_value = test_table
        mock_get_rules.return_value = mock_game_rules

        orchestrator = GameOrchestrator()

        with patch.object(test_table, "create_game_instance"):
            success, message, session = orchestrator.create_session(test_table.id)

            assert success is True
            assert session is not None
            assert test_table.id in orchestrator.sessions

    @patch("src.online_poker.services.game_orchestrator.TableManager.get_table_by_id")
    def test_create_session_table_not_found(self, mock_get_table):
        """Test session creation with table not found."""
        mock_get_table.return_value = None

        orchestrator = GameOrchestrator()
        success, message, session = orchestrator.create_session("nonexistent")

        assert success is False
        assert "not found" in message
        assert session is None

    @patch("src.online_poker.services.game_orchestrator.TableManager.get_table_by_id")
    @patch("src.online_poker.services.game_orchestrator.TableManager.get_variant_rules")
    def test_create_session_already_exists(
        self, mock_get_rules, mock_get_table, app_context, test_table, mock_game_rules
    ):
        """Test creating session when one already exists."""
        mock_get_table.return_value = test_table
        mock_get_rules.return_value = mock_game_rules

        orchestrator = GameOrchestrator()

        with patch.object(test_table, "create_game_instance"):
            # Create first session
            orchestrator.create_session(test_table.id)

            # Try to create second session
            success, message, session = orchestrator.create_session(test_table.id)

            assert success is False
            assert "already exists" in message

    def test_get_session_exists(self, app_context, test_table, mock_game_rules):
        """Test getting an existing session."""
        orchestrator = GameOrchestrator()

        with patch.object(test_table, "create_game_instance"):
            mock_session = GameSession(test_table, mock_game_rules)
            orchestrator.sessions[test_table.id] = mock_session

            session = orchestrator.get_session(test_table.id)

            assert session == mock_session

    def test_get_session_not_exists(self):
        """Test getting a non-existent session."""
        orchestrator = GameOrchestrator()
        session = orchestrator.get_session("nonexistent")

        assert session is None

    def test_remove_session_exists(self, app_context, test_table, mock_game_rules):
        """Test removing an existing session."""
        orchestrator = GameOrchestrator()

        with patch.object(test_table, "create_game_instance"):
            mock_session = GameSession(test_table, mock_game_rules)
            orchestrator.sessions[test_table.id] = mock_session

            success = orchestrator.remove_session(test_table.id)

            assert success is True
            assert test_table.id not in orchestrator.sessions

    def test_remove_session_not_exists(self):
        """Test removing a non-existent session."""
        orchestrator = GameOrchestrator()
        success = orchestrator.remove_session("nonexistent")

        assert success is False

    def test_get_all_sessions(self, app_context, test_table, mock_game_rules):
        """Test getting all sessions."""
        orchestrator = GameOrchestrator()

        with patch.object(test_table, "create_game_instance"):
            mock_session = GameSession(test_table, mock_game_rules)
            orchestrator.sessions[test_table.id] = mock_session

            sessions = orchestrator.get_all_sessions()

            assert len(sessions) == 1
            assert sessions[0] == mock_session

    def test_get_session_count(self, app_context, test_table, mock_game_rules):
        """Test getting session count."""
        orchestrator = GameOrchestrator()

        assert orchestrator.get_session_count() == 0

        with patch.object(test_table, "create_game_instance"):
            mock_session = GameSession(test_table, mock_game_rules)
            orchestrator.sessions[test_table.id] = mock_session

            assert orchestrator.get_session_count() == 1

    def test_cleanup_inactive_sessions(self, app_context, test_table, mock_game_rules):
        """Test cleaning up inactive sessions."""
        orchestrator = GameOrchestrator()

        with patch.object(test_table, "create_game_instance"):
            mock_session = GameSession(test_table, mock_game_rules)
            # Make session inactive
            mock_session.last_activity = datetime.utcnow() - timedelta(minutes=45)
            orchestrator.sessions[test_table.id] = mock_session

            cleaned_count = orchestrator.cleanup_inactive_sessions(30)

            assert cleaned_count == 1
            assert len(orchestrator.sessions) == 0

    def test_get_orchestrator_stats(self, app_context, test_table, mock_game_rules):
        """Test getting orchestrator statistics."""
        orchestrator = GameOrchestrator()

        with patch.object(test_table, "create_game_instance"):
            mock_session = GameSession(test_table, mock_game_rules)
            mock_session.connected_players.update(["user123", "user456"])
            mock_session.spectators.add("spectator123")
            orchestrator.sessions[test_table.id] = mock_session

            stats = orchestrator.get_orchestrator_stats()

            assert stats["total_sessions"] == 1
            assert stats["active_sessions"] == 1
            assert stats["total_players"] == 2
            assert stats["total_spectators"] == 1
