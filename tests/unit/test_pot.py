"""Unit tests for Pot class."""
import pytest
from generic_poker.game.pot import Pot, PotBet, ActivePotNew, BetInfo

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
        assert pot.player_bets == [PotBet("P1", 100)]
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
        assert pot.player_bets == [PotBet("P1", 100)]
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
        assert pot.player_bets == [PotBet("P2", 100)]
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
        assert pot.player_bets == [PotBet("P2", 100)]
        assert len(empty_pot.round_pots) == 1  # Should still be in first round

    def test_short_bet_triggers_restructure(self, empty_pot):
        """Bet cannot meet cap amount, triggers restructure."""
        current = empty_pot.round_pots[-1]
        pot = current.main_pot
        pot.current_bet = 300
        pot.cap_amount = 300
        pot.capped = True
        pot.player_bets = [PotBet("P1", 300)]
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
        side_pot = ActivePotNew(
            amount=300,
            current_bet=300,
            eligible_players={"P1"},
            active_players={"P1"},
            excluded_players=set(),
            player_bets=[PotBet("P1", 300)],
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
        assert side_pot.player_bets == [PotBet("P1", 300), PotBet("P2", 300)]
        assert side_pot.eligible_players == {"P1", "P2"}
        
    def test_multiple_uncapped_side_pots(self, empty_pot):
        """Multiple uncapped side pots available."""
        current = empty_pot.round_pots[-1]

        # Create two side pots with different bet levels
        side_pot1 = ActivePotNew(
            amount=200,
            current_bet=200,
            eligible_players={"P1"},
            active_players={"P1"},
            excluded_players=set(),
            player_bets=[PotBet("P1", 200)],
            order=1
        )
        side_pot2 = ActivePotNew(
            amount=100,
            current_bet=100,
            eligible_players={"P1"},
            active_players={"P1"},
            excluded_players=set(),
            player_bets=[PotBet("P1", 100)],
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
        assert side_pot1.player_bets == [PotBet("P1", 200), PotBet("P2", 200)]
        assert side_pot2.player_bets == [PotBet("P1", 100), PotBet("P2", 100)]

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
        assert side_pot.player_bets == [PotBet("P1", 300)]
        
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
        assert side_pot.player_bets == [PotBet("P1", 300)]

class TestRestructurePot:
    """Test cases for _restructure_pot method."""
    
    def test_simple_restructure(self, empty_pot):
        """Simple pot restructure with one short stack."""
        current = empty_pot.round_pots[-1]

        pot = current.main_pot
        pot.current_bet = 300
        pot.amount = 400     # P1 has put in 100, P2 has put in 300
        pot.player_bets = [
            PotBet("P1", 100),  # P1 had bet 100
            PotBet("P2", 300)   # P2 had bet 300
        ]
        pot.eligible_players = {"P1", "P2"}
        pot.active_players = {"P1", "P2"}
        
        bet = BetInfo(
            player_id="P1",
            amount=100,  # Can only add 100 more
            is_all_in=False,
            stack_before=100,
            prev_total=100,
            new_total=200
        )
        
        empty_pot._restructure_pot(pot, bet, 100)
        
        # Main pot: P1: 200, P2: 200
        assert pot.amount == 400
        assert pot.current_bet == 200
        assert pot.cap_amount == 200
        assert pot.capped
        assert len(pot.player_bets) == 2
        assert any(pb.player_id == "P1" and pb.amount == 200 for pb in pot.player_bets)
        assert any(pb.player_id == "P2" and pb.amount == 200 for pb in pot.player_bets)
        
        # Side pot: P2's excess 100
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        side_pot = current.side_pots[0]
        assert side_pot.amount == 100
        assert side_pot.eligible_players == {"P2"}
        assert not side_pot.capped

    def test_restructure_with_multiple_excess(self, empty_pot):
        """Restructure when multiple players have excess amounts."""
        current = empty_pot.round_pots[-1]

        pot = current.main_pot
        pot.current_bet = 300
        pot.amount = 700  # P1: 100, P2: 300, P3: 300
        pot.player_bets = [
            PotBet("P1", 100),
            PotBet("P2", 300),
            PotBet("P3", 300)
        ]
        pot.eligible_players = {"P1", "P2", "P3"}
        pot.active_players = {"P1", "P2", "P3"}
        
        bet = BetInfo(
            player_id="P1",
            amount=100,
            is_all_in=False,
            stack_before=100,
            prev_total=100,
            new_total=200
        )
        
        empty_pot._restructure_pot(pot, bet, 100)
        
        # Main pot: P1,P2,P3 all 200
        assert pot.amount == 600
        assert pot.current_bet == 200
        assert pot.cap_amount == 200
        assert pot.capped
        assert len(pot.player_bets) == 3
        assert any(pb.player_id == "P1" and pb.amount == 200 for pb in pot.player_bets)
        assert any(pb.player_id == "P2" and pb.amount == 200 for pb in pot.player_bets)
        assert any(pb.player_id == "P3" and pb.amount == 200 for pb in pot.player_bets)
        
        # Side pot: P2,P3 excess 100 each
        assert len(empty_pot.round_pots[-1].side_pots) == 1
        side_pot = current.side_pots[0]
        assert side_pot.amount == 200
        assert side_pot.eligible_players == {"P2", "P3"}
        assert not side_pot.capped

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
        
        empty_pot.end_betting_round()
        round1_total = empty_pot.round_pots[0].round_total
        
        # Round 2
        empty_pot.add_bet("P1", 950, False, 250)   # Bet 200 more into side pot
        assert empty_pot.round_pots[-1].main_pot.amount == 1500  # Main pot unchanged
        assert empty_pot.round_pots[-1].side_pots[0].amount == 700  # Previous 500 + 200 from P1
        
        empty_pot.add_bet("P3", 950, False, 250)   # Call 200
        assert empty_pot.round_pots[-1].main_pot.amount == 1500  # Main pot unchanged
        assert empty_pot.round_pots[-1].side_pots[0].amount == 900  # Previous 700 + 200 from P3
        
        # Verify Round 1 remained unchanged
        assert empty_pot.round_pots[0].round_total == round1_total

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