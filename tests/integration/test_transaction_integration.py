"""Integration tests for transaction management system."""

import pytest
from flask import Flask

from src.online_poker.database import db, init_database
from src.online_poker.services.user_manager import UserManager
from src.online_poker.services.transaction_manager import TransactionManager, InsufficientFundsError
from src.online_poker.models.transaction import Transaction


@pytest.fixture
def app():
    """Create test Flask app with database setup."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    init_database(app)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        user = UserManager.create_user("testuser", "test@example.com", "password123", 1000)
        return user


class TestTransactionIntegration:
    """Test transaction management integration."""
    
    def test_create_bonus_transaction(self, app, test_user):
        """Test creating a bonus transaction."""
        with app.app_context():
            transaction = TransactionManager.create_bonus_transaction(
                test_user.id, 500, "Welcome bonus"
            )
            
            assert transaction.amount == 500
            assert transaction.transaction_type == Transaction.TYPE_BONUS
            assert transaction.description == "Welcome bonus"
            
            # Check user balance updated
            updated_user = UserManager.get_user_by_id(test_user.id)
            assert updated_user.bankroll == 1500
    
    def test_create_buyin_transaction(self, app, test_user):
        """Test creating a buy-in transaction."""
        with app.app_context():
            transaction = TransactionManager.create_buyin_transaction(
                test_user.id, 300, "table-123", "Test Table"
            )
            
            assert transaction.amount == -300
            assert transaction.transaction_type == Transaction.TYPE_BUYIN
            assert transaction.table_id == "table-123"
            assert "Test Table" in transaction.description
            
            # Check user balance updated
            updated_user = UserManager.get_user_by_id(test_user.id)
            assert updated_user.bankroll == 700
    
    def test_insufficient_funds_error(self, app, test_user):
        """Test insufficient funds error."""
        with app.app_context():
            with pytest.raises(InsufficientFundsError):
                TransactionManager.create_buyin_transaction(
                    test_user.id, 2000, "table-123", "Test Table"
                )
            
            # Check user balance unchanged
            updated_user = UserManager.get_user_by_id(test_user.id)
            assert updated_user.bankroll == 1000
    
    def test_transaction_history(self, app, test_user):
        """Test transaction history retrieval."""
        with app.app_context():
            # Create multiple transactions
            TransactionManager.create_bonus_transaction(test_user.id, 200, "Bonus 1")
            TransactionManager.create_buyin_transaction(test_user.id, 100, "table-1", "Table 1")
            TransactionManager.create_winnings_transaction(test_user.id, 150, "table-1", "Table 1", 1)
            
            # Get transaction history
            transactions = TransactionManager.get_user_transactions(test_user.id)
            
            assert len(transactions) == 3
            # Should be ordered by most recent first
            assert transactions[0].transaction_type == Transaction.TYPE_WINNINGS
            assert transactions[1].transaction_type == Transaction.TYPE_BUYIN
            assert transactions[2].transaction_type == Transaction.TYPE_BONUS
    
    def test_transaction_summary(self, app, test_user):
        """Test transaction summary calculation."""
        with app.app_context():
            # Create various transactions
            TransactionManager.create_bonus_transaction(test_user.id, 200, "Bonus")
            TransactionManager.create_buyin_transaction(test_user.id, 100, "table-1", "Table 1")
            TransactionManager.create_winnings_transaction(test_user.id, 150, "table-1", "Table 1", 1)
            TransactionManager.create_rake_transaction(test_user.id, 5, "table-1", "Table 1", 1)
            
            summary = TransactionManager.get_transaction_summary(test_user.id, days=30)
            
            assert summary['total_transactions'] == 4
            assert summary['total_credits'] == 350  # 200 + 150
            assert summary['total_debits'] == 105   # 100 + 5
            assert summary['net_change'] == 245     # 350 - 105
    
    def test_user_balance_validation(self, app, test_user):
        """Test user balance validation."""
        with app.app_context():
            # User should be able to afford 500
            can_afford = TransactionManager.validate_user_can_afford(test_user.id, 500)
            assert can_afford is True
            
            # User should not be able to afford 2000
            can_afford = TransactionManager.validate_user_can_afford(test_user.id, 2000)
            assert can_afford is False
            
            # Get current balance
            balance = TransactionManager.get_user_balance(test_user.id)
            assert balance == 1000
    
    def test_transaction_reversal(self, app, test_user):
        """Test transaction reversal."""
        with app.app_context():
            # Create original transaction
            original = TransactionManager.create_bonus_transaction(
                test_user.id, 200, "Original bonus"
            )
            
            # Check balance after original
            user_after_original = UserManager.get_user_by_id(test_user.id)
            assert user_after_original.bankroll == 1200
            
            # Reverse the transaction
            reversal = TransactionManager.reverse_transaction(
                original.id, "Test reversal"
            )
            
            assert reversal is not None
            assert reversal.amount == -200  # Opposite of original
            assert reversal.transaction_type == Transaction.TYPE_ADJUSTMENT
            assert "Reversal" in reversal.description
            
            # Check balance after reversal
            user_after_reversal = UserManager.get_user_by_id(test_user.id)
            assert user_after_reversal.bankroll == 1000  # Back to original
    
    def test_multiple_transaction_types(self, app, test_user):
        """Test creating different types of transactions."""
        with app.app_context():
            # Create different transaction types
            bonus = TransactionManager.create_bonus_transaction(test_user.id, 100, "Bonus")
            buyin = TransactionManager.create_buyin_transaction(test_user.id, 200, "table-1", "Table 1")
            cashout = TransactionManager.create_cashout_transaction(test_user.id, 150, "table-1", "Table 1")
            winnings = TransactionManager.create_winnings_transaction(test_user.id, 75, "table-1", "Table 1", 1)
            rake = TransactionManager.create_rake_transaction(test_user.id, 5, "table-1", "Table 1", 1)
            adjustment = TransactionManager.create_adjustment_transaction(test_user.id, -20, "Test adjustment")
            
            # Verify transaction types
            assert bonus.transaction_type == Transaction.TYPE_BONUS
            assert buyin.transaction_type == Transaction.TYPE_BUYIN
            assert cashout.transaction_type == Transaction.TYPE_CASHOUT
            assert winnings.transaction_type == Transaction.TYPE_WINNINGS
            assert rake.transaction_type == Transaction.TYPE_RAKE
            assert adjustment.transaction_type == Transaction.TYPE_ADJUSTMENT
            
            # Check final balance: 1000 + 100 - 200 + 150 + 75 - 5 - 20 = 1100
            final_user = UserManager.get_user_by_id(test_user.id)
            assert final_user.bankroll == 1100