"""Enhanced Table implementation with realistic poker seating."""
import itertools
import logging
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum

from generic_poker.core.card import Card, Visibility
from generic_poker.core.deck import Deck, DeckType
from generic_poker.core.hand import PlayerHand
from generic_poker.config.loader import GameRules, ForcedBets
from generic_poker.evaluation.evaluator import EvaluationType, evaluator
from generic_poker.evaluation.cardrule import CardRule
from generic_poker.game.bringin import BringInDeterminator
from generic_poker.game.player import Player, PlayerPosition, Position

logger = logging.getLogger(__name__)

class SeatStatus(Enum):
    """Status of a seat at the table."""
    EMPTY = "empty"
    OCCUPIED = "occupied"
    RESERVED = "reserved"  # Temporarily held for a player

@dataclass
class Seat:
    """Represents a physical seat at the poker table."""
    number: int
    status: SeatStatus = SeatStatus.EMPTY
    player: Optional[Player] = None
    reserved_for: Optional[str] = None  # Player ID if reserved
    
    def is_available(self) -> bool:
        """Check if seat is available for a new player."""
        return self.status == SeatStatus.EMPTY
    
    def occupy(self, player: Player) -> None:
        """Assign a player to this seat."""
        if not self.is_available():
            raise ValueError(f"Seat {self.number} is not available")
        self.player = player
        self.status = SeatStatus.OCCUPIED
        self.reserved_for = None
    
    def vacate(self) -> Optional[Player]:
        """Remove player from seat and return the player."""
        player = self.player
        self.player = None
        self.status = SeatStatus.EMPTY
        self.reserved_for = None
        return player
    
    def reserve(self, player_id: str) -> None:
        """Reserve seat for a specific player."""
        if not self.is_available():
            raise ValueError(f"Seat {self.number} is not available for reservation")
        self.status = SeatStatus.RESERVED
        self.reserved_for = player_id

class TableLayout:
    """Manages the physical layout and seating arrangement of a poker table."""
    
    def __init__(self, max_seats: int):
        """Initialize table layout with specified number of seats."""
        if max_seats < 2 or max_seats > 10:
            raise ValueError("Table must have between 2 and 10 seats")
        
        self.max_seats = max_seats
        self.seats: Dict[int, Seat] = {}
        
        # Initialize all seats
        for i in range(1, max_seats + 1):
            self.seats[i] = Seat(number=i)
    
    def get_available_seats(self) -> List[int]:
        """Get list of available seat numbers."""
        return [num for num, seat in self.seats.items() if seat.is_available()]
    
    def get_occupied_seats(self) -> List[int]:
        """Get list of occupied seat numbers."""
        return [num for num, seat in self.seats.items() if seat.status == SeatStatus.OCCUPIED]
    
    def get_players_in_seat_order(self) -> List[Player]:
        """Get all players ordered by their seat numbers."""
        players = []
        for seat_num in sorted(self.seats.keys()):
            seat = self.seats[seat_num]
            if seat.player:
                players.append(seat.player)
        return players
    
    def get_player_seat(self, player_id: str) -> Optional[int]:
        """Get the seat number for a specific player."""
        for seat_num, seat in self.seats.items():
            if seat.player and seat.player.id == player_id:
                return seat_num
        return None
    
    def assign_player_to_seat(self, player: Player, seat_number: int) -> None:
        """Assign a player to a specific seat."""
        if seat_number not in self.seats:
            raise ValueError(f"Invalid seat number: {seat_number}")
        
        # Check if player is already seated elsewhere
        current_seat = self.get_player_seat(player.id)
        if current_seat:
            raise ValueError(f"Player {player.name} is already seated at seat {current_seat}")
        
        self.seats[seat_number].occupy(player)
    
    def remove_player_from_seat(self, seat_number: int) -> Optional[Player]:
        """Remove player from a specific seat."""
        if seat_number not in self.seats:
            raise ValueError(f"Invalid seat number: {seat_number}")
        
        return self.seats[seat_number].vacate()
    
    def assign_random_seat(self, player: Player) -> int:
        """Assign player to a random available seat."""
        available = self.get_available_seats()
        if not available:
            raise ValueError("No available seats")
        
        seat_number = random.choice(available)
        self.assign_player_to_seat(player, seat_number)
        return seat_number
    
    def reserve_seat(self, seat_number: int, player_id: str) -> None:
        """Reserve a seat for a player."""
        if seat_number not in self.seats:
            raise ValueError(f"Invalid seat number: {seat_number}")
        
        self.seats[seat_number].reserve(player_id)

class Table:
    """
    Enhanced table implementation with realistic seating and positioning.
    
    Attributes:
        layout: Physical seating layout
        button_seat: Seat number where the button currently is
        deck: Current deck
        community_cards: Shared community cards
        min_buyin: Minimum buy-in amount
        max_buyin: Maximum buy-in amount
        rules: Game rules configuration
    """
    
    def __init__(
        self,
        max_seats: Optional[int] = None,
        min_buyin: int = 0,
        max_buyin: int = 0,
        deck_type: DeckType = DeckType.STANDARD,
        rules: Optional[GameRules] = None,
        max_players: Optional[int] = None  # Backward compatibility
    ):
        """
        Initialize a new table.
        
        Args:
            max_seats: Maximum number of seats at the table
            min_buyin: Minimum buy-in amount
            max_buyin: Maximum buy-in amount
            deck_type: Type of deck to use (default: STANDARD)
            rules: Game rules configuration (optional)
            max_players: Deprecated alias for max_seats (backward compatibility)
        """
        # Handle backward compatibility
        if max_players is not None and max_seats is None:
            max_seats = max_players
        elif max_seats is None:
            raise ValueError("Either max_seats or max_players must be specified")
        
        if max_players is not None and max_seats != max_players:
            raise ValueError("Cannot specify both max_seats and max_players with different values")
        self.layout = TableLayout(max_seats)
        self.min_buyin = min_buyin
        self.max_buyin = max_buyin
        self.deck_type = deck_type
        self.rules = rules
        
        # Button starts at seat 1 by default
        self.button_seat: int = 1
        
        # Game state
        self.deck = Deck(deck_type=self.deck_type)
        self.discard_pile = Deck()
        self.discard_pile.clear()
        self.community_cards: Dict[str, List[Card]] = {}
    
    @property
    def max_players(self) -> int:
        """Get maximum number of players (seats) at table. Backward compatibility property."""
        return self.layout.max_seats
    
    @property
    def players(self) -> Dict[str, Player]:
        """Get dictionary of all players currently at the table."""
        result = {}
        for seat in self.layout.seats.values():
            if seat.player:
                result[seat.player.id] = seat.player
        return result
    
    def add_player(
        self, 
        player_id: str, 
        name: str, 
        buyin: int, 
        preferred_seat: Optional[int] = None
    ) -> int:
        """
        Add a player to the table.
        
        Args:
            player_id: Unique identifier for player
            name: Display name
            buyin: Initial buy-in amount
            preferred_seat: Specific seat number requested (optional)
            
        Returns:
            Seat number assigned to the player
            
        Raises:
            ValueError: If table is full, buyin invalid, or seat unavailable
        """
        if buyin < self.min_buyin or buyin > self.max_buyin:
            raise ValueError(
                f"Buy-in must be between {self.min_buyin} and {self.max_buyin}"
            )
        
        if not self.layout.get_available_seats():
            raise ValueError("Table is full")
        
        player = Player(id=player_id, name=name, stack=buyin)
        
        if preferred_seat is not None:
            if preferred_seat not in self.layout.seats:
                raise ValueError(f"Invalid seat number: {preferred_seat}")
            if not self.layout.seats[preferred_seat].is_available():
                raise ValueError(f"Seat {preferred_seat} is not available")
            
            self.layout.assign_player_to_seat(player, preferred_seat)
            return preferred_seat
        else:
            return self._assign_next_sequential_seat(player)
    
    def add_player_to_random_seat(self, player_id: str, name: str, buyin: int) -> int:
        """Add player to a random available seat. Convenience method."""
        return self._assign_random_seat_internal(player_id, name, buyin)
    
    def _assign_next_sequential_seat(self, player: Player) -> int:
        """
        Assign player to the next available seat sequentially for backward compatibility.
        This ensures consistent ordering when tests don't specify preferred seats.
        """
        available_seats = sorted(self.layout.get_available_seats())
        if not available_seats:
            raise ValueError("No available seats")
        
        seat_number = available_seats[0]  # Take the lowest numbered available seat
        self.layout.assign_player_to_seat(player, seat_number)
        return seat_number
    
    def _assign_random_seat_internal(self, player_id: str, name: str, buyin: int) -> int:
        """Internal method for truly random seat assignment."""
        if buyin < self.min_buyin or buyin > self.max_buyin:
            raise ValueError(
                f"Buy-in must be between {self.min_buyin} and {self.max_buyin}"
            )
        
        if not self.layout.get_available_seats():
            raise ValueError("Table is full")
        
        player = Player(id=player_id, name=name, stack=buyin)
        return self.layout.assign_random_seat(player)
    
    def remove_player(self, player_id: str) -> None:
        """Remove a player from the table."""
        seat_number = self.layout.get_player_seat(player_id)
        if seat_number:
            self.layout.remove_player_from_seat(seat_number)
    
    def get_available_seats(self) -> List[int]:
        """Get list of available seat numbers."""
        return self.layout.get_available_seats()
    
    def get_occupied_seats(self) -> List[int]:
        """Get list of occupied seat numbers."""
        return self.layout.get_occupied_seats()
    
    def reserve_seat(self, seat_number: int, player_id: str) -> None:
        """Reserve a seat for a specific player."""
        self.layout.reserve_seat(seat_number, player_id)
    
    def move_button(self) -> None:
        """
        Move the dealer button to the next occupied seat clockwise.
        
        The button moves to the next player in seat order, wrapping around
        from the highest seat number to seat 1.
        """
        occupied_seats = sorted(self.layout.get_occupied_seats())
        if len(occupied_seats) <= 1:
            return  # Need at least 2 players to move button
        
        # If button is not on an occupied seat, find the next occupied seat clockwise
        if self.button_seat not in occupied_seats:
            # Find the next occupied seat clockwise from current button position
            all_seats = sorted(self.layout.seats.keys())
            try:
                current_idx = all_seats.index(self.button_seat)
            except ValueError:
                # Invalid button position, default to first occupied seat
                self.button_seat = occupied_seats[0]
                return
            
            # Look for next occupied seat clockwise
            for i in range(1, len(all_seats) + 1):
                next_seat = all_seats[(current_idx + i) % len(all_seats)]
                if next_seat in occupied_seats:
                    self.button_seat = next_seat
                    return
            
            # Fallback (shouldn't happen if there are occupied seats)
            self.button_seat = occupied_seats[0]
            return
        
        # Button is on an occupied seat, move to next occupied seat
        try:
            current_idx = occupied_seats.index(self.button_seat)
        except ValueError:
            # This shouldn't happen given the check above, but handle it
            self.button_seat = occupied_seats[0]
            return
        
        # Move to next occupied seat
        next_idx = (current_idx + 1) % len(occupied_seats)
        self.button_seat = occupied_seats[next_idx]
    
    def get_position_order(self, include_inactive: bool = True) -> List[Player]:
        """
        Get players in action order starting from the button.
        
        Args:
            include_inactive: If True, includes inactive players for position tracking
        
        Returns players in clockwise order starting with the button player,
        with proper position assignments (BTN, SB, BB).
        """
        occupied_seats = sorted(self.layout.get_occupied_seats())
        if not occupied_seats:
            return []
        
        # Find button position in occupied seats
        try:
            button_idx = occupied_seats.index(self.button_seat)
        except ValueError:
            # Button not on occupied seat, default to first player
            button_idx = 0
            self.button_seat = occupied_seats[0]
        
        # Create ordered list starting from button
        ordered_seats = (
            occupied_seats[button_idx:] + 
            occupied_seats[:button_idx]
        )
        
        # Get players in order
        players = []
        for seat_num in ordered_seats:
            seat = self.layout.seats[seat_num]
            if seat.player:
                if include_inactive or seat.player.is_active:
                    players.append(seat.player)
        
        # Assign positions to active players only
        active_players = [p for p in players if p.is_active]
        self._assign_positions(active_players)
        
        return players
    
    def _assign_positions(self, players: List[Player]) -> None:
        """Assign poker positions to players based on button order."""
        num_players = len(players)
        
        if num_players == 0:
            return
        
        # Clear existing positions for all players
        for player in players:
            player.position = None
        
        if num_players == 1:
            players[0].position = PlayerPosition([Position.BUTTON])
        elif num_players == 2:
            # Heads-up: Button/SB and BB
            players[0].position = PlayerPosition([Position.BUTTON, Position.SMALL_BLIND])
            players[1].position = PlayerPosition([Position.BIG_BLIND])
        else:
            # 3+ players: BTN, SB, BB, then others
            players[0].position = PlayerPosition([Position.BUTTON])
            players[1].position = PlayerPosition([Position.SMALL_BLIND])
            players[2].position = PlayerPosition([Position.BIG_BLIND])
    
    def get_player_in_seat(self, seat_number: int) -> Optional[Player]:
        """Get the player sitting in a specific seat."""
        if seat_number not in self.layout.seats:
            return None
        return self.layout.seats[seat_number].player
    
    def get_player_seat_number(self, player_id: str) -> Optional[int]:
        """Get the seat number for a specific player."""
        return self.layout.get_player_seat(player_id)
    
    # Maintain backward compatibility with existing methods
    def get_player_after_big_blind(self) -> Optional[Player]:
        """Return the first active player after the big blind."""
        players = self.get_position_order()
        bb_idx = next((i for i, p in enumerate(players) 
                      if p.position and p.position.has_position(Position.BIG_BLIND)), -1)
        if bb_idx == -1 or len(players) <= bb_idx + 1:
            return None
        return players[bb_idx + 1]
    
    def get_next_active_player(self, start_position: int) -> Optional[Player]:
        """
        Return the next active player from a starting position.
        
        Args:
            start_position: Starting position index (0-based)
            
        Returns:
            Next active player or None if no active players found
        """
        # Get all players (including inactive) for proper position tracking
        all_players = self.get_position_order(include_inactive=True)
        active_players = [p for p in all_players if p.is_active]
        
        if not active_players:
            return None
            
        start_idx = start_position % len(active_players)
        next_idx = (start_idx + 1) % len(active_players)
        
        # Find next active player
        checked = 0
        while not active_players[next_idx].is_active and checked < len(active_players):
            next_idx = (next_idx + 1) % len(active_players)
            checked += 1
            
        if checked >= len(active_players):
            return None  # No active players found
            
        return active_players[next_idx]
    
    def get_next_player_after(self, current_player_id: str) -> Optional[Player]:
        """
        Get the next active player after the specified player, handling inactive players.
        
        Args:
            current_player_id: ID of the current player
            
        Returns:
            Next active player or None if no active players found
        """
        # Get ALL players (including inactive) to find current player's position
        all_players = self.get_position_order(include_inactive=True)
        
        if not all_players:
            return None
        
        # Find current player in the list
        try:
            current_idx = next(i for i, p in enumerate(all_players) if p.id == current_player_id)
        except StopIteration:
            # Current player not found, return first active player
            active_players = [p for p in all_players if p.is_active]
            return active_players[0] if active_players else None
        
        # Find next active player
        next_idx = (current_idx + 1) % len(all_players)
        checked = 0
        
        while checked < len(all_players):
            candidate = all_players[next_idx]
            if candidate.is_active:
                return candidate
            next_idx = (next_idx + 1) % len(all_players)
            checked += 1
            
        return None  # No active players found
    
    def get_active_players_in_order(self) -> List[Player]:
        """
        Get only active players in position order.
        
        Returns:
            List of active players in clockwise order from button
        """
        return self.get_position_order(include_inactive=False)
    
    @property 
    def button_pos(self) -> int:    
        """
        Get button position as 0-based index for backward compatibility.
        
        Returns:
            0-based index of button position in current player order
        """
        players = self.get_position_order()
        if not players:
            return 0
            
        # Find the button player in the position order
        for i, player in enumerate(players):
            if (player.position and 
                player.position.has_position(Position.BUTTON)):
                return i
                
        return 0  # Fallback
    
    def get_bring_in_player(self, bring_in_amount: int) -> Optional[Player]:
        """Return the player required to post the bring-in."""
        active_players = [p for p in self.players.values() if p.is_active]
        if not active_players:
            return None
        
        num_visible = sum(1 for c in active_players[0].hand.get_cards() 
                         if c.visibility == Visibility.FACE_UP)
        bring_in_rule = (CardRule(self.rules.forced_bets.rule) 
                        if self.rules and self.rules.forced_bets.rule 
                        else CardRule.LOW_CARD)
        
        player = BringInDeterminator.determine_first_to_act(
            active_players, num_visible, bring_in_rule, self.rules
        )
        return player or active_players[0]  # Fallback to first active player
    
    def get_player_with_best_hand(self, forced_bets: ForcedBets) -> Optional[Player]:
        """Return the player with the best visible hand based on game rules."""
        logger.debug(f"Evaluating best hand among active players using forced bets: {forced_bets}")
        active_players = [p for p in self.players.values() if p.is_active]
        if not active_players:
            return None

        # Get visible community cards from appropriate subsets
        visible_community = self._get_visible_community_cards_for_betting()

        # Use max face-up count across all players (not just first) since
        # expose actions can result in different face-up counts per player
        max_face_up = max(
            sum(1 for c in p.hand.get_cards() if c.visibility == Visibility.FACE_UP)
            for p in active_players
        )
        if max_face_up == 0 and not visible_community:
            logger.debug("No visible cards, falling back to first active player")
            return active_players[0]

        from generic_poker.game.bringin import BringInDeterminator, CardRule
        bring_in_rule = (CardRule(forced_bets['rule'])
                        if self.rules and forced_bets['rule']
                        else CardRule.LOW_CARD)

        # Determine total visible cards for evaluation
        total_visible = max_face_up + len(visible_community)
        eval_type = BringInDeterminator._get_dynamic_eval_type(
            total_visible, bring_in_rule, forced_bets, self.rules
        )
        logger.debug(f"Evaluating best hand with {max_face_up} player + {len(visible_community)} community visible cards using {eval_type}")

        # Get required hand size for the eval type
        from generic_poker.evaluation.constants import HAND_SIZES
        required_size = HAND_SIZES.get(eval_type.value, 5)

        def best_n_cards(cards, n):
            """Find the best n-card subset from cards for the eval type."""
            if len(cards) <= n:
                return cards
            best = None
            for combo in itertools.combinations(cards, n):
                combo_list = list(combo)
                if best is None:
                    best = combo_list
                elif evaluator.compare_hands(combo_list, best, eval_type) > 0:
                    best = combo_list
            return best or cards[:n]

        best_player = None
        best_hand = None

        for player in active_players:
            player_visible = [c for c in player.hand.get_cards()
                              if c.visibility == Visibility.FACE_UP]
            all_visible = player_visible + visible_community
            # Skip players with fewer visible cards than the evaluator requires
            if len(all_visible) < required_size:
                continue
            try:
                player_hand = best_n_cards(all_visible, required_size)
                if best_hand is None:
                    best_hand = player_hand
                    best_player = player
                elif evaluator.compare_hands(player_hand, best_hand, eval_type) > 0:
                    best_hand = player_hand
                    best_player = player
            except (ValueError, KeyError) as e:
                # Skip players whose hands can't be evaluated (e.g., joker in lookup table)
                logger.debug(f"Skipping {player.name} in best hand eval: {e}")
                continue

        # Fallback to first active player if no one could be evaluated
        if best_player is None:
            best_player = active_players[0]

        logger.debug(f"Best hand player: {best_player.name} with cards {best_hand}")
        return best_player
    
    def _get_visible_community_cards_for_betting(self) -> List[Card]:
        """
        Get visible community cards that should be used for betting order evaluation.
        
        This method determines which community card subsets to include based on the
        showdown configuration. If the showdown specifies a community_subset, only
        cards from that subset are used. Otherwise, all visible community cards are used.
        """
        # Check if we have showdown rules that specify community subsets
        if (self.rules and 
            hasattr(self.rules, 'showdown') and 
            self.rules.showdown and 
            hasattr(self.rules.showdown, 'best_hand') and
            self.rules.showdown.best_hand):
            
            # Look for community_subset specification in showdown rules
            for hand_config in self.rules.showdown.best_hand:
                if isinstance(hand_config, dict) and 'community_subset' in hand_config:
                    subset_name = hand_config['community_subset']
                    if subset_name in self.community_cards:
                        visible_cards = [c for c in self.community_cards[subset_name] 
                                       if c.visibility == Visibility.FACE_UP]
                        logger.debug(f"Using community subset '{subset_name}' for betting order: {len(visible_cards)} cards")
                        return visible_cards
        
        # Fallback: use all visible community cards
        visible_community = []
        for subset_cards in self.community_cards.values():
            visible_community.extend([c for c in subset_cards if c.visibility == Visibility.FACE_UP])
        
        logger.debug(f"Using all visible community cards for betting order: {len(visible_community)} cards")
        return visible_community
    
    def get_active_players(self) -> List[Player]:
        """Get list of all active players."""
        return [p for p in self.players.values() if p.is_active]
    
    def get_player_to_act(self, round_start: bool = False) -> Optional[Player]:
        """
        Get the next player to act based on position order.
        
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
                return positions[0]  # Button/SB acts first preflop
            else:
                return positions[1]  # BB acts first postflop
        
        # For 3+ players
        if round_start:
            if len(positions) <= 3:
                return positions[0]  # BTN acts first in 3-player
            else:
                return positions[3]  # UTG (after BB) acts first in larger games
        else:
            return positions[1]  # SB acts first postflop
    
    # Game state methods (unchanged from original)
    def deal_hole_cards(self, num_cards: int, face_up: bool = False, subset: str = "default") -> Dict[str, List[Card]]:
        """Deal hole cards to all active players."""
        active_players = [p for p in self.players.values() if p.is_active]
        cards_dealt = {player.id: [] for player in active_players}
        
        for _ in range(num_cards):
            for player in active_players:
                card = self.deck.deal_card(face_up=face_up)
                if card:
                    logger.info(f"  Dealt {card} to player {player.name} in subset '{subset}'")
                    player.hand.add_card(card)
                    cards_dealt[player.id].append(card)
                    if subset and subset != "default":
                        player.hand.add_to_subset(card, subset)
        
        return cards_dealt
    
    def deal_card_to_player(self, player_id: str, face_up: bool = False, subset: str = "default") -> Optional[Card]:
        """Deal a single card to a specific player."""
        player = self.players.get(player_id)
        if not player:
            logger.warning(f"Player {player_id} not found")
            return None
        
        card = self.deck.deal_card(face_up=face_up)
        if card:
            player.hand.add_card(card)
            if subset and subset != "default":
                player.hand.add_to_subset(card, subset)
            logger.debug(f"Dealt {card} to {player.name} ({'face up' if face_up else 'face down'})")
            return card
        else:
            logger.warning("No cards left in deck")
            return None
    
    def deal_community_cards(self, num_cards: int, subsets: List[str] = ["default"], face_up: bool = True) -> List[Card]:
        """Deal cards to community card areas."""
        cards_dealt = []
        for _ in range(num_cards):
            card = self.deck.deal_card(face_up=face_up)
            if card:
                cards_dealt.append(card)
                for subset in subsets:
                    if subset not in self.community_cards:
                        self.community_cards[subset] = []
                    self.community_cards[subset].append(card)
                    logger.debug(f"Dealt {card} to community subset '{subset}'")
        return cards_dealt
    
    def expose_community_cards(self, subset: str = "default", indices: Optional[List[int]] = None) -> None:
        """Flip specified community cards face-up in a subset."""
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
        """Get the number of community cards in a specific subset."""
        return len(self.community_cards.get(subset, []))
    
    def clear_hands(self) -> None:
        """Clear all player hands, community cards, and reset the deck."""
        for player in self.players.values():
            player.hand.clear()
            player.is_active = True  # Reset fold status for new hand
        self.community_cards.clear()
        self.discard_pile.clear()
        self.deck = Deck(deck_type=self.deck_type)