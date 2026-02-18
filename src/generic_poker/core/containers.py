"""Interfaces and implementations for card containers."""

from abc import ABC, abstractmethod

from .card import Card


class CardContainer(ABC):
    """Interface for any collection of cards (deck, hand, etc.)."""

    @abstractmethod
    def add_card(self, card: Card) -> None:
        """Add a single card to the container."""
        pass

    @abstractmethod
    def add_cards(self, cards: list[Card]) -> None:
        """Add multiple cards to the container."""
        pass

    @abstractmethod
    def remove_card(self, card: Card) -> Card:
        """
        Remove and return a specific card.

        Raises:
            ValueError: If card not in container
        """
        pass

    @abstractmethod
    def remove_cards(self, cards: list[Card]) -> list[Card]:
        """
        Remove and return specific cards.

        Raises:
            ValueError: If any card not in container
        """
        pass

    @abstractmethod
    def get_cards(self, visible_only: bool = False) -> list[Card]:
        """
        Get all cards in the container.

        Args:
            visible_only: If True, return only face-up cards
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Remove all cards from the container."""
        pass

    @property
    @abstractmethod
    def size(self) -> int:
        """Number of cards in the container."""
        pass
