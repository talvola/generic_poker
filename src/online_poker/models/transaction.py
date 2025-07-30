"""Transaction model for bankroll management."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from ..database import db


class Transaction(db.Model):
    """Model for tracking bankroll transactions."""
    
    __tablename__ = 'transactions'
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Transaction details
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Positive for credits, negative for debits
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional table reference
    table_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey('poker_tables.id'))
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign keys
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey('users.id'), nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    
    # Transaction types
    TYPE_BUYIN = "table_buyin"
    TYPE_CASHOUT = "table_cashout"
    TYPE_WINNINGS = "hand_winnings"
    TYPE_RAKE = "rake_deduction"
    TYPE_BONUS = "bonus_credit"
    TYPE_ADJUSTMENT = "manual_adjustment"
    
    def __init__(self, user_id: str, amount: int, transaction_type: str, 
                 description: str, table_id: Optional[str] = None):
        """Initialize transaction."""
        self.user_id = user_id
        self.amount = amount
        self.transaction_type = transaction_type
        self.description = description
        self.table_id = table_id
    
    @classmethod
    def create_buyin_transaction(cls, user_id: str, amount: int, table_id: str, table_name: str) -> "Transaction":
        """Create a buy-in transaction."""
        description = f"Buy-in to table '{table_name}'"
        return cls(user_id, -abs(amount), cls.TYPE_BUYIN, description, table_id)
    
    @classmethod
    def create_cashout_transaction(cls, user_id: str, amount: int, table_id: str, table_name: str) -> "Transaction":
        """Create a cash-out transaction."""
        description = f"Cash-out from table '{table_name}'"
        return cls(user_id, amount, cls.TYPE_CASHOUT, description, table_id)
    
    @classmethod
    def create_winnings_transaction(cls, user_id: str, amount: int, table_id: str, 
                                  table_name: str, hand_number: int) -> "Transaction":
        """Create a winnings transaction."""
        description = f"Winnings from hand #{hand_number} at table '{table_name}'"
        return cls(user_id, amount, cls.TYPE_WINNINGS, description, table_id)
    
    @classmethod
    def create_rake_transaction(cls, user_id: str, amount: int, table_id: str, 
                              table_name: str, hand_number: int) -> "Transaction":
        """Create a rake deduction transaction."""
        description = f"Rake from hand #{hand_number} at table '{table_name}'"
        return cls(user_id, -abs(amount), cls.TYPE_RAKE, description, table_id)
    
    def is_credit(self) -> bool:
        """Check if transaction is a credit (positive amount)."""
        return self.amount > 0
    
    def is_debit(self) -> bool:
        """Check if transaction is a debit (negative amount)."""
        return self.amount < 0
    
    def get_absolute_amount(self) -> int:
        """Get absolute value of transaction amount."""
        return abs(self.amount)
    
    def to_dict(self) -> dict:
        """Convert transaction to dictionary representation."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'description': self.description,
            'table_id': self.table_id,
            'created_at': self.created_at.isoformat(),
            'is_credit': self.is_credit(),
            'absolute_amount': self.get_absolute_amount()
        }
    
    def __repr__(self) -> str:
        return f'<Transaction {self.transaction_type}: {self.amount}>'