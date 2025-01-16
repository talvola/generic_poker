"""Core game implementation controlling game flow."""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Any

from generic_poker.config.loader import GameRules, GameActionType
from generic_poker.game.table import Table, Player, Position
from generic_poker.game.betting import (
    BettingManager, create_betting_manager,
    BettingStructure, BetType, PlayerBet
)

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
        max_buyin: int = 0
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
                    
                    # Find next active player that isn't the folding player
                    players = self.table.get_position_order()
                    active_players = [p for p in players if p.is_active and p.id != player_id]
                    
                    if active_players:
                        # Move to the next player in position after the folding player
                        try:
                            current_idx = next(i for i, p in enumerate(players) if p.id == player_id)
                            # Look for next active player after current position
                            next_player = None
                            for i in range(current_idx + 1, len(players)):
                                if players[i].is_active:
                                    next_player = players[i]
                                    break
                            # If none found after, wrap to start
                            if not next_player:
                                for i in range(current_idx):
                                    if players[i].is_active:
                                        next_player = players[i]
                                        break
                            
                            if next_player:
                                self.current_player = next_player.id
                                logger.debug(f"After fold, action moves to {next_player.name}")
                        except StopIteration:
                            # If current player not found, move to first active
                            self.current_player = active_players[0].id
                            logger.debug(f"After fold, action moves to {active_players[0].name}")
                    
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
                    
                    if current_bet.amount < self.betting.current_bet:
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
                        self._next_step()
                        return ActionResult(success=True, state_changed=True)
                    
                    # Move to next player if round not complete
                    self._next_player()
                    return ActionResult(success=True)
                    
                elif action == PlayerAction.CALL:
                    call_amount = self.betting.get_required_bet(player_id)
                    total_bet = self.betting.current_bet  # Target amount
                    
                    logger.debug(f"Processing call: required={call_amount}, total={total_bet}")
                    
                    if call_amount > player.stack:
                        call_amount = player.stack  # All-in
                        logger.info(f"{player.name} calls all-in for ${call_amount}")
                    else:
                        logger.info(f"{player.name} calls ${call_amount}")
                
                    # Place the total bet amount
                    self.betting.place_bet(player_id, total_bet, player.stack)
                    player.stack -= call_amount  # Deduct only the additional amount needed
                    
                elif action in [PlayerAction.BET, PlayerAction.RAISE]:
                    if amount > player.stack:
                        logger.warning(f"{player.name} cannot bet ${amount} - only has ${player.stack}")
                        return ActionResult(
                            success=False,
                            error="Not enough chips"
                        )
                    logger.info(f"{player.name} {action.value}s ${amount}")
                    self.betting.place_bet(player_id, amount, player.stack)
                    player.stack -= amount
                    
            except ValueError as e:
                logger.error(f"Error processing {player.name}'s action: {e}")
                return ActionResult(
                    success=False,
                    error=str(e)
                )
            
            # Move to next player
            self._next_player()
            
            # Check if betting round complete
            if self.betting.round_complete():
                logger.info("Betting round complete")
                self._next_step()
                return ActionResult(success=True, state_changed=True)
                
            return ActionResult(success=True)
        
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
                self._next_step()
                
            elif step.action_type == GameActionType.BET:
                if step.action_config["type"] == "blinds":
                    logger.info("Processing forced bets")
                    self._handle_forced_bets()
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
                
            # Small blind is half the small bet
            sb_amount = self.betting.small_bet // 2
            bb_amount = self.betting.small_bet
            
            # Find SB and BB players
            sb_player = next(p for p in players if p.position.value == "SB")
            bb_player = next(p for p in players if p.position.value == "BB")
            
            # Post small blind
            sb_player.stack -= sb_amount
            self.betting.place_bet(sb_player.id, sb_amount, sb_player.stack, is_forced=True)
            logger.info(f"{sb_player.name} posts small blind of ${sb_amount}")
            
            # Post big blind
            bb_player.stack -= bb_amount
            self.betting.place_bet(bb_player.id, bb_amount, bb_player.stack, is_forced=True)
            logger.info(f"{bb_player.name} posts big blind of ${bb_amount}")
            
            # Update current bet to BB amount
            self.betting.current_bet = bb_amount
            
            logger.debug("After posting blinds:")
            for player_id, bet in self.betting.current_bets.items():
                logger.debug(f"  {self.table.players[player_id].name}: ${bet.amount} (blind={bet.posted_blind})")
        
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
                logger.debug(f"  {p.name}: {p.position.value}")
            
            # Check if this is the first betting round after blinds
            is_first_bet = (
                len(self.betting.current_bets) > 0 and  # Blinds have been posted
                not any(bet.has_acted for bet in self.betting.current_bets.values())  # No one has acted yet
            )
            
            logger.debug(f"Is first betting round: {is_first_bet}")
            
            if is_first_bet and not self.betting.current_bets.get(self.current_player, PlayerBet()).has_acted:
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
            
        # Get all pots to award (main pot and side pots)
        pots_to_award = [(
            self.betting.pot.main_pot,
            {p.id: p for p in active_players}
        )]
        
        # Add side pots if any exist
        for side_pot in self.betting.pot.side_pots:
            eligible_players = {
                pid: self.table.players[pid]
                for pid in side_pot.keys()
                if self.table.players[pid].is_active
            }
            if eligible_players:
                pots_to_award.append((
                    max(side_pot.values()),
                    eligible_players
                ))
                
        # Award each pot
        for pot_amount, eligible_players in pots_to_award:
            if not eligible_players:
                continue
                
            # Find best hand(s) among eligible players
            best_hand_result = None
            winners = []
            
            for player_id, player in eligible_players.items():
                if player_id not in player_best_hands:
                    continue
                    
                current_hand = player_best_hands[player_id]
                
                if not best_hand_result:
                    best_hand_result = current_hand
                    winners = [player_id]
                    continue
                    
                comparison = evaluator.compare_hands(
                    current_hand,
                    player_best_hands[winners[0]],
                    eval_type
                )
                
                if comparison > 0:  # Current hand better
                    best_hand_result = current_hand
                    winners = [player_id]
                elif comparison == 0:  # Tie
                    winners.append(player_id)
                    
            # Award pot to winner(s)
            if winners:
                amount_per_winner = pot_amount // len(winners)
                remainder = pot_amount % len(winners)
                
                for i, winner_id in enumerate(winners):
                    award = amount_per_winner
                    if i < remainder:  # Distribute remainder one chip at a time
                        award += 1
                    self.table.players[winner_id].stack += award
                    logger.info(f"{self.table.players[winner_id].name} wins ${award}")
        
        self.state = GameState.COMPLETE