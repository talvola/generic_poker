"""Transaction management service for bankroll operations."""

from datetime import datetime, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import and_, desc

from ..database import db
from ..models.transaction import Transaction
from ..models.user import User
from .user_manager import UserManager


class TransactionError(Exception):
    """Exception raised for transaction errors."""

    pass


class InsufficientFundsError(TransactionError):
    """Exception raised when user has insufficient funds."""

    pass


class TransactionManager:
    """Service class for managing bankroll transactions."""

    @staticmethod
    def create_transaction(
        user_id: str, amount: int, transaction_type: str, description: str, table_id: str | None = None
    ) -> Transaction:
        """Create a new transaction with atomic bankroll update.

        Args:
            user_id: User's unique ID
            amount: Transaction amount (positive for credit, negative for debit)
            transaction_type: Type of transaction
            description: Human-readable description
            table_id: Optional table ID for table-related transactions

        Returns:
            Transaction: Created transaction instance

        Raises:
            TransactionError: If transaction fails
            InsufficientFundsError: If user has insufficient funds for debit
        """
        try:
            # Get user with row lock to prevent concurrent modifications
            user = db.session.query(User).filter_by(id=user_id).with_for_update().first()
            if not user:
                raise TransactionError(f"User {user_id} not found")

            # Check for sufficient funds on debit transactions
            if amount < 0 and user.bankroll + amount < 0:
                raise InsufficientFundsError(
                    f"Insufficient funds: current balance {user.bankroll}, attempted debit {abs(amount)}"
                )

            # Update user bankroll
            user.bankroll += amount

            # Create transaction record
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                transaction_type=transaction_type,
                description=description,
                table_id=table_id,
            )

            db.session.add(transaction)
            db.session.commit()  # Commit the transaction

            current_app.logger.info(
                f"Transaction created: {transaction.id} - User {user.username} {transaction_type} {amount}"
            )

            return transaction

        except (InsufficientFundsError, TransactionError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating transaction: {e}")
            raise TransactionError(f"Failed to create transaction: {str(e)}")

    @staticmethod
    def create_buyin_transaction(user_id: str, amount: int, table_id: str, table_name: str) -> Transaction:
        """Create a table buy-in transaction.

        Args:
            user_id: User's unique ID
            amount: Buy-in amount (positive value)
            table_id: Table ID
            table_name: Table name for description

        Returns:
            Transaction: Created buy-in transaction
        """
        if amount <= 0:
            raise TransactionError("Buy-in amount must be positive")

        return TransactionManager.create_transaction(
            user_id=user_id,
            amount=-amount,  # Debit from bankroll
            transaction_type=Transaction.TYPE_BUYIN,
            description=f"Buy-in to table '{table_name}'",
            table_id=table_id,
        )

    @staticmethod
    def create_cashout_transaction(user_id: str, amount: int, table_id: str, table_name: str) -> Transaction:
        """Create a table cash-out transaction.

        Args:
            user_id: User's unique ID
            amount: Cash-out amount (positive value)
            table_id: Table ID
            table_name: Table name for description

        Returns:
            Transaction: Created cash-out transaction
        """
        if amount <= 0:
            raise TransactionError("Cash-out amount must be positive")

        return TransactionManager.create_transaction(
            user_id=user_id,
            amount=amount,  # Credit to bankroll
            transaction_type=Transaction.TYPE_CASHOUT,
            description=f"Cash-out from table '{table_name}'",
            table_id=table_id,
        )

    @staticmethod
    def create_winnings_transaction(
        user_id: str, amount: int, table_id: str, table_name: str, hand_number: int
    ) -> Transaction:
        """Create a hand winnings transaction.

        Args:
            user_id: User's unique ID
            amount: Winnings amount (positive value)
            table_id: Table ID
            table_name: Table name for description
            hand_number: Hand number

        Returns:
            Transaction: Created winnings transaction
        """
        if amount <= 0:
            raise TransactionError("Winnings amount must be positive")

        return TransactionManager.create_transaction(
            user_id=user_id,
            amount=amount,  # Credit to bankroll
            transaction_type=Transaction.TYPE_WINNINGS,
            description=f"Winnings from hand #{hand_number} at table '{table_name}'",
            table_id=table_id,
        )

    @staticmethod
    def create_rake_transaction(
        user_id: str, amount: int, table_id: str, table_name: str, hand_number: int
    ) -> Transaction:
        """Create a rake deduction transaction.

        Args:
            user_id: User's unique ID
            amount: Rake amount (positive value)
            table_id: Table ID
            table_name: Table name for description
            hand_number: Hand number

        Returns:
            Transaction: Created rake transaction
        """
        if amount <= 0:
            raise TransactionError("Rake amount must be positive")

        return TransactionManager.create_transaction(
            user_id=user_id,
            amount=-amount,  # Debit from bankroll
            transaction_type=Transaction.TYPE_RAKE,
            description=f"Rake from hand #{hand_number} at table '{table_name}'",
            table_id=table_id,
        )

    @staticmethod
    def create_bonus_transaction(user_id: str, amount: int, description: str) -> Transaction:
        """Create a bonus credit transaction.

        Args:
            user_id: User's unique ID
            amount: Bonus amount (positive value)
            description: Bonus description

        Returns:
            Transaction: Created bonus transaction
        """
        if amount <= 0:
            raise TransactionError("Bonus amount must be positive")

        return TransactionManager.create_transaction(
            user_id=user_id,
            amount=amount,  # Credit to bankroll
            transaction_type=Transaction.TYPE_BONUS,
            description=description,
        )

    @staticmethod
    def create_adjustment_transaction(user_id: str, amount: int, description: str) -> Transaction:
        """Create a manual adjustment transaction.

        Args:
            user_id: User's unique ID
            amount: Adjustment amount (positive or negative)
            description: Adjustment description

        Returns:
            Transaction: Created adjustment transaction
        """
        if amount == 0:
            raise TransactionError("Adjustment amount cannot be zero")

        return TransactionManager.create_transaction(
            user_id=user_id, amount=amount, transaction_type=Transaction.TYPE_ADJUSTMENT, description=description
        )

    @staticmethod
    def get_user_transactions(
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        transaction_type: str | None = None,
        table_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[Transaction]:
        """Get user's transaction history with filtering.

        Args:
            user_id: User's unique ID
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            transaction_type: Filter by transaction type
            table_id: Filter by table ID
            start_date: Filter transactions after this date
            end_date: Filter transactions before this date

        Returns:
            List[Transaction]: List of transactions
        """
        try:
            query = Transaction.query.filter_by(user_id=user_id)

            # Apply filters
            if transaction_type:
                query = query.filter(Transaction.transaction_type == transaction_type)

            if table_id:
                query = query.filter(Transaction.table_id == table_id)

            if start_date:
                query = query.filter(Transaction.created_at >= start_date)

            if end_date:
                query = query.filter(Transaction.created_at <= end_date)

            # Order by most recent first
            query = query.order_by(desc(Transaction.created_at))

            # Apply pagination
            transactions = query.offset(offset).limit(limit).all()

            return transactions

        except Exception as e:
            current_app.logger.error(f"Error getting user transactions: {e}")
            return []

    @staticmethod
    def get_transaction_summary(user_id: str, days: int = 30) -> dict[str, Any]:
        """Get transaction summary for a user over specified days.

        Args:
            user_id: User's unique ID
            days: Number of days to include in summary

        Returns:
            Dict: Transaction summary statistics
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            transactions = Transaction.query.filter(
                and_(Transaction.user_id == user_id, Transaction.created_at >= start_date)
            ).all()

            # Calculate summary statistics
            total_credits = sum(t.amount for t in transactions if t.amount > 0)
            total_debits = sum(abs(t.amount) for t in transactions if t.amount < 0)
            net_change = total_credits - total_debits

            # Count by transaction type
            type_counts = {}
            type_amounts = {}

            for transaction in transactions:
                t_type = transaction.transaction_type
                type_counts[t_type] = type_counts.get(t_type, 0) + 1
                type_amounts[t_type] = type_amounts.get(t_type, 0) + transaction.amount

            return {
                "period_days": days,
                "total_transactions": len(transactions),
                "total_credits": total_credits,
                "total_debits": total_debits,
                "net_change": net_change,
                "transaction_counts": type_counts,
                "transaction_amounts": type_amounts,
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            current_app.logger.error(f"Error getting transaction summary: {e}")
            return {}

    @staticmethod
    def get_table_transactions(table_id: str, limit: int = 100) -> list[Transaction]:
        """Get all transactions for a specific table.

        Args:
            table_id: Table ID
            limit: Maximum number of transactions to return

        Returns:
            List[Transaction]: List of table transactions
        """
        try:
            transactions = (
                Transaction.query.filter_by(table_id=table_id).order_by(desc(Transaction.created_at)).limit(limit).all()
            )

            return transactions

        except Exception as e:
            current_app.logger.error(f"Error getting table transactions: {e}")
            return []

    @staticmethod
    def validate_user_can_afford(user_id: str, amount: int) -> bool:
        """Check if user can afford a specific amount.

        Args:
            user_id: User's unique ID
            amount: Amount to check (positive value)

        Returns:
            bool: True if user can afford the amount
        """
        try:
            user = UserManager.get_user_by_id(user_id)
            if not user:
                return False

            return user.bankroll >= amount

        except Exception as e:
            current_app.logger.error(f"Error validating user funds: {e}")
            return False

    @staticmethod
    def get_user_balance(user_id: str) -> int | None:
        """Get current user balance.

        Args:
            user_id: User's unique ID

        Returns:
            int: Current balance or None if user not found
        """
        try:
            user = UserManager.get_user_by_id(user_id)
            return user.bankroll if user else None

        except Exception as e:
            current_app.logger.error(f"Error getting user balance: {e}")
            return None

    @staticmethod
    def _create_transaction_no_commit(
        user_id: str, amount: int, transaction_type: str, description: str, table_id: str | None = None
    ) -> Transaction:
        """Create a transaction without committing (for batch processing).

        Args:
            user_id: User's unique ID
            amount: Transaction amount (positive for credit, negative for debit)
            transaction_type: Type of transaction
            description: Human-readable description
            table_id: Optional table ID for table-related transactions

        Returns:
            Transaction: Created transaction instance

        Raises:
            TransactionError: If transaction fails
            InsufficientFundsError: If user has insufficient funds for debit
        """
        # Get user with row lock to prevent concurrent modifications
        user = db.session.query(User).filter_by(id=user_id).with_for_update().first()
        if not user:
            raise TransactionError(f"User {user_id} not found")

        # Check for sufficient funds on debit transactions
        if amount < 0 and user.bankroll + amount < 0:
            raise InsufficientFundsError(
                f"Insufficient funds: current balance {user.bankroll}, attempted debit {abs(amount)}"
            )

        # Update user bankroll
        user.bankroll += amount

        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            table_id=table_id,
        )

        db.session.add(transaction)
        return transaction

    @staticmethod
    def process_batch_transactions(transactions_data: list[dict[str, Any]]) -> tuple[list[Transaction], list[str]]:
        """Process multiple transactions atomically.

        Args:
            transactions_data: List of transaction data dictionaries

        Returns:
            Tuple: (successful_transactions, error_messages)
        """
        successful_transactions = []
        error_messages = []

        try:
            # Process all transactions in a single database transaction
            # If any fails, all will be rolled back
            for i, tx_data in enumerate(transactions_data):
                try:
                    transaction = TransactionManager._create_transaction_no_commit(
                        user_id=tx_data["user_id"],
                        amount=tx_data["amount"],
                        transaction_type=tx_data["transaction_type"],
                        description=tx_data["description"],
                        table_id=tx_data.get("table_id"),
                    )
                    successful_transactions.append(transaction)

                except Exception as e:
                    error_messages.append(f"Transaction {i}: {str(e)}")
                    # Rollback all transactions on any failure
                    db.session.rollback()
                    return [], error_messages

            # Commit all transactions if all succeeded
            db.session.commit()
            current_app.logger.info(f"Processed batch of {len(successful_transactions)} transactions")

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Batch transaction failed: {e}")
            error_messages.append(f"Batch transaction failed: {str(e)}")
            return [], error_messages

        return successful_transactions, error_messages

    @staticmethod
    def reverse_transaction(transaction_id: str, reason: str) -> Transaction | None:
        """Reverse a transaction by creating an opposite transaction.

        Args:
            transaction_id: ID of transaction to reverse
            reason: Reason for reversal

        Returns:
            Transaction: Reversal transaction or None if failed
        """
        try:
            # Get original transaction
            original = Transaction.query.filter_by(id=transaction_id).first()
            if not original:
                raise TransactionError(f"Transaction {transaction_id} not found")

            # Create reversal transaction
            reversal = TransactionManager.create_transaction(
                user_id=original.user_id,
                amount=-original.amount,  # Opposite amount
                transaction_type=Transaction.TYPE_ADJUSTMENT,
                description=f"Reversal of {original.transaction_type}: {reason}",
                table_id=original.table_id,
            )

            current_app.logger.info(f"Reversed transaction {transaction_id}: {reversal.id}")
            return reversal

        except Exception as e:
            current_app.logger.error(f"Error reversing transaction {transaction_id}: {e}")
            return None
