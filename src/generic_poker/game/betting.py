"""Betting management and tracking."""
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from abc import ABC, abstractmethod
from enum import Enum

from generic_poker.config.loader import BettingStructure
from generic_poker.game.pot import Pot
from generic_poker.game.table import Player

import logging 

logger = logging.getLogger(__name__)

class BetType(Enum):
    """Types of bets in a round."""
    ANTE = "ante"
    BLIND = "blind"
    BRING_IN = "bring_in"
    SMALL = "small"
    BIG = "big"


@dataclass
class BetConfig:
    """Configuration for a betting round."""
    min_bet: int
    max_bet: Optional[int] = None  # None for no-limit
    min_raise: Optional[int] = None  # For no-limit/pot-limit games


@dataclass
class PlayerBet:
    """Tracks a player's betting in the current round."""
    amount: int = 0
    has_acted: bool = False  # True if player has taken an action this round
    posted_blind: bool = False  # True if this bet was a blind
    is_all_in: bool = False

class BettingManager(ABC):
    """
    Abstract base class for betting managers.
    
    Different implementations handle different betting structures
    (limit, no-limit, pot-limit).
    """
    
    def __init__(self):
        """Initialize betting manager."""
        self.pot = Pot()
        self.current_bets: Dict[str, PlayerBet] = {}  # player_id -> bet info
        self.current_bet: int = 0  # Highest bet in current round
        self.betting_round: int = 0  # Track which betting round we're in
        self.last_raise_size = 0 # Track minimum raise rules (still needed?)
        self.small_bet: int = 0  
        
    def get_main_pot_amount(self) -> int:
        """Get the amount in the current round's main pot."""
        return self.pot.round_pots[-1].main_pot.amount

    def get_side_pot_count(self) -> int:
        """Get the number of side pots in the current round."""
        return len(self.pot.round_pots[-1].side_pots)

    def get_side_pot_amount(self, index: int) -> int:
        """Get the amount in the specified side pot for the current round."""
        return self.pot.round_pots[-1].side_pots[index].amount

    def get_total_pot(self) -> int:
        """Get the total pot amount across all pots in the current round."""
        return self.pot.total
    
    def award_pots(self, winners: List[Player], side_pot_index: Optional[int] = None) -> None:
        """Award main or specified side pot to winners, updating stacks."""
        if not winners:
            logger.error("No winners to award pots")
            return
        amount = (self.pot.round_pots[-1].side_pots[side_pot_index].amount 
                if side_pot_index is not None 
                else self.pot.round_pots[-1].main_pot.amount)
        if len(winners) == 1:
            winners[0].stack += amount
            logger.info(f"Awarded pot of ${amount} to {winners[0].name}")
        else:
            amount_per_player = amount // len(winners)
            remainder = amount % len(winners)
            for i, winner in enumerate(winners):
                award = amount_per_player + (1 if i < remainder else 0)
                winner.stack += award
                logger.info(f"Awarded ${award} to {winner.name} from split pot")
        self.pot.award_to_winners(winners, side_pot_index)  # Clears pot

    def get_side_pot_eligible_players(self, index: int) -> Set[str]:
        """Get eligible players for a side pot."""
        return self.pot.round_pots[-1].side_pots[index].eligible_players

    @abstractmethod
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """Get minimum bet allowed for player."""
        pass
        
    @abstractmethod
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """Get maximum bet allowed for player."""
        pass
        
    @abstractmethod
    def validate_bet(self, player_id: str, amount: int, player_stack: int) -> bool:
        """
        Validate if a bet is legal.
        
        Args:
            player_id: ID of betting player
            amount: Total amount player will have bet
            player_stack: Player's current stack
            
        Returns:
            True if bet is valid, False otherwise
        """
        pass
        
    def place_bet(self, player_id: str, amount: int, stack: int, is_forced: bool = False) -> None:
        """
        Place a bet for a player.

        Args:
            player_id: ID of betting player
            amount: Total amount player will have bet in this round after this action.
                    This is the total for the current round only, not across all rounds.
                    Use get_amount_to_add() to compute the incremental chips needed.
            stack: Player's chip stack before this bet
            is_forced: Whether this is a forced bet (blind/ante)

        Examples:
            # Round 1: P1 opens for 100
            betting.place_bet("P1", 100, 1000)  # Adds 100, stack becomes 900
            
            # Round 1: P2 raises to 300
            betting.place_bet("P2", 300, 1000)  # Adds 300, stack becomes 700
            
            # Round 2: P1 bets 200 anew
            betting.place_bet("P1", 200, 900)  # Adds 200, stack becomes 700
        """
        # Get current amount from player if any
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        amount_to_add = amount - current_bet
              
        # Skip validation for forced bets
        if not is_forced and not self.validate_bet(player_id, amount, stack):
            raise ValueError(f"Invalid bet: {amount}") 
           
        is_all_in = amount_to_add >= stack

        logger.debug(f"Processing bet: player={player_id}, new_total={amount}, "
                    f"current_amount={current_bet}, to_add={amount_to_add}, "
                    f"stack_before={stack}")       
                
        # Track raise size if this bet is raising
        if amount > self.current_bet:
            raise_size = amount - self.current_bet
            logger.debug(f"Tracking raise size: {raise_size}")
            self.last_raise_size = raise_size        
        
        # Update player bet tracking
        new_bet = PlayerBet()
        new_bet.amount = amount
        new_bet.has_acted = not is_forced  # Only mark as acted if not a forced bet
        new_bet.posted_blind = is_forced or self.current_bets.get(player_id, PlayerBet()).posted_blind
        new_bet.is_all_in = is_all_in
        
        self.current_bets[player_id] = new_bet
        
        # Update pot with the additional amount
        if amount_to_add > 0:
            self.pot.add_bet(player_id, amount, is_all_in, stack)
       
        # Update current bet if this is highest
        self.current_bet = max(self.current_bet, amount)
        
        logger.debug(f"After bet: current_bet={self.current_bet}, "
                    f"last_raise_size={self.last_raise_size}, "
                    f"pot={self.pot.total}, "
                    f"player_bets={[(pid, bet.amount) for pid, bet in self.current_bets.items()]}")

    def get_amount_to_add(self, player_id: str, proposed_total: int) -> int:
        """
        Calculate how much more a player needs to add to reach a proposed total bet.

        Args:
            player_id: ID of player
            proposed_total: Total amount player wants to bet

        Returns:
            Amount player needs to add to reach proposed total

        Example:
            # P1 has bet 100, wants to know how much to add to bet 300 total
            amount_to_add = betting.get_amount_to_add("P1", 300)  # Returns 200
        """
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        return proposed_total - current_bet

    def get_stack_impact(self, player_id: str, proposed_total: int) -> tuple[int, int]:
        """
        Calculate impact on player's stack for a proposed bet.

        Args:
            player_id: ID of player
            proposed_total: Total amount player wants to bet

        Returns:
            Tuple of (amount_to_add, new_stack)
            where amount_to_add is how much more needs to be bet
            and new_stack is what their stack will be after the bet

        Example:
            # P1 has stack of 1000, has bet 100, wants to bet 300 total
            amount_to_add, new_stack = betting.get_stack_impact("P1", 300)
            # Returns (200, 800)
        """
        amount_to_add = self.get_amount_to_add(player_id, proposed_total)
        current_stack = self.table.get_player_stack(player_id)  # Need to add this method
        return amount_to_add, current_stack - amount_to_add
        
    def get_required_bet(self, player_id: str) -> int:
        """Get amount player needs to bet to call."""
        current_bet = self.current_bets.get(
            player_id,
            PlayerBet()
        ).amount
        return self.current_bet - current_bet
        
    def round_complete(self) -> bool:
        """
        Check if betting round is complete.
        
        Round is complete when:
        1. All active players have acted
        2. All active players have matched the current bet or are all-in
        """
        logger.debug(f"Checking if round complete. Current bets: {[(pid, bet.amount, bet.has_acted) for pid, bet in self.current_bets.items()]}")
        
        # Everyone must have acted
        for bet in self.current_bets.values():
            if not bet.has_acted:
                logger.debug("Round not complete - not everyone has acted")
                return False
        
        # All bets must be equal to current bet
        amounts = set()
        for bet in self.current_bets.values():
            if not bet.is_all_in:
                amounts.add(bet.amount)
        
        logger.debug(f"Unique bet amounts: {amounts}")
        if len(amounts) > 1:
            logger.debug("Round not complete - bets not equal")
            return False
            
        logger.debug("Round complete - all players acted and bets equal")
        return True
        
    def new_round(self, preserve_current_bet: bool = False) -> None:
        """
        Start a new betting round or continue within the current round after blinds.
        
        Args:
            preserve_current_bet: If True, continue current round (e.g., blinds to betting),
                                preserving bet amount and blind bets; if False, start a new round.
        """
        if preserve_current_bet:
            # Continue same round, preserve blinds and current bet
            current = self.current_bet
            blind_bets = {pid: bet for pid, bet in self.current_bets.items() if bet.posted_blind}
            self.current_bets = blind_bets  # Keep only blinds, reset others
        else:
            # True new round (e.g., after dealing)
            self.current_bets.clear()
            current = 0
            self.betting_round += 1
            self.pot.end_betting_round()  # Start new Pot round
        self.current_bet = current
        logger.debug(f"Starting betting round {self.betting_round}: preserve_bet={preserve_current_bet}, "
                    f"current_bet={self.current_bet}, "
                    f"current_bets={[(pid, bet.amount, 'acted' if bet.has_acted else 'not acted', 'blind' if bet.posted_blind else 'not blind') for pid, bet in self.current_bets.items()]}")
        

class LimitBettingManager(BettingManager):
    """Betting manager for limit games."""
    
    def __init__(self, small_bet: int, big_bet: int):
        """
        Initialize limit betting manager.
        
        Args:
            small_bet: Size of small bets
            big_bet: Size of big bets
        """
        assert small_bet is not None and small_bet > 0, "small_bet must be set"
        super().__init__()
        self.small_bet = small_bet
        self.big_bet = big_bet
        
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """
        Get minimum bet size.
        
        In limit games with blinds:
        - First two betting rounds use small bet
        - Later rounds use big bet
        - Blinds and antes always use small bet
        """
        small_bet = self.small_bet if self.small_bet is not None else 0
        big_bet = self.big_bet if self.big_bet is not None else 0

        if bet_type in [BetType.BLIND, BetType.ANTE]:
            return small_bet
            
        # First two betting rounds use small bet
        if self.betting_round < 2:  # 0-based, so rounds 0 and 1
            return small_bet
        return big_bet
        
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """Get maximum bet (same as min in limit games).

        player_stack is ignored because limit games have fixed bet sizes.
        """
        return self.get_min_bet(player_id, bet_type)
        
    # def validate_bet(self, player_id: str, amount: int, player_stack: int) -> bool:
    #     """
    #     Validate bet is correct size for limit game.
        
    #     Args:
    #         player_id: ID of betting player
    #         amount: Total amount player will have bet
    #         player_stack: Player's current stack
            
    #     Returns:
    #         True if bet is valid, False otherwise
    #     """
    #     logger.debug(f"Validating limit bet: player={player_id}, amount={amount}, "
    #                 f"current_bet={self.current_bet}, stack={player_stack}")
        
    #     if amount == 0:  # Check/fold always valid
    #         return True
            
    #     current_bet = self.current_bets.get(player_id, PlayerBet()).amount
    #     to_call = self.current_bet - current_bet
        
    #     # All-in for less than call amount is valid
    #     if amount < self.current_bet and amount == current_bet + player_stack:
    #         return True
            
    #     if amount == self.current_bet:  # Calling exact amount is valid
    #         return to_call <= player_stack
            
    #     # For raises in limit games, must be exactly double the current bet
    #     # (unless completing a partial bet like SB->full bet)
    #     if current_bet > 0 and amount == self.current_bet:
    #         return True
            
    #     if amount > self.current_bet:
    #         # Must be exactly one bet size more
    #         bet_size = self.get_min_bet(player_id, BetType.BIG)
    #         expected = self.current_bet + bet_size
    #         if amount != expected:
    #             logger.debug(f"Invalid raise: {amount} != {expected}")
    #             return False
                
    #         # Check stack size
    #         additional_needed = amount - current_bet
    #         if additional_needed > player_stack:
    #             return False
                
    #         return True
            
    #     return False

    def validate_bet(self, player_id: str, amount: int, player_stack: int) -> bool:
        logger.debug(f"Validating limit bet: player={player_id}, amount={amount}, "
                    f"current_bet={self.current_bet}, stack={player_stack}")
        
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        to_call = self.current_bet - current_bet
        bet_size = self.get_min_bet(player_id, BetType.BIG)  # 10 in round 0
        
        if amount == 0:  # Check/fold
            return True
        if amount < self.current_bet and amount == current_bet + player_stack:  # All-in
            return True
        if amount == self.current_bet:  # Call
            return to_call <= player_stack
        
        # First non-forced bet after blinds must be small bet
        all_forced = all(bet.posted_blind for bet in self.current_bets.values())
        if all_forced and len(self.current_bets) > 0:  # After blinds
            expected = bet_size  # 10
            if amount != expected:
                logger.debug(f"Invalid first bet: {amount} != {expected}")
                return False
            return amount <= player_stack
        
        # Raises must increment by bet_size
        if amount > self.current_bet:
            expected = self.current_bet + bet_size
            if amount != expected:
                logger.debug(f"Invalid raise: {amount} != {expected}")
                return False
            additional_needed = amount - current_bet
            return additional_needed <= player_stack
        
        logger.debug(f"Invalid bet: {amount} not handled by rules")
        return False

class NoLimitBettingManager(BettingManager):
    """Betting manager for no-limit games."""
    
    def __init__(self, small_bet: int):
        """
        Initialize no-limit betting manager.
        
        Args:
            min_bet: Minimum bet size
        """
        assert small_bet > 0, "small_bet must be set"
        super().__init__()
        self.small_bet = small_bet
        self.last_raise_size = small_bet  # Initialize to small bet
        
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """
        Get minimum bet allowed.
        
        In no-limit:
        - If no previous bet, minimum is BB (small_bet)
        - If calling a bet, minimum is current bet
        - If raising, minimum is:
          current bet + max(BB, previous raise size)
        """
        if self.current_bet == 0:
            logger.debug("No prior bet, using small_bet as min bet.")
            return self.small_bet
        
        # For raising, minimum is current bet plus at least 
        # the size of the previous raise (or BB if larger)
        min_raise = max(self.small_bet, self.last_raise_size)
        logger.debug(f"Min Raise Calculation: Current Bet: {self.current_bet}, "
                    f"Last Raise: {self.last_raise_size}, Min Raise: {min_raise}")
        
        return self.current_bet + min_raise
         
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """
        Get maximum bet size.
        
        In No Limit, max bet is always player's stack.
        """
        return player_stack
        
    def validate_bet(self, player_id: str, amount: int, player_stack: int) -> bool:
        """
        Validate bet in no-limit game.
        
        Args:
            player_id: ID of betting player
            amount: Total amount player will have bet
            player_stack: Player's current stack
            
        Returns:
            True if bet is valid, False otherwise
        """
        logger.debug(f"Validating NL bet: player={player_id}, amount={amount}, "
                    f"current_bet={self.current_bet}, stack={player_stack}")
        
        if amount == 0:  # Check/fold always valid
            return True
            
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        to_call = self.current_bet - current_bet
        
        # Allow all-in bets (calls or raises) for the player's full stack
        if amount == current_bet + player_stack or amount == player_stack:
            logger.debug(f"Player {player_id} is going all-in for {amount}")
            return True
            
        if amount == self.current_bet:  # Calling exact amount is valid
            return to_call <= player_stack
            
        # For raises:
        min_raise = self.get_min_bet(player_id, BetType.BIG)
        # Can't raise more than stack
        max_raise = self.get_max_bet(player_id, BetType.BIG, player_stack)
        
        # Must be at least minimum raise unless all-in
        if amount < min_raise:
            return False
            
        # Can't bet more than stack
        additional_needed = amount - current_bet
        if additional_needed > player_stack:
            return False
            
        return True


class PotLimitBettingManager(BettingManager):
    """Betting manager for pot-limit games."""
    
    def __init__(self, small_bet: int):
        """
        Initialize pot-limit betting manager.
        
        Args:
            min_bet: Minimum bet size
        """
        assert small_bet > 0, "small_bet must be set"
        super().__init__()
        self.small_bet = small_bet
        self.last_raise_size = 0
        
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """Get minimum bet size - same as no-limit."""
        if self.current_bet == 0:
            return self.small_bet
        return self.current_bet + max(self.small_bet, self.last_raise_size)
        
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """
        Get maximum bet size.
        
        In Pot Limit:
        max raise = size of pot after call
        total bet = current bet + call amount + max raise
        """
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        call_amount = self.current_bet - current_bet
        
        # Calculate pot size after call
        pot_after_call = self.pot.total + call_amount
        
        # Maximum raise is size of pot after call
        max_raise = pot_after_call
        
        # Total bet is: current bet + raise amount
        max_bet = self.current_bet + max_raise
        
        # Can't bet more than stack
        return min(max_bet, player_stack)
               
    def validate_bet(self, player_id: str, amount: int, player_stack: int) -> bool:
        """
        Validate bet in pot-limit game.
        
        Args:
            player_id: ID of betting player
            amount: Total amount player will have bet
            player_stack: Player's current stack
            
        Returns:
            True if bet is valid, False otherwise
        """
        logger.debug(f"Validating PL bet: player={player_id}, amount={amount}, "
                    f"current_bet={self.current_bet}, stack={player_stack}")
        
        if amount == 0:  # Check/fold always valid
            return True
            
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        to_call = self.current_bet - current_bet
        
        # All-in for less than call amount is valid
        if amount < self.current_bet and amount == current_bet + player_stack:
            return True
            
        if amount == self.current_bet:  # Calling exact amount is valid
            return to_call <= player_stack
            
        # For raises:
        min_raise = self.get_min_bet(player_id, BetType.BIG)
        max_raise = self.get_max_bet(player_id, BetType.BIG, player_stack)
        
        # Must be between min raise and max pot limit
        if not (min_raise <= amount <= max_raise):
            return False
            
        # Can't bet more than stack
        additional_needed = amount - current_bet
        if additional_needed > player_stack:
            return False
            
        return True


def create_betting_manager(
    structure: BettingStructure,
    small_bet: int,
    big_bet: Optional[int] = None
) -> BettingManager:
    """
    Factory function to create appropriate betting manager.
    
    Args:
        structure: Type of betting structure
        small_bet: Small bet/min bet size
        big_bet: Big bet size (for limit games)
        
    Returns:
        Configured betting manager
    """
    assert small_bet is not None and small_bet > 0, "small_bet must be set"

    if structure == BettingStructure.LIMIT:
        if big_bet is None:
            raise ValueError("Big bet size required for limit games")
        return LimitBettingManager(small_bet, big_bet)
        
    if structure == BettingStructure.NO_LIMIT:
        return NoLimitBettingManager(small_bet)
        
    if structure == BettingStructure.POT_LIMIT:
        return PotLimitBettingManager(small_bet)
        
    raise ValueError(f"Unknown betting structure: {structure}")