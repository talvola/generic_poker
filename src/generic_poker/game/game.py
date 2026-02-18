"""Core game implementation controlling game flow."""
import logging
import json
import itertools
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Set

from generic_poker.config.loader import GameRules, GameActionType, ForcedBets, ProtectionOption
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
from generic_poker.game.game_result import GameResult
from generic_poker.game.showdown_manager import ShowdownManager

from generic_poker.evaluation.evaluator import evaluator

logger = logging.getLogger(__name__)  
    
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
        auto_progress: bool = True,
        named_bets: Optional[Dict[str, int]] = None
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
        # Default bring-in to half the small bet for bring-in style games
        if bring_in is None and self.rules.forced_bets and self.rules.forced_bets.style == "bring-in":
            self.bring_in = max(1, self.small_bet // 2)
        else:
            self.bring_in = bring_in
        self.ante = ante            

        self.auto_progress = auto_progress  # Store the setting     
        
        self.action_handler = PlayerActionHandler(self)

        # Initialize the showdown manager
        self.showdown_manager = ShowdownManager(self.table, self.betting, self.rules)        
        # Give the showdown manager a reference to the game instance for access to game_choices
        self.showdown_manager.game = self

        self.state = GameState.WAITING
        self.current_step = -1  # Not started
        self.current_player: Optional[Player] = None  # player to act
    
        self.last_hand_result = None  # Store the last hand result here

        self.bring_in_player_id = None

        self.declarations: Dict[str, Dict[int, str]] = {}

        self.dynamic_wild_rank = None  # Store rank that becomes wild due to last card dealt
        
        self.player_wild_ranks: Dict[str, Optional[Rank]] = {}  # player_id -> wild_rank

        self.named_bets = named_bets or {}
        self.pending_protection_decisions: Dict[str, Dict] = {}


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
    
    def add_player(self, player_id: str, name: str, buyin: int, preferred_seat: Optional[int] = None) -> None:
        """Add a player to the game."""
        self.table.add_player(player_id, name, buyin, preferred_seat)
        
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
                
    def start_hand(self, shuffle_deck: bool = False) -> None:
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
        self.table.deck.shuffle() if shuffle_deck else None
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

        
    def _should_skip_step(self, step) -> bool:
        """
        Check if a step should be skipped based on its conditional state.
        
        Args:
            step: The GameStep to check
            
        Returns:
            True if the step should be skipped (condition not met), False otherwise
        """
        # Check for conditional state directly on the GameStep
        if hasattr(step, 'conditional_state') and step.conditional_state:
            return not self._check_condition(step.conditional_state)
        
        # Check for conditional state in action_config if not found directly on step
        elif step.action_type in [GameActionType.DEAL, GameActionType.DISCARD, 
                                GameActionType.DRAW, GameActionType.EXPOSE,
                                GameActionType.BET]:
            if isinstance(step.action_config, dict) and "conditional_state" in step.action_config:
                conditional_state = step.action_config["conditional_state"]
                if conditional_state:
                    return not self._check_condition(conditional_state)
        
        return False
        
    def _is_first_betting_round(self):
        """
        Determine if we are currently in the first betting round, accounting for conditional steps.
        """
        for i, step in enumerate(self.rules.gameplay):
            # Skip steps that wouldn't execute due to unmet conditions
            if self._should_skip_step(step):
                continue
                
            if step.action_type == GameActionType.BET and step.action_config.get("type") == "small":
                return i == self.current_step
            elif step.action_type == GameActionType.GROUPED:
                # For grouped actions, we need to check if any substep has a small bet
                # and if the grouped action itself should be skipped
                for j, subaction in enumerate(step.action_config):
                    if "bet" in subaction and subaction["bet"].get("type") == "small":
                        return i == self.current_step and self.action_handler.current_substep == j
                        
        return False        
         
    def player_action(self, player_id: str, action: PlayerAction, amount: int = 0, cards: Optional[List[Card]] = None, declaration_data: Optional[List[Dict]] = None) -> ActionResult:
        """Delegate to PlayerActionHandler and handle step advancement."""
        result = self.action_handler.handle_action(player_id, action, amount, cards, declaration_data)
        if result.advance_step and self.auto_progress and self.state != GameState.COMPLETE:
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
                           
            # First check if this step should be skipped due to conditional state
            if self._check_and_skip_conditional_step():
                logger.info(f"   Skipping conditional step {self.current_step}: '{step.name}'")
                return  # Step was skipped, _next_step was called, no further processing needed
                                   
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
                        logger.debug(f"Starting betting round: {step.name} with new_round({(self.betting.betting_round == 0)})")
                        preserve_bet = (self.betting.betting_round == 0)
                        self.betting.new_round(preserve_bet)
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
                # not sure if we ever see 'deal' here - need to test GROUPED combinations of actions more to validate
                elif "deal" in first_subaction:
                    self.state = GameState.DEALING
                    self._handle_deal(first_subaction["deal"])
                    if self.auto_progress:
                        self.action_handler.current_substep += 1
                        if self.action_handler.current_substep >= len(step.action_config):
                            self._next_step()
                        else:
                            self.process_current_step()  # Process next grouped action                    

            elif step.action_type == GameActionType.BET:
                if step.action_config["type"] in ["antes", "blinds", "bring-in"]:
                    self.handle_forced_bets(step.action_config["type"])  # Use new method with bet_type
                    self.state = GameState.BETTING  # Set here for all forced bets
                    logger.info(f"DEBUG: After forced bets, current_player: {self.current_player.name if self.current_player else None}")
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
                    logger.debug(f"Starting betting round: {step.name} with new_round({preserve_bet})")
                    self.betting.new_round(preserve_bet)
                    self.current_player = self.next_player(round_start=True)
                    logger.info(f"DEBUG: Set current player for betting round to: {self.current_player.name if self.current_player else None} ({self.current_player.id if self.current_player else None})")

            elif step.action_type == GameActionType.DEAL:
                # Check conditional state for the deal step
                conditional_state = step.action_config.get("conditional_state")
                if conditional_state and not self._check_condition(conditional_state):
                    logger.info(f"Skipping deal step '{step.name}' - condition not met")
                    if self.auto_progress:
                        self._next_step()
                    return
                    
                logger.debug(f"Handling deal action: {step.action_config}")
                self.state = GameState.DEALING
                self._handle_deal(step.action_config)
                if self.auto_progress:  
                    self._next_step()

            elif step.action_type == GameActionType.CHOOSE:
                logger.info("Handling player choice")
                self.state = GameState.DEALING
                self._handle_choose(step.action_config)
                # Don't auto-progress - wait for player's choice

            elif step.action_type == GameActionType.ROLL_DIE:
                self.state = GameState.DEALING
                self._handle_roll_die(step.action_config)
                if self.auto_progress:  
                    self._next_step()                    

            elif step.action_type == GameActionType.REMOVE:
                logger.debug(f"Handling remove action: {step.action_config}")
                self.state = GameState.DEALING
                self._handle_remove(step.action_config)
                if self.auto_progress:  
                    self._next_step()                             

            # treating discard and draw (which is discard/draw) separately for now,
            # but could be refactored to be the same thing
            elif step.action_type == GameActionType.DISCARD:
                # Check conditional state for the discard step
                # ET: isn't this handled above?   this might be dead code
                conditional_state = step.action_config.get("conditional_state")
                if conditional_state and not self._check_condition(conditional_state):
                    logger.info(f"Skipping discard step '{step.name}' - condition not met")
                    if self.auto_progress:
                        self._next_step()
                    return

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

            elif step.action_type == GameActionType.REPLACE_COMMUNITY:
                self.state = GameState.DRAWING
                self.action_handler.setup_replace_community_round(step.action_config)
                self.current_player = self.next_player(round_start=True)
                self.action_handler.first_player_in_round = self.current_player.id

            elif step.action_type == GameActionType.SHOWDOWN:
                logger.info("Moving to showdown")
                self.state = GameState.SHOWDOWN
                self._handle_showdown()

    def _check_condition(self, condition: Dict[str, Any]) -> bool:
        """
        Check if a condition is met.
        
        Args:
            condition: Condition specification from rules
            
        Returns:
            True if condition matches, False otherwise
        """
        # If no condition, then it's always true
        if not condition:
            return True
            
        condition_type = condition.get('type')

        logger.info(f"Checking condition: {condition_type}")
        
        if condition_type == "all_exposed" or condition_type == "any_exposed" or condition_type == "none_exposed":
            # Original conditional states logic for exposed cards (unchanged)
            # This would be for games where dealing depends on exposed cards
            # We should implement this logic if needed
            return True  # Placeholder - implement actual logic as needed
                
        elif condition_type == "board_composition":
            # Condition type for board composition checks
            subset = condition.get('subset', 'default')
            check_type = condition.get('check')
            
            if check_type == "color":
                check_color = condition.get('color', 'black')
                min_count = condition.get('min_count', 2)
                
                # Get cards from the specified subset
                subset_cards = self.table.community_cards.get(subset, [])
                
                # Count cards of the specified color
                color_count = sum(1 for card in subset_cards if card.color == check_color)
                
                # Determine if condition is met
                meets_condition = color_count >= min_count
                logger.info(f"Condition check for {check_color} cards in {subset}: " +
                        f"found {color_count}, need {min_count}, condition {'met' if meets_condition else 'not met'}")
                return meets_condition
                
        elif condition_type == "player_choice":
            # New condition type for player choices
            subset = condition.get('subset')  # The choice variable name
            
            logger.info(f"   subset: {subset}")

            # Check if we have game_choices dictionary
            if not hasattr(self, 'game_choices'):
                logger.warning("No game choices available to check condition")
                return False
                
            # Check for single value match
            if 'value' in condition:
                expected_value = condition.get('value')
                actual_value = self.game_choices.get(subset)
                matches = actual_value == expected_value
                logger.info(f"Checking player choice condition: {subset}={actual_value}, expected {expected_value}, {'match' if matches else 'no match'}")
                return matches
                
            # Check for value in list
            if 'values' in condition:
                expected_values = condition.get('values', [])
                actual_value = self.game_choices.get(subset)
                matches = actual_value in expected_values
                logger.info(f"Checking player choice condition: {subset}={actual_value}, expected one of {expected_values}, {'match' if matches else 'no match'}")
                return matches
        
        # Default: condition not recognized or not implemented
        logger.warning(f"Unknown or unhandled condition type: {condition_type}")
        return False

    def _check_and_skip_conditional_step(self) -> bool:
        """
        Check if the current step has a conditional state that isn't met, and skip it if necessary.
        
        Returns:
            True if the step was skipped, False otherwise
        """
        step = self.rules.gameplay[self.current_step]
        
        # Check for conditional state directly on the GameStep
        if hasattr(step, 'conditional_state') and step.conditional_state:
            conditional_state = step.conditional_state
            
            # Check the condition
            if not self._check_condition(conditional_state):
                logger.info(f"Skipping step {self.current_step}: '{step.name}' - condition not met")
                self._next_step()
                return True
        
        # Check for conditional state in action_config if not found directly on step
        elif step.action_type in [GameActionType.DEAL, GameActionType.DISCARD, 
                                GameActionType.DRAW, GameActionType.EXPOSE,
                                GameActionType.BET]:
            conditional_state = None
            
            if isinstance(step.action_config, dict) and "conditional_state" in step.action_config:
                conditional_state = step.action_config["conditional_state"]
                
                if conditional_state and not self._check_condition(conditional_state):
                    logger.info(f"Skipping step {self.current_step}: '{step.name}' - condition not met")
                    self._next_step()
                    return True
                
        return False

    def _handle_deal(self, config: Dict[str, Any], player_id=None) -> None:
        """
        Handle a dealing action.
        
        Args:
            config: Deal configuration dictionary
            player_id: Optional player ID to deal to. If None, deal to all active players.
        """
        location = config["location"]
        conditional_state = config.get("conditional_state", None)
        wild_card_rules = config.get("wildCards", None)
     
        # Handle conditional dealing based on conditions
        if conditional_state:
            # Use the new _check_condition method to determine if condition is met
            should_deal = self._check_condition(conditional_state)
                       
            # If condition not met skip dealing
            if not should_deal:
                logger.info(f"Conditional dealing - condition not met, skipping deal/discard")
                return  # Skip dealing entirely

            logger.info(f"Conditional dealing - condition met, continuing with deal")

        # Process the deal configuration             
        for card_config in config["cards"]:
            num_cards = card_config["number"]
            protection_option = card_config.get("protection_option")  # NEW

            # NEW: Check if this card has protection options
            if protection_option and location == "player":
                self._handle_protected_deal(card_config, player_id, wild_card_rules)
            else:
                # Existing dealing logic - returns True if should continue, False if should skip
                should_continue = self._handle_standard_deal(card_config, location, player_id, wild_card_rules, conditional_state, num_cards)
                if not should_continue:
                    continue  # Skip this card_config iteration

        # After dealing, update player wild ranks if there are lowest_hole rules
        wild_card_rules = config.get("wildCards", [])
        if any(rule.get("type") == "lowest_hole" for rule in wild_card_rules):
            self._update_player_wild_ranks(wild_card_rules)                    

    def _handle_protected_deal(self, card_config: Dict, player_id: Optional[str], wild_card_rules: List) -> None:
        """Handle dealing with protection option."""
        protection_option = card_config["protection_option"]
        timing = protection_option.get("timing", "post_deal")
        
        # Store wild card rules for later use
        self._current_wild_rules = wild_card_rules
        
        if timing == "pre_deal":
            self._handle_pre_deal_protection(card_config, player_id, wild_card_rules)
        else:
            self._handle_post_deal_protection(card_config, player_id, wild_card_rules)
        
        # Set game state and current player for protection decisions
        if self.pending_protection_decisions:
            self.state = GameState.PROTECTION_DECISION
            # Use the first player from our stored order
            if hasattr(self, 'protection_decision_order') and self.protection_decision_order:
                first_player_id = self.protection_decision_order[0]
                self.current_player = self.table.players[first_player_id]
            else:
                # Fallback
                first_player_id = next(iter(self.pending_protection_decisions.keys()))
                self.current_player = self.table.players[first_player_id]
            logger.info(f"Protection decisions needed - starting with {self.current_player.name}")

    def _handle_post_deal_protection(self, card_config: Dict, player_id: Optional[str], wild_card_rules: List) -> None:
        """Deal card face down first, then offer protection."""
        players_to_deal = self._get_players_to_deal(player_id)
        
        if not hasattr(self, 'pending_protection_decisions'):
            self.pending_protection_decisions = {}
        
        # Store the order of players for protection decisions
        self.protection_decision_order = []
        
        for player in players_to_deal:
            # Deal card face down initially
            card = self.table.deal_card_to_player(player.id, face_up=False)
            
            if card and wild_card_rules:
                self._apply_wild_card_rules_to_card(card, wild_card_rules, False)
            
            # Set up protection decision
            protection_option = card_config["protection_option"]
            cost_name = protection_option["cost"]
            cost = self.named_bets.get(cost_name, 0)
            
            self.pending_protection_decisions[player.id] = {
                "card": card,
                "cost": cost,
                "cost_name": cost_name,
                "prompt": protection_option.get("prompt", f"Pay ${cost} to flip {card} face up?")
            }
            
            # Track the order
            self.protection_decision_order.append(player.id)
            
            logger.info(f"Dealt {card} to {player.name} face down - protection available for ${cost}")

    def _complete_protection_round(self) -> None:
        """Called when all protection decisions are complete."""
        # Update wild cards after all protection decisions
        if hasattr(self, '_current_wild_rules'):
            wild_card_rules = self._current_wild_rules
            if any(rule.get("type") == "lowest_hole" for rule in wild_card_rules):
                self._update_player_wild_ranks(wild_card_rules)
        
        # Clear any temporary state
        if hasattr(self, '_current_wild_rules'):
            delattr(self, '_current_wild_rules')
        if hasattr(self, 'protection_decision_order'):
            delattr(self, 'protection_decision_order')
        
        # Reset game state
        self.state = GameState.DEALING
        self.current_player = None
        
        logger.info("Protection round complete - all decisions made")

    def _handle_standard_deal(self, card_config: Dict, location: str, player_id: Optional[str], 
                            wild_card_rules: List, conditional_state: Dict, num_cards: int) -> bool:
        """
        Handle standard dealing logic.
        
        Returns:
            bool: True if processing should continue, False if this card should be skipped
        """
        # Determine card state - handle conditional state if present
        if conditional_state and "state" not in card_config:
            # Get players to deal to (single player or all active players)
            if player_id:
                # Find the player object by ID
                player = next((p for p in self.table.get_active_players() if p.id == player_id), None)
                players_to_deal = [player] if player else []
                if not player:
                    logger.warning(f"Player with ID {player_id} not found or not active")
            else:
                players_to_deal = self.table.get_active_players()
            
            # Process the conditional logic for each player
            for current_player in players_to_deal:
                # Get player's current visible state
                player_cards = current_player.hand.get_cards()
                condition_type = conditional_state["type"]
                
                # Evaluate the condition
                if condition_type == "all_exposed":
                    condition_met = all(card.visibility == Visibility.FACE_UP for card in player_cards)
                elif condition_type == "any_exposed":
                    condition_met = any(card.visibility == Visibility.FACE_UP for card in player_cards)
                elif condition_type == "none_exposed":
                    condition_met = all(card.visibility == Visibility.FACE_DOWN for card in player_cards)
                else:
                    logger.warning(f"Unknown condition type: {condition_type}")
                    condition_met = False
                
                # Determine state based on condition
                if condition_met:
                    state = conditional_state["true_state"]
                else:
                    state = conditional_state["false_state"]
                    
                face_up = state == "face up"
                
                # Deal the card to this specific player
                if location == "player":
                    # Deal the card
                    card = self.table.deal_card_to_player(current_player.id, face_up=face_up)
                    
                    # Apply wild card rules if this is a Joker
                    if card and wild_card_rules and card.rank == Rank.JOKER:
                        self._apply_wild_card_rules_to_card(card, wild_card_rules, face_up)
                
                logger.info(f"Dealt card to {current_player.name} ({state}) based on condition '{condition_type}'")
        else:
            state = card_config.get("state", "face down")
            # Skip if state is "none" (for conditional dealing where we don't deal)
            if state == "none":
                logger.info("Skipping deal with 'none' state")
                return False  # Signal to skip this card    

            subsets = card_config.get("subset", "default")  # Now can be string or list
            hole_subset = card_config.get("hole_subset", "default")  # Default to "default" if not specified
            face_up = state == "face up"
            
            if location == "player":
                if player_id:
                    # Deal to the specific player by ID
                    player_name = self.table.players[player_id].name or f"Player {player_id}"
                    logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to player {player_name} ({state})")
                    for _ in range(num_cards):
                        card = self.table.deal_card_to_player(player_id, subset=hole_subset, face_up=face_up)
                        # Apply wild card rules if needed
                        if card and wild_card_rules:
                            self._apply_wild_card_rules_to_card(card, wild_card_rules, face_up)
                else:
                    # Deal to all active players
                    logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to each player ({state}.  subset: {hole_subset}, face_up: {face_up})")
                    cards_dealt_dict = self.table.deal_hole_cards(num_cards, subset=hole_subset, face_up=face_up)

                    # Apply wild card rules to any Jokers dealt
                    if wild_card_rules:
                        for active_player_id, cards in cards_dealt_dict.items():
                            for card in cards:
                                # Check if ANY wild card rule applies to this card
                                self._apply_wild_card_rules_to_card(card, wild_card_rules, face_up)
                                    
            else:  # community
                # Convert single string subset to list for consistency
                if isinstance(subsets, str):
                    subsets = [subsets]

                logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to community subsets {subsets} ({state})")
                cards = self.table.deal_community_cards(num_cards, subsets=subsets, face_up=face_up)
                
                # Apply wild card rules to any Jokers dealt to community
                if wild_card_rules and cards:
                    for card in cards:
                        # Check if ANY wild card rule applies to this card
                        self._apply_wild_card_rules_to_card(card, wild_card_rules, face_up)

        return True  # Continue processing

    def _get_players_to_deal(self, player_id: Optional[str]) -> List[Player]:
        """Get list of players to deal to in correct order (SB first)."""
        if player_id:
            player = next((p for p in self.table.get_active_players() if p.id == player_id), None)
            return [player] if player else []
        else:
            # Return players in dealing order (SB first, not BTN first)
            all_players = self.table.get_position_order(include_inactive=True)
            active_players = [p for p in all_players if p.is_active]
            
            if len(active_players) >= 2:
                # Start from SB
                sb_idx = next((i for i, p in enumerate(active_players) 
                            if p.position and p.position.has_position(Position.SMALL_BLIND)), None)
                if sb_idx is not None:
                    return active_players[sb_idx:] + active_players[:sb_idx]
            
            return active_players
    
    def _apply_wild_card_rules_to_card(self, card: Card, wild_rules: List[Dict[str, Any]], face_up: bool) -> None:
        """
        Apply wild card rules to a specific card.
        
        Args:
            card: The card to apply rules to
            wild_rules: List of wild card rules to apply
            face_up: Whether the card is face up
        """
        for rule in wild_rules:
            wild_type = rule.get("type")
            role = rule.get("role", "wild")
            scope = rule.get("scope", "global")
            match_type = rule.get("match", "rank")  # Default to "rank" for backward compatibility

            # Skip lowest_hole rules - they're processed separately after all cards are dealt
            if wild_type == "lowest_hole":
                continue

            # Determine which WildType to use
            if role == "bug":
                wild_card_type = WildType.BUG
            elif role == "wild":
                wild_card_type = WildType.NAMED
            else:
                # For other types, use MATCHING or NATURAL as appropriate
                wild_card_type = WildType.MATCHING
            
            # Handle the new last_community_card type
            if wild_type == "last_community_card":
                # Always make this specific card wild
                card.make_wild(wild_card_type)
                
                if match_type == "rank":
                    # Store the wild rank and make all existing cards of this rank wild
                    target_rank = card.rank
                    self.dynamic_wild_rank = target_rank
                    
                    if scope == "global":
                        self._make_all_existing_matching_rank_wild(target_rank, wild_card_type)
                    
                    logger.info(f"Applied last_community_card rule: {target_rank} rank is now wild")
                    
                elif match_type == "card":
                    # Only this specific card is wild
                    logger.info(f"Applied last_community_card rule: only {card} is wild")
                    
                elif match_type == "suit":
                    # Future extension: all cards of this suit are wild
                    target_suit = card.suit
                    # Implementation would go here
                    logger.info(f"Applied last_community_card rule: {target_suit} suit is now wild")
                
                continue

            # FIRST: Check if card matches the rule type
            card_matches_rule = False
            if wild_type == "joker" and card.rank == Rank.JOKER:
                card_matches_rule = True
            elif wild_type == "rank":
                target_rank = Rank(rule.get("rank", "R"))  # Default to Joker if no rank
                if card.rank == target_rank:
                    card_matches_rule = True
                    

            # Only proceed if the card matches the rule type
            if not card_matches_rule:
                continue                    

            # Handle conditional wild cards (only for matching cards)
            if role == "conditional" and "condition" in rule:
                condition = rule.get("condition", {})
                visibility_condition = condition.get("visibility")
                
                if visibility_condition == "face up" and face_up:
                    # Face up condition met
                    true_role = condition.get("true_role", "wild")
                    true_wild_type = WildType.BUG if true_role == "bug" else WildType.NAMED
                    card.make_wild(true_wild_type)
                    logger.info(f"Applied conditional wild card rule (face up): {wild_type} as {true_role}")
                    
                elif visibility_condition == "face down" and not face_up:
                    # Face down condition met
                    true_role = condition.get("true_role", "wild")
                    true_wild_type = WildType.BUG if true_role == "bug" else WildType.NAMED
                    card.make_wild(true_wild_type)
                    logger.info(f"Applied conditional wild card rule (face down): {wild_type} as {true_role}")
                    
                else:
                    # Condition not met
                    false_role = condition.get("false_role", "wild")
                    false_wild_type = WildType.BUG if false_role == "bug" else WildType.NAMED
                    card.make_wild(false_wild_type)
                    logger.info(f"Applied conditional wild card rule (condition not met): {wild_type} as {false_role}")
            else:
                # Non-conditional wild card (for matching cards)
                card.make_wild(wild_card_type)
                logger.info(f"Applied wild card rule: {wild_type} as {role}")

    def _update_player_wild_ranks(self, wild_rules: List[Dict[str, Any]]) -> None:
        """Update wild ranks for all players based on their current hole cards."""
        logger.info("Updating player wild ranks based on lowest_hole rules")
        for rule in wild_rules:
            if rule.get("type") != "lowest_hole":
                continue
                
            visibility = Visibility.FACE_DOWN if rule.get("visibility") == "face down" else Visibility.FACE_UP
            role = rule.get("role", "wild")
            wild_type = WildType.BUG if role == "bug" else WildType.NAMED
            
            for player in self.table.get_active_players():
                old_wild_rank = self.player_wild_ranks.get(player.id)
                new_wild_rank = self._find_player_wild_rank(player, visibility)
                
                if old_wild_rank != new_wild_rank:
                    # Remove old wild status
                    if old_wild_rank:
                        self._remove_wild_status_for_player(player, old_wild_rank)
                    
                    # Set new wild status
                    if new_wild_rank:
                        self._set_wild_status_for_player(player, new_wild_rank, wild_type)
                        
                    # Update tracking
                    self.player_wild_ranks[player.id] = new_wild_rank
                    
                    logger.info(f"Player {player.name} wild rank changed from {old_wild_rank} to {new_wild_rank}")

    def _find_player_wild_rank(self, player: Player, visibility: Visibility) -> Optional[Rank]:
        """Find the lowest rank card for a player with the specified visibility."""
        hole_cards = player.hand.get_cards()
        eligible_cards = [c for c in hole_cards if c.visibility == visibility]
        
        if not eligible_cards:
            return None
            
        from generic_poker.evaluation.constants import BASE_RANKS
        # BASE_RANKS is ordered high to low (A, K, Q, ..., 3, 2)
        # So we want MAX index for lowest rank
        lowest_card = max(eligible_cards, key=lambda c: BASE_RANKS.index(c.rank.value))
        return lowest_card.rank

    def _remove_wild_status_for_player(self, player: Player, rank: Rank) -> None:
        """Remove wild status from all cards of a specific rank for a player."""
        # Remove from player's hole cards
        for card in player.hand.get_cards():
            if card.rank == rank and card.is_wild:
                card.clear_wild()  # We'll need to add this method to Card
                logger.debug(f"Removed wild status from {card} for player {player.name}")

    def _set_wild_status_for_player(self, player: Player, rank: Rank, wild_type: WildType) -> None:
        """Set wild status for all cards of a specific rank for a player."""
        # Set for player's hole cards - ALL cards of this rank
        for card in player.hand.get_cards():
            if card.rank == rank and not card.is_wild:
                card.make_wild(wild_type)
                logger.debug(f"Made {card} wild for player {player.name}")                  

    def _make_all_existing_matching_rank_wild(self, target_rank: Rank, wild_card_type: WildType) -> None:
        """Make all existing cards of a specific rank wild (not cards still in deck)."""
        
        # Make all player cards of this rank wild
        for player in self.table.players.values():
            for card in player.hand.get_cards():
                if card.rank == target_rank and not card.is_wild:
                    card.make_wild(wild_card_type)
                    logger.debug(f"Made existing card {card} wild for player {player.name}")
        
        # Make all community cards of this rank wild
        for subset_name, cards in self.table.community_cards.items():
            for card in cards:
                if card.rank == target_rank and not card.is_wild:
                    card.make_wild(wild_card_type)
                    logger.debug(f"Made existing community card {card} wild in subset {subset_name}")

    def _handle_roll_die(self, config: Dict[str, Any]) -> None:
        """Handle a die roll action."""
        # Create a special "die" deck
        die_deck = Deck(include_jokers=0, deck_type="die")
        die_deck.shuffle()
        
        # "Deal" a single die face
        die_card = die_deck.deal_card(face_up=True)
        if die_card:
            # Store the result in a special community subset
            die_subset = config.get("subset", "Die")
            if die_subset not in self.table.community_cards:
                self.table.community_cards[die_subset] = []
            self.table.community_cards[die_subset].append(die_card)
            
            # Store the game mode based on the die value
            die_value = int(die_card.rank.value)
            # Store the mode generically - could be used by games other than Binglaha
            self.die_determined_game_mode = "high_low" if die_value <= 3 else "high_only"
            
            logger.info(f"Rolled die: {die_value} - Game mode set to: {self.die_determined_game_mode}")              
                
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
                              
    def _handle_choose(self, config: Dict[str, Any]) -> None:
        """
        Handle a player choice action.
        
        Args:
            config: Choose action configuration
        """
        possible_values = config.get("possible_values", [])
        value_name = config.get("value")
        
        if not possible_values:
            logger.warning("No possible values provided for choice")
            return
            
        # Initialize game_choices if needed
        if not hasattr(self, 'game_choices'):
            self.game_choices = {}
        
        # Determine which player makes the choice (UTG by default)
        # Use the existing table.get_player_after_big_blind method
        chooser = self.table.get_player_after_big_blind()
        
        # Special case for heads-up (2 players) - button chooses
        player_count = len([p for p in self.table.players.values() if p.is_active])
        if player_count <= 3:
            # In heads-up or 3-handed, button player chooses
            players = self.table.get_position_order()
            button_player = next((p for p in players if p.position and p.position.has_position(Position.BUTTON)), None)
            if button_player:
                chooser = button_player
                logger.info(f"Heads-up/3-handed game: Button player {button_player.name} will choose game variant")
        
        if chooser:
            self.current_player = chooser
            logger.info(f"Player {chooser.name} to choose from {possible_values} for {value_name}")
        else:
            logger.warning("Could not determine which player should choose")
            # Don't set a default here - wait for player_action

    def get_effective_forced_bets(game_instance, forced_bets: ForcedBets) -> Dict[str, Any]:
        """Get the effective forced bets configuration based on current game state."""
        if forced_bets.conditionalOrders is not None:
            # Check each conditional order using the existing _check_condition method
            for cond_order in forced_bets.conditionalOrders:
                condition = cond_order['condition']
                if game_instance._check_condition(condition):
                    return cond_order['forcedBet']
            
            # No conditions matched, return default
            return forced_bets.default
        else:
            # Simple configuration
            return {
                'style': forced_bets.style,
                'rule': forced_bets.rule,
                'bringInEval': forced_bets.bringInEval
            }
    
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

        elif bet_type == "blinds":
            positions = self.table.get_position_order()

            # Determine who posts the blind based on betting order
            if self.rules.betting_order.initial == "dealer":
                # New England Hold'em style - dealer posts blind (and possibly ante)
                blind_player = next((p for p in positions if p.position and p.position.has_position(Position.BUTTON)), None)
                blind_amount = self.big_blind  # Use big_blind as the single blind amount
                blind_name = "dealer blind"
                ante_player = blind_player
            else:
                # Traditional style - separate small and big blinds
                sb_player = next((p for p in positions if p.position and p.position.has_position(Position.SMALL_BLIND)), None)
                bb_player = next((p for p in positions if p.position and p.position.has_position(Position.BIG_BLIND)), None)
                ante_player = bb_player

                # Post small blind
                if sb_player and self.small_blind > 0:
                    sb_amount = min(self.small_blind, sb_player.stack)
                    sb_player.stack -= sb_amount
                    self.betting.place_bet(sb_player.id, sb_amount, sb_player.stack + sb_amount, is_forced=True)
                    logger.info(f"{sb_player.name} posts small blind of ${sb_amount}...")

                # Post big blind
                if bb_player and self.big_blind > 0:
                    bb_amount = min(self.big_blind, bb_player.stack)
                    bb_player.stack -= bb_amount
                    self.betting.place_bet(bb_player.id, bb_amount, bb_player.stack + bb_amount, is_forced=True)
                    logger.info(f"{bb_player.name} posts big blind of ${bb_amount}...")
                     
            # Handle dealer blind + ante (New England Hold'em)
            if self.rules.betting_order.initial == "dealer" and blind_player:
                # Post the dealer blind
                if self.big_blind > 0:
                    blind_amount = min(self.big_blind, blind_player.stack)
                    blind_player.stack -= blind_amount
                    self.betting.place_bet(blind_player.id, blind_amount, blind_player.stack + blind_amount, is_forced=True)
                    logger.info(f"{blind_player.name} posts {blind_name} of ${blind_amount}...")
                    
            # Post the ante (if configured)
            if self.ante and self.ante > 0 and ante_player:
                ante_amount = min(self.ante, ante_player.stack)
                ante_player.stack -= ante_amount
                self.betting.place_bet(ante_player.id, ante_amount, ante_player.stack + ante_amount, is_forced=True, is_ante=True)
                logger.info(f"{ante_player.name} posts ante of ${ante_amount}...")                     

        elif bet_type == "bring-in":
            bring_in_amount = self.bring_in or self.small_bet  # Use bring_in if set, else small_bet
            bring_in_player = self.table.get_bring_in_player(bring_in_amount)
            if bring_in_player:
                self.current_player = bring_in_player
                # Get all face-up cards for better logging
                face_up_cards = [card for card in bring_in_player.hand.cards 
                               if card.visibility == Visibility.FACE_UP]
                cards_display = ", ".join(str(card) for card in face_up_cards) if face_up_cards else "no face-up cards"
                logger.info(f"Bring-in player: {bring_in_player.name} with face-up cards: {cards_display}")
            else:
                logger.error("No bring-in player determined")
                self.current_player = active_players[0]  # Fallback
            # No current_player set; next_player() will use betting_order.initial
                           
        logger.debug(f"Starting betting round with new_round(True)")
        self.betting.new_round(preserve_current_bet=True)  # Reset bets, keep forced bets in pot
        
        if bet_type == "bring-in":
            # For bring-in, the bring-in player continues to act
            # current_player is already set above
            pass
        elif bet_type in ["antes", "blinds"]:
            # For antes and blinds, no one acts after posting - game should advance to next step
            self.current_player = None
            logger.info(f"DEBUG: After forced bets ({bet_type}), set current_player to None - ready for next step")
        else:
            # For other bet types, set first player to act
            logger.info(f"DEBUG: Before next_player call, current_player: {self.current_player.name if self.current_player else None}")
            self.current_player = self.next_player(round_start=True)
            logger.info(f"DEBUG: After next_player call, current_player: {self.current_player.name if self.current_player else None}")

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

        # Process the next step
        self.process_current_step()
        
    def _get_subsequent_order_type(self) -> str:
        """
        Determine the subsequent betting order type, considering conditional orders.
        
        Returns:
            The order type string (e.g., "dealer", "high_hand", "last_actor", etc.)
        """
        subsequent_config = self.rules.betting_order.subsequent

        logger.debug(f"  Subsequent order config: {subsequent_config}")
        
        # If it's a simple string, return it directly
        if isinstance(subsequent_config, str):
            return subsequent_config
        
        # If it's a conditional configuration, evaluate conditions
        if isinstance(subsequent_config, dict) and "conditionalOrders" in subsequent_config:
            for conditional_order in subsequent_config["conditionalOrders"]:
                condition = conditional_order["condition"]
                if self._check_condition(condition):
                    return conditional_order["order"]
            
            # No conditions matched, use default
            return subsequent_config.get("default", "dealer")
        
        # Fallback
        return "dealer"
        
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
        
        logger.debug(f"  round_start = {round_start}")
        logger.debug(f"  is_voluntary_bet = {is_voluntary_bet}" )
        logger.debug(f"  forced_bettors = {forced_bettors}" )
        logger.debug(f"  self.betting.betting_round = {self.betting.betting_round}" )

        # Check if this is the first voluntary bet after forced bets
        is_first_after_blinds = (self.betting.betting_round == 0 and is_voluntary_bet and forced_bettors)
        
        # Check if this is a continued action after player has chosen something
        is_after_choice = (hasattr(self, 'game_choices') and self.game_choices and self.current_player is not None)
        
        logger.debug(f"  is_first_after_blinds = {is_first_after_blinds}")
        logger.debug(f"  is_after_choice = {is_after_choice}")

        if round_start:
            # In Paradise Road Pick'em, when a player chooses a game type, they should
            # be the first to act in the subsequent betting round. This is true for any
            # choice, not just stud games.
            if is_first_after_blinds:
                # If we've just had a player make a choice, let them act first
                if is_after_choice and self.action_handler.current_substep == 0:
                    logger.debug(f"After game choice: keeping current player {self.current_player.name}")
                    return self.current_player
                
                # Otherwise use standard first-after-blinds logic 
                last_forced_bettor_id = forced_bettors[-1] if forced_bettors else None
                logger.debug(f"  last_forced_bettor_id: {last_forced_bettor_id}")
                if last_forced_bettor_id:
                    players = self.table.get_position_order()
                    logger.debug(f"  position_order: {[p.name for p in players]}")
                    try:
                        forced_bettor_idx = next(i for i, p in enumerate(players) if p.id == last_forced_bettor_id)
                        logger.debug(f"  forced_bettor_idx: {forced_bettor_idx}")
                        next_idx = (forced_bettor_idx + 1) % len(players)
                        logger.debug(f"  next_idx (before active check): {next_idx}")
                        while not players[next_idx].is_active:
                            logger.debug(f"  player {players[next_idx].name} is not active, skipping")
                            next_idx = (next_idx + 1) % len(players)
                            if next_idx == forced_bettor_idx:  # Full circle
                                return None
                        next_player = players[next_idx]
                        logger.debug(f"First voluntary betting round: Starting with {next_player.name}")
                        return next_player
                    except StopIteration:
                        logger.debug(f"  StopIteration - using fallback")
                        return active_players[0]  # Fallback                                  

            else:
                # Use subsequent order for all other round starts (including draw phases)
                # Now using the conditional order evaluation
                order_type = self._get_subsequent_order_type()
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
                    forced_bets = Game.get_effective_forced_bets(self, self.rules.forced_bets)
                    next_player = self.table.get_player_with_best_hand(forced_bets)
                    logger.debug(f"  high_hand: Starting with {next_player.name}")       
                elif order_type == "last_actor":
                    # New England Hold'em: player who would have been next to act goes first
                    if self.betting.last_actor_id:
                        last_actor = self.table.players.get(self.betting.last_actor_id)
                        if last_actor and last_actor.is_active:
                            # Get the player AFTER the last actor
                            players = self.table.get_position_order()
                            try:
                                last_actor_idx = next(i for i, p in enumerate(players) if p.id == self.betting.last_actor_id)
                                next_idx = (last_actor_idx + 1) % len(players)
                                while not players[next_idx].is_active:
                                    next_idx = (next_idx + 1) % len(players)
                                    if next_idx == last_actor_idx:  # Full circle
                                        next_player = None
                                        break
                                else:
                                    next_player = players[next_idx]
                                
                                if next_player:
                                    logger.debug(f"  last_actor: Last actor was {last_actor.name}, starting with {next_player.name}")
                                else:
                                    logger.debug(f"  last_actor: Could not find next player after {last_actor.name}")
                                    next_player = self.table.get_next_active_player(self.table.button_pos)
                            except StopIteration:
                                logger.debug(f"  last_actor not found in position order, falling back to dealer")
                                next_player = self.table.get_next_active_player(self.table.button_pos)
                        else:
                            # Fallback if last actor is no longer active
                            logger.debug(f"  last_actor not active, falling back to dealer")
                            next_player = self.table.get_next_active_player(self.table.button_pos)
                    else:
                        # No last actor recorded, fallback to dealer
                        logger.debug(f"  no last_actor recorded, falling back to dealer")
                        next_player = self.table.get_next_active_player(self.table.button_pos)                            
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
            logger.debug(f"Position order: {[p.name for p in players]}")
            logger.debug(f"Current player: {self.current_player.name}")
            try:
                current_idx = next(i for i, p in enumerate(players) if p.id == self.current_player.id)
                logger.debug(f"Current player index: {current_idx}")
                next_idx = (current_idx + 1) % len(players)
                logger.debug(f"Next index (before active check): {next_idx}")
                while not players[next_idx].is_active:
                    logger.debug(f"Player {players[next_idx].name} is not active, skipping")
                    next_idx = (next_idx + 1) % len(players)
                    if next_idx == current_idx:  # Full circle
                        return None
                logger.debug(f"Next player: {players[next_idx].name}")
                return players[next_idx]
            except StopIteration:
                return active_players[0]  # Fallback
        return active_players[0]  # Default fallback


    def _handle_showdown(self) -> None:
        """Handle showdown and determine winners."""
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            self.state = GameState.COMPLETE
            return
        
        # Transfer declarations to the showdown manager if needed
        if hasattr(self, 'declarations') and self.rules.showdown.declaration_mode == "declare":
            self.showdown_manager.set_declarations(self.declarations)

        # Transfer game_choices to ShowdownManager if needed
        if hasattr(self, 'game_choices'):
            self.showdown_manager.game_choices = self.game_choices            
        
        # Use the ShowdownManager to handle the showdown
        self.last_hand_result = self.showdown_manager.handle_showdown()
        self.state = GameState.COMPLETE

    def _handle_fold_win(self) -> None:
        """Handle case when all but one player folds."""
        active_players = [p for p in self.table.players.values() if p.is_active]
        
        # Use the ShowdownManager to handle the fold win
        self.last_hand_result = self.showdown_manager.handle_fold_win(active_players)
        self.state = GameState.COMPLETE

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

    