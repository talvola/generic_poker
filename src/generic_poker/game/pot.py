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
        
    @property
    def total(self) -> int:
        """Total amount in all pots."""
        return self.main_pot + sum(pot.amount for pot in self.side_pots)
        
    def add_bet(self, player_id: str, amount: int, is_all_in: bool = False) -> None:
        """
        Add a bet to the pot.
        
        Args:
            player_id: ID of betting player
            amount: Amount being bet
            is_all_in: Whether player is going all-in with this bet
        """
        self.main_pot += amount
        self.total_bets[player_id] = self.total_bets.get(player_id, 0) + amount
        
        if is_all_in:
            self._create_side_pot(player_id)
            
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
            
    def _create_side_pot(self, all_in_player_id: str) -> None:
        """
        Create a side pot when a player is all-in.
        
        Args:
            all_in_player_id: ID of player who went all-in
        """
        all_in_amount = self.total_bets[all_in_player_id]
        
        # Find players who have bet more
        excess_players = {
            pid: amt - all_in_amount
            for pid, amt in self.total_bets.items()
            if amt > all_in_amount
        }
        
        if excess_players:
            # Create side pot for excess amounts
            side_pot = SidePot(
                amount=sum(excess_players.values()),
                eligible_players=set(excess_players.keys())
            )
            self.side_pots.append(side_pot)
            
            # Reduce main pot
            self.main_pot -= side_pot.amount
            
    def clear(self) -> None:
        """Reset pot to empty state."""
        self.main_pot = 0
        self.side_pots.clear()
        self.total_bets.clear()