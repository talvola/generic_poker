"""Card related classes and utilities."""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Set, Dict


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
    JOKER = 'R'  # For jokers
    ONE = '1'  # For games with 1-6 die instead of using Ace
    
    def __str__(self) -> str:
        return self.value
    
    @property
    def full_name(self) -> str:
        """Get the full name of the rank."""
        return RANK_NAMES.get(self.value, self.value)
        
    @property
    def plural_name(self) -> str:
        """Get the plural form of the rank name."""
        name = self.full_name
        # Special cases
        if name == "Six":
            return "Sixes"
        # Add 's' to all ranks
        return f"{name}s"    

# Mapping from rank symbols to full names
RANK_NAMES: Dict[str, str] = {
    'A': 'Ace',
    'K': 'King',
    'Q': 'Queen', 
    'J': 'Jack',
    'T': 'Ten',
    '9': 'Nine',
    '8': 'Eight',
    '7': 'Seven',
    '6': 'Six',
    '5': 'Five',
    '4': 'Four',
    '3': 'Three',
    '2': 'Two',
    'R': 'Joker',
    '1': 'One'
}

class Visibility(Enum):
    """Card visibility states."""
    FACE_DOWN = auto()
    FACE_UP = auto()


class WildType(Enum):
    """Types of wild cards."""
    NATURAL = auto()     # Card is always wild (like a Joker)
    NAMED = auto()       # Card is designated wild by game rules
    MATCHING = auto()    # Card is wild if matches some condition
    BUG = auto()         # Card is a bug (Ace or straight/flush)

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
            return 'Rj'  # Special format for Jokers
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
    
    @property
    def color(self) -> str:
        """Get the color of the card (red or black)."""
        if self.suit in [Suit.HEARTS, Suit.DIAMONDS]:
            return "red"
        elif self.suit in [Suit.CLUBS, Suit.SPADES]:
            return "black"
        return "unknown"  # For jokers or other special cards

    def make_wild(self, wild_type: WildType) -> None:
        """Make this card wild. For natural Jokers, allow changing to BUG or NAMED but not MATCHING."""
        if self.rank == Rank.JOKER and self.suit == Suit.JOKER and self.wild_type == WildType.NATURAL:
            if wild_type in (WildType.BUG, WildType.NAMED):
                self.wild_type = wild_type
            # Joker is already wild from creation; don't downgrade to MATCHING
            return
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
            return cls(rank=Rank.JOKER, suit=Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
        elif card_str[0] == '*' and card_str[1] != 'j':
            raise ValueError(f"Invalid joker format: {card_str}")
            
        rank_str, suit_str = card_str[0], card_str[1]
        
        try:
            rank = next(r for r in Rank if r.value == rank_str.upper())
            suit = next(s for s in Suit if s.value == suit_str.lower())
        except StopIteration:
            raise ValueError(f"Invalid rank or suit in: {card_str}")
            
        return cls(rank=rank, suit=suit)