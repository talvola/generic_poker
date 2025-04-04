"""Table implementation managing game state."""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from generic_poker.core.card import Card, Visibility
from generic_poker.core.deck import Deck, DeckType
from generic_poker.core.hand import PlayerHand

logger = logging.getLogger(__name__)

class Position(Enum):
    """Core player positions that affect game mechanics."""
    BUTTON = "BTN"
    SMALL_BLIND = "SB"
    BIG_BLIND = "BB"

@dataclass
class PlayerPosition:
    """Represents a player's position(s) at the table."""
    positions: List[Position]  # A player can have multiple positions in heads-up

    @property
    def value(self) -> str:
        """Return primary position value."""
        return self.positions[0].value if self.positions else 'NA'

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
    position: Optional[PlayerPosition] = None
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
    
class Table:
    """
    Manages the state of a poker table.
    
    Attributes:
        max_players: Maximum players allowed
        players: Current players
        button_pos: Position of dealer button
        deck: Current deck
        community_cards: Shared community cards
        min_buyin: Minimum buy-in amount
        max_buyin: Maximum buy-in amount
    """
    
    def __init__(self, max_players: int, min_buyin: int, max_buyin: int, deck_type: DeckType = DeckType.STANDARD):
        """
        Initialize a new table.
        
        Args:
            max_players: Maximum number of players allowed
            min_buyin: Minimum buy-in amount
            max_buyin: Maximum buy-in amount
            deck_type: Type of deck to use (default: STANDARD)
        """
        self.max_players = max_players
        self.min_buyin = min_buyin
        self.max_buyin = max_buyin
        self.deck_type = deck_type  # Store the deck type
  
        self.players: Dict[str, Player] = {}  # id -> Player
        self.button_pos: int = 0  # Index of button position
        self.deck = Deck(deck_type=self.deck_type)
        self.discard_pile = Deck()  # New discard pile
        self.discard_pile.clear()  # Ensure it's empty
        self.community_cards: Dict[str, List[Card]] = {}
       
    def add_player(self, player_id: str, name: str, buyin: int) -> None:
        """
        Add a player to the table.
        
        Args:
            player_id: Unique identifier for player
            name: Display name
            buyin: Initial buy-in amount
            
        Raises:
            ValueError: If table is full or buyin invalid
        """
        if len(self.players) >= self.max_players:
            raise ValueError("Table is full")
            
        if buyin < self.min_buyin or buyin > self.max_buyin:
            raise ValueError(
                f"Buy-in must be between {self.min_buyin} and {self.max_buyin}"
            )
            
        self.players[player_id] = Player(
            id=player_id,
            name=name,
            stack=buyin
        )
        
    def remove_player(self, player_id: str) -> None:
        """Remove a player from the table."""
        if player_id in self.players:
            del self.players[player_id]
            
    def move_button(self) -> None:
        """
        Move the dealer button to the next position.
        
        The button moves clockwise (left) around the table,
        so each player gets a chance to be on the button.
        """
        active_players = list(self.players.values())
        if not active_players:
            return
            
        self.button_pos = (self.button_pos + 1) % len(active_players)
        
    def get_position_order(self) -> List[Player]:
        """
        Get players in position order for betting.
        
        In 3+ player games:
            - BTN, SB, BB are distinct positions
        In heads-up (2 player) games:
            - First player is both BTN and SB
            - Second player is BB
        Single player or empty table:
            - Returns list with no positions assigned
        """
        active_players = list(self.players.values())
        num_players = len(active_players)
        
        if num_players == 0:
            return []
            
        # Single player - no positions assigned
        if num_players == 1:
            active_players[0].position = None
            return active_players
            
        # Rotate list so button_pos is first
        rotated_players = (
            active_players[self.button_pos:] + 
            active_players[:self.button_pos]
        )
            
        # For heads-up play
        if num_players == 2:
            rotated_players[0].position = PlayerPosition([Position.BUTTON, Position.SMALL_BLIND])
            rotated_players[1].position = PlayerPosition([Position.BIG_BLIND])
            return rotated_players
        
        # For 3+ players
        else:
            rotated_players[0].position = PlayerPosition([Position.BUTTON])
            rotated_players[1].position = PlayerPosition([Position.SMALL_BLIND])
            rotated_players[2].position = PlayerPosition([Position.BIG_BLIND])
            
            # Clear any existing positions for other players
            for player in rotated_players[3:]:
                player.position = None
                    
            return rotated_players
        
    def get_player_to_act(self, round_start: bool = False) -> Optional[Player]:
        """
        Get the next player to act.
        
        Args:
            round_start: True if this is start of betting round
            
        Returns:
            Next player to act or None if no one can act
        """
        positions = self.get_position_order()
        if not positions:
            return None
            
        # Heads-up play has special betting order
        if len(positions) == 2:
            if round_start:
                # Preflop: Button/SB acts first
                return positions[0]
            else:
                # Postflop: BB acts first 
                return positions[1]
                
        # For 3+ players
        if round_start:
            if len(positions) <= 3:
                # In 3-player game, BTN acts first pre-flop
                return positions[0]
            else:
                # In larger games, UTG (after BB) acts first pre-flop
                return positions[3]
        else:
            # For post-flop betting, SB acts first
            return positions[1]
            

    def get_active_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.is_active]

    def deal_hole_cards(self, num_cards: int, face_up: bool = False, subset: str = "default") -> None:
        """
        Deal hole cards to all active players and assign them to a specified subset.

        Args:
            num_cards: Number of cards to deal to each player
            face_up: Whether to deal the cards face up (default: False)
            subset: Name of the subset to assign the cards to (default: "default")
        """
        active_players = [p for p in self.players.values() if p.is_active]
        
        for _ in range(num_cards):
            for player in active_players:
                card = self.deck.deal_card(face_up=face_up)  # Pass face_up to Deck
                if card:
                    logger.info(f"  Dealt {card} to player {player.name} in subset '{subset}'")
                    player.hand.add_card(card)  # Add to the hand's card list
                    if subset and subset != "default":  # Only assign to subset if specified and not "default"
                        player.hand.add_to_subset(card, subset)     
                    
    def deal_community_cards(self, num_cards: int, subset: str = "default", face_up: bool = True) -> None:
        """
        Deal community cards to a specific subset.

        Args:
            num_cards: Number of community cards to deal
            subset: Name of the subset to deal to (default: "default")
            face_up: Whether to deal the cards face up (default: True)
        """
        if subset not in self.community_cards:
            self.community_cards[subset] = []
        cards = self.deck.deal_cards(num_cards, face_up=face_up)
        if cards:
            logger.info(f"  Dealt {len(cards)} community {'card' if len(cards) == 1 else 'cards'} to subset '{subset}': {cards}")
        self.community_cards[subset].extend(cards)
        
    def expose_community_cards(self, subset: str = "default", indices: Optional[List[int]] = None) -> None:
        """
        Flip specified community cards face-up in a subset. If no indices provided, flip all face-down cards in the subset.

        Args:
            subset: Name of the subset to expose cards from (default: "default")
            indices: Optional list of indices of cards to expose in the subset
        """
        if subset not in self.community_cards:
            logger.warning(f"Subset '{subset}' does not exist.")
            return
        cards = self.community_cards[subset]
        if indices is None:
            for card in cards:
                if card.visibility == Visibility.FACE_DOWN:
                    card.visibility = Visibility.FACE_UP
                    logger.info(f"  Exposed {card} in subset '{subset}'")
        else:
            for idx in indices:
                if 0 <= idx < len(cards) and cards[idx].visibility == Visibility.FACE_DOWN:
                    cards[idx].visibility = Visibility.FACE_UP
                    logger.info(f"  Exposed {cards[idx]} in subset '{subset}'")

    def get_community_card_count(self, subset: str = "default") -> int:
        """
        Get the number of community cards in a specific subset.

        Args:
            subset: Name of the subset to count cards from (default: "default")

        Returns:
            Number of cards in the specified subset, or 0 if the subset doesn’t exist
        """
        return len(self.community_cards.get(subset, []))                    

    def clear_hands(self) -> None:
        """Clear all player hands, community cards, and reset the deck."""
        for player in self.players.values():
            player.hand.clear()
        self.community_cards.clear()
        self.discard_pile.clear()
        self.deck = Deck(deck_type=self.deck_type)  # Use stored deck_type
       