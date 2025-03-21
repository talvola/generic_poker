"""Unit tests for Pot class."""
import pytest
from generic_poker.game.pot import Pot, ActivePot, BetInfo
from generic_poker.game.table import Player

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
        force=True
    )

@pytest.fixture
def empty_pot():
    """Create an empty pot for testing."""
    return Pot()

@pytest.fixture
def mock_players():
    """Create mock players for testing."""
    return [
        Player("P1", "Alice", 100),
        Player("P2", "Bob", 100),
        Player("P3", "Charlie", 100)
    ]

class TestContributeToPot:
    """Test cases for _contribute_to_pot method."""
    
    def test_normal_contribution(self, empty_pot):
        """Normal contribution to pot."""
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        bet = BetInfo(
            player_id="P1",
            amount=100,
            is_all_in=False,
            stack_before=1000,
            prev_total=0,
            new_total=100
        )
        
        empty_pot._contribute_to_pot(pot, bet, 100)
        
        assert pot.amount == 100
        assert pot.player_bets == {"P1": 100}
        assert pot.eligible_players == {"P1"}
        assert pot.active_players == {"P1"}
        assert len(empty_pot.round_pots) == 1  # Should still be in first round

    def test_all_in_contribution(self, empty_pot):
        """Contribution from all-in player."""
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        bet = BetInfo(
            player_id="P1",
            amount=100,
            is_all_in=True,
            stack_before=100,
            prev_total=0,
            new_total=100
        )
        
        empty_pot._contribute_to_pot(pot, bet, 100)
        
        assert pot.amount == 100
        assert pot.player_bets == {"P1": 100}
        assert pot.eligible_players == {"P1"}
        assert not pot.active_players  # All-in player not active
        assert len(empty_pot.round_pots) == 1  # Should still be in first round

class TestHandleBetToCappedPot:
    """Test cases for _handle_bet_to_capped_pot method."""
    
    def test_bet_meets_cap(self, empty_pot):
        """Bet exactly meets the cap amount."""
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        pot.current_bet = 100
        pot.cap_amount = 100
        pot.capped = True
        
        bet = BetInfo(
            player_id="P2",
            amount=100,
            is_all_in=False,
            stack_before=1000,
            prev_total=0,
            new_total=100
        )
        
        remaining = empty_pot._handle_bet_to_capped_pot(pot, bet, 100)
        
        assert remaining == 0
        assert pot.amount == 100
        assert pot.player_bets == {"P2": 100}
        assert len(empty_pot.round_pots) == 1  # Should still be in first round
        
    def test_bet_exceeds_cap(self, empty_pot):
        """Bet is larger than cap amount."""
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        pot.current_bet = 100
        pot.cap_amount = 100
        pot.capped = True
        
        bet = BetInfo(
            player_id="P2",
            amount=300,
            is_all_in=False,
            stack_before=1000,
            prev_total=0,
            new_total=300
        )
        
        remaining = empty_pot._handle_bet_to_capped_pot(pot, bet, 300)
        
        assert remaining == 200  # Should return excess
        assert pot.amount == 100  # Should only take cap amount
        assert pot.player_bets == {"P2": 100}
        assert len(empty_pot.round_pots) == 1  # Should still be in first round

    def test_short_bet_triggers_restructure(self, empty_pot):
        """Bet cannot meet cap amount, triggers restructure."""
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        pot.current_bet = 300
        pot.cap_amount = 300
        pot.capped = True
        pot.player_bets = {"P1": 300}
        pot.amount = 300
        
        bet = BetInfo(
            player_id="P2",
            amount=100,
            is_all_in=True,
            stack_before=100,
            prev_total=0,
            new_total=100
        )
        
        remaining = empty_pot._handle_bet_to_capped_pot(pot, bet, 100)
        
        assert remaining == 0  # All used in restructure
        assert pot.amount == 200  # Should be reduced
        assert len(pot.player_bets) == 2
        assert pot.cap_amount == 100  # New cap at short stack amount
        assert len(empty_pot.round_pots) == 1  # Should still be in first round

class TestDistributeExcessToSidePots:
    """Test cases for _distribute_excess_to_side_pots method."""
    
    def test_single_uncapped_side_pot(self, empty_pot):
        """Single uncapped side pot available."""
        current = empty_pot.round_pots[-1]

        # Create existing side pot
        side_pot = ActivePot(
            amount=300,
            current_bet=300,
            eligible_players={"P1"},
            active_players={"P1"},
            excluded_players=set(),
            player_bets={"P1": 300},
            player_antes={},
            order=1
        )
        current.side_pots.append(side_pot)
        
        bet = BetInfo(
            player_id="P2",
            amount=300,
            is_all_in=False,
            stack_before=1000,
            prev_total=0,
            new_total=300
        )
        
        remaining = empty_pot._distribute_excess_to_side_pots(bet, 300)
        
        assert remaining == 0
        assert side_pot.amount == 600  # 300 each from P1 and P2
        assert side_pot.player_bets == {"P1": 300, "P2": 300}
        assert side_pot.eligible_players == {"P1", "P2"}
        
    def test_multiple_uncapped_side_pots(self, empty_pot):
        """Multiple uncapped side pots available."""
        current = empty_pot.round_pots[-1]

        # Create two side pots with different bet levels
        side_pot1 = ActivePot(
            amount=200,
            current_bet=200,
            eligible_players={"P1"},
            active_players={"P1"},
            excluded_players=set(),
            player_bets={"P1": 200},
            player_antes={},
            order=1
        )
        side_pot2 = ActivePot(
            amount=100,
            current_bet=100,
            eligible_players={"P1"},
            active_players={"P1"},
            excluded_players=set(),
            player_bets={"P1": 100},
            player_antes={},
            order=2
        )
        current.side_pots.extend([side_pot1, side_pot2])
        
        bet = BetInfo(
            player_id="P2",
            amount=300,
            is_all_in=False,
            stack_before=1000,
            prev_total=0,
            new_total=300
        )
        
        remaining = empty_pot._distribute_excess_to_side_pots(bet, 300)
        
        assert remaining == 0
        assert side_pot1.amount == 400  # 200 each
        assert side_pot2.amount == 200  # 100 each
        assert side_pot1.player_bets == {"P1": 200, "P2": 200}
        assert side_pot2.player_bets == {"P1": 100, "P2": 100}

class TestCreateNewSidePot:
    """Test cases for _create_new_side_pot method."""
    
    def test_normal_side_pot(self, empty_pot):
        """Create normal uncapped side pot."""
        current = empty_pot.round_pots[-1]

        bet = BetInfo(
            player_id="P1",
            amount=300,
            is_all_in=False,
            stack_before=1000,
            prev_total=0,
            new_total=300
        )
        
        empty_pot._create_new_side_pot(bet, 300)
        
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        side_pot = current.side_pots[0]
        assert side_pot.amount == 300
        assert side_pot.current_bet == 300
        assert side_pot.eligible_players == {"P1"}
        assert side_pot.active_players == {"P1"}  # Not all-in
        assert not side_pot.capped
        assert side_pot.player_bets == {"P1": 300}
        
    def test_all_in_side_pot(self, empty_pot):
        """Create capped side pot from all-in bet."""
        current = empty_pot.round_pots[-1]

        bet = BetInfo(
            player_id="P1",
            amount=300,
            is_all_in=True,
            stack_before=300,
            prev_total=0,
            new_total=300
        )
        
        empty_pot._create_new_side_pot(bet, 300)
        
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        side_pot = current.side_pots[0]
        assert side_pot.amount == 300
        assert side_pot.current_bet == 300
        assert side_pot.eligible_players == {"P1"}
        assert not side_pot.active_players  # All-in
        assert side_pot.capped
        assert side_pot.cap_amount == 300
        assert side_pot.player_bets == {"P1": 300}

class TestRestructuredPot:
    def test_simple_restructure(self, empty_pot):
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        # Initialize the pot
        pot.current_bet = 300
        pot.amount = 400  # Initial state: 100 from P1 + 300 from P2
        pot.player_bets = {"P1": 100, "P2": 300}
        pot.eligible_players = {"P1", "P2"}
        pot.active_players = {"P1", "P2"}

        target_amount = 200
        side_pot = empty_pot._restructure_pot(pot, target_amount)
        current.side_pots.append(side_pot)

        # Corrected assertions
        assert pot.amount == 300  # 100 from P1 + 200 from P2
        assert pot.current_bet == 200  # Reflects the target_amount
        assert pot.player_bets == {"P1": 100, "P2": 200}
        assert pot.capped  # Since restructured to a target
        assert side_pot.amount == 100
        assert side_pot.player_bets == {"P2": 100}

    def test_simple_restructure_add_bet(self, empty_pot):
        empty_pot.add_bet("P1", 100, False, 200)
        empty_pot.add_bet("P2", 300, False, 1000)

        # After first two bets
        current = empty_pot.round_pots[-1]
        assert current.main_pot.amount == 400  # 100 from P1 + 300 from P2
        assert current.main_pot.current_bet == 300  # P2 raised to 300
        assert not current.main_pot.capped
        assert current.main_pot.player_bets == {"P1": 100, "P2": 300}

        empty_pot.add_bet("P1", 200, True, 100)  # P1 adds 100 (total 200), all-in

        # After P1’s all-in
        assert current.main_pot.amount == 400  # 200 from P1 + 200 from P2
        assert current.main_pot.current_bet == 200  # Capped at P1’s all-in amount
        assert current.main_pot.capped
        assert current.main_pot.player_bets == {"P1": 200, "P2": 200}
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 100  # P2’s excess
        assert current.side_pots[0].player_bets == {"P2": 100}


    def test_restructure_with_multiple_excess(self, empty_pot):
        """
        Test restructuring a pot with multiple players contributing excess.
        P1 has bet 100, P2 and P3 have bet 300 each. Target amount is 200.
        Main pot caps at 200 per player where possible, excess from P2 and P3 goes to a side pot.
        """
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        # Initialize the pot
        pot.current_bet = 300
        pot.amount = 700  # 100 from P1 + 300 from P2 + 300 from P3
        pot.player_bets = {"P1": 100, "P2": 300, "P3": 300}
        pot.eligible_players = {"P1", "P2", "P3"}
        pot.active_players = {"P1", "P2", "P3"}
        
        # Define target_amount directly
        target_amount = 200
        
        # Call the method and capture the returned side pot
        side_pot = empty_pot._restructure_pot(pot, target_amount)
        current.side_pots.append(side_pot)
        
        # Assertions for the main pot
        assert pot.amount == 500  # 100 from P1 + 200 from P2 + 200 from P3
        assert pot.current_bet == 200
        assert pot.cap_amount == 200
        assert pot.capped
        assert pot.player_bets == {"P1": 100, "P2": 200, "P3": 200}
        
        # Assertions for the side pot
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        side_pot = current.side_pots[0]
        assert side_pot.amount == 200  # 100 from P2 + 100 from P3
        assert side_pot.eligible_players == {"P2", "P3"}
        assert not side_pot.capped

# new set of tests

class TestTutorialCase01:
    """Test betting patterns with add_bet based on walkthrough."""

    def test_two_players_no_all_in(self, empty_pot):
        """Case 0 - Create pot with P1 betting 100."""
        empty_pot.add_bet("P1", 100, False, 1000)
        # Basic assertions
        current = empty_pot.round_pots[-1]
        assert current.main_pot.amount == 100
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        assert current.main_pot.active_players == {"P1"}  
        assert current.main_pot.eligible_players == {"P1"} 
        assert current.main_pot.player_bets == {"P1": 100}  
        """ then P2 calls 100 """
        empty_pot.add_bet("P2", 100, False, 1000)
        assert current.main_pot.amount == 200
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        assert current.main_pot.active_players == {"P1", "P2"}
        assert current.main_pot.eligible_players == {"P1", "P2"}
        assert current.main_pot.player_bets == {"P1": 100, "P2": 100}   

    def test_two_players_P1_all_in_P2_call(self, empty_pot):
        """Case 1a - Create pot with P1 betting 100, which is all-in"""
        empty_pot.add_bet("P1", 100, True, 100)
        # Basic assertions
        current = empty_pot.round_pots[-1]
        assert current.main_pot.amount == 100
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 100
        assert len(current.side_pots) == 0
        assert current.main_pot.active_players == set()     # not sure if this is correct
        assert current.main_pot.eligible_players == {"P1"}
        assert current.main_pot.player_bets == {"P1": 100}
        """ then P2 calls 100, not all-in"""
        empty_pot.add_bet("P2", 100, False, 1000)
        assert current.main_pot.amount == 200
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 100
        assert len(current.side_pots) == 0
        assert current.main_pot.active_players == {"P2"}
        assert current.main_pot.eligible_players == {"P1", "P2"}
        assert current.main_pot.player_bets == {"P1": 100, "P2": 100}
        
    def test_two_players_P1_all_in_P2_raise(self, empty_pot):
        """Case 1b - Create pot with P1 betting 100, which is all-in"""
        empty_pot.add_bet("P1", 100, True, 100)
        # Basic assertions
        current = empty_pot.round_pots[-1]
        assert current.main_pot.amount == 100
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 100
        assert len(current.side_pots) == 0
        assert current.main_pot.active_players == set()
        assert current.main_pot.eligible_players == {"P1"}
        assert current.main_pot.player_bets == {"P1": 100}
        """ then P2 raises to 200, not all-in, creating side-pot"""
        empty_pot.add_bet("P2", 200, False, 1000)
        assert current.main_pot.amount == 200
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 100
        assert len(current.side_pots) == 1
        assert current.main_pot.active_players == {'P2'}     # not sure if this is correct - or whether if it's capped it even matters
        assert current.main_pot.eligible_players == {"P1", "P2"}
        assert current.main_pot.player_bets == {"P1": 100, "P2": 100}
        assert current.side_pots[0].amount == 100
        assert not current.side_pots[0].capped
        assert current.side_pots[0].active_players == {"P2"}
        assert current.side_pots[0].eligible_players == {"P2"}
        assert current.side_pots[0].player_bets == {"P2": 100}

    def test_two_players_P1_all_in_P2_call_less(self, empty_pot):
        """Case 1c - Create pot with P1 betting 100, which is all-in"""
        empty_pot.add_bet("P1", 100, True, 100)
        # Basic assertions
        current = empty_pot.round_pots[-1]
        assert current.main_pot.amount == 100
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 100
        assert len(current.side_pots) == 0
        assert current.main_pot.active_players == set()
        assert current.main_pot.eligible_players == {"P1"}
        assert current.main_pot.player_bets == {"P1": 100}
        """ then P2 calls 50 all-in, meaning we need to split up the main pot, creating side-pot"""
        empty_pot.add_bet("P2", 50, True, 50)
        assert current.main_pot.amount == 100  # 50 from each
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 50
        assert len(current.side_pots) == 1
        assert current.main_pot.active_players == set()  
        assert current.main_pot.eligible_players == {"P1", "P2"}
        assert current.main_pot.player_bets == {"P1": 50, "P2": 50}
        assert current.side_pots[0].amount == 50
        assert current.side_pots[0].capped
        assert current.side_pots[0].active_players == {"P1"}
        assert current.side_pots[0].eligible_players == {"P1"}
        assert current.side_pots[0].player_bets == {"P1": 50}

class TestTutorialCase2:
    def test_two_players_P1_bet_P2_call_allin(self, empty_pot):
        """Case 2a - Create pot with P1 betting 100"""
        empty_pot.add_bet("P1", 100, False, 1000)
        # Basic assertions
        current = empty_pot.round_pots[-1]
        assert current.main_pot.amount == 100
        assert not current.main_pot.capped
        assert len(current.side_pots) == 0
        assert current.main_pot.active_players == {"P1"}
        assert current.main_pot.eligible_players == {"P1"}
        assert current.main_pot.player_bets == {"P1": 100}
        """ then P2 calls 100, all-in"""
        empty_pot.add_bet("P2", 100, True, 100)
        assert current.main_pot.amount == 200
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 100
        assert len(current.side_pots) == 0
        assert current.main_pot.active_players == {"P1"}
        assert current.main_pot.eligible_players == {"P1", "P2"}
        assert current.main_pot.player_bets == {"P1": 100, "P2": 100}

    def test_two_players_P1_bet_P2_call_less(self, empty_pot):
        """Case 2a - Create pot with P1 betting 100"""
        empty_pot.add_bet("P1", 100, False, 1000)
        # Basic assertions
        current = empty_pot.round_pots[-1]
        assert current.main_pot.amount == 100
        assert not current.main_pot.capped
        assert len(current.side_pots) == 0
        assert current.main_pot.active_players == {"P1"}
        assert current.main_pot.eligible_players == {"P1"}
        assert current.main_pot.player_bets == {"P1": 100}
        """ then P2 calls for less $50, all-in"""
        empty_pot.add_bet("P2", 50, True, 50)
        assert current.main_pot.amount == 100
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 50
        assert len(current.side_pots) == 1   
        assert current.main_pot.active_players == {"P1"}
        assert current.main_pot.eligible_players == {"P1", "P2"}
        assert current.main_pot.player_bets == {"P1": 50, "P2": 50}
        assert current.side_pots[0].amount == 50
        assert not current.side_pots[0].capped
        assert current.side_pots[0].active_players == {"P1"}
        assert current.side_pots[0].eligible_players == {"P1"}
        assert current.side_pots[0].player_bets == {"P1": 50}
        

class TestBasicBettingPatterns:
    """Test basic betting patterns with add_bet."""

    @pytest.fixture
    def capped_pot(self, empty_pot):
        """Create pot with P1 betting 100, P2 all-in for 50."""
        empty_pot.add_bet("P1", 100, False, 1000)
        empty_pot.add_bet("P2", 50, True, 50)
        return empty_pot    

    def test_standard_bet_sequence(self, empty_pot):
        """Test sequence: P1 bets 100, P2 calls, P3 raises to 300, P1 and P2 call."""
        current = empty_pot.round_pots[-1]

        # P1 opens for 100
        empty_pot.add_bet("P1", 100, False, 1000)
        assert current.main_pot.amount == 100
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        assert current.main_pot.active_players == {"P1"}  # Added assertion
        
        # P2 calls 100
        empty_pot.add_bet("P2", 100, False, 1000)
        assert current.main_pot.amount == 200
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        assert current.main_pot.active_players == {"P1", "P2"}  # Added assertion
        
        # P3 raises to 300
        empty_pot.add_bet("P3", 300, False, 1000)
        assert current.main_pot.amount == 500  # 100 + 100 + 300
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        
        # P1 calls 300 (not 200 - specifying total amount)
        empty_pot.add_bet("P1", 300, False, 900)
        assert current.main_pot.amount == 700
        
        # P2 calls 300
        empty_pot.add_bet("P2", 300, False, 900)
        assert current.main_pot.amount == 900
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0

    def test_multiple_rounds_betting(self, empty_pot):
        """Multiple betting rounds showing pot evolution."""
        current = empty_pot.round_pots[-1]

        # Round 1
        empty_pot.add_bet("P1", 100, False, 1000)  # Open
        empty_pot.add_bet("P2", 300, False, 1000)  # Raise
        empty_pot.add_bet("P3", 300, False, 1000)  # Call
        empty_pot.add_bet("P1", 300, False, 900)   # Call
        assert current.main_pot.amount == 900
        assert not current.main_pot.capped
        
        # Round 2
        empty_pot.add_bet("P1", 500, False, 600)   # Bet total 500
        empty_pot.add_bet("P2", 350, True, 50)     # All-in total 350
        empty_pot.add_bet("P3", 700, True, 400)    # All-in raise total 700
        empty_pot.add_bet("P1", 700, False, 400)   # Call

    def test_all_in_partial_call(self, capped_pot):
        """P3 all-in for 75 (more than main pot, less than side)."""
        current = capped_pot.round_pots[-1]

        capped_pot.add_bet("P3", 75, True, 75)
        assert current.main_pot.amount == 150  # 50 each
        assert len(current.side_pots) == 2
        assert current.side_pots[0].amount == 50  # 25 each P1/P3
        assert current.side_pots[1].amount == 25  # P1's excess

    def test_three_player_mixed_allin_sequence(self, empty_pot):
        """Three players with mix of standard bets and all-ins."""
        current = empty_pot.round_pots[-1]

        # P1 standard bet
        empty_pot.add_bet("P1", 100, False, 1000)
        assert current.main_pot.amount == 100  # 100 from P1
        assert len(empty_pot.round_pots[-1].side_pots) == 0   # no side pots
        # P2 all-in short
        empty_pot.add_bet("P2", 50, True, 50)
        assert current.main_pot.amount == 100 # 50 from P1, 50 from P2
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for rest of P1's money
        assert current.side_pots[0].amount == 50  # 50 from P1
        # P3 standard raise
        empty_pot.add_bet("P3", 200, False, 1000)
        assert current.main_pot.amount == 150 # 50 from P1, 50 from P2, 50 from P3
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for P1 and P3
        assert current.side_pots[0].amount == 200  # 50 from P1, 150 from P3

    def test_four_player_mixed_allin_sequence(self, empty_pot):
        """Four players with mix of standard bets and all-ins."""
        current = empty_pot.round_pots[-1]

        # P1 standard bet
        empty_pot.add_bet("P1", 100, False, 1000)
        assert current.main_pot.amount == 100  # 100 from P1
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0   # no side pots
        # P2 all-in short
        empty_pot.add_bet("P2", 50, True, 50)
        assert current.main_pot.amount == 100 # 50 from P1, 50 from P2
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for rest of P1's money
        assert current.side_pots[0].amount == 50  # 50 from P1
        assert not current.side_pots[0].capped
        # P3 standard raise
        empty_pot.add_bet("P3", 200, False, 1000)
        assert current.main_pot.amount == 150 # 50 from P1, 50 from P2, 50 from P3
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for P1 and P3
        assert current.side_pots[0].amount == 200  # 50 from P1, 150 from P3
        assert not current.side_pots[0].capped
        # P4 all-in above
        empty_pot.add_bet("P4", 400, True, 400)
        assert current.main_pot.amount == 200 # 50 from P1, 50 from P2, 50 from P3, 50 from P4 
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for P1, P3 and P4
        assert current.side_pots[0].amount == 550  # 50 from P1, 150 from P3
        assert current.side_pots[0].capped   # capped since P4 is all-in        

    def test_five_player_mixed_allin_sequence(self, empty_pot):
        """Five players with mix of standard bets and all-ins."""
        current = empty_pot.round_pots[-1]

        # P1 standard bet
        empty_pot.add_bet("P1", 100, False, 1000)
        assert current.main_pot.amount == 100  # 100 from P1
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0   # no side pots
        # P2 all-in short
        empty_pot.add_bet("P2", 50, True, 50)
        assert current.main_pot.amount == 100 # 50 from P1, 50 from P2
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for rest of P1's money
        assert current.side_pots[0].amount == 50  # 50 from P1
        assert not current.side_pots[0].capped
        # P3 standard raise
        empty_pot.add_bet("P3", 200, False, 1000)
        assert current.main_pot.amount == 150 # 50 from P1, 50 from P2, 50 from P3
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for P1 and P3
        assert current.side_pots[0].amount == 200  # 50 from P1, 150 from P3
        assert not current.side_pots[0].capped
        # P4 all-in above
        empty_pot.add_bet("P4", 400, True, 400)
        assert current.main_pot.amount == 200 # 50 from P1, 50 from P2, 50 from P3, 50 from P4 
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for P1, P3 and P4
        assert current.side_pots[0].amount == 550  # 50 from P1, 150 from P3, 350 from P4
        assert current.side_pots[0].capped   # capped since P4 is all-in      
        # P5 all-in short
        empty_pot.add_bet("P5", 150, True, 150)               
        assert current.main_pot.amount == 250 # 50 from P1, 50 from P2, 50 from P3, 50 from P4, 50 from P5
        assert len(empty_pot.round_pots[-1].side_pots) == 2   # new side pot for P1, P3
        assert current.side_pots[0].amount == 350  # 50 from P1, 100 from P3, 100 from P4, 100 from P5
        assert current.side_pots[0].capped   # still capped since P4 was all-in
        assert current.side_pots[1].amount == 300  # 50 from P3, 250 from P4
        assert current.side_pots[1].capped   # still capped since P4 was all-in 

    def test_six_player_mixed_allin_sequence(self, empty_pot):
        """Six players with mix of standard bets and all-ins."""
        current = empty_pot.round_pots[-1]

        # P1 standard bet
        empty_pot.add_bet("P1", 100, False, 1000)
        assert current.main_pot.amount == 100  # 100 from P1
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0   # no side pots
        # P2 all-in short
        empty_pot.add_bet("P2", 50, True, 50)
        assert current.main_pot.amount == 100 # 50 from P1, 50 from P2
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for rest of P1's money
        assert current.side_pots[0].amount == 50  # 50 from P1
        assert not current.side_pots[0].capped
        # P3 standard raise
        empty_pot.add_bet("P3", 200, False, 1000)
        assert current.main_pot.amount == 150 # 50 from P1, 50 from P2, 50 from P3
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for P1 and P3
        assert current.side_pots[0].amount == 200  # 50 from P1, 150 from P3
        assert not current.side_pots[0].capped
        # P4 all-in above
        empty_pot.add_bet("P4", 400, True, 400)
        assert current.main_pot.amount == 200 # 50 from P1, 50 from P2, 50 from P3, 50 from P4 
        assert len(empty_pot.round_pots[-1].side_pots) == 1   # side pot for P1, P3 and P4
        assert current.side_pots[0].amount == 550  # 50 from P1, 150 from P3, 350 from P4
        assert current.side_pots[0].capped   # capped since P4 is all-in      
        # P5 all-in short
        empty_pot.add_bet("P5", 150, True, 150)               
        assert current.main_pot.amount == 250 # 50 from P1, 50 from P2, 50 from P3, 50 from P4, 50 from P5
        assert len(empty_pot.round_pots[-1].side_pots) == 2   # new side pot for P1, P3
        assert current.side_pots[0].amount == 350  # 50 from P1, 100 from P3, 100 from P4, 100 from P5
        assert current.side_pots[0].capped   # still capped since P4 was all-in
        assert current.side_pots[1].amount == 300  # 50 from P3, 250 from P4
        assert current.side_pots[1].capped   # still capped since P4 was all-in 
        # P6 calls max
        empty_pot.add_bet("P6", 400, False, 1000)
        assert current.main_pot.amount == 300 # 50 from P1, 50 from P2, 50 from P3, 50 from P4, 50 from P5, 50 from P6
        assert len(empty_pot.round_pots[-1].side_pots) == 2    # no new side pot needed
        assert current.side_pots[0].amount == 450  # 50 from P1, 100 from P3, 100 from P4, 100 from P5, 100 from P6
        assert current.side_pots[0].capped   # still capped since P4 was all-in
        assert current.side_pots[1].amount == 550  # 50 from P3, 250 from P4, 250 from P6
        assert current.side_pots[1].capped   # still capped 

class TestEmptyPotBetting:
    """Tests starting from empty pot."""

    def test_standard_opening_bet(self, empty_pot):
        """Standard opening bet (no all-in)."""
        current = empty_pot.round_pots[-1]
        empty_pot.add_bet("P1", 100, False, 1000)
        assert current.main_pot.amount == 100
        assert not current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0
    
    def test_all_in_opening_bet(self, empty_pot):
        """All-in opening bet."""
        current = empty_pot.round_pots[-1]

        empty_pot.add_bet("P1", 500, True, 500)
        assert current.main_pot.amount == 500
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 500  # Added assertion
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        assert not current.main_pot.active_players  # Added assertion
        assert current.main_pot.eligible_players == {"P1"}  # Added assertion

class TestUncappedMainPotBetting:
    """Tests with uncapped main pot."""
    
    @pytest.fixture
    def uncapped_pot(self, empty_pot):
        """Create pot with P1 betting 100."""
        empty_pot.add_bet("P1", 100, False, 1000)
        return empty_pot
    
    def test_standard_call(self, uncapped_pot):
        """P2 makes standard call."""
        current = uncapped_pot.round_pots[-1]
        uncapped_pot.add_bet("P2", 100, False, 1000)
        assert current.main_pot.amount == 200
        assert not current.main_pot.capped
        assert len(current.side_pots) == 0
    
    def test_standard_raise(self, uncapped_pot):
        """P2 makes standard raise."""
        current = uncapped_pot.round_pots[-1]
        uncapped_pot.add_bet("P2", 300, False, 1000)
        assert current.main_pot.amount == 400
        assert not current.main_pot.capped
        assert len(current.side_pots) == 0
    
    def test_all_in_above_current(self, uncapped_pot):
        """P2 goes all-in above current bet."""
        current = uncapped_pot.round_pots[-1]
        uncapped_pot.add_bet("P2", 500, True, 500)
        assert current.main_pot.amount == 600  # P1:100 + P2:500
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 500
        assert len(current.side_pots) == 0
    
    def test_all_in_below_current(self, uncapped_pot):
        """P2 goes all-in below current bet."""
        current = uncapped_pot.round_pots[-1]
        uncapped_pot.add_bet("P2", 50, True, 50)
        assert current.main_pot.amount == 100  # 50 each
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 50
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 50  # P1's excess

class TestCappedMainPotBetting:
    """Tests with capped main pot from short stack all-in."""
    
    @pytest.fixture
    def capped_pot(self, empty_pot):
        """Create pot with P1 betting 100, P2 all-in for 50."""
        empty_pot.add_bet("P1", 100, False, 1000)
        empty_pot.add_bet("P2", 50, True, 50)
        return empty_pot
    
    def test_standard_call_both_pots(self, capped_pot):
        """P3 calls both main and side pot."""
        current = capped_pot.round_pots[-1]
        capped_pot.add_bet("P3", 100, False, 1000)
        assert current.main_pot.amount == 150  # 50 each
        assert current.main_pot.capped
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 100  # 50 each P1/P3
    
    def test_all_in_partial_call(self, capped_pot):
        """P3 all-in for 75 (more than main pot, less than side)."""
        current = capped_pot.round_pots[-1]
        capped_pot.add_bet("P3", 75, True, 75)
        assert current.main_pot.amount == 150  # 50 each
        assert len(current.side_pots) == 2
        assert current.side_pots[0].amount == 50  # 25 each P1/P3
        assert current.side_pots[1].amount == 25  # P1's excess

class TestMultipleCappedPotsBetting:
    """Tests with multiple capped pots from series of all-ins."""
    
    @pytest.fixture
    def multi_capped_pot(self, empty_pot):
        """Create pot with series of all-ins:
        P1 all-in 100
        P2 all-in 200
        P3 all-in 300
        """
        empty_pot.add_bet("P1", 100, True, 100)
        empty_pot.add_bet("P2", 200, True, 200)
        empty_pot.add_bet("P3", 300, True, 300)
        return empty_pot
    
    def test_standard_call_all_pots(self, multi_capped_pot):
        """P4 calls amount to cover all pots."""
        current = multi_capped_pot.round_pots[-1]
        multi_capped_pot.add_bet("P4", 300, False, 1000)
        assert current.main_pot.amount == 400  # 100 each
        assert len(current.side_pots) == 2
        assert current.side_pots[0].amount == 300  # 100 each P2/P3/P4
        assert current.side_pots[1].amount == 200  # 100 each P3/P4
    
    def test_standard_raise_new_side_pot(self, multi_capped_pot):
        """P4 raises creating new uncapped side pot."""
        current = multi_capped_pot.round_pots[-1]      
        multi_capped_pot.add_bet("P4", 500, False, 1000)
        assert current.main_pot.amount == 400  # 100 each
        assert len(current.side_pots) == 3
        assert current.side_pots[0].amount == 300  # 100 each P2/P3/P4
        assert current.side_pots[1].amount == 200  # 100 each P3/P4
        assert current.side_pots[2].amount == 200  # P4's excess raise
    
    def test_all_in_between_pots(self, multi_capped_pot):
        """P4 all-in for amount between existing pot sizes."""
        current = multi_capped_pot.round_pots[-1]      
        multi_capped_pot.add_bet("P4", 250, True, 250)
        assert current.main_pot.amount == 400  # 100 each
        assert len(current.side_pots) == 3
        assert current.side_pots[0].amount == 300  # 100 each P2/P3/P4
        assert current.side_pots[1].amount == 100  # 50 each P3/P4
        assert current.side_pots[2].amount == 50  # P3's excess

class TestComplexScenarios:
    """Tests for complex multi-player scenarios."""

    def test_six_player_mixed_allin_sequence(self, empty_pot):
        """Six players with mix of standard bets and all-ins."""
        # P1 standard bet
        current = empty_pot.round_pots[-1]      
        empty_pot.add_bet("P1", 100, False, 1000)    
        assert current.main_pot.amount == 100  # 100 from P1
        assert not current.main_pot.capped     # not capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0     # no side pots

        # P2 all-in short
        empty_pot.add_bet("P2", 50, True, 50)        
        assert current.main_pot.amount == 100  # 50 from P1 and 50 from P2
        assert current.main_pot.capped         #  capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1     # 1 side pot
        assert current.side_pots[0].amount == 50  # 50 from P1
        assert not current.side_pots[0].capped # not capped        

        # P3 standard raise
        empty_pot.add_bet("P3", 200, False, 1000)      
        assert current.main_pot.amount == 150  # 50 from P1, 50 from P2, 50 from P3
        assert current.main_pot.capped         #  capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1     # 1 side pot
        assert current.side_pots[0].amount == 200  # 50 from P1, 150 from P3
        assert not current.side_pots[0].capped # not capped                        

        # P4 all-in above
        empty_pot.add_bet("P4", 400, True, 400)     
        assert current.main_pot.amount == 200  # 50 from P1, 50 from P2, 50 from P3, 50 from P4
        assert current.main_pot.capped         #  capped
        assert len(empty_pot.round_pots[-1].side_pots) == 1     # 1 side pot
        assert current.side_pots[0].amount == 550  # 50 from P1, 150 from P3, 350 from P4
        assert current.side_pots[0].capped # capped since P4 is all in     

        # P5 all-in short
        empty_pot.add_bet("P5", 150, True, 150)              
        assert current.main_pot.amount == 250  # 50 from P1, 50 from P2, 50 from P3, 50 from P4, 50 from P5
        assert current.main_pot.capped         #  capped
        assert len(empty_pot.round_pots[-1].side_pots) == 2     # 2 side pots - we are creating a new side pot since player is short 
        assert current.side_pots[0].amount == 350  # 50 from P1, 100 from P3, 100 from P4, 100 from P5
        assert current.side_pots[0].capped # capped since P4 is all in     
        assert current.side_pots[1].amount == 300  # 50 from P3, 250 from P4
        assert current.side_pots[1].capped # capped since P4 is all in 
        # P6 calls max
        empty_pot.add_bet("P6", 400, False, 1000)
        assert current.main_pot.amount == 300  # 50 from P1, 50 from P2, 50 from P3, 50 from P4, 50 from P5, 50 from P6
        assert current.main_pot.capped         #  capped
        assert len(empty_pot.round_pots[-1].side_pots) == 2     # 2 side pots - we are creating a new side pot since player is short 
        assert current.side_pots[0].amount == 450  # 50 from P1, 100 from P3, 100 from P4, 100 from P5, 100 from P6
        assert current.side_pots[0].capped # capped since P4 is all in     
        assert current.side_pots[1].amount == 550  # 50 from P3, 250 from P4, 250 from P6
        assert current.side_pots[1].capped # capped since P4 is all in         
        
    def test_equal_amount_all_ins(self, empty_pot):
        """Test when multiple players go all-in for exactly same amount.
        
        Sequence:
        P1: all-in 200
        P2: all-in 200
        P3: all-in 200
        P4: all-in 200
        
        Should result in single pot of 800 (200 × 4) with no side pots
        since everyone contributed equally.
        """
        current = empty_pot.round_pots[-1]      

        # P1 all-in 200
        empty_pot.add_bet("P1", 200, True, 200)
        assert current.main_pot.amount == 200
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        
        # P2 all-in 200
        empty_pot.add_bet("P2", 200, True, 200)
        assert current.main_pot.amount == 400  # 200 each
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0  # No side pot needed
        
        # P3 all-in 200 
        empty_pot.add_bet("P3", 200, True, 200)
        assert current.main_pot.amount == 600  # 200 each
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0  # No side pot needed
        
        # P4 all-in 200
        empty_pot.add_bet("P4", 200, True, 200)
        assert current.main_pot.amount == 800  # 200 each
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0  # No side pot needed
        
        # Additional assertions to verify pot state
        assert current.main_pot.current_bet == 200
        assert current.main_pot.cap_amount == 200
        assert current.main_pot.eligible_players == {"P1", "P2", "P3", "P4"}
        assert not current.main_pot.active_players  # All players all-in

    def test_multiple_rounds_betting_round1(self, empty_pot):
        """Multiple betting rounds showing pot evolution."""
        current = empty_pot.round_pots[-1]      

        # Round 1
        empty_pot.add_bet("P1", 100, False, 1000)  # Open
        empty_pot.add_bet("P2", 300, False, 1000)  # Raise
        empty_pot.add_bet("P3", 300, False, 1000)  # Call
        empty_pot.add_bet("P1", 300, False, 900)   # Call
        
        assert current.main_pot.amount == 900
        assert not current.main_pot.capped

    def test_multiple_rounds_betting_round2(self, empty_pot):
        """Multiple betting rounds showing pot evolution."""
        current = empty_pot.round_pots[-1]      
        
        # Round 1
        empty_pot.add_bet("P1", 100, False, 1000)  # Open
        empty_pot.add_bet("P2", 300, False, 1000)  # Raise
        empty_pot.add_bet("P3", 300, False, 1000)  # Call
        empty_pot.add_bet("P1", 300, False, 900)   # Call
        
        assert current.main_pot.amount == 900
        assert not current.main_pot.capped

class TestMultipleRounds:

    def test_multiple_betting_rounds(self, empty_pot):
        """Test betting across multiple rounds.

        Starting stacks:
        P1: 1000
        P2: 500
        P3: 1000

        Round 1:
        P1 bets 500
        P2 calls 500 (all-in)
        P3 raises to 750
        P1 calls 750

        End of Round 1:
        - Main pot: $1500 ($500 each) - capped
        - Side pot: $500 ($250 each P1/P3) - uncapped

        Round 2:
        P1 bets 200 (into uncapped side pot)
        P3 calls 200
        """
        # Round 1
        empty_pot.add_bet("P1", 500, False, 1000)  # Open
        assert empty_pot.round_pots[-1].main_pot.amount == 500

        empty_pot.add_bet("P2", 500, True, 500)   # Call all-in
        assert empty_pot.round_pots[-1].main_pot.amount == 1000
        assert empty_pot.round_pots[-1].main_pot.capped
        assert empty_pot.round_pots[-1].main_pot.cap_amount == 500

        empty_pot.add_bet("P3", 750, False, 1000)  # Raise
        assert empty_pot.round_pots[-1].main_pot.amount == 1500  # $500 each
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        assert empty_pot.round_pots[-1].side_pots[0].amount == 250  # P3's extra $250

        empty_pot.add_bet("P1", 750, False, 500)   # Call raise
        assert empty_pot.round_pots[-1].main_pot.amount == 1500
        assert empty_pot.round_pots[-1].side_pots[0].amount == 500  # $250 each P1/P3
        assert not empty_pot.round_pots[-1].side_pots[0].capped  # Side pot still uncapped

        round1_main = empty_pot.round_pots[-1].main_pot.amount
        round1_side = empty_pot.round_pots[-1].side_pots[0].amount

        empty_pot.end_betting_round()

        # Round 2
        empty_pot.add_bet("P1", 200, False, 250)  # Bet 200 into side pot
        assert empty_pot.round_pots[-1].main_pot.amount == 1500  # Main pot unchanged
        assert empty_pot.round_pots[-1].side_pots[0].amount == 700  # Previous 500 + 200 from P1

        empty_pot.add_bet("P3", 200, False, 250)  # Call 200
        assert empty_pot.round_pots[-1].main_pot.amount == 1500
        assert empty_pot.round_pots[-1].side_pots[0].amount == 900  # Previous 700 + 200 from P3

        assert empty_pot.round_pots[0].main_pot.amount == round1_main
        assert empty_pot.round_pots[0].side_pots[0].amount == round1_side
        assert empty_pot.total == 2400  # 1500 + 500 + 400

    def test_pots_preserved_across_rounds(self, empty_pot):
        """Ensure previous round pots are unchanged by new round bets."""
        # Round 1: P1 all-in, P2 raises
        empty_pot.add_bet("P1", 1000, True, 1000)  # P1 all-in
        empty_pot.add_bet("P2", 2000, False, 3000)  # P2 calls and raises
        assert empty_pot.round_pots[-1].main_pot.amount == 2000
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        assert empty_pot.round_pots[-1].side_pots[0].amount == 1000
        assert empty_pot.total == 3000  # 2000 + 1000
        
        round1_main = empty_pot.round_pots[-1].main_pot.amount
        round1_side = empty_pot.round_pots[-1].side_pots[0].amount
        
        empty_pot.end_betting_round()
        
        # Round 2: P2 bets 500 more
        empty_pot.add_bet("P2", 500, False, 1000)  # Additional 500
        assert empty_pot.round_pots[-1].main_pot.amount == 2000  # Unchanged
        assert empty_pot.round_pots[-1].side_pots[0].amount == 1500  # 1000 + 500
        assert empty_pot.total == 3500  # 2000 + 500 + 1000
        
        assert empty_pot.round_pots[0].main_pot.amount == round1_main
        assert empty_pot.round_pots[0].side_pots[0].amount == round1_side    

    def test_multiple_side_pots_across_rounds(self, empty_pot):
        """Test preservation with multiple side pots across rounds."""
        # Round 1
        empty_pot.add_bet("P1", 100, False, 1000)
        empty_pot.add_bet("P2", 50, True, 50)
        empty_pot.add_bet("P3", 150, False, 1000)
        assert empty_pot.round_pots[-1].main_pot.amount == 150
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        assert empty_pot.round_pots[-1].side_pots[0].amount == 150
        assert empty_pot.total == 300
        
        round1_main = empty_pot.round_pots[-1].main_pot.amount
        round1_side = empty_pot.round_pots[-1].side_pots[0].amount
        
        empty_pot.end_betting_round()
        
        # Round 2
        empty_pot.add_bet("P1", 200, False, 900)  # Bet 200
        empty_pot.add_bet("P3", 300, False, 800)  # Bet 300 total (call 200 + raise 100)
        assert empty_pot.round_pots[-1].main_pot.amount == 150
        assert empty_pot.round_pots[-1].side_pots[0].amount == 650  # 150 + 200 P1 + 300 P3
        assert empty_pot.total == 800  # 150 + 650
        
        assert empty_pot.round_pots[0].main_pot.amount == round1_main
        assert empty_pot.round_pots[0].side_pots[0].amount == round1_side

    def test_empty_round_after_all_ins(self, empty_pot):
        """Test a new round with no active players after all-ins."""
        # Round 1: All players all-in
        empty_pot.add_bet("P1", 100, True, 100)
        empty_pot.add_bet("P2", 100, True, 100)
        assert empty_pot.round_pots[-1].main_pot.amount == 200
        assert empty_pot.round_pots[-1].main_pot.capped
        assert empty_pot.round_pots[-1].main_pot.active_players == set()
        assert empty_pot.total == 200
        
        round1_main = empty_pot.round_pots[-1].main_pot.amount
        
        empty_pot.end_betting_round()
        
        # Round 2: No active players
        assert empty_pot.round_pots[-1].main_pot.amount == 200
        assert empty_pot.round_pots[-1].main_pot.active_players == set()
        assert len(empty_pot.round_pots[-1].side_pots) == 0
        assert empty_pot.total == 200
        
        # Verify Round 1
        assert empty_pot.round_pots[0].main_pot.amount == round1_main

    def test_multiple_rounds_with_side_pot_capping(self, empty_pot):
        """Test side pot capping across rounds."""
        # Round 1
        empty_pot.add_bet("P1", 300, False, 1000)
        empty_pot.add_bet("P2", 100, True, 100)
        empty_pot.add_bet("P3", 400, True, 400)
        empty_pot.add_bet("P1", 400, False, 700)
        assert empty_pot.round_pots[-1].main_pot.amount == 300
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        assert empty_pot.round_pots[-1].side_pots[0].amount == 600
        assert empty_pot.round_pots[-1].side_pots[0].capped
        assert empty_pot.total == 900
        
        round1_main = empty_pot.round_pots[-1].main_pot.amount
        round1_side = empty_pot.round_pots[-1].side_pots[0].amount
        
        empty_pot.end_betting_round()
        
        # Round 2
        empty_pot.add_bet("P1", 600, True, 600)
        assert empty_pot.round_pots[-1].main_pot.amount == 300
        assert empty_pot.round_pots[-1].side_pots[0].amount == 600
        assert len(empty_pot.round_pots[-1].side_pots) == 2
        assert empty_pot.round_pots[-1].side_pots[1].amount == 600
        assert empty_pot.round_pots[-1].side_pots[1].capped
        assert empty_pot.total == 1500
        
        assert empty_pot.round_pots[0].main_pot.amount == round1_main
        assert empty_pot.round_pots[0].side_pots[0].amount == round1_side


class TestDifferentPotStates:
    """Test betting with different pot states."""
    
    def test_multiple_allin_sequence(self, empty_pot):
        """Test sequence creating multiple capped pots.
        
        Sequence:
        P1: all-in 100
        P2: all-in 200
        P3: all-in 300
        P4: all-in 400
        P5: calls 400
        
        Should create:
        Main pot: 500 (100 × 5)
        Side pot 1: 400 (100 × 4, no P1)
        Side pot 2: 300 (100 × 3, no P1/P2)
        Side pot 3: 100 (100 × 1, no P1/P2/P3)
        """
        current = empty_pot.round_pots[-1]      

        # P1 all-in 100
        empty_pot.add_bet("P1", 100, True, 100)
        assert current.main_pot.amount == 100
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0

        # P2 all-in 200
        empty_pot.add_bet("P2", 200, True, 200)
        assert current.main_pot.amount == 200  # 100 each
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        assert current.side_pots[0].amount == 100  # P2's excess
        
        # P3 all-in 300
        empty_pot.add_bet("P3", 300, True, 300)
        assert current.main_pot.amount == 300  # 100 each
        assert len(empty_pot.round_pots[-1].side_pots) == 2
        assert current.side_pots[0].amount == 200  # 100 each P2/P3
        assert current.side_pots[1].amount == 100  # P3's excess
        
        # P4 all-in 400
        empty_pot.add_bet("P4", 400, True, 400)
        assert current.main_pot.amount == 400  # 100 each
        assert len(empty_pot.round_pots[-1].side_pots) == 3
        assert current.side_pots[0].amount == 300  # 100 each P2/P3/P4
        assert current.side_pots[1].amount == 200  # 100 each P3/P4
        assert current.side_pots[2].amount == 100  # P4's excess
        
        # P5 calls 400
        empty_pot.add_bet("P5", 400, False, 1000)
        assert current.main_pot.amount == 500  # 100 each
        assert len(empty_pot.round_pots[-1].side_pots) == 3
        assert current.side_pots[0].amount == 400  # 100 each P2/P3/P4/P5
        assert current.side_pots[1].amount == 300  # 100 each P3/P4/P5
        assert current.side_pots[2].amount == 200  # 100 each P4/P5

    def test_bet_after_multiple_caps(self, empty_pot):
        """Test betting when there are already multiple capped pots.
        
        Sequence:
        P1: all-in 100
        P2: all-in 200 
        P3: all-in 300
        P4: bets 500 (more than previous all-ins)
        """
        current = empty_pot.round_pots[-1]      

        # Setup multiple capped pots first
        empty_pot.add_bet("P1", 100, True, 100)
        empty_pot.add_bet("P2", 200, True, 200)
        empty_pot.add_bet("P3", 300, True, 300)
        
        # P4 bets more than all previous all-ins
        empty_pot.add_bet("P4", 500, False, 1000)
        
        # Verify distribution across pots
        assert current.main_pot.amount == 400  # 100 each
        assert len(empty_pot.round_pots[-1].side_pots) == 3
        assert current.side_pots[0].amount == 300  # 100 each P2/P3/P4
        assert current.side_pots[1].amount == 200  # 100 each P3/P4
        assert current.side_pots[2].amount == 200  # P4's excess 200

    def test_allin_exactly_matching_previous(self, empty_pot):
        """Test when player goes all-in for exactly same amount as previous all-in.
        
        This tests edge case where we don't want to create unnecessary side pots.
        """
        current = empty_pot.round_pots[-1]      

        # P1 all-in 200
        empty_pot.add_bet("P1", 200, True, 200)
        assert current.main_pot.amount == 200
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0

        # P2 all-in exact same amount
        empty_pot.add_bet("P2", 200, True, 200)
        assert current.main_pot.amount == 400  # 200 each
        assert current.main_pot.capped
        assert len(empty_pot.round_pots[-1].side_pots) == 0  # No side pot needed
        
        # P3 bets more
        empty_pot.add_bet("P3", 500, False, 1000)
        assert current.main_pot.amount == 600  # 200 each
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        assert current.side_pots[0].amount == 300  # P3's excess        

def test_award_to_winners_single_main_pot(mock_players):
    """Test awarding main pot clears it correctly."""
    pot = Pot()
    p1, p2, _ = mock_players
    pot.add_bet(p1.id, 50, False, 100)
    pot.add_bet(p2.id, 50, False, 100)
    assert pot.total == 100

    pot.award_to_winners([p1])
    assert pot.total == 0
    assert pot.round_pots[-1].main_pot.amount == 0
    assert not pot.round_pots[-1].main_pot.eligible_players

def test_award_to_winners_split_main_pot(mock_players):
    """Test splitting main pot clears it."""
    pot = Pot()
    p1, p2, p3 = mock_players
    pot.add_bet(p1.id, 30, False, 100)
    pot.add_bet(p2.id, 30, False, 100)
    pot.add_bet(p3.id, 30, False, 100)
    assert pot.total == 90

    pot.award_to_winners([p1, p2, p3])
    assert pot.total == 0
    assert pot.round_pots[-1].main_pot.amount == 0
    assert not pot.round_pots[-1].main_pot.eligible_players

def test_award_to_winners_side_pot(mock_players):
    """Test awarding a side pot clears it."""
    pot = Pot()
    p1, p2, p3 = mock_players
    pot.add_bet(p1.id, 100, False, 200)
    pot.add_bet(p2.id, 100, False, 200)
    pot.add_bet(p3.id, 50, True, 50)
    assert pot.total == 250
    assert pot.round_pots[-1].main_pot.amount == 150
    assert len(pot.round_pots[-1].side_pots) == 1
    assert pot.round_pots[-1].side_pots[0].amount == 100

    pot.award_to_winners([p1], side_pot_index=0)
    assert pot.round_pots[-1].side_pots[0].amount == 0
    assert not pot.round_pots[-1].side_pots[0].eligible_players
    assert pot.total == 150  # Main pot remains

def test_award_to_winners_no_winners(mock_players):
    """Test no-op when no winners provided."""
    pot = Pot()
    p1, _, _ = mock_players
    pot.add_bet(p1.id, 50, False, 100)
    pot.award_to_winners([])
    assert pot.total == 50  # Pot unchanged
    assert pot.round_pots[-1].main_pot.amount == 50

class TestsFromBettingFlow:
    """Tests at Pot level from Game-level unit tests."""

    def test_basic_call_sequence(self, empty_pot):
        """Test basic sequence: Button calls, SB calls, BB checks."""

        current = empty_pot.round_pots[-1]      

        # post blinds
        empty_pot.add_bet("SB", 5, False, 1000)    
        empty_pot.add_bet("BB", 10, False, 1000)    

        # betting stage
        empty_pot.add_bet("BTN", 10, False, 1000)
        empty_pot.add_bet("SB", 10, False, 995)  # SB calling the big blind $10
        empty_pot.add_bet("BB", 10, False, 990)  # BB checking - not necessary to call add_bet

        assert current.main_pot.amount == 30  # 10 fom each

class TestAntesHandling:
    """Tests for ante-specific functionality in the Pot class."""

    def test_antes_single_round(self, empty_pot):
        """Test antes posted by all players in a single round."""
        current = empty_pot.round_pots[-1]

        # Three players post $2 ante each
        empty_pot.add_bet("P1", 2, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 2, False, 1000, is_ante=True)
        empty_pot.add_bet("P3", 2, False, 1000, is_ante=True)

        assert current.main_pot.amount == 6  # 2 from each
        assert empty_pot.ante_total == 6
        assert current.main_pot.player_antes == {"P1": 2, "P2": 2, "P3": 2}
        assert current.main_pot.player_bets == {"P1": 2, "P2": 2, "P3": 2}
        assert empty_pot.total == 6
        assert empty_pot.total_bets == {"round_1_P1": 2, "round_1_P2": 2, "round_1_P3": 2}
        assert empty_pot.total_antes == {"round_1_P1": 2, "round_1_P2": 2, "round_1_P3": 2}
        assert current.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert current.main_pot.active_players == {"P1", "P2", "P3"}

    def test_antes_reset_across_rounds(self, empty_pot):
        """Test that antes are reset after a betting round ends."""
        current = empty_pot.round_pots[-1]

        # Round 1: Post antes
        empty_pot.add_bet("P1", 2, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 2, False, 1000, is_ante=True)
        assert empty_pot.ante_total == 4
        assert current.main_pot.player_antes == {"P1": 2, "P2": 2}

        empty_pot.end_betting_round()

        # Round 2: Antes should be cleared
        current = empty_pot.round_pots[-1]
        assert empty_pot.ante_total == 0
        assert current.main_pot.player_antes == {}
        assert empty_pot.total_antes == {}
        assert current.main_pot.amount == 4  # Carried over from Round 1
        assert empty_pot.total == 4      

    def test_antes_with_betting(self, empty_pot):
        """Test antes followed by normal betting."""
        current = empty_pot.round_pots[-1]
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 1000, is_ante=True)
        assert empty_pot.ante_total == 2
        assert current.main_pot.amount == 2
        empty_pot.add_bet("P1", 11, False, 999)  # Total 11 (1 ante + 10 bet)
        empty_pot.add_bet("P2", 11, False, 999)  # Total 11 (1 ante + 10 bet)
        assert current.main_pot.amount == 24  # 2 antes + 22 bets (11 each)
        assert empty_pot.ante_total == 2
        assert current.main_pot.player_antes == {"P1": 1, "P2": 1}
        assert current.main_pot.player_bets == {"P1": 12, "P2": 12}
        assert empty_pot.total == 24
        assert empty_pot.total_bets == {"round_1_P1": 12, "round_1_P2": 12}
        assert empty_pot.total_antes == {"round_1_P1": 1, "round_1_P2": 1}
        assert current.main_pot.eligible_players == {"P1", "P2"}
        assert current.main_pot.active_players == {"P1", "P2"}

class TestBringInHandling:
    """Tests for Stud-style bring-in bets."""

    def test_bring_in_basic(self, empty_pot):
        """Test basic bring-in followed by calls."""
        current = empty_pot.round_pots[-1]
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P3", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P1", 4, False, 999)
        empty_pot.add_bet("P2", 4, False, 999)
        empty_pot.add_bet("P3", 4, False, 999)
        assert current.main_pot.amount == 15
        assert empty_pot.ante_total == 3
        assert current.main_pot.player_antes == {"P1": 1, "P2": 1, "P3": 1}
        assert current.main_pot.player_bets == {"P1": 5, "P2": 5, "P3": 5}
        assert empty_pot.total == 15
        assert empty_pot.total_bets == {"round_1_P1": 5, "round_1_P2": 5, "round_1_P3": 5}
        assert empty_pot.total_antes == {"round_1_P1": 1, "round_1_P2": 1, "round_1_P3": 1}
        assert current.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert current.main_pot.active_players == {"P1", "P2", "P3"}

    def test_bring_in_with_all_in(self, empty_pot):
        """Test bring-in with one player all-in short."""
        current = empty_pot.round_pots[-1]
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 4, is_ante=True)
        empty_pot.add_bet("P3", 1, False, 1000, is_ante=True)
        assert current.main_pot.amount == 3
        empty_pot.add_bet("P1", 4, False, 999)
        assert current.main_pot.amount == 7 # 3 from antes, and 4 more from P1
        empty_pot.add_bet("P2", 3, True, 3)
        # at this point, we should have split the main pot since we had a call for less because of stack size
        # it should contain the 3 antes, and then 3 from each of P1 and P2 since P2 was 'short'
        assert current.main_pot.amount == 9 # 3 from antes, 3 more from P1, and 3 more from P2 who is all-in
        # then there shold be a side pot of $1 for the extra $1 from P1.   It is not capped
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 1
        assert not current.side_pots[0].capped
        assert current.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert current.side_pots[0].eligible_players == {"P1"}  # P2 has not yet contributed to the side pot, so is not there.
        # P3 now calls the bring-in of $4
        empty_pot.add_bet("P3", 4, False, 999)
        assert current.main_pot.amount == 12 # 3 from antes, 3 from P1, 3 from P2, and 3 from P3
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 4 # includes the ante
        # the side pot gets the extra $1 from P3's call of the bring-in
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 2
        assert empty_pot.total == 14
        assert empty_pot.total_bets == {"round_1_P1": 5, "round_1_P2": 4, "round_1_P3": 5}
        assert empty_pot.total_antes == {"round_1_P1": 1, "round_1_P2": 1, "round_1_P3": 1}
        assert current.main_pot.eligible_players == {"P1", "P2", "P3"}
        assert current.side_pots[0].eligible_players == {"P1", "P3"}  # P1 and P3 have contributed

    def test_bring_in_with_raise(self, empty_pot):
        """Test bring-in followed by a raise and all-in."""
        current = empty_pot.round_pots[-1]
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P3", 1, False, 10, is_ante=True)
        assert current.main_pot.amount == 3
        empty_pot.add_bet("P1", 4, False, 999)
        assert current.main_pot.amount == 7 # 3 from antes, and 4 more from P1
        empty_pot.add_bet("P2", 10, False, 999)
        assert current.main_pot.amount == 17 # 3 from antes, 4 from P1, and 10 from P2
        # P3 is calling for less - $9 instead of the required $10
        empty_pot.add_bet("P3", 9, True, 9)
        assert current.main_pot.amount == 25 # 3 from antes, 4 from P1, and 9 from P2, 9 from P3
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 1 # P3's excess         
        # P1 calls the $10
        empty_pot.add_bet("P1", 10, False, 996)
        assert current.main_pot.amount == 30
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 2 # P3 and P1's excess         
        assert empty_pot.total == 32
        assert empty_pot.total_bets == {"round_1_P1": 11, "round_1_P2": 11, "round_1_P3": 10}
        assert empty_pot.total_antes == {"round_1_P1": 1, "round_1_P2": 1, "round_1_P3": 1}
        assert current.main_pot.eligible_players == {"P1", "P2", "P3"}   
        assert current.side_pots[0].eligible_players == {"P1", "P2"}  # P1 and P2 have contributed

class TestStudPokerScenarios:
    """Tests simulating Stud poker multi-street dynamics."""

    def test_stud_third_to_fourth_street(self, empty_pot):
        """Test Stud transition from Third to Fourth Street with side pot."""
        current = empty_pot.round_pots[-1]

        # Antes
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 51, is_ante=True)
        empty_pot.add_bet("P3", 1, False, 1000, is_ante=True)

        # Third Street: P1 bring-in $3, P2 all-in $50, P3 calls, P1 calls
        empty_pot.add_bet("P1", 4, False, 999)
        empty_pot.add_bet("P2", 50, True, 50)
        empty_pot.add_bet("P3", 50, False, 999)
        empty_pot.add_bet("P1", 50, False, 996)
        assert current.main_pot.amount == 153  # 50 each + antes
        assert current.main_pot.capped
        assert len(current.side_pots) == 0

        empty_pot.end_betting_round()

        # Fourth Street: P1 bets $100, P3 calls
        current = empty_pot.round_pots[-1]
        empty_pot.add_bet("P1", 100, False, 946)
        empty_pot.add_bet("P3", 100, False, 949)
        assert current.main_pot.amount == 153  # Unchanged
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 200  # 100 each P1/P3
        assert not current.side_pots[0].capped    

    def test_stud_multi_all_in(self, empty_pot):
        """Test Stud with multiple all-ins across streets."""
        current = empty_pot.round_pots[-1]

        # Antes
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 31, is_ante=True)
        empty_pot.add_bet("P3", 1, False, 151, is_ante=True)

        # Third Street
        empty_pot.add_bet("P1", 4, False, 999)    # Bring-in
        empty_pot.add_bet("P2", 30, True, 30)     # All-in
        empty_pot.add_bet("P3", 150, True, 150)   # All-in
        empty_pot.add_bet("P1", 150, False, 996)
        assert current.main_pot.amount == 93      # 30 each + antes
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 240 # 120 each P1/P3
        assert current.side_pots[0].capped        

class TestEdgeCases:
    """Tests for unusual or boundary conditions."""        

    def test_ante_and_blinds_mixed(self, empty_pot):
        """Test mixed ante and blinds scenario."""
        current = empty_pot.round_pots[-1]

        # Antes
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P3", 1, False, 1000, is_ante=True)

        # Blinds (SB/BB)
        empty_pot.add_bet("P2", 5, False, 999)   # 5 SB
        empty_pot.add_bet("P3", 10, False, 999)  # 10 BB

        # P1 calls BB
        empty_pot.add_bet("P1", 10, False, 999)  # 10
        # P2 calls 
        empty_pot.add_bet("P2", 10, False, 999)  # 10        
        assert current.main_pot.amount == 33      # $1 ante + $10 from each
        assert empty_pot.ante_total == 3
        assert current.main_pot.player_antes == {"P1": 1, "P2": 1, "P3": 1}
        assert current.main_pot.player_bets == {"P1": 11, "P2": 11, "P3": 11}

    def test_incomplete_bring_in_all_in(self, empty_pot):
        """Test player all-in for less than bring-in amount."""
        current = empty_pot.round_pots[-1]

        # Antes
        empty_pot.add_bet("P1", 1, False, 2, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 1000, is_ante=True)

        # P1 all-in $2 total (1 ante + 1), less than $3 bring-in
        empty_pot.add_bet("P1", 1, True, 1)
        empty_pot.add_bet("P2", 3, False, 999)  # Bring-in $3 
        assert current.main_pot.amount == 4      # 2 P1 + 2 P2
        assert current.main_pot.capped
        assert current.main_pot.cap_amount == 2
        assert len(current.side_pots) == 1
        assert current.side_pots[0].amount == 2 # 2 extra from P2
     

    def test_zero_amount_bet_after_ante(self, empty_pot):
        """Test zero-amount bet after antes (e.g., check)."""
        current = empty_pot.round_pots[-1]

        # Antes
        empty_pot.add_bet("P1", 1, False, 1000, is_ante=True)
        empty_pot.add_bet("P2", 1, False, 1000, is_ante=True)

        # P1 tries to bet 0 more (simulating check)
        empty_pot.add_bet("P1", 0, False, 999)  # Total still 1
        assert current.main_pot.amount == 2
        assert current.main_pot.player_bets == {"P1": 1, "P2": 1}
        assert empty_pot.total == 2        