"""Card related classes and utilities."""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Set


class Suit(Enum):
    """Card suits."""
    CLUBS = 'c'
    DIAMONDS = 'd'
    HEARTS = 'h'
    SPADES = 's'
    JOKER = 'j'  # For games with jokers
    
    def __str__(self) -> str:
        return self.value


class Rank(Enum):
    """Card ranks."""
    TWO = '2'
    THREE = '3'
    FOUR = '4'
    FIVE = '5'
    SIX = '6'
    SEVEN = '7'
    EIGHT = '8'
    NINE = '9'
    TEN = 'T'
    JACK = 'J'
    QUEEN = 'Q'
    KING = 'K'
    ACE = 'A'
    JOKER = '*'  # For jokers
    
    def __str__(self) -> str:
        return self.value


class Visibility(Enum):
    """Card visibility states."""
    FACE_DOWN = auto()
    FACE_UP = auto()


class WildType(Enum):
    """Types of wild cards."""
    NATURAL = auto()     # Card is always wild (like a Joker)
    NAMED = auto()       # Card is designated wild by game rules
    MATCHING = auto()    # Card is wild if matches some condition


@dataclass
class Card:
    """
    Represents a playing card.
    
    Attributes:
        rank: Card rank (2-A, or * for Joker)
        suit: Card suit (clubs, diamonds, hearts, spades, joker)
        visibility: Whether card is face up or down
        is_wild: Whether card is currently wild
        wild_type: Type of wildness if card is wild
    """
    rank: Rank
    suit: Suit
    visibility: Visibility = Visibility.FACE_DOWN
    is_wild: bool = False
    wild_type: Optional[WildType] = None
    
    def __str__(self) -> str:
        """String representation in format 'As' for Ace of spades."""
        if self.rank == Rank.JOKER:
            return '*j'  # Special format for Jokers
        return f"{self.rank}{self.suit}"
    
    def __eq__(self, other: object) -> bool:
        """Cards are equal if rank and suit match."""
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit
    
    def flip(self) -> None:
        """Flip the card's visibility."""
        self.visibility = (
            Visibility.FACE_DOWN 
            if self.visibility == Visibility.FACE_UP 
            else Visibility.FACE_UP
        )
    
    def make_wild(self, wild_type: WildType) -> None:
        """Make this card wild."""
        self.is_wild = True
        self.wild_type = wild_type
    
    def clear_wild(self) -> None:
        """Remove wild status from card."""
        self.is_wild = False
        self.wild_type = None
    
    @classmethod
    def from_string(cls, card_str: str) -> 'Card':
        """
        Create a Card from a string representation.
        
        Args:
            card_str: String in format 'As' for Ace of spades,
                     or '*j' for Joker
            
        Returns:
            Card instance
            
        Raises:
            ValueError: If string format is invalid
        """
        if len(card_str) != 2:
            raise ValueError(f"Invalid card string: {card_str}")
            
        # Handle Jokers
        if card_str == '*j':
            return cls(
                rank=Rank.JOKER,
                suit=Suit.JOKER,
                is_wild=True,
                wild_type=WildType.NATURAL
            )
            
        rank_str, suit_str = card_str[0], card_str[1]
        
        try:
            rank = next(r for r in Rank if r.value == rank_str.upper())
            suit = next(s for s in Suit if s.value == suit_str.lower())
        except StopIteration:
            raise ValueError(f"Invalid rank or suit in: {card_str}")
            
        return cls(rank=rank, suit=suit)