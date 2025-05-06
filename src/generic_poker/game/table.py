"""Table implementation managing game state."""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from generic_poker.core.card import Card, Visibility
from generic_poker.core.deck import Deck, DeckType
from generic_poker.core.hand import PlayerHand
from generic_poker.config.loader import GameRules
from generic_poker.evaluation.evaluator import EvaluationType, evaluator
from generic_poker.evaluation.cardrule import CardRule
from generic_poker.game.bringin import BringInDeterminator
from generic_poker.game.player import Player, PlayerPosition, Position

logger = logging.getLogger(__name__)
   
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
        rules: Game rules configuration
    """
    
    def __init__(
        self,
        max_players: int,
        min_buyin: int,
        max_buyin: int,
        deck_type: DeckType = DeckType.STANDARD,
        rules: Optional[GameRules] = None
    ):
        """
        Initialize a new table.
        
        Args:
            max_players: Maximum number of players allowed
            min_buyin: Minimum buy-in amount
            max_buyin: Maximum buy-in amount
            deck_type: Type of deck to use (default: STANDARD)
            rules: Game rules configuration (optional)
        """
        self.max_players = max_players
        self.min_buyin = min_buyin
        self.max_buyin = max_buyin
        self.deck_type = deck_type  # Store the deck type
        self.rules = rules  # Store the rules
  
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
        
    def get_player_after_big_blind(self) -> Optional[Player]:
        """Return the first active player after the big blind."""
        players = self.get_position_order()
        bb_idx = next((i for i, p in enumerate(players) if p.position and p.position.has_position(Position.BIG_BLIND)), -1)
        if bb_idx == -1:
            return self.get_next_active_player(self.button_pos)  # Fallback
        next_idx = (bb_idx + 1) % len(players)
        while not players[next_idx].is_active:
            next_idx = (next_idx + 1) % len(players)
            if next_idx == bb_idx:  # Full circle
                return None
        return players[next_idx]

    def get_bring_in_player(self, bring_in_amount: int) -> Optional[Player]:
        """Return the player required to post the bring-in."""
        active_players = [p for p in self.players.values() if p.is_active]
        if not active_players:
            return None
        num_visible = sum(1 for c in active_players[0].hand.get_cards() if c.visibility == Visibility.FACE_UP)
        bring_in_rule = CardRule(self.rules.forced_bets.rule) if self.rules and self.rules.forced_bets.rule else CardRule.LOW_CARD
        player = BringInDeterminator.determine_first_to_act(active_players, num_visible, bring_in_rule, self.rules)
        if player is None:
            logger.debug("No bring-in player determined, falling back to first active player")
            return active_players[0]  # Fallback to first active player        
        return player
    
    def get_player_with_best_hand(self) -> Optional[Player]:
        """Return the player with the best visible hand based on game rules."""
        active_players = [p for p in self.players.values() if p.is_active]
        if not active_players:
            return None
        
        # Determine the number of visible cards (assuming all players have the same number)
        num_visible = sum(1 for c in active_players[0].hand.get_cards() if c.visibility == Visibility.FACE_UP)
        if num_visible == 0:
            logger.debug("No visible cards, falling back to first active player")
            return active_players[0]  # Fallback if no visible cards yet
        
        # Get the appropriate evaluation type based on the number of visible cards and rules
        from generic_poker.game.bringin import BringInDeterminator, CardRule
        bring_in_rule = CardRule(self.rules.forced_bets.rule) if self.rules and self.rules.forced_bets.rule else CardRule.LOW_CARD
        eval_type = BringInDeterminator._get_dynamic_eval_type(num_visible, bring_in_rule, self.rules)
        logger.debug(f"Evaluating best hand with {num_visible} visible cards using {eval_type}")

        # Compare visible hands to find the best player
        from generic_poker.evaluation.evaluator import evaluator
        best_player = active_players[0]
        best_hand = [c for c in best_player.hand.get_cards() if c.visibility == Visibility.FACE_UP][:num_visible]

        logger.debug(f"   Initial best hand: {best_hand}")
        for player in active_players[1:]:
            visible_cards = [c for c in player.hand.get_cards() if c.visibility == Visibility.FACE_UP][:num_visible]
            logger.debug(f"      comparing to: {visible_cards}")
            if evaluator.compare_hands(visible_cards, best_hand, eval_type) > 0:
                best_hand = visible_cards
                logger.debug(f"      updating best hand to: {best_hand}")
                best_player = player
        
        logger.debug(f"Best hand player: {best_player.name} with cards {best_hand}")
        return best_player
    
    def get_next_active_player(self, start_position: int) -> Optional[Player]:
        """Return the next active player from a starting position."""
        players = self.get_position_order()
        start_idx = start_position % len(players)
        next_idx = (start_idx + 1) % len(players)
        while not players[next_idx].is_active:
            next_idx = (next_idx + 1) % len(players)
            if next_idx == start_idx:  # Full circle
                return None
        return players[next_idx]    

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

    def deal_hole_cards(self, num_cards: int, face_up: bool = False, subset: str = "default") -> Dict[str, List[Card]]:
        """
        Deal hole cards to all active players and assign them to a specified subset.

        Args:
            num_cards: Number of cards to deal to each player
            face_up: Whether to deal the cards face up (default: False)
            subset: Name of the subset to assign the cards to (default: "default")
            
        Returns:
            Dictionary mapping player IDs to lists of cards dealt to that player
        """
        active_players = [p for p in self.players.values() if p.is_active]
        cards_dealt = {player.id: [] for player in active_players}
        
        for _ in range(num_cards):
            for player in active_players:
                card = self.deck.deal_card(face_up=face_up)  # Pass face_up to Deck
                if card:
                    logger.info(f"  Dealt {card} to player {player.name} in subset '{subset}'")
                    player.hand.add_card(card)  # Add to the hand's card list
                    cards_dealt[player.id].append(card)  # Track the card dealt
                    if subset and subset != "default":  # Only assign to subset if specified and not "default"
                        player.hand.add_to_subset(card, subset)
        
        return cards_dealt  
                    
    def deal_card_to_player(self, player_id: str, face_up: bool = False, subset: str = "default") -> Optional[Card]:
        """
        Deal a single card to a specific player.
        
        Args:
            player_id: ID of the player to deal to
            face_up: Whether to deal the card face up
            subset: Name of the subset to assign the card to
            
        Returns:
            The card that was dealt, or None if no cards left or player not found
        """
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
        """
        Deal cards to community card areas.
        
        Args:
            num_cards: Number of cards to deal
            subsets: List of subsets to assign the cards to
            face_up: Whether to deal the cards face up
            
        Returns:
            List of cards that were dealt
        """
        cards_dealt = []
        for _ in range(num_cards):
            card = self.deck.deal_card(face_up=face_up)
            if card:
                cards_dealt.append(card)
                # Add to all specified subsets
                for subset in subsets:
                    if subset not in self.community_cards:
                        self.community_cards[subset] = []
                    self.community_cards[subset].append(card)
                    logger.debug(f"Dealt {card} to community subset '{subset}'")
        return cards_dealt
        
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
       