"""Pot management and distribution."""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from generic_poker.game.table import Player

logger = logging.getLogger(__name__)


@dataclass
class SidePot:
    """Represents a side pot when players are all-in."""
    amount: int
    eligible_players: Set[str]  # Set of player IDs eligible for this pot

@dataclass
class BettingLevel:
    """Represents a level of betting between all-in amounts."""
    start_amount: int
    end_amount: int
    eligible_players: Set[str]
    contribution_per_player: int

    @property
    def total_amount(self) -> int:
        """Calculate total amount in this level."""
        return self.contribution_per_player * len(self.eligible_players)
    
@dataclass
class BetHistoryEntry:
    """Records a betting action."""
    player_id: str
    amount: int
    cumulative_amount: int
    is_all_in: bool

    def __str__(self):
        return (f"{self.player_id}: bet {self.amount} "
                f"(total {self.cumulative_amount})"
                f"{' all-in' if self.is_all_in else ''}")

class Pot:
    """
    Manages poker pot(s) and their distribution.
    
    Handles:
    - main_amount pot tracking
    - Side pots for all-in situations
    - Split pot distribution
    - Remain_amountders from split pots
    """
    
    def __init__(self):
        """Initialize empty pot."""
        self.main_pot: int = 0
        self.side_pots: List[SidePot] = []
        self.total_bets: Dict[str, int] = {}  # player_id -> total contributed
        self.is_all_in: Dict[str, bool] = {}  # Track all-in status
        self.bet_history: List[BetHistoryEntry] = []  # Track betting sequence

    def _log_state(self, prefix: str = ""):
        """Debug helper to log current state."""
        logger.debug(f"\n=== {prefix} Pot State ===")
        logger.debug(f"Main pot: {self.main_pot}")
        logger.debug(f"Total bets: {self.total_bets}")
        logger.debug(f"All-in status: {self.is_all_in}")
        logger.debug("Betting history:")
        for entry in self.bet_history:
            logger.debug(f"  {entry}")
        logger.debug("Side pots:")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"  Pot {i}: amount={pot.amount}, eligible={pot.eligible_players}")
        logger.debug("=====================\n")

    def _find_all_in_levels(self) -> List[int]:
        """Find all distinct all-in amounts based on betting history."""
        logger.debug("\nFinding all-in levels from history:")
        levels = []
        seen = set()
        
        for entry in self.bet_history:
            if entry.is_all_in and entry.cumulative_amount not in seen:
                levels.append(entry.cumulative_amount)
                seen.add(entry.cumulative_amount)
                logger.debug(f"  Found level {entry.cumulative_amount} from {entry}")
                
        levels.sort()
        logger.debug(f"Final levels (sorted): {levels}")
        return levels
    
    def _create_side_pots_for_levels(self, levels: List[BettingLevel]) -> List[SidePot]:
        """Create side pots for each betting level."""
        logger.debug("Creating side pots for levels")
        pots: List[SidePot] = []
        
        for level in levels:
            pot = SidePot(
                amount=level.total_amount,
                eligible_players=level.eligible_players
            )
            pots.append(pot)
            logger.debug(f"Created pot: amount={pot.amount}, eligible={pot.eligible_players}")
            
        return pots

    def _update_main_pot(self) -> None:
        """Update main pot based on minimum all-in amount and current contributions."""
        logger.debug("\n=== Updating main pot ===")
        logger.debug(f"Total bets: {self.total_bets}")
        logger.debug(f"All-in status: {self.is_all_in}")
        
        if not self.is_all_in:  # No all-ins yet
            logger.debug("No all-ins, skipping update")
            return
                
        # Find minimum all-in amount
        min_all_in = min(
            self.total_bets[pid]
            for pid in self.total_bets
            if self.is_all_in.get(pid, False)
        )
        logger.debug(f"Minimum all-in amount: {min_all_in}")
        
        # Calculate each player's contribution
        contributions = {
            pid: min(bet, min_all_in)
            for pid, bet in self.total_bets.items()
        }
        logger.debug(f"Individual contributions: {contributions}")
        
        # Sum contributions
        main_pot = sum(contributions.values())
        logger.debug(f"Total main pot: {main_pot}")
        
        self.main_pot = main_pot
        logger.debug("=== Main pot update complete ===\n")

    def _find_betting_levels(self, current_amount: int) -> List[BettingLevel]:
        """
        Find all betting levels above the current amount.
        """
        logger.debug(f"\nFinding betting levels above {current_amount}")
        logger.debug("Current betting history:")
        for entry in self.bet_history:
            logger.debug(f"  {entry}")
        
        # Get maximum bet to understand current betting round level
        max_bet = max(entry.cumulative_amount for entry in self.bet_history)
        logger.debug(f"Maximum bet in current round: {max_bet}")
        
        # Start collecting level amounts
        level_amounts = set()
        
        # Add all-in amounts first
        all_in_amounts = sorted(
            self.total_bets[pid]
            for pid, is_all_in in self.is_all_in.items()
            if is_all_in
        )
        
        if all_in_amounts:
            min_all_in = all_in_amounts[0]
            logger.debug(f"Minimum all-in amount: {min_all_in}")
            
            # If there's an all-in below max bet, we need levels at both points
            if min_all_in < max_bet:
                level_amounts.add(min_all_in)
                level_amounts.add(max_bet)
                logger.debug(f"Adding split levels for below-bet all-in: {min_all_in} and {max_bet}")
            
            # Add any other all-in amounts
            level_amounts.update(all_in_amounts[1:])
        
        # Add matched bet amounts
        for i, entry in enumerate(self.bet_history):
            amount = entry.cumulative_amount
            if amount > current_amount:
                # Check if this amount was matched or is highest bet
                if amount == max_bet or any(
                    e.cumulative_amount >= amount 
                    for e in self.bet_history[i+1:]
                ):
                    level_amounts.add(amount)
                    logger.debug(f"Adding matched bet level: {amount}")
        
        # Sort levels
        level_amounts = sorted(level_amounts)
        logger.debug(f"Final level amounts: {level_amounts}")
        
        # Create levels
        levels = []
        start_amount = current_amount
        
        for end_amount in level_amounts:
            if end_amount <= start_amount:
                continue
                
            # Find eligible players for this level
            eligible = set()
            for pid, bet in self.total_bets.items():
                if bet >= end_amount:
                    if bet == end_amount and self.is_all_in.get(pid, False):
                        # Player went all-in exactly at this amount
                        eligible.add(pid)
                    elif bet > end_amount or bet == max_bet:
                        # Player bet more or matched highest bet
                        eligible.add(pid)
            
            if eligible:
                level = BettingLevel(
                    start_amount=start_amount,
                    end_amount=end_amount,
                    eligible_players=eligible,
                    contribution_per_player=end_amount - start_amount
                )
                levels.append(level)
                logger.debug(f"Created level: {start_amount}-{end_amount}")
                logger.debug(f"  Contribution: {end_amount - start_amount}")
                logger.debug(f"  Eligible: {eligible}")
                start_amount = end_amount
        
        return levels

    def _redistribute_pots(self, amount: int) -> None:
        """Redistribute pots at given all-in amount."""
        logger.debug(f"\n=== Redistributing pots at amount {amount} ===")
        
        # Update main pot first based on minimum all-in
        if self.is_all_in:
            min_all_in = min(self.total_bets[pid] for pid in self.total_bets if self.is_all_in.get(pid, False))
            self.main_pot = min_all_in * len(self.total_bets)
            logger.debug(f"Set main pot to {self.main_pot} ({min_all_in} × {len(self.total_bets)})")
        
        # Find and create side pots
        levels = self._find_betting_levels(amount)
        if not levels:
            logger.debug("No levels found to redistribute")
            return
            
        # Keep track of existing side pots at other levels
        existing_pots = []
        level_starts = {level.start_amount for level in levels}
        
        for pot in self.side_pots:
            pot_start = min(self.total_bets[pid] for pid in pot.eligible_players) - pot.amount
            if pot_start not in level_starts:
                existing_pots.append(pot)
                logger.debug(f"Preserving existing pot: start={pot_start}, amount={pot.amount}")
                
        # Create new side pots
        new_pots = []
        for level in levels:
            pot = SidePot(
                amount=level.contribution_per_player * len(level.eligible_players),
                eligible_players=level.eligible_players
            )
            new_pots.append(pot)
            logger.debug(f"Created new pot: amount={pot.amount}, eligible={pot.eligible_players}, "
                        f"level={level.start_amount}-{level.end_amount}")
        
        # Merge existing and new pots, maintaining order
        self.side_pots = sorted(existing_pots + new_pots,
                            key=lambda p: min(self.total_bets[pid] for pid in p.eligible_players))
        
        logger.debug("=== Final state after redistribution ===")
        logger.debug(f"Main pot: {self.main_pot}")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"Side pot {i}: amount={pot.amount}, eligible={pot.eligible_players}")
        
    @property
    def total(self) -> int:
        """Total amount in all pots."""
        return self.main_pot + sum(pot.amount for pot in self.side_pots)
        
    def add_bet(self, player_id: str, amount: int, is_all_in: bool = False) -> None:
        """Add a bet to the pot and manage side pots."""
        logger.debug(f"\n>>> Adding bet: player={player_id}, amount={amount}, all_in={is_all_in}")
        self._log_state("Before bet")
        
        # Update pot and bets
        self.main_pot += amount
        cumulative = self.total_bets.get(player_id, 0) + amount
        self.total_bets[player_id] = cumulative
        
        # Record bet in history
        entry = BetHistoryEntry(
            player_id=player_id,
            amount=amount,
            cumulative_amount=cumulative,
            is_all_in=is_all_in
        )
        self.bet_history.append(entry)
        logger.debug(f"Added to history: {entry}")
        
        if is_all_in:
            self.is_all_in[player_id] = True
            logger.debug(f"Marked {player_id} as all-in")
        
        # Get sorted unique all-in amounts to process
        all_in_levels = self._find_all_in_levels()
        logger.debug(f"Found all-in levels to check: {all_in_levels}")
        
        # Process each level
        for level in all_in_levels:
            logger.debug(f"\nProcessing all-in level: {level}")
            self._redistribute_pots(level)
            
        self._log_state("After bet")

    def clear(self) -> None:
        """Reset pot to empty state."""
        self.main_pot = 0
        self.side_pots.clear()
        self.total_bets.clear()
        self.is_all_in.clear()                           
            
    def award_to_winners(
        self,
        winners: List[Player],
        side_pot_index: Optional[int] = None
    ) -> None:
        """
        Award pot to winner(s).
        
        Args:
            winners: List of winning players
            side_pot_index: Optional index of side pot to award
        """
        if not winners:
            logger.error("Cannot award pot - no winners specified")
            return
            
        # Determine pot amount to award
        if side_pot_index is not None:
            if side_pot_index >= len(self.side_pots):
                logger.error(f"Invalid side pot index: {side_pot_index}")
                return
            amount = self.side_pots[side_pot_index].amount
        else:
            amount = self.main_pot
            
        # Award pot
        if len(winners) == 1:
            # Single winner gets whole pot
            winners[0].stack += amount
            logger.info(f"Awarded pot of ${amount} to {winners[0].name}")
        else:
            # Split pot among winners
            self._split_pot(amount, winners)
            
    def _split_pot(self, amount: int, winners: List[Player]) -> None:
        """Split pot amount among winners, handling remainders."""
        amount_per_player = amount // len(winners)
        remainder = amount % len(winners)
        
        for i, winner in enumerate(winners):
            award = amount_per_player
            if i < remainder:  # Distribute remainder one chip at a time
                award += 1
            winner.stack += award
            logger.info(f"Awarded ${award} to {winner.name} from split pot")
            
    def _debug_state(self) -> None:
        """Debug helper to print current pot state."""
        logger.debug("\n=== Current Pot State ===")
        logger.debug(f"Main pot: {self.main_pot}")
        logger.debug(f"Total bets: {self.total_bets}")
        logger.debug(f"All-in status: {self.is_all_in}")
        logger.debug("Side pots:")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"  Pot {i}: amount={pot.amount}, eligible={pot.eligible_players}")
        logger.debug("=====================\n")

    def _debug_betting_levels(self, amount: int) -> None:
        """Debug helper to analyze betting level detection."""
        logger.debug(f"\n=== Analyzing betting levels from {amount} ===")
        logger.debug("Current bets and status:")
        for pid, bet in self.total_bets.items():
            status = "all-in" if self.is_all_in.get(pid, False) else "active"
            logger.debug(f"  {pid}: {bet} ({status})")
            
        logger.debug("\nBetting history:")
        for entry in self.bet_history:
            logger.debug(f"  {entry}")
            
        logger.debug("\nPotential level boundaries:")
        seen = set()
        for entry in self.bet_history:
            if entry.cumulative_amount > amount and entry.cumulative_amount not in seen:
                seen.add(entry.cumulative_amount)
                callers = [e for e in self.bet_history 
                        if e.cumulative_amount >= entry.cumulative_amount]
                logger.debug(f"  Amount {entry.cumulative_amount}:")
                logger.debug(f"    Original bet by: {entry.player_id}")
                logger.debug(f"    Called/exceeded by: {[e.player_id for e in callers]}")
                
        levels = self._find_betting_levels(amount)
        logger.debug("\nDetected levels:")
        for level in levels:
            logger.debug(f"  {level.start_amount}-{level.end_amount}:")
            logger.debug(f"    Contribution: {level.contribution_per_player}")
            logger.debug(f"    Eligible: {level.eligible_players}")
        logger.debug("=== Analysis complete ===\n")        