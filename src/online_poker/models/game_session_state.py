"""Game session state model for persisting active session info across restarts."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class GameSessionState(db.Model):
    """Persists game session state so it can be recovered after server restart.

    Stores the minimum info needed to reconstruct a session between hands:
    dealer position, hands played count, and activity timestamp.
    """

    __tablename__ = "game_session_state"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_id: Mapped[str] = mapped_column(String(36), ForeignKey("poker_tables.id"), unique=True, nullable=False)
    dealer_seat: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hands_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_activity: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    session_id: Mapped[str | None] = mapped_column(String(36))

    # Mixed game rotation state (nullable for non-mixed games)
    current_variant_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hands_in_current_variant: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orbit_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    table: Mapped["PokerTable"] = relationship("PokerTable")

    def __repr__(self) -> str:
        return f"<GameSessionState table={self.table_id} dealer_seat={self.dealer_seat} hands={self.hands_played}>"
