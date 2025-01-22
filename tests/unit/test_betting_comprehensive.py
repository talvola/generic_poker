import pytest
from typing import List, Dict, Any, Tuple, Optional
from generic_poker.game.betting import (
    BettingManager, NoLimitBettingManager, LimitBettingManager, 
    PotLimitBettingManager, BetType, PlayerBet
)
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
    
    def test_all_in_bet(self, nl_betting):
        """P1($1000) goes all-in."""
        nl_betting.place_bet("P1", 1000, 1000)
        assert nl_betting.pot.total == 1000
        assert nl_betting.pot.main_pot.amount == 1000
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 1000
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1"}

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
    
    def test_bet_and_raise(self, nl_betting):
        """
        P1 bets 500, P2 raises to 750.
        Testing raise mechanics without all-ins.
        """
        nl_betting.place_bet("P1", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 500
        
        nl_betting.place_bet("P2", 750, 1000, is_forced=True)
        assert nl_betting.pot.main_pot.amount == 1250
        assert not nl_betting.pot.main_pot.capped
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
    
    def test_bet_and_all_in_raise(self, nl_betting):
        """
        P1 bets 500, P2 raises all-in to 1000.
        Testing raise to all-in.
        """
        nl_betting.place_bet("P1", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 500
        
        nl_betting.place_bet("P2", 1000, 1000)
        assert nl_betting.pot.main_pot.amount == 1500
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 1000
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}

class TestTwoPlayersP1Short:
    """Two player scenarios where P1 has $100, P2 has $1000."""
    
    def test_short_all_in_and_call(self, nl_betting):
        """P1 all-in for 100, P2 calls exactly."""
        nl_betting.place_bet("P1", 100, 100)
        assert nl_betting.pot.main_pot.amount == 100
        assert nl_betting.pot.main_pot.capped
        
        nl_betting.place_bet("P2", 100, 1000)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 0
        assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2"}
    
    def test_short_all_in_and_raise(self, nl_betting):
        """P1 all-in for 100, P2 raises to 500."""
        nl_betting.place_bet("P1", 100, 100)
        assert nl_betting.pot.main_pot.amount == 100
        
        nl_betting.place_bet("P2", 500, 1000)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 400
        assert nl_betting.pot.side_pots[0].eligible_players == {"P2"}
    
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
        
        nl_betting.place_bet("P2", 100, 100)
        assert nl_betting.pot.main_pot.amount == 200
        assert nl_betting.pot.main_pot.capped
        assert nl_betting.pot.main_pot.cap_amount == 100
        assert len(nl_betting.pot.side_pots) == 1
        assert nl_betting.pot.side_pots[0].amount == 900
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