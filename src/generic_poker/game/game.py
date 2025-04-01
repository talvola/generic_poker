"""Core game implementation controlling game flow."""
import logging
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple, Set

from generic_poker.config.loader import GameRules, GameActionType
from generic_poker.game.table import Table, Player, Position
from generic_poker.game.betting import (
    BettingManager, LimitBettingManager, create_betting_manager,
    BettingStructure, BetType, PlayerBet
)
from generic_poker.game.bringin import BringInDeterminator, CardRule
from generic_poker.core.card import Card, Visibility, WildType, Rank
from generic_poker.evaluation.evaluator import EvaluationType, evaluator

from generic_poker.evaluation.constants import HAND_SIZES

logger = logging.getLogger(__name__)


class GameState(Enum):
    """Possible states of the game."""
    WAITING = "waiting"  # Waiting for players
    DEALING = "dealing"  # Cards being dealt
    BETTING = "betting"  # Betting round in progress
    DRAWING = "drawing"  # Draw/discard in progress
    SHOWDOWN = "showdown"  # Final showdown
    COMPLETE = "complete"  # Hand complete


class PlayerAction(Enum):
    """Actions a player can take."""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    BRING_IN = "bring_in" 
    DISCARD = "discard" # simplified discard only
    DRAW = "draw" # really more general discard and then draw
    SEPARATE  = "separate"  # separate hand into subsets
    EXPOSE  = "expose"  # expose down cards (make face up)
    PASS = "pass"  # New player action

@dataclass
class ActionResult:
    """Result of a player action."""
    success: bool
    error: Optional[str] = None
    state_changed: bool = False

@dataclass
class PotResult:
    """Information about a pot and its winner(s)."""
    amount: int  # Amount in the pot
    winners: List[str]  # List of player IDs who won this pot
    split: bool = False  # Whether the pot was split (multiple winners)
    pot_type: str = "main"  # "main" or "side"
    hand_type: str = "Hand"  # from game config showdown
    side_pot_index: Optional[int] = None  # Index of side pot if applicable
    eligible_players: Set[str] = None  # Players who could win this pot
    
    def __post_init__(self):
        if self.eligible_players is None:
            self.eligible_players = set()
        self.split = len(self.winners) > 1
        
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
        if self.split:
            return f"{pot_name}: ${self.amount} - Split between {winners_str} (${self.amount_per_player} each)"
        else:
            return f"{pot_name}: ${self.amount} - Won by {winners_str}"  

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
            "amount_per_player": self.amount_per_player
        }
    
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
    rank: int = 0  # Internal rank value (lower is better for low games)
    
    def __str__(self) -> str:
        """String representation of the hand result."""
        cards_str = ", ".join(str(card) for card in self.cards)
        return f"Player {self.player_id}: {self.hand_description} ({cards_str})"
    
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
            "rank": self.rank
        }    

@dataclass
class GameResult:
    """Complete results of a poker hand."""
    pots: List[PotResult]  # Results for each pot
    hands: Dict[str, HandResult]  # Hand results by player ID
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
            for hand in player_hands:
                hand_type = getattr(hand, 'hand_type', 'Unspecified')
                if hand_type not in all_hands_by_type:
                    all_hands_by_type[hand_type] = []
                all_hands_by_type[hand_type].append(hand)
        
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
            # Find hands that aren't in the winning hands
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
        min_buyin: int = 0,
        max_buyin: int = 0,
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
            
        self.rules = rules
        self.table = Table(
            max_players=rules.max_players,
            min_buyin=min_buyin,
            max_buyin=max_buyin
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
        
        self.state = GameState.WAITING
        self.current_step = -1  # Not started
        self.current_player: Optional[str] = None  # ID of player to act
        self.current_substep = None  # None for non-grouped steps, integer for grouped substeps       
    
        self.last_hand_result = None  # Store the last hand result here

        self.pending_exposures: Dict[str, List[Card]] = {}  # player_id -> list of cards to expose
        self.current_expose_config = None  # To store the expose config during the step        
        self.pending_passes: Dict[str, Tuple[Card, str]] = {}  # player_id -> (card, recipient_id)
        self.current_pass_config = None        

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
        self.betting.new_round(preserve_current_bet=False)

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

    def get_valid_actions(self, player_id: str) -> List[Tuple[PlayerAction, Optional[int], Optional[int]]]:
            """
            Get list of valid actions for a player.
            
            Args:
                player_id: ID of player to check
                
            Returns:
                List of tuples (action, min_amount, max_amount) where amounts are None
                if not applicable (like for fold/check)
                
            Example:
                For betting actions:

                [(PlayerAction.FOLD, None, None),
                (PlayerAction.CALL, 10, 10),
                (PlayerAction.RAISE, 20, 100)]

                For discard / draw actions:

                [(PlayerAction.DISCARD, 1, 1)] 
            """
            if player_id != self.current_player.id:  
                logger.info(f"Not this player's turn ({player_id} vs {self.current_player.id})")
                return []  # Not this player's turn 

            step = self.rules.gameplay[self.current_step]
            config = step.action_config  # Dict for regular steps, List for grouped steps                
                
            # Handle grouped actions
            if step.action_type == GameActionType.GROUPED:
                if self.current_substep is None or self.current_substep >= len(config):
                    logger.warning(f"Invalid substep {self.current_substep} for grouped step {step.name}")
                    return []
                subaction = config[self.current_substep]
                subaction_key = list(subaction.keys())[0]  # e.g., "bet", "discard"
                
                if subaction_key == "bet":
                    if self.state != GameState.BETTING:
                        return []
                    bet_config = subaction["bet"]
                    player = self.table.players[player_id]
                    current_bet = self.betting.current_bets.get(player_id, PlayerBet()).amount
                    required_bet = self.betting.get_required_bet(player_id)
                    valid_actions = []
                    
                    if bet_config.get("type") == "bring-in":
                        valid_actions.append((PlayerAction.BRING_IN, self.bring_in, self.bring_in))
                        if player.stack >= self.small_bet:
                            valid_actions.append((PlayerAction.BET, self.small_bet, self.small_bet))
                        elif player.stack > self.bring_in:
                            valid_actions.append((PlayerAction.BET, player.stack, player.stack))
                        return valid_actions
                    
                    logger.debug(f"Player: {player_id}, Required Bet: {required_bet}, Current Bet: {current_bet}")
                    logger.debug(f"  Stack: {player.stack}")
                    
                    valid_actions.append((PlayerAction.FOLD, None, None))
                    if required_bet > 0:
                        if player.stack >= required_bet:
                            valid_actions.append((PlayerAction.CALL, self.betting.current_bet, self.betting.current_bet))
                        elif player.stack > 0:
                            total_amount = current_bet + player.stack
                            valid_actions.append((PlayerAction.CALL, total_amount, total_amount))
                    else:
                        valid_actions.append((PlayerAction.CHECK, None, None))
                    
                    zero_cards_betting = bet_config.get("zeroCardsBetting")
                    hole_cards = player.hand.get_cards()
                    if zero_cards_betting == "call_only" and len(hole_cards) == 0:
                        logger.debug(f"Zero cards betting mode is 'call_only' for substep")
                        return valid_actions
                    
                    if player.stack > required_bet:
                        current_total = self.betting.current_bet
                        is_stud = self.rules.forced_bets.style == "bring-in"
                        step_type = bet_config.get("type", "small")
                        bet_size = self.small_bet if step_type == "small" else self.big_bet
                        
                        active_players = [p for p in self.table.get_position_order() if p.is_active]
                        bring_in_idx = next((i for i, p in enumerate(active_players) if self.betting.current_bets.get(p.id, PlayerBet()).posted_blind), -1)
                        acted_count = sum(1 for b in self.betting.current_bets.values() if b.has_acted or b.posted_blind)
                        is_first_after_bring_in = (is_stud and step_type == "small" and bring_in_idx != -1 and 
                                                active_players[(bring_in_idx + 1) % len(active_players)].id == player_id and
                                                acted_count <= 1)
                        
                        if is_first_after_bring_in:
                            action = PlayerAction.BET
                            min_amount = self.small_bet
                            max_amount = min_amount if self.betting_structure == BettingStructure.LIMIT else self.betting.get_max_bet(player_id, BetType.SMALL, player.stack)
                        elif current_total == 0:
                            action = PlayerAction.BET
                            min_amount = bet_size
                            max_amount = min_amount if self.betting_structure == BettingStructure.LIMIT else self.betting.get_max_bet(player_id, BetType.SMALL if step_type == "small" else BetType.BIG, player.stack)
                        else:
                            action = PlayerAction.RAISE
                            min_amount = self.betting.get_min_raise(player_id)
                            max_amount = min_amount if self.betting_structure == BettingStructure.LIMIT else self.betting.get_max_bet(player_id, BetType.BIG, player.stack)
                        
                        if player.stack >= min_amount:
                            valid_actions.append((action, min_amount, max_amount))
                        else:
                            all_in_amount = player.stack + current_bet
                            valid_actions.append((action, all_in_amount, all_in_amount))
                    
                    logger.debug(f"Valid actions for {player_id}: {valid_actions}")
                    return valid_actions
                
                elif subaction_key == "discard" and self.state == GameState.DRAWING:
                    card_config = subaction["discard"]["cards"][0]
                    max_discard = card_config.get("number", 0)
                    min_discard = card_config.get("min_number", max_discard)  # Default to max if min not specified
                    return [(PlayerAction.DISCARD, min_discard, max_discard)]
                
                elif subaction_key == "draw" and self.state == GameState.DRAWING:
                    card_config = subaction["draw"]["cards"][0]
                    max_discard = card_config.get("number", 0)
                    min_discard = card_config.get("min_number", 0)
                    return [(PlayerAction.DRAW, min_discard, max_discard)]
                
                elif subaction_key == "separate" and self.state == GameState.DRAWING:
                    total_cards = sum(cfg["number"] for cfg in subaction["separate"]["cards"])
                    return [(PlayerAction.SEPARATE, total_cards, total_cards)]
                
                elif subaction_key == "expose" and self.state == GameState.DRAWING:
                    total_cards = sum(cfg["number"] for cfg in subaction["expose"]["cards"])
                    return [(PlayerAction.EXPOSE, total_cards, total_cards)]
                
                elif subaction_key == "pass" and self.state == GameState.DRAWING:
                    config = subaction["pass"]["cards"][0]
                    num_to_pass = config["number"]
                    return [(PlayerAction.PASS, num_to_pass, num_to_pass)]
                
                return []  # Invalid state or sub-action
                    
            # For discard state, return discard actions
            if self.state == GameState.DRAWING:
                is_discard = getattr(self, "current_discard_config", None) is not None
                is_draw = getattr(self, "current_draw_config", None) is not None
                is_separate = getattr(self, "current_separate_config", None) is not None
                is_expose = getattr(self, "current_expose_config", None) is not None
                is_pass = getattr(self, "current_pass_config", None) is not None

                # discard is the simpler case
                if is_discard:
                    card_config = self.current_discard_config["cards"][0]
                    # for now, the discard config only specifies one number, so use for both min and max discard value
                    max_discard = card_config.get("number", 0)
                    min_discard = card_config.get("number", 0)          
                    return [(PlayerAction.DISCARD, min_discard, max_discard)]
                elif is_draw:
                    card_config = self.current_draw_config["cards"][0]
                    max_discard = card_config.get("number", 0)
                    min_discard = card_config.get("min_number", 0)
                    return [(PlayerAction.DRAW, min_discard, max_discard)]
                elif is_separate:
                    total_cards = sum(cfg["number"] for cfg in self.current_separate_config["cards"])
                    return [(PlayerAction.SEPARATE, total_cards, total_cards)]
                elif is_expose:
                    total_cards = sum(cfg["number"] for cfg in self.current_expose_config["cards"])
                    return [(PlayerAction.EXPOSE, total_cards, total_cards)]
                elif is_pass:
                    config = self.current_pass_config["cards"][0]
                    num_to_pass = config["number"]
                    return [(PlayerAction.PASS, num_to_pass, num_to_pass)]                
                                                    
            if self.state != GameState.BETTING:
                return []  # Not betting phase
                
            player = self.table.players[player_id]
            current_bet = self.betting.current_bets.get(player_id, PlayerBet()).amount
            required_bet = self.betting.get_required_bet(player_id)
            
            valid_actions = []
            step = self.rules.gameplay[self.current_step]           

            if step.action_config["type"] == "bring-in":
                valid_actions.append((PlayerAction.BRING_IN, self.bring_in, self.bring_in))
                if player.stack >= self.small_bet:
                    valid_actions.append((PlayerAction.BET, self.small_bet, self.small_bet))
                elif player.stack > self.bring_in:
                    valid_actions.append((PlayerAction.BET, player.stack, player.stack))
                return valid_actions
    
    
            logger.debug(f"Player: {player_id}, Required Bet: {required_bet}, Current Bet: {current_bet}")
            logger.debug(f"  Stack: {player.stack}")   

            # Always allow folding (even if player could check)
            valid_actions.append((PlayerAction.FOLD, None, None))            
            
            # CALL if player has enough chips
            if required_bet > 0:
                if player.stack >= required_bet:
                    valid_actions.append((PlayerAction.CALL, self.betting.current_bet, self.betting.current_bet))
                elif player.stack > 0:
                    # ✅ Allow all-in call for less than required bet
                    # For all-in, the total would be current_bet + stack
                    total_amount = current_bet + player.stack
                    valid_actions.append((PlayerAction.CALL, total_amount, total_amount))
            else:
                valid_actions.append((PlayerAction.CHECK, None, None))

            # default to None
            zero_cards_betting = step.action_config["zeroCardsBetting"] if "zeroCardsBetting" in step.action_config else None
            hole_cards = player.hand.get_cards()

            if zero_cards_betting is not None and zero_cards_betting == "call_only" and len(hole_cards) == 0:
                    logger.debug(f"Zero cards betting mode is 'call_only' for step {self.current_step}. Only allowing call or check.")
                    logger.debug(f"Valid actions for {player_id}: {valid_actions}")
                    return valid_actions  # Only allow call in zero cards betting mode
            else:
                # Determine possible BET or RAISE
                if player.stack > required_bet:
                    current_total = self.betting.current_bet
                    is_stud = self.rules.forced_bets.style == "bring-in"
                    step_type = step.action_config["type"]
                    bet_size = self.small_bet if step_type == "small" else self.big_bet
                        
                    active_players = [p for p in self.table.get_position_order() if p.is_active]
                    bring_in_idx = next((i for i, p in enumerate(active_players) if self.betting.current_bets.get(p.id, PlayerBet()).posted_blind), -1)
                    acted_count = sum(1 for b in self.betting.current_bets.values() if b.has_acted or b.posted_blind)
                    is_first_after_bring_in = (is_stud and step_type == "small" and bring_in_idx != -1 and 
                                            active_players[(bring_in_idx + 1) % len(active_players)].id == player_id and
                                            acted_count <= 1)

                    current_bet = self.betting.current_bets.get(player_id, PlayerBet()).amount

                    if is_first_after_bring_in:
                        # First player after bring-in in limit Stud
                        logger.debug(f"First player after bring-in")   
                        action = PlayerAction.BET  # Or COMPLETE if added
                        min_amount = self.small_bet  # 10
                        max_amount = min_amount if self.betting_structure == BettingStructure.LIMIT else self.betting.get_max_bet(player_id, BetType.SMALL, player.stack)
                        logger.debug(f"  BET min_amount: {min_amount}")   
                        logger.debug(f"  BET max_amount: {max_amount}") 
                    elif current_total == 0:
                        action = PlayerAction.BET
                        #min_amount = self.betting.get_min_bet(player_id, BetType.BIG)
                        min_amount = bet_size  # 10 for "small", 20 for "big"
                        max_amount = min_amount if self.betting_structure == BettingStructure.LIMIT else self.betting.get_max_bet(player_id, BetType.SMALL if step_type == "small" else BetType.BIG, player.stack)
                        logger.debug(f"  BET min_amount: {min_amount}")   
                        logger.debug(f"  BET max_amount: {max_amount}")   
                    else:
                        action = PlayerAction.RAISE
                        min_amount = self.betting.get_min_raise(player_id)
                    # max_amount = self.betting.get_max_bet(player_id, BetType.BIG, player.stack)  
                        max_amount = min_amount if self.betting_structure == BettingStructure.LIMIT else self.betting.get_max_bet(player_id, BetType.BIG, player.stack)
                        logger.debug(f"  RAISE min_amount: {min_amount}")   
                        logger.debug(f"  RAISE max_amount: {max_amount}")                                    

                    # moved to above
                    # max_amount = self.betting.get_max_bet(player_id, BetType.BIG, player.stack)

                    logger.debug(f"Player: {player_id}, Required Bet: {required_bet}, Current Total: {current_total}")
                    logger.debug(f"Min Amount: {min_amount}, Max Amount: {max_amount}")                
                    
                    # ✅ Normal raise if player has enough chips
                    #if player.stack + current_bet >= min_amount:
                    if player.stack >= min_amount:
                        valid_actions.append((action, min_amount, max_amount))
                    else:
                        # All-in raise if stack can't meet min raise
                        all_in_amount = player.stack + current_bet
                        valid_actions.append((action, all_in_amount, all_in_amount))        
                  
            logger.debug(f"Valid actions for {player_id}: {valid_actions}")
            return valid_actions        
        
    def _is_first_betting_round(self):
        for i, step in enumerate(self.rules.gameplay):
            if step.action_type == GameActionType.BET and step.action_config.get("type") == "small":
                return i == self.current_step
            elif step.action_type == GameActionType.GROUPED:
                for j, subaction in enumerate(step.action_config):
                    if "bet" in subaction and subaction["bet"].get("type") == "small":
                        return i == self.current_step and self.current_substep == j
        return False
        
    def player_action(
            self,
            player_id: str,
            action: PlayerAction,
            amount: int = 0,
            cards: Optional[List[Card]] = None  # New parameter for discard
        ) -> ActionResult:
            """
            Handle a player action.
            
            Args:
                player_id: ID of acting player
                action: Action being taken
                amount: Bet amount if applicable
                
            Returns:
                Result of the action
            """
            player = self.table.players[player_id]
            logger.info(f"Processing action from {player.name}: {action.value}")
            
            # Check if it's this player's turn
            if player_id != self.current_player.id:  # Compare with Player object's id
                logger.warning(f"Invalid action - not {player.name}'s turn")
                return ActionResult(
                    success=False,
                    error="Not your turn"
                )
                
            # Get the current step
            step = self.rules.gameplay[self.current_step]

            # Handle grouped actions
            if step.action_type == GameActionType.GROUPED:
                subactions = step.action_config  # List of sub-action configs
                if not hasattr(self, 'grouped_step_completed'):
                    self.grouped_step_completed = set()  # Players who’ve completed initial bet
                    self.discard_completed = set()  # Players who’ve discarded (for oncePerStep)

                current_subaction = subactions[self.current_substep]
                subaction_key = list(current_subaction.keys())[0]  # e.g., "bet", "discard"

                logger.debug(f"Current subaction: {subaction_key} for {player.name}") 

                # Process the current sub-action
                if "bet" in subaction_key and action in [PlayerAction.CHECK, PlayerAction.CALL, PlayerAction.BET, PlayerAction.RAISE, PlayerAction.FOLD]:
                    if self.state != GameState.BETTING:
                        return ActionResult(success=False, error="Cannot bet in current state")
                    if action == PlayerAction.FOLD:
                        player.is_active = False
                        bet = self.betting.current_bets.get(player_id, PlayerBet())
                        bet.has_acted = True

                        # Check if only one player remains
                        if len(active_players) == 1:
                            self._handle_fold_win(active_players)
                            return ActionResult(success=True, state_changed=True)      
                    elif action == PlayerAction.CHECK:
                        current_bet = self.betting.current_bets.get(player_id, PlayerBet())
                        required_bet = self.betting.get_required_bet(player_id)      

                        if required_bet > 0:
                            logger.warning(f"{player.name} cannot check - must call ${required_bet}")
                            return ActionResult(
                                success=False,
                                error="Cannot check - must call or fold"
                            )    
                        
                        current_bet.has_acted = True  # Mark them as having acted
                        self.betting.current_bets[player_id] = current_bet  # Record check  

                    elif action == PlayerAction.CALL:
                        call_amount = self.betting.get_required_bet(player_id)
                        current_bet = self.betting.current_bets.get(player_id, PlayerBet())
                        total_bet = self.betting.current_bet  # Target amount       

                        # Handle all-in calls
                        if call_amount > player.stack:
                            call_amount = player.stack
                            total_bet = current_bet.amount + call_amount
                            logger.info(f"{player.name} calls all-in for ${call_amount}")
                        else:
                            logger.info(f"{player.name} calls ${call_amount}")                                         

                        # Place the total bet amount
                        self.betting.place_bet(player_id, total_bet, player.stack)
                        player.stack -= call_amount  # Deduct only the additional amount needed

                    # unlikely this would be part of a nested run, but for completeness
                    elif action == PlayerAction.BRING_IN:
                        valid_actions = self.get_valid_actions(player_id)
                        valid_bet = next((a for a in valid_actions if a[0] == PlayerAction.BRING_IN), None)
                        if not valid_bet or amount != valid_bet[1]:
                            return ActionResult(success=False, error=f"Invalid bring-in amount: ${amount}")
                        logger.info(f"{player.name} brings in for ${amount}")
                        self.betting.place_bet(player_id, amount, player.stack, is_forced=True)
                        player.stack -= amount  # Already deducted additional amount

                    else: # BET, RAISE
                        # Validate bet/raise amount
                        valid_actions = self.get_valid_actions(player_id)
                        valid_bet = next((a for a in valid_actions if a[0] == action), None)
                        if not valid_bet or (action in [PlayerAction.BET, PlayerAction.RAISE] and amount not in range(valid_bet[1], valid_bet[2] + 1)):
                            return ActionResult(success=False, error=f"Invalid bet action or amount: ${amount}")
                        
                        current_bet = self.betting.current_bets.get(player_id, PlayerBet())
                        current_ante = self.betting.pot.total_antes.get(f"round_{self.betting.pot.current_round}_{player_id}", 0)
                        
                        # Adjust for all-in
                        if amount >= player.stack:  # Changed from > to >=
                            logger.info(f"{player.name} is going all-in with ${player.stack}")
                            amount = player.stack + current_bet.amount  # Include what's already in
                            additional = player.stack  # Take entire remaining stack   
                        else:
                            # Normal raise
                            # Ante is included in current_bet, but not in the amount, so need to adjust
                            additional = amount - current_bet.amount + current_ante                  

                        if additional > player.stack:
                            return ActionResult(
                                success=False,
                                error="Not enough chips to complete this action"
                            )
                        
                        # I don't understand the logic here - need to test stud games and blind games
                        #bet_type = BetType.SMALL if (self.rules.forced_bets.style == "bring-in" and 
                        #                        current_subaction["type"] == "small") else BetType.BIG   
                        logger.debug(f"Current subaction: {current_subaction}")
                        bet_type = BetType.SMALL if current_subaction["bet"]["type"] == "small" else BetType.BIG
                                                                   
                        self.betting.place_bet(player_id, amount, player.stack, bet_type=bet_type)
                        player.stack -= additional

                    # Advance player after every bet
                    active_players = set(p.id for p in self.table.get_active_players())
                    if player_id not in self.grouped_step_completed:
                        self.grouped_step_completed.add(player_id)
                        self.current_substep += 1  # Move to discard for initial bet
                    else:
                        # Additional betting, stay at substep 0
                        self.current_player = self.next_player(round_start=False)
                        if self.betting.round_complete() and self.grouped_step_completed == active_players:
                            logger.info(f"Grouped step {step.name} complete")
                            if self.auto_progress:
                                self._next_step()
                            for attr in ["current_discard_config", "current_draw_config", "current_separate_config", "current_expose_config", "current_pass_config"]:
                                if hasattr(self, attr):
                                    delattr(self, attr)
                            delattr(self, 'discard_completed')
                            return ActionResult(success=True, state_changed=True)
                        return ActionResult(success=True)
               
                elif "discard" in subaction_key and action == PlayerAction.DISCARD:
                    if self.state != GameState.DRAWING:
                        return ActionResult(success=False, error="Cannot discard in current state")
                    discard_config = current_subaction["discard"]
                    once_per_step = discard_config["cards"][0].get("oncePerStep", False)     
                    if once_per_step and player_id in self.discard_completed:
                        return ActionResult(success=False, error="Discard already completed")   
                    if not cards and len(cards) > 0:  # Allow empty list for 0 discards
                        return ActionResult(success=False, error="No cards specified when required")                                                    
                    if not self._handle_discard_action(player, cards):
                        return ActionResult(success=False, error="Invalid discard action")
                    # Log discard completion
                    logger.info(f"{player.name} discards {len(cards)} cards: {cards}") 
                    self.discard_completed.add(player_id)
                    # Advance substep or player
                    self.current_substep += 1                    
                
                elif "draw" in subaction_key and action == PlayerAction.DRAW:
                    if self.state != GameState.DRAWING:
                        return ActionResult(success=False, error="Cannot draw in current state")
                    if not cards:
                        return ActionResult(success=False, error="No draw specified")
                    if not hasattr(self, '_handle_draw_action') or not self._handle_draw_action(player, cards):
                        return ActionResult(success=False, error="Draw action not supported")
                    # Log discard completion
                    logger.info(f"{player.name} draws {len(cards)} cards: {cards}")                     
                    # Advance substep or player
                    self.current_substep += 1   

                elif "separate" in subaction_key and action == PlayerAction.SEPARATE:
                    if self.state != GameState.DRAWING or not hasattr(self, "current_separate_config"):
                        return ActionResult(success=False, error="Cannot separate in current state")
                    if not cards:
                        return ActionResult(success=False, error="No cards specified")
                    if not self._handle_separate_action(player, cards):
                        return ActionResult(success=False, error="Invalid separation")
                    logger.info(f"{player.name} separates their cards: {cards}")                     
                    # Advance substep or player
                    self.current_substep += 1   

                elif "expose" in subaction_key and action == PlayerAction.EXPOSE:
                    if self.state != GameState.DRAWING or not hasattr(self, "current_expose_config"):
                        return ActionResult(success=False, error="Cannot expose in current state")
                    if not cards:
                        return ActionResult(success=False, error="No cards specified")
                    if not self._validate_expose_action(player, cards):
                        return ActionResult(success=False, error="Invalid exposure")
                    self.pending_exposures[player_id] = cards
                    logger.info(f"{player.name} exposes {len(cards)} cards: {cards}")                     
                    # Advance substep or player
                    self.current_substep += 1   

                elif "pass" in subaction_key and action == PlayerAction.PASS:
                    if self.state != GameState.DRAWING or not hasattr(self, "current_pass_config"):
                        return ActionResult(success=False, error="Cannot pass in current state")
                    if not cards:
                        return ActionResult(success=False, error="No cards specified")
                    if not self._validate_pass_action(player, cards):
                        return ActionResult(success=False, error="Invalid pass")
                    active_players = [p for p in self.table.players.values() if p.is_active]
                    current_idx = active_players.index(player)
                    recipient_idx = (current_idx + 1) % len(active_players)
                    recipient_id = active_players[recipient_idx].id
                    self.pending_passes[player_id] = (cards[0], recipient_id)
                    logger.info(f"{player.name} passes {len(cards)} cards: {cards}")                     
                    # Advance substep or player
                    self.current_substep += 1   

                else:
                    return ActionResult(success=False, error=f"Invalid action {action} for substep {subaction_key}")
                
                active_players = [p for p in self.table.players.values() if p.is_active]
                if self.current_substep >= len(subactions):
                    # Player completed all sub-actions
                    self.current_substep = 0
                    if self.betting.round_complete() and self.grouped_step_completed == active_players:
                        logger.info(f"Grouped step {step.name} complete")
                        if self.auto_progress:
                            self._next_step()
                        for attr in ["current_discard_config", "current_draw_config", "current_separate_config", "current_expose_config", "current_pass_config"]:
                            if hasattr(self, attr):
                                delattr(self, attr)
                        delattr(self, 'discard_completed')
                        return ActionResult(success=True, state_changed=True)
                    else:
                        # Move to next player, reset to betting if round incomplete
                        self.current_player = self.next_player(round_start=False)
                        first_subaction = subactions[0]
                        first_key = list(first_subaction.keys())[0]
                        if "bet" in first_key:
                            self.state = GameState.BETTING
                            bet_config = first_subaction["bet"]
                            if bet_config.get("type") not in ["antes", "blinds", "bring-in"] and not self.betting.round_complete():
                                is_first_betting_round = self._is_first_betting_round()
                                self.betting.new_round(is_first_betting_round)
                        elif "discard" in first_key:
                            self.state = GameState.DRAWING
                            self._setup_discard_round(first_subaction["discard"])
                        elif "draw" in first_key:
                            self.state = GameState.DRAWING
                            self._setup_draw_round(first_subaction["draw"])
                        elif "separate" in first_key:
                            self.state = GameState.DRAWING
                            self._setup_separate_round(first_subaction["separate"])
                        elif "expose" in first_key:
                            self.state = GameState.DRAWING
                            self._setup_expose_round(first_subaction["expose"])
                        elif "pass" in first_key:
                            self.state = GameState.DRAWING
                            self._setup_pass_round(first_subaction["pass"])         
                else:
                    # Move to next sub-action for current player
                    next_subaction = subactions[self.current_substep]
                    next_key = list(next_subaction.keys())[0]
                    if "bet" in next_key:
                        self.state = GameState.BETTING
                        bet_config = next_subaction["bet"]
                        if bet_config.get("type") not in ["antes", "blinds", "bring-in"]:
                            self.betting.new_round(self._is_first_betting_round())
                    elif "discard" in next_key:
                        self.state = GameState.DRAWING
                        self._setup_discard_round(next_subaction["discard"])      
                    elif "draw" in next_key:
                        self.state = GameState.DRAWING
                        self._setup_draw_round(next_subaction["draw"])
                    elif "separate" in next_key:
                        self.state = GameState.DRAWING
                        self._setup_separate_round(next_subaction["separate"])
                    elif "expose" in next_key:
                        self.state = GameState.DRAWING
                        self._setup_expose_round(next_subaction["expose"])
                    elif "pass" in next_key:
                        self.state = GameState.DRAWING
                        self._setup_pass_round(next_subaction["pass"])                                                                     

                return ActionResult(success=True)            

            # Handle discard / draw actions
            if action == PlayerAction.DISCARD or action == PlayerAction.DRAW:
                if self.state != GameState.DRAWING:
                    logger.warning(f"Invalid action - not drawing state: {self.state}")
                    return ActionResult(
                        success=False,
                        error="Cannot discard in current state"
                    )
                    
                if cards is None:
                    cards = []
                    
                # Make sure all cards are in player's hand
                for card in cards:
                    if card not in player.hand.cards:
                        logger.warning(f"{player.name} trying to discard card not in hand: {card}")
                        return ActionResult(
                            success=False,
                            error="Cannot discard card not in hand"
                        )
                
                # Process the discard
                if not self._handle_discard_action(player, cards):
                    return ActionResult(
                        success=False,
                        error="Invalid discard action"
                    )
                    
                # Move to next player
                self.current_player = self.next_player(round_start=False)
                
                # Check if discard round is complete
                if self._check_discard_round_complete():
                    logger.info("Discard round complete")
                    if self.auto_progress:
                        self._next_step()
                    return ActionResult(success=True, state_changed=True)
                    
                return ActionResult(success=True)
            
            if action == PlayerAction.SEPARATE:
                if self.state != GameState.DRAWING or not hasattr(self, "current_separate_config"):
                    return ActionResult(success=False, error="Cannot separate in current state")
                if not cards:
                    return ActionResult(success=False, error="No cards specified")
                
                if not self._handle_separate_action(player, cards):
                    return ActionResult(success=False, error="Invalid separation")
                
                self.current_player = self.next_player(round_start=False)
                if self._check_separate_round_complete():
                    logger.info("Separate round complete")
                    if self.auto_progress:
                        self._next_step()
                    return ActionResult(success=True, state_changed=True)
                return ActionResult(success=True)       
            
            if action == PlayerAction.EXPOSE:
                if self.state != GameState.DRAWING or not hasattr(self, "current_expose_config"):
                    return ActionResult(success=False, error="Cannot expose in current state")
                if not cards:
                    return ActionResult(success=False, error="No cards specified for exposure")
                
                # Validate the exposure choice
                if not self._validate_expose_action(player, cards):
                    return ActionResult(success=False, error="Invalid exposure")
                
                # Store the player's choice instead of flipping immediately
                self.pending_exposures[player_id] = cards
                logger.info(f"Player {player.name} selected {len(cards)} cards to expose (pending)")
                    
                # Move to the next player
                self.current_player = self.next_player(round_start=False)
                if self._check_expose_round_complete():
                    # All players have chosen; apply exposures simultaneously
                    self._apply_all_exposures()
                    logger.info("Expose round complete; all exposures applied")
                    if self.auto_progress:
                        self._next_step()  
                    return ActionResult(success=True, state_changed=True)
                return ActionResult(success=True)      
            
            if action == PlayerAction.PASS:
                if self.state != GameState.DRAWING or not hasattr(self, "current_pass_config"):
                    return ActionResult(success=False, error="Cannot pass in current state")
                if not cards:
                    return ActionResult(success=False, error="No cards specified for passing")
                
                # Validate the pass action
                if not self._validate_pass_action(player, cards):
                    return ActionResult(success=False, error="Invalid pass")
                
                # Determine the recipient (player to the left)
                active_players = [p for p in self.table.players.values() if p.is_active]
                current_idx = active_players.index(player)
                recipient_idx = (current_idx + 1) % len(active_players)  # Left is next player
                recipient_id = active_players[recipient_idx].id
                
                # Store the pass (assuming 1 card for simplicity)
                self.pending_passes[player_id] = (cards[0], recipient_id)
                logger.info(f"Player {player.name} selected {cards[0]} to pass to player {recipient_id} (pending)")

                # Move to the next player
                self.current_player = self.next_player(round_start=False)
                if self._check_pass_round_complete():
                    # All players have chosen; apply passes simultaneously
                    self._apply_all_passes()
                    logger.info("Pass round complete; all passes applied")
                    if self.auto_progress:
                        self._next_step()  # Move to next step (e.g., turn betting)
                    return ActionResult(success=True, state_changed=True)
                return ActionResult(success=True)            

            # the rest handle different betting actions     
                    
            if self.state != GameState.BETTING:
                logger.warning(f"Invalid action - not betting state: {self.state}")
                return ActionResult(
                    success=False,
                    error="Cannot act in current state"
                )
                
            try:
                if action == PlayerAction.FOLD:
                    logger.info(f"{player.name} folds")
                    player.is_active = False
                    # Update betting status
                    bet = self.betting.current_bets.get(player_id, PlayerBet())
                    bet.has_acted = True
                    
                    # Get active players after the fold
                    players = self.table.get_position_order()
                    active_players = [p for p in players if p.is_active]
                    
                    # Check if only one player remains
                    if len(active_players) == 1:
                        self._handle_fold_win(active_players)
                        return ActionResult(success=True, state_changed=True)
                        
                    self.current_player = self.next_player(round_start=False)
                    return ActionResult(success=True)
                    
                elif action == PlayerAction.CHECK:
                    # Get player's current bet amount
                    current_bet = self.betting.current_bets.get(player_id, PlayerBet())
                    required_bet = self.betting.get_required_bet(player_id)

                    logger.debug(f"Check validation for {player.name}:")
                    logger.debug(f"  - Player has bet: ${current_bet.amount}")
                    logger.debug(f"  - Current table bet: ${self.betting.current_bet}")
                    logger.debug(f"  - Required additional bet: ${required_bet}")
                    logger.debug(f"  - Bet details: acted={current_bet.has_acted}, blind={current_bet.posted_blind}")

                    if required_bet > 0:
                        logger.warning(f"{player.name} cannot check - must call ${required_bet}")
                        return ActionResult(
                            success=False,
                            error="Cannot check - must call or fold"
                        )                    
                        
                    logger.info(f"{player.name} checks")
                    current_bet.has_acted = True  # Mark them as having acted
                    self.betting.current_bets[player_id] = current_bet  # Record check

                    logger.debug(f"Current bets after check: {self.betting.current_bets}")

                    # Check if betting round is complete
                    if self.betting.round_complete():
                        logger.debug("Betting round complete after check")
                        if self.auto_progress:
                            self._next_step()
                        return ActionResult(success=True, state_changed=True)
                    
                    # Move to next player if round not complete
                    self.current_player = self.next_player(round_start=False)
                    return ActionResult(success=True)
                    
                elif action == PlayerAction.CALL:
                    call_amount = self.betting.get_required_bet(player_id)
                    current_bet = self.betting.current_bets.get(player_id, PlayerBet())
                    total_bet = self.betting.current_bet  # Target amount
                    
                    logger.debug(f"Processing call: required={call_amount}, total={total_bet}")
                    
                    # Handle all-in calls
                    if call_amount > player.stack:
                        call_amount = player.stack
                        total_bet = current_bet.amount + call_amount
                        logger.info(f"{player.name} calls all-in for ${call_amount}")
                    else:
                        logger.info(f"{player.name} calls ${call_amount}")
                  
                    # Place the total bet amount
                    self.betting.place_bet(player_id, total_bet, player.stack)
                    player.stack -= call_amount  # Deduct only the additional amount needed
                    
                elif action == PlayerAction.BRING_IN:
                    valid_actions = self.get_valid_actions(player_id)
                    valid_bet = next((a for a in valid_actions if a[0] == PlayerAction.BRING_IN), None)
                    if not valid_bet or amount != valid_bet[1]:
                        return ActionResult(success=False, error=f"Invalid bring-in amount: ${amount}")
                    logger.info(f"{player.name} brings in for ${amount}")
                    self.betting.place_bet(player_id, amount, player.stack, is_forced=True)
                    player.stack -= amount  # Already deducted additional amount
                    self.current_player = self.next_player(round_start=False)
                    return ActionResult(success=True)
                        
                elif action in [PlayerAction.BET, PlayerAction.RAISE]:
                    # Validate bet/raise amount
                    valid_actions = self.get_valid_actions(player_id)

                    logger.debug(f"Valid actions: {valid_actions}")

                    valid_bet = next((a for a in valid_actions if a[0] == action), None)
                    if not valid_bet:
                        return ActionResult(success=False, error=f"Invalid {action.value}")
                    _, min_amount, max_amount = valid_bet

                    logger.debug(f"Attempting action: {action}, Amount: {amount}, Min: {min_amount}, Max: {max_amount} with stack of {player.stack}")

                    if (min_amount is not None and amount < min_amount) or (max_amount is not None and amount > max_amount):
                        return ActionResult(
                            success=False,
                            error=f"Invalid {action.value} amount: ${amount}"
                        )
                    
                    current_bet = self.betting.current_bets.get(player_id, PlayerBet())
                    current_ante = self.betting.pot.total_antes.get(f"round_{self.betting.pot.current_round}_{player_id}", 0)
                    logger.debug(f"  current_bet is {current_bet}")
                    logger.debug(f"  current_ante is {current_ante}")
                    
                    # Adjust for all-in
                    if amount >= player.stack:  # Changed from > to >=
                        logger.info(f"{player.name} is going all-in with ${player.stack}")
                        amount = player.stack + current_bet.amount  # Include what's already in
                        additional = player.stack  # Take entire remaining stack   
                    else:
                        # Normal raise
                        # Ante is included in current_bet, but not in the amount, so need to adjust
                        additional = amount - current_bet.amount + current_ante                  

                    if additional > player.stack:
                        return ActionResult(
                            success=False,
                            error="Not enough chips to complete this action"
                        )
                        
                    # ✅ Place the bet and deduct from stack
                    logger.info(f"{player.name} {action.value}s to ${amount}")
                    step = self.rules.gameplay[self.current_step]
                    #bet_type = BetType.SMALL if (self.rules.forced_bets.style == "bring-in" and 
                    #                            step.action_config["type"] == "small") else BetType.BIG                    
                    bet_type = BetType.SMALL if step.action_config["type"] == "small" else BetType.BIG
                    logger.debug(f"bet_type={bet_type} self.rules.forced_bets.style={self.rules.forced_bets.style} step.action_config={step.action_config}")
                    logger.debug(f"  step.action_config[type]={step.action_config['type']}")


                    self.betting.place_bet(player_id, amount, player.stack, bet_type=bet_type)
                    player.stack -= additional

                    logger.debug(f"{player.name}'s remaining stack: ${player.stack}")

                    # 🔄 Update last_raise_size only if not all-in
                    if action == PlayerAction.RAISE and amount != player.stack:
                        self.betting.last_raise_size = additional
                        logger.debug(f"Updated last raise size to ${self.betting.last_raise_size}")                 
                              
                # Move to next player
                self.current_player = self.next_player(round_start=False)
                
                # Check if betting round complete
                if self.betting.round_complete():
                    logger.info("Betting round complete")
                    if self.auto_progress:
                        self._next_step()
                    return ActionResult(success=True, state_changed=True)
                    
                return ActionResult(success=True)
            
            except ValueError as e:
                logger.error(f"Error processing {player.name}'s action: {e}")
                return ActionResult(
                    success=False,
                    error=str(e)
                )            
        
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
            logger.info(f"Processing step {self.current_step}: {step.name}")
                           
            if step.action_type == GameActionType.GROUPED:
                logger.info(f"Starting grouped step: {step.name}")
                self.current_substep = 0  # Start with the first sub-action
                # Assume action_config is a list like ["bet", "discard"]
                first_subaction = step.action_config[self.current_substep]

                # Set state based on the first sub-action
                if "bet" in first_subaction:
                    bet_config = first_subaction["bet"]
                    self.state = GameState.BETTING
                    if bet_config.get("type") in ["antes", "blinds", "bring-in"]:
                        self.handle_forced_bets(bet_config["type"])
                        if self.auto_progress:
                            self._next_step()
                            return
                    else:
                        logger.info(f"Starting betting round in grouped step: {step.name}")
                        # Determine if this is the first betting round
                        is_first_betting_round = False
                        for i, s in enumerate(self.rules.gameplay[:self.current_step + 1]):
                            # Check prior steps and current step up to this point
                            if s.action_type == GameActionType.BET and s.action_config.get("type") == "small":
                                is_first_betting_round = (i == self.current_step)
                            elif s.action_type == GameActionType.GROUPED:
                                for subaction in s.action_config:
                                    if "bet" in subaction and subaction["bet"].get("type") == "small":
                                        is_first_betting_round = (i == self.current_step and subaction == first_subaction)
                                        break
                                if is_first_betting_round:
                                    break
                        preserve_bet = is_first_betting_round
                        self.betting.new_round(preserve_bet)
                        self.current_player = self.next_player(round_start=True)
                elif "discard" in first_subaction:
                    self.state = GameState.DRAWING
                    self._setup_discard_round(step.action_config[self.current_substep])
                elif "draw" in first_subaction:
                    self.state = GameState.DRAWING
                    self._setup_draw_round(step.action_config[self.current_substep])
                elif "separate" in first_subaction:
                    self.state = GameState.DRAWING
                    self._setup_separate_round(step.action_config[self.current_substep])                    
                elif "expose" in first_subaction:
                    self.state = GameState.DRAWING
                    self._setup_expose_round(step.action_config[self.current_substep])    
                elif "pass" in first_subaction:
                    self.state = GameState.DRAWING
                    self._setup_pass_round(step.action_config[self.current_substep])    
                # Add other sub-action types as needed (e.g., "separate", "expose")
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

            # treating discard and draw (which is discard/draw) separately for now,
            # but could be refactored to be the same thing
            elif step.action_type == GameActionType.DISCARD:
                logger.info(f"Starting discard round: {step.name}")
                self.state = GameState.DRAWING
                self._setup_discard_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
            
            elif step.action_type == GameActionType.DRAW:
                logger.info(f"Starting draw round: {step.name}")
                self.state = GameState.DRAWING
                self._setup_draw_round(step.action_config)
                self.current_player = self.next_player(round_start=True)

            elif step.action_type == GameActionType.SEPARATE:
                logger.info(f"Starting separate round: {step.name}")
                self.state = GameState.DRAWING  # Reuse DRAWING for player interaction
                self._setup_separate_round(step.action_config)
                self.current_player = self.next_player(round_start=True)

            elif step.action_type == GameActionType.EXPOSE:
                logger.info(f"Starting expose round: {step.name}")
                self.state = GameState.DRAWING  # Reuse DRAWING state for player actions
                self._setup_expose_round(step.action_config)
                self.current_player = self.next_player(round_start=True)

            elif step.action_type == GameActionType.PASS:
                logger.info(f"Starting pass round: {step.name}")
                self.state = GameState.DRAWING
                self._setup_pass_round(step.action_config)
                self.current_player = self.next_player(round_start=True)

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
            face_up = state == "face up"
            
            if location == "player":
                logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to each player ({state})")
                self.table.deal_hole_cards(num_cards, face_up=face_up)
            else:  # community
                logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to community subset '{subset}' ({state})")
                self.table.deal_community_cards(num_cards, subset=subset, face_up=face_up)               
                
    def _setup_discard_round(self, config: Dict[str, Any]) -> None:
        """Set up a discard round based on configuration."""
        self.current_discard_config = config
        logger.debug(f"Setting up discard round with config: {config}")

    def _setup_draw_round(self, config: Dict[str, Any]) -> None:
        """Set up a draw round based on configuration."""
        self.current_draw_config = config
        logger.debug(f"Setting up draw round with config: {config}")

    def _setup_separate_round(self, config: Dict[str, Any]) -> None:
        self.current_separate_config = config
        logger.debug(f"Setting up separate round with config: {config}")     

    def _setup_expose_round(self, config: Dict[str, Any]) -> None:
        """Set up an expose round based on configuration."""
        self.current_expose_config = config
        logger.debug(f"Setting up expose round with config: {config}")   

    def _setup_pass_round(self, config: Dict[str, Any]) -> None:
        """Set up a pass round based on configuration."""
        self.current_pass_config = config
        logger.debug(f"Setting up pass round with config: {config}")                

    def _check_discard_round_complete(self) -> bool:
        """Check if the current discard round is complete."""
        # In the simplest implementation, we just check if we've gone through all active players
        players_order = self.table.get_position_order()
        active_players = [p for p in players_order if p.is_active]
        
        # Consider all players have acted if we've cycled back to the first player
        # (This is simplified - in production you'd want to track which players have acted)
        return len(active_players) > 0 and self.current_player == active_players[0].id
        
    def _handle_discard_action(self, player: Player, cards: List[Card]) -> bool:
        """
        Handle a discard or draw action for a player.
        
        Args:
            player: The player discarding cards
            cards: Cards to discard
            
        Returns:
            True if discard was successful, False otherwise
        """
        # Get discard parameters
        # right now, suporting the simple discard case - no redraw 

        # see if discard or draw config exists   
        is_discard = getattr(self, "current_discard_config", None) is not None
        is_draw = getattr(self, "current_draw_config", None) is not None

        logger.debug(f"Handling discard action for {player.name}: {cards} - is_discard: {is_discard}, is_draw: {is_draw}")

        if not (is_discard or is_draw):
            logger.warning("No discard or draw config set")
            return False
    
        config = self.current_discard_config if is_discard else self.current_draw_config
        card_config = config["cards"][0]
        max_discard = card_config.get("number", 0)
        min_discard = card_config.get("min_number", 0 if is_draw else max_discard)

        # Skip count validation for automated rules like "matching ranks"
        rule = card_config.get("rule", "none")
        if rule != "matching ranks":
            if len(cards) < min_discard or len(cards) > max_discard:
                logger.warning(f"Invalid discard count: {len(cards)} not in range [{min_discard}, {max_discard}]")
                return False
            
            for card in cards:
                if card not in player.hand.cards:
                    logger.warning(f"Card {card} not in {player.name}'s hand")
                    return False      

        face_up = card_config.get("state", "face down") == "face up"
        entire_subset = card_config.get("entire_subset", False)               
        
        if is_draw:
            # Determine draw amount (if any)
            draw_amount = len(cards)  # Default: draw same number as discard
            draw_amount_config = card_config.get("draw_amount")
            
            if draw_amount_config:
                if draw_amount_config.get("relative_to") == "discard":
                    # Adjust draw amount based on discard amount
                    draw_amount = len(cards) + draw_amount_config.get("amount", 0)
                    # Ensure non-negative
                    draw_amount = max(0, draw_amount)

        # handle some values only in discard
        if is_discard:
            rule = card_config.get("rule", "none")  # Default to "none" if not specified
            state = card_config.get("state", "face down")  # Default to face down if not specified
            discard_location = card_config.get("discardLocation", "discard_pile")  # Default to discard pile if not specified
            discard_subset = card_config.get("discardSubset", "default")  # Default to "default" if not specified         

        # If entire_subset is true, validate the cards match an existing subset
        if is_discard and entire_subset:
            player_subsets = player.hand.subsets
            valid_discard = False
            for subset_name, subset_cards in player_subsets.items():
                if len(subset_cards) == len(cards) and all(c in subset_cards for c in cards):
                    valid_discard = True
                    # Remove the entire subset
                    player.hand.subsets[subset_name].clear()
                    logger.info(f"Player {player.name} discarded subset '{subset_name}'")
                    break
            if not valid_discard:
                logger.warning(f"Player {player.name} discarded {cards}, but it doesn’t match an entire subset")
                return False
        
        # see if we have an automated rule for discards - cards array parameter not used
        if is_discard and rule == "matching ranks":
            # Get the ranks of the cards in the specified subset (e.g., "Discard" board)
            if discard_location == "community":
                discard_cards = self.table.community_cards.get(discard_subset, [])
            else:
                # nothing else supported yet
                discard_cards = []   

            discard_ranks = {card.rank for card in discard_cards}

            hole_cards = player.hand.get_cards()
            cards_to_discard = [card for card in hole_cards if card.rank in discard_ranks]

            if not cards_to_discard:
                logger.debug(f"No cards to discard for {player.name} matching ranks {discard_ranks}")
                return True  # Still successful if no matches
            
            # Perform the discard
            for card in cards_to_discard:
                player.hand.remove_card(card)
                if discard_location == "community":
                    self.table.community_cards[discard_subset].append(card)
                    card.visibility = Visibility.FACE_UP if state == "face up" else Visibility.FACE_DOWN
                else:
                    self.table.discard_pile[discard_subset].append(card)
                    card.visibility = Visibility.FACE_UP if state == "face up" else Visibility.FACE_DOWN

            logger.info(f"Player {player.id} discarded {len(cards_to_discard)} cards matching ranks {discard_ranks}")
        else: # used in draw and discard
            # use what the player specified
            # Validate discard count
            if len(cards) > max_discard:
                logger.warning(f"{player.name} trying to discard too many cards: {len(cards)} > {max_discard}")
                return False
                
            if len(cards) < min_discard:
                logger.warning(f"{player.name} trying to discard too few cards: {len(cards)} < {min_discard}")
                return False            

            # Remove cards from hand and add to discard pile
            for card in cards:
                player.hand.remove_card(card)
                if face_up:
                    card.visibility = Visibility.FACE_UP
                self.table.discard_pile.add_card(card)

            logger.info(f"{player.name} discards {len(cards)} cards: {cards}")                
        
        if is_draw:
            # Draw new cards if applicable
            if draw_amount > 0:
                if len(self.table.deck.cards) < draw_amount:
                    logger.warning(f"Not enough cards to draw {draw_amount} for {player.name}; available: {len(self.table.deck.cards)}")
                    draw_amount = len(self.table.deck.cards)                
                new_cards = self.table.deck.deal_cards(draw_amount)
                player.hand.add_cards(new_cards)
                logger.info(f"{player.name} draws {len(new_cards)} new cards: {new_cards}")
        
        return True
                          
    def _handle_separate_action(self, player: Player, cards: List[Card]) -> bool:
        config = self.current_separate_config["cards"]
        all_cards = player.hand.get_cards()
        
        # Validate total cards and source
        expected_total = sum(cfg["number"] for cfg in config)
        if len(cards) != expected_total or not all(c in all_cards for c in cards):
            logger.warning(f"Invalid card selection for {player.name}: {cards}")
            return False
        
        # Assign cards to subsets
        card_index = 0
        player.hand.clear_subsets()  # Clear existing subsets
        for cfg in config:
            subset = cfg["hole_subset"]
            num = cfg["number"]
            subset_cards = cards[card_index:card_index + num]
            for card in subset_cards:
                player.hand.add_to_subset(card, subset)
            card_index += num
        
        logger.info(f"{player.name} separated cards into: {dict(player.hand.subsets)}")
        return True
       
    def _check_separate_round_complete(self) -> bool:
        config = self.current_separate_config["cards"]
        active_players = [p for p in self.table.players.values() if p.is_active]
        return all(
            all(len(p.hand.get_subset(cfg["hole_subset"])) == cfg["number"] for cfg in config)
            for p in active_players
        )    
    
    def _validate_expose_action(self, player: Player, cards: List[Card]) -> bool:
        """Validate the player's exposure choice without applying it."""
        config = self.current_expose_config["cards"][0]
        num_to_expose = config["number"]  # e.g., 2
        required_state = config.get("state", "face down")

        if len(cards) != num_to_expose:
            logger.warning(f"Player {player.name} selected {len(cards)} cards, but {num_to_expose} are required")
            return False

        player_hand = player.hand.get_cards()
        for card in cards:
            if card not in player_hand:
                logger.warning(f"Player {player.name} tried to expose a card not in their hand: {card}")
                return False
            if required_state == "face down" and card.visibility != Visibility.FACE_DOWN:
                logger.warning(f"Player {player.name} tried to expose a card that is not face down: {card}")
                return False

        return True    

    def _handle_expose_action(self, player: Player, cards: List[Card]) -> bool:
        """Handle a player's exposure of cards."""
        config = self.current_expose_config["cards"][0]  # Single config for simplicity
        num_to_expose = config["number"]
        required_state = config.get("state", "face down")  # Default to face down

        # Validate number of cards and their state
        if len(cards) != num_to_expose:
            logger.warning(f"Player {player.name} attempted to expose {len(cards)} cards, but {num_to_expose} are required")
            return False

        player_hand = player.hand.get_cards()
        for card in cards:
            if card not in player_hand:
                logger.warning(f"Player {player.name} tried to expose a card not in their hand: {card}")
                return False
            if required_state == "face down" and card.visibility != Visibility.FACE_DOWN:
                logger.warning(f"Player {player.name} tried to expose a card that is not face down: {card}")
                return False

        # Expose the selected cards
        for card in cards:
            card.visibility = Visibility.FACE_UP
            logger.info(f"Player {player.name} exposed {card}")

        return True    
    
    def _check_expose_round_complete(self) -> bool:
        """Check if all active players have selected cards to expose."""
        active_players = [p for p in self.table.players.values() if p.is_active]
        return all(p.id in self.pending_exposures for p in active_players)    
    
    def _apply_all_exposures(self) -> None:
        """Apply all pending exposures simultaneously."""
        for player_id, cards in self.pending_exposures.items():
            player = self.table.players[player_id]
            for card in cards:
                if card in player.hand.get_cards() and card.visibility == Visibility.FACE_DOWN:
                    card.visibility = Visibility.FACE_UP
                    logger.info(f"Player {player.name} exposed {card}")
        self.pending_exposures.clear()  # Reset after applying        
    
    def _validate_pass_action(self, player: Player, cards: List[Card]) -> bool:
        """Validate the player's pass choice without applying it."""
        config = self.current_pass_config["cards"][0]
        num_to_pass = config["number"]  # e.g., 1
        required_state = config.get("state", "face down")

        if len(cards) != num_to_pass:
            logger.warning(f"Player {player.name} selected {len(cards)} cards, but {num_to_pass} are required")
            return False

        player_hand = player.hand.get_cards()
        for card in cards:
            if card not in player_hand:
                logger.warning(f"Player {player.name} tried to pass a card not in their hand: {card}")
                return False
            if required_state == "face down" and card.visibility != Visibility.FACE_DOWN:
                logger.warning(f"Player {player.name} tried to pass a card that is not face down: {card}")
                return False

        return True    
    
    def _check_pass_round_complete(self) -> bool:
        """Check if all active players have selected cards to pass."""
        active_players = [p for p in self.table.players.values() if p.is_active]
        return all(p.id in self.pending_passes for p in active_players)    

    def _apply_all_passes(self) -> None:
        """Apply all pending passes simultaneously."""
        new_hands = {player_id: [] for player_id in self.table.players}  # Temporary storage
        
        # Remove passed cards from original hands and assign to new hands
        for player_id, (card, recipient_id) in self.pending_passes.items():
            player = self.table.players[player_id]
            player.hand.remove_card(card)
            new_hands[recipient_id].append(card)
        
        # Add received cards to each player's hand
        for player_id, cards in new_hands.items():
            if cards:  # Only if they received something
                player = self.table.players[player_id]
                player.hand.add_cards(cards)
                logger.info(f"Player {player.name} received {cards}")

        self.pending_passes.clear()  # Reset after applying        
                              
    def handle_forced_bets(self, bet_type: str):
        """Handle forced bets (antes or blinds) at the start of a hand."""
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
            self.current_player = None  # No player has acted yet; bring-in will determine first
            self.betting.new_round(preserve_current_bet=True)  # Preserve ante as part of round but reset acted flags

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
            self.current_player = self.next_player(round_start=True)
            self.betting.new_round(preserve_current_bet=True)        

        elif bet_type == "bring-in":
            # Determine bring-in player (lowest up-card)
            num_visible = sum(1 for c in active_players[0].hand.get_cards() if c.visibility == Visibility.FACE_UP)
            bring_in_rule = CardRule(self.rules.forced_bets.rule)
            bring_in_player = BringInDeterminator.determine_first_to_act(active_players, num_visible, bring_in_rule, self.rules)
            if bring_in_player:
                self.current_player = bring_in_player
                logger.info(f"Bring-in player: {bring_in_player.name} with {bring_in_player.hand.cards[-1]}")
            else:
                logger.error("No bring-in player determined")
                self.current_player = active_players[0]  # Fallback
            # Betting round starts with bring-in player, no auto-post yet
            self.betting.new_round(preserve_current_bet=True)  # Reset bets, keep ante in pot
                           
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
        self.current_step += 1
        self.process_current_step()
        
    def next_player(self, round_start: bool = False) -> Optional[Player]:
        """
        Determine the next player to act based on game type and round state.
        
        Args:
            round_start: True if this is the start of a betting round
        
        Returns:
            Next player to act or None if no active players
        """
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            return None
        
        # Check if this is a stud game with bring-in
        is_stud_game = self.rules.forced_bets.style == "bring-in"

        if is_stud_game:
            step = self.rules.gameplay[self.current_step]
            bring_in_rule = CardRule(self.rules.forced_bets.rule)

            # Find the "Initial Bet" step dynamically
            # Debug the gameplay steps
            logger.debug(f"Gameplay steps: {[s.__dict__ for s in self.rules.gameplay]}")
            bring_in_step_idx = next((i for i, s in enumerate(self.rules.gameplay) if s.action_config.get("type") == "bring-in"), -1)
            initial_bet_step_idx = bring_in_step_idx + 1 if bring_in_step_idx != -1 else -1
            logger.debug(f"  current step: {self.current_step}, bring_in_step_idx: {bring_in_step_idx}, initial_bet_step_idx: {initial_bet_step_idx}")

            num_visible = sum(1 for c in active_players[0].hand.get_cards() if c.visibility == Visibility.FACE_UP)      

            if round_start and step.action_config.get("type") == "bring-in":
                bring_in_player = BringInDeterminator.determine_first_to_act(active_players, num_visible, bring_in_rule, self.rules)
                logger.debug(f"Stud first-to-act in bring-in round: {bring_in_player.name}")
                return bring_in_player
            elif round_start and self.current_step == initial_bet_step_idx:  # "Initial Bet" (first small bet round)
                # Start with player after last bring-in
                logger.debug(f"  self.betting.current_bets = {self.betting.current_bets}")
                # find the player with posted_blind = True
                current_idx = next((i for i, p in enumerate(active_players) if self.betting.current_bets.get(p.id, PlayerBet()).posted_blind), -1)
                #last_bring_in = next((p for p in active_players if self.betting.current_bets.get(p.id, PlayerBet()).amount > 0), active_players[0])
                #current_idx = active_players.index(last_bring_in)
                next_idx = (current_idx + 1) % len(active_players)
                logger.debug(f"Stud first-to-act in round {self.betting.betting_round + 1}: {active_players[next_idx].name}")
                return active_players[next_idx]
            elif round_start:
                # For non-betting rounds (e.g., expose) or betting rounds with visible cards
                if num_visible == 0:  # No cards visible yet (e.g., expose step)
                    logger.debug(f"No visible cards; starting with first active player: {active_players[0].name}")
                    return active_players[0]           
                # Later betting rounds (e.g., Fourth Street Bet)                    
                first_player = BringInDeterminator.determine_first_to_act(active_players, num_visible, bring_in_rule, self.rules)
                if first_player is None:
                    logger.warning("No first player determined; defaulting to first active player")
                    return active_players[0]               
                logger.debug(f"Stud first-to-act in round {self.betting.betting_round + 1}: {first_player.name}")
                return first_player          
            elif self.current_player:
                current_idx = active_players.index(self.current_player)
                next_idx = (current_idx + 1) % len(active_players)
                logger.debug(f"Stud next player: {active_players[next_idx].name}")
                return active_players[next_idx]
            return active_players[0]       
            
        # Blinds-based games (e.g., Hold'em)
        players = self.table.get_position_order()  # BTN -> SB -> BB order
        active_players = [p for p in players if p.is_active]
        if not active_players:
            return None            
        
        # Determine if this is the first voluntary betting round
        is_first_betting_round = False
        first_bet_step = None
        for i, step in enumerate(self.rules.gameplay):
            if step.action_type == GameActionType.BET and step.action_config.get("type") == "small":
                first_bet_step = i
                break
            elif step.action_type == GameActionType.GROUPED:
                for j, subaction in enumerate(step.action_config):
                    if "bet" in subaction and subaction["bet"].get("type") == "small":
                        first_bet_step = i
                        break
                if first_bet_step is not None:
                    break

        # If this is the first betting step encountered, it’s the first round
        is_first_betting_round = (first_bet_step == self.current_step)

        logger.debug(f"First betting round: {is_first_betting_round} and round_start: {round_start}")
        if round_start:
            if is_first_betting_round:
                # First betting round (e.g., pre-flop in Hold'em): Start with BTN in 3-player
                if len(active_players) <= 3:
                    for player in players:
                        if player.position and player.position.has_position(Position.BUTTON) and player.is_active:
                            logger.debug(f"Pre-flop first action to BTN: {player.name}")
                            return player
                    logger.debug(f"BTN not active, starting with: {active_players[0].name}")
                    return active_players[0]                        
                else:
                    bb_idx = next((i for i, p in enumerate(players) if p.has_position(Position.BIG_BLIND) and p.is_active), -1)
                    next_idx = (bb_idx + 1) % len(players)
                    while not players[next_idx].is_active:
                        next_idx = (next_idx + 1) % len(players)                   
                    logger.debug(f"Pre-flop first action to UTG: {players[next_idx].name}")
                    return players[next_idx]
            else:
                # Subsequent rounds: Start with SB
                for player in players:
                    if player.position and player.position.has_position(Position.SMALL_BLIND) and player.is_active:
                        logger.debug(f"Subsequent round action to SB: {player.name}")
                        return player
                logger.debug(f"SB not active, starting with: {active_players[0].name}")
                return active_players[0]
                    
        # Subsequent actions in the round
        if self.current_player:
            try:
                current_idx = next(i for i, p in enumerate(players) if p.id == self.current_player.id)
                next_idx = (current_idx + 1) % len(players)
                # Skip inactive players
                while not players[next_idx].is_active:
                    next_idx = (next_idx + 1) % len(players)
                    if next_idx == current_idx:  # Full circle, no active players left
                        return None                
                logger.debug(f"Next player: {players[next_idx].name}")
                return players[next_idx]
            except StopIteration:
                # Current player no longer active (e.g., folded); start with first active
                logger.debug(f"Current player not found, starting with: {active_players[0].name}")
                return active_players[0]

        # Default: First active player
        logger.debug(f"Defaulting to first active player: {active_players[0].name}")
        return active_players[0]
    
    def _handle_fold_win(self, active_players: List[Player]) -> None:
        """Handle pot award when all but one player folds."""
        logger.info("All but one player folded - hand complete")
        
        # Get total pot amount before awarding
        total_pot = self.betting.get_total_pot()
        
        # Award the pot
        self.state = GameState.COMPLETE
        self.betting.award_pots(active_players)
        
        # Create hand results only for active players (winners) but without showing cards
        hand_results = {}
        for player in active_players:
            hand_result = HandResult(
                player_id=player.id,
                cards=[],
                hand_name="Not shown",
                hand_description="Hand not shown - won uncontested",
                evaluation_type="unknown"
            )
            hand_results[player.id] = [hand_result]  # Wrap in a list
        
        # Create pot result
        pot_result = PotResult(
            amount=total_pot,
            winners=[p.id for p in active_players],
            pot_type="main",
            hand_type="Entire Pot",
            eligible_players=set(p.id for p in active_players)
        )
        
        # Store the result
        self.last_hand_result = GameResult(
            pots=[pot_result],
            hands=hand_results,
            winning_hands=list(hand_results.values())[0],  # First list of hands
            is_complete=True
        )

    def _handle_showdown(self) -> None:
        """
        Handle showdown and determine winners.
        
        Evaluates all active players' hands and awards pots.
        Handles multiple hand configurations for split pot games.
        """
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            self.state = GameState.COMPLETE
            return
        
        # Get showdown rules
        showdown_rules = self.rules.showdown
        best_hand_configs = showdown_rules.best_hand
        default_action = showdown_rules.default_action
        
        # Initialize structures for tracking results
        pot_results = []
        hand_results = {}
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
        for config_index, hand_config in enumerate(best_hand_configs):
            config_name = hand_config.get('name', f"Configuration {config_index+1}")
            eval_type = EvaluationType(hand_config.get('evaluationType', 'high'))
            qualifier = hand_config.get('qualifier', None)
            
            logger.info(f"  Evaluating {config_name} with evaluation type {eval_type}")  
            if qualifier:
                logger.info(f"    with qualifier {qualifier}")  

            # Find best hands for this configuration
            config_results = self._evaluate_hands_for_config(
                active_players, 
                hand_config, 
                eval_type
            )
           
            # Update the overall hand results
            for player_id, result in config_results.items():
                if player_id not in hand_results:
                    hand_results[player_id] = []

                hand_results[player_id].append(result)
                logger.info(f"  Player {player_id} has {result.hand_description}")  
            
            # Award pots for this configuration
            pot_winners, had_winners = self._award_pots_for_config(
                active_players,
                config_results,
                eval_type,
                hand_config,
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
                        if winner_id in config_results:
                            winning_hand = config_results[winner_id]
                            winning_hand.hand_type = config_name
                            winning_hands.append(winning_hand)
            else:
                # Save the pot results even though no winners
                # This ensures they show up in the game result
                for pot_result in pot_winners:
                    pot_result.winners = []  # Clear winners list
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
        if not had_any_winners and default_action and default_action.get('condition') == 'no_qualifier_met':
            logger.debug("No player qualified for any hand - handling default action")
            action = default_action.get('action')
            
            if action == 'split_pot':
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
                        for hand in hand_results[player.id]:
                            hand.hand_type = "Split (No Qualifier)"
                            winning_hands.append(hand)             

            elif action == 'best_hand':
                logger.debug("   best_hand: evaluate hands using the alternate evaluation type")
                # For 'best_hand' action, evaluate hands using the alternate evaluation type
                alternate_configs = default_action.get('bestHand', [])
                
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
                                hand_results[player_id] = []
                            
                            # Set the hand_type attribute on the result
                            result.hand_type = alt_name
                            hand_results[player_id].append(result)
                        
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
                                if winner_id in alt_results:
                                    winning_hand = alt_results[winner_id]
                                    winning_hand.hand_type = alt_name
                                    alt_winning_hands.append(winning_hand)
                    
                    # Use the alternate results
                    awarded_pot_results = alt_pot_results
                    winning_hands = alt_winning_hands                               

        # Store the complete game result
        self.last_hand_result = GameResult(
            pots=awarded_pot_results,
            hands=hand_results,
            winning_hands=winning_hands,
            is_complete=True
        )
        
        # Sanity check - verify total pot amounts match
        if self.last_hand_result.total_pot != total_pot:
            logger.warning(
                f"Pot amount mismatch: {self.last_hand_result.total_pot} vs {total_pot}"
            )
        
        self.state = GameState.COMPLETE

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
            best_hand = self._find_best_hand_for_player(
                player,
                self.table.community_cards,
                hand_config,
                eval_type
            )
          
            # allow an empty hand to play if it has value
            if zero_cards_pip_value is not None and not best_hand:
                logger.info(f"Player {player.name} has no valid hand for {hand_type}, but zeroCardsPipValue is set to {zero_cards_pip_value}. Assigning a default hand.")
                # create results
                results[player.id] = HandResult(
                    player_id=player.id,
                    cards=[],
                    hand_name="No Cards",
                    hand_description="No Cards",
                    hand_type=hand_type,
                    evaluation_type=eval_type.value,
                    community_cards=self.table.community_cards
                )

                return results
            
            if not best_hand:
                logger.info(f"Player {player.name} has no valid hand for {hand_type}. Skipping...")
                continue
            
            # Create hand result
            results[player.id] = HandResult(
                player_id=player.id,
                cards=best_hand,
                hand_name=describer.describe_hand(best_hand),
                hand_description=describer.describe_hand_detailed(best_hand),
                hand_type=hand_type,
                evaluation_type=eval_type.value,
                community_cards=self.table.community_cards
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
        from generic_poker.evaluation.evaluator import evaluator
        
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
                winners = self._find_winners(qualified_players, player_hands, eval_type)
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
            winners = self._find_winners(qualified_players, player_hands, eval_type)
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
                winners = self._find_winners(qualified_players, player_hands, eval_type)
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
            winners = self._find_winners(qualified_players, player_hands, eval_type)
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
    ) -> List[Card]:
        """
        Find the best possible hand for a player according to the game rules.
        
        Args:
            player: The player
            community_cards: Available community cards
            showdown_rules: Showdown configuration from game rules
            eval_type: Type of hand evaluation to use
            
        Returns:
            List of cards representing the player's best hand
        """
        from generic_poker.evaluation.evaluator import evaluator
        import itertools

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
                return []
        else:
            # Use all cards if no subset specified or default (e.g., Hold'em, Stud)
            hole_cards = player.hand.get_cards()
            if not hole_cards:
                logger.warning(f"No cards in hand for player {player.id}")
                return []
            
        if not hole_cards and "minimumCards" in showdown_rules:
            minimum_cards = showdown_rules["minimumCards"]
            if minimum_cards > 0:
                logger.warning(f"Player {player.id} has 0 cards, needs {minimum_cards} to qualify")
                return []
            # Handle 0-card variants
            if "zeroCardsPipValue" in showdown_rules and eval_type.startswith("low_pip"):
                # For low pip evaluation, return an empty hand with a pip value
                # The evaluator will use zeroCardsPipValue (e.g., 0 for best low)
                return []            
        
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

            if best_hand:
                return best_hand
            else:
                logger.warning(f"No valid hand combinations for player {player.id}")
                return []
                       
        # Handle different types of hand compositions
        if "anyCards" in showdown_rules:
            total_cards = showdown_rules["anyCards"]
            allowed_combinations = showdown_rules.get("holeCardsAllowed", [])

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
    
            else:
                # Fallback to all hole cards
                all_cards = hole_cards + comm_cards
                if len(all_cards) >= total_cards:
                    for hand_combo in itertools.combinations(all_cards, total_cards):
                        hand = list(hand_combo)
                        if best_hand is None or evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand
            
            # If there are no community cards or exactly the right number of hole cards,
            # we can just use the hole cards (straight poker case)
            if not comm_cards and len(hole_cards) == total_cards:
                return hole_cards
            
            # if we are padding, then don't check the length of all_cards against total_cards
            # because we want to allow padding to fill in the gaps
            if len(all_cards) < total_cards and not padding:
                # Not enough cards total
                logger.warning(
                    f"Not enough cards for player {player.id}: "
                    f"Has {len(hole_cards)} hole cards and {len(comm_cards)} community cards "
                    f"(need {total_cards} total)"
                )
                return []
            
            return best_hand or [] 
                   
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

            # If we found a valid hand, return it
            if best_hand:
                return best_hand
            else:
                logger.warning(
                    f"No valid hand combinations for player {player.id}"
                )
                return []            
        
        # Handle cases with specific requirements for hole and/or community cards
        elif "holeCards" in showdown_rules or "communityCards" in showdown_rules:
            logger.debug(f"Evaluating showdown rules for player {player.id} with hole cards: {hole_cards} and community cards: {comm_cards}")
            # Get requirements (default to 0 if not specified)
            required_hole = showdown_rules.get("holeCards", 0)
            required_community = showdown_rules.get("communityCards", 0)

            # Special case for "all" hole cards
            if required_hole == "all":
                required_hole = len(hole_cards)  # Use all available hole cards
                # Dynamically calculate community cards based on eval_type hand size
                total_cards_needed = HAND_SIZES.get(eval_type, 5)  # Default to 5 if eval_type not found
                required_community = max(0, total_cards_needed - required_hole)
                # Cap by available community cards
                required_community = min(required_community, len(comm_cards))
            else:
                required_hole = int(required_hole)  # Ensure numeric for other cases

            logger.debug(
                f"Required hole cards: {required_hole}, Required community cards: {required_community} "
                f"(player {player.id} has {len(hole_cards)} hole and {len(comm_cards)} community)"
            )
            
            # Ensure we have enough cards to evaluate (if padding, we will get enough so OK)
            if (len(hole_cards) < required_hole or len(comm_cards) < required_community) and not padding:
                logger.warning(
                    f"Not enough cards for player {player.id}: "
                    f"Has {len(hole_cards)} hole cards (need {required_hole}) and "
                    f"{len(comm_cards)} community cards (need {required_community})"
                )
                return []
            
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
            
            logger.debug(f'Best hand found for player {player.id} using showdown rules: {best_hand}')
            return best_hand
              
        # Default: just use all hole cards
        return hole_cards

    def _find_winners(
        self,
        players: List[Player],
        player_hands: Dict[str, List[Card]],
        eval_type: EvaluationType
    ) -> List[Player]:
        """Find best hand(s) among players."""
        if not players:
            return []
            
        from generic_poker.evaluation.evaluator import evaluator
        
        # Get first player as initial best
        best_players = [players[0]]
        best_hand = player_hands[players[0].id]
        
        # Compare against other players
        for player in players[1:]:
            if player.id not in player_hands:
                continue
                
            current_hand = player_hands[player.id]
            comparison = evaluator.compare_hands(current_hand, best_hand, eval_type)
            
            if comparison > 0:  # Current hand better
                best_hand = current_hand
                best_players = [player]
            elif comparison == 0:  # Tie
                best_players.append(player)
                
        return best_players        

    def format_actions_for_display(self, player_id: str) -> List[str]:
        """
        Convert valid actions to user-friendly display strings.
        
        Args:
            player_id: ID of player to get formatted actions for
            
        Returns:
            List of formatted action strings ready for display
        
        Example output:
            ["Fold", "Call $10 (+$5)", "Raise to $20 (+$15)"]
        """
        # Get valid actions
        valid_actions = self.get_valid_actions(player_id)
        if not valid_actions:
            return []
        
        player = self.table.players[player_id]
        current_player_bet = self.betting.current_bets.get(player_id, PlayerBet()).amount
        formatted_actions = []
        
        for action, min_amount, max_amount in valid_actions:
            if action == PlayerAction.FOLD:
                formatted_actions.append("Fold")
                
            elif action == PlayerAction.CHECK:
                formatted_actions.append("Check")
                
            elif action == PlayerAction.CALL:
                additional = min_amount - current_player_bet
                formatted_actions.append(f"Call ${min_amount} (+${additional})")
                
            elif action in [PlayerAction.BET, PlayerAction.RAISE]:
                # For fixed limit, min_amount and max_amount should be the same
                if min_amount == max_amount:
                    additional = min_amount - current_player_bet
                    action_name = "Bet" if action == PlayerAction.BET else "Raise to"
                    formatted_actions.append(f"{action_name} ${min_amount} (+${additional})")
                # For pot limit or no limit, show a slider or multiple options
                else:
                    additional_min = min_amount - current_player_bet
                    action_name = "Bet" if action == PlayerAction.BET else "Raise to"
                    
                    # If this is a no-limit or pot-limit game, we might want to show range
                    formatted_actions.append(f"{action_name} ${min_amount}-${max_amount} (min +${additional_min})")
                    
                    # Additionally, we could add common bet sizing options:
                    if self.betting_structure != BettingStructure.LIMIT:
                        pot_size = self.betting.get_total_pot()
                        
                        # Half pot
                        half_pot = min(current_player_bet + (pot_size // 2), max_amount)
                        if half_pot > min_amount:
                            additional = half_pot - current_player_bet
                            formatted_actions.append(f"{action_name} ${half_pot} - Half Pot (+${additional})")
                        
                        # Full pot
                        full_pot = min(current_player_bet + pot_size, max_amount)
                        if full_pot > half_pot:
                            additional = full_pot - current_player_bet
                            formatted_actions.append(f"{action_name} ${full_pot} - Pot (+${additional})")
                        
                        # All-in
                        if max_amount > full_pot:
                            additional = max_amount - current_player_bet
                            formatted_actions.append(f"All-in ${max_amount} (+${additional})")
        
        return formatted_actions        
    