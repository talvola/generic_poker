"""Unit tests for WebSocket manager."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from flask import Flask
from flask_socketio import SocketIO

from src.online_poker.services.websocket_manager import WebSocketManager, GameEvent
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
def mock_socketio():
    """Create mock SocketIO instance."""
    socketio = MagicMock(spec=SocketIO)
    socketio.emit = MagicMock()
    socketio.server = MagicMock()
    return socketio


@pytest.fixture
def websocket_manager(mock_socketio):
    """Create WebSocket manager instance."""
    with patch('src.online_poker.services.websocket_manager.join_room'):
        with patch('src.online_poker.services.websocket_manager.leave_room'):
            with patch('src.online_poker.services.websocket_manager.emit'):
                with patch('src.online_poker.services.websocket_manager.disconnect'):
                    manager = WebSocketManager(mock_socketio)
                    return manager


@pytest.fixture
def test_user(app_context):
    """Create a test user."""
    from src.online_poker.services.user_manager import UserManager
    user = UserManager.create_user("testuser", "test@example.com", "password123", 1000)
    return user


class TestWebSocketManager:
    """Test WebSocketManager functionality."""
    
    def test_websocket_manager_initialization(self, mock_socketio):
        """Test WebSocket manager initialization."""
        with patch('src.online_poker.services.websocket_manager.join_room'):
            with patch('src.online_poker.services.websocket_manager.leave_room'):
                with patch('src.online_poker.services.websocket_manager.emit'):
                    with patch('src.online_poker.services.websocket_manager.disconnect'):
                        manager = WebSocketManager(mock_socketio)
                        
                        assert manager.socketio == mock_socketio
                        assert isinstance(manager.user_sessions, dict)
                        assert isinstance(manager.session_users, dict)
                        assert isinstance(manager.table_rooms, dict)
                        assert isinstance(manager.user_tables, dict)
    
    def test_join_table_room_success(self, websocket_manager):
        """Test successfully joining a table room."""
        user_id = "user123"
        table_id = "table456"
        session_id = "session789"
        
        # Set up user session
        websocket_manager.user_sessions[user_id] = session_id
        
        with patch('src.online_poker.services.websocket_manager.join_room') as mock_join:
            success = websocket_manager.join_table_room(user_id, table_id)
            
            assert success is True
            assert table_id in websocket_manager.table_rooms
            assert session_id in websocket_manager.table_rooms[table_id]
            assert websocket_manager.user_tables[user_id] == table_id
            
            mock_join.assert_called_once_with(f"table_{table_id}", sid=session_id)
    
    def test_join_table_room_no_session(self, websocket_manager):
        """Test joining table room when user has no session."""
        user_id = "user123"
        table_id = "table456"
        
        success = websocket_manager.join_table_room(user_id, table_id)
        
        assert success is False
        assert table_id not in websocket_manager.table_rooms
    
    def test_leave_table_room_success(self, websocket_manager):
        """Test successfully leaving a table room."""
        user_id = "user123"
        table_id = "table456"
        session_id = "session789"
        
        # Set up user session and room membership
        websocket_manager.user_sessions[user_id] = session_id
        websocket_manager.table_rooms[table_id] = {session_id}
        websocket_manager.user_tables[user_id] = table_id
        
        with patch('src.online_poker.services.websocket_manager.leave_room') as mock_leave:
            success = websocket_manager.leave_table_room(user_id, table_id)
            
            assert success is True
            assert table_id not in websocket_manager.table_rooms
            assert user_id not in websocket_manager.user_tables
            
            mock_leave.assert_called_once_with(f"table_{table_id}", sid=session_id)
    
    def test_leave_table_room_no_session(self, websocket_manager):
        """Test leaving table room when user has no session."""
        user_id = "user123"
        table_id = "table456"
        
        success = websocket_manager.leave_table_room(user_id, table_id)
        
        assert success is False
    
    def test_broadcast_to_table(self, websocket_manager, mock_socketio):
        """Test broadcasting to table participants."""
        table_id = "table123"
        event = GameEvent.GAME_STATE_UPDATE
        data = {"test": "data"}
        
        websocket_manager.broadcast_to_table(table_id, event, data)
        
        mock_socketio.emit.assert_called_once_with(event, data, room=f"table_{table_id}")
    
    def test_broadcast_to_table_exclude_user(self, websocket_manager, mock_socketio):
        """Test broadcasting to table with user exclusion."""
        table_id = "table123"
        event = GameEvent.PLAYER_JOINED
        data = {"user_id": "user456"}
        exclude_user = "user123"
        exclude_session = "session123"
        other_session = "session456"
        
        # Set up sessions and room
        websocket_manager.user_sessions[exclude_user] = exclude_session
        websocket_manager.table_rooms[table_id] = {exclude_session, other_session}
        
        websocket_manager.broadcast_to_table(table_id, event, data, exclude_user=exclude_user)
        
        # Should emit to the other session only
        mock_socketio.emit.assert_called_once_with(event, data, room=other_session)
    
    def test_send_to_user_success(self, websocket_manager, mock_socketio):
        """Test sending message to specific user."""
        user_id = "user123"
        session_id = "session456"
        event = GameEvent.NOTIFICATION
        data = {"message": "Test notification"}
        
        websocket_manager.user_sessions[user_id] = session_id
        
        success = websocket_manager.send_to_user(user_id, event, data)
        
        assert success is True
        mock_socketio.emit.assert_called_once_with(event, data, room=session_id)
    
    def test_send_to_user_no_session(self, websocket_manager, mock_socketio):
        """Test sending message to user with no session."""
        user_id = "user123"
        event = GameEvent.NOTIFICATION
        data = {"message": "Test notification"}
        
        success = websocket_manager.send_to_user(user_id, event, data)
        
        assert success is False
        mock_socketio.emit.assert_not_called()
    
    @patch('src.online_poker.services.websocket_manager.PlayerSessionManager.handle_player_disconnect')
    def test_handle_table_disconnect(self, mock_handle_disconnect, websocket_manager):
        """Test handling table disconnection."""
        user_id = "user123"
        table_id = "table456"
        
        websocket_manager.handle_table_disconnect(user_id, table_id)
        
        mock_handle_disconnect.assert_called_once_with(user_id, table_id)
    
    @patch('src.online_poker.services.websocket_manager.PlayerSessionManager.handle_player_reconnect')
    @patch('src.online_poker.services.websocket_manager.GameStateManager.generate_game_state_view')
    def test_handle_table_reconnect_success(self, mock_generate_state, mock_handle_reconnect, websocket_manager):
        """Test successful table reconnection."""
        user_id = "user123"
        table_id = "table456"
        
        mock_handle_reconnect.return_value = (True, "Reconnected", {"session": "info"})
        mock_game_state = MagicMock()
        mock_game_state.to_dict.return_value = {"game": "state"}
        mock_generate_state.return_value = mock_game_state
        
        success = websocket_manager.handle_table_reconnect(user_id, table_id)
        
        assert success is True
        mock_handle_reconnect.assert_called_once_with(user_id, table_id)
    
    @patch('src.online_poker.services.websocket_manager.PlayerSessionManager.handle_player_reconnect')
    def test_handle_table_reconnect_failure(self, mock_handle_reconnect, websocket_manager):
        """Test failed table reconnection."""
        user_id = "user123"
        table_id = "table456"
        
        mock_handle_reconnect.return_value = (False, "Failed to reconnect", None)
        
        success = websocket_manager.handle_table_reconnect(user_id, table_id)
        
        assert success is False
    
    @patch('src.online_poker.services.websocket_manager.PlayerSessionManager.get_player_info')
    @patch('src.online_poker.services.websocket_manager.GameStateManager.generate_game_state_view')
    def test_broadcast_game_state_update(self, mock_generate_state, mock_get_player_info, websocket_manager, mock_socketio):
        """Test broadcasting game state update."""
        table_id = "table123"
        user_id = "user456"
        session_id = "session789"
        
        # Set up room and sessions
        websocket_manager.table_rooms[table_id] = {session_id}
        websocket_manager.session_users[session_id] = user_id
        
        mock_get_player_info.return_value = {"is_spectator": False}
        mock_game_state = MagicMock()
        mock_game_state.to_dict.return_value = {"game": "state"}
        mock_generate_state.return_value = mock_game_state
        
        websocket_manager.broadcast_game_state_update(table_id)
        
        mock_generate_state.assert_called_once_with(table_id, user_id, False)
        mock_socketio.emit.assert_called_once_with(
            GameEvent.GAME_STATE_UPDATE, 
            {"game": "state"}, 
            room=session_id
        )
    
    def test_send_notification(self, websocket_manager):
        """Test sending notification."""
        user_id = "user123"
        session_id = "session456"
        message = "Test notification"
        notification_type = "info"
        
        websocket_manager.user_sessions[user_id] = session_id
        
        with patch.object(websocket_manager, 'send_to_user', return_value=True) as mock_send:
            success = websocket_manager.send_notification(user_id, message, notification_type)
            
            assert success is True
            mock_send.assert_called_once()
            
            # Check the call arguments
            call_args = mock_send.call_args
            assert call_args[0][0] == user_id
            assert call_args[0][1] == GameEvent.NOTIFICATION
            assert call_args[0][2]['message'] == message
            assert call_args[0][2]['type'] == notification_type
    
    def test_get_connected_users(self, websocket_manager):
        """Test getting connected users."""
        user1 = "user123"
        user2 = "user456"
        
        websocket_manager.user_sessions[user1] = "session1"
        websocket_manager.user_sessions[user2] = "session2"
        
        connected_users = websocket_manager.get_connected_users()
        
        assert len(connected_users) == 2
        assert user1 in connected_users
        assert user2 in connected_users
    
    def test_get_table_participants(self, websocket_manager):
        """Test getting table participants."""
        table_id = "table123"
        user1 = "user456"
        user2 = "user789"
        session1 = "session1"
        session2 = "session2"
        
        websocket_manager.table_rooms[table_id] = {session1, session2}
        websocket_manager.session_users[session1] = user1
        websocket_manager.session_users[session2] = user2
        
        participants = websocket_manager.get_table_participants(table_id)
        
        assert len(participants) == 2
        assert user1 in participants
        assert user2 in participants
    
    def test_is_user_connected(self, websocket_manager):
        """Test checking if user is connected."""
        user_id = "user123"
        
        # User not connected
        assert websocket_manager.is_user_connected(user_id) is False
        
        # User connected
        websocket_manager.user_sessions[user_id] = "session456"
        assert websocket_manager.is_user_connected(user_id) is True
    
    def test_get_connection_stats(self, websocket_manager):
        """Test getting connection statistics."""
        # Set up some connections and rooms
        websocket_manager.user_sessions["user1"] = "session1"
        websocket_manager.user_sessions["user2"] = "session2"
        websocket_manager.table_rooms["table1"] = {"session1"}
        websocket_manager.table_rooms["table2"] = {"session1", "session2"}
        
        stats = websocket_manager.get_connection_stats()
        
        assert stats['connected_users'] == 2
        assert stats['active_tables'] == 2
        assert stats['total_room_participants'] == 3  # session1 + (session1, session2)


class TestGameEvent:
    """Test GameEvent constants."""
    
    def test_game_event_constants(self):
        """Test that all game event constants are defined."""
        assert GameEvent.PLAYER_JOINED == "player_joined"
        assert GameEvent.PLAYER_LEFT == "player_left"
        assert GameEvent.GAME_STATE_UPDATE == "game_state_update"
        assert GameEvent.PLAYER_ACTION == "player_action"
        assert GameEvent.HAND_COMPLETE == "hand_complete"
        assert GameEvent.CHAT_MESSAGE == "chat_message"
        assert GameEvent.PLAYER_DISCONNECTED == "player_disconnected"
        assert GameEvent.PLAYER_RECONNECTED == "player_reconnected"
        assert GameEvent.TABLE_UPDATE == "table_update"
        assert GameEvent.ERROR == "error"
        assert GameEvent.NOTIFICATION == "notification"