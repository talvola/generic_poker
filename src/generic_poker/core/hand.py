"""Player hand implementation."""

import logging
from collections import defaultdict

from .card import Card, Visibility
from .containers import CardContainer

logger = logging.getLogger(__name__)


class PlayerHand(CardContainer):
    """
    A player's poker hand.

    Can be subdivided into named subsets for games that require it.

    Attributes:
        cards: List of all cards in the hand
        subsets: Optional mapping of subset names to cards
    """

    def __init__(self):
        """Initialize an empty hand."""
        self.cards: list[Card] = []
        self.subsets: dict[str, list[Card]] = defaultdict(list)

    def add_to_subset(self, card: Card, subset_name: str) -> None:
        """
        Add a card to a specific subset.

        Args:
            card: Card to add
            subset_name: Name of subset to add to

        Raises:
            ValueError: If card not in hand
        """
        if card not in self.cards:
            raise ValueError(f"Card {card} not in hand")

        self.subsets[subset_name].append(card)

    def remove_from_subset(self, card: Card, subset_name: str) -> None:
        """
        Remove a card from a specific subset.

        Args:
            card: Card to remove
            subset_name: Name of subset to remove from

        Raises:
            ValueError: If card not in subset
        """
        if subset_name not in self.subsets:
            raise ValueError(f"No subset named {subset_name}")

        try:
            self.subsets[subset_name].remove(card)
        except ValueError:
            raise ValueError(f"Card {card} not in subset {subset_name}")

    def get_subset(self, subset_name: str) -> list[Card]:
        """Get all cards in a specific subset."""
        return self.subsets.get(subset_name, []).copy()

    def clear_subsets(self) -> None:
        """Remove all subset assignments but keep cards."""
        self.subsets.clear()

    def show_all(self) -> None:
        """Make all cards in hand visible."""
        for card in self.cards:
            card.visibility = Visibility.FACE_UP

    def hide_all(self) -> None:
        """Make all cards in hand hidden."""
        for card in self.cards:
            card.visibility = Visibility.FACE_DOWN

    # CardContainer implementation
    def add_card(self, card: Card) -> None:
        """Add a card to the hand."""
        self.cards.append(card)

    def add_cards(self, cards: list[Card]) -> None:
        """Add multiple cards to the hand."""
        self.cards.extend(cards)

    def remove_card(self, card: Card) -> Card:
        """Remove a specific card from the hand."""
        try:
            self.cards.remove(card)
            # Also remove from any subsets
            for subset in self.subsets.values():
                if card in subset:
                    subset.remove(card)
            return card
        except ValueError:
            raise ValueError(f"Card {card} not in hand")

    def remove_cards(self, cards: list[Card]) -> list[Card]:
        """Remove specific cards from the hand."""
        for card in cards:
            self.remove_card(card)
        return cards

    def get_cards(self, visible_only: bool = False) -> list[Card]:
        """Get all cards in the hand."""
        if visible_only:
            return [c for c in self.cards if c.visibility == Visibility.FACE_UP]
        return self.cards.copy()

    def clear(self) -> None:
        """Remove all cards from the hand."""
        self.cards.clear()
        self.subsets.clear()

    @classmethod
    def from_string(cls, hand_str: str) -> list[Card]:
        """
        Create a Hand from a string representation.

        Args:
            hand_str: String of concatenated card representations (e.g., "AsAhJs9s5s")
                      Each card is 2 characters: rank (A, K, Q, J, T, 9-2, X for Joker)
                      followed by suit (s, h, d, c, j for Joker).

        Returns:
            Hand instance with the parsed cards

        Raises:
            ValueError: If the string format is invalid (e.g., wrong length, invalid cards)
        """
        # Validate the string length (each card is 2 characters)
        if len(hand_str) % 2 != 0:
            raise ValueError(f"Invalid hand string length: {hand_str} (must be multiple of 2)")

        # Split the string into 2-character chunks
        card_strings = [hand_str[i : i + 2] for i in range(0, len(hand_str), 2)]

        # Create an empty list
        hand = []

        # Convert each card string to a Card object
        for i, card_str in enumerate(card_strings):
            try:
                card = Card.from_string(card_str)
            except ValueError as e:
                raise ValueError(f"Invalid card at position {i + 1} in hand string '{hand_str}': {e}")

            hand.append(card)

        logger.debug(f"Created hand from string '{hand_str}': {[str(c) for c in hand]}")
        return hand

    @property
    def size(self) -> int:
        """Number of cards in the hand."""
        return len(self.cards)

    def __str__(self) -> str:
        """String representation showing cards in hand."""
        if not self.cards:
            return "Empty hand"

        # Sort cards by visibility first
        visible = []
        hidden = []
        for card in self.cards:
            if card.visibility == Visibility.FACE_UP:
                visible.append(str(card))
            else:
                hidden.append("**")

        return f"Hand: {' '.join(visible + hidden)}"
