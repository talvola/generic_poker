"""Table implementation managing game state."""
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

from generic_poker.core.card import Card
from generic_poker.core.deck import Deck
from generic_poker.core.hand import PlayerHand


class Position(Enum):
    """Player positions at the table."""
    SMALL_BLIND = "SB"
    BIG_BLIND = "BB"
    UNDER_THE_GUN = "UTG"
    MIDDLE_POSITION = "MP"
    CUTOFF = "CO"
    BUTTON = "BTN"


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
    position: Optional[Position] = None
    hand: Optional[PlayerHand] = None
    is_active: bool = True

    def __post_init__(self):
        """Initialize player's hand if not provided."""
        if self.hand is None:
            self.hand = PlayerHand()


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
    
    def __init__(self, max_players: int, min_buyin: int, max_buyin: int):
        """
        Initialize a new table.
        
        Args:
            max_players: Maximum number of players allowed
            min_buyin: Minimum buy-in amount
            max_buyin: Maximum buy-in amount
        """
        self.max_players = max_players
        self.min_buyin = min_buyin
        self.max_buyin = max_buyin
        
        self.players: Dict[str, Player] = {}  # id -> Player
        self.button_pos: int = 0  # Index of button position
        self.deck = Deck()
        self.community_cards: List[Card] = []
        
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
        """Move the dealer button to the next position."""
        active_players = [p for p in self.players.values() if p.is_active]
        if not active_players:
            return
            
        self.button_pos = (self.button_pos + 1) % len(active_players)
        
    def get_position_order(self) -> List[Player]:
        """
        Get players in position order for betting.
        
        Returns list in BTN->SB->BB order, which means:
        - For blind posting: players are in order
        - For betting: start with player after BB (BTN)
        """
        active_players = list(self.players.values())
        if not active_players:
            return []
        
        # Organize positions
        if len(active_players) <= 3:
            # Heads up or 3-handed
            active_players[0].position = Position.BUTTON
            active_players[1].position = Position.SMALL_BLIND
            if len(active_players) > 2:
                active_players[2].position = Position.BIG_BLIND
        else:
            # Full ring
            positions = [
                Position.BUTTON,
                Position.SMALL_BLIND,
                Position.BIG_BLIND,
                Position.UNDER_THE_GUN,
                Position.MIDDLE_POSITION,
                Position.CUTOFF,
            ]
            for i, player in enumerate(active_players):
                player.position = positions[min(i, len(positions) - 1)]
        
        return active_players
        
    def get_player_to_act(self, round_start: bool = False) -> Optional[Player]:
        """
        Get the next player to act.
        
        Args:
            round_start: True if this is start of betting round
            
        Returns:
            Next player to act or None if no one can act
        """
        active_players = [p for p in self.players.values() if p.is_active]
        if not active_players:
            return None
            
        if round_start:
            # UTG or next position after BB acts first
            positions = self.get_position_order()
            return positions[2] if len(positions) > 2 else positions[0]
        else:
            # TODO: Implement getting next player in order
            # Need to track last actor
            pass
            
    def deal_hole_cards(self, num_cards: int) -> None:
        """
        Deal hole cards to all active players.
        
        Args:
            num_cards: Number of cards to deal to each player
        """
        self.deck.shuffle()
        active_players = [p for p in self.players.values() if p.is_active]
        
        for _ in range(num_cards):
            for player in active_players:
                card = self.deck.deal_card()
                if card:
                    player.hand.add_card(card)
                    
    def deal_community_cards(self, num_cards: int) -> None:
        """
        Deal community cards.
        
        Args:
            num_cards: Number of community cards to deal
        """
        cards = self.deck.deal_cards(num_cards, face_up=True)
        self.community_cards.extend(cards)
        
    def clear_hands(self) -> None:
        """Clear all player hands and community cards."""
        for player in self.players.values():
            player.hand.clear()
        self.community_cards.clear()
        self.deck = Deck()  # New shuffled deck