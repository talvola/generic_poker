from dataclasses import dataclass, field
from enum import Enum

from generic_poker.core.hand import PlayerHand


class Position(Enum):
    """Core player positions that affect game mechanics."""

    BUTTON = "BTN"
    SMALL_BLIND = "SB"
    BIG_BLIND = "BB"


@dataclass
class PlayerPosition:
    """Represents a player's position(s) at the table."""

    positions: list[Position]  # A player can have multiple positions in heads-up

    @property
    def value(self) -> str:
        """Return primary position value."""
        return self.positions[0].value if self.positions else "NA"

    def has_position(self, position: Position) -> bool:
        """Check if player has a specific position."""
        return position in self.positions


@dataclass
class Player:
    """
    Represents a player at the table.

    Attributes:
        id: Unique identifier for the player
        name: Display name
        stack: Current chip stack
        position: Current position at table
        hand: Current cards
        is_active: Whether player is in current hand
    """

    id: str
    name: str
    stack: int
    position: PlayerPosition | None = None
    hand: PlayerHand = field(default_factory=PlayerHand)  # Always initialized
    is_active: bool = True

    def __post_init__(self):
        """Initialize player's hand if not provided."""
        if self.hand is None:
            self.hand = PlayerHand()

    def __eq__(self, other):
        if not isinstance(other, Player):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


def has_position(player, pos):
    return player.position is not None and player.position.has_position(pos)
