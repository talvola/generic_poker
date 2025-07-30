"""Table access control model for managing player permissions."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from ..database import db


class TableAccess(db.Model):
    """Model for tracking table access permissions and player sessions."""
    
    __tablename__ = 'table_access'
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign keys
    table_id: Mapped[str] = mapped_column(String(36), ForeignKey('poker_tables.id'), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey('users.id'), nullable=False)
    
    # Access information
    access_granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    invite_code_used: Mapped[Optional[str]] = mapped_column(String(20))
    is_spectator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Session tracking
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Player state at table
    seat_number: Mapped[Optional[int]] = mapped_column()  # None for spectators
    buy_in_amount: Mapped[Optional[int]] = mapped_column()  # Chips bought in with
    current_stack: Mapped[Optional[int]] = mapped_column()  # Current chip count
    
    # Relationships
    table: Mapped["PokerTable"] = relationship("PokerTable", back_populates="access_records")
    user: Mapped["User"] = relationship("User", back_populates="table_access")
    
    def __init__(self, table_id: str, user_id: str, invite_code_used: Optional[str] = None,
                 is_spectator: bool = False, seat_number: Optional[int] = None,
                 buy_in_amount: Optional[int] = None):
        """Initialize table access record."""
        self.table_id = table_id
        self.user_id = user_id
        self.invite_code_used = invite_code_used
        self.is_spectator = is_spectator
        self.seat_number = seat_number
        self.buy_in_amount = buy_in_amount
        self.current_stack = buy_in_amount
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def is_inactive(self, timeout_minutes: int = 30) -> bool:
        """Check if access record has been inactive for specified minutes."""
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.utcnow() - self.last_activity > timeout
    
    def leave_table(self) -> None:
        """Mark player as having left the table."""
        self.is_active = False
        self.seat_number = None
    
    def update_stack(self, new_stack: int) -> None:
        """Update player's current chip stack."""
        self.current_stack = new_stack
        self.update_activity()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert access record to dictionary representation."""
        return {
            'id': self.id,
            'table_id': self.table_id,
            'user_id': self.user_id,
            'access_granted_at': self.access_granted_at.isoformat(),
            'is_spectator': self.is_spectator,
            'last_activity': self.last_activity.isoformat(),
            'is_active': self.is_active,
            'seat_number': self.seat_number,
            'buy_in_amount': self.buy_in_amount,
            'current_stack': self.current_stack
        }
    
    def __repr__(self) -> str:
        return f'<TableAccess {self.user_id} at table {self.table_id}>'