#!/usr/bin/env python3
"""Demo script for testing the game state management system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask
from src.online_poker.database import db
from src.online_poker.services.game_state_manager import GameStateManager
from src.online_poker.services.player_session_manager import PlayerSessionManager
from src.online_poker.services.user_manager import UserManager
from src.online_poker.services.table_manager import TableManager
from src.online_poker.models.table import PokerTable
from src.online_poker.models.game_state_view import GamePhase
from generic_poker.game.betting import BettingStructure


def create_test_app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_game_state.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    
    return app


def main():
    """Run the game state manager demo."""
    print("=== Game State Manager Demo ===\n")
    
    app = create_test_app()
    
    with app.app_context():
        # Create test users
        print("1. Creating test users...")
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
        print("\n2. Creating test table...")
        table = PokerTable(
            name="Demo Game State Table",
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
        
        # Join players to table and game
        print("\n3. Players joining table and game...")
        
        # Alice joins
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            user1.id, table.id, 200
        )
        if success:
            print(f"   ✓ Alice joined: {message}")
        else:
            print(f"   ✗ Alice failed: {message}")
        
        # Bob joins
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            user2.id, table.id, 150
        )
        if success:
            print(f"   ✓ Bob joined: {message}")
        else:
            print(f"   ✗ Bob failed: {message}")
        
        # Charlie joins as spectator
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            user3.id, table.id, 0, as_spectator=True
        )
        if success:
            print(f"   ✓ Charlie joined as spectator: {message}")
        else:
            print(f"   ✗ Charlie spectator failed: {message}")
        
        # Test game state generation
        print("\n4. Generating game state views...")
        
        # Alice's perspective (player)
        alice_state = GameStateManager.generate_game_state_view(table.id, user1.id, False)
        if alice_state:
            print(f"   Alice's view:")
            print(f"     Session ID: {alice_state.session_id}")
            print(f"     Game phase: {alice_state.game_phase.value}")
            print(f"     Hand number: {alice_state.hand_number}")
            print(f"     Players: {len(alice_state.players)}")
            print(f"     Is spectator: {alice_state.is_spectator}")
            print(f"     Valid actions: {len(alice_state.valid_actions)}")
            
            print("     Player details:")
            for player in alice_state.players:
                print(f"       - {player.username} (Seat {player.seat_number}): ${player.chip_stack}")
                print(f"         Connected: {player.is_connected}, Cards: {len(player.cards)}")
        else:
            print("   ✗ Failed to generate Alice's game state")
        
        # Bob's perspective (player)
        bob_state = GameStateManager.generate_game_state_view(table.id, user2.id, False)
        if bob_state:
            print(f"   Bob's view:")
            print(f"     Game phase: {bob_state.game_phase.value}")
            print(f"     Players: {len(bob_state.players)}")
            print(f"     Valid actions: {len(bob_state.valid_actions)}")
        else:
            print("   ✗ Failed to generate Bob's game state")
        
        # Charlie's perspective (spectator)
        charlie_state = GameStateManager.generate_game_state_view(table.id, user3.id, True)
        if charlie_state:
            print(f"   Charlie's view (spectator):")
            print(f"     Game phase: {charlie_state.game_phase.value}")
            print(f"     Players: {len(charlie_state.players)}")
            print(f"     Is spectator: {charlie_state.is_spectator}")
            print(f"     Valid actions: {len(charlie_state.valid_actions)} (should be 0)")
        else:
            print("   ✗ Failed to generate Charlie's game state")
        
        # Test game state components
        print("\n5. Testing game state components...")
        
        if alice_state:
            # Test pot info
            pot_info = alice_state.pot_info
            print(f"   Pot info:")
            print(f"     Main pot: ${pot_info.main_pot}")
            print(f"     Total pot: ${pot_info.total_pot}")
            print(f"     Current bet: ${pot_info.current_bet}")
            
            # Test community cards
            community_cards = alice_state.community_cards
            print(f"   Community cards: {community_cards}")
            
            # Test table info
            table_info = alice_state.table_info
            print(f"   Table info:")
            print(f"     Name: {table_info.get('name', 'N/A')}")
            print(f"     Variant: {table_info.get('variant', 'N/A')}")
            print(f"     Stakes: {table_info.get('stakes', 'N/A')}")
            
            # Test player methods
            alice_player = alice_state.get_player_by_id(user1.id)
            if alice_player:
                print(f"   Alice player info:")
                print(f"     Position: {alice_player.position}")
                print(f"     Is current player: {alice_player.is_current_player}")
                print(f"     Is connected: {alice_player.is_connected}")
            
            # Test active players
            active_players = alice_state.get_active_players()
            print(f"   Active players: {len(active_players)}")
            
            # Test connected players
            connected_players = alice_state.get_connected_players()
            print(f"   Connected players: {len(connected_players)}")
        
        # Test state change detection
        print("\n6. Testing state change detection...")
        
        if alice_state and bob_state:
            # Create a modified state to test change detection
            modified_state = alice_state
            modified_state.game_phase = GamePhase.FLOP
            modified_state.current_player = user2.id
            modified_state.pot_info.main_pot = 100
            
            # Detect changes
            changes = GameStateManager.detect_state_changes(alice_state, modified_state)
            print(f"   Detected {len(changes)} changes:")
            for change in changes:
                print(f"     - {change.update_type}: {change.data}")
        
        # Test game state updates
        print("\n7. Testing game state updates...")
        
        # Create a test update
        update = GameStateManager.create_game_state_update(
            table.id, "test_update", {"message": "Test update"}, [user1.id, user2.id]
        )
        
        print(f"   Created update:")
        print(f"     Type: {update.update_type}")
        print(f"     Data: {update.data}")
        print(f"     Affected players: {update.affected_players}")
        print(f"     Timestamp: {update.timestamp}")
        
        # Test hand completion processing
        print("\n8. Testing hand completion processing...")
        
        from src.online_poker.services.game_orchestrator import game_orchestrator
        session = game_orchestrator.get_session(table.id)
        if session:
            hand_result = GameStateManager.process_hand_completion(session)
            if hand_result:
                print(f"   Hand result:")
                print(f"     Hand number: {hand_result.hand_number}")
                print(f"     Winners: {len(hand_result.winners)}")
                print(f"     Final board: {hand_result.final_board}")
                print(f"     Summary: {hand_result.hand_summary}")
            else:
                print("   No hand result available")
        
        # Test serialization
        print("\n9. Testing serialization...")
        
        if alice_state:
            # Convert to dictionary
            state_dict = alice_state.to_dict()
            print(f"   Serialized state keys: {list(state_dict.keys())}")
            print(f"   Serialized size: {len(str(state_dict))} characters")
            
            # Test individual component serialization
            if alice_state.players:
                player_dict = alice_state.players[0].to_dict()
                print(f"   Player serialization keys: {list(player_dict.keys())}")
            
            pot_dict = alice_state.pot_info.to_dict()
            print(f"   Pot info serialization keys: {list(pot_dict.keys())}")
            
            if alice_state.valid_actions:
                action_dict = alice_state.valid_actions[0].to_dict()
                print(f"   Action serialization keys: {list(action_dict.keys())}")
        
        # Test error handling
        print("\n10. Testing error handling...")
        
        # Try to generate state for non-existent table
        invalid_state = GameStateManager.generate_game_state_view("invalid-table", user1.id, False)
        print(f"   Invalid table state: {invalid_state is None}")
        
        # Try to generate state for non-existent user
        invalid_user_state = GameStateManager.generate_game_state_view(table.id, "invalid-user", False)
        print(f"   Invalid user state: {invalid_user_state is not None}")  # Should still work
        
        print("\n=== Demo completed successfully! ===")


if __name__ == "__main__":
    main()