"""Core game implementation controlling game flow."""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple

from generic_poker.config.loader import GameRules, GameActionType
from generic_poker.game.table import Table, Player, Position
from generic_poker.game.betting import (
    BettingManager, LimitBettingManager, create_betting_manager,
    BettingStructure, BetType, PlayerBet
)
from generic_poker.core.card import Card
from generic_poker.evaluation.evaluator import EvaluationType

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


@dataclass
class ActionResult:
    """Result of a player action."""
    success: bool
    error: Optional[str] = None
    state_changed: bool = False


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
        small_bet: int,
        big_bet: Optional[int] = None,
        min_buyin: int = 0,
        max_buyin: int = 0,
        auto_progress: bool = True  # Add this parameter
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
        self.betting = create_betting_manager(structure, small_bet, big_bet)
        self.auto_progress = auto_progress  # Store the setting     
        
        self.state = GameState.WAITING
        self.current_step = -1  # Not started
        self.current_player: Optional[str] = None  # ID of player to act
    
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
        self.current_step = 0
        self.state = GameState.DEALING
        logger.info("Hand started - moving to first step")
        
        # Execute first step
        self.process_current_step()

    def get_valid_actions(self, player_id: str) -> List[Tuple[PlayerAction, Optional[int], Optional[int]]]:
            """
            Get list of valid actions for a player.
            
            Args:
                player_id: ID of player to check
                
            Returns:
                List of tuples (action, min_amount, max_amount) where amounts are None
                if not applicable (like for fold/check)
                
            Example:
                [(PlayerAction.FOLD, None, None),
                (PlayerAction.CALL, 10, 10),
                (PlayerAction.RAISE, 20, 100)]
            """
            if player_id != self.current_player:
                return []  # Not player's turn
                
            if self.state != GameState.BETTING:
                return []  # Not betting phase
                
            player = self.table.players[player_id]
            current_bet = self.betting.current_bets.get(player_id, PlayerBet()).amount
            required_bet = self.betting.get_required_bet(player_id)

            logger.debug(f"Player: {player_id}, Required Bet: {required_bet}, Current Bet: {current_bet}")
            logger.debug(f"  Stack: {player.stack}")   
            
            valid_actions = []

            # Always allow folding (even if player could check)
            valid_actions.append((PlayerAction.FOLD, None, None))            
            
            # CALL if player has enough chips
            if required_bet > 0:
                if player.stack >= required_bet:
                    valid_actions.append((PlayerAction.CALL, required_bet, required_bet))
                elif player.stack > 0:
                    # ✅ Allow all-in call for less than required bet
                    valid_actions.append((PlayerAction.CALL, player.stack, player.stack))
            else:
                valid_actions.append((PlayerAction.CHECK, None, None))
                
             # Determine possible BET or RAISE
            if player.stack > required_bet:
                current_total = self.betting.current_bet
                current_bet = self.betting.current_bets.get(player_id, PlayerBet()).amount

                # ✅ Correct minimum raise: last raise size or small bet
                min_amount = self.betting.get_min_bet(player_id, BetType.BIG)
                max_amount = self.betting.get_max_bet(player_id, BetType.BIG, player.stack)

                logger.debug(f"Player: {player_id}, Required Bet: {required_bet}, Current Total: {current_total}")
                logger.debug(f"Min Amount: {min_amount}, Max Amount: {max_amount}")                
                
                if current_total == 0:
                    action = PlayerAction.BET
                else:
                    action = PlayerAction.RAISE

                # ✅ Normal raise if player has enough chips
                if player.stack + current_bet >= min_amount:
                    valid_actions.append((action, min_amount, max_amount))
                else:
                    # All-in raise if stack can't meet min raise
                    all_in_amount = player.stack + current_bet
                    valid_actions.append((action, all_in_amount, all_in_amount))        
                  
            logger.debug(f"Valid actions for {player_id}: {valid_actions}")
            return valid_actions        
        
    def player_action(
            self,
            player_id: str,
            action: PlayerAction,
            amount: int = 0
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
            
            if player_id != self.current_player:
                logger.warning(f"Invalid action - not {player.name}'s turn")
                return ActionResult(
                    success=False,
                    error="Not your turn"
                )
                
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
                        
                    self._next_player()
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
                    
                    # Check if betting round is complete
                    if self.betting.round_complete():
                        logger.debug("Betting round complete after check")
                        if self.auto_progress:
                            self._next_step()
                        return ActionResult(success=True, state_changed=True)
                    
                    # Move to next player if round not complete
                    self._next_player()
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
                    
                elif action in [PlayerAction.BET, PlayerAction.RAISE]:
                    # Validate bet/raise amount
                    valid_actions = self.get_valid_actions(player_id)

                    logger.debug(f"Valid actions: {valid_actions}")

                    valid_raise = next(
                        (a for a in valid_actions if a[0] == action),
                        None
                    )
                   
                    if not valid_raise:
                        return ActionResult(
                            success=False,
                            error=f"Invalid {action.value}"
                        )
                        
                    _, min_amount, max_amount = valid_raise

                    logger.debug(f"Attempting action: {action}, Amount: {amount}, Min: {min_amount}, Max: {max_amount}")

                    if (min_amount is not None and amount < min_amount) or (max_amount is not None and amount > max_amount):
                        return ActionResult(
                            success=False,
                            error=f"Invalid {action.value} amount: ${amount}"
                        )
                    
                    current_bet = self.betting.current_bets.get(player_id, PlayerBet())
                    
                    # Adjust for all-in
                    if amount >= player.stack:  # Changed from > to >=
                        logger.info(f"{player.name} is going all-in with ${player.stack}")
                        amount = player.stack + current_bet.amount  # Include what's already in
                        additional = player.stack  # Take entire remaining stack   
                    else:
                        # Normal raise
                        additional = amount - current_bet.amount                        

                    if additional > player.stack:
                        return ActionResult(
                            success=False,
                            error="Not enough chips to complete this action"
                        )
                        
                    # ✅ Place the bet and deduct from stack
                    logger.info(f"{player.name} {action.value}s to ${amount}")
                    self.betting.place_bet(player_id, amount, player.stack)
                    player.stack -= additional

                    logger.debug(f"{player.name}'s remaining stack: ${player.stack}")

                    # 🔄 Update last_raise_size only if not all-in
                    if action == PlayerAction.RAISE and amount != player.stack:
                        self.betting.last_raise_size = additional
                        logger.debug(f"Updated last raise size to ${self.betting.last_raise_size}")                 
                              
                # Move to next player
                self._next_player()
                
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
            
            if step.action_type == GameActionType.DEAL:
                logger.debug(f"Handling deal action: {step.action_config}")
                self._handle_deal(step.action_config)
                if self.auto_progress:  # Add check here
                    self._next_step()
                
            elif step.action_type == GameActionType.BET:
                if step.action_config["type"] == "blinds":
                    logger.info("Processing forced bets")
                    self._handle_forced_bets()
                    if self.auto_progress:  # Add check here
                        self._next_step()
                else:
                    logger.info(f"Starting betting round: {step.name}")
                    self.state = GameState.BETTING
                    # Preserve current bet if this is first betting round after blinds
                    preserve_bet = len(self.betting.current_bets) > 0
                    self.betting.new_round(preserve_bet)
                    self._next_player()
                
            elif step.action_type == GameActionType.SHOWDOWN:
                logger.info("Moving to showdown")
                self.state = GameState.SHOWDOWN
                self._handle_showdown()
            
    def _handle_deal(self, config: Dict[str, Any]) -> None:
        """Handle a dealing action."""
        location = config["location"]
        for card_config in config["cards"]:
            num_cards = card_config["number"]
            
            if location == "player":
                logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to each player")
                self.table.deal_hole_cards(num_cards)
            else:  # community
                logger.info(f"Dealing {num_cards} {'card' if num_cards == 1 else 'cards'} to board")
                self.table.deal_community_cards(num_cards)
                
    def _handle_forced_bets(self) -> None:
        """Handle posting of blinds or antes."""
        players = self.table.get_position_order()
        if not players:
            return
            
        logger.debug("Posting forced bets. Players in order:")
        for p in players:
            logger.debug(f"  {p.name}: {p.id} ({p.position.value if p.position else 'NA'})")
            
        logger.debug(f"Small Bet: {self.betting.small_bet}")
        assert self.betting.small_bet is not None and self.betting.small_bet > 0, "small_bet must be set before posting blinds"

        sb_amount = self.betting.small_bet // 2
        bb_amount = self.betting.small_bet
        
        # Find SB and BB players - handle both regular and heads-up cases
        sb_player = next(
            (p for p in players if (pos := p.position) and pos.has_position(Position.SMALL_BLIND)),
            None
        )
        bb_player = next(
            (p for p in players if (pos := p.position) and pos.has_position(Position.BIG_BLIND)),
            None
        )

        # Ensure Small Blind player exists
        if (sb_player := next((p for p in players if (pos := p.position) and pos.has_position(Position.SMALL_BLIND)), None)) is None:
            logger.error("Small Blind player not found. Cannot post blinds.")
            return  # Or handle the error appropriately

        # Ensure Big Blind player exists
        if (bb_player := next((p for p in players if (pos := p.position) and pos.has_position(Position.BIG_BLIND)), None)) is None:
            logger.error("Big Blind player not found. Cannot post blinds.")
            return  # Or handle the error appropriately        
       
        # Post small blind
        sb_player.stack -= sb_amount
        self.betting.place_bet(sb_player.id, sb_amount, sb_player.stack, is_forced=True)
        logger.info(f"{sb_player.name} posts small blind of ${sb_amount} (Remaining stack: ${sb_player.stack})")
        
        # Post big blind
        bb_player.stack -= bb_amount
        self.betting.place_bet(bb_player.id, bb_amount, bb_player.stack, is_forced=True)
        logger.info(f"{bb_player.name} posts big blind of ${bb_amount} (Remaining stack: ${bb_player.stack})")
        
        # Update current bet to BB amount
        self.betting.current_bet = bb_amount

        # Initialize last_raise_size to the big blind
        self.betting.last_raise_size = bb_amount
            
        logger.debug("After posting blinds:")
        for player_id, bet in self.betting.current_bets.items():
            logger.debug(f"  {self.table.players[player_id].name}: ${bet.amount} (blind={bet.posted_blind})")

        # Set first player to act (BTN in 3-player game)
        self._next_player()  # Move to BTN
        self.state = GameState.BETTING  # Ready for action            
        
    def _next_step(self) -> None:
        """Move to next step in gameplay sequence."""
        self.current_step += 1
        self.process_current_step()
        
    def _next_player(self) -> None:
            """
            Set next player to act based on betting position.
            
            For first betting round:
            1. First action: BTN (after BB has posted)
            2. Then SB
            3. Then BB gets option
            """
            players = self.table.get_position_order()  # Gives us BTN->SB->BB order
            active_players = [p for p in players if p.is_active]
            
            logger.debug("Current active players and positions:")
            for p in active_players:
                logger.debug(f"  {p.name}: {(pos.value if (pos := p.position) else 'NA')}")
            
            # Check if this is the first betting round after blinds
            is_first_bet = (
                len(self.betting.current_bets) > 0 and  # Blinds have been posted
                not any(bet.has_acted for bet in self.betting.current_bets.values())  # No one has acted yet
            )
            
            logger.debug(f"Is first betting round: {is_first_bet}")
            
            if (
                is_first_bet and 
                (player_id := self.current_player) and 
                not self.betting.current_bets.get(player_id, PlayerBet()).has_acted
            ):
                # First action of the round goes to BTN
                for player in players:
                    if player.position == Position.BUTTON:
                        self.current_player = player.id
                        logger.debug(f"First action to button: {player.name}")
                        return
            else:
                # Find next active player after current
                if self.current_player:
                    try:
                        current_idx = next(
                            i for i, p in enumerate(players)
                            if p.id == self.current_player
                        )
                        
                        # Check players after current position
                        for i in range(current_idx + 1, len(players)):
                            if players[i].is_active:
                                self.current_player = players[i].id
                                logger.debug(f"Action to next player: {players[i].name}")
                                return
                                
                        # Wrap around to start
                        for i in range(current_idx):
                            if players[i].is_active:
                                self.current_player = players[i].id
                                logger.debug(f"Action wraps to: {players[i].name}")
                                return
                    except StopIteration:
                        # Current player not found (e.g., they just folded)
                        if active_players:
                            self.current_player = active_players[0].id
                            logger.debug(f"Current player not found, starting with: {self.table.players[self.current_player].name}")
                            return
                
            # If we get here and have active players, start with first
            if active_players:
                self.current_player = active_players[0].id
                logger.debug(f"Starting with first active player: {self.table.players[self.current_player].name}")

    def _handle_fold_win(self, active_players: List[Player]) -> None:
        """Handle pot award when all but one player folds."""
        logger.info("All but one player folded - hand complete")
        self.state = GameState.COMPLETE
        self.betting.award_pots(active_players)

    def _handle_showdown(self) -> None:
        """
        Handle showdown and determine winners.
        
        Evaluates all active players' hands and awards pots.
        Side pots are handled in order from smallest to largest.
        """
        from generic_poker.evaluation.evaluator import evaluator, EvaluationType
        
        active_players = [p for p in self.table.players.values() if p.is_active]
        if not active_players:
            return
            
        # Get evaluation settings from rules
        showdown_rules = self.rules.showdown.best_hand[0]  # Use first evaluation type for now
        eval_type = EvaluationType(showdown_rules.get('evaluationType', 'high'))
        
        # For each hand config in the showdown rules, find best hand
        player_best_hands = {}
        
        for player in active_players:
            cards = player.hand.get_cards()
            
            # For now, just use 'anyCards' if specified, otherwise all cards
            num_cards = showdown_rules.get('anyCards', len(cards))
            if len(cards) < num_cards:
                logger.warning(
                    f"Player {player.id} has fewer cards than required: "
                    f"{len(cards)} vs {num_cards}"
                )
                continue
                
            # For straight poker, just use all cards
            # TODO: Handle cases where best hand must be selected from available cards
            player_best_hands[player.id] = cards
            
        # Award any side pots first
        for i in range(self.betting.get_side_pot_count()):
            eligible_ids = self.betting.get_side_pot_eligible_players(i)
            eligible_players = [p for p in active_players if p.id in eligible_ids]
            if eligible_players:
                # Find best hand among eligible players
                pot_winners = self._find_winners(eligible_players, player_best_hands, eval_type)
                if pot_winners:
                    self.betting.award_pots(pot_winners, i)
                    
        # Award main pot
        winners = self._find_winners(active_players, player_best_hands, eval_type)
        if winners:
            self.betting.award_pots(winners)
            
        self.state = GameState.COMPLETE

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