"""Core game implementation controlling game flow."""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple, Set

from generic_poker.config.loader import GameRules, GameActionType
from generic_poker.game.table import Table, Player, Position
from generic_poker.game.betting import (
    BettingManager, LimitBettingManager, create_betting_manager,
    BettingStructure, BetType, PlayerBet
)
from generic_poker.core.card import Card
from generic_poker.evaluation.evaluator import EvaluationType, evaluator

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
        if structure == BettingStructure.LIMIT:
            if small_bet is None or big_bet is None:
                raise ValueError("Limit games require small_bet and big_bet")
            self.small_bet = small_bet
            self.big_bet = big_bet
            # small blind in Limit games is half the small bet
            self.small_blind = small_bet // 2
            self.big_blind = small_bet
            self.betting = create_betting_manager(structure, small_bet, big_bet)
        else:  # NO_LIMIT or POT_LIMIT
            if small_blind is None or big_blind is None:
                raise ValueError("No-Limit/Pot-Limit games require small_blind and big_blind")
            self.small_blind = small_blind
            self.big_blind = big_blind
            # the minimum bet is always the big blind in No-Limit/Pot-Limit games
            self.small_bet = big_blind
            self.big_bet = big_blind
            self.betting = create_betting_manager(structure, small_blind, big_blind)     
        self.auto_progress = auto_progress  # Store the setting     
        
        self.state = GameState.WAITING
        self.current_step = -1  # Not started
        self.current_player: Optional[str] = None  # ID of player to act
    
        self.last_hand_result = None  # Store the last hand result here

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
                    valid_actions.append((PlayerAction.CALL, self.betting.current_bet, self.betting.current_bet))
                elif player.stack > 0:
                    # ✅ Allow all-in call for less than required bet
                    # For all-in, the total would be current_bet + stack
                    total_amount = current_bet + player.stack
                    valid_actions.append((PlayerAction.CALL, total_amount, total_amount))
            else:
                valid_actions.append((PlayerAction.CHECK, None, None))
                
             # Determine possible BET or RAISE
            if player.stack > required_bet:
                current_total = self.betting.current_bet
                current_bet = self.betting.current_bets.get(player_id, PlayerBet()).amount

                if current_total == 0:
                    action = PlayerAction.BET
                    min_amount = self.betting.get_min_bet(player_id, BetType.BIG)
                else:
                    action = PlayerAction.RAISE
                    min_amount = self.betting.get_min_raise(player_id)  # Use get_min_raise for raises

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
                self.state = GameState.DEALING
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
        
        For first betting round (pre-flop):
            1. First action: UTG (or BTN in 3-player game) after BB has posted
            2. Then proceeds clockwise
        For later betting rounds (post-flop and beyond):
            1. First action: SB
            2. Then BB
            3. Then BTN/UTG and others clockwise
        """
        players = self.table.get_position_order()  # Gives us BTN->SB->BB order
        active_players = [p for p in players if p.is_active]
            
        logger.debug("Current active players and positions:")
        for p in active_players:
            logger.debug(f"  {p.name}: {(pos.value if (pos := p.position) else 'NA')}")

        # Determine if we're in the pre-flop betting round
        is_preflop = self.current_step == 0 or (
            self.current_step < len(self.rules.gameplay) and
            self.rules.gameplay[self.current_step - 1].name.lower() in 
            ["post blinds", "ante", "deal hole cards", "pre-flop"]
        )            
            
        logger.debug(f"Is pre-flop betting: {is_preflop}")

        # For the very first action of a betting round
        if not any(bet.has_acted for bet in self.betting.current_bets.values()):
            # First round (pre-flop)
            if is_preflop:
                # Action starts with BTN in a 3-player game
                for player in players:
                    if player.position and player.position.has_position(Position.BUTTON):
                        self.current_player = player.id
                        logger.debug(f"First pre-flop action to button: {player.name}")
                        return
            # Later rounds (post-flop)
            else:
                # Start with SB
                for player in players:
                    if player.position.has_position(Position.SMALL_BLIND):
                        self.current_player = player.id
                        logger.debug(f"First post-flop action to SB: {player.name}")
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
        
        # Get total pot amount before awarding
        total_pot = self.betting.get_total_pot()
        
        # Award the pot
        self.state = GameState.COMPLETE
        self.betting.award_pots(active_players)
        
        # Create hand results only for active players (winners) but without showing cards
        hand_results = {}
        for player in active_players:
            hand_results[player.id] = HandResult(
                player_id=player.id,
                cards=[],  # Don't include actual cards
                hand_name="Not shown",
                hand_description="Hand not shown - won uncontested",
                evaluation_type="unknown"
            )
        
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
            winning_hands=list(hand_results.values()),
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
        
        for player in players:
            # Find the player's best hand for this configuration
            best_hand = self._find_best_hand_for_player(
                player,
                self.table.community_cards,
                hand_config,
                eval_type
            )
          
            if not best_hand:
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
        community_cards: List[Card],
        showdown_rules: dict,
        eval_type: EvaluationType
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
        
        hole_cards = player.hand.get_cards()
        best_hand = None
        
        # Handle different types of hand compositions
        if "anyCards" in showdown_rules:
            total_cards = showdown_rules["anyCards"]
            all_cards = hole_cards + community_cards
            
            # If there are no community cards or exactly the right number of hole cards,
            # we can just use the hole cards (straight poker case)
            if not community_cards and len(hole_cards) == total_cards:
                return hole_cards
            
            # Otherwise, find the best hand from all available cards
            if len(all_cards) >= total_cards:
                # Try all possible combinations
                for combo in itertools.combinations(all_cards, total_cards):
                    hand = list(combo)
                    
                    if best_hand is None:
                        best_hand = hand
                    else:
                        if evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                            best_hand = hand
                
                return best_hand
            else:
                # Not enough cards total
                logger.warning(
                    f"Not enough cards for player {player.id}: "
                    f"Has {len(hole_cards)} hole cards and {len(community_cards)} community cards "
                    f"(need {total_cards} total)"
                )
                return []
            
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
                if len(hole_cards) < required_hole or len(community_cards) < required_community:
                    continue
                
                # Generate combinations for this option
                hole_combos = list(itertools.combinations(hole_cards, required_hole))
                community_combos = [tuple()] if required_community == 0 else list(itertools.combinations(community_cards, required_community))
                
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
            # Get requirements (default to 0 if not specified)
            required_hole = showdown_rules.get("holeCards", 0)
            required_community = showdown_rules.get("communityCards", 0)
            
            # Ensure we have enough cards to evaluate
            if len(hole_cards) < required_hole or len(community_cards) < required_community:
                logger.warning(
                    f"Not enough cards for player {player.id}: "
                    f"Has {len(hole_cards)} hole cards (need {required_hole}) and "
                    f"{len(community_cards)} community cards (need {required_community})"
                )
                return []
            
            # Generate combinations only for categories with requirements > 0
            hole_combos = [tuple()] if required_hole == 0 else list(itertools.combinations(hole_cards, required_hole))
            community_combos = [tuple()] if required_community == 0 else list(itertools.combinations(community_cards, required_community))
            
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
                    if self.betting.structure != BettingStructure.LIMIT:
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
    