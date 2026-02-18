"""Game history model for storing completed hands."""

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class GameHistory(db.Model):
    """Model for storing completed poker hands."""

    __tablename__ = "game_history"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Game identification
    hand_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Game data (stored as JSON)
    players: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    actions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    results: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string

    # Additional metadata
    variant: Mapped[str] = mapped_column(String(50), nullable=False)
    betting_structure: Mapped[str] = mapped_column(String(20), nullable=False)
    stakes: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string

    # Timestamp
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Foreign keys
    table_id: Mapped[str] = mapped_column(String(36), ForeignKey("poker_tables.id"), nullable=False)

    # Relationships
    table: Mapped["PokerTable"] = relationship("PokerTable", back_populates="game_history")

    def __init__(
        self,
        table_id: str,
        hand_number: int,
        players: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        results: dict[str, Any],
        variant: str,
        betting_structure: str,
        stakes: dict[str, int],
    ):
        """Initialize game history record."""
        self.table_id = table_id
        self.hand_number = hand_number
        self.players = json.dumps(players)
        self.actions = json.dumps(actions)
        self.results = json.dumps(results)
        self.variant = variant
        self.betting_structure = betting_structure
        self.stakes = json.dumps(stakes)

    def get_players(self) -> list[dict[str, Any]]:
        """Get players data as list of dictionaries."""
        return json.loads(self.players)

    def get_actions(self) -> list[dict[str, Any]]:
        """Get actions data as list of dictionaries."""
        return json.loads(self.actions)

    def get_results(self) -> dict[str, Any]:
        """Get results data as dictionary."""
        return json.loads(self.results)

    def get_stakes(self) -> dict[str, int]:
        """Get stakes data as dictionary."""
        return json.loads(self.stakes)

    def get_winner_ids(self) -> list[str]:
        """Get list of winner user IDs."""
        results = self.get_results()
        return results.get("winners", [])

    def get_total_pot(self) -> int:
        """Get total pot amount for this hand."""
        results = self.get_results()
        return results.get("total_pot", 0)

    def get_player_count(self) -> int:
        """Get number of players in this hand."""
        return len(self.get_players())

    def was_player_involved(self, user_id: str) -> bool:
        """Check if a specific user was involved in this hand."""
        players = self.get_players()
        return any(player.get("user_id") == user_id for player in players)

    def get_player_result(self, user_id: str) -> dict[str, Any]:
        """Get specific player's result from this hand."""
        players = self.get_players()
        results = self.get_results()

        # Find player in players list
        player_data = None
        for player in players:
            if player.get("user_id") == user_id:
                player_data = player
                break

        if not player_data:
            return {}

        # Get player's winnings from results
        player_winnings = results.get("player_winnings", {})
        winnings = player_winnings.get(user_id, 0)

        return {
            "player_data": player_data,
            "winnings": winnings,
            "net_result": winnings - player_data.get("total_bet", 0),
            "was_winner": user_id in self.get_winner_ids(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert game history to dictionary representation."""
        return {
            "id": self.id,
            "table_id": self.table_id,
            "hand_number": self.hand_number,
            "players": self.get_players(),
            "actions": self.get_actions(),
            "results": self.get_results(),
            "variant": self.variant,
            "betting_structure": self.betting_structure,
            "stakes": self.get_stakes(),
            "completed_at": self.completed_at.isoformat(),
            "total_pot": self.get_total_pot(),
            "player_count": self.get_player_count(),
            "winners": self.get_winner_ids(),
        }

    def to_export_format(self) -> str:
        """Export hand history in a standard format."""
        # This could be expanded to support various export formats
        # For now, return a simple text representation
        players = self.get_players()
        actions = self.get_actions()
        self.get_results()

        export_lines = [
            f"Hand #{self.hand_number} - {self.variant} {self.betting_structure}",
            f"Table: {self.table_id}",
            f"Date: {self.completed_at.isoformat()}",
            f"Stakes: {self.get_stakes()}",
            "",
            "Players:",
        ]

        for player in players:
            export_lines.append(f"  {player.get('username', 'Unknown')} - {player.get('starting_chips', 0)} chips")

        export_lines.extend(["", "Actions:"])
        for action in actions:
            export_lines.append(f"  {action}")

        export_lines.extend(["", "Results:"])
        export_lines.append(f"  Total Pot: {self.get_total_pot()}")
        export_lines.append(f"  Winners: {', '.join(self.get_winner_ids())}")

        return "\n".join(export_lines)

    def __repr__(self) -> str:
        return f"<GameHistory Hand #{self.hand_number} at Table {self.table_id}>"
