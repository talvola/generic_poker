#!/usr/bin/env python3
"""Demo script for testing the game orchestration system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask
from src.online_poker.database import db
from src.online_poker.services.game_orchestrator import game_orchestrator
from src.online_poker.services.user_manager import UserManager
from src.online_poker.services.table_manager import TableManager
from src.online_poker.models.table import PokerTable
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game_state import PlayerAction


def create_test_app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_orchestrator.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    
    return app


def main():
    """Run the game orchestrator demo."""
    print("=== Game Orchestrator Demo ===\n")
    
    app = create_test_app()
    
    with app.app_context():
        # Create or get test users
        print("1. Setting up test users...")
        try:
            user1 = UserManager.create_user("alice", "alice@example.com", "password123", 2000)
        except:
            user1 = UserManager.get_user_by_username("alice")
        
        try:
            user2 = UserManager.create_user("bob", "bob@example.com", "password123", 2000)
        except:
            user2 = UserManager.get_user_by_username("bob")
        
        try:
            user3 = UserManager.create_user("charlie", "charlie@example.com", "password123", 2000)
        except:
            user3 = UserManager.get_user_by_username("charlie")
        
        print(f"   Using users: {user1.username}, {user2.username}, {user3.username}")
        
        # Create a test table
        print("\n2. Creating test table...")
        table = PokerTable(
            name="Demo Hold'em Table",
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
        
        # Test orchestrator stats
        print("\n3. Initial orchestrator stats...")
        stats = game_orchestrator.get_orchestrator_stats()
        print(f"   Sessions: {stats['total_sessions']}")
        print(f"   Players: {stats['total_players']}")
        
        # Create a game session
        print("\n4. Creating game session...")
        success, message, session = game_orchestrator.create_session(table.id)
        if success:
            print(f"   ✓ {message}")
            print(f"   Session ID: {session.session_id}")
        else:
            print(f"   ✗ {message}")
            return
        
        # Get session info
        print("\n5. Session information...")
        info = session.get_session_info()
        print(f"   Table: {info['table_name']}")
        print(f"   Variant: {info['variant']}")
        print(f"   Stakes: {info['stakes']}")
        print(f"   State: {info['game_state']}")
        print(f"   Players: {info['connected_players']}")
        
        # Add players to session
        print("\n6. Adding players to session...")
        
        # Add Alice with appropriate buy-in (20x big blind = 200)
        success, message = session.add_player(user1.id, user1.username, 200)
        if success:
            print(f"   ✓ {user1.username} joined: {message}")
        else:
            print(f"   ✗ {user1.username} failed: {message}")
        
        # Add Bob with appropriate buy-in
        success, message = session.add_player(user2.id, user2.username, 150)
        if success:
            print(f"   ✓ {user2.username} joined: {message}")
        else:
            print(f"   ✗ {user2.username} failed: {message}")
        
        # Add Charlie as spectator
        success, message = session.add_spectator(user3.id)
        if success:
            print(f"   ✓ {user3.username} joined as spectator: {message}")
        else:
            print(f"   ✗ {user3.username} spectator failed: {message}")
        
        # Check session state after adding players
        print("\n7. Session state after adding players...")
        info = session.get_session_info()
        print(f"   Connected players: {info['connected_players']}")
        print(f"   Spectators: {info['spectators']}")
        print(f"   Game state: {info['game_state']}")
        print(f"   Is paused: {info['is_paused']}")
        if info['is_paused']:
            print(f"   Pause reason: {info['pause_reason']}")
        
        # Test player disconnect/reconnect
        print("\n8. Testing disconnect/reconnect...")
        session.handle_player_disconnect(user1.id)
        info = session.get_session_info()
        print(f"   After Alice disconnect - Connected: {info['connected_players']}, Disconnected: {info['disconnected_players']}")
        print(f"   Is paused: {info['is_paused']} ({info['pause_reason']})")
        
        success, message = session.handle_player_reconnect(user1.id)
        if success:
            print(f"   ✓ Alice reconnected: {message}")
        else:
            print(f"   ✗ Alice reconnect failed: {message}")
        
        info = session.get_session_info()
        print(f"   After reconnect - Connected: {info['connected_players']}, Is paused: {info['is_paused']}")
        
        # Test orchestrator stats with active session
        print("\n9. Orchestrator stats with active session...")
        stats = game_orchestrator.get_orchestrator_stats()
        print(f"   Total sessions: {stats['total_sessions']}")
        print(f"   Active sessions: {stats['active_sessions']}")
        print(f"   Total players: {stats['total_players']}")
        print(f"   Total spectators: {stats['total_spectators']}")
        print(f"   Avg players per session: {stats['average_players_per_session']:.1f}")
        
        # Test session removal
        print("\n10. Removing session...")
        success = game_orchestrator.remove_session(table.id)
        if success:
            print("   ✓ Session removed successfully")
        else:
            print("   ✗ Failed to remove session")
        
        print(f"   Remaining sessions: {game_orchestrator.get_session_count()}")
        
        print("\n=== Demo completed successfully! ===")


if __name__ == "__main__":
    main()