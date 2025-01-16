"""Deck implementation."""
from typing import List, Optional, Set
import random

from .card import Card, Rank, Suit, Visibility
from .containers import CardContainer


class Deck(CardContainer):
    """
    A deck of playing cards.
    
    Attributes:
        cards: List of cards in the deck
        include_jokers: Whether deck includes jokers
    """
    
    def __init__(self, include_jokers: bool = False):
        """
        Initialize a new deck.
        
        Args:
            include_jokers: Whether to include joker cards
        """
        self.cards: List[Card] = []
        self._initialize_deck(include_jokers)
        
    def _initialize_deck(self, include_jokers: bool) -> None:
        """Create a fresh deck of cards."""
        # Add standard cards
        for suit in [s for s in Suit if s != Suit.JOKER]:
            for rank in [r for r in Rank if r != Rank.JOKER]:
                self.cards.append(Card(rank=rank, suit=suit))
                
        # Add jokers if requested
        if include_jokers:
            self.cards.extend([
                Card(Rank.JOKER, Suit.JOKER, is_wild=True) 
                for _ in range(2)
            ])
    
    def shuffle(self, times: int = 1) -> None:
        """
        Shuffle the deck.
        
        Args:
            times: Number of times to shuffle
        """
        for _ in range(times):
            random.shuffle(self.cards)
    
    def deal_card(self, face_up: bool = False) -> Optional[Card]:
        """
        Deal a single card from the top of the deck.
        
        Args:
            face_up: Whether to deal card face up
            
        Returns:
            Card or None if deck is empty
        """
        if not self.cards:
            return None
            
        card = self.cards.pop()
        if face_up:
            card.visibility = Visibility.FACE_UP
        return card
    
    def deal_cards(self, count: int, face_up: bool = False) -> List[Card]:
        """
        Deal multiple cards from the top of the deck.
        
        Args:
            count: Number of cards to deal
            face_up: Whether to deal cards face up
            
        Returns:
            List of cards (may be fewer than requested if deck runs out)
        """
        cards = []
        for _ in range(count):
            card = self.deal_card(face_up)
            if card is None:
                break
            cards.append(card)
        return cards
    
    # CardContainer implementation
    def add_card(self, card: Card) -> None:
        """Add a card to the deck."""
        self.cards.append(card)
        
    def add_cards(self, cards: List[Card]) -> None:
        """Add multiple cards to the deck."""
        self.cards.extend(cards)
        
    def remove_card(self, card: Card) -> Card:
            """
            Remove a specific card from the deck.
            Matches only on rank and suit, ignoring visibility.
            
            Args:
                card: Card to remove
                
            Returns:
                The removed card
                
            Raises:
                ValueError: If card not in deck
            """
            for deck_card in self.cards:
                if (deck_card.rank == card.rank and 
                    deck_card.suit == card.suit):
                    self.cards.remove(deck_card)
                    return deck_card
            raise ValueError(f"Card {card} not in deck")
            
    def remove_cards(self, cards: List[Card]) -> List[Card]:
        """Remove specific cards from the deck."""
        for card in cards:
            self.remove_card(card)
        return cards
    
    def get_cards(self, visible_only: bool = False) -> List[Card]:
        """Get all cards in the deck."""
        if visible_only:
            return [c for c in self.cards if c.visibility == Visibility.FACE_UP]
        return self.cards.copy()
    
    def clear(self) -> None:
        """Remove all cards from the deck."""
        self.cards.clear()
        
    @property
    def size(self) -> int:
        """Number of cards in the deck."""
        return len(self.cards)