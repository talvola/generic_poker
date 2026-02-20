"""DisabledVariant model for runtime variant toggling."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class DisabledVariant(db.Model):
    """Model for tracking disabled game variants."""

    __tablename__ = "disabled_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    variant_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    disabled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    disabled_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # Relationships
    admin: Mapped["User"] = relationship("User")

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "variant_name": self.variant_name,
            "reason": self.reason,
            "disabled_at": self.disabled_at.isoformat(),
            "disabled_by": self.disabled_by,
        }

    def __repr__(self) -> str:
        return f"<DisabledVariant {self.variant_name}>"
