#!/usr/bin/env python3
"""Demo script for testing the player session management system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask
from src.online_poker.database import db
from src.online_poker.services.player_session_manager import PlayerSessionManager
from src.online_poker.services.user_manager import UserManager
from src.online_poker.services.table_manager import TableManager
from src.online_poker.models.table import PokerTable
from generic_poker.game.betting import BettingStructure


def create_test_app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_player_session.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    
    return app


def main():
    """Run the player session manager demo."""
    print("=== Player Session Manager Demo ===\n")
    
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
        
        print(f"   Users: {user1.username} (${user1.bankroll}), {user2.username} (${user2.bankroll}), {user3.username} (${user3.bankroll})")
        
        # Create a test table
        print("\n2. Creating test table...")
        table = PokerTable(
            name="Demo Player Session Table",
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
        stakes = table.get_stakes()
        print(f"   Stakes: ${stakes['small_blind']}/${stakes['big_blind']}")
        print(f"   Buy-in range: ${table.get_minimum_buyin()} - ${table.get_maximum_buyin()}")
        
        # Test buy-in validation
        print("\n3. Testing buy-in validation...")
        
        # Valid buy-in
        is_valid, message = PlayerSessionManager.validate_buy_in(user1.id, table.id, 500)
        print(f"   Alice $500 buy-in: {'✓' if is_valid else '✗'} {message}")
        
        # Below minimum
        is_valid, message = PlayerSessionManager.validate_buy_in(user1.id, table.id, 50)
        print(f"   Alice $50 buy-in: {'✓' if is_valid else '✗'} {message}")
        
        # Above maximum
        is_valid, message = PlayerSessionManager.validate_buy_in(user1.id, table.id, 1000)
        print(f"   Alice $1000 buy-in: {'✓' if is_valid else '✗'} {message}")
        
        # Insufficient bankroll (Charlie has $1000, trying $800 which is above max anyway)
        is_valid, message = PlayerSessionManager.validate_buy_in(user3.id, table.id, 300)
        print(f"   Charlie $300 buy-in: {'✓' if is_valid else '✗'} {message}")
        
        # Test joining table and game
        print("\n4. Testing player joining...")
        
        # Alice joins as player
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            user1.id, table.id, 200  # Maximum buy-in
        )
        if success:
            print(f"   ✓ Alice joined: {message}")
            print(f"     Session ID: {session_info['session']['session_id']}")
            print(f"     Seat: {session_info['access_record']['seat_number']}")
            print(f"     Stack: ${session_info['access_record']['current_stack']}")
        else:
            print(f"   ✗ Alice failed: {message}")
        
        # Bob joins as player
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            user2.id, table.id, 150  # Within buy-in range
        )
        if success:
            print(f"   ✓ Bob joined: {message}")
            print(f"     Seat: {session_info['access_record']['seat_number']}")
            print(f"     Stack: ${session_info['access_record']['current_stack']}")
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
        
        # Test table session info
        print("\n5. Table session information...")
        table_info = PlayerSessionManager.get_table_session_info(table.id)
        if table_info:
            print(f"   Table: {table_info['table']['name']}")
            print(f"   Players: {table_info['stats']['total_players']}")
            print(f"   Spectators: {table_info['stats']['total_spectators']}")
            print(f"   Available seats: {table_info['stats']['seats_available']}")
            print(f"   Game session active: {table_info['stats']['has_game_session']}")
            
            print("   Active players:")
            for player in table_info['players']:
                print(f"     - {player['username']} (Seat {player['seat_number']}, ${player['current_stack']})")
            
            print("   Spectators:")
            for spectator in table_info['spectators']:
                print(f"     - {spectator['username']}")
        
        # Test player info
        print("\n6. Individual player information...")
        alice_info = PlayerSessionManager.get_player_info(user1.id, table.id)
        if alice_info:
            print(f"   Alice:")
            print(f"     Game status: {alice_info['game_status']}")
            print(f"     Buy-in: ${alice_info['buy_in_amount']}")
            print(f"     Current stack: ${alice_info['current_stack']}")
            print(f"     Session duration: {alice_info['session_duration']:.1f}s")
        
        # Test disconnect/reconnect
        print("\n7. Testing disconnect/reconnect...")
        
        # Alice disconnects
        success, message = PlayerSessionManager.handle_player_disconnect(user1.id, table.id)
        if success:
            print(f"   ✓ Alice disconnect: {message}")
        else:
            print(f"   ✗ Alice disconnect failed: {message}")
        
        # Check game session state
        table_info = PlayerSessionManager.get_table_session_info(table.id)
        if table_info and table_info['session']:
            session = table_info['session']
            print(f"   Game state after disconnect: {session['game_state']}")
            print(f"   Connected players: {session['connected_players']}")
            print(f"   Disconnected players: {session['disconnected_players']}")
            print(f"   Is paused: {session['is_paused']} ({session['pause_reason']})")
        
        # Alice reconnects
        success, message, session_info = PlayerSessionManager.handle_player_reconnect(user1.id, table.id)
        if success:
            print(f"   ✓ Alice reconnect: {message}")
            session = session_info['session']
            print(f"   Game state after reconnect: {session['game_state']}")
            print(f"   Is paused: {session['is_paused']}")
        else:
            print(f"   ✗ Alice reconnect failed: {message}")
        
        # Test leaving
        print("\n8. Testing player leaving...")
        
        # Charlie leaves (spectator)
        success, message, cashout_info = PlayerSessionManager.leave_table_and_game(
            user3.id, table.id, "Demo finished"
        )
        if success:
            print(f"   ✓ Charlie left: {message}")
            if cashout_info:
                print(f"     Cashout info: {cashout_info}")
        else:
            print(f"   ✗ Charlie leave failed: {message}")
        
        # Bob leaves (player)
        success, message, cashout_info = PlayerSessionManager.leave_table_and_game(
            user2.id, table.id, "Demo finished"
        )
        if success:
            print(f"   ✓ Bob left: {message}")
            if cashout_info:
                print(f"     Initial stack: ${cashout_info['initial_stack']}")
                print(f"     Final stack: ${cashout_info['final_stack']}")
                print(f"     Profit/Loss: ${cashout_info['profit_loss']}")
                print(f"     Session duration: {cashout_info['session_duration']:.1f}s")
        else:
            print(f"   ✗ Bob leave failed: {message}")
        
        # Check final table state
        print("\n9. Final table state...")
        table_info = PlayerSessionManager.get_table_session_info(table.id)
        if table_info:
            print(f"   Players remaining: {table_info['stats']['total_players']}")
            print(f"   Spectators remaining: {table_info['stats']['total_spectators']}")
            
            if table_info['session']:
                session = table_info['session']
                print(f"   Game session paused: {session['is_paused']} ({session['pause_reason']})")
        
        # Check user bankrolls
        print("\n10. Final user bankrolls...")
        user1 = UserManager.get_user_by_id(user1.id)
        user2 = UserManager.get_user_by_id(user2.id)
        user3 = UserManager.get_user_by_id(user3.id)
        print(f"   Alice: ${user1.bankroll}")
        print(f"   Bob: ${user2.bankroll}")
        print(f"   Charlie: ${user3.bankroll}")
        
        print("\n=== Demo completed successfully! ===")


if __name__ == "__main__":
    main()