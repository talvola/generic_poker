import logging
from typing import List, Optional, Tuple, Dict, Set, Any

from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.core.card import Card, Visibility
from generic_poker.game.table import Player
from generic_poker.game.action_result import ActionResult
from generic_poker.game.betting import PlayerBet, BetType
from generic_poker.config.loader import BettingStructure, GameActionType

logger = logging.getLogger(__name__)

class PlayerActionHandler:
    def __init__(self, game):
        """Initialize with a reference to the Game instance."""
        self.game = game
        # Action-related state variables
        self.first_player_in_round: Optional[str] = None  # ID of the first player to act in the current non-betting round
        self.current_substep: Optional[int] = None
        self.grouped_step_completed: set = set()
        self.player_completed_subactions: Dict[str, Set[int]] = {}  # {player_id: set of completed subaction indices}
        self.pending_exposures: Dict[str, List[Card]] = {}
        self.pending_passes: Dict[str, Tuple[Card, str]] = {}
        self.pending_declarations: Dict[str, List[Dict]] = {}  # player_id -> [{"pot_index": int, "declaration": str}, ...]

    def setup_grouped_step(self, subactions: List[Dict]) -> None:
        """Initialize tracking for a grouped step."""
        active_players = [p.id for p in self.game.table.get_active_players()]
        self.player_completed_subactions = {pid: set() for pid in active_players}
        self.current_substep = 0
        self.grouped_step_completed = set()

    def get_valid_actions(self, player_id: str) -> List[Tuple[PlayerAction, Optional[int], Optional[int]]]:
        """
        Get list of valid actions for a player.

        Args:
            player_id: ID of player to check

        Returns:
            List of tuples (action, min_amount, max_amount) where amounts are None if not applicable
        """
        if player_id != self.game.current_player.id:
            logger.info(f"Not this player's turn ({player_id} vs {self.game.current_player.id})")
            return []

        step = self.game.rules.gameplay[self.game.current_step]

        # Handle CHOOSE action type
        if step.action_type == GameActionType.CHOOSE:
            logger.debug(f"Getting valid actions for player {player_id} for CHOOSE action")
            # Return CHOOSE action with possible values
            possible_values = step.action_config.get("possible_values", [])
            return [(PlayerAction.CHOOSE, 0, len(possible_values) - 1, possible_values)]
            
        config = step.action_config

        # Handle grouped actions
        if step.action_type == GameActionType.GROUPED:
            if self.current_substep is None or self.current_substep >= len(config):
                logger.warning(f"Invalid substep {self.current_substep} for grouped step {step.name}")
                return []
            subaction = config[self.current_substep]
            subaction_key = list(subaction.keys())[0]

            logger.debug(f"Getting valid actions for player {player_id} in grouped step {step.name}, subaction: {subaction_key} with state {self.game.state}")

            if subaction_key == "bet" and self.game.state == GameState.BETTING:
                return self._get_betting_actions(player_id, subaction["bet"])
            elif subaction_key == "discard" and self.game.state == GameState.DRAWING:
                card_config = subaction["discard"]["cards"][0]
                max_discard = card_config.get("number", 0)
                min_discard = card_config.get("min_number", max_discard)
                return [(PlayerAction.DISCARD, min_discard, max_discard)]
            elif subaction_key == "draw" and self.game.state == GameState.DRAWING:
                card_config = subaction["draw"]["cards"][0]
                max_discard = card_config.get("number", 0)
                min_discard = card_config.get("min_number", 0)
                return [(PlayerAction.DRAW, min_discard, max_discard)]
            elif subaction_key == "separate" and self.game.state == GameState.DRAWING:
                total_cards = sum(cfg["number"] for cfg in subaction["separate"]["cards"])
                return [(PlayerAction.SEPARATE, total_cards, total_cards)]
            elif subaction_key == "expose" and self.game.state == GameState.DRAWING:
                card_config = subaction["expose"]["cards"][0]
                max_expose = card_config.get("number", 0)
                min_expose = card_config.get("min_number", max_expose)
                return [(PlayerAction.EXPOSE, min_expose, max_expose)]            
            elif subaction_key == "pass" and self.game.state == GameState.DRAWING:
                num_to_pass = subaction["pass"]["cards"][0]["number"]
                return [(PlayerAction.PASS, num_to_pass, num_to_pass)]
            elif subaction_key == "declare" and self.game.state == GameState.DRAWING:
                return [(PlayerAction.DECLARE, None, None)]    
            # we could have a grouped deal action depending on the game
            # this isn't really the player dealing - it's more of accepting a deal
            elif subaction_key == "deal" and self.game.state == GameState.DEALING:
                logger.debug(f"Not a true player action - grouped deal action for player {player_id} in grouped step {step.name}")
                return [(PlayerAction.DEAL, None, None)]                             
            return []

        # Non-grouped actions
        if self.game.state == GameState.DRAWING:
            if hasattr(self.game, "current_discard_config"):
                card_config = self.game.current_discard_config["cards"][0]
                max_discard = card_config.get("number", 0)
                min_discard = card_config.get("number", 0)
                return [(PlayerAction.DISCARD, min_discard, max_discard)]
            elif hasattr(self.game, "current_draw_config"):
                card_config = self.game.current_draw_config["cards"][0]
                max_discard = card_config.get("number", 0)
                min_discard = card_config.get("min_number", 0)
                return [(PlayerAction.DRAW, min_discard, max_discard)]
            elif hasattr(self.game, "current_separate_config"):
                total_cards = sum(cfg["number"] for cfg in self.game.current_separate_config["cards"])
                return [(PlayerAction.SEPARATE, total_cards, total_cards)]
            elif hasattr(self.game, "current_expose_config"):
                card_config = self.game.current_expose_config["cards"][0]
                max_expose = card_config.get("number", 0)
                min_expose = card_config.get("min_number", max_expose)
                return [(PlayerAction.EXPOSE, min_expose, max_expose)]
            elif hasattr(self.game, "current_pass_config"):
                num_to_pass = self.game.current_pass_config["cards"][0]["number"]
                return [(PlayerAction.PASS, num_to_pass, num_to_pass)]
            elif hasattr(self.game, "current_declare_config"):
                return [(PlayerAction.DECLARE, None, None)]            

        if self.game.state == GameState.BETTING:
            return self._get_betting_actions(player_id, config)
        return []

    def _get_betting_actions(self, player_id: str, bet_config: Dict) -> List[Tuple[PlayerAction, Optional[int], Optional[int]]]:
        """Helper method to get betting actions."""
        logger.debug(f"Getting betting actions for player {player_id} with bet_config: {bet_config} ({self.game.betting.bring_in_posted})")
        player = self.game.table.players[player_id]
        current_bet = self.game.betting.current_bets.get(player_id, PlayerBet()).amount
        required_bet = self.game.betting.get_required_bet(player_id)

        logger.debug(f"  Current bet: {current_bet}, Required bet: {required_bet}, Player stack: {player.stack}")

        valid_actions = []

        if bet_config.get("type") == "bring-in" and not self.game.betting.bring_in_posted:
            valid_actions.append((PlayerAction.BRING_IN, self.game.bring_in, self.game.bring_in))
            if player.stack >= self.game.small_bet:
                valid_actions.append((PlayerAction.BET, self.game.small_bet, self.game.small_bet))
            elif player.stack > self.game.bring_in:
                valid_actions.append((PlayerAction.BET, player.stack, player.stack))
            return valid_actions

        valid_actions.append((PlayerAction.FOLD, None, None))
        if required_bet > 0:
            if player.stack >= required_bet:
                valid_actions.append((PlayerAction.CALL, self.game.betting.current_bet, self.game.betting.current_bet))
            elif player.stack > 0:
                total_amount = current_bet + player.stack
                valid_actions.append((PlayerAction.CALL, total_amount, total_amount))
        else:
            valid_actions.append((PlayerAction.CHECK, None, None))

        zero_cards_betting = bet_config.get("zeroCardsBetting")
        hole_cards = player.hand.get_cards()
        if zero_cards_betting == "call_only" and len(hole_cards) == 0:
            return valid_actions

        if player.stack > required_bet:
            current_total = self.game.betting.current_bet
            is_stud = self.game.rules.forced_bets.style == "bring-in"
            step_type = bet_config.get("type", "small")
            bet_size = self.game.small_bet if step_type == "small" else self.game.big_bet

            active_players = [p for p in self.game.table.get_position_order() if p.is_active]
            bring_in_idx = next((i for i, p in enumerate(active_players) if self.game.betting.current_bets.get(p.id, PlayerBet()).posted_blind), -1)
            acted_count = sum(1 for b in self.game.betting.current_bets.values() if b.has_acted or b.posted_blind)
            is_first_after_bring_in = (is_stud and step_type == "small" and bring_in_idx != -1 and
                                       active_players[(bring_in_idx + 1) % len(active_players)].id == player_id and
                                       acted_count <= 1)

            logger.debug(f"Player {player.name} (ID: {player_id}) is first after bring-in: {is_first_after_bring_in}, current_total: {current_total}")
            logger.debug(f"  is_stud= {is_stud}, step_type: {step_type}, bring_in_idx: {bring_in_idx}, acted_count: {acted_count}, active: {active_players[(bring_in_idx + 1) % len(active_players)].id}")
            logger.debug(f"  bet_size: {bet_size}")
            if is_first_after_bring_in:
                # if the previous player completed instead of bet, then allow a raise here
                if current_total == self.game.bring_in:
                    action = PlayerAction.BET
                    min_amount = self.game.small_bet
                    max_amount = min_amount if self.game.betting_structure == BettingStructure.LIMIT else self.game.betting.get_max_bet(player_id, BetType.SMALL, player.stack)
                    logger.debug(f"   Player {player.name} (ID: {player_id}) min_amount: {min_amount}, max_amount: {max_amount}")
                else:
                    action = PlayerAction.RAISE
                    min_amount = self.game.betting.get_min_raise(player_id)
                    max_amount = min_amount if self.game.betting_structure == BettingStructure.LIMIT else self.game.betting.get_max_bet(player_id, BetType.SMALL, player.stack)
                    logger.debug(f"   Player {player.name} (ID: {player_id}) min_amount: {min_amount}, max_amount: {max_amount}")
            elif current_total == 0:
                action = PlayerAction.BET
                min_amount = bet_size
                max_amount = min_amount if self.game.betting_structure == BettingStructure.LIMIT else self.game.betting.get_max_bet(player_id, BetType.SMALL if step_type == "small" else BetType.BIG, player.stack)
                logger.debug(f"   Player {player.name} (ID: {player_id}) min_amount: {min_amount}, max_amount: {max_amount}")
            else:
                action = PlayerAction.RAISE
                min_amount = self.game.betting.get_min_raise(player_id)
                max_amount = min_amount if self.game.betting_structure == BettingStructure.LIMIT else self.game.betting.get_max_bet(player_id, BetType.BIG, player.stack)
                logger.debug(f"   Player {player.name} (ID: {player_id}) min_amount: {min_amount}, max_amount: {max_amount}")

            if player.stack >= min_amount:
                valid_actions.append((action, min_amount, max_amount))
            else:
                all_in_amount = player.stack + current_bet
                valid_actions.append((action, all_in_amount, all_in_amount))

        return valid_actions

    def handle_action(self, player_id: str, action: PlayerAction, amount: int = 0, cards: Optional[List[Card]] = None, declaration_data: Optional[List[Dict]] = None, choice_value: Optional[str] = None) -> ActionResult:
        """
        Handle a player action.

        Args:
            player_id: ID of acting player
            action: Action being taken
            amount: Bet amount if applicable
            cards: Cards involved in the action (e.g., discard)

        Returns:
            ActionResult with success, error, and advance_step flags
        """
        player = self.game.table.players[player_id]
        if player_id != self.game.current_player.id:
            logger.warning(f"Invalid action - not {player.name}'s turn")
            return ActionResult(success=False, error="Not your turn")
        active_players = [p for p in self.game.table.players.values() if p.is_active]

        step = self.game.rules.gameplay[self.game.current_step]

        logger.debug(f"Handling action {action} for player {player.name} (ID: {player_id})")

        # Handle the CHOOSE action
        if action == PlayerAction.CHOOSE and step.action_type == GameActionType.CHOOSE:
            # Validate the player
            if player_id != self.game.current_player.id:
                return ActionResult(success=False, message="Not your turn to choose")
            
            # Get the choose config
            config = step.action_config
            possible_values = config.get("possible_values", [])
            value_name = config.get("value")
            
            if not possible_values:
                return ActionResult(success=False, message="No choices available")
            
            # Determine the chosen value
            if choice_value is not None:
                # Direct value provided
                if choice_value not in possible_values:
                    return ActionResult(success=False, message=f"Invalid choice: {choice_value}")
                chosen_value = choice_value
            else:
                # Use amount as index
                choice_index = min(max(0, amount), len(possible_values) - 1)
                chosen_value = possible_values[choice_index]
            
            # Store the choice
            if not hasattr(self.game, 'game_choices'):
                self.game.game_choices = {}
                
            self.game.game_choices[value_name] = chosen_value
            logger.info(f"Player {player_id} chose {chosen_value} for {value_name}")
            
            # Handle special setup for stud games
            if chosen_value in ["Seven Card Stud", "Seven Card Stud 8", "Razz"]:
                self.game.is_stud_game = True
                self.game.next_stud_street = 4
                self.game.stud_order = "low" if chosen_value == "Razz" else "high"
            else:
                self.game.is_stud_game = False
                
            # Advance to next step
            return ActionResult(success=True, advance_step=True)
    
        # Handle grouped actions
        if step.action_type == GameActionType.GROUPED:
            return self._handle_grouped_action(player_id, action, amount, cards)

        # Non-grouped actions
        if action in [PlayerAction.DISCARD, PlayerAction.DRAW]:
            if self.game.state != GameState.DRAWING:
                return ActionResult(success=False, error="Cannot discard/draw in current state")
            if not cards:
                cards = []
            if not self._handle_discard_action(player, cards):
                return ActionResult(success=False, error="Invalid discard/draw action")
            logger.info(f"{player.name} {'discards' if action == PlayerAction.DISCARD else 'draws'} {len(cards)} cards: {cards}")
            self.game.current_player = self.game.next_player(round_start=False)
            if self._check_discard_round_complete():
                return ActionResult(success=True, advance_step=True)
            return ActionResult(success=True)

        if action == PlayerAction.SEPARATE:
            if self.game.state != GameState.DRAWING or not hasattr(self.game, "current_separate_config"):
                return ActionResult(success=False, error="Cannot separate in current state")
            if not cards:
                return ActionResult(success=False, error="No cards specified")
            if not self._handle_separate_action(player, cards):
                return ActionResult(success=False, error="Invalid separation")
            logger.info(f"{player.name} separates their cards: {cards}")
            self.game.current_player = self.game.next_player(round_start=False)
            if self._check_separate_round_complete():
                return ActionResult(success=True, advance_step=True)
            return ActionResult(success=True)

        if action == PlayerAction.EXPOSE:
            if self.game.state != GameState.DRAWING or not hasattr(self.game, "current_expose_config"):
                return ActionResult(success=False, error="Cannot expose in current state")
            if not cards:
                cards = []
            if not self._validate_expose_action(player, cards):
                return ActionResult(success=False, error="Invalid exposure")
            
            # Check if this is an immediate expose action
            is_immediate = False
            config = self.game.current_expose_config["cards"][0]
            if config.get("immediate", False):
                is_immediate = True

            if is_immediate:
                # Apply exposure immediately
                for card in cards:
                    if card in player.hand.get_cards() and card.visibility == Visibility.FACE_DOWN:
                        card.visibility = Visibility.FACE_UP
                        logger.info(f"Player {player.name} immediately exposed {card}")
                
                # When grouped with other actions, move to next substep
                if hasattr(self, "current_substep") and self.current_substep is not None:
                    step = self.game.rules.gameplay[self.game.current_step]
                    if step.action_type == GameActionType.GROUPED:
                        self.player_completed_subactions[player_id].add(self.current_substep)
                        # Check if we've completed all substeps
                        if self.current_substep == len(step.action_config) - 1:
                            self.grouped_step_completed.add(player_id)
                            self.current_substep = 0
                            self.game.current_player = self.game.next_player(round_start=False)
                        else:
                            # Move to next substep (likely dealing the next card)
                            self.current_substep += 1
                            self._update_state_for_next_subaction(step.action_config)
                        return ActionResult(success=True)
            else:                
                self.pending_exposures[player_id] = cards
                logger.info(f"{player.name} exposes {len(cards)} cards: {cards}")
                self.game.current_player = self.game.next_player(round_start=False)
                if self._check_expose_round_complete():
                    self._apply_all_exposures()
                    return ActionResult(success=True, advance_step=True)
                return ActionResult(success=True)

        if action == PlayerAction.PASS:
            if self.game.state != GameState.DRAWING or not hasattr(self.game, "current_pass_config"):
                return ActionResult(success=False, error="Cannot pass in current state")
            if not cards:
                return ActionResult(success=False, error="No cards specified")
            if not self._validate_pass_action(player, cards):
                return ActionResult(success=False, error="Invalid pass")
            current_idx = active_players.index(player)
            recipient_idx = (current_idx + 1) % len(active_players)
            recipient_id = active_players[recipient_idx].id
            self.pending_passes[player_id] = (cards[0], recipient_id)
            logger.info(f"{player.name} passes {len(cards)} cards to {recipient_id}: {cards}")
            self.game.current_player = self.game.next_player(round_start=False)
            if self._check_pass_round_complete():
                self._apply_all_passes()
                return ActionResult(success=True, advance_step=True)
            return ActionResult(success=True)
        
        if action == PlayerAction.DECLARE:
            if self.game.state != GameState.DRAWING or not hasattr(self.game, "current_declare_config"):
                return ActionResult(success=False, error="Cannot declare in current state")
            if not declaration_data:
                return ActionResult(success=False, error="No declaration data specified")
            if not self._validate_declare_action(player, declaration_data):
                return ActionResult(success=False, error="Invalid declaration")
            self.pending_declarations[player_id] = declaration_data
            logger.info(f"{player.name} declares: {declaration_data}")
            self.game.current_player = self.game.next_player(round_start=False)
            if self._check_declare_round_complete():
                self._apply_all_declarations()
                return ActionResult(success=True, advance_step=True)
            return ActionResult(success=True)        

        # Betting actions
        if self.game.state != GameState.BETTING:
            return ActionResult(success=False, error="Cannot bet in current state")
        return self._handle_betting_action(player_id, action, amount)
   
    def _handle_grouped_action(self, player_id: str, action: PlayerAction, amount: int, cards: Optional[List[Card]]) -> ActionResult:
        """Handle actions within a grouped step."""
        player = self.game.table.players[player_id]
        step = self.game.rules.gameplay[self.game.current_step]
        subactions = step.action_config
        current_subaction = subactions[self.current_substep]
        subaction_key = list(current_subaction.keys())[0]
        active_players = set(p.id for p in self.game.table.get_active_players())

        logger.debug(f"Handling grouped action {action} for player {player.name} (ID: {player_id}), subaction: {subaction_key}, current_substep: {self.current_substep}")

        if "bet" in subaction_key and action in [PlayerAction.CHECK, PlayerAction.CALL, PlayerAction.BET, PlayerAction.RAISE, PlayerAction.FOLD, PlayerAction.BRING_IN]:
            if self.game.state != GameState.BETTING:
                return ActionResult(success=False, error="Cannot bet in current state")
            result = self._handle_betting_action(player_id, action, amount, manage_player=False)
            if not result.success:
                return result
            # Track completion (even if folding, as it affects betting round)
            self.player_completed_subactions[player_id].add(self.current_substep)
            if action == PlayerAction.FOLD:
                # Player folds, skip remaining subactions
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            elif self.player_completed_subactions[player_id] == set(range(len(subactions))):
                # Player has completed all subactions (e.g., responding to a raise), advance to next player
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                # Move to next subaction
                logger.info(f"{player.name} bet - incrementing substep")
                self.current_substep += 1
                self._update_state_for_next_subaction(subactions)

        elif "discard" in subaction_key and action == PlayerAction.DISCARD:
            if self.game.state != GameState.DRAWING:
                return ActionResult(success=False, error="Cannot discard in current state")
            discard_config = current_subaction["discard"]
            card_config = discard_config["cards"][0]
            min_discard = card_config.get("min_number", 0)
            max_discard = card_config.get("number", 0)
            once_per_step = card_config.get("oncePerStep", False)
            
            # Check oncePerStep using player_completed_subactions
            if once_per_step and self.current_substep in self.player_completed_subactions[player_id]:
                return ActionResult(success=False, error="Discard already completed")
            
            # Validate discard amount
            if not cards and min_discard > 0:
                return ActionResult(success=False, error="No cards specified when required")
            elif cards and (len(cards) < min_discard or len(cards) > max_discard):
                return ActionResult(success=False, error=f"Invalid number of cards: must be between {min_discard} and {max_discard}")
            
            if not self._handle_discard_action(player, cards):
                return ActionResult(success=False, error="Invalid discard action")
            
            logger.info(f"{player.name} discards {len(cards)} cards: {cards}")
            self.player_completed_subactions[player_id].add(self.current_substep)
            # Check if all subactions are complete
            if self.current_substep == len(subactions) - 1:
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                self.current_substep += 1
            self._update_state_for_next_subaction(subactions)

        elif "draw" in subaction_key and action == PlayerAction.DRAW:
            if self.game.state != GameState.DRAWING:
                return ActionResult(success=False, error="Cannot draw in current state")
            if not cards:
                return ActionResult(success=False, error="No cards specified")
            if not self._handle_discard_action(player, cards):  # Using discard logic for draw
                return ActionResult(success=False, error="Invalid draw action")
            logger.info(f"{player.name} draws {len(cards)} cards: {cards}")
            self.player_completed_subactions[player_id].add(self.current_substep)
            if self.current_substep == len(subactions) - 1:
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                self.current_substep += 1
            self._update_state_for_next_subaction(subactions)

        elif "separate" in subaction_key and action == PlayerAction.SEPARATE:
            if self.game.state != GameState.DRAWING:
                return ActionResult(success=False, error="Cannot separate in current state")
            if not cards:
                return ActionResult(success=False, error="No cards specified")
            if not self._handle_separate_action(player, cards):
                return ActionResult(success=False, error="Invalid separation")
            logger.info(f"{player.name} separates their cards: {cards}")
            self.player_completed_subactions[player_id].add(self.current_substep)
            if self.current_substep == len(subactions) - 1:
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                self.current_substep += 1
            self._update_state_for_next_subaction(subactions)

        elif "expose" in subaction_key and action == PlayerAction.EXPOSE:
            expose_config = current_subaction["expose"]

            if self.game.state != GameState.DRAWING:
                return ActionResult(success=False, error="Cannot expose in current state")
            if not cards:
                cards = []
            if not self._validate_expose_action(player, cards):
                return ActionResult(success=False, error="Invalid exposure")       

            # Check if this is an immediate expose
            is_immediate = expose_config["cards"][0].get("immediate", False)
            logger.debug(f"Player {player.name} is exposing cards: {cards}, immediate: {is_immediate}")
            
            if is_immediate:
                # Apply exposure immediately
                for card in cards:
                    if card in player.hand.get_cards() and card.visibility == Visibility.FACE_DOWN:
                        card.visibility = Visibility.FACE_UP
                        logger.info(f"Player {player.name} immediately exposed {card}")
            else:
                # Use pending exposures
                self.pending_exposures[player_id] = cards
                logger.info(f"{player.name} will expose {len(cards)} cards: {cards}")            

            self.player_completed_subactions[player_id].add(self.current_substep)

            # Check if all substeps are complete for this player
            if self.current_substep == len(subactions) - 1:
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                self.current_substep += 1
            self._update_state_for_next_subaction(subactions)

        elif "pass" in subaction_key and action == PlayerAction.PASS:
            if self.game.state != GameState.DRAWING:
                return ActionResult(success=False, error="Cannot pass in current state")
            if not cards:
                return ActionResult(success=False, error="No cards specified")
            if not self._validate_pass_action(player, cards):
                return ActionResult(success=False, error="Invalid pass")
            active_players_list = [p for p in self.game.table.players.values() if p.is_active]
            current_idx = active_players_list.index(player)
            recipient_idx = (current_idx + 1) % len(active_players_list)
            recipient_id = active_players_list[recipient_idx].id
            self.pending_passes[player_id] = (cards[0], recipient_id)
            logger.info(f"{player.name} passes {len(cards)} cards to {recipient_id}: {cards}")
            self.player_completed_subactions[player_id].add(self.current_substep)
            if self.current_substep == len(subactions) - 1:
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                self.current_substep += 1
            self._update_state_for_next_subaction(subactions)

        elif subaction_key == "declare" and action == PlayerAction.DECLARE:
            if self.game.state != GameState.DECLARING:
                return ActionResult(success=False, error="Cannot declare in current state")
            if not declaration_data:
                return ActionResult(success=False, error="No declaration data specified")
            if not self._validate_declare_action(player, declaration_data):
                return ActionResult(success=False, error="Invalid declaration")
            self.pending_declarations[player_id] = declaration_data
            logger.info(f"{player.name} declares: {declaration_data}")
            self.player_completed_subactions[player_id].add(self.current_substep)
            if self.current_substep == len(subactions) - 1:
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                self.current_substep += 1
            self._update_state_for_next_subaction(subactions)

        elif subaction_key == "deal" and action == PlayerAction.DEAL:
            if self.game.state != GameState.DEALING:
                return ActionResult(success=False, error="Cannot deal in current state")
            logger.info(f"{player.name} accepts the deal: config: {current_subaction}")
            self.game._handle_deal(current_subaction['deal'], player_id=player_id)
            self.player_completed_subactions[player_id].add(self.current_substep)
            if self.current_substep == len(subactions) - 1:
                self.grouped_step_completed.add(player_id)
                self.current_substep = 0
                self.game.current_player = self.game.next_player(round_start=False)
            else:
                self.current_substep += 1
            self._update_state_for_next_subaction(subactions)

        else:
            return ActionResult(success=False, error=f"Invalid action {action} for substep {subaction_key}")
  
        # Check if the grouped step is complete
        if self.grouped_step_completed == active_players and self.game.betting.round_complete():
            logger.info("All players completed grouped step and betting round is complete")
            return ActionResult(success=True, advance_step=True)

        return ActionResult(success=True)  

    def _advance_player_if_needed(self, manage_player: bool, round_complete: bool) -> ActionResult:
        """Advance player and check round completion if manage_player is True."""
        if not manage_player:
            return ActionResult(success=True)
        self.game.current_player = self.game.next_player(round_start=False)
        if round_complete:
            return ActionResult(success=True, advance_step=True)
        return ActionResult(success=True)
    
    def _calculate_bet_amounts(self, player_id: str, action: PlayerAction, amount: int, current_bet: int, current_ante: int) -> Tuple[int, int]:
        """Calculate total and additional amounts for a bet, handling all-in and antes."""
        player = self.game.table.players[player_id]
        if action == PlayerAction.CALL:
            total_amount = self.game.betting.current_bet
            additional_amount = self.game.betting.get_required_bet(player_id)
            if additional_amount > player.stack:
                additional_amount = player.stack
                total_amount = current_bet + additional_amount
        else:  # BET or RAISE
            if amount >= player.stack + current_bet:
                logger.info(f"{player.name} is going all-in with ${player.stack}")
                additional_amount = player.stack
                total_amount = player.stack + current_bet
            else:
        #        additional_amount = amount - current_bet + current_ante
                additional_amount = amount - current_bet  # Remove the + current_ante
                total_amount = amount
        return total_amount, additional_amount
    
    def _place_bet(self, player_id: str, total_amount: int, additional_amount: int, bet_type: BetType, is_forced: bool = False) -> None:
        """Place a bet and update player stack."""
        player = self.game.table.players[player_id]
        self.game.betting.place_bet(player_id, total_amount, player.stack, bet_type=bet_type, is_forced=is_forced)
        player.stack -= additional_amount    

    def _handle_betting_action(self, player_id: str, action: PlayerAction, amount: int, manage_player: bool = True) -> ActionResult:
        """Handle betting-related actions, advancing player only if manage_player is True."""
        player = self.game.table.players[player_id]
        valid_actions = self.get_valid_actions(player_id)

        # Determine bet_type from step configuration
        step = self.game.rules.gameplay[self.game.current_step]
        bet_config = step.action_config[self.current_substep].get("bet", {}) if step.action_type == GameActionType.GROUPED else step.action_config
        is_bring_in_step = bet_config.get("type") == "bring-in"
        bet_type = BetType.SMALL if bet_config.get("type") in ("small") or is_bring_in_step else BetType.BIG
        if action == PlayerAction.BRING_IN:
            bet_type = BetType.BRING_IN

        if action == PlayerAction.FOLD:
            player.is_active = False
            bet = self.game.betting.current_bets.get(player_id, PlayerBet())
            bet.has_acted = True
            self.game.betting.current_bets[player_id] = bet  # Make sure the updated bet is stored

            active_players = [p for p in self.game.table.get_position_order() if p.is_active]
            if len(active_players) == 1:
                self.game._handle_fold_win()
                return ActionResult(success=True, advance_step=True)
            logger.info(f"{player.name} folds")

            # Check if round is complete after this fold
            return self._advance_player_if_needed(manage_player, self.game.betting.round_complete())

        elif action == PlayerAction.CHECK:
            required_bet = self.game.betting.get_required_bet(player_id)
            if required_bet > 0:
                logger.debug(f"{player.name} cannot check; must call ${required_bet}")
                return ActionResult(success=False, error="Cannot check - must call or fold")
            current_bet = self.game.betting.current_bets.get(player_id, PlayerBet())
            current_bet.has_acted = True
            self.game.betting.current_bets[player_id] = current_bet

            # NEW: Track the last actor for check as well
            self.game.betting.last_actor_id = player_id
            logger.debug(f"handle_betting_action(CHECK): Updated last_actor_id to {player_id} (check)")

            logger.info(f"{player.name} checks")
            return self._advance_player_if_needed(manage_player, self.game.betting.round_complete())

        elif action == PlayerAction.CALL:
            current_bet = self.game.betting.current_bets.get(player_id, PlayerBet()).amount
            current_ante = self.game.betting.pot.total_antes.get(f"round_{self.game.betting.pot.current_round}_{player_id}", 0)
            total_amount, additional_amount = self._calculate_bet_amounts(player_id, action, amount, current_bet, current_ante)
            if additional_amount > player.stack:
                logger.debug(f"{player.name} needs ${additional_amount} to call but has ${player.stack}")
                return ActionResult(success=False, error="Not enough chips")
            logger.info(f"{player.name} calls ${additional_amount}")
            self._place_bet(player_id, total_amount, additional_amount, bet_type)
            return self._advance_player_if_needed(manage_player, self.game.betting.round_complete())          

        elif action == PlayerAction.BRING_IN:
            valid_bring_in = next((a for a in valid_actions if a[0] == PlayerAction.BRING_IN), None)
            if not valid_bring_in or amount != valid_bring_in[1]:
                logger.debug(f"Invalid bring-in for {player.name}: ${amount}, expected ${valid_bring_in[1] if valid_bring_in else 'N/A'}")
                return ActionResult(success=False, error=f"Invalid bring-in amount: ${amount}")
            logger.info(f"{player.name} brings in for ${amount}")
            self._place_bet(player_id, amount, amount, BetType.BRING_IN, is_forced=True)
            self.game.bring_in_player_id = player_id  # Record bring-in player       
            result = self._advance_player_if_needed(manage_player, False)
            if is_bring_in_step:
                result.advance_step = True
            return result

        # this will also handle a complete action - which is a BET in a bring-in game phase
        elif action == PlayerAction.BET or action == PlayerAction.RAISE:
            valid_bet = next((a for a in valid_actions if a[0] == action), None)
            if not valid_bet:
                logger.debug(f"No valid {action.value} action available for {player.name}")
                return ActionResult(success=False, error=f"Invalid {action.value} - no valid action available")

            if amount not in range(valid_bet[1], valid_bet[2] + 1):
                logger.debug(f"Invalid {action.value} for {player.name}: ${amount}, expected range ${valid_bet[1]}-${valid_bet[2]}")
                return ActionResult(success=False, error=f"Invalid {action.value} amount: ${amount}")  

            current_bet = self.game.betting.current_bets.get(player_id, PlayerBet()).amount
            current_ante = self.game.betting.pot.total_antes.get(f"round_{self.game.betting.pot.current_round}_{player_id}", 0)
            total_amount, additional_amount = self._calculate_bet_amounts(player_id, action, amount, current_bet, current_ante)
            if additional_amount > player.stack:
                logger.debug(f"{player.name} needs ${additional_amount} but has ${player.stack}")
                return ActionResult(success=False, error="Not enough chips")
            if is_bring_in_step:
                logger.info(f"{player.name} brings in for ${amount}")
                self._place_bet(player_id, total_amount, additional_amount, bet_type, is_forced=True)
                self.game.bring_in_player_id = player_id  # Record bring-in player       
                result = self._advance_player_if_needed(manage_player, False)
                result.advance_step = True
            else:
                logger.info(f"{player.name} {action.value.lower()}s ${total_amount}")
                self._place_bet(player_id, total_amount, additional_amount, bet_type)
                result = self._advance_player_if_needed(manage_player, self.game.betting.round_complete())
            return result     

        logger.warning(f"Unsupported betting action by {player.name}: {action}")
        return ActionResult(success=False, error=f"Unsupported betting action: {action}")

    def _update_state_for_next_subaction(self, subactions: List[Dict]) -> None:
        """Update game state for the next sub-action in a grouped step."""
        next_subaction = subactions[self.current_substep]
        next_key = list(next_subaction.keys())[0]
        logger.debug(f"Updating state for next subaction: {next_subaction} {next_key}")

        if "bet" in next_key:
            self.game.state = GameState.BETTING
            bet_config = next_subaction["bet"]
            if bet_config.get("type") not in ["antes", "blinds", "bring-in"] and not self.game.betting.round_complete():
                logger.debug(f"Starting betting round: {next_subaction} with new_round({self.game._is_first_betting_round()})")
                self.game.betting.new_round(self.game._is_first_betting_round())
        elif "discard" in next_key:
            self.game.state = GameState.DRAWING
            self.setup_discard_round(next_subaction["discard"])  # Changed to self
            # DON'T change current_player here - keep the same player for grouped actions
        elif "draw" in next_key:
            self.game.state = GameState.DRAWING
            self.setup_draw_round(next_subaction["draw"])  # Changed to self
            # DON'T change current_player here - keep the same player for grouped actions
        elif "separate" in next_key:
            self.game.state = GameState.DRAWING
            self.setup_separate_round(next_subaction["separate"])  # Changed to self
            # DON'T change current_player here - keep the same player for grouped actions
        elif "expose" in next_key:
            self.game.state = GameState.DRAWING
            self.setup_expose_round(next_subaction["expose"])  # Changed to self
            # DON'T change current_player here - keep the same player for grouped actions
        elif "pass" in next_key:
            self.game.state = GameState.DRAWING
            self.setup_pass_round(next_subaction["pass"])  # Changed to self
            # DON'T change current_player here - keep the same player for grouped actions
        elif "declare" in next_key:
            self.game.state = GameState.DECLARING
            self.setup_declare_round(next_subaction["declare"])     
            # DON'T change current_player here - keep the same player for grouped actions
        elif "deal" in next_key:
            self.game.state = GameState.DEALING
            logging.info(f"Next step is a deal - not a player action - no setup needed for {self.game.current_player.name}")

    def _handle_discard_action(self, player: Player, cards: List[Card]) -> bool:
        """Handle discard or draw action."""
        is_discard = hasattr(self.game, "current_discard_config")
        is_draw = hasattr(self.game, "current_draw_config")
        if not (is_discard or is_draw):
            return False
        
        config = self.game.current_discard_config if is_discard else self.game.current_draw_config
        card_config = config["cards"][0]
        max_discard = card_config.get("number", 0)
        min_discard = card_config.get("min_number", 0 if is_draw else max_discard)
        subset = card_config.get("hole_subset", "default")  # Get the subset for drawing

        logger.debug(f"Handling discard action for player {player.name} with cards: {cards}, card_config: {card_config}")

        if card_config.get("rule", "none") != "matching ranks":
            if len(cards) < min_discard or len(cards) > max_discard or any(card not in player.hand.cards for card in cards):
                return False

        face_up = card_config.get("state", "face down") == "face up"
        entire_subset = card_config.get("entire_subset", False)

        if is_discard and entire_subset:
            for subset_name, subset_cards in player.hand.subsets.items():
                if len(subset_cards) == len(cards) and all(c in subset_cards for c in cards):
                    player.hand.subsets[subset_name].clear()
                    break
            else:
                return False

        # Handle special discard rules like "matching ranks"
        if is_discard and card_config.get("rule") == "matching ranks":
            discard_subset = card_config.get("discardSubset", "default")
            discard_cards = self.game.table.community_cards.get(discard_subset, []) if card_config.get("discardLocation") == "community" else []
            discard_ranks = {card.rank for card in discard_cards}

            logger.debug(f"Player {player.name} has cards: {player.hand.get_cards()}")
            logger.debug(f"Discarding matching ranks: {discard_ranks}")

            cards_to_discard = [card for card in player.hand.get_cards() if card.rank in discard_ranks]

            logger.debug(f"cards to discard: {cards_to_discard}")

            if not cards_to_discard:
                return True
            for card in cards_to_discard:
                player.hand.remove_card(card)
                if card_config.get("discardLocation") == "community":
                    self.game.table.community_cards[discard_subset].append(card)
                else:
                    self.game.table.discard_pile[discard_subset].append(card)
                card.visibility = Visibility.FACE_UP if face_up else Visibility.FACE_DOWN
        else:
            # Standard discard
            for card in cards:
                player.hand.remove_card(card)
                if face_up:
                    card.visibility = Visibility.FACE_UP
                self.game.table.discard_pile.add_card(card)

        # Draw logic - handle the case where draw is relative to discard
        if is_draw:
            draw_amount = len(cards)  # Default is to draw same as discard

            # Check if draw_amount is relative to discard and adjust accordingly
            draw_amount_config = card_config.get("draw_amount", None)
            if draw_amount_config and draw_amount_config.get("relative_to") == "discard":
                relative_amount = draw_amount_config.get("amount", 0)
                draw_amount = draw_amount + relative_amount
                logger.info(f"Draw amount is relative to discard: {len(cards)} discarded + {relative_amount} = {draw_amount} to draw")

            # Ensure we don't try to draw more cards than available in the deck
            if len(self.game.table.deck.cards) < draw_amount:
                draw_amount = len(self.game.table.deck.cards)
                logger.warning(f"Not enough cards in deck, drawing only {draw_amount} cards")

            # Draw the cards
            if draw_amount > 0:                
                new_cards = self.game.table.deck.deal_cards(draw_amount)
                player.hand.add_cards(new_cards)

                # Assign new cards to the specified subset if needed
                if subset and subset != "default":
                    for card in new_cards:
                        player.hand.add_to_subset(card, subset)                

                logger.info(f"Player {player.name} drew {draw_amount} cards after discarding {len(cards)}")

        return True

    def _check_discard_round_complete(self) -> bool:
        """Check if the discard/draw round is complete by seeing if we've cycled back to the first player."""
        if self.first_player_in_round is None:
            logger.warning("First player in round not set")
            return False
        return self.game.current_player.id == self.first_player_in_round

    def _handle_separate_action(self, player: Player, cards: List[Card]) -> bool:
        """Handle separating cards into subsets."""
        config = self.game.current_separate_config["cards"]
        visibility_reqs = self.game.current_separate_config.get("visibility_requirements", [])
        all_cards = player.hand.get_cards()
        expected_total = sum(cfg["number"] for cfg in config)

        if len(cards) != expected_total or not all(c in all_cards for c in cards):
            logger.warning(f"Player {player.name} provided invalid cards for separation")
            return False
    
        player.hand.clear_subsets()
        card_index = 0
        for cfg in config:
            subset = cfg["hole_subset"]
            num = cfg["number"]
            subset_cards = cards[card_index:card_index + num]

            # Validate visibility requirements
            req = next((r for r in visibility_reqs if r["hole_subset"] == subset), None)  
            if req:
                min_face_down = req.get("min_face_down", 0)
                min_face_up = req.get("min_face_up", 0)
                face_down_count = sum(1 for card in subset_cards if card.visibility == Visibility.FACE_DOWN)
                face_up_count = sum(1 for card in subset_cards if card.visibility == Visibility.FACE_UP)
                
                if face_down_count < min_face_down or face_up_count < min_face_up:
                    logger.warning(f"Player {player.name}'s subset '{subset}' does not meet visibility requirements: "
                                f"needs at least {min_face_down} face-down and {min_face_up} face-up cards")
                    return False             
                         
            for card in subset_cards:
                player.hand.add_to_subset(card, subset)
            card_index += num

        # Validate hand comparison for each player
        comparison_config = self.game.current_separate_config.get("hand_comparison", None)
        if comparison_config:
            from generic_poker.evaluation.evaluator import EvaluationType, evaluator

            subsets = comparison_config["subsets"]
            comparison_rule = comparison_config["comparison_rule"]
            
            hand1 = player.hand.get_subset(subsets[0]["hole_subset"])
            hand2 = player.hand.get_subset(subsets[1]["hole_subset"])
            eval_type1 =  EvaluationType(subsets[0]["evaluationType"])
            eval_type2 = EvaluationType(subsets[1]["evaluationType"])
            
            from generic_poker.evaluation.evaluator import EvaluationType, evaluator

            result = evaluator.compare_hands_with_offset(
                hand1, hand2, eval_type1, eval_type2
            )
            
            if comparison_rule == "greater_than" and result <= 0:
                logger.warning(f"Player {player.name}'s {subsets[0]['hole_subset']} ({hand1}) is not better than their {subsets[1]['hole_subset']} ({hand2})")
                player.hand.clear_subsets()
                return False
                                
        return True

    def _handle_expose_action(self, player: Player, cards: List[Card]) -> bool:
        """Handle a player's exposure of cards."""
        config = self.game.current_expose_config["cards"][0]  # Single config for simplicity
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
    
    def _check_separate_round_complete(self) -> bool:
        """Check if the separate round is complete."""
        config = self.game.current_separate_config["cards"]
        active_players = [p for p in self.game.table.players.values() if p.is_active]
        return all(all(len(p.hand.get_subset(cfg["hole_subset"])) == cfg["number"] for cfg in config) for p in active_players)

    def _validate_expose_action(self, player: Player, cards: List[Card]) -> bool:
        """Validate exposure action."""
        config = self.game.current_expose_config["cards"][0]
        num_to_expose = config["number"]
        min_to_expose = config.get("min_number", num_to_expose)  # Default to num_to_expose if not specified
        required_state = config.get("state", "face down")
        
        # Check if the number of cards is within the allowed range
        if len(cards) < min_to_expose or len(cards) > num_to_expose:
            logger.warning(f"Player {player.name} attempted to expose {len(cards)} cards, but must expose between {min_to_expose} and {num_to_expose}")
            return False
            
        # Validate that all cards are in the player's hand and have the required state
        for card in cards:
            if card not in player.hand.get_cards():
                logger.warning(f"Player {player.name} tried to expose a card not in their hand: {card}")
                return False
            if required_state == "face down" and card.visibility != Visibility.FACE_DOWN:
                logger.warning(f"Player {player.name} tried to expose a card that is not face down: {card}")
                return False
                
        return True

    def _check_expose_round_complete(self) -> bool:
        """Check if the expose round is complete."""
        active_players = [p for p in self.game.table.players.values() if p.is_active]
        return all(p.id in self.pending_exposures for p in active_players)

    def _apply_all_exposures(self) -> None:
        """Apply all pending exposures."""
        for player_id, cards in self.pending_exposures.items():
            player = self.game.table.players[player_id]
            for card in cards:
                if card in player.hand.get_cards() and card.visibility == Visibility.FACE_DOWN:
                    card.visibility = Visibility.FACE_UP
        self.pending_exposures.clear()

    def _validate_pass_action(self, player: Player, cards: List[Card]) -> bool:
        """Validate pass action."""
        config = self.game.current_pass_config["cards"][0]
        num_to_pass = config["number"]
        required_state = config.get("state", "face down")
        if len(cards) != num_to_pass or any(card not in player.hand.get_cards() or (required_state == "face down" and card.visibility != Visibility.FACE_DOWN) for card in cards):
            return False
        return True

    def _check_pass_round_complete(self) -> bool:
        """Check if the pass round is complete."""
        active_players = [p for p in self.game.table.players.values() if p.is_active]
        return all(p.id in self.pending_passes for p in active_players)

    def _apply_all_passes(self) -> None:
        """Apply all pending passes."""
        new_hands = {pid: [] for pid in self.game.table.players}
        for player_id, (card, recipient_id) in self.pending_passes.items():
            player = self.game.table.players[player_id]
            player.hand.remove_card(card)
            new_hands[recipient_id].append(card)
        for player_id, cards in new_hands.items():
            if cards:
                self.game.table.players[player_id].hand.add_cards(cards)
        self.pending_passes.clear()

    def _validate_declare_action(self, player: Player, declaration_data: List[Dict]) -> bool:
        """Validate declaration action."""
        config = self.game.current_declare_config
        allowed_options = config.get("options", [])
        per_pot = config.get("per_pot", False)

        if not declaration_data:
            logger.warning(f"Player {player.name} provided empty declaration data")
            return False

        if per_pot:
            eligible_pots = self._get_eligible_pots(player)
            if len(declaration_data) != len(eligible_pots):
                logger.warning(f"Player {player.name} provided {len(declaration_data)} declarations, "
                               f"expected {len(eligible_pots)} for eligible pots")
                return False
            for decl in declaration_data:
                pot_index = decl.get("pot_index")
                declaration = decl.get("declaration")
                if pot_index not in eligible_pots:
                    logger.warning(f"Player {player.name} declared for invalid pot index {pot_index}")
                    return False
                if declaration not in allowed_options:
                    logger.warning(f"Player {player.name} provided invalid declaration '{declaration}'")
                    return False
        else:
            if len(declaration_data) != 1:
                logger.warning(f"Player {player.name} provided {len(declaration_data)} declarations, "
                               f"expected 1 when per_pot is false")
                return False
            declaration = declaration_data[0].get("declaration")
            if declaration not in allowed_options:
                logger.warning(f"Player {player.name} provided invalid declaration '{declaration}'")
                return False

        return True       

    def _check_declare_round_complete(self) -> bool:
        """Check if the declare round is complete."""
        active_players = [p for p in self.game.table.players.values() if p.is_active]
        return all(p.id in self.pending_declarations for p in active_players)

    def _apply_all_declarations(self) -> None:
        """Apply all pending declarations to game state."""
        declarations = {}
        for player_id, decl_list in self.pending_declarations.items():
            declarations[player_id] = {decl["pot_index"]: decl["declaration"] for decl in decl_list}
        self.game.declarations = declarations
        logger.info(f"Applied declarations: {declarations}")
        self.pending_declarations.clear()

    def _get_eligible_pots(self, player: Player) -> List[int]:
        """Get the pot indices (main and side) the player is eligible for."""
        eligible_pots = [-1]  # Main pot
        for i in range(self.game.betting.get_side_pot_count()):
            if player.id in self.game.betting.get_side_pot_eligible_players(i):
                eligible_pots.append(i)
        return eligible_pots     

    def format_actions_for_display(self, player_id: str) -> List[str]:
        """Format valid actions for display."""
        valid_actions = self.get_valid_actions(player_id)
        if not valid_actions:
            return []
        player = self.game.table.players[player_id]
        current_bet = self.game.betting.current_bets.get(player_id, PlayerBet()).amount
        formatted = []
        for action, min_amount, max_amount in valid_actions:
            if action == PlayerAction.FOLD:
                formatted.append("Fold")
            elif action == PlayerAction.CHECK:
                formatted.append("Check")
            elif action == PlayerAction.CALL:
                additional = min_amount - current_bet
                formatted.append(f"Call ${min_amount} (+${additional})")
            elif action in [PlayerAction.BET, PlayerAction.RAISE]:
                if min_amount == max_amount:
                    additional = min_amount - current_bet
                    action_name = "Bet" if action == PlayerAction.BET else "Raise to"
                    formatted.append(f"{action_name} ${min_amount} (+${additional})")
                else:
                    additional_min = min_amount - current_bet
                    action_name = "Bet" if action == PlayerAction.BET else "Raise to"
                    formatted.append(f"{action_name} ${min_amount}-${max_amount} (min +${additional_min})")
                    if self.game.betting_structure != BettingStructure.LIMIT:
                        pot_size = self.game.betting.get_total_pot()
                        half_pot = min(current_bet + (pot_size // 2), max_amount)
                        if half_pot > min_amount:
                            additional = half_pot - current_bet
                            formatted.append(f"{action_name} ${half_pot} - Half Pot (+${additional})")
                        full_pot = min(current_bet + pot_size, max_amount)
                        if full_pot > half_pot:
                            additional = full_pot - current_bet
                            formatted.append(f"{action_name} ${full_pot} - Pot (+${additional})")
                        if max_amount > full_pot:
                            additional = max_amount - current_bet
                            formatted.append(f"All-in ${max_amount} (+${additional})")
            elif action == PlayerAction.BRING_IN:
                formatted.append(f"Bring-in ${min_amount}")
        return formatted

    def setup_discard_round(self, config: Dict[str, Any]) -> None:
        """
        Set up a discard round.
        
        Args:
            config: Discard configuration
        """
        # Check conditional state - skip if condition not met
        conditional_state = config.get("conditional_state")
        if conditional_state and not self.game._check_condition(conditional_state):
            logger.info("Skipping discard round - condition not met")
            # Let the game know to skip this step completely
            if self.game.auto_progress:
                self.game._next_step()
            return
            
        self.game.current_discard_config = config
        self.game.state = GameState.DRAWING

        # Only set first_player_in_round and current_player if NOT in a grouped action
        if not hasattr(self, 'current_substep') or self.current_substep is None:
            self.first_player_in_round = None
            self.game.current_player = self.game.next_player(round_start=True)
            if self.game.current_player:
                self.first_player_in_round = self.game.current_player.id        
        
    #    self.first_player_in_round = None  # Track first player to determine when round is complete
    #    
    #    # Set the current player to the first player (usually UTG or first active)
    #    self.game.current_player = self.game.next_player(round_start=True)
    #    if self.game.current_player:
    #        self.first_player_in_round = self.game.current_player.id

    def setup_draw_round(self, config: Dict) -> None:
        """Set up a draw round."""
        self.game.current_draw_config = config

    def setup_separate_round(self, config: Dict) -> None:
        """Set up a separate round."""
        self.game.current_separate_config = config

    def setup_expose_round(self, config: Dict) -> None:
        """Set up an expose round."""
        self.game.current_expose_config = config

    def setup_pass_round(self, config: Dict) -> None:
        """Set up a pass round."""
        self.game.current_pass_config = config

    def setup_declare_round(self, config: Dict) -> None:
        """Set up a pass round."""
        self.game.current_declare_config = config        

    def setup_grouped_step(self, step_config: List[Dict]) -> None:
        """Set up a grouped step."""
        active_players = [p.id for p in self.game.table.get_active_players()]
        self.player_completed_subactions = {pid: set() for pid in active_players}
        self.current_substep = 0

        self.grouped_step_completed = set()
