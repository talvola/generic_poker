"""Unit tests for disconnect manager."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
from threading import Timer
from flask import Flask

from src.online_poker.services.disconnect_manager import DisconnectManager, DisconnectedPlayer
from src.online_poker.models.user import User
from src.online_poker.database import db


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
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
def disconnect_manager():
    """Create disconnect manager instance."""
    return DisconnectManager()


@pytest.fixture
def test_user(app_context):
    """Create a test user."""
    from src.online_poker.services.user_manager import UserManager
    user = UserManager.create_user("testuser", "test@example.com", "password123", 1000)
    return user


class TestDisconnectedPlayer:
    """Test DisconnectedPlayer functionality."""
    
    def test_disconnected_player_initialization(self):
        """Test disconnected player initialization."""
        user_id = "user123"
        table_id = "table456"
        disconnect_time = datetime.utcnow()
        
        player = DisconnectedPlayer(user_id, table_id, disconnect_time, 5)
        
        assert player.user_id == user_id
        assert player.table_id == table_id
        assert player.disconnect_time == disconnect_time
        assert player.timeout_minutes == 5
        assert player.has_auto_folded is False
        assert player.is_current_player_on_disconnect is False
    
    def test_disconnected_player_is_expired_false(self):
        """Test disconnected player not expired."""
        disconnect_time = datetime.utcnow() - timedelta(minutes=2)
        player = DisconnectedPlayer("user1", "table1", disconnect_time, 5)
        
        assert player.is_expired() is False
    
    def test_disconnected_player_is_expired_true(self):
        """Test disconnected player expired."""
        disconnect_time = datetime.utcnow() - timedelta(minutes=10)
        player = DisconnectedPlayer("user1", "table1", disconnect_time, 5)
        
        assert player.is_expired() is True
    
    def test_disconnected_player_time_remaining(self):
        """Test time remaining calculation."""
        disconnect_time = datetime.utcnow() - timedelta(minutes=2)
        player = DisconnectedPlayer("user1", "table1", disconnect_time, 5)
        
        time_remaining = player.time_remaining()
        assert 170 <= time_remaining <= 180  # Should be around 3 minutes (180 seconds)
    
    def test_disconnected_player_time_remaining_expired(self):
        """Test time remaining when expired."""
        disconnect_time = datetime.utcnow() - timedelta(minutes=10)
        player = DisconnectedPlayer("user1", "table1", disconnect_time, 5)
        
        time_remaining = player.time_remaining()
        assert time_remaining == 0
    
    @patch('src.online_poker.services.disconnect_manager.Timer')
    def test_start_timers_current_player(self, mock_timer):
        """Test starting timers for current player."""
        player = DisconnectedPlayer("user1", "table1", datetime.utcnow(), 5)
        player.is_current_player_on_disconnect = True
        
        mock_disconnect_manager = MagicMock()
        player.start_timers(mock_disconnect_manager)
        
        # Should create two timers: auto-fold (30s) and removal (300s)
        assert mock_timer.call_count == 2
    
    @patch('src.online_poker.services.disconnect_manager.Timer')
    def test_start_timers_non_current_player(self, mock_timer):
        """Test starting timers for non-current player."""
        player = DisconnectedPlayer("user1", "table1", datetime.utcnow(), 5)
        player.is_current_player_on_disconnect = False
        
        mock_disconnect_manager = MagicMock()
        player.start_timers(mock_disconnect_manager)
        
        # Should create one timer: removal (300s), auto-fold happens immediately
        assert mock_timer.call_count == 1
        mock_disconnect_manager._handle_auto_fold.assert_called_once()
    
    def test_cancel_timers(self):
        """Test canceling timers."""
        player = DisconnectedPlayer("user1", "table1", datetime.utcnow(), 5)
        
        # Mock timers
        mock_auto_fold = MagicMock()
        mock_removal = MagicMock()
        player.auto_fold_timer = mock_auto_fold
        player.removal_timer = mock_removal
        
        player.cancel_timers()
        
        mock_auto_fold.cancel.assert_called_once()
        mock_removal.cancel.assert_called_once()
        assert player.auto_fold_timer is None
        assert player.removal_timer is None


class TestDisconnectManager:
    """Test DisconnectManager functionality."""
    
    def test_disconnect_manager_initialization(self, disconnect_manager):
        """Test disconnect manager initialization."""
        assert isinstance(disconnect_manager.disconnected_players, dict)
        assert isinstance(disconnect_manager.table_disconnects, dict)
        assert disconnect_manager.lock is not None
    
    @patch('src.online_poker.services.disconnect_manager.PlayerSessionManager.handle_player_disconnect')
    @patch('src.online_poker.services.disconnect_manager.get_websocket_manager')
    def test_handle_player_disconnect_success(self, mock_get_ws, mock_handle_disconnect, 
                                            disconnect_manager):
        """Test successful player disconnect handling."""
        user_id = "user123"
        table_id = "table456"
        
        # Mock WebSocket manager
        mock_ws_manager = MagicMock()
        mock_get_ws.return_value = mock_ws_manager
        
        with patch.object(DisconnectedPlayer, 'start_timers') as mock_start_timers:
            success, message = disconnect_manager.handle_player_disconnect(
                user_id, table_id, is_current_player=True
            )
            
            assert success is True
            assert user_id in disconnect_manager.disconnected_players
            assert table_id in disconnect_manager.table_disconnects
            assert user_id in disconnect_manager.table_disconnects[table_id]
            
            # Check disconnected player properties
            disconnected_player = disconnect_manager.disconnected_players[user_id]
            assert disconnected_player.user_id == user_id
            assert disconnected_player.table_id == table_id
            assert disconnected_player.is_current_player_on_disconnect is True
            
            # Verify timers were started
            mock_start_timers.assert_called_once()
            
            # Verify WebSocket broadcast
            mock_ws_manager.broadcast_to_table.assert_called_once()
    
    def test_handle_player_disconnect_already_disconnected(self, disconnect_manager):
        """Test handling disconnect for already disconnected player."""
        user_id = "user123"
        table_id = "table456"
        
        # Add player as already disconnected
        disconnect_manager.disconnected_players[user_id] = DisconnectedPlayer(
            user_id, table_id, datetime.utcnow()
        )
        
        success, message = disconnect_manager.handle_player_disconnect(user_id, table_id)
        
        assert success is True
        assert "already handling" in message.lower()
    
    @patch('src.online_poker.services.disconnect_manager.PlayerSessionManager.handle_player_reconnect')
    @patch('src.online_poker.services.disconnect_manager.GameStateManager.generate_game_state_view')
    @patch('src.online_poker.services.disconnect_manager.get_websocket_manager')
    def test_handle_player_reconnect_success(self, mock_get_ws, mock_generate_state, 
                                           mock_handle_reconnect, disconnect_manager):
        """Test successful player reconnect handling."""
        user_id = "user123"
        table_id = "table456"
        
        # Add disconnected player
        disconnected_player = DisconnectedPlayer(user_id, table_id, datetime.utcnow())
        disconnect_manager.disconnected_players[user_id] = disconnected_player
        disconnect_manager.table_disconnects[table_id] = {user_id}
        
        # Mock successful reconnect
        mock_handle_reconnect.return_value = (True, "Reconnected", {"session": "info"})
        
        # Mock game state
        mock_game_state = MagicMock()
        mock_game_state.to_dict.return_value = {"game": "state"}
        mock_generate_state.return_value = mock_game_state
        
        # Mock WebSocket manager
        mock_ws_manager = MagicMock()
        mock_get_ws.return_value = mock_ws_manager
        
        with patch.object(disconnected_player, 'cancel_timers') as mock_cancel:
            success, message, reconnect_info = disconnect_manager.handle_player_reconnect(
                user_id, table_id
            )
            
            assert success is True
            assert reconnect_info is not None
            assert reconnect_info['user_id'] == user_id
            assert reconnect_info['table_id'] == table_id
            
            # Verify cleanup
            assert user_id not in disconnect_manager.disconnected_players
            assert table_id not in disconnect_manager.table_disconnects
            
            # Verify timers were cancelled (called twice due to cleanup)
            assert mock_cancel.call_count >= 1
            
            # Verify WebSocket notifications
            mock_ws_manager.broadcast_to_table.assert_called()
            mock_ws_manager.send_to_user.assert_called()
    
    def test_handle_player_reconnect_not_disconnected(self, disconnect_manager):
        """Test reconnect for player who wasn't disconnected."""
        user_id = "user123"
        table_id = "table456"
        
        success, message, reconnect_info = disconnect_manager.handle_player_reconnect(
            user_id, table_id
        )
        
        assert success is False
        assert "not disconnected" in message.lower()
        assert reconnect_info is None
    
    def test_handle_player_reconnect_expired(self, disconnect_manager):
        """Test reconnect for expired disconnect."""
        user_id = "user123"
        table_id = "table456"
        
        # Add expired disconnected player
        old_disconnect_time = datetime.utcnow() - timedelta(minutes=15)
        disconnected_player = DisconnectedPlayer(user_id, table_id, old_disconnect_time, 5)
        disconnect_manager.disconnected_players[user_id] = disconnected_player
        
        success, message, reconnect_info = disconnect_manager.handle_player_reconnect(
            user_id, table_id
        )
        
        assert success is False
        assert "timeout expired" in message.lower()
        assert reconnect_info is None
        assert user_id not in disconnect_manager.disconnected_players
    
    def test_handle_auto_fold(self, disconnect_manager):
        """Test auto-fold handling."""
        user_id = "user123"
        table_id = "table456"
        
        # Add disconnected player
        disconnected_player = DisconnectedPlayer(user_id, table_id, datetime.utcnow())
        disconnect_manager.disconnected_players[user_id] = disconnected_player
        
        with patch('src.online_poker.services.disconnect_manager.game_orchestrator') as mock_orchestrator_module:
            with patch('src.online_poker.services.disconnect_manager.GameStateManager._get_current_player') as mock_get_current:
                with patch('src.online_poker.services.disconnect_manager.get_websocket_manager') as mock_get_ws:
                    # Mock game session
                    mock_session = MagicMock()
                    mock_session.process_player_action.return_value = (True, "Folded", None)
                    mock_orchestrator_module.game_orchestrator.get_session.return_value = mock_session
                    mock_get_current.return_value = user_id
                    
                    # Mock WebSocket manager
                    mock_ws_manager = MagicMock()
                    mock_get_ws.return_value = mock_ws_manager
                    
                    disconnect_manager._handle_auto_fold(user_id, table_id)
                    
                    # Verify auto-fold was processed
                    mock_session.process_player_action.assert_called_once()
                    assert disconnected_player.has_auto_folded is True
                    
                    # Verify WebSocket notifications
                    mock_ws_manager.broadcast_to_table.assert_called()
                    mock_ws_manager.broadcast_game_state_update.assert_called()
    
    def test_handle_auto_fold_not_current_player(self, disconnect_manager):
        """Test auto-fold when player is not current to act."""
        user_id = "user123"
        table_id = "table456"
        
        # Add disconnected player
        disconnected_player = DisconnectedPlayer(user_id, table_id, datetime.utcnow())
        disconnect_manager.disconnected_players[user_id] = disconnected_player
        
        with patch('src.online_poker.services.disconnect_manager.game_orchestrator') as mock_orchestrator_module:
            with patch('src.online_poker.services.disconnect_manager.GameStateManager._get_current_player') as mock_get_current:
                mock_session = MagicMock()
                mock_orchestrator_module.game_orchestrator.get_session.return_value = mock_session
                mock_get_current.return_value = "other_user"  # Different user is current
                
                disconnect_manager._handle_auto_fold(user_id, table_id)
                
                # Should not process fold action
                mock_session.process_player_action.assert_not_called()
                assert disconnected_player.has_auto_folded is False
    
    @patch('src.online_poker.services.disconnect_manager.PlayerSessionManager.leave_table_and_game')
    @patch('src.online_poker.services.disconnect_manager.get_websocket_manager')
    def test_handle_auto_removal(self, mock_get_ws, mock_leave_table, disconnect_manager):
        """Test auto-removal handling."""
        user_id = "user123"
        table_id = "table456"
        
        # Add disconnected player
        disconnected_player = DisconnectedPlayer(user_id, table_id, datetime.utcnow())
        disconnect_manager.disconnected_players[user_id] = disconnected_player
        disconnect_manager.table_disconnects[table_id] = {user_id}
        
        # Mock successful removal
        cashout_info = {"final_stack": 500}
        mock_leave_table.return_value = (True, "Removed", cashout_info)
        
        # Mock WebSocket manager
        mock_ws_manager = MagicMock()
        mock_get_ws.return_value = mock_ws_manager
        
        disconnect_manager._handle_auto_removal(user_id, table_id)
        
        # Verify removal was processed
        mock_leave_table.assert_called_once_with(user_id, table_id, "Disconnected too long")
        
        # Verify cleanup
        assert user_id not in disconnect_manager.disconnected_players
        assert table_id not in disconnect_manager.table_disconnects
        
        # Verify WebSocket notifications
        mock_ws_manager.broadcast_to_table.assert_called()
        mock_ws_manager.broadcast_game_state_update.assert_called()
    
    def test_get_disconnected_player_info_exists(self, disconnect_manager):
        """Test getting disconnect info for existing player."""
        user_id = "user123"
        table_id = "table456"
        disconnect_time = datetime.utcnow()
        
        disconnected_player = DisconnectedPlayer(user_id, table_id, disconnect_time, 5)
        disconnect_manager.disconnected_players[user_id] = disconnected_player
        
        info = disconnect_manager.get_disconnected_player_info(user_id)
        
        assert info is not None
        assert info['user_id'] == user_id
        assert info['table_id'] == table_id
        assert info['timeout_minutes'] == 5
        assert 'time_remaining' in info
        assert 'has_auto_folded' in info
    
    def test_get_disconnected_player_info_not_exists(self, disconnect_manager):
        """Test getting disconnect info for non-existent player."""
        info = disconnect_manager.get_disconnected_player_info("nonexistent")
        assert info is None
    
    def test_get_table_disconnects(self, disconnect_manager):
        """Test getting disconnects for a table."""
        table_id = "table456"
        user1 = "user123"
        user2 = "user789"
        
        # Add disconnected players
        disconnect_manager.disconnected_players[user1] = DisconnectedPlayer(
            user1, table_id, datetime.utcnow()
        )
        disconnect_manager.disconnected_players[user2] = DisconnectedPlayer(
            user2, table_id, datetime.utcnow()
        )
        disconnect_manager.table_disconnects[table_id] = {user1, user2}
        
        disconnects = disconnect_manager.get_table_disconnects(table_id)
        
        assert len(disconnects) == 2
        user_ids = [d['user_id'] for d in disconnects]
        assert user1 in user_ids
        assert user2 in user_ids
    
    def test_is_player_disconnected(self, disconnect_manager):
        """Test checking if player is disconnected."""
        user_id = "user123"
        
        # Player not disconnected
        assert disconnect_manager.is_player_disconnected(user_id) is False
        
        # Add disconnected player
        disconnect_manager.disconnected_players[user_id] = DisconnectedPlayer(
            user_id, "table456", datetime.utcnow()
        )
        
        # Player is disconnected
        assert disconnect_manager.is_player_disconnected(user_id) is True
    
    def test_cleanup_expired_disconnects(self, disconnect_manager):
        """Test cleaning up expired disconnects."""
        user1 = "user123"
        user2 = "user456"
        table_id = "table789"
        
        # Add one expired and one active disconnect
        old_time = datetime.utcnow() - timedelta(minutes=15)
        recent_time = datetime.utcnow() - timedelta(minutes=2)
        
        disconnect_manager.disconnected_players[user1] = DisconnectedPlayer(
            user1, table_id, old_time, 5  # Expired (15 min > 5 min timeout)
        )
        disconnect_manager.disconnected_players[user2] = DisconnectedPlayer(
            user2, table_id, recent_time, 5  # Not expired
        )
        
        with patch.object(disconnect_manager, '_handle_auto_removal') as mock_removal:
            cleaned_count = disconnect_manager.cleanup_expired_disconnects()
            
            assert cleaned_count == 1
            mock_removal.assert_called_once_with(user1, table_id)
    
    def test_get_disconnect_stats(self, disconnect_manager):
        """Test getting disconnect statistics."""
        # Add some disconnected players
        user1 = "user123"
        user2 = "user456"
        table_id = "table789"
        
        dp1 = DisconnectedPlayer(user1, table_id, datetime.utcnow())
        dp1.has_auto_folded = True
        dp2 = DisconnectedPlayer(user2, table_id, datetime.utcnow() - timedelta(minutes=15), 5)
        
        disconnect_manager.disconnected_players[user1] = dp1
        disconnect_manager.disconnected_players[user2] = dp2
        disconnect_manager.table_disconnects[table_id] = {user1, user2}
        
        stats = disconnect_manager.get_disconnect_stats()
        
        assert stats['total_disconnected_players'] == 2
        assert stats['auto_folded_players'] == 1
        assert stats['expired_disconnects'] == 1
        assert stats['active_table_disconnects'] == 1
        assert 'average_disconnect_time' in stats
    
    def test_force_reconnect_player(self, disconnect_manager):
        """Test force reconnecting a player."""
        user_id = "user123"
        table_id = "table456"
        
        # Add disconnected player
        disconnect_manager.disconnected_players[user_id] = DisconnectedPlayer(
            user_id, table_id, datetime.utcnow()
        )
        
        with patch.object(disconnect_manager, 'handle_player_reconnect') as mock_reconnect:
            mock_reconnect.return_value = (True, "Reconnected", {"info": "data"})
            
            success, message = disconnect_manager.force_reconnect_player(user_id, table_id)
            
            assert success is True
            mock_reconnect.assert_called_once_with(user_id, table_id)
    
    def test_force_reconnect_player_not_disconnected(self, disconnect_manager):
        """Test force reconnecting a player who isn't disconnected."""
        success, message = disconnect_manager.force_reconnect_player("user123", "table456")
        
        assert success is False
        assert "not disconnected" in message.lower()
    
    def test_force_remove_player(self, disconnect_manager):
        """Test force removing a player."""
        user_id = "user123"
        table_id = "table456"
        
        # Add disconnected player
        disconnect_manager.disconnected_players[user_id] = DisconnectedPlayer(
            user_id, table_id, datetime.utcnow()
        )
        
        with patch.object(disconnect_manager, '_handle_auto_removal') as mock_removal:
            success, message = disconnect_manager.force_remove_player(user_id)
            
            assert success is True
            mock_removal.assert_called_once_with(user_id, table_id)
    
    def test_force_remove_player_not_disconnected(self, disconnect_manager):
        """Test force removing a player who isn't disconnected."""
        success, message = disconnect_manager.force_remove_player("user123")
        
        assert success is False
        assert "not disconnected" in message.lower()