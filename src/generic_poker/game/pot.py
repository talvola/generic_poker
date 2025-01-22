"""Pot management and distribution."""
import logging
from dataclasses import dataclass
from typing import List, Set, Dict, Optional

logger = logging.getLogger(__name__)

@dataclass
class ActivePot:
    """Represents a pot (main or side) that can still receive bets."""
    amount: int               # Total amount in this pot
    current_bet: int          # Current bet that must be called
    eligible_players: Set[str] # Players who can win this pot
    active_players: Set[str]   # Players who can still bet in this pot
    capped: bool = False      # True if pot has all-in player (can't raise)
    cap_amount: int = 0       # If capped, maximum bet allowed
      
@dataclass
class BetInfo:
    """Information about a bet being processed."""
    player_id: str
    amount: int          # Amount being added
    is_all_in: bool      
    stack_before: int
    prev_total: int      # Player's previous total contribution
    new_total: int       # Total after this bet

class Pot:
    def __init__(self):
        self.main_pot = ActivePot(0, 0, set(), set())
        self.side_pots: List[ActivePot] = []
        self.total_bets: Dict[str, int] = {}  
        self.is_all_in: Dict[str, bool] = {}

    def _contribute_to_pot(self, pot: ActivePot, bet: BetInfo, amount: int) -> None:
        """Add a contribution to a specific pot and update its state."""
        pot.amount += amount
        pot.eligible_players.add(bet.player_id)
        if not bet.is_all_in:
            pot.active_players.add(bet.player_id)
        logger.debug(f"Added {amount} to pot (now contains {pot.amount})")

    def _calculate_pot_contribution(self, pot: ActivePot, bet: BetInfo, remaining: int, prev_contribution: int = 0) -> int:
        """Calculate how much of remaining chips should go into this pot."""
        if pot.capped:
            to_call = max(0, pot.cap_amount - prev_contribution)
            contribution = min(remaining, to_call)
            logger.debug(f"Pot is capped - can contribute {contribution} to reach cap of {pot.cap_amount}")
        else:
            contribution = remaining
            logger.debug(f"Pot not capped - can contribute full {contribution}")
        return contribution

    def _create_side_pot(self, amount: int, bet: BetInfo) -> ActivePot:
        """Create a new side pot with the given amount."""
        side_pot = ActivePot(
            amount=amount,
            current_bet=amount,
            eligible_players={bet.player_id},
            active_players=set() if bet.is_all_in else {bet.player_id}
        )
        if bet.is_all_in:
            logger.debug(f"Capping new side pot at {amount} since {bet.player_id} is all-in")
            side_pot.capped = True
            side_pot.cap_amount = amount
        return side_pot

    def _log_pot_state(self, message: str = "After bet:"):
        """Log the current state of all pots."""
        logger.debug(f"\n{message}")
        logger.debug(f"Main pot: ${self.main_pot.amount} (bet: ${self.main_pot.current_bet})")
        logger.debug(f"Main pot eligible: {self.main_pot.eligible_players}")
        debug_cap = f" (max bet ${self.main_pot.cap_amount})" if self.main_pot.capped else ""
        logger.debug(f"Main pot capped: {self.main_pot.capped}{debug_cap}")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"Side pot {i}: ${pot.amount}")
            logger.debug(f"  Eligible: {pot.eligible_players}")
            debug_cap = f" (max bet ${pot.cap_amount})" if pot.capped else ""
            logger.debug(f"  Capped: {pot.capped}{debug_cap}")

    def _validate_pot_state(self) -> None:
        """Validate pot invariants."""
        # Total in all pots should match sum of all bets
        total_in_pots = self.total
        total_bets = sum(self.total_bets.values())
        assert total_in_pots == total_bets, f"Pot total {total_in_pots} doesn't match bet total {total_bets}"
        
        # Check each pot's eligible players
        for player_id in self.total_bets:
            if self.total_bets[player_id] > 0:
                assert any(player_id in pot.eligible_players 
                         for pot in [self.main_pot] + self.side_pots), \
                    f"Player {player_id} has bet but isn't eligible for any pot"
                
    def _handle_all_in_below_current(self, bet: BetInfo) -> bool:
        """Handle case where player goes all-in for less than current bet."""
        max_bet = max(self.total_bets.values(), default=0)
        if not bet.is_all_in or bet.new_total >= max_bet:
            return False
                
        logger.debug(f"Handling all-in below current bet: {bet.new_total} < {max_bet}")
        logger.debug(f"Current total_bets: {self.total_bets}")
        
        # Calculate main pot amount at new all-in level
        main_pot_amount = 0
        # Include the all-in player's contribution first
        main_pot_amount += bet.new_total
        logger.debug(f"Adding {bet.new_total} from {bet.player_id} to main pot (all-in)")
        
        # Track excess amounts for side pot
        excess_amounts = {}
        all_ins_above = set()  # Track all-in bets above this one
        
        # Handle other players' contributions
        for pid, existing_bet in self.total_bets.items():
            if pid != bet.player_id:  # Skip all-in player
                if existing_bet <= bet.new_total:
                    main_pot_amount += existing_bet
                    logger.debug(f"Adding {existing_bet} from {pid} to main pot (under all-in)")
                else:
                    # Add all-in amount to main pot
                    main_pot_amount += bet.new_total
                    logger.debug(f"Adding {bet.new_total} from {pid} to main pot (capped)")
                    # Track excess for side pot
                    excess = existing_bet - bet.new_total
                    excess_amounts[pid] = excess
                    logger.debug(f"Tracking excess {excess} from {pid} for side pot")
                    # Track if this was from an all-in
                    if pid in self.is_all_in:
                        all_ins_above.add(pid)
                        logger.debug(f"Player {pid} was all-in above current")
        
        # Set up main pot
        self.main_pot.amount = main_pot_amount
        self.main_pot.eligible_players.add(bet.player_id)
        self.main_pot.current_bet = bet.new_total
        self.main_pot.capped = True
        self.main_pot.cap_amount = bet.new_total
        logger.debug(f"Set main pot to {main_pot_amount} capped at {bet.new_total}")
        
        # Create single side pot for all excess
        self.side_pots = []
        if excess_amounts:
            side_pot_amount = sum(excess_amounts.values())
            eligible_players = set(excess_amounts.keys())
            
            side_pot = ActivePot(
                amount=side_pot_amount,
                current_bet=max(excess_amounts.values()),
                eligible_players=eligible_players,
                active_players=set()
            )
            
            # Side pot should be capped if all contributors were all-in
            if all(pid in all_ins_above for pid in eligible_players):
                logger.debug(f"Capping side pot as all contributors were all-in")
                side_pot.capped = True
                side_pot.cap_amount = max(excess_amounts.values())
            
            self.side_pots.append(side_pot)
            logger.debug(f"Created side pot with {side_pot_amount} total excess from {eligible_players}")
            if side_pot.capped:
                logger.debug(f"Side pot capped at {side_pot.cap_amount}")
        
        # Update status
        self.is_all_in[bet.player_id] = True
        if bet.player_id in self.main_pot.active_players:
            self.main_pot.active_players.remove(bet.player_id)
        
        logger.debug("\nAfter handling all-in below current:")
        logger.debug(f"Main pot: {self.main_pot.amount} (bet: {self.main_pot.current_bet})")
        logger.debug(f"Main pot eligible players: {self.main_pot.eligible_players}")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"Side pot {i}: {pot.amount} (eligible: {pot.eligible_players})")
            if pot.capped:
                logger.debug(f"  Capped at {pot.cap_amount}")
        
        return True

    def _handle_normal_bet(self, bet: BetInfo) -> None:
        """Handle a regular bet or call."""
        self.main_pot.amount += bet.amount
        self.main_pot.eligible_players.add(bet.player_id)
        if not bet.is_all_in:
            self.main_pot.active_players.add(bet.player_id)
        self.main_pot.current_bet = max(self.main_pot.current_bet, bet.new_total)

    def _handle_bet_above_all_in(self, bet: BetInfo) -> None:
        """
        Handle betting that exceeds an all-in amount.
        Process through each pot, respecting caps from all-ins.
        """
        logger.debug(f"\nHandling bet above all-in: {bet.player_id}, amount=${bet.amount}")
        logger.debug(f"Player's previous contribution: ${bet.prev_total}")
        logger.debug(f"New total contribution will be: ${bet.new_total}")
        
        remaining = bet.amount
        current_pot_index = -1  # -1 for main pot, 0+ for side pots
        
        while remaining > 0:
            if current_pot_index == -1:
                current_pot = self.main_pot
                pot_name = "main"
            else:
                if current_pot_index >= len(self.side_pots):
                    # Need new side pot
                    new_pot = ActivePot(
                        amount=0,
                        current_bet=0,
                        eligible_players=set(),
                        active_players=set(),
                        capped=False,
                        cap_amount=0
                    )
                    self.side_pots.append(new_pot)
                    logger.debug(f"Created new side pot {current_pot_index}")
                current_pot = self.side_pots[current_pot_index]
                pot_name = f"side pot {current_pot_index}"
                
            logger.debug(f"\nProcessing {pot_name}")
            logger.debug(f"  Current state: ${current_pot.amount}, bet level: ${current_pot.current_bet}")
            logger.debug(f"  Eligible players: {current_pot.eligible_players}")
            logger.debug(f"  Active players: {current_pot.active_players}")
            if current_pot.capped:
                logger.debug(f"  Pot is capped at ${current_pot.cap_amount} per player")
                    
            # How much to add to this pot?
            if current_pot.capped:
                # Can only add up to cap amount
                already_in_this_pot = 0
                if current_pot_index == -1:
                    already_in_this_pot = bet.prev_total
                else:
                    # For side pots, need to account for amounts in previous pots
                    prev_caps = self.main_pot.cap_amount if self.main_pot.capped else 0
                    for i in range(current_pot_index):
                        if self.side_pots[i].capped:
                            prev_caps += self.side_pots[i].cap_amount
                    already_in_this_pot = max(0, bet.prev_total - prev_caps)
                
                to_call = max(0, current_pot.cap_amount - already_in_this_pot)
                contribution = min(remaining, to_call)
                logger.debug(f"  Pot is capped - player already has ${already_in_this_pot} in this pot")
                logger.debug(f"  Can only add ${contribution} to reach cap of ${current_pot.cap_amount}")
            else:
                # Can add whatever we want
                contribution = remaining
                logger.debug(f"  Pot not capped - adding entire remaining amount ${contribution}")
                
            if contribution > 0:
                current_pot.amount += contribution
                current_pot.eligible_players.add(bet.player_id)
                if not bet.is_all_in:
                    current_pot.active_players.add(bet.player_id)
                remaining -= contribution

                # Update pot status after contribution
                if bet.is_all_in:
                    # Check if this makes all eligible players all-in
                    all_players_all_in = True
                    for eligible_player in current_pot.eligible_players:
                        if eligible_player not in self.is_all_in and eligible_player != bet.player_id:
                            all_players_all_in = False
                            break
                    
                    if all_players_all_in:
                        logger.debug("  All eligible players now all-in, capping pot")
                        current_pot.capped = True
                        current_pot.cap_amount = current_pot.current_bet
                
                logger.debug(f"  Pot now contains ${current_pot.amount}")
                logger.debug(f"  ${remaining} of bet remaining to process")
                        
            # Move to next pot if needed
            if remaining > 0:
                current_pot_index += 1
                logger.debug(f"Moving to next pot with ${remaining} remaining")
                    
        logger.debug("\nAfter handling bet:")
        logger.debug(f"Main pot: ${self.main_pot.amount} (capped: {self.main_pot.capped})")
        if self.main_pot.capped:
            logger.debug(f"  Main pot cap: ${self.main_pot.cap_amount} per player")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"Side pot {i}: ${pot.amount}")
            logger.debug(f"  Eligible players: {pot.eligible_players}")
            logger.debug(f"  Active players: {pot.active_players}")
            if pot.capped:
                logger.debug(f"  Capped at ${pot.cap_amount} per player")

    def _distribute_to_pots(self, bet: BetInfo) -> None:
            """Distribute a bet across main pot and side pots, respecting caps."""
            remaining = bet.amount
            
            # Add to main pot up to its cap
            if self.main_pot.capped:
                main_contribution = min(remaining, max(0, self.main_pot.cap_amount - bet.prev_total))
                if main_contribution > 0:
                    self._contribute_to_pot(self.main_pot, bet, main_contribution)
                    remaining -= main_contribution
                    logger.debug(f"Added {main_contribution} to main pot (capped at {self.main_pot.cap_amount})")
            
            # Process remaining chips
            if remaining > 0:
                logger.debug(f"Have {remaining} remaining after main pot")
                
                if not self.side_pots:
                    # Create first side pot
                    side_pot = self._create_side_pot(remaining, bet)
                    self.side_pots.append(side_pot)
                    logger.debug(f"Created first side pot with {remaining}")
                else:
                    # Process through existing side pots
                    for pot in list(self.side_pots):  # Use list to allow modification
                        if remaining <= 0:
                            break
                        
                        if pot.capped:
                            contribution = min(remaining, pot.cap_amount)
                            if contribution > 0:
                                self._contribute_to_pot(pot, bet, contribution)
                                remaining -= contribution
                                logger.debug(f"Added {contribution} to capped side pot")
                        else:
                            self._contribute_to_pot(pot, bet, remaining)
                            if bet.is_all_in:
                                logger.debug(f"Player {bet.player_id} all-in, capping side pot at {remaining}")
                                pot.capped = True
                                pot.cap_amount = remaining
                            remaining = 0
                    
                    # If we still have chips, create new side pot
                    if remaining > 0:
                        new_pot = self._create_side_pot(remaining, bet)
                        self.side_pots.append(new_pot)
                        logger.debug(f"Created new side pot with {remaining}")                

    def add_bet(
        self,
        player_id: str,
        amount: int,      
        is_all_in: bool,  
        stack_before: int 
    ) -> None:
        """
        Add a bet to the pot structure.
        """
        prev_total = self.total_bets.get(player_id, 0)
        new_total = prev_total + amount
        
        bet = BetInfo(
            player_id=player_id,
            amount=amount,
            is_all_in=is_all_in,
            stack_before=stack_before,
            prev_total=prev_total,
            new_total=new_total
        )
        
        logger.debug(f"\nProcessing bet: {player_id}, amount={amount}, "
                    f"all_in={is_all_in}")
        
        # Track contribution
        self.total_bets[player_id] = new_total
        
        # Find current maximum bet
        current_max = max(self.total_bets.values(), default=0)
        
        # Handle specific cases
        if is_all_in:
            if current_max > 0 and new_total < current_max:
                # All-in below current bet
                logger.debug(f"All-in below current bet: {new_total} < {current_max}")
                self._handle_all_in_below_current(bet)
            elif not self.is_all_in:
                # First all-in - caps main pot at this bet size
                logger.debug(f"First all-in - capping main pot at {amount}")
                self.main_pot.amount += amount
                self.main_pot.eligible_players.add(player_id)
                self.main_pot.current_bet = amount
                self.main_pot.capped = True
                self.main_pot.cap_amount = amount
            else:
                # All-in above previous level
                self._distribute_to_pots(bet)
        else:
            # Regular bet - respect existing caps
            if self.is_all_in:
                self._handle_bet_above_all_in(bet)
            else:
                self._handle_normal_bet(bet)
                
        # Update all-in status
        if is_all_in:
            self.is_all_in[player_id] = True
            if player_id in self.main_pot.active_players:
                self.main_pot.active_players.remove(player_id)
            for pot in self.side_pots:
                if player_id in pot.active_players:
                    pot.active_players.remove(player_id)

        # Log final state
        logger.debug("\nAfter bet:")
        logger.debug(f"Main pot: ${self.main_pot.amount} (bet: ${self.main_pot.current_bet})")
        logger.debug(f"Main pot eligible: {self.main_pot.eligible_players}")
        debug_cap = f" (max bet ${self.main_pot.cap_amount})" if self.main_pot.capped else ""
        logger.debug(f"Main pot capped: {self.main_pot.capped}{debug_cap}")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"Side pot {i}: ${pot.amount}")
            logger.debug(f"  Eligible: {pot.eligible_players}")
            debug_cap = f" (max bet ${pot.cap_amount})" if pot.capped else ""
            logger.debug(f"  Capped: {pot.capped}{debug_cap}")
                
    @property
    def total(self) -> int:
        """Total amount in all pots."""
        return (self.main_pot.amount + 
                sum(pot.amount for pot in self.side_pots))
                
    def get_current_bet(self) -> int:
        """Get current bet that must be called."""
        if not self.main_pot.active_players:
            return 0
        return max(
            pot.current_bet 
            for pot in [self.main_pot] + self.side_pots
            if pot.active_players
        )