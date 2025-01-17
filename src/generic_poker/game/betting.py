"""Betting management and tracking."""
from dataclasses import dataclass
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from enum import Enum

from generic_poker.config.loader import BettingStructure
from generic_poker.game.pot import Pot

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
    def __init__(self):
        self.amount: int = 0
        self.has_acted: bool = False  # True if player has taken an action this round
        self.posted_blind: bool = False  # True if this bet was a blind
        self.is_all_in: bool = False

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
            amount: Total amount player will have bet after this action
            stack: Player's current stack
            is_forced: Whether this is a forced bet (blind/ante)
        """
        # Get current amount from player if any
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        amount_to_add = amount - current_bet
        
        logger.debug(f"Processing bet: player={player_id}, new_total={amount}, "
                    f"current_amount={current_bet}, to_add={amount_to_add}")
        
        # Skip validation for forced bets
        if not is_forced and not self.validate_bet(player_id, amount, stack):
            raise ValueError(f"Invalid bet: {amount}") 
           
        is_all_in = amount_to_add >= stack
        
        # Update player bet tracking
        new_bet = PlayerBet()
        new_bet.amount = amount
        new_bet.has_acted = not is_forced  # Only mark as acted if not a forced bet
        new_bet.posted_blind = is_forced or self.current_bets.get(player_id, PlayerBet()).posted_blind
        new_bet.is_all_in = is_all_in
        
        self.current_bets[player_id] = new_bet
        
        # Update pot with the additional amount
        if amount_to_add > 0:
            self.pot.add_bet(player_id, amount_to_add, is_all_in)
        
        # Update current bet if this is highest
        self.current_bet = max(self.current_bet, amount)
        
        logger.debug(f"After bet: current_bet={self.current_bet}, "
                    f"pot={self.pot.total}, "
                    f"player_bets={[(pid, bet.amount) for pid, bet in self.current_bets.items()]}")

        
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
        Start a new betting round.
        
        Args:
            preserve_current_bet: If True, keep current bet amount and blind information
        """
        if preserve_current_bet:
            # Keep the current bet amount and preserve blind information
            current = self.current_bet
            blind_bets = {
                player_id: bet
                for player_id, bet in self.current_bets.items()
                if bet.posted_blind
            }
            self.current_bets = blind_bets
        else:
            # Reset everything
            self.current_bets.clear()
            current = 0
            self.betting_round += 1  # Increment round counter
            
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
        if bet_type in [BetType.BLIND, BetType.ANTE]:
            return self.small_bet
            
        # First two betting rounds use small bet
        if self.betting_round < 2:  # 0-based, so rounds 0 and 1
            return self.small_bet
        return self.big_bet
        
    def get_max_bet(self, player_id: str, bet_type: BetType) -> int:
        """Get maximum bet (same as min in limit games)."""
        return self.get_min_bet(player_id, bet_type)
        
    def validate_bet(self, player_id: str, amount: int, player_stack: int) -> bool:
        """
        Validate bet is correct size for limit game.
        
        Args:
            player_id: ID of betting player
            amount: Total amount player will have bet
            player_stack: Player's current stack
            
        Returns:
            True if bet is valid, False otherwise
        """
        logger.debug(f"Validating limit bet: player={player_id}, amount={amount}, "
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
            
        # For raises in limit games, must be exactly double the current bet
        # (unless completing a partial bet like SB->full bet)
        if current_bet > 0 and amount == self.current_bet:
            return True
            
        if amount > self.current_bet:
            # Must be exactly one bet size more
            bet_size = self.get_min_bet(player_id, BetType.BIG)
            expected = self.current_bet + bet_size
            if amount != expected:
                logger.debug(f"Invalid raise: {amount} != {expected}")
                return False
                
            # Check stack size
            additional_needed = amount - current_bet
            if additional_needed > player_stack:
                return False
                
            return True
            
        return False


class NoLimitBettingManager(BettingManager):
    """Betting manager for no-limit games."""
    
    def __init__(self, min_bet: int):
        """
        Initialize no-limit betting manager.
        
        Args:
            min_bet: Minimum bet size
        """
        super().__init__()
        self.min_bet = min_bet
        self.last_raise_size = 0  # Track size of last raise for minimum raise rules
        
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """
        Get minimum bet size.
        
        In no-limit:
        - If no bet, minimum is big blind
        - If raising, must raise at least as much as previous raise
        """
        if self.current_bet == 0:
            return self.min_bet
        # Must raise at least as much as the previous raise
        return self.current_bet + max(self.min_bet, self.last_raise_size)
         
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
        
        # All-in for less than call amount is valid
        if amount < self.current_bet and amount == current_bet + player_stack:
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
    
    def __init__(self, min_bet: int):
        """
        Initialize pot-limit betting manager.
        
        Args:
            min_bet: Minimum bet size
        """
        super().__init__()
        self.min_bet = min_bet
        self.last_raise_size = 0
        
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """Get minimum bet size - same as no-limit."""
        if self.current_bet == 0:
            return self.min_bet
        return self.current_bet + max(self.min_bet, self.last_raise_size)
        
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """
        Get maximum bet size.
        
        In Pot Limit:
        max bet = min(player stack, current pot + bets on table + call amount)
        """
        pot_size = self.pot.main_pot
        for side_pot in self.pot.side_pots:
            pot_size += side_pot.amount
        bets_on_table = sum(bet.amount for bet in self.current_bets.values())
        call_amount = self.get_required_bet(player_id)
        
        return min(
            player_stack,
            pot_size + bets_on_table + call_amount
        )
        
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
    if structure == BettingStructure.LIMIT:
        if big_bet is None:
            raise ValueError("Big bet size required for limit games")
        return LimitBettingManager(small_bet, big_bet)
        
    if structure == BettingStructure.NO_LIMIT:
        return NoLimitBettingManager(small_bet)
        
    if structure == BettingStructure.POT_LIMIT:
        return PotLimitBettingManager(small_bet)
        
    raise ValueError(f"Unknown betting structure: {structure}")