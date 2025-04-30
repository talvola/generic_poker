"""Core game implementation controlling game flow."""
import logging
import json
import itertools
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Set

from generic_poker.config.loader import GameRules, GameActionType
from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.game.table import Table, Player, Position
from generic_poker.game.betting import (
    BettingManager, LimitBettingManager, create_betting_manager,
    BettingStructure, BetType, PlayerBet
)
from generic_poker.game.bringin import BringInDeterminator
from generic_poker.core.card import Card, Visibility, WildType, Rank, Suit
from generic_poker.core.deck import Deck, DeckType
from generic_poker.evaluation.evaluator import EvaluationType, evaluator

from generic_poker.evaluation.constants import HAND_SIZES, BASE_RANKS
from generic_poker.evaluation.cardrule import CardRule

from generic_poker.game.action_result import ActionResult
from generic_poker.game.player_action_handler import PlayerActionHandler

from generic_poker.evaluation.evaluator import evaluator

logger = logging.getLogger(__name__)
    
@dataclass
class HandResult:
    """Information about a player's hand and its evaluation."""
    player_id: str
    cards: List[Card]  # Cards in the hand
    hand_name: str  # e.g., "Full House"
    hand_description: str  # e.g., "Full House, Aces over Kings"
    evaluation_type: str  # "high", "low", etc.
    hand_type: str = "Hand"  # from game config showdown
    community_cards: List[Card] = field(default_factory=list)  # Community cards if applicable
    used_hole_cards: List[Card] = field(default_factory=list)  # Cards used in the hand
    rank: int = 0  
    ordered_rank: int = 0  
    classifications: Dict[str, str] = field(default_factory=dict)  # New field for classifications
    
    def __str__(self) -> str:
        """String representation of the hand result."""
        cards_str = ", ".join(str(card) for card in self.cards)
        # Append classification if present
        classification_str = ""
        if "face_butt" in self.classifications:
            classification_str = f" ({self.classifications['face_butt'].capitalize()})"        
        return f"Player {self.player_id}: {self.hand_description}{classification_str} ({cards_str})"
        
    def to_json(self) -> dict:
        """Convert to JSON-compatible dictionary."""
        return {
            "player_id": self.player_id,
            "cards": [str(card) for card in self.cards],
            "hand_name": self.hand_name,
            "hand_description": self.hand_description,
            "evaluation_type": self.evaluation_type,
            "hand_type": self.hand_type,
            "community_cards": [str(card) for card in self.community_cards],
            "used_hole_cards": [str(card) for card in self.used_hole_cards],  # Added for Omaha Hi/Hi
            "rank": self.rank,
            "ordered_rank": self.ordered_rank,
            "classifications": self.classifications  # Include classifications
        }
    
@dataclass
class PotResult:
    """Information about a pot and its winner(s)."""
    amount: int  # Amount in the pot
    winners: List[str]  # List of player IDs who won this pot
    pot_type: str = "main"  # "main" or "side"
    hand_type: str = "Hand"  # from game config showdown
    side_pot_index: Optional[int] = None  # Index of side pot if applicable
    eligible_players: Set[str] = None  # Players who could win this pot
    reason: Optional[str] = None  # Reason for pot award (e.g., "Best high hand")
    best_hands: List[HandResult] = field(default_factory=list)  # Best hands for this pot's hand_type
    declarations: Dict[str, str] = field(default_factory=dict)  # Player ID -> declaration (e.g., "high")
    split: bool = False  # Whether the pot was split (multiple winners)

    def __post_init__(self):
        # Ensure eligible_players is a set
        if self.eligible_players is None:
            self.eligible_players = set()
        # Ensure winners is a list
        if self.winners is None:
            self.winners = []
        # Set split based on number of winners
        self.split = len(self.winners) > 1
        # Ensure best_hands is a list
        if self.best_hands is None:
            self.best_hands = []
        # Ensure declarations is a dict
        if self.declarations is None:
            self.declarations = {}
        
    @property
    def amount_per_player(self) -> int:
        """Amount each winner receives from the pot."""
        if not self.winners:
            return 0
        return self.amount // len(self.winners)
    
    def __str__(self) -> str:
        """String representation of the pot result."""
        pot_name = "Main pot" if self.pot_type == "main" else f"Side pot {self.side_pot_index + 1}"
        winners_str = ", ".join(self.winners)
        reason_str = f" ({self.reason})" if self.reason else ""
        if self.split:
            return f"{pot_name}: ${self.amount} - Split between {winners_str} (${self.amount_per_player} each){reason_str}"
        else:
            return f"{pot_name}: ${self.amount} - Won by {winners_str}{reason_str}"

    def to_json(self) -> dict:
        """Convert to JSON-compatible dictionary."""
        return {
            "amount": self.amount,
            "winners": self.winners,
            "split": self.split,
            "pot_type": self.pot_type,
            "hand_type": self.hand_type,
            "side_pot_index": self.side_pot_index,
            "eligible_players": list(self.eligible_players),
            "amount_per_player": self.amount_per_player,
            "reason": self.reason,
            "best_hands": [hand.to_json() for hand in self.best_hands],
            "declarations": self.declarations
        }

@dataclass
class GameResult:
    """Complete results of a poker hand."""
    pots: List[PotResult]  # Results for each pot
    hands: Dict[str, List[HandResult]]  # Hand results by player ID, now a list
    winning_hands: List[HandResult]  # List of winning hands (may be multiple)
    is_complete: bool = True  # Whether the hand played to completion
    
    @property
    def total_pot(self) -> int:
        """Total amount in all pots."""
        return sum(pot.amount for pot in self.pots)
    
    @property
    def winners(self) -> List[str]:
        """List of all unique winner IDs."""
        all_winners = [winner for pot in self.pots for winner in pot.winners]
        return list(set(all_winners))
    
    def __str__(self) -> str:
        """String representation of the game result."""
        lines = [f"Game Result (Complete: {self.is_complete})"]
        lines.append(f"Total pot: ${self.total_pot}")

        # Group pot results by type (high/low)
        pot_groups = {}
        for pot in self.pots:
            pot_type = getattr(pot, 'hand_type', 'Unspecified')
            if pot_type not in pot_groups:
                pot_groups[pot_type] = []
            pot_groups[pot_type].append(pot)

        # Display pot results by group
        lines.append("\nPot Results:")
        for pot_type, pots in pot_groups.items():
            lines.append(f"\n{pot_type} Pot Division:")
            for pot in pots:
                lines.append(f"- {pot}")

        # Create a mapping of hand type to all hands of that type
        all_hands_by_type = {}
        for player_id, player_hands in self.hands.items():
            # Handle both list and dict cases for player_hands
            if isinstance(player_hands, dict):
                hands_iter = player_hands.values()
            elif isinstance(player_hands, list):
                hands_iter = player_hands
            else:
                raise ValueError(f"Unexpected type for player_hands: {type(player_hands)}")

            for hand in hands_iter:
                hand_type = getattr(hand, 'hand_type', 'Unspecified')
                if hand_type not in all_hands_by_type:
                    all_hands_by_type[hand_type] = []
                all_hands_by_type[hand_type].append(hand)

        # [Rest of the method remains unchanged]
        # Create a mapping of hand type to winning hands of that type
        winning_hands_by_type = {}
        for hand in self.winning_hands:
            hand_type = getattr(hand, 'hand_type', 'Unspecified')
            if hand_type not in winning_hands_by_type:
                winning_hands_by_type[hand_type] = []
            winning_hands_by_type[hand_type].append(hand)

        # Get winning hand player IDs by type
        winning_players_by_type = {}
        for hand_type, hands in winning_hands_by_type.items():
            winning_players_by_type[hand_type] = {hand.player_id for hand in hands}

        # Display each hand type section
        for hand_type, all_hands in all_hands_by_type.items():
            lines.append(f"\n{hand_type}:")

            # Winning hands for this type
            winning_hands = winning_hands_by_type.get(hand_type, [])
            if winning_hands:
                lines.append("\tWinning Hands:")
                for hand in winning_hands:
                    lines.append(f"\t\t- {hand}")

            # Losing hands for this type
            winning_ids = winning_players_by_type.get(hand_type, set())
            losing_hands = [hand for hand in all_hands if hand.player_id not in winning_ids]
            if losing_hands:
                lines.append("\tLosing Hands:")
                for hand in losing_hands:
                    lines.append(f"\t\t- {hand}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Convert to JSON string."""
        result_dict = {
            "is_complete": self.is_complete,
            "total_pot": self.total_pot,
            "pots": [pot.to_json() for pot in self.pots],
            "hands": {pid: [hand.to_json() for hand in hands] for pid, hands in self.hands.items()},
            "winning_hands": [hand.to_json() for hand in self.winning_hands]
        }
        return json.dumps(result_dict, indent=2)        
    
class Game:
    """
    Controls game flow and state.
    
    Attributes:
        rules: Rules for the poker variant
        table: Table instance managing players/cards
        betting: Betting manager for current game
        state: Current game state
        current_step: Index of current step in gameplay sequence
    """
    
    def __init__(
        self,
        rules: GameRules,
        structure: BettingStructure,
        # For Limit games
        small_bet: Optional[int] = None,
        big_bet: Optional[int] = None,
        # For No-Limit/Pot-Limit games
        small_blind: Optional[int] = None,
        big_blind: Optional[int] = None,    
        mandatory_straddle: Optional[int] = None,
        # For games with Antes:
        ante: Optional[int] = None,
        # For Stud games:
        bring_in: Optional[int] = None,
        # Common parameters
        min_buyin: int = 100,
        max_buyin: int = 2000,
        auto_progress: bool = True
    ):
        """
        Initialize new game.
        
        Args:
            rules: Game rules configuration
            structure: Betting structure to use
            small_bet: Small bet/min bet size
            big_bet: Big bet size (required for limit games)
            min_buyin: Minimum buy-in amount
            max_buyin: Maximum buy-in amount
        """
        if structure not in rules.betting_structures:
            raise ValueError(
                f"Betting structure {structure} not allowed for {rules.game}"
            )
            
        # Convert rules.deck_type string to DeckType enum
        try:
            deck_type = DeckType(rules.deck_type)
        except ValueError:
            deck_type = DeckType.STANDARD  # Default to STANDARD if invalid

        self.rules = rules
        self.table = Table(
            max_players=rules.max_players,
            min_buyin=min_buyin,
            max_buyin=max_buyin,
            deck_type=deck_type,
            rules=rules  # Pass rules to Table
        )

        # Betting rules
        self.betting_structure = structure
        if structure == BettingStructure.LIMIT:
            if small_bet is None or big_bet is None:
                raise ValueError("Limit games require small_bet and big_bet")
            self.small_bet = small_bet
            self.big_bet = big_bet
            # small blind in Limit games is half the small bet
            self.small_blind = small_bet // 2
            self.big_blind = small_bet
            self.betting = create_betting_manager(structure, self.small_bet, self.big_bet, self.table)
        else:  # NO_LIMIT or POT_LIMIT
            if small_blind is None or big_blind is None:
                raise ValueError("No-Limit/Pot-Limit games require small_blind and big_blind")
            self.small_blind = small_blind
            self.big_blind = big_blind
            # the minimum bet is always the big blind in No-Limit/Pot-Limit games
            self.small_bet = big_blind
            self.big_bet = big_blind
            self.betting = create_betting_manager(structure, self.small_bet, self.big_bet, self.table)   
        self.bring_in = bring_in            
        self.ante = ante            

        self.auto_progress = auto_progress  # Store the setting     
        
        self.action_handler = PlayerActionHandler(self)

        self.state = GameState.WAITING
        self.current_step = -1  # Not started
        self.current_player: Optional[Player] = None  # player to act
    
        self.last_hand_result = None  # Store the last hand result here

        self.bring_in_player_id = None

        self.declarations: Dict[str, Dict[int, str]] = {}
    

    def get_game_description(self) -> str:
        """
        Get a human-friendly description of the game.
        
        Returns:
            A formatted string describing the game as it would appear in a casino.
            
        Example: "$10/$20 Limit Texas Hold'em"
        """
       
        # Determine betting structure name
        from generic_poker.game.betting import (
            LimitBettingManager, NoLimitBettingManager, PotLimitBettingManager
        )
        
        betting_structure = "Unknown"
        if isinstance(self.betting, LimitBettingManager):
            betting_structure = "Limit"
        elif isinstance(self.betting, NoLimitBettingManager):
            betting_structure = "No Limit"
        elif isinstance(self.betting, PotLimitBettingManager):
            betting_structure = "Pot Limit"
            
        if isinstance(self.betting, LimitBettingManager):
            # For Limit, show bet sizes
            return f"${self.small_bet}/${self.big_bet} {betting_structure} {self.rules.game}"
        else:
            # For No-Limit/Pot-Limit, show blind sizes
            return f"${self.small_blind}/${self.big_blind} {betting_structure} {self.rules.game}"

    def get_table_info(self) -> Dict[str, Any]:
        """
        Get detailed information about the current table.
        
        Returns:
            Dictionary with table information including:
            - game_description: Formatted game description
            - player_count: Number of players at the table
            - active_players: Number of players in the current hand
            - min_buyin: Minimum buy-in amount
            - max_buyin: Maximum buy-in amount
            - avg_stack: Average stack size
            - pot_size: Current pot size
        """
        active_count = sum(1 for p in self.table.players.values() if p.is_active)
        total_chips = sum(p.stack for p in self.table.players.values())
        avg_stack = total_chips / len(self.table.players) if self.table.players else 0
        
        return {
            "game_description": self.get_game_description(),
            "player_count": len(self.table.players),
            "active_players": active_count,
            "min_buyin": self.table.min_buyin,
            "max_buyin": self.table.max_buyin,
            "avg_stack": avg_stack,
            "pot_size": self.betting.get_total_pot() if hasattr(self.betting, "get_total_pot") else 0
        }

    def __str__(self) -> str:
        """String representation of the game."""
        return self.get_game_description()
    
    def add_player(self, player_id: str, name: str, buyin: int) -> None:
        """Add a player to the game."""
        self.table.add_player(player_id, name, buyin)
        
        # Check if we can start
        if len(self.table.players) >= self.rules.min_players:
            self.state = GameState.DEALING
            
    def remove_player(self, player_id: str) -> None:
        """Remove a player from the game."""
        self.table.remove_player(player_id)
        
        # Check if we need to stop
        if len(self.table.players) < self.rules.min_players:
            self.state = GameState.WAITING
            
    def get_valid_actions(self, player_id: str) -> List[Tuple[PlayerAction, Optional[int], Optional[int]]]:
        """Wrapper for PlayerActionHandler."""
        return self.action_handler.get_valid_actions(player_id)
                
    def start_hand(self) -> None:
        """
        Start a new hand.
        
        Raises:
            ValueError: If game cannot start
        """
        logger.info("Starting new hand")
        if len(self.table.players) < self.rules.min_players:
            logger.error("Cannot start hand - not enough players")
            raise ValueError("Not enough players to start")
            
        # Reset state
        self.table.clear_hands()
        self.betting.new_hand()

        self.current_step = 0
        self.state = GameState.BETTING 
        self.current_player = None

        logger.info("Hand started - moving to first step")
        
        # Execute first step - should this be conditioned on auto progress setting?
        self.process_current_step() 

    def _all_players_have_acted(self, players: List[Player]) -> bool:
        """Check if all players have acted in the current round."""
        # In a discard round, we can't use the betting.round_complete method
        # We'll consider the round complete when we've cycled through all active players
        # This is simplified - in a real implementation you might want to track this state
        return True        

        
    def _is_first_betting_round(self):
        for i, step in enumerate(self.rules.gameplay):
            if step.action_type == GameActionType.BET and step.action_config.get("type") == "small":
                return i == self.current_step
            elif step.action_type == GameActionType.GROUPED:
                for j, subaction in enumerate(step.action_config):
                    if "bet" in subaction and subaction["bet"].get("type") == "small":
                        return i == self.current_step and self.action_handler.current_substep == j
        return False
        
         
    def player_action(self, player_id: str, action: PlayerAction, amount: int = 0, cards: Optional[List[Card]] = None, declaration_data: Optional[List[Dict]] = None) -> ActionResult:
        """Delegate to PlayerActionHandler and handle step advancement."""
        result = self.action_handler.handle_action(player_id, action, amount, cards, declaration_data)
        if result.advance_step and self.auto_progress:
            self._next_step()
            # Clean up temporary attributes
            for attr in ["current_discard_config", "current_draw_config", "current_separate_config", 
                         "current_expose_config", "current_pass_config", "current_declare_config"]:
                if hasattr(self, attr):
                    delattr(self, attr)
        return result
            
    def process_current_step(self) -> None:
            """
            Process the current step in the gameplay sequence.
            Returns when player input is needed or step is complete.
            """
            if self.current_step >= len(self.rules.gameplay):
                logger.info("All steps complete - game finished")
                self.state = GameState.COMPLETE
                return
                
            step = self.rules.gameplay[self.current_step]
            logger.info(f"Processing step {self.current_step}: {step.name} {step.action_type}")
                           
            if step.action_type == GameActionType.GROUPED:
                self.action_handler.setup_grouped_step(step.action_config)
                first_subaction = step.action_config[0]

                # Set state based on the first sub-action
                if "bet" in first_subaction:
                    self.state = GameState.BETTING
                    bet_config = first_subaction["bet"]
                    if bet_config.get("type") in ["antes", "blinds", "bring-in"]:
                        self.handle_forced_bets(bet_config["type"])
                        if self.auto_progress:
                            self._next_step()
                    else:
                        self.betting.new_round(self._is_first_betting_round())
                        self.current_player = self.next_player(round_start=True)
                elif "discard" in first_subaction:
                    self.state = GameState.DRAWING
                    self.action_handler.setup_discard_round(first_subaction["discard"])
                    self.current_player = self.next_player(round_start=True)
                elif "draw" in first_subaction:
                    self.state = GameState.DRAWING
                    self.action_handler.setup_draw_round(first_subaction["draw"])
                    self.current_player = self.next_player(round_start=True)
                elif "separate" in first_subaction:
                    self.state = GameState.DRAWING
                    self.action_handler.setup_separate_round(first_subaction["separate"])                    
                    self.current_player = self.next_player(round_start=True)
                elif "expose" in first_subaction:
                    self.state = GameState.DRAWING
                    self.action_handler.setup_expose_round(first_subaction["expose"])                    
                    self.current_player = self.next_player(round_start=True)
                elif "pass" in first_subaction:
                    self.state = GameState.DRAWING
                    self.action_handler.setup_pass_round(first_subaction["pass"])                    
                    self.current_player = self.next_player(round_start=True)
                elif "declare" in first_subaction:
                    self.state = GameState.DRAWING
                    self.action_handler.setup_declare_round(first_subaction["declare"])
                    self.current_player = self.next_player(round_start=True)

            elif step.action_type == GameActionType.BET:
                if step.action_config["type"] in ["antes", "blinds", "bring-in"]:
                    self.handle_forced_bets(step.action_config["type"])  # Use new method with bet_type
                    self.state = GameState.BETTING  # Set here for all forced bets
                    if self.auto_progress:
                        self._next_step()
                else:
                    logger.info(f"Starting betting round: {step.name}")
                    self.state = GameState.BETTING
                    first_bet_step = None
                    for i, s in enumerate(self.rules.gameplay):
                        if s.action_type == GameActionType.BET and s.action_config.get("type") == "small":
                            first_bet_step = i
                            break
                        elif s.action_type == GameActionType.GROUPED:
                            for subaction in s.action_config:
                                if "bet" in subaction and subaction["bet"].get("type") == "small":
                                    first_bet_step = i
                                    break
                            if first_bet_step is not None:
                                break
                    preserve_bet = (first_bet_step == self.current_step)
                    self.betting.new_round(preserve_bet)
                    self.current_player = self.next_player(round_start=True)

            elif step.action_type == GameActionType.DEAL:
                logger.debug(f"Handling deal action: {step.action_config}")
                self.state = GameState.DEALING
                self._handle_deal(step.action_config)
                if self.auto_progress:  
                    self._next_step()

            elif step.action_type == GameActionType.REMOVE:
                logger.debug(f"Handling deal action: {step.action_config}")
                self.state = GameState.DEALING
                self._handle_remove(step.action_config)
                if self.auto_progress:  
                    self._next_step()                    

            # treating discard and draw (which is discard/draw) separately for now,
            # but could be refactored to be the same thing
            elif step.action_type == GameActionType.DISCARD:
                self.state = GameState.DRAWING
                self.action_handler.setup_discard_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
                self.action_handler.first_player_in_round = self.current_player.id
                
            elif step.action_type == GameActionType.DRAW:
                self.state = GameState.DRAWING
                self.action_handler.setup_draw_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
                self.action_handler.first_player_in_round = self.current_player.id

            elif step.action_type == GameActionType.SEPARATE:
                self.state = GameState.DRAWING
                self.action_handler.setup_separate_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
                self.action_handler.first_player_in_round = self.current_player.id

            elif step.action_type == GameActionType.EXPOSE:
                self.state = GameState.DRAWING
                self.action_handler.setup_expose_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
                self.action_handler.first_player_in_round = self.current_player.id

            elif step.action_type == GameActionType.PASS:
                self.state = GameState.DRAWING
                self.action_handler.setup_pass_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
                self.action_handler.first_player_in_round = self.current_player.id

            elif step.action_type == GameActionType.DECLARE:
                self.state = GameState.DRAWING
                self.action_handler.setup_declare_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
                self.action_handler.first_player_in_round = self.current_player.id                

            elif step.action_type == GameActionType.SHOWDOWN:
                logger.info("Moving to showdown")
                self.state = GameState.SHOWDOWN
                self._handle_showdown()

    def _handle_deal(self, config: Dict[str, Any]) -> None:
        """Handle a dealing action."""
        location = config["location"]
        for card_config in config["cards"]:
            num_cards = card_config["number"]
            state = card_config["state"]
            subset = card_config.get("subset", "default")  # Default to "default" if not specified
            hole_subset = card_config.get("hole_subset", "default")  # Default to "default" if not specified
            face_up = state == "face up"
            
            if location == "player":
                logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to each player ({state})")
                self.table.deal_hole_cards(num_cards, subset=hole_subset, face_up=face_up)
            else:  # community
                logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to community subset '{subset}' ({state})")
                self.table.deal_community_cards(num_cards, subset=subset, face_up=face_up)               
                
    def _handle_remove(self, config: Dict[str, Any]) -> None:
        """Handle a remove action by removing board subsets based on river card ranks."""
        # Validate the action type
        if config.get("type") != "subset":
            logger.warning(f"Unsupported remove type: {config.get('type')}")
            return

        # Get the criteria and subsets from the config
        criteria = config.get("criteria")
        subsets = config.get("subsets", ["Board 1", "Board 2", "Board 3"])  # Default if not specified

        if not subsets:
            logger.warning("No subsets specified for removal")
            return

        # For now, support only the tournament variation criteria
        if criteria not in ["Lowest River Card", "lowest_river_card_unless_all_same"]:
            logger.warning(f"Unsupported remove criteria: {criteria}")
            return

        # Collect river cards from each subset
        river_cards = {}
        for subset in subsets:
            if subset in self.table.community_cards and len(self.table.community_cards[subset]) >= 5:
                river_card = self.table.community_cards[subset][-1]  # Last card is the river
                river_cards[subset] = river_card.rank
            else:
                logger.warning(f"Subset {subset} does not have enough cards for river removal")
                continue

        if not river_cards:
            logger.warning("No valid subsets available for removal")
            return

        # Get all ranks
        ranks = list(river_cards.values())
        # Tournament rule: if all river cards have the same rank, keep all boards
        if all(rank == ranks[0] for rank in ranks):
            logger.info("All river cards have the same rank; no boards removed")
            return

        # Use BASE_RANKS to determine the actual rank position (lower index = higher rank)
        # Convert Enum values to their string representation for comparison
        rank_positions = {subset: BASE_RANKS.index(rank.value) for subset, rank in river_cards.items()}

        # Find the lowest rank (highest index in BASE_RANKS)
        max_position = max(rank_positions.values())
        # Identify subsets to remove (those with the lowest rank)
        to_remove = [subset for subset, position in rank_positions.items() if position == max_position]

        # Remove the identified subsets
        for subset in to_remove:
            if subset in self.table.community_cards:
                del self.table.community_cards[subset]
                logger.info(f"Removed subset {subset} due to lowest river card rank")                 
                              
    def handle_forced_bets(self, bet_type: str):
        """Handle forced bets (antes or blinds) at the start of a hand."""
        logger.info(f"Handling forced bets: {bet_type}")
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            return

        if bet_type == "antes":
            ante_amount = self.ante
            logger.debug(f"Posting antes: ${ante_amount}")
            # All players post antes
            for player in active_players:
                amount = min(ante_amount, player.stack)
                if amount > 0:
                    player.stack -= amount
                    #self.betting.pot.add_bet(player.id, amount, is_all_in=(amount == player.stack), stack_before=player.stack)
                    self.betting.place_bet(player.id, amount, player.stack + amount, is_forced=True, is_ante=True)
                    logger.info(f"{player.name} posts ante of ${amount} (Remaining stack: ${player.stack})")
           # self.current_player = None  # No player has acted yet; bring-in will determine first
           # self.betting.new_round(preserve_current_bet=True)  # Preserve ante as part of round but reset acted flags

        elif bet_type == "blinds":
            positions = self.table.get_position_order()
            sb_player = next((p for p in positions if p.position and p.position.has_position(Position.SMALL_BLIND)), None)
            bb_player = next((p for p in positions if p.position and p.position.has_position(Position.BIG_BLIND)), None)
            # use small_blind and big_blind here - they should be set appropriately for the game giving the betting
            # style (limit, no-limit, pot-limit)
            if sb_player and self.small_blind > 0:
                sb_amount = min(self.small_blind, sb_player.stack)
                sb_player.stack -= sb_amount
                self.betting.place_bet(sb_player.id, sb_amount, sb_player.stack + sb_amount, is_forced=True)
                logger.info(f"{sb_player.name} posts small blind of ${sb_amount}...")
            if bb_player and self.big_blind > 0:
                bb_amount = min(self.big_blind, bb_player.stack)
                bb_player.stack -= bb_amount
                self.betting.place_bet(bb_player.id, bb_amount, bb_player.stack + bb_amount, is_forced=True)
                logger.info(f"{bb_player.name} posts big blind of ${bb_amount}...")
          #  self.current_player = self.next_player(round_start=True)
          #  self.betting.new_round(preserve_current_bet=True)        

        elif bet_type == "bring-in":
            bring_in_amount = self.bring_in or self.small_bet  # Use bring_in if set, else small_bet
            bring_in_player = self.table.get_bring_in_player(bring_in_amount)
            if bring_in_player:
                self.current_player = bring_in_player
                logger.info(f"Bring-in player: {bring_in_player.name} with {bring_in_player.hand.cards[-1]}")
            else:
                logger.error("No bring-in player determined")
                self.current_player = active_players[0]  # Fallback
            # No current_player set; next_player() will use betting_order.initial
                           
        self.betting.new_round(preserve_current_bet=True)  # Reset bets, keep forced bets in pot
        if bet_type != "bring-in":  # Only set current_player after bring-in if not already set
            self.current_player = self.next_player(round_start=True)

    def _set_next_player_after(self, player_id: str) -> None:
        """Set the current player to the player after the specified player."""
        players = self.table.get_position_order()
        active_players = [p for p in players if p.is_active]
        
        try:
            idx = next(i for i, p in enumerate(active_players) if p.id == player_id)
            next_idx = (idx + 1) % len(active_players)
            self.current_player = active_players[next_idx]
        except (StopIteration, IndexError):
            if active_players:
                self.current_player = active_players[0]
            else:
                self.current_player = None        
        
    def _next_step(self) -> None:
        """Move to next step in gameplay sequence."""

        # Clean up temporary attributes
        for attr in ["current_discard_config", "current_draw_config", "current_separate_config", 
                        "current_expose_config", "current_pass_config", "current_declare_config"]:
            if hasattr(self, attr):
                delattr(self, attr)        
                
        self.current_step += 1
        self.process_current_step()
        
    def next_player(self, round_start: bool = False) -> Optional[Player]:
        logger.debug(f"Determining next player (round_start={round_start}, current_step={self.current_step})")
        
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            return None
        
        # Determine if this is a voluntary betting round
        is_voluntary_bet = False
        current_step_config = self.rules.gameplay[self.current_step] if self.current_step < len(self.rules.gameplay) else None
        if current_step_config:
            if current_step_config.action_type == GameActionType.BET:
                bet_type = current_step_config.action_config.get("type")
                is_voluntary_bet = bet_type not in ["antes", "blinds", "bring-in"]
            elif current_step_config.action_type == GameActionType.GROUPED:
                substep = self.action_handler.current_substep
                if substep < len(current_step_config.action_config):
                    subaction = current_step_config.action_config[substep]
                    if "bet" in subaction:
                        bet_type = subaction["bet"].get("type")
                        is_voluntary_bet = bet_type not in ["antes", "blinds", "bring-in"]
        
        # Identify forced bettors
        current_bets = self.betting.current_bets  # {player_id: PlayerBet}
        forced_bettors = [pid for pid, bet in current_bets.items() if bet.posted_blind]
        
        if round_start:
            # Use initial order only for the first voluntary betting round after forced bets
            if self.betting.betting_round == 0 and is_voluntary_bet and forced_bettors:
                last_forced_bettor_id = forced_bettors[-1]  # Last player to post a blind (BB)
                players = self.table.get_position_order()
                try:
                    forced_bettor_idx = next(i for i, p in enumerate(players) if p.id == last_forced_bettor_id)
                    next_idx = (forced_bettor_idx + 1) % len(players)
                    while not players[next_idx].is_active:
                        next_idx = (next_idx + 1) % len(players)
                        if next_idx == forced_bettor_idx:  # Full circle
                            return None
                    next_player = players[next_idx]
                    logger.debug(f"First voluntary betting round: Starting with {next_player.name}")
                    return next_player
                except StopIteration:
                    return active_players[0]  # Fallback
            else:
                # Use subsequent order for all other round starts (including draw phases)
                order_type = self.rules.betting_order.subsequent
                logger.debug(f"Using subsequent order type: {order_type} (step={self.current_step}, betting_round={self.betting.betting_round})")
                if order_type == "dealer":
                    next_player = self.table.get_next_active_player(self.table.button_pos)
                    logger.debug(f"  dealer: Starting with {next_player.name}")
                elif order_type == "after_big_blind":
                    next_player = self.table.get_player_after_big_blind()
                    logger.debug(f"  after_big_blind: Starting with {next_player.name}")
                elif order_type == "bring_in":
                    next_player = self.table.get_bring_in_player(self.bring_in or self.small_bet)
                    logger.debug(f"  bring_in: Starting with {next_player.name}")
                elif order_type == "high_hand":
                    next_player = self.table.get_player_with_best_hand()
                    logger.debug(f"  high_hand: Starting with {next_player.name}")                    
                else:
                    logger.warning(f"Unsupported subsequent order '{order_type}', defaulting to dealer")
                    next_player = self.table.get_next_active_player(self.table.button_pos)
                    logger.debug(f"  default: Starting with {next_player.name}")
                if next_player:
                    return next_player
                return active_players[0]  # Fallback
        
        # Mid-round: Move to next active player
        if self.current_player:
            players = self.table.get_position_order()
            try:
                current_idx = next(i for i, p in enumerate(players) if p.id == self.current_player.id)
                next_idx = (current_idx + 1) % len(players)
                while not players[next_idx].is_active:
                    next_idx = (next_idx + 1) % len(players)
                    if next_idx == current_idx:  # Full circle
                        return None
                logger.debug(f"Next player: {players[next_idx].name}")
                return players[next_idx]
            except StopIteration:
                return active_players[0]  # Fallback
        return active_players[0]  # Default fallback

    def _handle_fold_win(self, active_players: List[Player]) -> None:
        logger.info("All but one player folded - hand complete")
        
        total_pot = self.betting.get_total_pot()
        
        self.state = GameState.COMPLETE
        self.betting.award_pots(active_players)
        
        hand_results = {}
        for player in active_players:
            hand_result = HandResult(
                player_id=player.id,
                cards=[],
                hand_name="Not shown",
                hand_description="Hand not shown - won uncontested",
                evaluation_type="unknown",
                hand_type="Uncontested"  # Optional: for clarity
            )
            hand_results[player.id] = [hand_result]
        
        # Fix: Include all winning hands
        winning_hands = [hand for player_hands in hand_results.values() for hand in player_hands]
        
        pot_result = PotResult(
            amount=total_pot,
            winners=[p.id for p in active_players],
            pot_type="main",
            hand_type="Entire Pot",
            eligible_players=set(p.id for p in active_players)
        )
        
        self.last_hand_result = GameResult(
            pots=[pot_result],
            hands=hand_results,
            winning_hands=winning_hands,  # Updated
            is_complete=True
        )

    def _handle_showdown_with_declare(self) -> None:
        """
        Handle showdown with declarations for Hi-Lo games.
        
        For declaration_mode='declare', uses Variation #2 from Conjelco:
        - Players declare 'high', 'low', or 'high_low' per pot.
        - High portion: Best high hand among 'high' or 'high_low' declarers.
        - Low portion: Best low hand among 'low' or 'high_low' declarers.
        - 'High_low' declarers must win both outright to scoop, but can win a tied portion.
        - Unwon portions go to the other portion's winners; if none eligible, split among all.

        Currently, assumption is no qualifier when using declare
        """

        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            self.state = GameState.COMPLETE
            return
            
        # Get showdown rules
        showdown_rules = self.rules.showdown
        best_hand_configs = showdown_rules.best_hand

        # Validate Hi-Lo with declarations
        if len(best_hand_configs) != 2 or showdown_rules.declaration_mode != "declare":
            logger.error("Declarations only supported for Hi-Lo games with two configurations and declaration_mode='declare'")
            return  # Could fall back to existing logic if needed        
        
        # Assume two configurations: high and low
        high_config = best_hand_configs[0]  # e.g., "High Hand"
        low_config = best_hand_configs[1]   # e.g., "Low Hand"
        high_eval_type = EvaluationType(high_config.get('evaluationType', 'high'))
        low_eval_type = EvaluationType(low_config.get('evaluationType', 'low'))

        # Evaluate all hands
        high_results = self._evaluate_hands_for_config(active_players, high_config, high_eval_type)
        low_results = self._evaluate_hands_for_config(active_players, low_config, low_eval_type)

        # Store hand results
        hand_results = {
            p.id: {
                high_config.get('name', 'High'): high_results.get(p.id),
                low_config.get('name', 'Low'): low_results.get(p.id)
            } for p in active_players
        }
        pot_results = []
        winning_hands = []

        # Pot info
        main_pot_eligible = set(p.id for p in active_players)
        side_pots_eligible = [set(self.betting.get_side_pot_eligible_players(i)) 
                              for i in range(self.betting.get_side_pot_count())]
        
        # Process each pot
        for pot_index in [-1] + list(range(self.betting.get_side_pot_count())):
            if pot_index == -1:
                eligible_ids = main_pot_eligible
                pot_amount = self.betting.get_main_pot_amount()
            else:
                eligible_ids = side_pots_eligible[pot_index]
                pot_amount = self.betting.get_side_pot_amount(pot_index)        

            if not eligible_ids or pot_amount <= 0:
                continue

            # Get declarations
            declarations = {pid: self.declarations.get(pid, {}).get(pot_index) 
                            for pid in eligible_ids}
            logger.debug(f"Pot {pot_index}: Declarations {declarations}")      

            # Check if all players declared high_low
            all_high_low = all(decl == "high_low" for decl in declarations.values())            
            
            # Eligible players per portion
            high_eligible = [pid for pid in eligible_ids 
                            if declarations.get(pid) in ["high", "high_low"]]
            low_eligible = [pid for pid in eligible_ids 
                            if declarations.get(pid) in ["low", "high_low"]]        

            # Best high hands
            H = []
            best_high_hands = []
            if high_eligible and high_results:
                high_hands = {pid: high_results[pid] for pid in high_eligible 
                            if pid in high_results and high_results[pid]}
                if high_hands:
                    # Find best high hand(s) using compare_hands
                    best_pids = []
                    best_hand = None
                    for pid, result in high_hands.items():
                        hand = result.cards
                        if not best_hand:
                            best_pids = [pid]
                            best_hand = hand
                            best_high_hands = [result]
                        else:
                            comparison = evaluator.compare_hands(hand, best_hand, high_eval_type)
                            if comparison > 0:  # Current hand is better
                                best_pids = [pid]
                                best_hand = hand
                                best_high_hands = [result]
                            elif comparison == 0:  # Tie
                                best_pids.append(pid)
                                best_high_hands.append(result)
                    H = best_pids
            logger.debug(f"Pot {pot_index}: Best high hands {H}")

            # Best low hands
            L = []
            best_low_hands = []
            if low_eligible and low_results:
                low_hands = {pid: low_results[pid] for pid in low_eligible 
                            if pid in low_results and low_results[pid]}
                if low_hands:
                    # Find best low hand(s) using compare_hands
                    best_pids = []
                    best_hand = None
                    for pid, result in low_hands.items():
                        hand = result.cards
                        if not best_hand:
                            best_pids = [pid]
                            best_hand = hand
                            best_low_hands = [result]
                        else:
                            comparison = evaluator.compare_hands(hand, best_hand, low_eval_type)
                            if comparison > 0:  # Current hand is better
                                best_pids = [pid]
                                best_hand = hand
                                best_low_hands = [result]
                            elif comparison == 0:  # Tie
                                best_pids.append(pid)
                                best_low_hands.append(result)
                    L = best_pids
            logger.debug(f"Pot {pot_index}: Best low hands {L}")

            # Determine high_low eligibility
            high_low_eligible = {}
            for pid in eligible_ids:
                if declarations.get(pid) == "high_low":
                    # Must win or tie both high and low
                    in_high = pid in H
                    in_low = pid in L
                    high_low_eligible[pid] = in_high and in_low
                else:
                    high_low_eligible[pid] = True  # Non-high_low players are eligible
            logger.debug(f"Pot {pot_index}: High_low eligibility {high_low_eligible}")            

            # use https://www.conjelco.com/faq/high-low-declare.html Variation #2 for this
            # High winners per Variation #2
            high_winners = []
            high_reason = "Best high hand"
            for pid in H:
                decl = declarations.get(pid)
                if high_low_eligible[pid]:
                    if decl == "high":
                        high_winners.append(pid)
                    elif decl == "high_low":
                        high_winners.append(pid)
            # If no winners yet, check high declarers
            if not high_winners:
                high_only = [pid for pid in high_eligible if declarations.get(pid) == "high" and high_low_eligible[pid]]
                if high_only and high_hands:
                    best_high_only_pids = []
                    best_hand = None
                    for pid in high_only:
                        if pid in high_hands:
                            hand = high_hands[pid].cards
                            if not best_hand:
                                best_high_only_pids = [pid]
                                best_hand = hand
                            else:
                                comparison = evaluator.compare_hands(hand, best_hand, high_eval_type)
                                if comparison > 0:
                                    best_high_only_pids = [pid]
                                    best_hand = hand
                                elif comparison == 0:
                                    best_high_only_pids.append(pid)
                    high_winners = best_high_only_pids
                    high_reason = "Best high hand among high declarers"
            logger.debug(f"Pot {pot_index}: High winners {high_winners}")

            # Low winners per Variation #2
            low_winners = []
            low_reason = "Best low hand"
            for pid in L:
                decl = declarations.get(pid)
                if high_low_eligible[pid]:
                    if decl == "low":
                        low_winners.append(pid)
                    elif decl == "high_low":
                        low_winners.append(pid)
            # If no winners yet, check low declarers
            if not low_winners:
                low_only = [pid for pid in low_eligible if declarations.get(pid) == "low" and high_low_eligible[pid]]
                if low_only and low_hands:
                    best_low_only_pids = []
                    best_hand = None
                    for pid in low_only:
                        if pid in low_hands:
                            hand = low_hands[pid].cards
                            if not best_hand:
                                best_low_only_pids = [pid]
                                best_hand = hand
                            else:
                                comparison = evaluator.compare_hands(hand, best_hand, low_eval_type)
                                if comparison > 0:
                                    best_low_only_pids = [pid]
                                    best_hand = hand
                                elif comparison == 0:
                                    best_low_only_pids.append(pid)
                    low_winners = best_low_only_pids
                    low_reason = "Best low hand among low declarers"
            logger.debug(f"Pot {pot_index}: Low winners {low_winners}")

            # Handle no winners
            if not high_winners and low_winners:
                high_winners = low_winners.copy()
                high_reason = "Reallocated to low winners (no qualifying high hand)"
            if not low_winners and high_winners:
                low_winners = high_winners.copy()
                low_reason = "Reallocated to high winners (no qualifying low hand)"
            if not high_winners and not low_winners:
                # Exception: if all high_low and none qualify, split among all
                if all_high_low and not any(high_low_eligible.values()):
                    high_winners = list(eligible_ids)
                    low_winners = list(eligible_ids)
                    high_reason = "Split among all players (no high_low players qualified)"
                    low_reason = "Split among all players (no high_low players qualified)"
                else:
                    high_winners = list(eligible_ids)
                    low_winners = list(eligible_ids)
                    high_reason = "Split among all players (no qualifying hands)"
                    low_reason = "Split among all players (no qualifying hands)"
            logger.debug(f"Pot {pot_index}: Final high winners {high_winners}, low winners {low_winners}")

            # Award high portion (50%)
            high_amount = int(pot_amount * 0.5)
            if high_winners:
                winners = [self.table.players[pid] for pid in high_winners]
                self.betting.award_pots(winners, pot_index if pot_index >= 0 else None, high_amount)
                pot_result = PotResult(
                    amount=high_amount,
                    winners=high_winners,
                    pot_type="side" if pot_index >= 0 else "main",
                    hand_type=high_config.get('name', 'High'),
                    side_pot_index=pot_index if pot_index >= 0 else None,
                    eligible_players=eligible_ids,
                    reason=high_reason,
                    best_hands=best_high_hands,
                    declarations=declarations                    
                )
                pot_results.append(pot_result)
                logger.debug(f"Pot {pot_index}: Created high pot result: {pot_result}")
                for pid in high_winners:
                    if pid in high_results and high_results[pid]:
                        hand = high_results[pid]
                        hand.hand_type = high_config.get('name', 'High')
                        winning_hands.append(hand)  

            # Award low portion (50%)
            low_amount = int(pot_amount * 0.5)
            if low_winners:
                winners = [self.table.players[pid] for pid in low_winners]
                self.betting.award_pots(winners, pot_index if pot_index >= 0 else None, low_amount)
                pot_result = PotResult(
                    amount=low_amount,
                    winners=low_winners,
                    pot_type="side" if pot_index >= 0 else "main",
                    hand_type=low_config.get('name', 'Low'),
                    side_pot_index=pot_index if pot_index >= 0 else None,
                    eligible_players=eligible_ids,
                    reason=low_reason,
                    best_hands=best_low_hands,
                    declarations=declarations
                )
                pot_results.append(pot_result)
                logger.debug(f"Pot {pot_index}: Created low pot result: {pot_result}")
                for pid in low_winners:
                    if pid in low_results and low_results[pid]:
                        hand = low_results[pid]
                        hand.hand_type = low_config.get('name', 'Low')
                        winning_hands.append(hand)

        # Store results
        self.last_hand_result = GameResult(
            pots=pot_results,
            hands={pid: list(results.values()) for pid, results in hand_results.items()},
            winning_hands=winning_hands,
            is_complete=True
        )
        logger.debug(f"Final pot results: {[(p.hand_type, p.winners, p.amount) for p in pot_results]}")
        self.state = GameState.COMPLETE

    def _handle_showdown(self) -> None:
        """
        Handle showdown and determine winners, supporting declarations for Hi-Lo games.
        
        For declaration_mode='declare', uses Variation #2 from Conjelco:
        - Players declare 'high', 'low', or 'high_low' per pot.
        - High portion: Best high hand among 'high' or 'high_low' declarers.
        - Low portion: Best low hand among 'low' or 'high_low' declarers (meeting qualifier).
        - 'High_low' declarers must win both outright to scoop, but can win a tied portion.
        - Unwon portions go to the other portion's winners; if none eligible, split among all.
        """
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            self.state = GameState.COMPLETE
            return
        
        # Get showdown rules
        showdown_rules = self.rules.showdown
        best_hand_configs = showdown_rules.best_hand

        # for now - completely separate code - we'll merge things together later
        if showdown_rules.declaration_mode == "declare":
            self._handle_showdown_with_declare()
            return
            
        default_actions = showdown_rules.defaultActions  # Per-configuration alternate rules
        global_default_action = showdown_rules.globalDefaultAction  # Global fallback
                
        # Initialize structures for tracking results
        pot_results = []
        hand_results = {}  # player_id -> {config_name: HandResult}
        winning_hands = []
        
        # Get total pot amount for tracking
        original_main_pot = self.betting.get_main_pot_amount()
        original_side_pots = [self.betting.get_side_pot_amount(i) for i in range(self.betting.get_side_pot_count())]        
        total_pot = self.betting.get_total_pot()
                
        # If there's only one hand configuration, it gets 100% of the pot
        pot_percentage = 1.0 / len(best_hand_configs)

        # Track awarded divisions
        had_any_winners = False       

        # Track which portions of the pot were awarded
        awarded_portions = 0
        awarded_pot_results = []        
        
        logger.info(f"Showdown with {len(best_hand_configs)} possible hands to win")  

        # Process each hand configuration
        for config in best_hand_configs:
            config_name = config.get('name', f"Configuration {len(hand_results)+1}")
            eval_type = EvaluationType(config.get('evaluationType', 'high'))
            qualifier = config.get('qualifier', None)
            
            logger.info(f"  Evaluating {config_name} with evaluation type {eval_type}")  
            if qualifier:
                logger.info(f"    with qualifier {qualifier}")  

            config_results = {}
            if 'usesUnusedFrom' in config:
                # Handle configurations like "Remaining Two Cards"
                ref_config_name = config['usesUnusedFrom']
                for player in active_players:
                    if player.id in hand_results and ref_config_name in hand_results[player.id]:
                        ref_result = hand_results[player.id][ref_config_name]
                        used_hole = ref_result.used_hole_cards
                        all_hole = player.hand.get_cards()
                        unused_hole = [c for c in all_hole if c not in used_hole]
                        required_hole = config.get("holeCards", 2)
                        required_community = config.get("communityCards", 0)

                        if len(unused_hole) < required_hole:
                            logger.warning(f"Player {player.id} has insufficient unused hole cards for {config_name}")
                            config_results[player.id] = None
                            continue

                        hand = unused_hole[:required_hole]  # Take required number of unused hole cards
                        if required_community > 0:
                            comm_cards = self.table.community_cards.get('default', [])
                            if len(comm_cards) >= required_community:
                                hand.extend(list(itertools.combinations(comm_cards, required_community))[0])

                        from generic_poker.evaluation.hand_description import HandDescriber
                        describer = HandDescriber(eval_type)
                        result = HandResult(
                            player_id=player.id,     
                            cards=hand,                                                   
                            hand_name=describer.describe_hand(hand),
                            hand_description=describer.describe_hand_detailed(hand),
                            hand_type=config_name,
                            evaluation_type=eval_type.value,
                            used_hole_cards=unused_hole[:required_hole]  # Used hole cards are the hand's hole cards
                        )
                        config_results[player.id] = result
                    else:
                        logger.warning(f"Referenced config '{ref_config_name}' not found for player {player.id}")
                        config_results[player.id] = None
            else:
                # Normal evaluation for configurations like "High Hand"
                config_results = self._evaluate_hands_for_config(active_players, config, eval_type)
           
            # Update hand_results with config_results
            for player_id, result in config_results.items():
                if result:  # Only store if there's a valid result
                    if player_id not in hand_results:
                        hand_results[player_id] = {}
                    hand_results[player_id][config_name] = result
                    logger.info(f"  Player {player_id} has {result.hand_description} for {config_name}")
            
            # Award pots for this configuration
            pot_winners, had_winners = self._award_pots_for_config(
                active_players,
                config_results,
                eval_type,
                config,
                pot_percentage,
                original_main_pot,
                original_side_pots
            )
            had_any_winners = had_any_winners or had_winners
            
            # Track if this portion was awarded
            if had_winners:
                logging.debug("Had winners - saving pot results")
                awarded_portions += 1
                awarded_pot_results.extend(pot_winners)
                
                # Add winning hands to the list with proper type
                for pot_result in pot_winners:
                    for winner_id in pot_result.winners:
                        if winner_id in config_results and config_results[winner_id]:
                            winning_hand = config_results[winner_id]
                            winning_hand.hand_type = config_name
                            winning_hands.append(winning_hand)
            else:
                # No winners due to qualifier not met; check for per-configuration default actions
                applicable_actions = [da for da in default_actions if config_name in da.get('appliesTo', [])]
                if applicable_actions:
                    logger.debug(f"No winners for {config_name}; applying default action")
                    for default_action in applicable_actions:
                        action = default_action.get('action', {})
                        if action.get('type') == 'evaluate_special':
                            # Apply special evaluation (e.g., highest spade in hole)
                            best_players, best_cards_dict = self._find_best_players_for_special(
                                active_players=active_players,
                                criterion=action['evaluation'].get('criterion'),
                                suit=action['evaluation'].get('suit'),
                                from_source=action['evaluation'].get('from'),
                                subsets=action['evaluation'].get('subsets', ['default'])
                            )
                            if best_players:
                                # Award this configuration's pot portion to the best players
                                special_pot_winners = self._award_special_pot(
                                    best_players=best_players,
                                    main_pot=original_main_pot,
                                    side_pots=original_side_pots,
                                    pot_percentage=pot_percentage,
                                    config_name=config_name
                                )
                                awarded_portions += 1
                                awarded_pot_results.extend(special_pot_winners)
                                had_any_winners = True
                                # Record the winning hands dynamically
                                for player in best_players:
                                    qualifying_cards = best_cards_dict.get(player.id, [])
                                    criterion = action['evaluation'].get('criterion', 'unknown')
                                    suit = action['evaluation'].get('suit', '')
                                    # Format criterion and suit: replace underscores with spaces and capitalize each word
                                    criterion_formatted = ' '.join(word.capitalize() for word in criterion.split('_'))
                                    suit_formatted = ' '.join(word.capitalize() for word in suit.split('_')) if suit else ''
                                    hand_name = f"{criterion_formatted} {suit_formatted}".strip() if suit else criterion_formatted
                                    hand_description = f"{hand_name} ({', '.join(str(c) for c in qualifying_cards)})" if qualifying_cards else hand_name

                                    special_hand = HandResult(
                                        player_id=player.id,
                                        cards=qualifying_cards,
                                        hand_name=hand_name,
                                        hand_description=hand_description,
                                        hand_type=config_name,
                                        evaluation_type="special",
                                        used_hole_cards=qualifying_cards,
                                        community_cards=[]
                                    )
                                    if player.id not in hand_results:
                                        hand_results[player.id] = {}
                                    hand_results[player.id][config_name] = special_hand
                                    winning_hands.append(special_hand)
                if not applicable_actions or not any(pot_result.winners for pot_result in awarded_pot_results[-len(pot_winners):]):
                    # No applicable action or no winners found; record empty pot results
                    for pot_result in pot_winners:
                        pot_result.winners = []
                        awarded_pot_results.append(pot_result)
               
        # If some portions were not awarded, redistribute to the winners of other portions
        if awarded_portions > 0 and awarded_portions < len(best_hand_configs):
            logging.debug("Some portions not awarded - redistribute to the winners of other portions")
            remaining_percentage = 1.0 - (awarded_portions * pot_percentage)
            
            if remaining_percentage > 0 and awarded_pot_results:
                # Award remaining pot proportionally to existing winners
                self._redistribute_unawarded_pot(
                    original_main_pot, 
                    original_side_pots,
                    remaining_percentage, 
                    awarded_pot_results
                )

        # Handle default action if no winners in any division
        if not had_any_winners and global_default_action and global_default_action.get('condition') == 'no_qualifier_met':
            logger.debug("No player qualified for any hand - handling global default action")
            action = global_default_action.get('action')
            action_type = action.get('type', 'split_pot')
            
            if action_type == 'split_pot':
                logger.debug("   split_pot: split the pot among all active players")
                # For 'split_pot' action, split the pot among all active players
                self._handle_split_among_active(active_players, original_main_pot, original_side_pots)
                
                # Create pot result entries for the split
                for i in range(len(original_side_pots)):
                    eligible_ids = self.betting.get_side_pot_eligible_players(i)
                    eligible_players = [p for p in active_players if p.id in eligible_ids]
                    
                    if eligible_players:
                        pot_result = PotResult(
                            amount=original_side_pots[i],
                            winners=[p.id for p in eligible_players],
                            pot_type="side",
                            hand_type="Split (No Qualifier)",
                            side_pot_index=i,
                            eligible_players=set(p.id for p in eligible_players)
                        )
                        awarded_pot_results.append(pot_result)
                
                # Main pot
                pot_result = PotResult(
                    amount=original_main_pot,
                    winners=[p.id for p in active_players],
                    pot_type="main",
                    hand_type="Split (No Qualifier)",
                    eligible_players=set(p.id for p in active_players)
                )
                awarded_pot_results.append(pot_result)
                
                # Also mark all hands as "winning" in this case
                for player in active_players:
                    if player.id in hand_results:
                        for hand in hand_results[player.id].values():
                            hand.hand_type = "Split (No Qualifier)"
                            winning_hands.append(hand)             

            elif action_type == 'best_hand':
                logger.debug("   best_hand: evaluate hands using the alternate evaluation type")
                # For 'best_hand' action, evaluate hands using the alternate evaluation type
                alternate_configs = action.get('bestHand', [])
                
                if alternate_configs:
                    # Process each alternate hand configuration
                    alt_pot_results = []
                    alt_winning_hands = []
                    
                    for alt_config in alternate_configs:
                        alt_name = alt_config.get('name', 'Alternate Hand')
                        alt_eval_type = EvaluationType(alt_config.get('evaluationType', 'high'))
                        
                        # Find best hands using alternate evaluation
                        alt_results = self._evaluate_hands_for_config(
                            active_players, 
                            alt_config,
                            alt_eval_type
                        )
                        
                        # Update the hand results
                        for player_id, result in alt_results.items():
                            if player_id not in hand_results:
                                hand_results[player_id] = {}
                            if result:
                                result.hand_type = alt_name
                                hand_results[player_id][alt_name] = result
                        
                        # Award pots using the alternate evaluation
                        alt_winners, had_alt_winners = self._award_alternate_pots(
                            active_players,
                            alt_results,
                            alt_eval_type,
                            alt_config,
                            original_main_pot,
                            original_side_pots
                        )
                        
                        alt_pot_results.extend(alt_winners)
                        
                        # Add winning hands
                        for pot_result in alt_winners:
                            for winner_id in pot_result.winners:
                                if winner_id in alt_results and alt_results[winner_id]:
                                    winning_hand = alt_results[winner_id]
                                    winning_hand.hand_type = alt_name
                                    alt_winning_hands.append(winning_hand)
                    
                    # Use the alternate results
                    awarded_pot_results = alt_pot_results
                    winning_hands = alt_winning_hands                                             

        # Store the complete game result
        self.last_hand_result = GameResult(
            pots=awarded_pot_results,
            hands={pid: list(results.values()) for pid, results in hand_results.items()},
            winning_hands=winning_hands,
            is_complete=True
        )
        
        # Sanity check - verify total pot amounts match
        if self.last_hand_result.total_pot != total_pot:
            logger.warning(
                f"Pot amount mismatch: {self.last_hand_result.total_pot} vs {total_pot}"
            )
        
        self.state = GameState.COMPLETE


    def _find_best_players_for_special(self, active_players, criterion, suit, from_source, subsets):
        """
        Find the best players and their qualifying cards based on a special evaluation criterion.
        
        Args:
            active_players (list): List of Player objects.
            criterion (str): Evaluation criterion (e.g., "highest_rank").
            suit (str): Suit to evaluate (e.g., "spades").
            from_source (str): Source of cards (e.g., "hole_cards").
            subsets (list): Subsets of cards to consider (e.g., ["default"]).
        
        Returns:
            tuple: (list of Player objects, dict of player_id -> list of Card objects)
        """
        if criterion != "highest_rank" or from_source != "hole_cards":
            logger.warning(f"Unsupported special evaluation: criterion={criterion}, from={from_source}")
            return [], {}
    
        # Suit mapping for static suits
        suit_map = {
            "clubs": Suit.CLUBS,
            "diamonds": Suit.DIAMONDS,
            "hearts": Suit.HEARTS,
            "spades": Suit.SPADES,
            "club": Suit.CLUBS,
            "diamond": Suit.DIAMONDS,
            "heart": Suit.HEARTS,
            "spade": Suit.SPADES,
            "joker": Suit.JOKER,
            "c": Suit.CLUBS,
            "d": Suit.DIAMONDS,
            "h": Suit.HEARTS,
            "s": Suit.SPADES,
            "j": Suit.JOKER
        }
        
        # Determine the suit enum
        if suit == "river_card_suit":
            try:
                community_cards = self.table.community_cards.get('default', [])
                if not community_cards:
                    logger.error("No community cards available to determine river card suit")
                    return [], {}
                river_card = community_cards[-1]  # Last card is the river
                suit_enum = river_card.suit
                suit_name = river_card.suit.name.lower()  # For logging/description
            except IndexError:
                logger.error("Failed to access river card from community cards")
                return [], {}
        elif suit:
            try:
                suit_enum = suit_map[suit.lower()]
                suit_name = suit  # Use the JSON-provided suit name for description
            except KeyError:
                logger.error(f"Invalid suit specified: {suit}")
                return [], {}
        else:
            suit_enum = None
            suit_name = ""
            
        best_rank_index = len(BASE_RANKS)  # Worst possible index (lower index = better rank)
        best_players = []
        best_cards_dict = {}  # player_id -> list of qualifying cards
        
        for player in active_players:
            if from_source == "hole_cards":
                hole_cards = player.hand.get_cards()
                if suit_enum:
                    suit_cards = [card for card in hole_cards if card.suit == suit_enum]
                else:
                    suit_cards = hole_cards  # No suit filter if not specified

                if suit_cards:
                    highest_card = min(suit_cards, key=lambda c: BASE_RANKS.index(c.rank.value))
                    rank_index = BASE_RANKS.index(highest_card.rank.value)
                    if rank_index < best_rank_index:
                        best_rank_index = rank_index
                        best_players = [player]
                        best_cards_dict = {player.id: [highest_card]}
                    elif rank_index == best_rank_index:
                        best_players.append(player)
                        best_cards_dict[player.id] = [highest_card]
        
        logger.debug(f"Best players for {suit} {criterion}: {[p.id for p in best_players]} with cards: {best_cards_dict}")
        return best_players, best_cards_dict
    
    def _award_special_pot(self, best_players, main_pot, side_pots, pot_percentage, config_name):
        """
        Award a pot portion to players based on a special evaluation.
        
        Args:
            best_players (list): List of Player objects who won.
            main_pot (int): Main pot amount.
            side_pots (list): List of side pot amounts.
            pot_percentage (float): Percentage of the pot for this configuration.
            config_name (str): Name of the configuration (e.g., "Low Hand").
        
        Returns:
            list: List of PotResult objects.
        """
        pot_results = []
        winner_ids = [p.id for p in best_players]
        
        # Main pot portion
        main_amount = int(main_pot * pot_percentage)
        if main_amount > 0:
            pot_result = PotResult(
                amount=main_amount,
                winners=winner_ids,
                pot_type="main",
                hand_type=config_name,
                eligible_players=set(p.id for p in best_players)
            )
            pot_results.append(pot_result)
        
        # Side pots portion
        for i, side_amount in enumerate(side_pots):
            portion_amount = int(side_amount * pot_percentage)
            if portion_amount > 0:
                eligible_ids = self.betting.get_side_pot_eligible_players(i)
                eligible_winners = [p.id for p in best_players if p.id in eligible_ids]
                if eligible_winners:
                    pot_result = PotResult(
                        amount=portion_amount,
                        winners=eligible_winners,
                        pot_type="side",
                        hand_type=config_name,
                        side_pot_index=i,
                        eligible_players=set(eligible_ids)
                    )
                    pot_results.append(pot_result)
        
        logger.debug(f"Awarded {config_name} pot portion to {winner_ids}")
        return pot_results
    
    def apply_wild_cards(self, player: Player, comm_cards: List[Card], wild_rules: List[dict]) -> None:
        """Apply wild card rules to the player's hand and community cards."""
        logger.debug(f"Applying wild card rules for player {player.name} with community cards: {comm_cards} and wild rules: {wild_rules}") 
        for rule in wild_rules:
            rule_type = rule["type"]
            role = rule.get("role", "wild")
            wild_type = WildType.BUG if role == "bug" else WildType.NAMED

            if rule_type == "joker":
                # Jokers are already marked as wild, adjust role if needed
                for card in player.hand.get_cards() + comm_cards:
                    if card.rank == Rank.JOKER:
                        card.make_wild(wild_type)

            elif rule_type == "rank":
                rank = Rank(rule["rank"])
                for card in player.hand.get_cards() + comm_cards:
                    if card.rank == rank:
                        card.make_wild(wild_type)

            elif rule_type == "lowest_community":
                subset = rule.get("subset", "default")
                if not comm_cards:
                    continue
                # Sort by rank (A low, K high)
                sorted_cards = sorted(comm_cards, key=lambda c: list(Rank).index(c.rank))
                lowest_rank = sorted_cards[0].rank
                for card in player.hand.get_cards() + comm_cards:
                    if card.rank == lowest_rank:
                        card.make_wild(wild_type)

            elif rule_type == "lowest_hole":
                subset = rule.get("subset", "default")
                visibility = Visibility.FACE_DOWN if rule.get("visibility") == "face down" else Visibility.FACE_UP
                hole_cards = player.hand.get_subset(subset) if subset != "default" else player.hand.get_cards()
                eligible_cards = [c for c in hole_cards if c.visibility == visibility]
                if not eligible_cards:
                    continue
                sorted_cards = sorted(eligible_cards, key=lambda c: list(Rank).index(c.rank))
                lowest_rank = sorted_cards[0].rank
                for card in player.hand.get_cards():  # Player-specific
                    if card.rank == lowest_rank:
                        card.make_wild(wild_type)

    def _evaluate_hands_for_config(
        self,
        players: List[Player],
        hand_config: dict,
        eval_type: EvaluationType
    ) -> Dict[str, HandResult]:
        """
        Evaluate all players' best hands for a specific hand configuration.
        
        Args:
            players: List of active players
            hand_config: Configuration for this hand evaluation
            eval_type: Type of evaluation to use
            
        Returns:
            Dictionary mapping player IDs to their best hand results
        """
        from generic_poker.evaluation.hand_description import HandDescriber
        
        hand_type = hand_config.get('name', "Hand")
        describer = HandDescriber(eval_type)
        results = {}

        if "zeroCardsPipValue" in hand_config:
            zero_cards_pip_value = hand_config["zeroCardsPipValue"]     
        else:
            zero_cards_pip_value = None  # Default to None if not specified in the config

        for player in players:
            # Find the player's best hand for this configuration
            best_hand, used_hole_cards = self._find_best_hand_for_player(
                player,
                self.table.community_cards,
                hand_config,
                eval_type
            )
          
            # allow an empty hand to play if it has value
            if not best_hand and zero_cards_pip_value is not None:
                logger.info(f"Player {player.name} has no valid hand for {hand_type}, but zeroCardsPipValue is set to {zero_cards_pip_value}. Assigning a default hand.")
                # create results
                results[player.id] = HandResult(
                    player_id=player.id,
                    cards=[],
                    hand_name="No Cards",
                    hand_description="No Cards",
                    hand_type=hand_type,
                    evaluation_type=eval_type.value,
                    community_cards=self.table.community_cards,
                    used_hole_cards=[]  # No hole cards used for an empty hand
                )

                continue

            if not best_hand:
                logger.info(f"Player {player.name} has no valid hand for {hand_type}. Skipping...")
                continue

            # Determine classification (e.g., face/butt)
            classifications = {}
            if "classification" in hand_config:
                classification_config = hand_config["classification"]
                if classification_config["type"] == "face_butt":
                    face_ranks = [Rank[r] for r in classification_config["faceRanks"]]
                    all_cards = player.hand.get_cards()  # All 7 cards
                    has_face = any(card.rank in face_ranks for card in all_cards)
                    classifications[classification_config["fieldName"]] = "face" if has_face else "butt"

            # Evaluate the hand to get rank
            rank_result = evaluator.evaluate_hand(best_hand, eval_type)
            if not rank_result:
                logger.warning(f"Failed to evaluate hand for player {player.id}")
                continue            
            
            # Create hand result with used_hole_cards
            results[player.id] = HandResult(
                player_id=player.id,
                cards=best_hand,
                rank=rank_result.rank,
                ordered_rank=rank_result.ordered_rank,                
                hand_name=describer.describe_hand(best_hand),
                hand_description=describer.describe_hand_detailed(best_hand),
                hand_type=hand_type,
                evaluation_type=eval_type.value,
                community_cards=self.table.community_cards,
                used_hole_cards=used_hole_cards,
                classifications=classifications
            )
        
        return results

    def _award_pots_for_config(
        self,
        players: List[Player],
        hand_results: Dict[str, HandResult],
        eval_type: EvaluationType,
        hand_config: dict,
        pot_percentage: float,
        original_main_pot: int,  
        original_side_pots: List[int]         
    ) -> Tuple[List[PotResult], bool]:
        """
        Award pots for a specific hand configuration.
        
        Args:
            players: List of active players
            hand_results: Dictionary of player hand results
            eval_type: Type of evaluation being used
            qualifier: Optional qualifier that hands must meet
            pot_percentage: Percentage of the pot to award for this config
            
        Returns:
            Tuple of (pot results, had_winners)
        """
        
        pot_results = []
        player_hands = {
            player_id: result.cards 
            for player_id, result in hand_results.items()
        }
        
        # Convert players to dictionary for easier lookup
        player_dict = {player.id: player for player in players}
        
        # Get main pot and side pot info
        main_pot_amount = self.betting.get_main_pot_amount()
        side_pot_count = self.betting.get_side_pot_count()
        side_pot_amounts = [self.betting.get_side_pot_amount(i) for i in range(side_pot_count)]
        
        qualifier = hand_config.get('qualifier', None)

        # Get current pot info for logging
        current_main_pot = self.betting.get_main_pot_amount()
        current_side_pot_count = self.betting.get_side_pot_count()
        
        logger.info(f"    Main pot has ${current_main_pot}.   There are {current_side_pot_count} side pot(s)")  
  
        had_winners = False

        # Award side pots first
        for i in range(side_pot_count):
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [player_dict[pid] for pid in eligible_ids if pid in player_dict]
            
            # Find players with valid hands for this side pot
            qualified_players = []
            for player in eligible_players:
                if player.id not in player_hands:
                    continue
                    
                # Check qualifier if specified
                if qualifier:
                    hand = player_hands[player.id]
                    result = evaluator.evaluate_hand(hand, eval_type)
                    if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                        continue
                
                qualified_players.append(player)
            
            if qualified_players:
                # Find best hand among eligible players
                winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
                if winners:
                    had_winners = True
                    # Calculate pot amount based on ORIGINAL side pot
                    pot_amount = int(original_side_pots[i] * pot_percentage)
                    
                    # Award the pot portion
                    self.betting.award_pots(winners, i, pot_amount)
                    
                    # Track the result
                    pot_result = PotResult(
                        amount=pot_amount,
                        winners=[p.id for p in winners],
                        pot_type="side",
                        hand_type=hand_config.get('name', 'Unspecified'),
                        side_pot_index=i,
                        eligible_players=eligible_ids
                    )
                    pot_results.append(pot_result)
        
        # Award main pot
        eligible_players = [player_dict[pid] for pid in player_dict.keys()]
        
        # Find players with valid hands for main pot
        qualified_players = []
        for player in eligible_players:
            if player.id not in player_hands:
                continue
                
            # Check qualifier if specified
            if qualifier:
                hand = player_hands[player.id]
                result = evaluator.evaluate_hand(hand, eval_type)
                if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                    continue
            
            qualified_players.append(player)
        
        if qualified_players:
            winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
            if winners:
                had_winners = True
                # Calculate pot amount based on ORIGINAL main pot
                pot_amount = int(original_main_pot * pot_percentage)
                logger.info(f"       Awarding ${pot_amount} ({original_main_pot} * {pot_percentage}) to {winners}.")  
                
                # Award the pot portion
                self.betting.award_pots(winners, None, pot_amount)
                
                # Track the result
                pot_result = PotResult(
                    amount=pot_amount,
                    winners=[p.id for p in winners],
                    pot_type="main",
                    hand_type=hand_config.get('name', 'Unspecified'),
                    eligible_players=set(p.id for p in eligible_players)
                )
                pot_results.append(pot_result)
        
        return pot_results, had_winners

    def _redistribute_unawarded_pot(
        self,
        original_main_pot: int,
        original_side_pots: List[int],
        remaining_percentage: float,
        awarded_pot_results: List[PotResult]
    ) -> None:
        """
        Redistribute unawarded pot portions to existing winners.
        
        Args:
            original_main_pot: Original main pot amount
            original_side_pots: Original side pot amounts
            remaining_percentage: Percentage of pot remaining to award
            awarded_pot_results: Pot results that have been awarded so far
        """
        # Group awarded pots by type
        main_pots = [p for p in awarded_pot_results if p.pot_type == "main" and p.winners]
        side_pots = {}
        for pot in [p for p in awarded_pot_results if p.pot_type == "side" and p.winners]:
            if pot.side_pot_index not in side_pots:
                side_pots[pot.side_pot_index] = []
            side_pots[pot.side_pot_index].append(pot)
        
        # Redistribute main pot
        if main_pots:
            additional_main = int(original_main_pot * remaining_percentage)
            for pot in main_pots:
                # Find players who won this pot
                winners = [self.table.players[pid] for pid in pot.winners]
                
                # Award additional amount
                self.betting.award_pots(winners, None, additional_main)
                
                # Update pot amount in result
                pot.amount += additional_main
                
                logger.info(f"Redistributed ${additional_main} to {[p.name for p in winners]} (no qualifying low hand)")
        
        # Redistribute side pots
        for idx, pots in side_pots.items():
            if idx < len(original_side_pots):
                additional_side = int(original_side_pots[idx] * remaining_percentage)
                
                for pot in pots:
                    # Find players who won this pot
                    winners = [self.table.players[pid] for pid in pot.winners]
                    
                    # Award additional amount
                    self.betting.award_pots(winners, idx, additional_side)
                    
                    # Update pot amount in result
                    pot.amount += additional_side
                    
                    logger.info(f"Redistributed ${additional_side} to {[p.name for p in winners]} for side pot {idx} (no qualifying low hand)")


    def _handle_split_among_active(self, players: List[Player], main_pot: int, side_pots: List[int]) -> None:
        """
        Split the pot among all active players when no qualifier is met.
        
        Args:
            players: List of active players
            main_pot: Main pot amount
            side_pots: List of side pot amounts
        """
        # Award side pots first - only to eligible players
        for i, pot_amount in enumerate(side_pots):
            if pot_amount <= 0:
                continue
                
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [p for p in players if p.id in eligible_ids]
            
            if eligible_players:
                # Split this pot among eligible players
                amount_per_player = pot_amount // len(eligible_players)
                remainder = pot_amount % len(eligible_players)
                
                for j, player in enumerate(eligible_players):
                    award = amount_per_player + (1 if j < remainder else 0)
                    player.stack += award
                    logger.info(f"Split ${award} to {player.name} from side pot {i} (no qualifier)")
        
        # Award main pot to all active players
        if main_pot > 0:
            amount_per_player = main_pot // len(players)
            remainder = main_pot % len(players)
            
            for i, player in enumerate(players):
                award = amount_per_player + (1 if i < remainder else 0)
                player.stack += award
                logger.info(f"Split ${award} to {player.name} from main pot (no qualifier)")

    def _award_alternate_pots(
        self,
        players: List[Player],
        hand_results: Dict[str, HandResult],
        eval_type: EvaluationType,
        hand_config: dict,
        original_main_pot: int,
        original_side_pots: List[int]
    ) -> Tuple[List[PotResult], bool]:
        """
        Award pots using an alternate evaluation when no qualifier is met.
        
        Args:
            players: List of active players
            hand_results: Dictionary of player hand results
            eval_type: Type of evaluation being used
            hand_config: Hand configuration
            original_main_pot: Original main pot amount
            original_side_pots: Original side pot amounts
            
        Returns:
            Tuple of (pot results, had_winners)
        """
        # Similar implementation to _award_pots_for_config but without pot_percentage
        # and using the full pot amounts since this is the fallback evaluation
        
        pot_results = []
        player_hands = {
            player_id: result.cards 
            for player_id, result in hand_results.items()
        }
        
        # Convert players to dictionary for easier lookup
        player_dict = {player.id: player for player in players}
        
        # Qualifier for the alternate hand type (if any)
        qualifier = hand_config.get('qualifier', None)
        
        had_winners = False
        
        # Award side pots first
        for i in range(len(original_side_pots)):
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [player_dict[pid] for pid in eligible_ids if pid in player_dict]
            
            # Find qualified players
            qualified_players = []
            for player in eligible_players:
                if player.id not in player_hands:
                    continue
                    
                # Check qualifier if specified
                if qualifier:
                    hand = player_hands[player.id]
                    result = evaluator.evaluate_hand(hand, eval_type)
                    if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                        continue
                
                qualified_players.append(player)
            
            if qualified_players:
                # Find best hand among eligible players
                winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
                if winners:
                    had_winners = True
                    
                    # Award the full side pot
                    pot_amount = original_side_pots[i]
                    self.betting.award_pots(winners, i, pot_amount)
                    
                    # Track the result
                    pot_result = PotResult(
                        amount=pot_amount,
                        winners=[p.id for p in winners],
                        pot_type="side",
                        hand_type=hand_config.get('name', 'Alternate Hand'),
                        side_pot_index=i,
                        eligible_players=eligible_ids
                    )
                    pot_results.append(pot_result)
        
        # Award main pot
        eligible_players = [player_dict[pid] for pid in player_dict.keys()]
        
        # Find qualified players
        qualified_players = []
        for player in eligible_players:
            if player.id not in player_hands:
                continue
                
            # Check qualifier if specified
            if qualifier:
                hand = player_hands[player.id]
                result = evaluator.evaluate_hand(hand, eval_type)
                if not result or (result.rank > qualifier[0]) or (result.rank == qualifier[0] and result.ordered_rank > qualifier[1]):
                    continue
            
            qualified_players.append(player)
        
        if qualified_players:
            winners = self._find_winners(qualified_players, hand_results, eval_type, self.rules.showdown)
            if winners:
                had_winners = True
                
                # Award the full main pot
                pot_amount = original_main_pot
                self.betting.award_pots(winners, None, pot_amount)
                
                # Track the result
                pot_result = PotResult(
                    amount=pot_amount,
                    winners=[p.id for p in winners],
                    pot_type="main",
                    hand_type=hand_config.get('name', 'Alternate Hand'),
                    eligible_players=set(p.id for p in eligible_players)
                )
                pot_results.append(pot_result)
        
        return pot_results, had_winners                

    def get_hand_results(self) -> GameResult:
        """
        Get detailed results after a hand is complete.
        
        Returns:
            GameResult object with information about pots, winners, and hands
            
        Raises:
            ValueError: If the game is not in a completed state or no results available
        """
        if self.state not in [GameState.COMPLETE, GameState.SHOWDOWN]:
            raise ValueError("Cannot get results - hand not complete")
        
        if self.last_hand_result is None:
            raise ValueError("No results available - hand may have ended without showdown")
            
        return self.last_hand_result
       
    def _find_best_hand_for_player(
        self,
        player: Player,
        community_cards: Dict[str, List[Card]],
        showdown_rules: dict,
        eval_type: str
    ) -> tuple[List[Card], List[Card]]:
        """
        Find the best possible hand for a player according to the game rules.

        Args:
            player: The player
            community_cards: Available community cards
            showdown_rules: Showdown configuration from game rules
            eval_type: Type of hand evaluation to use

        Returns:
            Tuple of (best_hand, used_hole_cards) where:
                - best_hand: List of cards representing the player's best hand
                - used_hole_cards: List of hole cards used in the best hand
        """
        logger.info(f"_find_best_hand_for_player({player.id},{community_cards},{showdown_rules},{eval_type}'")

        
        hole_subset = showdown_rules.get("hole_subset", "default")
        community_subset = showdown_rules.get("community_subset", "default")
        padding = showdown_rules.get("padding", False)
        logger.debug(f"Finding best hand for player {player.id} with eval_type '{eval_type}' - using community subset '{community_subset}' and padding={padding}")
        
        # Get hole cards
        if hole_subset and hole_subset != "default":
            # Use specific subset if specified (e.g., SHESHE)
            hole_cards = player.hand.get_subset(hole_subset)
            if not hole_cards:
                logger.warning(f"No cards in hole subset '{hole_subset}' for player {player.id}")
                return [], []
        else:
            # Use all cards if no subset specified or default (e.g., Hold'em, Stud)
            hole_cards = player.hand.get_cards()
            if not hole_cards:
                logger.warning(f"No cards in hand for player {player.id}")
                return [], []
            
        # Filter hole cards by cardState if specified
        if "cardState" in showdown_rules:
            card_state = showdown_rules["cardState"]
            if card_state == "face down":
                hole_cards = [card for card in hole_cards if card.visibility == Visibility.FACE_DOWN]
            elif card_state == "face up":
                hole_cards = [card for card in hole_cards if card.visibility == Visibility.FACE_UP]
            else:
                logger.warning(f"Invalid cardState '{card_state}' for player {player.id}")
                return [], []            
            logger.debug(f"Filtered hole cards to {card_state}: {len(hole_cards)} cards remaining")
            if not hole_cards and "minimumCards" not in showdown_rules:
                logger.warning(f"No {card_state} cards available for player {player.id}")
                return [], []            
            
        if not hole_cards and "minimumCards" in showdown_rules:
            minimum_cards = showdown_rules["minimumCards"]
            if minimum_cards > 0:
                logger.warning(f"Player {player.id} has 0 cards, needs {minimum_cards} to qualify")
                return [], []
            # Handle 0-card variants
            if "zeroCardsPipValue" in showdown_rules and eval_type.startswith("low_pip"):
                # For low pip evaluation, return an empty hand with a pip value
                # The evaluator will use zeroCardsPipValue (e.g., 0 for best low)
                return [], []
        
        # # If no community cards exist (e.g., Stud), use hole cards only
        # if not community_cards:
        #     logger.debug(f"No community cards available for {player.id}, using hole cards only")
        #     comm_cards = []
        # else:
        #     comm_subset = showdown_rules.get("community_subset", "default")
        #     comm_cards = community_cards.get(comm_subset, [])
        #     if not comm_cards and comm_subset != "default":
        #         logger.warning(f"Community subset '{comm_subset}' not found for player {player.id}")

        # Get community cards
        comm_cards = community_cards.get(community_subset, []) if community_cards else []
        if not comm_cards and community_subset != "default":
            logger.warning(f"Community subset '{community_subset}' not found for player {player.id}")

        # Apply wild cards if present
        if "wildCards" in showdown_rules:
            self.apply_wild_cards(player, comm_cards=comm_cards, wild_rules=showdown_rules["wildCards"])

        best_hand = None
        best_used_hole_cards = []

        # Handle new "combinations" syntax under "bestHand"
        if "combinations" in showdown_rules:
            for combo in showdown_rules["combinations"]:
                required_hole = combo["holeCards"]
                required_community = combo["communityCards"]

                # Skip if not enough cards available
                if len(hole_cards) < required_hole or len(comm_cards) < required_community:
                    logger.debug(
                        f"Skipping combo for {player.id}: {required_hole} hole, "
                        f"{required_community} comm (have {len(hole_cards)} hole, {len(comm_cards)} comm)"
                    )
                    continue

                # Generate all possible combinations for this requirement
                hole_combos = (
                    [tuple()] if required_hole == 0 
                    else list(itertools.combinations(hole_cards, required_hole))
                )
                comm_combos = (
                    [tuple()] if required_community == 0 
                    else list(itertools.combinations(comm_cards, required_community))
                )

                # Try each combination
                for hole_combo in hole_combos:
                    for comm_combo in comm_combos:
                        hand = list(hole_combo) + list(comm_combo)
                        if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand
                            best_used_hole_cards = list(hole_combo)

            if best_hand:
                return best_hand, best_used_hole_cards
            else:
                logger.warning(f"No valid hand combinations for player {player.id}")
                return [], []
                       
        # Handle different types of hand compositions
        if "anyCards" in showdown_rules:
            total_cards = showdown_rules["anyCards"]
            allowed_combinations = showdown_rules.get("holeCardsAllowed", [])
            all_cards = hole_cards + comm_cards

            if allowed_combinations:
                # Evaluate each allowed combination
                for combo in allowed_combinations:
                    subset_cards = []
                    for subset_name in combo["hole_subsets"]:
                        subset_cards.extend(player.hand.get_subset(subset_name))
                    all_cards = subset_cards + comm_cards
                    if len(all_cards) >= total_cards:
                        for hand_combo in itertools.combinations(all_cards, total_cards):
                            hand = list(hand_combo)
                            if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                                best_hand = hand            
                                best_used_hole_cards = [c for c in hand if c in hole_cards]

            else:
                if len(all_cards) >= total_cards:
                    for hand_combo in itertools.combinations(all_cards, total_cards):
                        hand = list(hand_combo)
                        if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand
                            best_used_hole_cards = [c for c in hand if c in hole_cards]
            
            # If there are no community cards or exactly the right number of hole cards,
            # we can just use the hole cards (straight poker case)
            if not comm_cards and len(hole_cards) == total_cards:
                return hole_cards, hole_cards
            
            # if we are padding, then don't check the length of all_cards against total_cards
            # because we want to allow padding to fill in the gaps
            if len(all_cards) < total_cards and not padding:
                # Not enough cards total
                logger.warning(
                    f"Not enough cards for player {player.id}: "
                    f"Has {len(hole_cards)} hole cards and {len(comm_cards)} community cards "
                    f"(need {total_cards} total)"
                )
                return [], []
            return best_hand or [], best_used_hole_cards
                   
        # Handle cases with multiple possible combinations of hole and community cards
        elif "holeCards" in showdown_rules and isinstance(showdown_rules["holeCards"], list):
            hole_options = showdown_rules["holeCards"]
            comm_options = showdown_rules.get("communityCards", [])
            
            # If communityCards is a single value, convert it to a list for consistency
            if isinstance(comm_options, int):
                comm_options = [comm_options]
            
            # Try each valid combination of hole and community card counts
            for i, required_hole in enumerate(hole_options):
                # For each hole card option, get the corresponding community card option
                # If comm_options is shorter than hole_options, use the last value
                comm_index = min(i, len(comm_options) - 1) if comm_options else 0
                required_community = comm_options[comm_index] if comm_options else 0
                
                # Skip if we don't have enough cards
                if len(hole_cards) < required_hole or len(comm_cards) < required_community:
                    continue
                
                # Generate combinations for this option
                hole_combos = list(itertools.combinations(hole_cards, required_hole))
                community_combos = [tuple()] if required_community == 0 else list(itertools.combinations(comm_cards , required_community))
                
                # Try all combinations for this option
                for hole_combo in hole_combos:
                    for comm_combo in community_combos:
                        # Combine the two sets of cards
                        hand = list(hole_combo) + list(comm_combo)
                        
                        # Compare with our best hand so far
                        if best_hand is None:
                            best_hand = hand
                        else:
                            if evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                                best_hand = hand
                                best_used_hole_cards = list(hole_combo)

            # If we found a valid hand, return it
            if best_hand:
                return best_hand, best_used_hole_cards
            else:
                logger.warning(
                    f"No valid hand combinations for player {player.id}"
                )
                return [], []         
            
        # Handle cases with community card combinations
        elif "holeCards" in showdown_rules and "communityCardCombinations" in showdown_rules:
            combinations = showdown_rules["communityCardCombinations"]
            required_hole = showdown_rules.get("holeCards", 0)
            total_cards = showdown_rules.get("totalCards", 5)  # Default to 5 if not specified
            required_community = total_cards - required_hole

            for combo in combinations:
                # Collect cards from all subsets in this combination
                comm_cards = []
                for subset in combo:
                    if subset not in community_cards:
                        logger.debug(f"Subset '{subset}' not available for combination {combo} for player {player.id}")
                        break
                    comm_cards.extend(community_cards[subset])
                else:  # Proceed only if all subsets were found (no break occurred)
                    if len(comm_cards) < required_community:
                        logger.warning(f"Combination {combo} has {len(comm_cards)} cards, need {required_community} for player {player.id}")
                        continue

                    # Generate combinations
                    hole_combos = list(itertools.combinations(hole_cards, required_hole))
                    community_combos = list(itertools.combinations(comm_cards, required_community))

                    # Evaluate all combinations for this combination
                    for hole_combo in hole_combos:
                        for comm_combo in community_combos:
                            hand = list(hole_combo) + list(comm_combo)
                            if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                                best_hand = hand  
                                best_used_hole_cards = list(hole_combo)                            

            logger.debug(f'Best hand found for player {player.id} using showdown rules: {best_hand}')
            return best_hand if best_hand else [], best_used_hole_cards

        # Handle cases with specific requirements for hole and/or community cards
        elif "holeCards" in showdown_rules or "communityCards" in showdown_rules:
            logger.debug(f"Evaluating showdown rules for player {player.id} with hole cards: {hole_cards} and community cards: {comm_cards}")
            # Get requirements (default to 0 if not specified)
            required_hole = showdown_rules.get("holeCards", 0)
            required_community = showdown_rules.get("communityCards", 0)
            allowed_combinations = showdown_rules.get("holeCardsAllowed", [])  # Add support for holeCardsAllowed

            # Special case for "all" hole cards
            if required_hole == "all":
                required_hole = len(hole_cards)  # Use all available hole cards
                # Dynamically calculate community cards based on eval_type hand size
                total_cards_needed = HAND_SIZES.get(eval_type, 5)  # Default to 5 if eval_type not found
                # Cap by available community cards
                required_community = min(max(0, total_cards_needed - required_hole), len(comm_cards))
            else:
                required_hole = int(required_hole)  # Ensure numeric for other cases

            logger.debug(
                f"Required hole cards: {required_hole}, Required community cards: {required_community} "
                f"(player {player.id} has {len(hole_cards)} hole and {len(comm_cards)} community)"
            )

            # Filter hole cards based on allowed subsets if specified
            if allowed_combinations:
                usable_hole_cards = []
                for combo in allowed_combinations:
                    for subset_name in combo["hole_subsets"]:
                        usable_hole_cards.extend(player.hand.get_subset(subset_name))
                hole_cards = usable_hole_cards  # Restrict to allowed subsets
            else:
                hole_cards = hole_cards  # Use all hole cards if no restriction            
            
            # Ensure we have enough cards to evaluate (if padding, we will get enough so OK)
            if (len(hole_cards) < required_hole or len(comm_cards) < required_community) and not padding:
                logger.warning(
                    f"Not enough cards for player {player.id}: "
                    f"Has {len(hole_cards)} hole cards (need {required_hole}) and "
                    f"{len(comm_cards)} community cards (need {required_community})"
                )
                return [], []
            
            # Generate combinations only for categories with requirements > 0
            # use the minimum of the cards we have and the required list, since padding will take care of the rest
            hole_combos = [tuple()] if required_hole == 0 else list(itertools.combinations(hole_cards, min(len(hole_cards),required_hole)))
            community_combos = [tuple()] if required_community == 0 else list(itertools.combinations(comm_cards, required_community))
            
            # Try all combinations and find the best
            for hole_combo in hole_combos:
                for comm_combo in community_combos:                 
                    # Combine the two sets of cards
                    hand = list(hole_combo) + list(comm_combo)
                    
                    # Compare with our best hand so far
                    if best_hand is None:
                        best_hand = hand
                    else:
                        # Use compare_hands to determine which is better
                        if evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand
                            best_used_hole_cards = list(hole_combo)
            
            logger.debug(f'Best hand found for player {player.id} using showdown rules: {best_hand}')
            return best_hand if best_hand else [], best_used_hole_cards
              
        # Default: just use all hole cards
        return hole_cards, hole_cards


    def _find_winners(
        self,
        players: List[Player],
        player_hands: Dict[str, HandResult],
        eval_type: EvaluationType,
        showdown_rules: dict
    ) -> List[Player]:
        """Find best hand(s) among players."""
        if not players or not player_hands:
            return []
            
        # Get classification priority from showdown rules
        classification_priority = showdown_rules.classification_priority
        classification_field = "face_butt"  # Default field name from bestHand classification        
        
        # Helper to get classification rank
        def get_classification_rank(hand_result: HandResult) -> int:
            if not classification_priority:
                return 0
            logger.debug(f"Hand Result: {hand_result}")
            classification = hand_result.classifications.get(classification_field, "butt")
            try:
                return classification_priority.index(classification)
            except ValueError:
                return len(classification_priority)  # Unknown classification is worst
                
        # Get first player as initial best
        best_players = [players[0]]
        best_hand_result = player_hands[players[0].id]
        best_classification_rank = get_classification_rank(best_hand_result)
        
        # Compare against other players
        for player in players[1:]:
            if player.id not in player_hands:
                continue
                
            current_hand_result = player_hands[player.id]
            current_classification_rank = get_classification_rank(current_hand_result)
           
            # Compare by classification first
            if current_classification_rank < best_classification_rank:
                # Current hand has a better classification (e.g., "face" vs "butt")
                best_players = [player]
                best_hand_result = current_hand_result
                best_classification_rank = current_classification_rank
            elif current_classification_rank == best_classification_rank:
                # Same classification, compare by rank
                comparison = evaluator.compare_hands(
                    current_hand_result.cards,
                    best_hand_result.cards,
                    eval_type
                )
                if comparison > 0:  # Current hand better
                    best_players = [player]
                    best_hand_result = current_hand_result
                elif comparison == 0:  # Tie
                    best_players.append(player)
                
        return best_players        

    