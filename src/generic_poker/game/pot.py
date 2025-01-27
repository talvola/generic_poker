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

@dataclass
class PotBet:
    """Information about a bet in a pot."""
    player_id: str
    amount: int          # Amount being added

@dataclass
class ActivePotNew:
    """Represents a pot (main or side) that can still receive bets."""
    amount: int               # Total amount in this pot
    current_bet: int          # Current bet that must be called
    eligible_players: Set[str] # Players who can win this pot
    active_players: Set[str]   # Players who can still bet in this pot
    excluded_players: Set[str] # Players who can win this pot
    player_bets: List[PotBet]  # Bets in this pot
    main_pot: bool = False     # True if this is the main pot
    capped: bool = False      # True if pot has all-in player (can't raise)
    cap_amount: int = 0       # If capped, maximum bet allowed    
    order: int = 0            # Order of the pot

    # return a text name for the pot
    def name(self) -> str:
        return "Main Pot" if self.main_pot else f"Side Pot {self.order}"

class Pot:
    def __init__(self):
        self.main_pot = ActivePotNew(0, 0, set(), set(), set(), list(), True)
        self.side_pots: List[ActivePotNew] = []
        self.total_bets: Dict[str, int] = {}  
        self.is_all_in: Dict[str, bool] = {}    

    def _contribute_to_pot(self, pot: ActivePotNew, bet: BetInfo, amount: int) -> None:        
        """Add a contribution to a specific pot and update its state."""
        pot.amount += amount
        pot.eligible_players.add(bet.player_id)
        if not bet.is_all_in:
            pot.active_players.add(bet.player_id)

        potbet = PotBet(bet.player_id, amount)
        # add potbet to player_bets
        pot.player_bets.append(potbet)
        logger.debug(f"Added {amount} to pot (now contains {pot.amount})")

    def _create_side_pot(self, amount: int, bet: BetInfo) -> ActivePotNew:
        """Create a new side pot with the given amount."""
        side_pot = ActivePotNew(
            amount=amount,
            current_bet=amount,
            eligible_players={bet.player_id},
            active_players=set() if bet.is_all_in else {bet.player_id},
            excluded_players=set(),
            player_bets=[]
        )
        if bet.is_all_in:
            logger.debug(f"Capping new side pot at {amount} since {bet.player_id} is all-in")
            side_pot.capped = True
            side_pot.cap_amount = amount
        potbet = PotBet(bet.player_id, amount)
        side_pot.player_bets.append(potbet)
        return side_pot        

    @property
    def total(self) -> int:
        """Total amount in all pots."""
        return (self.main_pot.amount + 
                sum(pot.amount for pot in self.side_pots))
    
    def add_bet(
            self,
            player_id: str,
            amount: int,      
            is_all_in: bool,  
            stack_before: int 
        ) -> None:
        """
        Add a bet to the pot structure.
        
        For all-in bets:
        - cap_amount represents total amount player must match
        - current_bet represents amount needed to call
        - capped=True indicates no further raises allowed
        
        Args:
            player_id: ID of betting player
            amount: Amount being added this betting round
            is_all_in: Whether this is an all-in bet
            stack_before: Player's stack before this bet
        """
        
        # how much has the player bet in total up to this point
        prev_total = self.total_bets.get(player_id, 0)
        # what will the player's total bet be after this bet
        new_total = prev_total + amount
        
        bet = BetInfo(
            player_id=player_id,
            amount=amount,
            is_all_in=is_all_in,
            stack_before=stack_before,
            prev_total=prev_total,
            new_total=new_total
        )
        
        logger.debug(f"\nProcessing bet: player={player_id}, amount={amount}, "
                    f"all_in={is_all_in}, new_total={new_total}")
        
        # A capped pot is one that cannot grow in size.   Players may still bet into the pot, or 
        # complete incomplete bets - but the bet will not grow.   This happens when a player goes all-in.
        # We need to track the players who are in the pot and who are excluded from the pot.

        # Note - at most one uncapped pot at a time, but there could be no uncapped pots, for example
        # if the first player is all-in, then the main pot is capped.

        # The main pot is always there, starting empty, and always has all active players as participants.

        
        # when a bet comes in, we will first iterate through all capped pots in order to see if we need 
        # to put the bet into one or more of them.   This includes the main pot.

        # build list of capped pots - main pot if capped, and any capped side post
        capped_pots = [self.main_pot] if self.main_pot.capped else [] + [pot for pot in self.side_pots if pot.capped]
        # there should be zero or one uncapped pots - which could include main pot
        uncapped_pots = [pot for pot in self.side_pots if not pot.capped]
        if not self.main_pot.capped:
            uncapped_pots.insert(0, self.main_pot)        

        if capped_pots:
            logger.debug("Iterating through capped pots")
            for pot in capped_pots:
                logger.debug(f"  Processing capped pot {pot.name()}")
                if pot.capped:
                    # If we have enough bet, then we need to put the bet into the pot
                    if amount >= pot.cap_amount:
                        logger.debug(f"  Capped pot has room for bet of {amount}")
                        contribution = min(amount, pot.cap_amount)
                        if contribution > 0:
                            self._contribute_to_pot(pot, bet, contribution)
                            amount -= contribution
                            logger.debug(f"Added {contribution} to capped pot")
                        if amount == 0:
                            # done distributing the bet 
                            break
                    else:
                        # underbet of a capped pot - we need to split
                        logger.debug(f"  We have a bet of {amount} under the cap of {pot.cap_amount}")
                        logger.debug(f"  We need to split the capped pot and create a new side pot to hold the rest")
                        
                        # get the amount for the side pot 
                        side_pot_amount = pot.cap_amount - amount
                        logger.debug(f"  Side pot will have amount {side_pot_amount}")
                        # create the new side pot
                        side_pot = ActivePotNew(
                            amount=side_pot_amount,
                            current_bet=side_pot_amount,
                            eligible_players=set(),
                            active_players=set(),
                            excluded_players=set(),
                            player_bets=[]
                        )
                        # if all-in, then cap the side pot
                        if is_all_in:
                            logger.debug(f"  Player {player_id} was all-in.   Side pot capped at {side_pot_amount}")
                            side_pot.capped = True
                            side_pot.cap_amount = side_pot_amount
                        # add the player to the excluded list
                        side_pot.excluded_players.add(player_id)
                        # need to add the players from the original capped pot to the new side pot
                        for pb in pot.player_bets:
                            side_pot.eligible_players.add(pb.player_id)
                            side_pot.active_players.add(pb.player_id)
                            # the new side pot should only have bets from the new player
                            # the amount is what's over the amount staying in the smaller capped pot.
                            side_pot.player_bets.append(PotBet(pb.player_id, side_pot_amount)) 
                        # add the side pot to the list
                        self.side_pots.append(side_pot)
                        logger.debug(f"  Created side pot for difference: {side_pot.amount}")

                        # now, we need to reduce the capped pot
                        # set the new capped amount
                        pot.capped = True
                        pot.cap_amount = amount
                        # the pot total amount will be the sum of all original player bets, capped at the cap amount,
                        # and dthe current bet
                        pot.amount = sum([min(pb.amount, amount) for pb in pot.player_bets]) + amount
                        # add the player to the eligible and active lists
                        pot.eligible_players.add(player_id)
                        logger.debug(f"  Eligible players in capped pot are: {pot.eligible_players}")
                        pot.active_players.add(player_id)
                        # set the current bet to the cap amount
                        pot.current_bet = amount
                        # need to reduce each player bet in the capped pot to the cap amount
                        # we will iterate through the player bets and reduce each one to the cap amount
                        for pb in pot.player_bets:
                            if pb.amount > amount:
                                pb.amount = amount
                        # and append current player 
                        pot.player_bets.append(PotBet(player_id, amount))
                        logger.debug(f"  Capped pot current bet reduced to {amount}.   Pot size is {pot.amount}")
                        logger.debug(f"  Player bets in capped pot are: {pot.player_bets}")
                        logger.debug(f"  Player bets in new side pot are {side_pot.player_bets}")
                        amount = 0
                        break

        else:
            logger.debug("No capped pots to iterate through")

        if amount > 0:
            logger.debug(f"  Still have {amount} to distribute")
            if uncapped_pots:
                logger.debug("Iterating through uncapped pots")
                for pot in uncapped_pots:
                    logger.debug(f"Processing uncappped pot {pot.name()} with current bet of {pot.current_bet}.   Player {player_id} has bet {amount}")
                    if amount >= pot.current_bet:
                        self._contribute_to_pot(pot, bet, amount)
                        pot.current_bet = amount 
                        logger.debug(f"  Player {player_id}'s bet of {amount} added to pot.   Pot bet increased to {pot.current_bet}" )
                        if is_all_in:
                            # all-in bet, so cap the pot
                            logger.debug(f"  Player {player_id} was all-in.   Pot {pot.name()} capped at {pot.current_bet}" )
                            pot.capped = True
                            pot.cap_amount = pot.current_bet
                        amount = 0
                    else:
                        # need to create a side pot for the difference
                        amount_for_side_pot = pot.current_bet - amount
                        logger.debug(f"  Player {player_id} underbet.  Need to split out side pot from main pot")
                        logger.debug(f"  Main pot will shrink to {amount}.   Side pot will be created with amount {amount_for_side_pot}")
                        logger.debug(f"  Side pot will have {player_id} added to exclusions")
                    if amount == 0:
                        # done distributing the bet 
                        break

            else:
                logger.debug(f"No uncapped pots to iterate through - but we have a bet of {amount} to distribute")
                logger.debug(f"Will put this into a new side pot")
                side_pot = self._create_side_pot(amount, bet)
                self.side_pots.append(side_pot)
                logger.debug(f"Created side pot for difference: {side_pot.amount}")    
            return
    
        return
        # three main scenarios to consider
        # 1) nobody is all-in - so bets just keep going into the main pot
        # 2) someone went all-in, betting less than the minimum bet for the main not
        #    so, we need to shrink the main pot to the all-in amount and create a side pot
        # 3) someone went all-in into the main pot, then someone re-raised, so we need to create a side pot for the new bet, but the main pot stays the same 

        # Track contribution by the player
        self.total_bets[player_id] = new_total

        # let's identify which scenario we are in

        # only main pot, and this player is not going all-in (basic common case)
        if not self.side_pots and not is_all_in:
            # bets should be valid before we get here - adding a check for now while debugging

            if amount < self.main_pot.current_bet:
                logger.debug(f"** ERROR: player bet is less than the current bet without an all-in - error?")
                return

            # if capped, then going to need to create a side pot for the difference
            if self.main_pot.capped == True:
                logger.debug(f"basic case - no all-in, no side pots, but main pot was capped so need to split")

                logger.debug(f"  Current main pot player bets: {self.main_pot.player_bets}")                    

                # cap the main pot at its current bet
                self.main_pot.capped = True
                self.main_pot.cap_amount = self.main_pot.current_bet        

                # put current bet into main pot for the new player
                self._contribute_to_pot(self.main_pot, bet, self.main_pot.current_bet)

                logger.debug(f"  Post-capped main pot player bets: {self.main_pot.player_bets}")                    

                # set the main pot current bet to the sum of the player bets
                self.main_pot.amount = sum([pb.amount for pb in self.main_pot.player_bets])

                # create new set of player_bets for the side pot - since this should be 
                # the first time, only one bet to add 
                side_pot_bets = []
                side_pot_bets.append(PotBet(player_id, amount - self.main_pot.current_bet))

                logger.debug(f"  Side pot bets: {side_pot_bets}")

                # get the sum of the bets for the side pot
                side_pot_total = sum([pb.amount for pb in side_pot_bets])

                # no need for side pot if the difference is zero
                if (side_pot_total > 0):
                    # create side pot for the difference with current player
                    side_pot = ActivePotNew(
                        amount=side_pot_total,
                        current_bet=self.main_pot.current_bet - self.main_pot.cap_amount,
                        eligible_players={player_id},
                        active_players={player_id},
                        player_bets=side_pot_bets
                    )
                    self.side_pots.append(side_pot)
                    logger.debug(f"Created side pot for difference: {side_pot.amount}")    
            else:
                # just add to main pot - which always exists 
                logger.debug(f"basic case - no all-in, no side pots - adding to main pot")

                self._contribute_to_pot(self.main_pot, bet, amount)
                # the new main pot current bet is this bet (might be the same, but could have gone up)
                self.main_pot.current_bet = amount

            return

        # no side pots yet - either first to go all-in, or a raise after an all-in, which means
        # the main pot is capped
        if not self.side_pots and is_all_in:
            if self.main_pot.capped:
                logger.debug(f"basic case (2b) - no side pots, player is all-in with a capped main pot")
                # implement later!
            else:
            # no one has gone all-in before
                logger.debug(f"basic case (2a) - no side pots, player is all-in without any caps in place")

                # need to compare all-in amount with the current bet amount 
                # if all-in amount is less than the current bet amount, we need to shrink the main pot to the all-in amount
                # and create a side pot for the difference
                
                # get the player's bets for just the main_pot from the player_bets list
                player_bets = [pb for pb in self.main_pot.player_bets if pb.player_id == player_id]
                player_total = sum([pb.amount for pb in player_bets])
                logger.debug(f"main pot player_total={player_total}, amount={amount}, new_total={new_total}")

                if amount >= self.main_pot.current_bet:
                    self._contribute_to_pot(self.main_pot, bet, amount)
                    self.main_pot.current_bet = amount 
                    self.main_pot.capped = True
                    self.main_pot.cap_amount = amount 
                    return
                else:
                    # need to 'reset' the main pot and create a side pot
                    # we know this is the first side pot - we can generalize later 

                    # this is tricky since different players may have contributed different amounts to the main pot
                    # lets get each player's bet into the main pot.   if the player has put in more than
                    # the cap, we need to create a side pot for the difference.    if the player has put in less than the cap,
                    # then that's OK - just leave it.

                    logger.debug(f"  Current main pot player bets: {self.main_pot.player_bets}")                    

                    bets_to_reduce = [pb for pb in self.main_pot.player_bets if pb.amount > amount]

                    logger.debug(f"  Bets to reduce: {bets_to_reduce}")

                    # cap the main pot
                    self.main_pot.capped = True
                    self.main_pot.cap_amount = amount                        

                    # iterate through each of the existing main pot player bets and 'cap' them to the amount
                    # of the all-in
                    for pb in self.main_pot.player_bets:
                        if pb.amount > amount:
                            pb.amount = amount

                    logger.debug(f"  Post-capped main pot player bets: {self.main_pot.player_bets}")                    

                    # set the main pot current bet to the sum of the player bets
                    self.main_pot.amount = sum([pb.amount for pb in self.main_pot.player_bets])

                    # create new set of player_bets for the side pot - should contain one entry 
                    # with the amount over the main pot bet from each player 
                    side_pot_bets = []
                    for pb in bets_to_reduce:
                        side_pot_bets.append(PotBet(pb.player_id, pb.amount - amount))

                    logger.debug(f"  Side pot bets: {side_pot_bets}")

                    # get the sum of the bets for the side pot
                    side_pot_total = sum([pb.amount for pb in side_pot_bets])

                    # create side pot for the difference
                    side_pot = ActivePotNew(
                        amount=side_pot_total,
                        current_bet=self.main_pot.current_bet - self.main_pot.cap_amount,
                        eligible_players=set(),
                        active_players=set(),
                        player_bets=side_pot_bets
                    )
                    self.side_pots.append(side_pot)
                    logger.debug(f"Created side pot for difference: {side_pot.amount}")         

                    return           

                # cases
                # 1) main pot is not capped yet
                #  a) player's bet is less than the current bet - will need to split side pot out from main pot and cap the main pot
                #  b) player's bet is equal to the current bet - just add to main pot - but then cap it since we have an all-in
                #  c) player's bet is greater than the current bet - it's a raise - add to the main pot, and set the cap 
                # 
                # 2) main pot is capped
                #   a) player's bet is less than the cap - will need to split side pot out from main pot and reset the cap on the main pot
                #   b) player's bet is equal to the cap - just add to main pot
                #   c) player's bet is greater than the cap - it's a raise - add the cap amount to the main pot, then create a side pot for the raise amount
                # 

                if not self.main_pot.capped:
                    if amount < self.main_pot.current_bet:
                        # player is all-in, but less than the current bet
                        logger.debug(f"player is all-in, but less than the current bet - need to shrink main pot and create side pot")

                        # 

                        # shrink main pot to all-in amount
                        self.main_pot.amount = player_total
                        self.main_pot.current_bet = player_total
                        self.main_pot.capped = True
                        self.main_pot.cap_amount = player_total

                        # create side pot for the difference
                        side_pot = ActivePotNew(
                            amount=self.main_pot.amount - amount,
                            current_bet=self.main_pot.amount - amount,
                            eligible_players=set(),
                            active_players=set(),
                            player_bets=[]
                        )
                        self.side_pots.append(side_pot)
                        logger.debug(f"Created side pot for difference: {side_pot.amount}")


                # just add to main pot - which always exists 
                logger.debug(f"first all-in - no side pots - adding to main pot")

                self._contribute_to_pot(self.main_pot, bet, amount)
                # we do have to cap the pot though since this player went all-in 
                self.main_pot.capped = True
                self.main_pot.current_bet = amount
                self.main_pot.cap_amount = amount

                return
        
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
                logger.debug(f"First all-in - capping main pot at total bet {new_total}")
                self.main_pot.amount += amount
                self.main_pot.eligible_players.add(player_id)
                self.main_pot.current_bet = new_total
                self.main_pot.capped = True
                self.main_pot.cap_amount = new_total  # Cap is total amount to match
                logger.debug(f"Main pot: amount=${self.main_pot.amount}, "
                            f"cap=${self.main_pot.cap_amount}, "
                            f"current_bet=${self.main_pot.current_bet}")
            else:
                # All-in above previous level
                logger.debug(f"All-in above previous level - total bet will be {new_total}")
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
                self.main_pot.active_players.remove(bet.player_id)
            for pot in self.side_pots:
                if player_id in pot.active_players:
                    pot.active_players.remove(bet.player_id)

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

    

class PotOld:
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
        """
        Handle case where player goes all-in for less than current bet.
        
        Sets:
        - cap_amount to total bet that must be matched
        - current_bet to amount needed to call
        - capped=True to indicate no raises allowed
        """
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
        # Cap amount is the total amount that must be matched
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
        
        The method handles:
        1. Contributing to main pot up to its cap
        2. Contributing to existing side pots up to their caps
        3. Creating new side pots for excess chips
        """
        logger.debug(f"\nHandling bet above all-in: {bet.player_id}, amount=${bet.amount}")
        logger.debug(f"Player's previous contribution: ${bet.prev_total}")
        logger.debug(f"New total contribution will be: ${bet.new_total}")
        
        remaining = bet.amount
        current_pot_index = -1  # -1 for main pot, 0+ for side pots
        
        # First handle main pot
        if self.main_pot.capped:
            main_contribution = min(remaining, max(0, self.main_pot.cap_amount))
            if main_contribution > 0:
                self._contribute_to_pot(self.main_pot, bet, main_contribution)
                remaining -= main_contribution
                logger.debug(f"Added {main_contribution} to capped main pot")
        
        # Then handle each side pot level
        if remaining > 0:
            current_level = self.main_pot.cap_amount if self.main_pot.capped else 0
            if not self.side_pots:
                # No existing side pots - create new one with remaining chips
                side_pot = ActivePot(
                    amount=remaining,
                    current_bet=remaining,
                    eligible_players={bet.player_id},
                    active_players=set() if bet.is_all_in else {bet.player_id}
                )
                if bet.is_all_in:
                    side_pot.capped = True
                    side_pot.cap_amount = remaining
                self.side_pots.append(side_pot)
                logger.debug(f"Created first side pot with ${remaining}")
                remaining = 0
            else:
                # Process through existing side pots
                for pot in list(self.side_pots):
                    if remaining <= 0:
                        break
                        
                    if pot.capped:
                        # Only add up to cap amount for this level
                        contribution = min(remaining, pot.cap_amount)
                        if contribution > 0:
                            self._contribute_to_pot(pot, bet, contribution)
                            remaining -= contribution
                            current_level += pot.cap_amount
                            logger.debug(f"Added ${contribution} to capped side pot")
                    else:
                        # For uncapped levels, match previous bet
                        prev_level = current_level
                        contribution = min(remaining, pot.current_bet)
                        if contribution > 0:
                            self._contribute_to_pot(pot, bet, contribution)
                            remaining -= contribution
                            current_level += contribution
                            logger.debug(f"Added ${contribution} to uncapped side pot")
                    
                # If still have chips after processing existing pots
                if remaining > 0:
                    new_pot = ActivePot(
                        amount=remaining,
                        current_bet=remaining,
                        eligible_players={bet.player_id},
                        active_players=set() if bet.is_all_in else {bet.player_id}
                    )
                    if bet.is_all_in:
                        new_pot.capped = True
                        new_pot.cap_amount = remaining
                    self.side_pots.append(new_pot)
                    logger.debug(f"Created new side pot with remaining ${remaining}")
                    remaining = 0

        logger.debug("\nAfter handling bet:")
        logger.debug(f"Main pot: ${self.main_pot.amount} (capped: {self.main_pot.capped})")
        for i, pot in enumerate(self.side_pots):
            logger.debug(f"Side pot {i}: ${pot.amount}")
            logger.debug(f"  Eligible: {pot.eligible_players}")
            if pot.capped:
                logger.debug(f"  Capped at ${pot.cap_amount}")

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
        
        For all-in bets:
        - cap_amount represents total amount player must match
        - current_bet represents amount needed to call
        - capped=True indicates no further raises allowed
        
        Args:
            player_id: ID of betting player
            amount: Amount being added this betting round
            is_all_in: Whether this is an all-in bet
            stack_before: Player's stack before this bet
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
        
        logger.debug(f"\nProcessing bet: player={player_id}, amount={amount}, "
                    f"all_in={is_all_in}, new_total={new_total}")
        
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
                logger.debug(f"First all-in - capping main pot at total bet {new_total}")
                self.main_pot.amount += amount
                self.main_pot.eligible_players.add(player_id)
                self.main_pot.current_bet = new_total
                self.main_pot.capped = True
                self.main_pot.cap_amount = new_total  # Cap is total amount to match
                logger.debug(f"Main pot: amount=${self.main_pot.amount}, "
                            f"cap=${self.main_pot.cap_amount}, "
                            f"current_bet=${self.main_pot.current_bet}")
            else:
                # All-in above previous level
                logger.debug(f"All-in above previous level - total bet will be {new_total}")
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
                self.main_pot.active_players.remove(bet.player_id)
            for pot in self.side_pots:
                if player_id in pot.active_players:
                    pot.active_players.remove(bet.player_id)

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