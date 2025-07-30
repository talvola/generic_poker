#!/usr/bin/env python3
"""Demo script for testing the disconnect manager system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask
from src.online_poker.database import db
from src.online_poker.services.disconnect_manager import DisconnectManager, DisconnectedPlayer
from src.online_poker.services.user_manager import UserManager
from src.online_poker.models.table import PokerTable
from generic_poker.game.betting import BettingStructure
from datetime import datetime, timedelta


def create_test_app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_disconnect.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    
    return app


def main():
    """Run the disconnect manager demo."""
    print("=== Disconnect Manager Demo ===\n")
    
    app = create_test_app()
    
    with app.app_context():
        # Create disconnect manager
        print("1. Creating disconnect manager...")
        disconnect_manager = DisconnectManager()
        print(f"   Disconnect manager initialized")
        print(f"   Tracking: {len(disconnect_manager.disconnected_players)} disconnected players")
        
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
            name="Demo Disconnect Table",
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
        
        # Test DisconnectedPlayer class
        print("\n4. Testing DisconnectedPlayer class...")
        
        # Create disconnected player
        disconnect_time = datetime.utcnow()
        disconnected_player = DisconnectedPlayer(user1.id, table.id, disconnect_time, 5)
        
        print(f"   Created disconnected player:")
        print(f"     User: {user1.id}")
        print(f"     Table: {table.id}")
        print(f"     Disconnect time: {disconnect_time}")
        print(f"     Timeout: {disconnected_player.timeout_minutes} minutes")
        print(f"     Is expired: {disconnected_player.is_expired()}")
        print(f"     Time remaining: {disconnected_player.time_remaining()} seconds")
        print(f"     Has auto-folded: {disconnected_player.has_auto_folded}")
        
        # Test expired player
        old_disconnect_time = datetime.utcnow() - timedelta(minutes=10)
        expired_player = DisconnectedPlayer(user2.id, table.id, old_disconnect_time, 5)
        print(f"   Expired player (10 min ago):")
        print(f"     Is expired: {expired_player.is_expired()}")
        print(f"     Time remaining: {expired_player.time_remaining()} seconds")
        
        # Test disconnect handling
        print("\n5. Testing disconnect handling...")
        
        # Mock the game orchestrator and related services to prevent hanging
        with patch('src.online_poker.services.disconnect_manager.PlayerSessionManager.handle_player_disconnect') as mock_handle_disconnect:
            with patch('src.online_poker.services.disconnect_manager.get_websocket_manager') as mock_get_ws:
                # Mock successful disconnect handling
                mock_handle_disconnect.return_value = None
                mock_get_ws.return_value = None  # No WebSocket manager in demo
                
                # Mock the timer to prevent actual auto-fold execution
                with patch('src.online_poker.services.disconnect_manager.Timer') as mock_timer:
                    # Mock timer to not actually start
                    from unittest.mock import MagicMock
                    mock_timer_instance = MagicMock()
                    mock_timer.return_value = mock_timer_instance
                    
                    # Alice disconnects (current player)
                    success, message = disconnect_manager.handle_player_disconnect(
                        user1.id, table.id, is_current_player=True
                    )
                    print(f"   Alice disconnect (current player): {'✓' if success else '✗'} {message}")
                    
                    # Bob disconnects (not current player)
                    success, message = disconnect_manager.handle_player_disconnect(
                        user2.id, table.id, is_current_player=False
                    )
                    print(f"   Bob disconnect (not current): {'✓' if success else '✗'} {message}")
                    
                    # Charlie disconnects
                    success, message = disconnect_manager.handle_player_disconnect(
                        user3.id, table.id, is_current_player=False
                    )
                    print(f"   Charlie disconnect: {'✓' if success else '✗'} {message}")
        
        # Check disconnect tracking
        print(f"   Total disconnected players: {len(disconnect_manager.disconnected_players)}")
        print(f"   Tables with disconnects: {len(disconnect_manager.table_disconnects)}")
        
        # Test getting disconnect info
        print("\n6. Testing disconnect information retrieval...")
        
        alice_info = disconnect_manager.get_disconnected_player_info(user1.id)
        if alice_info:
            print(f"   Alice disconnect info:")
            print(f"     Table: {alice_info['table_id']}")
            print(f"     Timeout: {alice_info['timeout_minutes']} minutes")
            print(f"     Time remaining: {alice_info['time_remaining']} seconds")
            print(f"     Has auto-folded: {alice_info['has_auto_folded']}")
            print(f"     Is expired: {alice_info['is_expired']}")
        
        # Test table disconnects
        table_disconnects = disconnect_manager.get_table_disconnects(table.id)
        print(f"   Table disconnects: {len(table_disconnects)}")
        for disconnect in table_disconnects:
            print(f"     - User {disconnect['user_id']}: {disconnect['time_remaining']}s remaining")
        
        # Test player status checks
        print("\n7. Testing player status checks...")
        
        print(f"   Alice is disconnected: {disconnect_manager.is_player_disconnected(user1.id)}")
        print(f"   Bob is disconnected: {disconnect_manager.is_player_disconnected(user2.id)}")
        print(f"   Non-existent user disconnected: {disconnect_manager.is_player_disconnected('fake-user')}")
        
        # Test reconnection
        print("\n8. Testing reconnection handling...")
        
        # Alice reconnects
        with patch('src.online_poker.services.disconnect_manager.PlayerSessionManager.handle_player_reconnect') as mock_reconnect:
            with patch('src.online_poker.services.disconnect_manager.GameStateManager.generate_game_state_view') as mock_state:
                with patch('src.online_poker.services.disconnect_manager.get_websocket_manager') as mock_ws:
                    # Mock successful reconnect
                    mock_reconnect.return_value = (True, "Reconnected", {"session": "info"})
                    mock_game_state = type('MockGameState', (), {'to_dict': lambda: {"game": "state"}})()
                    mock_state.return_value = mock_game_state
                    mock_ws.return_value = None  # No WebSocket manager in demo
                    
                    success, message, reconnect_info = disconnect_manager.handle_player_reconnect(
                        user1.id, table.id
                    )
                    
                    print(f"   Alice reconnect: {'✓' if success else '✗'} {message}")
                    if reconnect_info:
                        print(f"     Disconnect duration: {reconnect_info['disconnect_duration']:.1f}s")
                        print(f"     Had auto-folded: {reconnect_info['had_auto_folded']}")
        
        # Try to reconnect non-disconnected player
        success, message, reconnect_info = disconnect_manager.handle_player_reconnect(
            "fake-user", table.id
        )
        print(f"   Fake user reconnect: {'✓' if success else '✗'} {message}")
        
        # Test expired reconnection
        print("\n9. Testing expired reconnection...")
        
        # Add expired disconnect
        old_time = datetime.utcnow() - timedelta(minutes=15)
        expired_disconnect = DisconnectedPlayer(user3.id, table.id, old_time, 5)
        disconnect_manager.disconnected_players[user3.id] = expired_disconnect
        disconnect_manager.table_disconnects[table.id] = {user3.id}
        
        success, message, reconnect_info = disconnect_manager.handle_player_reconnect(
            user3.id, table.id
        )
        print(f"   Charlie expired reconnect: {'✓' if success else '✗'} {message}")
        
        # Test disconnect statistics
        print("\n10. Testing disconnect statistics...")
        
        # Add some test disconnects for stats
        disconnect_manager.disconnected_players[user2.id] = DisconnectedPlayer(
            user2.id, table.id, datetime.utcnow() - timedelta(minutes=2)
        )
        disconnect_manager.disconnected_players[user2.id].has_auto_folded = True
        
        stats = disconnect_manager.get_disconnect_stats()
        print(f"   Disconnect statistics:")
        print(f"     Total disconnected: {stats['total_disconnected_players']}")
        print(f"     Auto-folded: {stats['auto_folded_players']}")
        print(f"     Expired: {stats['expired_disconnects']}")
        print(f"     Active table disconnects: {stats['active_table_disconnects']}")
        print(f"     Average disconnect time: {stats['average_disconnect_time']:.1f}s")
        
        # Test cleanup
        print("\n11. Testing cleanup operations...")
        
        # Add an expired disconnect for cleanup test
        very_old_time = datetime.utcnow() - timedelta(minutes=20)
        very_expired = DisconnectedPlayer("expired-user", table.id, very_old_time, 5)
        disconnect_manager.disconnected_players["expired-user"] = very_expired
        
        with patch.object(disconnect_manager, '_handle_auto_removal') as mock_removal:
            cleaned_count = disconnect_manager.cleanup_expired_disconnects()
            print(f"   Cleaned up expired disconnects: {cleaned_count}")
            if cleaned_count > 0:
                print(f"   Auto-removal called {mock_removal.call_count} times")
        
        # Test force operations
        print("\n12. Testing force operations...")
        
        # Force reconnect
        with patch.object(disconnect_manager, 'handle_player_reconnect') as mock_reconnect:
            mock_reconnect.return_value = (True, "Force reconnected", {"info": "data"})
            
            success, message = disconnect_manager.force_reconnect_player(user2.id, table.id)
            print(f"   Force reconnect Bob: {'✓' if success else '✗'} {message}")
        
        # Force remove
        disconnect_manager.disconnected_players["test-user"] = DisconnectedPlayer(
            "test-user", table.id, datetime.utcnow()
        )
        
        with patch.object(disconnect_manager, '_handle_auto_removal') as mock_removal:
            success, message = disconnect_manager.force_remove_player("test-user")
            print(f"   Force remove test user: {'✓' if success else '✗'} {message}")
        
        # Test error cases
        print("\n13. Testing error cases...")
        
        # Force reconnect non-disconnected player
        success, message = disconnect_manager.force_reconnect_player("non-disconnected", table.id)
        print(f"   Force reconnect non-disconnected: {'✓' if success else '✗'} {message}")
        
        # Force remove non-disconnected player
        success, message = disconnect_manager.force_remove_player("non-disconnected")
        print(f"   Force remove non-disconnected: {'✓' if success else '✗'} {message}")
        
        # Final state
        print("\n14. Final state...")
        final_stats = disconnect_manager.get_disconnect_stats()
        print(f"   Final disconnected players: {final_stats['total_disconnected_players']}")
        print(f"   Final active table disconnects: {final_stats['active_table_disconnects']}")
        
        print("\n=== Demo completed successfully! ===")


if __name__ == "__main__":
    # Import patch for the demo
    from unittest.mock import patch
    main()