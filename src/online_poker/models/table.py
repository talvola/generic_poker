"""Table model for poker tables."""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game

from ..database import db


class PokerTable(db.Model):
    """Model for poker tables."""

    __tablename__ = "poker_tables"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Table configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    variant: Mapped[str] = mapped_column(String(50), nullable=False)
    betting_structure: Mapped[str] = mapped_column(String(20), nullable=False)  # Limit, No-Limit, Pot-Limit
    stakes: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)

    # Privacy settings
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invite_code: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(128))

    # Bot settings
    allow_bots: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Mixed game flag
    is_mixed_game: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Foreign keys
    creator_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="created_tables")
    game_history: Mapped[list["GameHistory"]] = relationship("GameHistory", back_populates="table")
    access_records: Mapped[list["TableAccess"]] = relationship("TableAccess", back_populates="table")
    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="table")

    def __init__(
        self,
        name: str,
        variant: str,
        betting_structure: str,
        stakes: dict[str, int],
        max_players: int,
        creator_id: str,
        is_private: bool = False,
        allow_bots: bool = False,
        password: str | None = None,
    ):
        """Initialize poker table."""
        self.name = name
        self.variant = variant
        self.betting_structure = betting_structure
        self.stakes = json.dumps(stakes)
        self.max_players = max_players
        self.creator_id = creator_id
        self.is_private = is_private
        self.allow_bots = allow_bots

        if is_private:
            self.invite_code = self._generate_invite_code()

        if password:
            self.set_password(password)

    def _generate_invite_code(self) -> str:
        """Generate unique invite code for private tables."""
        import random
        import string

        return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def set_password(self, password: str) -> None:
        """Set table password hash."""
        import bcrypt

        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Check if provided password matches table password."""
        if not self.password_hash:
            return True  # No password set
        import bcrypt

        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def get_stakes(self) -> dict[str, int]:
        """Get stakes as dictionary."""
        return json.loads(self.stakes)

    def update_stakes(self, stakes: dict[str, int]) -> None:
        """Update table stakes."""
        self.stakes = json.dumps(stakes)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def is_inactive(self, timeout_minutes: int = 30) -> bool:
        """Check if table has been inactive for specified minutes."""
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.utcnow() - self.last_activity > timeout

    def _is_nl_or_pl(self) -> bool:
        """Check if this table uses No-Limit or Pot-Limit betting."""
        bs = self.betting_structure.lower().replace(" ", "-")
        return bs in ("no-limit", "pot-limit")

    def get_minimum_buyin(self) -> int:
        """Get minimum buy-in amount based on stakes."""
        stakes_dict = self.get_stakes()
        if self._is_nl_or_pl():
            return stakes_dict.get("big_blind", 2) * 20  # 20 big blinds minimum
        else:
            return stakes_dict.get("big_bet", 4) * 10  # 10 big bets for limit

    def get_maximum_buyin(self) -> int:
        """Get maximum buy-in amount based on stakes."""
        stakes_dict = self.get_stakes()
        if self._is_nl_or_pl():
            return stakes_dict.get("big_blind", 2) * 200  # 200 big blinds maximum
        else:
            return stakes_dict.get("big_bet", 4) * 50  # 50 big bets for limit

    def to_dict(self, include_sensitive: bool = False) -> dict[str, Any]:
        """Convert table to dictionary representation.

        Args:
            include_sensitive: Whether to include sensitive info like invite codes
        """
        # Count active players
        active_players = sum(1 for access in self.access_records if access.is_active and not access.is_spectator)
        active_spectators = sum(1 for access in self.access_records if access.is_active and access.is_spectator)

        result = {
            "id": self.id,
            "name": self.name,
            "variant": self.variant,
            "betting_structure": self.betting_structure,
            "stakes": self.get_stakes(),
            "max_players": self.max_players,
            "current_players": active_players,
            "spectators": active_spectators,
            "is_private": self.is_private,
            "is_mixed_game": self.is_mixed_game,
            "allow_bots": self.allow_bots,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "creator_id": self.creator_id,
            "minimum_buyin": self.get_minimum_buyin(),
            "maximum_buyin": self.get_maximum_buyin(),
            "is_full": active_players >= self.max_players,
        }

        # Only include sensitive information if requested and appropriate
        if include_sensitive and self.is_private:
            result["invite_code"] = self.invite_code

        return result

    def create_game_instance(self, rules: GameRules) -> Game:
        """Create a Game instance for this table.

        Args:
            rules: GameRules loaded for this table's variant

        Returns:
            Game instance configured for this table
        """
        from generic_poker.game.betting import BettingStructure

        # Map database format to enum format
        structure_mapping = {
            "no-limit": "No Limit",
            "pot-limit": "Pot Limit",
            "limit": "Limit",
            "No Limit": "No Limit",
            "Pot Limit": "Pot Limit",
            "Limit": "Limit",
        }

        # Convert betting structure string to enum
        structure_value = structure_mapping.get(self.betting_structure, self.betting_structure)
        betting_structure = BettingStructure(structure_value)
        stakes_dict = self.get_stakes()

        # Prepare game parameters
        game_params = {
            "rules": rules,
            "structure": betting_structure,
            "min_buyin": self.get_minimum_buyin(),
            "max_buyin": self.get_maximum_buyin(),
            "auto_progress": False,  # Online games should be manually controlled
        }

        # Add betting structure specific parameters
        if betting_structure == BettingStructure.LIMIT:
            game_params.update(
                {
                    "small_bet": stakes_dict.get("small_bet"),
                    "big_bet": stakes_dict.get("big_bet"),
                    "ante": stakes_dict.get("ante", 0),
                    "bring_in": stakes_dict.get("bring_in"),
                }
            )
        else:  # NO_LIMIT or POT_LIMIT
            game_params.update(
                {
                    "small_blind": stakes_dict.get("small_blind"),
                    "big_blind": stakes_dict.get("big_blind"),
                    "ante": stakes_dict.get("ante", 0),
                }
            )

        return Game(**game_params)

    def create_game_instance_for_variant(self, rules: GameRules, betting_structure_str: str) -> Game:
        """Create a Game instance with a specific betting structure override.

        Used by mixed game rotation where different variants use different structures
        (e.g., 8-Game Mix: NL Hold'em vs Limit Stud).

        Args:
            rules: GameRules for the current variant in the rotation
            betting_structure_str: Betting structure string ("Limit", "No Limit", "Pot Limit")

        Returns:
            Game instance configured for this variant
        """
        from generic_poker.game.betting import BettingStructure

        structure_mapping = {
            "no-limit": "No Limit",
            "pot-limit": "Pot Limit",
            "limit": "Limit",
            "No Limit": "No Limit",
            "Pot Limit": "Pot Limit",
            "Limit": "Limit",
            "No-Limit": "No Limit",
            "Pot-Limit": "Pot Limit",
        }

        structure_value = structure_mapping.get(betting_structure_str, betting_structure_str)
        betting_structure = BettingStructure(structure_value)
        stakes_dict = self.get_stakes()

        game_params = {
            "rules": rules,
            "structure": betting_structure,
            "min_buyin": self.get_minimum_buyin(),
            "max_buyin": self.get_maximum_buyin(),
            "auto_progress": False,
        }

        if betting_structure == BettingStructure.LIMIT:
            game_params.update(
                {
                    "small_bet": stakes_dict.get("small_bet"),
                    "big_bet": stakes_dict.get("big_bet"),
                    "ante": stakes_dict.get("ante", 0),
                    "bring_in": stakes_dict.get("bring_in"),
                }
            )
        else:
            # For NL/PL in mixed games, derive blinds from limit stakes
            # Convention: small_blind = small_bet/2, big_blind = small_bet
            small_bet = stakes_dict.get("small_bet", stakes_dict.get("small_blind", 1) * 2)
            game_params.update(
                {
                    "small_blind": stakes_dict.get("small_blind", small_bet // 2),
                    "big_blind": stakes_dict.get("big_blind", small_bet),
                    "ante": stakes_dict.get("ante", 0),
                }
            )

        return Game(**game_params)

    def __repr__(self) -> str:
        return f"<PokerTable {self.name} ({self.variant})>"
