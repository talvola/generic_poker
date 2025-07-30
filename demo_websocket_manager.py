#!/usr/bin/env python3
"""Demo script for testing the WebSocket manager system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask
from flask_socketio import SocketIO
from src.online_poker.database import db
from src.online_poker.services.websocket_manager import WebSocketManager, GameEvent
from src.online_poker.services.user_manager import UserManager
from src.online_poker.models.table import PokerTable
from generic_poker.game.betting import BettingStructure


def create_test_app():
    """Create a test Flask app with SocketIO."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_websocket.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    db.init_app(app)
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    with app.app_context():
        db.create_all()
    
    return app, socketio


def main():
    """Run the WebSocket manager demo."""
    print("=== WebSocket Manager Demo ===\n")
    
    app, socketio = create_test_app()
    
    with app.app_context():
        # Create WebSocket manager
        print("1. Creating WebSocket manager...")
        ws_manager = WebSocketManager(socketio)
        print(f"   WebSocket manager initialized")
        print(f"   Event handlers registered: {len(ws_manager.socketio.handlers)}")
        
        # Create test users
        print("\n2. Creating test users...")
        try:
            user1 = UserManager.create_user("alice", "alice@example.com", "password123", 2000)
            user2 = UserManager.create_user("bob", "bob@example.com", "password123", 1500)
            user3 = UserManager.create_user("charlie", "charlie@example.com", "password123", 1000)
        except:
            user1 = UserManager.get_user_by_username("alice")
            user2 = UserManager.get_user_by_username("bob")
            user3 = UserManager.get_user_by_username("charlie")
        
        print(f"   Users: {user1.username}, {user2.username}, {user3.username}")
        
        # Create a test table
        print("\n3. Creating test table...")
        table = PokerTable(
            name="Demo WebSocket Table",
            variant="hold_em",
            betting_structure=BettingStructure.NO_LIMIT.value,
            stakes={"small_blind": 5, "big_blind": 10},
            max_players=6,
            creator_id=user1.id,
            is_private=False
        )
        db.session.add(table)
        db.session.commit()
        print(f"   Created table: {table.name} (ID: {table.id})")
        
        # Simulate user sessions
        print("\n4. Simulating user sessions...")
        session1 = "session_alice_123"
        session2 = "session_bob_456"
        session3 = "session_charlie_789"
        
        ws_manager.user_sessions[user1.id] = session1
        ws_manager.session_users[session1] = user1.id
        
        ws_manager.user_sessions[user2.id] = session2
        ws_manager.session_users[session2] = user2.id
        
        ws_manager.user_sessions[user3.id] = session3
        ws_manager.session_users[session3] = user3.id
        
        print(f"   Simulated sessions for {len(ws_manager.user_sessions)} users")
        
        # Test connection status
        print("\n5. Testing connection status...")
        for user in [user1, user2, user3]:
            is_connected = ws_manager.is_user_connected(user.id)
            print(f"   {user.username} connected: {is_connected}")
        
        # Test joining table rooms
        print("\n6. Testing table room joining...")
        
        # Alice joins table room
        success = ws_manager.join_table_room(user1.id, table.id)
        print(f"   Alice join table room: {'✓' if success else '✗'}")
        
        # Bob joins table room
        success = ws_manager.join_table_room(user2.id, table.id)
        print(f"   Bob join table room: {'✓' if success else '✗'}")
        
        # Charlie joins as spectator
        success = ws_manager.join_table_room(user3.id, table.id)
        print(f"   Charlie join table room: {'✓' if success else '✗'}")
        
        # Check table participants
        participants = ws_manager.get_table_participants(table.id)
        print(f"   Table participants: {len(participants)} users")
        for participant_id in participants:
            user = UserManager.get_user_by_id(participant_id)
            print(f"     - {user.username if user else 'Unknown'}")
        
        # Test broadcasting
        print("\n7. Testing event broadcasting...")
        
        # Broadcast to table
        test_data = {
            "message": "Test broadcast message",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        print("   Broadcasting game state update to table...")
        ws_manager.broadcast_to_table(table.id, GameEvent.GAME_STATE_UPDATE, test_data)
        
        print("   Broadcasting player action (excluding Alice)...")
        action_data = {
            "user_id": user1.id,
            "action": "call",
            "amount": 50
        }
        ws_manager.broadcast_to_table(table.id, GameEvent.PLAYER_ACTION, action_data, exclude_user=user1.id)
        
        # Test direct messaging
        print("\n8. Testing direct messaging...")
        
        notification_data = {
            "message": "You have a new notification",
            "type": "info"
        }
        
        success = ws_manager.send_to_user(user2.id, GameEvent.NOTIFICATION, notification_data)
        print(f"   Send notification to Bob: {'✓' if success else '✗'}")
        
        # Test notification helper
        success = ws_manager.send_notification(user3.id, "Welcome to the game!", "success")
        print(f"   Send welcome notification to Charlie: {'✓' if success else '✗'}")
        
        # Test chat message simulation
        print("\n9. Testing chat message broadcasting...")
        
        chat_data = {
            "user_id": user1.id,
            "username": user1.username,
            "message": "Hello everyone!",
            "is_spectator": False,
            "timestamp": "2024-01-01T12:05:00Z"
        }
        
        ws_manager.broadcast_to_table(table.id, GameEvent.CHAT_MESSAGE, chat_data)
        print("   Broadcasted chat message from Alice")
        
        # Test disconnect handling
        print("\n10. Testing disconnect/reconnect handling...")
        
        # Simulate Alice disconnect
        print("   Simulating Alice disconnect...")
        ws_manager.handle_table_disconnect(user1.id, table.id)
        
        # Check participants after disconnect
        participants = ws_manager.get_table_participants(table.id)
        print(f"   Table participants after disconnect: {len(participants)}")
        
        # Simulate Alice reconnect
        print("   Simulating Alice reconnect...")
        # Re-add Alice's session for reconnect test
        ws_manager.user_sessions[user1.id] = session1
        ws_manager.session_users[session1] = user1.id
        
        with patch('src.online_poker.services.websocket_manager.PlayerSessionManager.handle_player_reconnect') as mock_reconnect:
            with patch('src.online_poker.services.websocket_manager.GameStateManager.generate_game_state_view') as mock_state:
                mock_reconnect.return_value = (True, "Reconnected successfully", {"session": "info"})
                mock_game_state = type('MockGameState', (), {'to_dict': lambda: {"game": "state"}})()
                mock_state.return_value = mock_game_state
                
                success = ws_manager.handle_table_reconnect(user1.id, table.id)
                print(f"   Alice reconnect: {'✓' if success else '✗'}")
        
        # Test leaving table rooms
        print("\n11. Testing table room leaving...")
        
        # Bob leaves table room
        success = ws_manager.leave_table_room(user2.id, table.id)
        print(f"   Bob leave table room: {'✓' if success else '✗'}")
        
        # Check final participants
        participants = ws_manager.get_table_participants(table.id)
        print(f"   Final table participants: {len(participants)}")
        
        # Test connection statistics
        print("\n12. Testing connection statistics...")
        
        stats = ws_manager.get_connection_stats()
        print(f"   Connection statistics:")
        print(f"     Connected users: {stats['connected_users']}")
        print(f"     Active tables: {stats['active_tables']}")
        print(f"     Total room participants: {stats['total_room_participants']}")
        
        # Test game event constants
        print("\n13. Testing game event constants...")
        
        events = [
            GameEvent.PLAYER_JOINED,
            GameEvent.PLAYER_LEFT,
            GameEvent.GAME_STATE_UPDATE,
            GameEvent.PLAYER_ACTION,
            GameEvent.HAND_COMPLETE,
            GameEvent.CHAT_MESSAGE,
            GameEvent.PLAYER_DISCONNECTED,
            GameEvent.PLAYER_RECONNECTED,
            GameEvent.TABLE_UPDATE,
            GameEvent.ERROR,
            GameEvent.NOTIFICATION
        ]
        
        print(f"   Available game events: {len(events)}")
        for event in events:
            print(f"     - {event}")
        
        # Test error handling
        print("\n14. Testing error handling...")
        
        # Try to join room for non-existent user
        success = ws_manager.join_table_room("non-existent-user", table.id)
        print(f"   Join room with invalid user: {'✓' if not success else '✗'} (should fail)")
        
        # Try to send message to non-existent user
        success = ws_manager.send_to_user("non-existent-user", GameEvent.NOTIFICATION, {"test": "data"})
        print(f"   Send to invalid user: {'✓' if not success else '✗'} (should fail)")
        
        # Try to get participants for non-existent table
        participants = ws_manager.get_table_participants("non-existent-table")
        print(f"   Get participants for invalid table: {len(participants)} (should be 0)")
        
        print("\n=== Demo completed successfully! ===")


if __name__ == "__main__":
    # Import patch for the demo
    from unittest.mock import patch
    main()