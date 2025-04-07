"""Betting management and tracking."""
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from abc import ABC, abstractmethod
from enum import Enum

from generic_poker.config.loader import BettingStructure
from generic_poker.game.pot import Pot
from generic_poker.game.table import Player, Table

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
    
    def __init__(self, table: 'Table'):
        """Initialize betting manager."""
        self.table = table  # Reference to Table for active players
        self.pot = Pot()
        self.current_bets: Dict[str, PlayerBet] = {}  # player_id -> bet info
        self.current_bet: int = 0  # Highest bet in current round
        self.betting_round: int = 0  # Track which betting round we're in
        self.last_raise_size = 0 # Track minimum raise rules (still needed?)
        self.small_bet: int = 0  
        self.bring_in_posted = False  # Track if bring-in has been posted
        
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
    
    def get_ante_total(self) -> int:
        """Get the total pot amount across all pots in the current round."""
        return self.pot.ante_total
    
    # def award_pots(self, winners: List[Player], side_pot_index: Optional[int] = None) -> None:
    #     """Award main or specified side pot to winners, updating stacks."""
    #     if not winners:
    #         logger.error("No winners to award pots")
    #         return
    #     amount = (self.pot.round_pots[-1].side_pots[side_pot_index].amount 
    #             if side_pot_index is not None 
    #             else self.pot.round_pots[-1].main_pot.amount)
    #     if len(winners) == 1:
    #         winners[0].stack += amount
    #         logger.info(f"Awarded pot of ${amount} to {winners[0].name}")
    #     else:
    #         amount_per_player = amount // len(winners)
    #         remainder = amount % len(winners)
    #         for i, winner in enumerate(winners):
    #             award = amount_per_player + (1 if i < remainder else 0)
    #             winner.stack += award
    #             logger.info(f"Awarded ${award} to {winner.name} from split pot")
    #     self.pot.award_to_winners(winners, side_pot_index)  # Clears pot

    def award_pots(self, winners: List[Player], side_pot_index: Optional[int] = None, award_amount: Optional[int] = None) -> None:
        """
        Award main or specified side pot to winners, updating stacks.
        
        Args:
            winners: List of players who won
            side_pot_index: Index of side pot to award (None for main pot)
            award_amount: Specific amount to award (if None, awards full pot)
        """
        if not winners:
            logger.error("No winners to award pots")
            return
            
        pot = (self.pot.round_pots[-1].side_pots[side_pot_index] 
            if side_pot_index is not None 
            else self.pot.round_pots[-1].main_pot)
        
        total_pot_amount = pot.amount
        
        # Determine how much to award
        if award_amount is None:
            # Award the full pot
            amount_to_award = total_pot_amount
            is_full_pot = True
        else:
            # Award the specified amount
            amount_to_award = min(award_amount, total_pot_amount)  # Don't award more than available
            is_full_pot = (amount_to_award >= total_pot_amount)

        # Don't award anything if the amount is zero
        if amount_to_award <= 0:
            logger.debug(f"No pot to award (amount: ${amount_to_award})")
            return            
        
        if len(winners) == 1:
            winners[0].stack += amount_to_award
            logger.info(f"Awarded pot of ${amount_to_award} to {winners[0].name}")
        else:
            amount_per_player = amount_to_award // len(winners)
            remainder = amount_to_award % len(winners)
            for i, winner in enumerate(winners):
                player_award = amount_per_player + (1 if i < remainder else 0)
                winner.stack += player_award
                logger.info(f"Awarded ${player_award} to {winner.name} from split pot")
        
        # Only clear the pot if we're awarding the full amount
        if is_full_pot:
            self.pot.award_to_winners(winners, side_pot_index)  # Clears pot
        else:
            # For partial awards, we reduce the pot by the awarded amount
            self.pot.award_partial_to_winners(winners, side_pot_index, amount_to_award)       

    def get_side_pot_eligible_players(self, index: int) -> Set[str]:
        """Get eligible players for a side pot."""
        return self.pot.round_pots[-1].side_pots[index].eligible_players

    def get_additional_required(self, player_id: str) -> int:
        """
        Get additional chips required for player to meet the current bet.
        
        This returns the number of chips that will be deducted from the player's stack
        if they call the current bet.
        
        Args:
            player_id: ID of player to check
            
        Returns:
            Additional chips required to call
        """
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        return self.current_bet - current_bet    
    
    @abstractmethod
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """
        Get minimum total bet amount required for a valid action.
        
        This represents the total amount a player must have bet after the action,
        not just the additional chips needed. The returned value can be directly 
        used as the 'amount' parameter in place_bet().
        
        For a call, this returns the current bet amount.
        For an initial bet (when no one has bet), this returns the minimum opening bet.
        
        Args:
            player_id: ID of player to check
            bet_type: Type of bet being made
            
        Returns:
            Total minimum bet amount in chips
        """
        pass
       
    @abstractmethod
    def get_min_raise(self, player_id: str) -> int:
        """
        Get minimum total bet amount for a valid raise.
        
        This represents the total amount a player must have bet to make a valid raise,
        not just the additional chips needed. The returned value can be directly 
        used as the 'amount' parameter in place_bet().
        
        Args:
            player_id: ID of player to check
            
        Returns:
            Total minimum raise amount in chips
        """
        pass

    @abstractmethod
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """
        Get maximum total bet amount allowed.
        
        This represents the total amount a player can bet after the action,
        not just the additional chips needed. The returned value can be directly 
        used as the 'amount' parameter in place_bet().
        
        Args:
            player_id: ID of player to check
            bet_type: Type of bet being made
            player_stack: Player's available stack size
            
        Returns:
            Total maximum bet amount in chips
        """
        pass
        
    @abstractmethod
    def validate_bet(self, player_id: str, amount: int, player_stack: int, bet_type: BetType = BetType.BIG) -> bool:
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
        
    def place_bet(self, player_id: str, amount: int, stack: int, is_forced: bool = False, bet_type: BetType = BetType.BIG, is_ante: bool = False) -> None:
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
        current_ante = self.pot.total_antes.get(f"round_{self.pot.current_round}_{player_id}", 0)
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount  # 1 after ante
        amount_to_add = amount - (current_bet - current_ante)  # 3 - (1 - 1) = 3
        
        logger.debug(f"place_bet(player_id: {player_id}, amount: {amount}, stack: {stack}, is_forced: {is_forced}, bet_type: {bet_type}, is_ante: {is_ante})")
        logger.debug(f"  current_bet: {current_bet}, current_ante: {current_ante}")
        logger.debug(f"  amount_to_add: {amount_to_add} (amount: {amount} - current_bet: {current_bet} + current_ante: {current_ante})")

        # Skip validation for forced bets
        if not is_forced and not self.validate_bet(player_id, amount, stack, bet_type):
            raise ValueError(f"Invalid bet: {amount}") 
           
        is_all_in = amount_to_add >= stack
                
        # Track raise size if this bet is raising
        if amount > self.current_bet:
            raise_size = amount - self.current_bet
            logger.debug(f"Tracking raise size: {raise_size}")
            self.last_raise_size = max(self.last_raise_size, raise_size)
        
        # Update player bet tracking
        new_bet = PlayerBet()
        new_bet.amount = current_bet + amount_to_add  # Always accumulate: 1 + 3 = 4
        new_bet.has_acted = not is_forced  # Only mark as acted if not a forced bet
        # ante is not a blind
        new_bet.posted_blind = (is_forced or self.current_bets.get(player_id, PlayerBet()).posted_blind) and not is_ante
        new_bet.is_all_in = is_all_in
        
        logger.debug(f"current_bets before: {[(pid, bet.amount) for pid, bet in self.current_bets.items()]}")
        logger.debug(f"  new_bet: {new_bet}")
        self.current_bets[player_id] = new_bet
        logger.debug(f"current_bets after: {[(pid, bet.amount) for pid, bet in self.current_bets.items()]}")

        # Update pot with the additional amount
        if amount_to_add > 0:
    #        self.pot.add_bet(player_id, new_bet.amount, is_all_in, stack, is_ante=is_ante)
            self.pot.add_bet(player_id, amount, is_all_in, stack, is_ante=is_ante)  # Pass 3, not 4
       
        # Update current bet if this is highest, and isn't an ante which doesn't impact the pot
        if not is_ante:
            self.current_bet = max(self.current_bet, amount)

        if bet_type == BetType.BRING_IN:  # Or check PlayerAction.BRING_IN depending on implementation
            self.bring_in_posted = True  # Set flag when bring-in is posted

        logger.debug(f"After bet: current_bet={self.current_bet}, "
                    f"last_raise_size={self.last_raise_size}, "
                    f"pot={self.pot.total}, "
#                    f"current_bets={[(pid, bet.amount) for pid, bet in self.current_bets.items()]}")
                    f"current_bets={[(pid, bet.amount, 'acted' if bet.has_acted else 'not acted', 'blind' if bet.posted_blind else 'not blind') for pid, bet in self.current_bets.items()]}")

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
        # get the ante - since it doesn't count towards the current bet
        current_ante = self.pot.total_antes.get(f"round_{self.pot.current_round}_{player_id}", 0)

        return self.current_bet - current_bet + current_ante
        
    def round_complete(self) -> bool:
        """
        Check if betting round is complete.
        
        Round is complete when:
        1. All active players have acted
        2. All active players have matched the current bet or are all-in
        """
        active_players = [p.id for p in self.table.players.values() if p.is_active]
        
        if len(self.current_bets) != len(active_players):
            logger.debug("Round not complete - not all players acted")
            return False
        
        for bet in self.current_bets.values():
            if not bet.has_acted:
                logger.debug("Round not complete - not everyone has acted")
                return False
        
        amounts = set(bet.amount for bet in self.current_bets.values() if not bet.is_all_in)
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
            # Continue same round, preserve current bet but reset 'has_acted' flags
            current = self.current_bet
            # Keep all bets but reset has_acted for everyone, not just blinds
            # Note: not sure if we want to do this if continuing a round - the blinds should not be set
            #for bet in self.current_bets.values():
            #    bet.has_acted = False
        else:
            # True new round (e.g., after dealing)
            self.current_bets.clear()
            current = 0
            self.betting_round += 1
            self.pot.end_betting_round()  # Start new Pot round
            self.bring_in_posted = False  # Reset at the start of each betting round
        self.current_bet = current

        logger.debug(f"Starting betting round {self.betting_round}: preserve_bet={preserve_current_bet}, "
                    f"current_bet={self.current_bet}, "
                    f"current_bets={[(pid, bet.amount, 'acted' if bet.has_acted else 'not acted', 'blind' if bet.posted_blind else 'not blind') for pid, bet in self.current_bets.items()]}")
     
    def new_hand(self) -> None:
        """Start a new hand."""
        self.current_bets.clear()
        self.current_bet = 0
        self.betting_round = 0
        self.bring_in_posted = False
        self.last_raise_size = 0  # Reset last raise size for new hand
        self.pot.new_hand()  # Reset pot for new hand
        logger.debug("New hand started: current_bet=0, betting_round=0, current_bets cleared")

class LimitBettingManager(BettingManager):
    """Betting manager for limit games."""
    
    def __init__(self, table: 'Table', small_bet: int, big_bet: int):
        """
        Initialize limit betting manager.
        
        Args:
            small_bet: Size of small bets
            big_bet: Size of big bets
        """
        assert small_bet is not None and small_bet > 0, "small_bet must be set"
        super().__init__(table)
        self.small_bet = small_bet
        self.big_bet = big_bet
                
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """
        Get minimum bet size.
        
        Returns the total amount the player must have bet to make a valid bet.
        In limit games with blinds, this is the current bet amount.
        """
        if bet_type == BetType.BRING_IN:
            return self.bring_in  # Assuming bring_in is passed to BettingManager somehow
        return self.current_bet  # Antes don’t affect this
            
    def get_min_raise(self, player_id: str) -> int:
        """
        Get minimum amount for a raise.
        
        In limit games:
        - Minimum raise is fixed at current bet + one bet unit (small or big depending on round)
        - This is also the maximum raise (only one bet size allowed in limit)
        """
        if self.current_bet == 0:
            # Opening bet - use the appropriate bet size for the round
            bet_size = self.small_bet if self.betting_round < 2 else self.big_bet
            return bet_size
        
        # Raise amount is fixed in limit games
        bet_size = self.small_bet if self.betting_round < 2 else self.big_bet
        return self.current_bet + bet_size
            
    def get_max_bet(self, player_id: str, bet_type: BetType, stack: int) -> int:
        """
        Get maximum bet size.
        
        Returns the total amount the player can bet.
        In limit games, this is the current bet plus one bet unit (small or big depending on round).
        """
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        bet_size = self.small_bet if self.betting_round < 2 else self.big_bet
        
        # If there's already a bet, the max is current bet + one bet unit
        if self.current_bet > 0:
            max_bet = self.current_bet + bet_size
        else:
            # Otherwise just the bet unit itself
            max_bet = bet_size
            
        # Can't bet more than stack
        return min(max_bet, current_bet + stack)
        
    def validate_bet(self, player_id: str, amount: int, player_stack: int, bet_type: BetType = BetType.BIG) -> bool:
        """
        Validate bet is correct size for limit game.
        
        Args:
            player_id: ID of betting player
            amount: Total amount player will have bet
            player_stack: Player's current stack
            bet_type: Whether this betting round is a small or big bet
            
        Returns:
            True if bet is valid, False otherwise
        """
        logger.debug(f"Validating limit bet in round {self.betting_round}: player={player_id}, amount={amount}, "
                    f"player_stack={player_stack},  bet_type={bet_type}")
                    
        logger.debug(f"self.current_bet={self.current_bet}")
        
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        to_call = self.current_bet - current_bet
        bet_size = self.small_bet if bet_type == BetType.SMALL else self.big_bet

        logger.debug(f"current_bet={current_bet}, to_call={to_call}, bet_size={bet_size}")

        if amount == 0:  # Check/fold always valid
            return True
                   
        # All-in for less than call amount is valid
        if amount < self.current_bet and amount == current_bet + player_stack:
            return True
            
        if amount == self.current_bet:  # Calling exact amount is valid
            return to_call <= player_stack
            
        # Stud post-bring-in completion
        if bet_type == BetType.SMALL and amount == self.small_bet and self.betting_round <= 2:
            logger.debug(f"Valid completion to small bet: {amount}")
            return amount <= player_stack
        
        # Standard limit betting
        if all(bet.posted_blind for bet in self.current_bets.values()):
            # First bet in the round should be exactly the bet unit
            if amount == bet_size:
                return amount <= player_stack
        
        # For raises, must be exactly current bet + one bet unit
        if amount == self.current_bet + bet_size:
            return amount - current_bet <= player_stack
            
        logger.debug(f"Invalid limit bet: {amount} not equal to current bet ({self.current_bet}) + bet unit ({bet_size})")
        return False

class NoLimitBettingManager(BettingManager):
    """Betting manager for no-limit games."""
    
    def __init__(self, table: 'Table', small_bet: int):
        """
        Initialize no-limit betting manager.
        
        Args:
            small_bet: Minimum bet size (usually equal to big blind)
        """
        assert small_bet > 0, "small_bet must be set"
        super().__init__(table)
        self.small_bet = small_bet
        self.last_raise_size = small_bet  # Initialize to small bet
        
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """
        Get minimum bet allowed.
        
        Returns the total amount the player must have bet to make a valid bet.
        In no-limit, this is either the current bet (for calls) or the small bet (for opening bets).
        """
        if self.current_bet == 0:
            return self.small_bet  # Minimum opening bet
        return self.current_bet  # Minimum to call is the current bet
         
    def get_min_raise(self, player_id: str) -> int:
        """
        Get minimum amount for a raise (not just a call).
        
        In no-limit:
        - Minimum raise is current bet + max(BB, previous raise size)
        """
        if self.current_bet == 0:
            return self.small_bet
        
        # For raising, minimum is current bet plus at least 
        # the size of the previous raise (or BB if larger)
        min_raise_increment = max(self.small_bet, self.last_raise_size)
        logger.debug(f"Min Raise Calculation: Current Bet: {self.current_bet}, Small Bet: {self.small_bet}, "
                     f"Last Raise: {self.last_raise_size}, Min Increment: {min_raise_increment}")
        
        return self.current_bet + min_raise_increment
         
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """
        Get maximum bet size.
        
        Returns the total amount the player can bet.
        In No Limit, this is their current bet plus their entire stack.
        """
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        return current_bet + player_stack  # Total bet including what's already in
        
    def validate_bet(self, player_id: str, amount: int, player_stack: int, bet_type: BetType = BetType.BIG) -> bool:
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
        min_raise = self.get_min_raise(player_id)
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
    
    def __init__(self, table: 'Table', small_bet: int):
        """
        Initialize pot-limit betting manager.
        
        Args:
            small_bet: Minimum bet size
        """
        assert small_bet > 0, "small_bet must be set"
        super().__init__(table)
        self.small_bet = small_bet
        self.last_raise_size = 0
        
    def get_min_bet(self, player_id: str, bet_type: BetType) -> int:
        """
        Get minimum bet allowed.
        
        Returns the total amount the player must have bet to make a valid bet.
        In pot-limit, this is either the current bet (for calls) or the small bet (for opening bets).
        """
        if self.current_bet == 0:
            return self.small_bet  # Minimum opening bet
        return self.current_bet  # Minimum to call is the current bet
        
    def get_min_raise(self, player_id: str) -> int:
        """
        Get minimum amount for a raise (not just a call).
        
        In pot-limit:
        - Minimum raise is current bet + max(BB, previous raise size)
        """
        if self.current_bet == 0:
            return self.small_bet
        
        # For raising, minimum is current bet plus at least 
        # the size of the previous raise (or BB if larger)
        min_raise_increment = max(self.small_bet, self.last_raise_size)
        
        return self.current_bet + min_raise_increment
        
    def get_max_bet(self, player_id: str, bet_type: BetType, player_stack: int) -> int:
        """
        Get maximum bet size.
        
        Returns the total amount the player can bet.
        In Pot Limit: max bet = current bet + pot after call
        """
        current_bet = self.current_bets.get(player_id, PlayerBet()).amount
        call_amount = self.current_bet - current_bet
        
        # Calculate pot size after call
        # Antes are not included in the pot for betting purposes in the first round

        #pot_after_call = self.pot.total(exclude_antes=(self.betting_round == 0)) + call_amount
        pot_after_call = self.get_total_pot() - self.get_ante_total() + call_amount
      
        max_bet = self.current_bet + pot_after_call
        
        # Can't bet more than stack
        max_player_bet = current_bet + player_stack
        return min(max_bet, max_player_bet)
               
    def validate_bet(self, player_id: str, amount: int, player_stack: int, bet_type: BetType = BetType.BIG) -> bool:
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
        min_raise = self.get_min_raise(player_id)
        max_raise = self.get_max_bet(player_id, BetType.BIG, player_stack)
        
        # Must be between min raise and max pot limit
        if amount < min_raise:
            return False
            
        if amount > max_raise:
            return False
            
        # Can't bet more than stack
        additional_needed = amount - current_bet
        if additional_needed > player_stack:
            return False
            
        return True


def create_betting_manager(
    structure: BettingStructure,
    small_bet: int,
    big_bet: Optional[int] = None,
    table: Optional['Table'] = None    
) -> BettingManager:
    """
    Factory function to create appropriate betting manager.
    
    Args:
        structure: Type of betting structure
        small_bet: Small bet/min bet size
        big_bet: Big bet size (for limit games)
        table: Table object for player access
        
    Returns:
        Configured betting manager
    """
    logger.debug(f'Creating betting manager: {structure}, small_bet={small_bet}, big_bet={big_bet}')
    assert small_bet is not None and small_bet > 0, "small_bet must be set"

    if structure == BettingStructure.LIMIT:
        if big_bet is None:
            raise ValueError("Big bet size required for limit games")
        return LimitBettingManager(table, small_bet, big_bet)
        
    if structure == BettingStructure.NO_LIMIT:
        return NoLimitBettingManager(table, small_bet)
        
    if structure == BettingStructure.POT_LIMIT:
        return PotLimitBettingManager(table, small_bet)
        
    raise ValueError(f"Unknown betting structure: {structure}")