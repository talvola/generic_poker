"""Pot management and distribution."""
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class ActivePotNew:
    """Represents a pot (main or side) that can receive bets."""
    amount: int                # Total amount in this pot
    current_bet: int          # Current bet that must be called
    eligible_players: Set[str] # Players who can win this pot
    active_players: Set[str]   # Players who can still bet in this pot
    excluded_players: Set[str] # Players who cannot participate (all-in for less)
    player_bets: Dict[str, int]  # Maps player_id to their total contribution in this pot
    main_pot: bool = False     # True if this is the main pot
    capped: bool = False      # True if pot has reached maximum size
    cap_amount: int = 0       # Maximum bet allowed if capped
    order: int = 0            # Order of creation (for side pots)
    closed: bool = False  # True when betting round ends

    def name(self) -> str:
        """Return descriptive name of pot."""
        return "Main Pot" if self.main_pot else f"Side Pot {self.order}"
    
    def __str__(self):
        bets = ", ".join(f"{pid}:{amt}" for pid, amt in self.player_bets.items())
        return (f"{self.name()}: amount={self.amount}, current_bet={self.current_bet}, "
                f"capped={self.capped}, cap_amount={self.cap_amount}, "
                f"eligible_players={self.eligible_players}, active_players={self.active_players}, excluded_players={self.excluded_players},"
                f"bets=[{bets}]")  
        
@dataclass
class BetInfo:
    """Information about a bet being processed."""
    player_id: str
    amount: int          # Amount being added
    is_all_in: bool     # True if player is going all-in
    stack_before: int   # Player's stack before bet
    prev_total: int     # Previous total contributed
    new_total: int      # New total contribution

@dataclass
class RoundPots:
    main_pot: ActivePotNew
    side_pots: List[ActivePotNew]
    round_number: int
    round_total: int = 0
    round_bets: Dict[str, Dict[str, int]] = field(default_factory=lambda: {})

class Pot:
    """Manages poker pot structure including main pot and side pots."""
    
    def __init__(self):
        """Initialize empty pot structure."""
        self.current_round = 1
        self.round_pots: List[RoundPots] = []
        self.total_bets: Dict[str, int] = {}  # Track total contributed by each player
        self.is_all_in: Dict[str, bool] = {}  # Track all-in status
        
        # Create initial round
        self._create_new_round()

    def _create_new_round(self):
        """Create pots for a new betting round."""
        last_round = self.round_pots[-1] if self.round_pots else None
        
        # If there are previous pots, carry them forward
        if last_round:
            new_round = RoundPots(
                main_pot=last_round.main_pot,  # Keep existing pots
                side_pots=last_round.side_pots,
                round_number=self.current_round,
                round_total=0  # New round starts with 0 total
            )
            
            # Update active players for new round
            new_round.main_pot.active_players = {
                p for p in last_round.main_pot.active_players 
                if not self.is_all_in[p]
            }
            new_round.main_pot.eligible_players = new_round.main_pot.active_players.copy()
            
        else:
            # First round - create new empty pots
            new_round = RoundPots(
                main_pot=ActivePotNew(
                    amount=0,
                    current_bet=0,
                    eligible_players=set(),
                    active_players=set(),
                    excluded_players=set(),
                    player_bets={},
                    main_pot=True
                ),
                side_pots=[],
                round_number=self.current_round,
                round_total=0
            )
        
        self.round_pots.append(new_round)

    def end_betting_round(self):
        """End current betting round and prepare for next."""
        current = self.round_pots[-1]
        
        # Calculate total just for this round's betting
        round_bets = current.round_bets
        logger.debug(f"\nCalculating round total:")
        logger.debug(f"  Round bets: {round_bets}")
        
        # Main pot totals
        main_pot_total = sum(amount for amount in round_bets.get('main_pot', {}).values())
        logger.debug(f"  Main pot betting total: {main_pot_total}")
        logger.debug(f"    Bets: {round_bets.get('main_pot', {})}")
        
        # Side pot totals
        side_pots_total = 0
        for i in range(len(current.side_pots)):
            pot_id = f'side_pot_{i}'
            pot_total = sum(amount for amount in round_bets.get(pot_id, {}).values())
            side_pots_total += pot_total
            logger.debug(f"  Side pot {i+1} betting total: {pot_total}")
            logger.debug(f"    Bets: {round_bets.get(pot_id, {})}")
        
        logger.debug(f"  Side pots combined total: {side_pots_total}")
        
        # Set round total
        current.round_total = main_pot_total + side_pots_total
        logger.debug(f"  Final round total: {current.round_total}")
        
        # Log current state before new round
        logger.debug("\nPot state at end of round:")
        logger.debug(f"  Main pot: {current.main_pot}")
        for i, pot in enumerate(current.side_pots):
            logger.debug(f"  Side pot {i+1}: {pot}")
        
        # Start new round
        self.current_round += 1
        self._create_new_round()
        logger.debug(f"\nStarting round {self.current_round}")
        
    @property 
    def total(self):
        """Total amount across all rounds and pots."""
        return sum(round_pots.round_total for round_pots in self.round_pots)
    
    @property
    def active_players(self) -> Set[str]:
        """Get players who can still bet."""
        current = self.round_pots[-1]
        return current.main_pot.active_players    

    def _contribute_to_pot(self, pot: ActivePotNew, bet: BetInfo, amount: int) -> None:
        if amount <= 0 or (pot.closed and pot.capped):
            return
        logger.debug(f"Contributing to {pot.name()}:")
        logger.debug(f"  Before: {pot}")
        logger.debug(f"    Player {bet.player_id} contributing {amount}")
        # Update player's total contribution
        pot.player_bets[bet.player_id] = pot.player_bets.get(bet.player_id, 0) + amount
        # Recalculate pot amount
        pot.amount = sum(pot.player_bets.values())
        # Update player sets
        if bet.player_id not in pot.excluded_players:
            pot.eligible_players.add(bet.player_id)
            if bet.is_all_in:
                pot.active_players.discard(bet.player_id)
            else:
                pot.active_players.add(bet.player_id)
        # Track contribution in round_bets
        current = self.round_pots[-1]
        pot_id = 'main_pot' if pot.main_pot else f'side_pot_{pot.order}'
        if pot_id not in current.round_bets:
            current.round_bets[pot_id] = {}
        current.round_bets[pot_id][bet.player_id] = amount
        logger.debug(f"  After: {pot}")
        logger.debug(f"  Round bets for {pot_id}: {current.round_bets[pot_id]}")

    def _handle_bet_to_capped_pot(self, pot: ActivePotNew, bet: BetInfo, remaining_amount: int) -> int:
        """Handle adding a bet to a capped pot."""

        # If pot is closed and capped, all money goes to side pots
        if pot.closed and pot.capped:
            return remaining_amount
            
        # If pot is closed but not capped, can still accept bets
             
        player_current = pot.player_bets.get(bet.player_id, 0)

        will_have = player_current + remaining_amount
        
        logger.debug(f"    Contribution analysis:")
        logger.debug(f"      Already in pot: {player_current}")
        logger.debug(f"      Adding now: {remaining_amount}")
        logger.debug(f"      Will have total: {will_have}")
        logger.debug(f"      Need to match: {pot.cap_amount}")  # Updated to pot.cap_amount for clarity
        
        if will_have >= pot.cap_amount:  # Changed from remaining_amount >= pot.current_bet
            logger.debug(f"    Will exceed cap")
            # Contribute only what's needed to reach cap
            can_add = max(0, pot.cap_amount - player_current)  # In case already at/over cap
            if can_add > 0:
                logger.debug(f"         contributing can_add of {can_add}")
                self._contribute_to_pot(pot, bet, can_add)
            logger.debug(f"      Returning: {remaining_amount - can_add}")
            return remaining_amount - can_add
                
        if will_have < pot.cap_amount:  # 100 < 300
            logger.debug("    Cannot meet cap - restructuring")
            # Add P2’s bet to the pot
            pot.player_bets[bet.player_id] = will_have
            pot.eligible_players.add(bet.player_id)
            pot.amount = sum(pot.player_bets.values())  # Temporary update: 300 + 100 = 400
            # Restructure with target_amount = will_have
            side_pot = self._restructure_pot(pot, will_have)
            if side_pot:  # Only append if a side pot is created
                if bet.is_all_in:
                    side_pot.capped = True
                    side_pot.cap_amount = side_pot.amount  # Total excess, e.g., 50      
                self.round_pots[-1].side_pots.append(side_pot)
            if bet.is_all_in:
                pot.active_players.discard(bet.player_id)
        return 0

    def _distribute_excess_to_side_pots(self, bet: BetInfo, amount: int) -> int:
        """Distribute excess chips to existing side pots.
        
        Args:
            bet: Information about the bet
            amount: Amount to distribute
            
        Returns:
            Amount still remaining after distribution
        """
        remaining = amount
        current_round = self.round_pots[-1]
        
        for side_pot in current_round.side_pots:
            if remaining <= 0:
                break
                
            # Skip if pot is capped or player excluded
            if (side_pot.capped and side_pot.closed) or bet.player_id in side_pot.excluded_players:
                continue
                
            # If this pot has a current bet, match it
            if side_pot.current_bet > 0:
                amount_to_add = min(remaining, side_pot.current_bet)
                self._contribute_to_pot(side_pot, bet, amount_to_add)
                remaining -= amount_to_add
            else:
                # No current bet, contribute whatever we have
                self._contribute_to_pot(side_pot, bet, remaining)
                remaining = 0
                
        return remaining

    def _create_new_side_pot(self, bet: BetInfo, amount: int) -> None:
        """Create a new side pot with remaining amount.
        
        Args:
            bet: Information about the bet
            amount: Amount to put in new side pot
        """

        if amount <= 0:
            logger.debug(f"  Skipping side pot creation: amount {amount} <= 0")
            return
            
        current_round = self.round_pots[-1]

        logger.debug(f"    Creating new side pot with remaining {amount}")
        side_pot = ActivePotNew(
            amount=0,
            current_bet=amount,  # Set current bet to the amount being bet
            eligible_players={bet.player_id},
            active_players=set() if bet.is_all_in else {bet.player_id},
            excluded_players=set(),
            player_bets={},
            order=len(current_round.side_pots) + 1
        )
        self._contribute_to_pot(side_pot, bet, amount)
        
        if bet.is_all_in:
            side_pot.capped = True
            side_pot.cap_amount = amount
            logger.debug(f"Capped new side pot at {amount}")
            
        current_round.side_pots.append(side_pot)

    def _restructure_pot(self, pot: ActivePotNew, target_amount: int) -> ActivePotNew:
        """
        Restructure the given pot by creating a side pot for contributions exceeding the target amount.
        
        Args:
            pot: The original pot to restructure.
            target_amount: The amount up to which the original pot will be capped.
        
        Returns:
            A new side pot containing the excess contributions.
        """
        side_pot_contributions = {}
        side_pot_eligible = set()
        
        # Adjust player bets and calculate excess
        for player_id, current_amount in list(pot.player_bets.items()):
            if current_amount > target_amount:
                excess_amount = current_amount - target_amount
                side_pot_contributions[player_id] = excess_amount
                side_pot_eligible.add(player_id)
                pot.player_bets[player_id] = target_amount
        
        # Update main pot
        pot.amount = sum(pot.player_bets.values())
        pot.current_bet = target_amount  # Set to the all-in amount
        pot.cap_amount = target_amount
        pot.capped = True  # Mark the pot as capped
    
        # Ensure all contributors are eligible
        pot.eligible_players = set(pot.player_bets.keys())  # Add this line

        # Only create a side pot if there's excess
        if not side_pot_contributions:
            logger.debug(f"    No excess contributions to create a side pot")
            return None        

        logger.debug(f"    Creating new side pot with for excess amount {sum(side_pot_contributions.values())} for bets {side_pot_contributions}")
        # Create side pot for excess
        side_pot = ActivePotNew(
            amount=sum(side_pot_contributions.values()),
            current_bet=max(side_pot_contributions.values()) if side_pot_contributions else 0,
            eligible_players=side_pot_eligible,
            active_players=set(side_pot_eligible),
            excluded_players=set(),
            player_bets=side_pot_contributions,
            order=pot.order + 1,
            main_pot=False,
            capped=False,
            cap_amount=0,
            closed=False
        )
        
        return side_pot

    def add_bet(self, player_id: str, total_amount: int, is_all_in: bool, stack_before: int) -> None:
        """Add a bet to the pot structure, creating side pots as needed.
        
        Args:
            player_id: ID of betting player
            total_amount: Total amount player will have invested after this action.
                        For example:
                        - If P1 opens for 100: total_amount=100
                        - If P2 wants to call P1: total_amount=100
                        - If P2 wants to raise to 300: total_amount=300
                        - If P1 (who bet 100) wants to call P2's raise: total_amount=300
            is_all_in: Whether this bet puts the player all-in
            stack_before: Player's chip stack before this bet
        """
        # Get current round's pots
        current = self.round_pots[-1]
        
        # If there are no active players yet (start of round), or if this player hasn't acted yet,
        # they should be allowed to bet
        if not current.main_pot.active_players or player_id not in current.main_pot.eligible_players:
            current.main_pot.active_players.add(player_id)
        elif player_id not in current.main_pot.active_players:
            raise ValueError(f"Player {player_id} is not active in current round")
                
        # Calculate amount being added
        prev_total = self.total_bets.get(player_id, 0)  # Get player's previous contribution
        amount_to_add = total_amount - prev_total  # Calculate incremental amount

        if total_amount < prev_total:
            raise ValueError(f"Total amount {total_amount} cannot be less than previous total {prev_total} for player {player_id}")        
        
        bet = BetInfo(
            player_id=player_id,
            amount=amount_to_add,
            is_all_in=is_all_in,
            stack_before=stack_before,
            prev_total=self.total_bets.get(player_id, 0),
            new_total=total_amount
        )
        
        logger.debug(f"\nProcessing new bet:")
        logger.debug(f"  Player: {player_id}")
        logger.debug(f"  Total amount: {total_amount}")
        logger.debug(f"  Amount to add: {amount_to_add}")
        logger.debug(f"  All-in: {is_all_in}")
        logger.debug(f"  Previous total: {prev_total}")
        logger.debug(f"Current pot state:")
        logger.debug(f"  Main pot: {current.main_pot}")
        for pot in current.side_pots:
            logger.debug(f"  {pot}")
        
        remaining_amount = amount_to_add
        processed_pots = []  # Track which pots we've handled
        
        # First handle any capped pots
        pots_to_check = [current.main_pot] + current.side_pots
        if any(p.capped or p.closed for p in pots_to_check):
            logger.debug("\nProcessing capped/closed pots:")
            for pot in pots_to_check:
                if not (pot.capped or pot.closed):
                    continue
                    
                logger.debug(f"  Examining {pot.name()}:")
                logger.debug(f"    Remaining amount: {remaining_amount}")

                if remaining_amount <= 0:
                    logger.debug("    No remaining amount to process")
                    break
                    
                if player_id in pot.excluded_players:
                    logger.debug(f"    Player {player_id} is excluded from this pot")
                    continue
                
                remaining_amount = self._handle_bet_to_capped_pot(pot, bet, remaining_amount)
                logger.debug(f"  After _handle_bet_to_capped_pot")
                logger.debug(f"    Remaining amount: {remaining_amount}")
                processed_pots.append(pot)
                
                if remaining_amount == 0:
                    break
                    
        # Handle uncapped pots
        if remaining_amount > 0:
            logger.debug(f"\nProcessing uncapped pots with remaining amount {remaining_amount}:")
            for pot in [p for p in [current.main_pot] + current.side_pots if p not in processed_pots]:
                logger.debug(f"  Examining {pot.name()}:")
                if remaining_amount <= 0:
                    logger.debug("    No remaining amount to process")
                    break
                if player_id in pot.excluded_players:
                    logger.debug(f"    Player {player_id} is excluded from this pot")
                    continue
                logger.debug(f"    Adding bet of {remaining_amount} to pot")
                self._contribute_to_pot(pot, bet, remaining_amount)
                remaining_amount = 0
                player_total = pot.player_bets.get(bet.player_id, 0)
                if is_all_in and pot.current_bet > 0 and player_total < pot.current_bet:
                    logger.debug(f"    Player is all-in and cannot meet current bet of {pot.current_bet}")
                    logger.debug(f"    Player's total contribution is {player_total}")
                    logger.debug(f"    Restructuring pot with target_amount={player_total}")
                    side_pot = self._restructure_pot(pot, player_total)
                    if side_pot:  # Only append if a side pot is created
                        current.side_pots.append(side_pot)
                elif player_total > pot.current_bet:
                    pot.current_bet = player_total
                    logger.debug(f"    Updated current bet to {player_total}")
                if is_all_in:
                    pot.capped = True
                    pot.cap_amount = player_total
                break
            # Ensure no side pot is created if remaining_amount is 0
            if remaining_amount > 0:
                logger.debug(f"  Remaining amount after side pots: {remaining_amount}")
                self._create_new_side_pot(bet, remaining_amount)
            else:
                logger.debug("  No remaining amount to create new side pot")
        
        # Update player tracking
        self.total_bets[player_id] = total_amount
        self.is_all_in[player_id] = is_all_in
        
        logger.debug(f"\nFinal pot state after bet:")
        logger.debug(f"  Total: {self.total}")
        logger.debug(f"  Main pot: {current.main_pot}")
        for pot in current.side_pots:
            logger.debug(f"  {pot}")