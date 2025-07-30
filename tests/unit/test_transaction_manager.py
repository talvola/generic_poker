"""Unit tests for TransactionManager service."""

import pytest
from datetime import datetime, timedelta
from flask import Flask

from src.online_poker.services.transaction_manager import (
    TransactionManager, TransactionError, InsufficientFundsError
)
from src.online_poker.services.user_manager import UserManager
from src.online_poker.models.transaction import Transaction
from src.online_poker.database import db


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
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
    user = UserManager.create_user("testuser", "test@example.com", "password123", 1000)
    return user


class TestTransactionCreation:
    """Test transaction creation methods."""
    
    def test_create_transaction_credit(self, app_context, test_user):
        """Test creating a credit transaction."""
        transaction = TransactionManager.create_transaction(
            user_id=test_user.id,
            amount=500,
            transaction_type=Transaction.TYPE_BONUS,
            description="Test bonus"
        )
        
        assert transaction.amount == 500
        assert transaction.transaction_type == Transaction.TYPE_BONUS
        assert transaction.description == "Test bonus"
        assert transaction.user_id == test_user.id
        
        # Check user balance updated
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 1500
    
    def test_create_transaction_debit(self, app_context, test_user):
        """Test creating a debit transaction."""
        transaction = TransactionManager.create_transaction(
            user_id=test_user.id,
            amount=-200,
            transaction_type=Transaction.TYPE_BUYIN,
            description="Test buy-in"
        )
        
        assert transaction.amount == -200
        assert transaction.transaction_type == Transaction.TYPE_BUYIN
        
        # Check user balance updated
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 800
    
    def test_create_transaction_insufficient_funds(self, app_context, test_user):
        """Test creating transaction with insufficient funds."""
        with pytest.raises(InsufficientFundsError):
            TransactionManager.create_transaction(
                user_id=test_user.id,
                amount=-2000,  # More than user's balance
                transaction_type=Transaction.TYPE_BUYIN,
                description="Test overdraft"
            )
        
        # Check user balance unchanged
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 1000
    
    def test_create_transaction_nonexistent_user(self, app_context):
        """Test creating transaction for nonexistent user."""
        with pytest.raises(TransactionError):
            TransactionManager.create_transaction(
                user_id="nonexistent-id",
                amount=100,
                transaction_type=Transaction.TYPE_BONUS,
                description="Test"
            )
    
    def test_create_buyin_transaction(self, app_context, test_user):
        """Test creating buy-in transaction."""
        transaction = TransactionManager.create_buyin_transaction(
            user_id=test_user.id,
            amount=300,
            table_id="table-123",
            table_name="Test Table"
        )
        
        assert transaction.amount == -300  # Debit
        assert transaction.transaction_type == Transaction.TYPE_BUYIN
        assert transaction.table_id == "table-123"
        assert "Test Table" in transaction.description
        
        # Check user balance
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 700
    
    def test_create_buyin_transaction_invalid_amount(self, app_context, test_user):
        """Test creating buy-in transaction with invalid amount."""
        with pytest.raises(TransactionError, match="Buy-in amount must be positive"):
            TransactionManager.create_buyin_transaction(
                user_id=test_user.id,
                amount=-100,
                table_id="table-123",
                table_name="Test Table"
            )
    
    def test_create_cashout_transaction(self, app_context, test_user):
        """Test creating cash-out transaction."""
        transaction = TransactionManager.create_cashout_transaction(
            user_id=test_user.id,
            amount=400,
            table_id="table-123",
            table_name="Test Table"
        )
        
        assert transaction.amount == 400  # Credit
        assert transaction.transaction_type == Transaction.TYPE_CASHOUT
        assert transaction.table_id == "table-123"
        
        # Check user balance
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 1400
    
    def test_create_winnings_transaction(self, app_context, test_user):
        """Test creating winnings transaction."""
        transaction = TransactionManager.create_winnings_transaction(
            user_id=test_user.id,
            amount=250,
            table_id="table-123",
            table_name="Test Table",
            hand_number=5
        )
        
        assert transaction.amount == 250  # Credit
        assert transaction.transaction_type == Transaction.TYPE_WINNINGS
        assert "hand #5" in transaction.description
        
        # Check user balance
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 1250
    
    def test_create_rake_transaction(self, app_context, test_user):
        """Test creating rake transaction."""
        transaction = TransactionManager.create_rake_transaction(
            user_id=test_user.id,
            amount=10,
            table_id="table-123",
            table_name="Test Table",
            hand_number=3
        )
        
        assert transaction.amount == -10  # Debit
        assert transaction.transaction_type == Transaction.TYPE_RAKE
        assert "hand #3" in transaction.description
        
        # Check user balance
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 990
    
    def test_create_bonus_transaction(self, app_context, test_user):
        """Test creating bonus transaction."""
        transaction = TransactionManager.create_bonus_transaction(
            user_id=test_user.id,
            amount=100,
            description="Welcome bonus"
        )
        
        assert transaction.amount == 100  # Credit
        assert transaction.transaction_type == Transaction.TYPE_BONUS
        assert transaction.description == "Welcome bonus"
        
        # Check user balance
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 1100
    
    def test_create_adjustment_transaction(self, app_context, test_user):
        """Test creating adjustment transaction."""
        transaction = TransactionManager.create_adjustment_transaction(
            user_id=test_user.id,
            amount=-50,
            description="Manual adjustment"
        )
        
        assert transaction.amount == -50  # Debit
        assert transaction.transaction_type == Transaction.TYPE_ADJUSTMENT
        assert transaction.description == "Manual adjustment"
        
        # Check user balance
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 950


class TestTransactionHistory:
    """Test transaction history and filtering methods."""
    
    def test_get_user_transactions_basic(self, app_context, test_user):
        """Test getting user transactions."""
        # Create some transactions
        TransactionManager.create_bonus_transaction(test_user.id, 100, "Bonus 1")
        TransactionManager.create_buyin_transaction(test_user.id, 200, "table-1", "Table 1")
        TransactionManager.create_winnings_transaction(test_user.id, 150, "table-1", "Table 1", 1)
        
        transactions = TransactionManager.get_user_transactions(test_user.id)
        
        assert len(transactions) == 3
        # Should be ordered by most recent first
        assert transactions[0].transaction_type == Transaction.TYPE_WINNINGS
        assert transactions[1].transaction_type == Transaction.TYPE_BUYIN
        assert transactions[2].transaction_type == Transaction.TYPE_BONUS
    
    def test_get_user_transactions_with_limit(self, app_context, test_user):
        """Test getting user transactions with limit."""
        # Create multiple transactions
        for i in range(5):
            TransactionManager.create_bonus_transaction(test_user.id, 10, f"Bonus {i}")
        
        transactions = TransactionManager.get_user_transactions(test_user.id, limit=3)
        
        assert len(transactions) == 3
    
    def test_get_user_transactions_with_offset(self, app_context, test_user):
        """Test getting user transactions with offset."""
        # Create multiple transactions
        for i in range(5):
            TransactionManager.create_bonus_transaction(test_user.id, 10, f"Bonus {i}")
        
        transactions = TransactionManager.get_user_transactions(test_user.id, limit=2, offset=2)
        
        assert len(transactions) == 2
    
    def test_get_user_transactions_filter_by_type(self, app_context, test_user):
        """Test filtering transactions by type."""
        TransactionManager.create_bonus_transaction(test_user.id, 100, "Bonus")
        TransactionManager.create_buyin_transaction(test_user.id, 200, "table-1", "Table 1")
        TransactionManager.create_winnings_transaction(test_user.id, 150, "table-1", "Table 1", 1)
        
        bonus_transactions = TransactionManager.get_user_transactions(
            test_user.id, transaction_type=Transaction.TYPE_BONUS
        )
        
        assert len(bonus_transactions) == 1
        assert bonus_transactions[0].transaction_type == Transaction.TYPE_BONUS
    
    def test_get_user_transactions_filter_by_table(self, app_context, test_user):
        """Test filtering transactions by table."""
        TransactionManager.create_buyin_transaction(test_user.id, 200, "table-1", "Table 1")
        TransactionManager.create_buyin_transaction(test_user.id, 300, "table-2", "Table 2")
        TransactionManager.create_winnings_transaction(test_user.id, 150, "table-1", "Table 1", 1)
        
        table1_transactions = TransactionManager.get_user_transactions(
            test_user.id, table_id="table-1"
        )
        
        assert len(table1_transactions) == 2
        for tx in table1_transactions:
            assert tx.table_id == "table-1"
    
    def test_get_user_transactions_filter_by_date(self, app_context, test_user):
        """Test filtering transactions by date."""
        # Create transaction
        TransactionManager.create_bonus_transaction(test_user.id, 100, "Recent bonus")
        
        # Filter by date range
        start_date = datetime.utcnow() - timedelta(hours=1)
        end_date = datetime.utcnow() + timedelta(hours=1)
        
        transactions = TransactionManager.get_user_transactions(
            test_user.id, start_date=start_date, end_date=end_date
        )
        
        assert len(transactions) == 1
        
        # Filter with date range that excludes the transaction
        old_start = datetime.utcnow() - timedelta(days=2)
        old_end = datetime.utcnow() - timedelta(days=1)
        
        old_transactions = TransactionManager.get_user_transactions(
            test_user.id, start_date=old_start, end_date=old_end
        )
        
        assert len(old_transactions) == 0


class TestTransactionSummary:
    """Test transaction summary methods."""
    
    def test_get_transaction_summary(self, app_context, test_user):
        """Test getting transaction summary."""
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
        
        # Check transaction counts by type
        assert summary['transaction_counts'][Transaction.TYPE_BONUS] == 1
        assert summary['transaction_counts'][Transaction.TYPE_BUYIN] == 1
        assert summary['transaction_counts'][Transaction.TYPE_WINNINGS] == 1
        assert summary['transaction_counts'][Transaction.TYPE_RAKE] == 1
    
    def test_get_table_transactions(self, app_context, test_user):
        """Test getting transactions for a specific table."""
        # Create transactions for different tables
        TransactionManager.create_buyin_transaction(test_user.id, 200, "table-1", "Table 1")
        TransactionManager.create_buyin_transaction(test_user.id, 300, "table-2", "Table 2")
        TransactionManager.create_winnings_transaction(test_user.id, 150, "table-1", "Table 1", 1)
        
        table1_transactions = TransactionManager.get_table_transactions("table-1")
        
        assert len(table1_transactions) == 2
        for tx in table1_transactions:
            assert tx.table_id == "table-1"


class TestTransactionValidation:
    """Test transaction validation methods."""
    
    def test_validate_user_can_afford_true(self, app_context, test_user):
        """Test user can afford amount."""
        can_afford = TransactionManager.validate_user_can_afford(test_user.id, 500)
        assert can_afford is True
    
    def test_validate_user_can_afford_false(self, app_context, test_user):
        """Test user cannot afford amount."""
        can_afford = TransactionManager.validate_user_can_afford(test_user.id, 2000)
        assert can_afford is False
    
    def test_validate_user_can_afford_nonexistent_user(self, app_context):
        """Test validation for nonexistent user."""
        can_afford = TransactionManager.validate_user_can_afford("nonexistent-id", 100)
        assert can_afford is False
    
    def test_get_user_balance(self, app_context, test_user):
        """Test getting user balance."""
        balance = TransactionManager.get_user_balance(test_user.id)
        assert balance == 1000
    
    def test_get_user_balance_nonexistent_user(self, app_context):
        """Test getting balance for nonexistent user."""
        balance = TransactionManager.get_user_balance("nonexistent-id")
        assert balance is None


class TestBatchTransactions:
    """Test batch transaction processing."""
    
    def test_process_batch_transactions_success(self, app_context, test_user):
        """Test successful batch transaction processing."""
        transactions_data = [
            {
                'user_id': test_user.id,
                'amount': 100,
                'transaction_type': Transaction.TYPE_BONUS,
                'description': 'Batch bonus 1'
            },
            {
                'user_id': test_user.id,
                'amount': -50,
                'transaction_type': Transaction.TYPE_ADJUSTMENT,
                'description': 'Batch adjustment'
            }
        ]
        
        successful, errors = TransactionManager.process_batch_transactions(transactions_data)
        
        assert len(successful) == 2
        assert len(errors) == 0
        
        # Check user balance updated correctly
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 1050  # 1000 + 100 - 50
    
    def test_process_batch_transactions_failure(self, app_context, test_user):
        """Test batch transaction processing with failure."""
        transactions_data = [
            {
                'user_id': test_user.id,
                'amount': 100,
                'transaction_type': Transaction.TYPE_BONUS,
                'description': 'Batch bonus'
            },
            {
                'user_id': test_user.id,
                'amount': -2000,  # Insufficient funds
                'transaction_type': Transaction.TYPE_ADJUSTMENT,
                'description': 'Batch overdraft'
            }
        ]
        
        successful, errors = TransactionManager.process_batch_transactions(transactions_data)
        
        assert len(successful) == 0  # All should fail due to rollback
        assert len(errors) > 0
        
        # Check user balance unchanged
        updated_user = UserManager.get_user_by_id(test_user.id)
        assert updated_user.bankroll == 1000


class TestTransactionReversal:
    """Test transaction reversal functionality."""
    
    def test_reverse_transaction(self, app_context, test_user):
        """Test reversing a transaction."""
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
    
    def test_reverse_nonexistent_transaction(self, app_context):
        """Test reversing nonexistent transaction."""
        reversal = TransactionManager.reverse_transaction(
            "nonexistent-id", "Test reversal"
        )
        
        assert reversal is None