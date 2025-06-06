"""Deck implementation."""
from typing import List, Optional, Set
import random
from enum import Enum, auto

from .card import Card, Rank, Suit, Visibility, WildType
from .containers import CardContainer

class DeckType(str, Enum):
    """Types of poker decks."""
    STANDARD = "standard"    # Full 52-card deck
    SHORT_TA = "short_ta"    # T-A only (20 cards)
    SHORT_6A = "short_6a"    # 6-A (36 cards)
    SHORT_27_JA = "short_27_ja" # 2-7,J-A (40 cards) - used in Mexican Poker
    DIE = "die"              # 6-sided die (1-6)

class Deck(CardContainer):
    """
    A deck of playing cards.
    
    Attributes:
        cards: List of cards in the deck
        include_jokers: Whether deck includes jokers
    """
    
    def __init__(self, include_jokers: int = 0, deck_type: DeckType = DeckType.STANDARD):
        """
        Initialize a new deck.
        
        Args:
            include_jokers: Whether to include joker cards
        """
        self.cards: List[Card] = []
        self._initialize_deck(include_jokers, deck_type)
        
    def _initialize_deck(self, include_jokers: int, deck_type: DeckType) -> None:
        """Create a fresh deck of cards based on the deck type."""

        if deck_type == DeckType.DIE:
            # Create a 6-card "deck" representing a die
            for i in range(1, 7):
                # Use number ranks 1-6 for the die faces
                # We need to ensure Rank can handle numeric strings as values
                rank_value = str(i)
                if rank_value not in [r.value for r in Rank]:
                    # If we don't have numeric ranks, use existing ones like 'A','2','3'...
                    # and map them to die values 1-6
                    rank_mapping = ['A', '2', '3', '4', '5', '6']
                    rank = Rank(rank_mapping[i-1])
                else:
                    rank = Rank(rank_value)
                # Use a neutral suit like CLUBS
                self.cards.append(Card(rank=rank, suit=Suit.CLUBS))
            return
    
        if deck_type == DeckType.SHORT_TA:
            ranks = [Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]
        elif deck_type == DeckType.SHORT_6A:
            ranks = [r for r in Rank if r not in {Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.JOKER, Rank.ONE}]
        elif deck_type == DeckType.SHORT_27_JA:
            ranks = [r for r in Rank if r not in {Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.ONE}]
        else:  # STANDARD
            ranks = [r for r in Rank if r not in {Rank.JOKER, Rank.ONE}]

        # Add standard cards
        for suit in [s for s in Suit if s != Suit.JOKER]:
            for rank in ranks:
                self.cards.append(Card(rank=rank, suit=suit))
                
        # Add jokers if requested
        if include_jokers > 0:
            self.cards.extend([
                Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
                for _ in range(include_jokers)
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