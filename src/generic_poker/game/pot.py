"""Pot management and distribution."""
from dataclasses import dataclass
from typing import List, Set, Dict, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class PotBet:
    """Tracks a single bet in a pot."""
    player_id: str
    amount: int          # Amount contributed to this specific pot

    def __str__(self):
        return f"{self.player_id}:{self.amount}"

@dataclass
class ActivePotNew:
    """Represents a pot (main or side) that can receive bets."""
    amount: int                # Total amount in this pot
    current_bet: int          # Current bet that must be called
    eligible_players: Set[str] # Players who can win this pot
    active_players: Set[str]   # Players who can still bet in this pot
    excluded_players: Set[str] # Players who cannot participate (all-in for less)
    player_bets: List[PotBet]  # Individual bets in this pot
    main_pot: bool = False     # True if this is the main pot
    capped: bool = False      # True if pot has reached maximum size
    cap_amount: int = 0       # Maximum bet allowed if capped
    order: int = 0            # Order of creation (for side pots)

    def name(self) -> str:
        """Return descriptive name of pot."""
        return "Main Pot" if self.main_pot else f"Side Pot {self.order}"
    
    def __str__(self):
        bets = ", ".join(str(bet) for bet in self.player_bets)
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
     
class Pot:
    """Manages poker pot structure including main pot and side pots."""
    
    def __init__(self):
        """Initialize empty pot structure."""
        self.main_pot = ActivePotNew(
            amount=0,
            current_bet=0,
            eligible_players=set(),
            active_players=set(),
            excluded_players=set(),
            player_bets=[],
            main_pot=True
        )
        self.side_pots: List[ActivePotNew] = []
        self.total_bets: Dict[str, int] = {}  # Track total contributed by each player
        self.is_all_in: Dict[str, bool] = {}  # Track all-in status
        
    @property
    def total(self) -> int:
        """Total amount across all pots."""
        return self.main_pot.amount + sum(pot.amount for pot in self.side_pots)

    def _contribute_to_pot(self, pot: ActivePotNew, bet: BetInfo, amount: int) -> None:
        """Add a contribution to a specific pot."""
        if amount <= 0:
            return
            
        logger.debug(f"Contributing to {pot.name()}:")
        logger.debug(f"  Before: {pot}")
        logger.debug(f"    Player {bet.player_id} contributing {amount}")
        
        # Calculate pot amount without this player's previous bets
        other_bets = [pb for pb in pot.player_bets if pb.player_id != bet.player_id]
        base_amount = sum(pb.amount for pb in other_bets)
        logger.debug(f"      Other bets: {other_bets}")
        logger.debug(f"      Base amount: {base_amount}")
        
        # Calculate previous amount this player had in pot
        prev_amount = sum(pb.amount for pb in pot.player_bets 
                        if pb.player_id == bet.player_id)
        logger.debug(f"      Previous amount: {prev_amount}")
        
        # If player has contributed before, need to add new amount to previous
        if bet.prev_total > 0:  # This is a call/raise - add to previous
            contribution = prev_amount + amount
        else:  # First contribution - use amount as is
            contribution = amount
            
        logger.debug(f"      New contribution: {contribution}")
        
        # Add to pot
        pot.amount = base_amount + contribution
        pot.player_bets = other_bets
        
        # Only add to eligible/active players if not excluded
        if bet.player_id not in pot.excluded_players:
            pot.eligible_players.add(bet.player_id)
            if not bet.is_all_in:
                pot.active_players.add(bet.player_id)
                
        pot.player_bets.append(PotBet(bet.player_id, contribution))
        
        logger.debug(f"  After: {pot}")

    def _handle_bet_to_capped_pot(self, pot: ActivePotNew, bet: BetInfo, remaining_amount: int) -> int:
        """Handle adding a bet to a capped pot.
        
        Args:
            pot: The pot being bet into
            bet: Information about the bet
            remaining_amount: Amount still to be added
            
        Returns:
            Amount still remaining after contribution
        """
        player_current = sum(pb.amount for pb in pot.player_bets 
                            if pb.player_id == bet.player_id)
        will_have = player_current + remaining_amount
        
        logger.debug(f"    Contribution analysis:")
        logger.debug(f"      Already in pot: {player_current}")
        logger.debug(f"      Adding now: {remaining_amount}")
        logger.debug(f"      Will have total: {will_have}")
        logger.debug(f"      Need to match: {pot.current_bet}")
        
        if remaining_amount >= pot.current_bet:
            logger.debug(f"    Bet matches or exceeds cap")
            # Contribute amount needed to match current bet
            matched_amount = min(remaining_amount, pot.current_bet)  # Changed to current_bet
            self._contribute_to_pot(pot, bet, matched_amount)
            return remaining_amount - matched_amount
                
        logger.debug(f"    Cannot meet current bet - restructuring")
        self._restructure_pot(pot, bet, remaining_amount)
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
        
        for side_pot in self.side_pots:
            if remaining <= 0:
                break
                
            if side_pot.capped or bet.player_id in side_pot.excluded_players:
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
        logger.debug(f"    Creating new side pot with remaining {amount}")
        side_pot = ActivePotNew(
            amount=0,
            current_bet=amount,  # Set current bet to the amount being bet
            eligible_players={bet.player_id},
            active_players=set() if bet.is_all_in else {bet.player_id},
            excluded_players=set(),
            player_bets=[],
            order=len(self.side_pots) + 1
        )
        self._contribute_to_pot(side_pot, bet, amount)
        
        if bet.is_all_in:
            side_pot.capped = True
            side_pot.cap_amount = amount
            logger.debug(f"Capped new side pot at {amount}")
            
        self.side_pots.append(side_pot)

    def _restructure_pot(self, pot: ActivePotNew, bet: BetInfo, available: int) -> None:
        """
        Restructure a pot when a player can't meet the current bet.
        Creates a side pot for the excess amount.
        """
        logger.debug(f"\nRestructuring {pot.name()} for short call:")
        logger.debug(f"  Current state: {pot}")
        logger.debug(f"  Player {bet.player_id} can contribute {available} more")

        # Calculate target amount for main pot
        target_amount = bet.prev_total + available
        logger.debug(f"  Player {bet.player_id} will have total of {target_amount} after bet")

        # Track excess amounts and players
        side_pot_bets = []
        side_pot_eligible = set()

        logger.debug(f"  Moving excess amounts to side pot:")
        # Convert existing player bets to target_amount
        for pb in pot.player_bets:
            if pb.amount > target_amount:
                excess_amount = pb.amount - target_amount
                logger.debug(f"    Moving {excess_amount} from {pb.player_id} to side pot")
                side_pot_bets.append(PotBet(pb.player_id, excess_amount))
                side_pot_eligible.add(pb.player_id)
                # Reduce amount in original pot
                pb.amount = target_amount
                logger.debug(f"    Reduced {pb.player_id}'s bet in main pot to {target_amount}")

        # Update calling player's bet to target_amount
        # First remove their old bet if any
        pot.player_bets = [pb for pb in pot.player_bets if pb.player_id != bet.player_id]
        # Then add their new total bet
        pot.player_bets.append(PotBet(bet.player_id, target_amount))
        # Add player to eligible players for this pot
        pot.eligible_players.add(bet.player_id)
        logger.debug(f"    Set {bet.player_id}'s bet in main pot to {target_amount}")

        # Update original pot
        pot.amount = sum(pb.amount for pb in pot.player_bets)  # Sum actual bets
        pot.current_bet = target_amount
        pot.cap_amount = target_amount
        pot.capped = True

        # Create side pot if there were excess amounts
        if side_pot_bets:
            side_pot = ActivePotNew(
                amount=0,
                current_bet=max(pb.amount for pb in side_pot_bets),  # Biggest excess amount
                eligible_players=side_pot_eligible,  # Only players with excess
                active_players=set(side_pot_eligible),  # Start all excess players active
                excluded_players={bet.player_id},  # Exclude calling player who couldn't match
                player_bets=[],
                order=len(self.side_pots) + 1
            )
            
            # Add the actual excess bets
            for excess_bet in side_pot_bets:
                self._contribute_to_pot(side_pot, BetInfo(
                    player_id=excess_bet.player_id,
                    amount=excess_bet.amount,
                    is_all_in=self.is_all_in.get(excess_bet.player_id, False),
                    stack_before=0,  # Not relevant for excess transfers
                    prev_total=0,  # Not relevant for excess transfers
                    new_total=excess_bet.amount
                ), excess_bet.amount)
                
            # Check if side pot should be capped
            for player_id in side_pot.eligible_players:
                all_in = self.is_all_in.get(player_id, False)
                logger.debug(f"    Player {player_id} all-in status: {all_in}")
                if all_in:
                    side_pot.capped = True
                    side_pot.cap_amount = side_pot.amount / len(side_pot.eligible_players)
                    logger.debug(f"    Capping side pot due to {player_id} being all-in")
                    break
                    
            self.side_pots.append(side_pot)
            logger.debug(f"  After restructuring:")
            logger.debug(f"    Main pot: {pot}")
            logger.debug(f"    New side pot: {side_pot}")
        else:
            logger.debug(f"  After restructuring:")
            logger.debug(f"    Main pot: {pot}")

    def add_bet(self, player_id: str, total_amount: int, is_all_in: bool, stack_before: int) -> None:
        """Add a bet to the pot structure, creating side pots as needed."""
        # Calculate amount being added
        prev_total = self.total_bets.get(player_id, 0)
        amount_to_add = total_amount - prev_total
        
        bet = BetInfo(
            player_id=player_id,
            amount=amount_to_add,  # Convert total to incremental for internal use
            is_all_in=is_all_in,
            stack_before=stack_before,
            prev_total=prev_total,
            new_total=total_amount
        )
        
        logger.debug(f"\nProcessing new bet:")
        logger.debug(f"  Player: {player_id}")
        logger.debug(f"  Total amount: {total_amount}")
        logger.debug(f"  Amount to add: {amount_to_add}")
        logger.debug(f"  All-in: {is_all_in}")
        logger.debug(f"  Previous total: {prev_total}")
        logger.debug(f"Current pot state:")
        logger.debug(f"  Main pot: {self.main_pot}")
        for pot in self.side_pots:
            logger.debug(f"  {pot}")
        
        remaining_amount = amount_to_add
        processed_pots = []  # Track which pots we've handled
        
        # First handle any capped pots
        if any(p.capped for p in [self.main_pot] + self.side_pots):
            logger.debug("\nProcessing capped pots:")
            for pot in [self.main_pot] + self.side_pots:
                if not pot.capped:
                    continue
                    
                logger.debug(f"  Examining {pot.name()}:")
                if remaining_amount <= 0:
                    logger.debug("    No remaining amount to process")
                    break
                    
                if player_id in pot.excluded_players:
                    logger.debug(f"    Player {player_id} is excluded from this pot")
                    continue
                
                remaining_amount = self._handle_bet_to_capped_pot(pot, bet, remaining_amount)
                processed_pots.append(pot)
                
                if remaining_amount == 0:
                    break
                    
        # Handle uncapped pots
        if remaining_amount > 0:
            logger.debug(f"\nProcessing uncapped pots with remaining amount {remaining_amount}:")
            for pot in [p for p in [self.main_pot] + self.side_pots 
                    if p not in processed_pots]:
                    
                logger.debug(f"  Examining {pot.name()}:")
                if remaining_amount <= 0:
                    logger.debug("    No remaining amount to process")
                    break
                    
                if player_id in pot.excluded_players:
                    logger.debug(f"    Player {player_id} is excluded from this pot")
                    continue
                    
                # Calculate total amount player will have after this addition
                player_current = sum(pb.amount for pb in pot.player_bets 
                                if pb.player_id == bet.player_id)
                total_after = player_current + remaining_amount
                
                # Restructure only if player can't meet the current bet even after adding
                if pot.current_bet > 0 and total_after < pot.current_bet:
                    logger.debug(f"    Player cannot meet current bet of {pot.current_bet}")
                    logger.debug(f"    Player has {player_current} and adding {remaining_amount}")
                    logger.debug(f"    Total {total_after} will be less than current bet")
                    logger.debug(f"    Restructuring pot...")
                    self._restructure_pot(pot, bet, remaining_amount)
                    remaining_amount = 0
                    break
                    
                # Otherwise add to pot normally
                logger.debug(f"    Adding normal bet of {remaining_amount}")
                self._contribute_to_pot(pot, bet, remaining_amount)
                
                # Update pot state
                if remaining_amount > pot.current_bet:
                    pot.current_bet = remaining_amount
                    logger.debug(f"    Updated current bet to {remaining_amount}")
                
                if is_all_in:
                    pot.capped = True
                    pot.cap_amount = total_amount
                    logger.debug(f"    Capped pot at {total_amount} due to all-in")
                    
                remaining_amount = 0
                
            # If we still have remaining amount, distribute to side pots
            if remaining_amount > 0:
                remaining_amount = self._distribute_excess_to_side_pots(bet, remaining_amount)
        
            # If still have remainder, create new side pot
            if remaining_amount > 0:
                self._create_new_side_pot(bet, remaining_amount)
        
        # Update player tracking
        self.total_bets[player_id] = total_amount
        self.is_all_in[player_id] = is_all_in
        
        logger.debug(f"\nFinal pot state after bet:")
        logger.debug(f"  Total: {self.total}")
        logger.debug(f"  Main pot: {self.main_pot}")
        for pot in self.side_pots:
            logger.debug(f"  {pot}")