"""User model for the online poker platform."""

import uuid
from datetime import datetime

import bcrypt
from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class User(UserMixin, db.Model):
    """User model for player accounts."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # User credentials
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    # Account information
    bankroll: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    created_tables: Mapped[list["PokerTable"]] = relationship("PokerTable", back_populates="creator")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    table_access: Mapped[list["TableAccess"]] = relationship("TableAccess", back_populates="user")
    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="user")

    def __init__(self, username: str, email: str, password: str, bankroll: int = 1000):
        """Initialize user with hashed password."""
        self.username = username
        self.email = email
        self.set_password(password)
        self.bankroll = bankroll

    def set_password(self, password: str) -> None:
        """Hash and set user password."""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Check if provided password matches stored hash."""
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def update_bankroll(self, amount: int) -> bool:
        """Update user bankroll. Returns True if successful."""
        new_bankroll = self.bankroll + amount
        if new_bankroll < 0:
            return False
        self.bankroll = new_bankroll
        return True

    def can_afford_buyin(self, buy_in_amount: int) -> bool:
        """Check if user can afford the buy-in amount."""
        return self.bankroll >= buy_in_amount

    def update_last_login(self) -> None:
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert user to dictionary representation."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "bankroll": self.bankroll,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active,
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"
