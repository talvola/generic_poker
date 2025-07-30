"""Test database setup and models."""

import pytest
from flask import Flask
from src.online_poker.config import TestingConfig
from src.online_poker.database import init_database, db
from src.online_poker.models import User, PokerTable, Transaction, GameHistory
from src.online_poker.db_utils import (
    create_user_with_validation, create_table_with_validation,
    process_transaction, get_user_statistics
)


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    init_database(app)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_user_model(app):
    """Test User model functionality."""
    with app.app_context():
        # Create user
        user = User("testuser", "test@example.com", "password123")
        db.session.add(user)
        db.session.commit()
        
        # Test password verification
        assert user.check_password("password123")
        assert not user.check_password("wrongpassword")
        
        # Test bankroll operations
        assert user.can_afford_buyin(500)
        assert not user.can_afford_buyin(2000)
        
        assert user.update_bankroll(500)
        assert user.bankroll == 1500
        
        assert not user.update_bankroll(-2000)  # Should fail
        assert user.bankroll == 1500  # Should remain unchanged


def test_poker_table_model(app):
    """Test PokerTable model functionality."""
    with app.app_context():
        # Create user first
        user = User("creator", "creator@example.com", "password123")
        db.session.add(user)
        db.session.commit()
        
        # Create table
        stakes = {"small_blind": 1, "big_blind": 2}
        table = PokerTable(
            name="Test Table",
            variant="texas_holdem",
            betting_structure="No-Limit",
            stakes=stakes,
            max_players=6,
            creator_id=user.id
        )
        db.session.add(table)
        db.session.commit()
        
        # Test stakes operations
        assert table.get_stakes() == stakes
        assert table.get_minimum_buyin() == 40  # 20 * big_blind
        assert table.get_maximum_buyin() == 400  # 200 * big_blind
        
        # Test activity tracking
        assert not table.is_inactive(30)
        table.update_activity()


def test_transaction_model(app):
    """Test Transaction model functionality."""
    with app.app_context():
        # Create user
        user = User("player", "player@example.com", "password123")
        db.session.add(user)
        db.session.commit()
        
        # Create transaction
        transaction = Transaction.create_buyin_transaction(
            user.id, 100, "table123", "Test Table"
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Test transaction properties
        assert transaction.is_debit()
        assert not transaction.is_credit()
        assert transaction.get_absolute_amount() == 100
        assert transaction.transaction_type == Transaction.TYPE_BUYIN


def test_game_history_model(app):
    """Test GameHistory model functionality."""
    with app.app_context():
        # Create user and table
        user = User("player", "player@example.com", "password123")
        db.session.add(user)
        db.session.commit()
        
        table = PokerTable(
            name="Test Table",
            variant="texas_holdem",
            betting_structure="No-Limit",
            stakes={"small_blind": 1, "big_blind": 2},
            max_players=6,
            creator_id=user.id
        )
        db.session.add(table)
        db.session.commit()
        
        # Create game history
        players = [{"user_id": user.id, "username": "player", "starting_chips": 1000}]
        actions = [{"player": user.id, "action": "fold"}]
        results = {"winners": [user.id], "total_pot": 100, "player_winnings": {user.id: 100}}
        
        history = GameHistory(
            table_id=table.id,
            hand_number=1,
            players=players,
            actions=actions,
            results=results,
            variant="texas_holdem",
            betting_structure="No-Limit",
            stakes={"small_blind": 1, "big_blind": 2}
        )
        db.session.add(history)
        db.session.commit()
        
        # Test history operations
        assert history.get_total_pot() == 100
        assert history.get_player_count() == 1
        assert history.was_player_involved(user.id)
        assert user.id in history.get_winner_ids()


def test_database_utilities(app):
    """Test database utility functions."""
    with app.app_context():
        # Test user creation
        user = create_user_with_validation("testuser", "test@example.com", "password123")
        assert user is not None
        assert user.username == "testuser"
        
        # Test duplicate user creation
        with pytest.raises(Exception):
            create_user_with_validation("testuser", "other@example.com", "password123")
        
        # Test table creation
        stakes = {"small_blind": 1, "big_blind": 2}
        table = create_table_with_validation(
            "Test Table", "texas_holdem", "No-Limit", stakes, 6, user.id
        )
        assert table is not None
        assert table.name == "Test Table"
        
        # Test transaction processing
        initial_bankroll = user.bankroll
        success = process_transaction(
            user.id, -100, Transaction.TYPE_BUYIN, "Test buy-in", table.id
        )
        assert success
        
        # Refresh user from database
        db.session.refresh(user)
        assert user.bankroll == initial_bankroll - 100
        
        # Test user statistics
        stats = get_user_statistics(user.id)
        assert stats['username'] == "testuser"
        assert stats['total_buyins'] == 100


def test_model_relationships(app):
    """Test model relationships."""
    with app.app_context():
        # Create user
        user = User("creator", "creator@example.com", "password123")
        db.session.add(user)
        db.session.commit()
        
        # Create table
        table = PokerTable(
            name="Test Table",
            variant="texas_holdem",
            betting_structure="No-Limit",
            stakes={"small_blind": 1, "big_blind": 2},
            max_players=6,
            creator_id=user.id
        )
        db.session.add(table)
        db.session.commit()
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            amount=-100,
            transaction_type=Transaction.TYPE_BUYIN,
            description="Test transaction",
            table_id=table.id
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Test relationships
        assert table.creator == user
        assert table in user.created_tables
        assert transaction.user == user
        assert transaction in user.transactions


if __name__ == '__main__':
    pytest.main([__file__])