import pytest
from typing import List, Dict, Any, Tuple, Optional
from generic_poker.game.betting import (
    BettingManager, NoLimitBettingManager, LimitBettingManager, 
    PotLimitBettingManager, BetType, PlayerBet
)
from generic_poker.game.pot import PotBet
from generic_poker.config.loader import BettingStructure

import logging
import sys

@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for all tests."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Force reconfiguration of logging
    )

@pytest.fixture
def nl_betting():
    """Create a No Limit betting manager with small bet of 10."""
    return NoLimitBettingManager(small_bet=10)

@pytest.fixture
def limit_betting():
    """Create a Limit betting manager with small bet 10, big bet 20."""
    return LimitBettingManager(small_bet=10, big_bet=20)    

@pytest.fixture
def pot_limit_betting():
    """Create a Pot Limit betting manager with small bet of 10."""
    return PotLimitBettingManager(small_bet=10)

class TestSinglePlayer:
    """Single player scenarios - testing basic bet handling."""
    
    def test_partial_stack_bet(self, nl_betting):
        """P1($1000) bets $500."""
        nl_betting.place_bet("P1", 500, 1000)
        assert nl_betting.pot.total == 500
        assert nl_betting.pot.main_pot.amount == 500
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1"}
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",500)]
    
    def test_all_in_bet(self, nl_betting):
        """P1($1000) goes all-in."""
        nl_betting.place_bet("P1", 1000, 1000)
        assert nl_betting.pot.total == 1000
        assert nl_betting.pot.main_pot.amount == 1000
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 1000
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1"}
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",1000)]

class TestTwoPlayersEqualStacks:
    """Two player scenarios where both players have equal stacks ($1000)."""
    
    def test_bet_and_call(self, nl_betting):
        """
        P1 bets 500, P2 calls.
        No all-ins, just simple bet and call.
        """
        nl_betting.place_bet("P1", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 500
        assert not nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 1000
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",500),PotBet("P2",500)]
    
    def test_bet_and_raise(self, nl_betting):
        """
        P1 bets 500, P2 raises to 750.
        Testing raise mechanics without all-ins.
        """
        nl_betting.place_bet("P1", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 500
        assert nl_betting.pot.main_pot.current_bet == 500
        
        nl_betting.place_bet("P2", 750, 1000, is_forced=True)
        assert nl_betting.pot.main_pot.amount == 1250
        assert not nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.current_bet == 750
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",500),PotBet("P2",750)]
   
    def test_bet_and_all_in_raise(self, nl_betting):
        """
        P1 bets 500, P2 raises all-in to 1000.
        Testing raise to all-in.
        """
        nl_betting.place_bet("P1", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 500
        assert nl_betting.pot.main_pot.current_bet == 500
        
        nl_betting.place_bet("P2", 1000, 1000)
        assert nl_betting.pot.main_pot.amount == 1500
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 1000
        assert nl_betting.pot.main_pot.current_bet == 1000
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",500),PotBet("P2",1000)]

class TestTwoPlayersP1Short:
    """Two player scenarios where P1 has $100, P2 has $1000."""
    
    def test_short_all_in_and_call(self, nl_betting):
        """P1 all-in for 100, P2 calls exactly."""
        nl_betting.place_bet("P1", 100, 100)
        assert nl_betting.pot.main_pot.amount == 100
        assert nl_betting.pot.main_pot.current_bet == 100
        assert nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 100, 1000)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.current_bet == 100
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",100),PotBet("P2",100)]
    
    def test_short_all_in_and_raise(self, nl_betting):
        """P1 all-in, P2 raises."""
        # P1 all-in for 100 (less than minimum raise but allowed because all-in)
        nl_betting.place_bet("P1", 100, 100)
        assert nl_betting.pot.total == 100
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert nl_betting.pot.main_pot.current_bet == 100
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",100)]
        
        # P2 raises to 500
        nl_betting.place_bet("P2", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 200  # 100 each
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 400  # P2's excess
        assert nl_betting.pot.side_pots[0].current_bet == 400
        assert nl_betting.pot.side_pots[0].eligible_players == {"P2"}  

        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",100),PotBet("P2",100)]
        assert nl_betting.pot.side_pots[0].player_bets == [PotBet("P2",400)]


    def test_short_all_in_and_all_in_raise(self, nl_betting):
        """P1 all-in for 100, P2 raises all-in to 1000."""
        nl_betting.place_bet("P1", 100, 100)
        assert nl_betting.pot.main_pot.amount == 100
        
        nl_betting.place_bet("P2", 1000, 1000)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 900
        assert nl_betting.pot.side_pots[0].eligible_players == {"P2"}
        assert nl_betting.pot.side_pots[0].capped    

class TestTwoPlayersP2Short:
    """Two player scenarios where P1 has $1000, P2 has $100."""
    
    def test_small_bet_and_call(self, nl_betting):
        """
        P1 bets small (50), P2 calls within stack.
        Testing simple bet/call under short stack size.
        """
        nl_betting.place_bet("P1", 50, 1000)
        assert nl_betting.pot.main_pot.amount == 50
        assert not nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 50, 100)
        assert nl_betting.pot.main_pot.amount == 100
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
    
    def test_small_bet_and_all_in_raise(self, nl_betting):
        """
        P1 bets 50, P2 raises all-in to 100.
        Testing short stack raising all-in over small bet.
        """
        nl_betting.place_bet("P1", 50, 1000)
        assert nl_betting.pot.main_pot.amount == 50
        
        nl_betting.place_bet("P2", 100, 100)
        assert nl_betting.pot.main_pot.amount == 150
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
    
    def test_all_in_and_short_call(self, nl_betting):
        """
        P1 all-in for 1000, P2 calls with 100.
        Testing call of large all-in with short stack.
        """
        nl_betting.place_bet("P1", 1000, 1000)
        assert nl_betting.pot.main_pot.amount == 1000
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.current_bet == 1000
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",1000)]
        assert nl_betting.pot.main_pot.eligible_players == {"P1"}
        
        nl_betting.place_bet("P2", 100, 100)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert nl_betting.pot.main_pot.current_bet == 100
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
        print ("main pot player bets is:")
        print (nl_betting.pot.main_pot.player_bets)
        assert nl_betting.pot.main_pot.player_bets == [PotBet("P1",100),PotBet("P2",100)]

        # side bet has the extra $900 from P1's original bet
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 900
        assert nl_betting.pot.side_pots[0].player_bets == [PotBet("P1",900)]
        assert nl_betting.pot.side_pots[0].eligible_players == {"P1"}
        assert nl_betting.pot.side_pots[0].capped

    def test_large_bet_and_short_call(self, nl_betting):
        """
        P1 bets 500 (not all-in), P2 calls with all-in 100.
        Testing short stack calling large non-all-in bet.
        """
        nl_betting.place_bet("P1", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 500
        
        nl_betting.place_bet("P2", 100, 100)
        assert nl_betting.pot.main_pot.amount == 200  # 100 each
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 400  # P1's excess
        assert nl_betting.pot.side_pots[0].eligible_players == {"P1"}        

class TestTwoPlayerEdgeCases:
    """Edge cases for two player scenarios focusing on pot capping."""
    
    def test_equal_all_ins(self, nl_betting):
        """
        Both players all-in for exact same amount.
        Should create single capped main pot.
        """
        nl_betting.place_bet("P1", 100, 100)
        assert nl_betting.pot.main_pot.amount == 100
        assert nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 100, 100)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.current_bets["P1"].is_all_in
        assert nl_betting.current_bets["P2"].is_all_in
    
    def test_uncapped_main_to_capped_side(self, nl_betting):
        """
        P1 bets non-all-in amount but P2's all-in causes restructure.
        Tests transition from uncapped to capped pot.
        """
        nl_betting.place_bet("P1", 500, 1000)  # Not all-in
        assert nl_betting.pot.main_pot.amount == 500
        assert not nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 200, 200)  # All-in below current bet
        assert nl_betting.pot.main_pot.amount == 400  # 200 each
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 200
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 300  # P1's excess
        assert not nl_betting.pot.side_pots[0].capped  # Not capped since P1 wasn't all-in
    
    def test_multiple_bets_then_all_in(self, nl_betting):
        """
        Multiple bet sequence followed by all-in restructure.
        
        Initial stacks:
        P1: $1000
        P2: $1000
        
        Sequence:
        1. P1 bets $100 (stack 900)
        - Pot: $100
        2. P2 raises to $300 (stack 700)
        - Pot: $400 ($100 P1, $300 P2)
        3. P1 raises to $600 (stack 400)
        - Pot: $900 ($600 P1, $300 P2)
        4. P2 all-in for $1000 (stack 0)
        - Pot: $1600 ($600 P1, $1000 P2)
        """
        # P1 opens 100
        nl_betting.place_bet("P1", 100, 1000)
        assert nl_betting.pot.main_pot.amount == 100
        
        # P2 raises to 300
        nl_betting.place_bet("P2", 300, 1000)
        assert nl_betting.pot.main_pot.amount == 400
        
        # P1 raises to 600
        nl_betting.place_bet("P1", 600, 900)  # Had bet 100, stack was 900
        assert nl_betting.pot.main_pot.amount == 900
        
        # P2 all-in for their stack (had bet 300, raising 700 more)
        nl_betting.place_bet("P2", 1000, 700)
        
        # Final state:
        # Main pot has $1600 ($600 P1, $1000 P2)
        assert nl_betting.pot.main_pot.amount == 1600
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 1000
        assert len(nl_betting.pot.side_pots) == 0  # No side pots yet as P1 hasn't acted
        
        # If P1 were to call, they would need to add $400 more to match P2's $1000
    
    def test_tiny_all_in_under_previous_bet(self, nl_betting):
        """
        Test very small all-in that's less than previous bets.
        Edge case testing small stack handling.
        """
        nl_betting.place_bet("P1", 100, 1000)
        assert nl_betting.pot.main_pot.amount == 100
        
        # P2 all-in for tiny amount
        nl_betting.place_bet("P2", 10, 10)
        assert nl_betting.pot.main_pot.amount == 20  # 10 each
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 10
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 90  # P1's excess
        assert not nl_betting.pot.side_pots[0].capped
    
    def test_all_in_then_bigger_all_in(self, nl_betting):
        """
        First player all-in, second player bigger all-in.
        Tests side pot capping when second all-in is larger.
        """
        nl_betting.place_bet("P1", 200, 200)  # All-in first
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 500, 500)  # Bigger all-in
        assert nl_betting.pot.main_pot.amount == 400  # 200 each
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 200
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 300  # P2's excess
        assert nl_betting.pot.side_pots[0].capped  # Should be capped as it's from all-in
        assert nl_betting.pot.side_pots[0].cap_amount == 300
    
    def test_exact_call_after_all_in(self, nl_betting):
        """
        Call exactly matches all-in amount.
        Tests edge case of exact matching.
        """
        nl_betting.place_bet("P1", 500, 500)  # All-in
        assert nl_betting.pot.main_pot.amount == 500
        assert nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 500, 1000)  # Exact call
        assert nl_betting.pot.main_pot.amount == 1000
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 500
        assert len(nl_betting.pot.side_pots) == 0        

class TestThreePlayersBasic:
    """Three player scenarios with equal stacks ($1000) and no side pots."""
    
    def test_simple_calls(self, nl_betting):
        """P1 bets, P2 and P3 call."""
        # P1 bets 100
        nl_betting.place_bet("P1", 100, 1000)
        assert nl_betting.pot.main_pot.amount == 100
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
        
        # P2 calls 100
        nl_betting.place_bet("P2", 100, 1000)
        assert nl_betting.pot.main_pot.amount == 200
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
        
        # P3 calls 100
        nl_betting.place_bet("P3", 100, 1000)
        assert nl_betting.pot.main_pot.amount == 300
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}
    
    def test_single_raise_with_calls(self, nl_betting):
        """P1 bets, P2 raises, P3 and P1 call."""
        # P1 bets 100
        nl_betting.place_bet("P1", 100, 1000)
        assert nl_betting.pot.total == 100
        
        # P2 raises to 300
        nl_betting.place_bet("P2", 300, 1000)
        assert nl_betting.pot.total == 400
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
        
        # P3 calls 300
        nl_betting.place_bet("P3", 300, 1000)
        assert nl_betting.pot.total == 700
        
        # P1 calls additional 200
        nl_betting.place_bet("P1", 300, 900)
        assert nl_betting.pot.total == 900
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
    
    def test_multiple_raises(self, nl_betting):
        """P1 bets, P2 raises, P3 re-raises, all call."""
        # P1 bets 100
        nl_betting.place_bet("P1", 100, 1000)
        assert nl_betting.pot.total == 100
        
        # P2 raises to 300
        nl_betting.place_bet("P2", 300, 1000)
        assert nl_betting.pot.total == 400
        
        # P3 re-raises to 600
        nl_betting.place_bet("P3", 600, 1000)
        assert nl_betting.pot.total == 1000  # P1: 100, P2: 300, P3: 600
        
        # P1 calls (adding 500)
        nl_betting.place_bet("P1", 600, 900)
        assert nl_betting.pot.total == 1500
        
        # P2 calls (adding 300)
        nl_betting.place_bet("P2", 600, 700)
        assert nl_betting.pot.total == 1800
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0

class TestThreePlayersSingleSidePot:
    """Three player scenarios with equal initial stacks ($1000) and one side pot."""
    
    def test_first_player_allin(self, nl_betting):
        """P1 all-in, P2 raises, P3 calls."""
        # P1 all-in for 200
        nl_betting.place_bet("P1", 200, 200)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 200
        assert len(nl_betting.pot.side_pots) == 0
        
        # P2 raises to 500
        nl_betting.place_bet("P2", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 400  # 200 each P1/P2
        assert nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 300  # P2's excess
        
        # P3 calls 500
        nl_betting.place_bet("P3", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 600  # 200 each
        assert nl_betting.pot.side_pots[0].amount == 600  # 300 each P2/P3
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert nl_betting.pot.side_pots[0].eligible_players == {"P2", "P3"}
    
    def test_middle_player_allin(self, nl_betting):
        """P1 bets, P2 all-in short, P3 raises, P1 calls.
        
        Sequence:
        1. P1 bets 300 
        - Main: 300
        2. P2 all-in for 200
        - Main: 400 (200 each)
        - Side A: 100 (P1 excess)
        3. P3 raises to 500
        - Main: 600 (200 each)
        - Side A: 600 (300 each P1/P3)
        4. P1 calls 500
        - Main: 600 (200 each)
        - Side A: 900 (300 each P1/P3)
        """
        # P1 bets 300
        nl_betting.place_bet("P1", 300, 1000)
        assert nl_betting.pot.total == 300
        print(f"\nAfter P1 bets 300:")
        print(f"Main pot: {nl_betting.pot.main_pot.amount}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        
        # P2 all-in for 200
        nl_betting.place_bet("P2", 200, 200)
        assert nl_betting.pot.main_pot.amount == 400  # P1: 200, P2: 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 200
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 100  # P1's excess
        print(f"\nAfter P2 all-in 200:")
        print(f"Main pot: {nl_betting.pot.main_pot.amount}")
        print(f"Main pot cap: {nl_betting.pot.main_pot.cap_amount}")
        print(f"Side pot: {nl_betting.pot.side_pots[0].amount}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        
        # P3 raises to 500
        nl_betting.place_bet("P3", 500, 1000, is_forced=True)
        print(f"\nAfter P3 raises to 500:")
        print(f"Main pot: {nl_betting.pot.main_pot.amount}")
        print(f"Main pot cap: {nl_betting.pot.main_pot.cap_amount}")
        print(f"Side pot: {nl_betting.pot.side_pots[0].amount}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        assert nl_betting.pot.main_pot.amount == 600  # 200 each
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 600  # 300 each P1/P3
        
        # P1 calls
        nl_betting.place_bet("P1", 500, 700, is_forced=True)
        print(f"\nAfter P1 calls:")
        print(f"Main pot: {nl_betting.pot.main_pot.amount}")
        print(f"Main pot cap: {nl_betting.pot.main_pot.cap_amount}")
        print(f"Side pot: {nl_betting.pot.side_pots[0].amount}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        assert nl_betting.pot.main_pot.amount == 600  # No change in main
        assert nl_betting.pot.side_pots[0].amount == 900  # Now 300 each from P1/P3
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert nl_betting.pot.side_pots[0].eligible_players == {"P1", "P3"}

    def test_last_player_allin(self, nl_betting):
        """P1 bets, P2 raises, P3 all-in short, others call.
        
        Sequence:
        1. P1 bets 300
        - Main: 300
        2. P2 raises to 600
        - Main: 900
        3. P3 all-in for 400
        - Main: 1200 (400 each)
        - Side: 200 (P2's excess)
        4. P1 calls 400
        - Main: 1200
        - Side: 200
        """
        # P1 bets 300
        nl_betting.place_bet("P1", 300, 1000)
        assert nl_betting.pot.total == 300
        print(f"\nAfter P1 bets 300:")
        print(f"Total pot: {nl_betting.pot.total}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        
        # P2 raises to 600
        nl_betting.place_bet("P2", 600, 1000)
        assert nl_betting.pot.total == 900  # P1: 300, P2: 600
        print(f"\nAfter P2 raises to 600:")
        print(f"Total pot: {nl_betting.pot.total}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        
        # P3 all-in for 400
        nl_betting.place_bet("P3", 400, 400, is_forced=True)
        print(f"\nAfter P3 all-in 400:")
        print(f"Main pot: {nl_betting.pot.main_pot.amount}")
        print(f"Main pot cap: {nl_betting.pot.main_pot.cap_amount}")
        if nl_betting.pot.side_pots:
            print(f"Side pot: {nl_betting.pot.side_pots[0].amount}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        assert nl_betting.pot.main_pot.amount == 1100  # P1: 300, P2: 600, P3: 400
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 400
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 200  # P2's excess 200
        
        # P1 calls 400 (reduced from 600)
        nl_betting.place_bet("P1", 400, 700)
        print(f"\nAfter P1 calls:")
        print(f"Main pot: {nl_betting.pot.main_pot.amount}")
        print(f"Main pot cap: {nl_betting.pot.main_pot.cap_amount}")
        print(f"Side pot: {nl_betting.pot.side_pots[0].amount}")
        print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
        assert nl_betting.pot.main_pot.amount == 1200  # 400 each
        assert nl_betting.pot.side_pots[0].amount == 200  # P2's excess
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert nl_betting.pot.side_pots[0].eligible_players == {"P1", "P2"}