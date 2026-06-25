"""CustomMix model — user-authored mixed-game rotations (Phase 9.3)."""

import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class CustomMix(db.Model):
    """A reusable, user-defined mixed-game rotation saved to a player's library.

    The ``rotation`` column stores the full ``MixedGameConfig`` JSON (same shape as
    a file in ``data/mixed_game_configs/``). Library entries are a convenience store
    only: at table creation the rotation is copied inline onto the table, so deleting
    a library mix never affects a running table.
    """

    __tablename__ = "custom_mixes"
    __table_args__ = (UniqueConstraint("user_id", "display_name", name="uq_custom_mix_user_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    rotation: Mapped[str] = mapped_column(Text, nullable=False)  # JSON (MixedGameConfig shape)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship("User")

    def config_dict(self) -> dict:
        """Parsed MixedGameConfig-shaped dict for this mix."""
        return json.loads(self.rotation)

    def to_dict(self) -> dict:
        """Convert to dictionary representation for the API."""
        data = self.config_dict()
        return {
            "id": self.id,
            "display_name": self.display_name,
            "rotation": data.get("rotation", []),
            "betting_structures": data.get("bettingStructures", []),
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<CustomMix {self.display_name} ({self.user_id})>"
