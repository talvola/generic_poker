import json
from dataclasses import dataclass, field

from generic_poker.core.card import Card


@dataclass
class HandResult:
    """Information about a player's hand and its evaluation."""

    player_id: str
    cards: list[Card]  # Cards in the hand
    hand_name: str  # e.g., "Full House"
    hand_description: str  # e.g., "Full House, Aces over Kings"
    evaluation_type: str  # "high", "low", etc.
    hand_type: str = "Hand"  # from game config showdown
    community_cards: list[Card] = field(default_factory=list)  # Community cards if applicable
    used_hole_cards: list[Card] = field(default_factory=list)  # Cards used in the hand
    rank: int = 0
    ordered_rank: int = 0
    classifications: dict[str, str] = field(default_factory=dict)  # New field for classifications

    def __str__(self) -> str:
        """String representation of the hand result."""
        cards_str = ", ".join(str(card) for card in self.cards)
        # Append classification if present
        classification_str = ""
        if "face_butt" in self.classifications:
            classification_str = f" ({self.classifications['face_butt'].capitalize()})"
        return f"Player {self.player_id}: {self.hand_description}{classification_str} ({cards_str})"

    def to_json(self) -> dict:
        """Convert to JSON-compatible dictionary."""
        return {
            "player_id": self.player_id,
            "cards": [str(card) for card in self.cards],
            "hand_name": self.hand_name,
            "hand_description": self.hand_description,
            "evaluation_type": self.evaluation_type,
            "hand_type": self.hand_type,
            "community_cards": [str(card) for card in self.community_cards],
            "used_hole_cards": [str(card) for card in self.used_hole_cards],  # Added for Omaha Hi/Hi
            "rank": self.rank,
            "ordered_rank": self.ordered_rank,
            "classifications": self.classifications,  # Include classifications
        }


@dataclass
class PotResult:
    """Information about a pot and its winner(s)."""

    amount: int  # Amount in the pot
    winners: list[str]  # List of player IDs who won this pot
    pot_type: str = "main"  # "main" or "side"
    hand_type: str = "Hand"  # from game config showdown
    side_pot_index: int | None = None  # Index of side pot if applicable
    eligible_players: set[str] = None  # Players who could win this pot
    reason: str | None = None  # Reason for pot award (e.g., "Best high hand")
    best_hands: list[HandResult] = field(default_factory=list)  # Best hands for this pot's hand_type
    declarations: dict[str, str] = field(default_factory=dict)  # Player ID -> declaration (e.g., "high")
    split: bool = False  # Whether the pot was split (multiple winners)

    def __post_init__(self):
        # Ensure eligible_players is a set
        if self.eligible_players is None:
            self.eligible_players = set()
        # Ensure winners is a list
        if self.winners is None:
            self.winners = []
        # Set split based on number of winners
        self.split = len(self.winners) > 1
        # Ensure best_hands is a list
        if self.best_hands is None:
            self.best_hands = []
        # Ensure declarations is a dict
        if self.declarations is None:
            self.declarations = {}

    @property
    def amount_per_player(self) -> int:
        """Amount each winner receives from the pot."""
        if not self.winners:
            return 0
        return self.amount // len(self.winners)

    def __str__(self) -> str:
        """String representation of the pot result."""
        pot_name = "Main pot" if self.pot_type == "main" else f"Side pot {self.side_pot_index + 1}"
        winners_str = ", ".join(self.winners)
        reason_str = f" ({self.reason})" if self.reason else ""
        if self.split:
            return (
                f"{pot_name}: ${self.amount} - Split between {winners_str} (${self.amount_per_player} each){reason_str}"
            )
        else:
            return f"{pot_name}: ${self.amount} - Won by {winners_str}{reason_str}"

    def to_json(self) -> dict:
        """Convert to JSON-compatible dictionary."""
        return {
            "amount": self.amount,
            "winners": self.winners,
            "split": self.split,
            "pot_type": self.pot_type,
            "hand_type": self.hand_type,
            "side_pot_index": self.side_pot_index,
            "eligible_players": list(self.eligible_players),
            "amount_per_player": self.amount_per_player,
            "reason": self.reason,
            "best_hands": [hand.to_json() for hand in self.best_hands],
            "declarations": self.declarations,
        }


@dataclass
class GameResult:
    """Complete results of a poker hand."""

    pots: list[PotResult]  # Results for each pot
    hands: dict[str, list[HandResult]]  # Hand results by player ID, now a list
    winning_hands: list[HandResult]  # List of winning hands (may be multiple)
    is_complete: bool = True  # Whether the hand played to completion

    @property
    def total_pot(self) -> int:
        """Total amount in all pots."""
        return sum(pot.amount for pot in self.pots)

    @property
    def winners(self) -> list[str]:
        """List of all unique winner IDs."""
        all_winners = [winner for pot in self.pots for winner in pot.winners]
        return list(set(all_winners))

    def __str__(self) -> str:
        """String representation of the game result."""
        lines = [f"Game Result (Complete: {self.is_complete})"]
        lines.append(f"Total pot: ${self.total_pot}")

        # Group pot results by type (high/low)
        pot_groups = {}
        for pot in self.pots:
            pot_type = getattr(pot, "hand_type", "Unspecified")
            if pot_type not in pot_groups:
                pot_groups[pot_type] = []
            pot_groups[pot_type].append(pot)

        # Display pot results by group
        lines.append("\nPot Results:")
        for pot_type, pots in pot_groups.items():
            lines.append(f"\n{pot_type} Pot Division:")
            for pot in pots:
                lines.append(f"- {pot}")

        # Create a mapping of hand type to all hands of that type
        all_hands_by_type = {}
        for _player_id, player_hands in self.hands.items():
            # Handle both list and dict cases for player_hands
            if isinstance(player_hands, dict):
                hands_iter = player_hands.values()
            elif isinstance(player_hands, list):
                hands_iter = player_hands
            else:
                raise ValueError(f"Unexpected type for player_hands: {type(player_hands)}")

            for hand in hands_iter:
                hand_type = getattr(hand, "hand_type", "Unspecified")
                if hand_type not in all_hands_by_type:
                    all_hands_by_type[hand_type] = []
                all_hands_by_type[hand_type].append(hand)

        # [Rest of the method remains unchanged]
        # Create a mapping of hand type to winning hands of that type
        winning_hands_by_type = {}
        for hand in self.winning_hands:
            hand_type = getattr(hand, "hand_type", "Unspecified")
            if hand_type not in winning_hands_by_type:
                winning_hands_by_type[hand_type] = []
            winning_hands_by_type[hand_type].append(hand)

        # Get winning hand player IDs by type
        winning_players_by_type = {}
        for hand_type, hands in winning_hands_by_type.items():
            winning_players_by_type[hand_type] = {hand.player_id for hand in hands}

        # Display each hand type section
        for hand_type, all_hands in all_hands_by_type.items():
            lines.append(f"\n{hand_type}:")

            # Winning hands for this type
            winning_hands = winning_hands_by_type.get(hand_type, [])
            if winning_hands:
                lines.append("\tWinning Hands:")
                for hand in winning_hands:
                    lines.append(f"\t\t- {hand}")

            # Losing hands for this type
            winning_ids = winning_players_by_type.get(hand_type, set())
            losing_hands = [hand for hand in all_hands if hand.player_id not in winning_ids]
            if losing_hands:
                lines.append("\tLosing Hands:")
                for hand in losing_hands:
                    lines.append(f"\t\t- {hand}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Convert to JSON string."""
        result_dict = {
            "is_complete": self.is_complete,
            "total_pot": self.total_pot,
            "pots": [pot.to_json() for pot in self.pots],
            "hands": {pid: [hand.to_json() for hand in hands] for pid, hands in self.hands.items()},
            "winning_hands": [hand.to_json() for hand in self.winning_hands],
        }
        return json.dumps(result_dict, indent=2)
