"""CustomVariant model — user-authored game configs (Phase 9.5)."""

import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class CustomVariant(db.Model):
    """A user-authored poker variant saved to a player's library.

    The ``config`` column stores full game-config JSON (same shape as a file in
    ``data/game_configs/``), already validated by the authoring pipeline. Library
    entries are a convenience store only: at table creation the config is copied
    inline onto the table, so deleting a library variant never affects a running
    table.
    """

    __tablename__ = "custom_variants"
    __table_args__ = (UniqueConstraint("user_id", "display_name", name="uq_custom_variant_user_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    # Official variant stem this was cloned from (informational only, never resolved).
    base_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON (game-config shape)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    owner: Mapped["User"] = relationship("User")

    def config_dict(self) -> dict:
        """Parsed game-config dict for this variant."""
        return json.loads(self.config)

    def to_dict(self) -> dict:
        """Convert to dictionary representation for the API."""
        cfg = self.config_dict()
        players = cfg.get("players", {})
        return {
            "id": self.id,
            "display_name": self.display_name,
            "base_variant": self.base_variant,
            "config": cfg,
            "min_players": players.get("min"),
            "max_players": players.get("max"),
            "betting_structures": cfg.get("bettingStructures", []),
            "deck_type": cfg.get("deck", {}).get("type"),
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<CustomVariant {self.display_name} ({self.user_id})>"
