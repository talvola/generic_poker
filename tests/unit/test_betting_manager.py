import pytest
from generic_poker.game.betting import (
    BettingManager, NoLimitBettingManager, LimitBettingManager, 
    PotLimitBettingManager, BetType, PlayerBet
)
from generic_poker.config.loader import BettingStructure
from generic_poker.game.table import Player, Table

import logging
import sys

logger = logging.getLogger(__name__)

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
    table = Table(
        max_players=6,
        min_buyin=500,
        max_buyin=500
    )    
    return NoLimitBettingManager(table, small_blind=5, big_blind=10)

@pytest.fixture
def limit_betting():
    """Create a Limit betting manager with small bet 10, big bet 20."""
    table = Table(
        max_players=6,
        min_buyin=500,
        max_buyin=500
    )     
    return LimitBettingManager(table, small_bet=10, big_bet=20)

# def test_basic_no_limit_betting(nl_betting):
#     """Test basic no-limit betting sequence without all-ins."""
#     # Setup initial state (simulate posting blinds)
#     nl_betting.place_bet("SB", 5, 500, is_forced=True)  # Small blind
#     nl_betting.place_bet("BB", 10, 500, is_forced=True) # Big blind
    
#     # Verify initial state
#     assert nl_betting.get_total_pot() == 15
#     assert nl_betting.current_bet == 10
    
#     # BTN calls
#     nl_betting.place_bet("BTN", 10, 500)
#     assert nl_betting.get_total_pot() == 25
#     assert nl_betting.current_bets["BTN"].amount == 10
    
#     # SB completes
#     nl_betting.place_bet("SB", 10, 495)  # 495 because already posted 5
#     assert nl_betting.get_total_pot() == 30
#     assert nl_betting.current_bets["SB"].amount == 10

# def test_simple_all_in_nl(nl_betting):
#     """Test simple all-in and call sequence."""
#     # SB with 5000 goes all-in
#     nl_betting.place_bet("SB", 5000, 5000)
#     assert nl_betting.get_total_pot() == 5000
#     assert nl_betting.get_main_pot_amount() == 5000
#     assert nl_betting.get_side_pot_count() == 0
    
#     # BB with 1000 calls all-in
#     nl_betting.place_bet("BB", 1000, 1000)
    
#     # Should create:
#     # - Main pot: 2000 (1000 each that both can win)
#     # - Side pot: 4000 (SB's excess)
#     assert nl_betting.get_main_pot_amount() == 2000, "Main pot should have 1000 from each"
#     assert nl_betting.get_side_pot_count() == 1, "Should have one side pot"
#     assert nl_betting.get_side_pot_amount(0) == 4000, "Side pot should have SB's excess"
#     assert nl_betting.get_total_pot() == 6000

# """Updated test cases for betting managers to test min/max bets correctly."""

# def test_nl_bet_size_restrictions(nl_betting):
#     """Test bet size restrictions in no-limit betting."""
#     # Post blinds
#     nl_betting.place_bet("SB", 5, 500, is_forced=True)
#     nl_betting.place_bet("BB", 10, 500, is_forced=True)
    
#     # In no-limit, min bet is amount to call
#     assert nl_betting.get_min_bet("UTG", BetType.BIG) == 10  # Call BB
    
#     # Using get_min_raise to get minimum raise amount
#     assert nl_betting.get_min_raise("UTG") == 20  # BB + BB
    
#     # Max bet is full stack
#     assert nl_betting.get_max_bet("UTG", BetType.BIG, 500) == 500  # Full stack
    
#     # UTG raises to 30
#     nl_betting.place_bet("UTG", 30, 500)
    
#     # Min bet is amount to call the current bet
#     assert nl_betting.get_min_bet("MP", BetType.BIG) == 30
    
#     # Min raise is now previous raise amount
#     raise_size = 30 - 10  # 20
#     assert nl_betting.get_min_raise("MP") == 50  # 30 + 20
    
#     # Max bet is full stack
#     assert nl_betting.get_max_bet("MP", BetType.BIG, 500) == 500  # Full stack
    
#     # MP raises to 100
#     nl_betting.place_bet("MP", 100, 500)
    
#     # Min bet is amount to call
#     assert nl_betting.get_min_bet("CO", BetType.BIG) == 100
    
#     # Min raise is current bet + previous raise
#     raise_size = 100 - 30  # 70
#     assert nl_betting.get_min_raise("CO") == 170  # 100 + 70
    
#     # Test stack constraints on max bet
#     assert nl_betting.get_max_bet("CO", BetType.BIG, 150) == 150  # Limited by stack
    
#     # Test all-in for less than min raise
#     nl_betting.place_bet("CO", 150, 150)  # All-in for less than min raise
    
#     # After all-in for less than min, min raise should account for last full raise of $70,
#     # not the short raise of $50 from CO
#     assert nl_betting.get_min_raise("BTN") == 220  # 150 + 70
    
#     # Min bet is still amount to call
#     assert nl_betting.get_min_bet("BTN", BetType.BIG) == 150


# def test_pot_limit_bet_size_restrictions(pot_limit_betting):
#     """Test bet size restrictions in pot-limit betting."""
#     # Post blinds
#     pot_limit_betting.place_bet("SB", 5, 500, is_forced=True)
#     pot_limit_betting.place_bet("BB", 10, 500, is_forced=True)
    
#     # Initial pot is 15 (5 + 10)
#     # Min bet is current bet (10)
#     # Min raise would be current bet (10) + BB (10) = 20
#     # Max bet is current bet (10) + pot after call (15 + 10) = 35
#     assert pot_limit_betting.get_min_bet("UTG", BetType.BIG) == 10, "Min bet is current bet (10)"
#     assert pot_limit_betting.get_additional_required("UTG") == 10, "UTG needs to add 10 chips"
#     assert pot_limit_betting.get_min_raise("UTG") == 20, "Min raise is current bet (10) + BB (10)"
#     assert pot_limit_betting.get_max_bet("UTG", BetType.BIG, 500) == 35, "Pot-limited max"
    
#     # UTG bets max: 35
#     pot_limit_betting.place_bet("UTG", 35, 500)
    
#     # Pot is now 50 (15 + 35)
#     # Min bet is current bet (35)
#     # Min raise would be current bet (35) + last raise (25) = 60
#     # Max bet is current bet (35) + pot after call (50 + 35) = 120
#     assert pot_limit_betting.get_min_bet("MP", BetType.BIG) == 35, "Min bet is current bet (35)"
#     assert pot_limit_betting.get_additional_required("MP") == 35, "MP needs to add 35 chips"
#     assert pot_limit_betting.get_min_raise("MP") == 60, "Min raise is current bet (35) + last raise (25)"
#     assert pot_limit_betting.get_max_bet("MP", BetType.BIG, 500) == 120, "Pot-limited max"
    
#     # MP raises to 100
#     pot_limit_betting.place_bet("MP", 100, 500)
    
#     # Pot is now 150 (50 + 100)
#     # Min bet is current bet (100)
#     # Min raise would be current bet (100) + last raise (65) = 165
#     # Max bet is current bet (100) + pot after call (150 + 100) = 350
#     assert pot_limit_betting.get_min_bet("CO", BetType.BIG) == 100, "Min bet is current bet (100)"
#     assert pot_limit_betting.get_additional_required("CO") == 100, "CO needs to add 100 chips"
#     assert pot_limit_betting.get_min_raise("CO") == 165, "Min raise is current bet (100) + last raise (65)"
#     assert pot_limit_betting.get_max_bet("CO", BetType.BIG, 500) == 350, "Pot-limited max"
    
#     # Test stack constraints
#     assert pot_limit_betting.get_max_bet("CO", BetType.BIG, 200) == 200, "Limited by stack"
    
#     # Test that multi-way action increases pot-limit properly
#     pot_limit_betting.place_bet("CO", 200, 500)
#     pot_limit_betting.place_bet("BTN", 200, 500)
    
#     # Pot is now 550 (150 + 200 + 200)
#     # Min bet is current bet (200)
#     # Min raise would be current bet (200) + last raise (100) = 300
#     # After call, pot would be 745 (550 + 195)
#     # Theoretically, max raise would be 200 + 745 = 945
#     # But SB only has 500 chips remaining (5 already in pot)
#     # So actual max bet is limited to 505 (not 945)
#     assert pot_limit_betting.get_min_bet("SB", BetType.BIG) == 200, "Min bet is current bet (200)"
#     assert pot_limit_betting.get_additional_required("SB") == 195, "SB needs to add 195 chips (already has 5 in)"
#     assert pot_limit_betting.get_min_raise("SB") == 300, "Min raise is current bet (200) + last raise (100)"
#     assert pot_limit_betting.get_max_bet("SB", BetType.BIG, 500) == 505, "Limited by stack"

def test_limit_bet_sizes(limit_betting):
    """Test bet size restrictions in limit betting."""
    # Post blinds
    limit_betting.place_bet("SB", 5, 500, is_forced=True)
    limit_betting.place_bet("BB", 10, 500, is_forced=True)
    
    # In limit, first two rounds use small bet (10)
    assert limit_betting.get_min_bet("BTN", BetType.BIG) == 10, "Min bet is current bet (10)"
    assert limit_betting.get_additional_required("BTN") == 10, "BTN needs to add 10 chips"
    assert limit_betting.get_max_bet("BTN", BetType.BIG, 500) == 20, "Max bet is current bet (10) + small bet (10)"
    
    # Make some bets to get to next round
    limit_betting.place_bet("BTN", 10, 500)
    limit_betting.place_bet("SB", 10, 495)
    limit_betting.place_bet("BB", 10, 490)
    limit_betting.new_round()
    
    # Later rounds use big bet (20)
    limit_betting.betting_round = 2  # Simulate later round
    assert limit_betting.get_min_bet("BTN", BetType.BIG) == 0, "No current bet"
    assert limit_betting.get_additional_required("BTN") == 0, "No additional required"
    assert limit_betting.get_max_bet("BTN", BetType.BIG, 500) == 20, "Max is big bet (20)"

def test_limit_min_raise_progression(limit_betting):
    """Test minimum raise requirements at each step."""
    # Post blinds
    limit_betting.place_bet("SB", 5, 500, is_forced=True)
    limit_betting.place_bet("BB", 10, 500, is_forced=True)
    
    # At this point:
    # - Current bet is 10 (BB)
    # - No raises yet
    assert limit_betting.get_min_bet("BTN", BetType.SMALL) == 10, "Minimum bet is current bet ($10)"
    assert limit_betting.get_additional_required("BTN") == 10, "BTN needs to add $10 to call"
    assert limit_betting.get_max_bet("BTN", BetType.SMALL, 500) == 20, "Max bet is current bet (10) + BB (10)"
    
    # BTN raises to 20
    limit_betting.place_bet("BTN", 20, 500, BetType.SMALL)
    
    # Now:
    # - Current bet is 20
    # - Last raise was 10 (20 - 10)
    assert limit_betting.get_min_bet("SB", BetType.SMALL) == 20, "Min bet is current bet ($20)"
    assert limit_betting.get_additional_required("SB") == 15, "SB needs to add $15 to call (already has $5 in)"
    assert limit_betting.get_min_raise("SB") == 30, "Min raise is current bet (20) + BB (10)"
    
    # SB raises to 30
    limit_betting.place_bet("SB", 30, 495, BetType.SMALL)
    
    # Now:
    # - Current bet is 30
    # - Another raise of 10
    assert limit_betting.get_min_bet("BB", BetType.SMALL) == 30, "Min bet is current bet ($30)"
    assert limit_betting.get_additional_required("BB") == 20, "BB needs to add $20 to call (already has $10 in)"
    assert limit_betting.get_min_raise("BB") == 40, "Min raise is current bet (30) + BB (10)"
    
    # BB caps it at 40
    limit_betting.place_bet("BB", 40, 490, BetType.SMALL)
    
    # Now:
    # - Current bet is 40
    # - Betting is capped
    assert limit_betting.get_min_bet("BTN", BetType.BIG) == 40, "Min bet is current bet ($40)"
    assert limit_betting.get_additional_required("BTN") == 20, "BTN needs to add $20 to call (already has $20 in)"
    # In limit hold'em, typically only 3-4 raises are allowed per round
    # BTN shouldn't be able to raise further

# def test_nl_min_raise_progression(nl_betting):
#     """Test minimum raise requirements at each step."""
#     # Post blinds
#     nl_betting.place_bet("SB", 5, 500, is_forced=True)
#     nl_betting.place_bet("BB", 10, 500, is_forced=True)
    
#     # At this point:
#     # - Current bet is 10 (BB)
#     # - No raises yet
#     assert nl_betting.get_min_bet("BTN", BetType.SMALL) == 10, "Min bet is current bet (10)"
#     assert nl_betting.get_additional_required("BTN") == 10, "BTN needs to add 10 chips"
#     assert nl_betting.get_min_raise("BTN") == 20, "Min raise is current bet (10) + BB (10)"
    
#     # BTN min-raises to 20.   Call of $10, raise of $10 - so next raise must be $20.
#     nl_betting.place_bet("BTN", 20, 500, BetType.SMALL)
#     # Now:
#     # - Current bet is 20
#     # - Last raise was 10 (20 - 10)
#     assert nl_betting.get_min_bet("SB", BetType.SMALL) == 20, "Min bet is current bet (20)"
#     assert nl_betting.get_additional_required("SB") == 15, "SB needs to add 15 chips (already has 5 in)"
#     assert nl_betting.get_min_raise("SB") == 30, "Min raise is current bet (20) + previous raise (10)"
    
#     # SB raises to 50 (a raise of 30)
#     nl_betting.place_bet("SB", 50, 495)
#     # Now:
#     # - Current bet is 50
#     # - Last raise was 30 (50 - 20)
#     assert nl_betting.get_min_bet("BB", BetType.SMALL) == 50, "Min bet is current bet (50)"
#     assert nl_betting.get_additional_required("BB") == 40, "BB needs to add 40 chips (already has 10 in)"
#     assert nl_betting.get_min_raise("BB") == 80, "Min raise is current bet (50) + previous raise (30)"
    
#     # BB re-raises to 100 (a raise of 50)
#     nl_betting.place_bet("BB", 100, 490)
#     # Now:
#     # - Current bet is 100
#     # - Last raise was 50 (100 - 50)
#     assert nl_betting.get_min_bet("BTN", BetType.SMALL) == 100, "Min bet is current bet (100)"
#     assert nl_betting.get_additional_required("BTN") == 80, "BTN needs to add 80 chips (already has 20 in)"
#     assert nl_betting.get_min_raise("BTN") == 150, "Min raise is current bet (100) + previous raise (50)"

# def test_nl_bet_size_validation(nl_betting):
#     """Test no-limit bet size validation."""
#     nl_betting.place_bet("SB", 5, 500, is_forced=True)
#     nl_betting.place_bet("BB", 10, 500, is_forced=True)
    
#     # Min raise should be BB size (10)
#     min_bet = nl_betting.get_min_bet("BTN", BetType.BIG)
#     assert min_bet == 20  # Current bet (10) + min raise (10)
    
#     # Can raise up to stack size
#     max_bet = nl_betting.get_max_bet("BTN", BetType.BIG, 500)
#     assert max_bet == 500
    
#     # After a larger raise, min raise increases
#     nl_betting.place_bet("BTN", 50, 500)  # Raise to 50
#     min_bet = nl_betting.get_min_bet("SB", BetType.BIG)
#     assert min_bet == 90  # Current bet (50) + previous raise (40)

# def test_nl_bet_size_validation(nl_betting):
#     """Test no-limit bet size validation."""
#     nl_betting.place_bet("SB", 5, 500, is_forced=True)
#     nl_betting.place_bet("BB", 10, 500, is_forced=True)
    
#     min_bet = nl_betting.get_min_bet("BTN", BetType.BIG)
#     assert min_bet == 10  # Current bet (10)
    
#     # Min raise should be BB size (10) + raise size (10)
#     min_raise = nl_betting.get_min_raise("BTN")
#     assert min_raise == 20  # Current bet (10) + min raise (10)
    
#     # Can raise up to stack size
#     max_bet = nl_betting.get_max_bet("BTN", BetType.BIG, 500)
#     assert max_bet == 500
    
#     # After a larger raise, min raise increases
#     nl_betting.place_bet("BTN", 50, 500)  # Raise to 50
#     min_bet = nl_betting.get_min_bet("SB", BetType.BIG)
#     assert min_bet == 50  # Current bet (50)
#     min_raise = nl_betting.get_min_raise("SB")
#     assert min_raise == 90  # Current bet (50) + previous raise (40)    

# def test_all_in_side_pot_creation(nl_betting):
#     """Test side pot creation with all-in bets."""
#     # SB with 5000 goes all-in
#     nl_betting.place_bet("SB", 5000, 5000)
#     assert nl_betting.get_total_pot() == 5000
#     assert nl_betting.get_main_pot_amount() == 5000
#     assert nl_betting.get_side_pot_count() == 0
    
#     # BB with 1000 calls all-in
#     nl_betting.place_bet("BB", 1000, 1000)
    
#     # Should create:
#     # - Main pot: 2000 (1000 each that both can win)
#     # - Side pot: 4000 (SB's excess that only they can win)
#     assert nl_betting.get_main_pot_amount() == 2000, "Main pot should contain amount both players can win"
#     assert nl_betting.get_side_pot_count() == 1, "Should create side pot for excess"
#     assert nl_betting.get_side_pot_amount(0) == 4000, "Side pot should contain SB's excess"
#     assert nl_betting.get_total_pot() == 6000 

# this test should be move to Game class test
# def test_all_in_return(nl_betting):
#     """Test returning excess chips when calling an all-in bet."""
#     # Setup without blinds for clarity
#     # SB with 5000, BB with 1000
#     nl_betting.place_bet("SB", 5000, 5000)  # SB goes all-in
#     assert nl_betting.get_total_pot() == 5000
    
#     # BB calls with their entire 1000
#     nl_betting.place_bet("BB", 1000, 1000)  # BB calls all-in
    
#     # Should only create pot of 2000 (1000 from each)
#     assert nl_betting.get_total_pot() == 2000
#     assert nl_betting.get_main_pot_amount() == 2000
#     assert nl_betting.get_side_pot_count() == 0

# def test_side_pots_different_stacks(nl_betting):
#     """Test side pot creation with different stack sizes."""
#     # Initial stacks:
#     # P1: 1000
#     # P2: 500
#     # P3: 250
#     # P4: 100
    
#     # P1 raises to 400
#     nl_betting.place_bet("P1", 400, 1000)
#     assert nl_betting.get_total_pot() == 400
#     assert nl_betting.get_main_pot_amount() == 400
#     assert nl_betting.get_side_pot_count() == 0
    
#     # P2 calls 400
#     nl_betting.place_bet("P2", 400, 500)
#     assert nl_betting.get_total_pot() == 800
#     assert nl_betting.get_main_pot_amount() == 800
#     assert nl_betting.get_side_pot_count() == 0
    
#     # P3 all-in for 250
#     nl_betting.place_bet("P3", 250, 250)
#     assert nl_betting.current_bets["P3"].is_all_in

#     # After P3's all-in:
#     # Main pot: $750 ($250 × 3) - capped at 250
#     # Side pot A: $300 ($150 excess from P1 and P2)
#     assert nl_betting.get_main_pot_amount() == 750, "Main pot should have $250 from each"
#     assert nl_betting.get_side_pot_count() == 1
#     assert nl_betting.get_side_pot_amount(0) == 300, "Side pot should have $150 each from P1,P2"
    
#     # P4 all-in for 100
#     nl_betting.place_bet("P4", 100, 100)
#     assert nl_betting.current_bets["P4"].is_all_in

#     # After P4's all-in:
#     # Main pot: $400 ($100 × 4)
#     # Two side pots totaling $750 ($450 + $300)
#     assert nl_betting.get_main_pot_amount() == 400, "Main pot should have $100 from each"
#     assert nl_betting.get_side_pot_count() == 2, "Should have two side pots"
    
#     # Verify side pots exist with correct amounts and eligibility
#     assert nl_betting.get_side_pot_amount(0) == 300, "Should have a $300 side pot for P1,P2"
#     assert nl_betting.get_side_pot_amount(1) == 450, "Should have a $450 side pot for P1,P2,P3"
    
#     # Total pot should match all bets
#     assert nl_betting.get_total_pot() == 1150, "Total should be 400 + 400 + 250 + 100" 

# def test_pot_limit_max_bet(pot_limit_betting):
#     """Test pot-limit betting restrictions."""
#     # Post blinds
#     pot_limit_betting.place_bet("SB", 5, 500, is_forced=True)
#     pot_limit_betting.place_bet("BB", 10, 500, is_forced=True)
    
#     # Calculating BTN's max bet:
#     # Current pot = 15
#     # To call = 10
#     # Pot after call = 25 (15 + 10)
#     # Max raise = 25 (pot size after call)
#     # Total max bet = current bet (10) + max raise (25) = 35
#     max_bet = pot_limit_betting.get_max_bet("BTN", BetType.BIG, 500)
#     assert max_bet == 35, "Max bet should be current bet (10) + pot size after call (25)"
    
#     # Make a pot-sized raise
#     pot_limit_betting.place_bet("BTN", 35, 500)
    
#     # Calculating SB's max bet:
#     # Current pot = 50 (15 + BTN's 35)
#     # To call = 30 (from 5 to 35)
#     # Pot after call = 80 (50 + 30)
#     # Max raise = 80 (pot size after call)
#     # Total max bet = current bet (35) + max raise (80) = 115
#     max_bet = pot_limit_betting.get_max_bet("SB", BetType.BIG, 495)
#     assert max_bet == 115, "Max bet should be current bet (35) + pot size after call (80)"
    
#     # Add logging to show calculation steps
#     logger.debug("\nPot Limit Calculation for SB:")
#     logger.debug(f"Current pot: ${pot_limit_betting.get_total_pot()}")
#     logger.debug(f"Current bet: ${pot_limit_betting.current_bet}")
#     logger.debug(f"SB current bet: ${pot_limit_betting.current_bets.get('SB', PlayerBet()).amount}")
#     logger.debug(f"To call: ${pot_limit_betting.current_bet - pot_limit_betting.current_bets.get('SB', PlayerBet()).amount}")
#     logger.debug(f"Pot after call would be: ${pot_limit_betting.get_total_pot() + (pot_limit_betting.current_bet - pot_limit_betting.current_bets.get('SB', PlayerBet()).amount)}")

# def test_multiple_small_all_ins(nl_betting):
#     """Test multiple all-ins where each is smaller than previous."""
#     # Initial stacks:
#     # P1: 400
#     # P2: 300
#     # P3: 200
#     # P4: 100
    
#     nl_betting.place_bet("P1", 400, 400)  # P1 all-in
#     assert nl_betting.get_total_pot() == 400
#     assert nl_betting.get_main_pot_amount() == 400
    
#     # After P2's all-in for 300:
#     # Main: 600 (300 each from P1,P2)
#     # Side 1: 100 (P1's excess)
#     nl_betting.place_bet("P2", 300, 300)  # P2 all-in
#     assert nl_betting.get_main_pot_amount() == 600, "Main pot should have 300 each"
#     assert nl_betting.get_side_pot_count() == 1
#     assert nl_betting.get_side_pot_amount(0) == 100, "Side pot should have P1's excess"
    
#     # After P3's all-in for 200:
#     # Main: 600 (200 each from P1,P2,P3)
#     # Side 1: 200 (100 each from P1,P2 for 200->300)
#     # Side 2: 100 (P1's excess 300->400)
#     nl_betting.place_bet("P3", 200, 200)  # P3 all-in
#     assert nl_betting.get_main_pot_amount() == 600, "Main pot should have 200 each from three players"
#     assert nl_betting.get_side_pot_count() == 2
    
#     assert nl_betting.get_side_pot_amount(0) == 100, "P1's excess (300->400)"
#     assert nl_betting.get_side_pot_amount(1) == 200, "100 each from P1,P2 (200->300 level)"
   
#     # P4 hasn't bet yet - total should be 900
#     assert nl_betting.get_total_pot() == 900

# def test_all_in_between_active_betting(nl_betting):
#     """Test all-in interrupting active betting sequence."""
#     # P1 opens for 100
#     nl_betting.place_bet("P1", 100, 1000)
#     assert nl_betting.get_main_pot_amount() == 100
#     assert nl_betting.get_total_pot() == 100
    
#     # P2 raises to 300
#     nl_betting.place_bet("P2", 300, 1000)
#     assert nl_betting.get_main_pot_amount() == 400
#     assert nl_betting.get_total_pot() == 400
    
#     # P3 all-in for 200
#     nl_betting.place_bet("P3", 200, 200)
#     assert nl_betting.get_main_pot_amount() == 500  # 100 from P1, $200 from P2 and P3
#     # we have to split the main pot since we have an all-in for less than the bet in the main pot, which was $300 
#     assert nl_betting.get_side_pot_count() == 1
#     assert nl_betting.get_side_pot_amount(0) == 100  # 100 extra from P2
    
#     # P4 calls full amount 300
#     nl_betting.place_bet("P4", 300, 1000)
#     # main pot bet is $200 from P2 and P3, $100 from P1 and now $200 from P4
#     assert nl_betting.get_main_pot_amount() == 700  # 100 x 1 + 200 × 3
#     # and the other $100 goes to the side pot
#     assert nl_betting.get_side_pot_count() == 1
#     assert nl_betting.get_side_pot_amount(0) == 200  # 100 extra from P2,P4

# def test_equal_stack_all_ins(nl_betting):
#     """Test multiple all-ins with equal stacks."""
#     # All players have 200
#     nl_betting.place_bet("P1", 200, 200)  # All-in
#     assert nl_betting.get_total_pot() == 200
    
#     nl_betting.place_bet("P2", 200, 200)  # All-in
#     assert nl_betting.get_total_pot() == 400
#     assert nl_betting.get_main_pot_amount() == 400
#     assert nl_betting.get_side_pot_count() == 0
    
#     nl_betting.place_bet("P3", 200, 200)  # All-in
#     assert nl_betting.get_total_pot() == 600
#     assert nl_betting.get_main_pot_amount() == 600
#     assert nl_betting.get_side_pot_count() == 0

# def test_micro_all_in_under_blind(nl_betting):
#     """Test all-in smaller than big blind.
    
#     Sequence:
#     1. SB posts $5
#     2. BB posts $10
#     3. BTN all-in for $3
    
#     Should result in:
#     - Main pot: $9 ($3 from each)
#     - Side pot: $9 ($2 more from SB + $7 more from BB)
#     """
#     # Post blinds
#     nl_betting.place_bet("SB", 5, 500, is_forced=True)
#     nl_betting.place_bet("BB", 10, 500, is_forced=True)
#     assert nl_betting.get_main_pot_amount() == 15
#     assert nl_betting.current_bet == 10
    
#     # BTN all-in for 3
#     nl_betting.place_bet("BTN", 3, 3)
    
#     # Main pot should have $3 from each player
#     assert nl_betting.get_main_pot_amount() == 9, "Main pot should have $3 × 3"
    
#     # Single side pot should have excess from SB and BB
#     assert nl_betting.get_side_pot_count() == 1, "Should have one side pot for excess blinds"
#     assert nl_betting.get_side_pot_amount(0) == 9, "Side pot should have $2 from SB + $7 from BB"
    
#     # Total pot should be $18
#     assert nl_betting.get_total_pot() == 18, "Total should be original $15 + $3 from BTN"

# # Add more test cases here

# def test_invalid_bet_rejection(limit_betting, nl_betting, pot_limit_betting):
#     """Test rejection of invalid bets."""
#     # Limit: Only 10 allowed in round 0
#     limit_betting.place_bet("SB", 5, 500, is_forced=True)
#     # Verify valid bet works
#     limit_betting.place_bet("BB", 10, 500)  # Should succeed
#     assert limit_betting.get_total_pot() == 15        
    
#     # No-Limit: Min raise below requirement
#     nl_betting.place_bet("SB", 5, 500, is_forced=True)
#     nl_betting.place_bet("BB", 10, 500, is_forced=True)
#     with pytest.raises(ValueError):
#         nl_betting.place_bet("BTN", 15, 500)  # Min is 20
    
#     # Pot-Limit: Above pot limit
#     pot_limit_betting.place_bet("SB", 5, 500, is_forced=True)
#     pot_limit_betting.place_bet("BB", 10, 500, is_forced=True)
#     with pytest.raises(ValueError):
#         pot_limit_betting.place_bet("BTN", 50, 500)  # Max is 35

# def test_min_bet_edge_cases(nl_betting, pot_limit_betting):
#     """Test min bet when last raise exceeds stack in realistic scenarios."""
#     # No-Limit
#     nl_betting.place_bet("SB", 50, 1000)
#     nl_betting.place_bet("BB", 200, 1000)
#     assert nl_betting.get_min_bet("BTN", BetType.BIG) == 200
#     nl_betting.place_bet("BTN", 100, 100)

#     # Pot-Limit
#     pot_limit_betting.place_bet("SB", 5, 500, is_forced=True)
#     pot_limit_betting.place_bet("BB", 10, 500, is_forced=True)
#     pot_limit_betting.place_bet("BTN", 10, 100)  # Pot = 25
#     pot_limit_betting.place_bet("SB", 35, 495)  # Pot = 55, call 5 + raise 30
#     assert pot_limit_betting.get_min_bet("BB", BetType.BIG) == 35
#     assert pot_limit_betting.get_min_raise("BB") == 60  # 35 + 25
#     pot_limit_betting.place_bet("BB", 100, 100)  # Adds 90 (call 25 + raise 65)
#     assert pot_limit_betting.get_total_pot() == 145  # 55 + 90

# def test_multi_round_betting(limit_betting, nl_betting, pot_limit_betting):
#     """Test betting across rounds with multiple players."""
#     # Limit
#     limit_betting.place_bet("P1", 10, 500)  # Round 0: P1 bets small
#     limit_betting.place_bet("P2", 10, 500)  # P2 calls
#     limit_betting.new_round()              # Round 1
#     limit_betting.place_bet("P1", 10, 490) # P1 bets small
#     limit_betting.place_bet("P2", 10, 490) # P2 calls
#     limit_betting.new_round()              # Round 2
#     limit_betting.place_bet("P1", 20, 480) # P1 bets big
#     assert limit_betting.get_total_pot() == 60  # 20 + 20 + 20
    
#     # No-Limit
#     nl_betting.place_bet("P1", 100, 1000)
#     nl_betting.new_round()
#     nl_betting.place_bet("P1", 200, 900)
#     assert nl_betting.get_total_pot() == 300
    
#     # Pot-Limit
#     pot_limit_betting.place_bet("P1", 5, 500, is_forced=True)  # SB
#     pot_limit_betting.place_bet("P2", 10, 500, is_forced=True) # BB
#     pot_limit_betting.place_bet("P1", 25, 495)                # P1: call 5 + raise 20
#     pot_limit_betting.new_round()
#     pot_limit_betting.place_bet("P2", 35, 485)                # P2: pot-sized bet
#     assert pot_limit_betting.get_total_pot() == 70            # 5 + 10 + 20 + 35

# def test_all_in_limit_pot(limit_betting, pot_limit_betting):
#     """Test all-in scenarios with realistic pot setup."""
#     # Limit
#     limit_betting.place_bet("P1", 10, 500)
#     limit_betting.place_bet("P2", 5, 5)
#     assert limit_betting.get_main_pot_amount() == 10  # 5 each
    
#     # Pot-Limit
#     pot_limit_betting.place_bet("P1", 5, 500, is_forced=True)  # SB
#     pot_limit_betting.place_bet("P2", 10, 500, is_forced=True) # BB
#     pot_limit_betting.place_bet("P1", 25, 495)                # Call 5 to complete blind + raise $15
#     pot_limit_betting.place_bet("P2", 50, 50)                 # All-in.  $15 calls the raise, $10 already bet in BB, so $25 raise.
#     assert pot_limit_betting.get_total_pot() == 75            # $25 from P1, $50 from P2
#     assert pot_limit_betting.get_side_pot_count() == 0        # everything is in the main pot


@pytest.fixture
def pot_limit_betting():
    """Create a Pot Limit betting manager with small bet of 10."""
    return PotLimitBettingManager(small_bet=10)

def verify_betting_state(betting: BettingManager, expected_state: dict):
    """Helper to verify betting manager state."""
    # Verify pot totals
    assert betting.get_total_pot() == expected_state["total_pot"], \
        f"Expected total pot {expected_state['total_pot']}, got {betting.get_total_pot()}"
    
    # Verify current bets
    for player, expected_bet in expected_state["current_bets"].items():
        actual_bet = betting.current_bets.get(player)
        assert actual_bet is not None, f"No bet found for player {player}"
        assert actual_bet.amount == expected_bet["amount"], \
            f"Expected bet of {expected_bet['amount']} for {player}, got {actual_bet.amount}"
        if "is_all_in" in expected_bet:
            assert actual_bet.is_all_in == expected_bet["is_all_in"], \
                f"Expected all-in status {expected_bet['is_all_in']} for {player}"
    
    # Verify pot structure if provided
    if "main_pot" in expected_state:
        assert betting.get_main_pot_amount() == expected_state["main_pot"], \
            f"Expected main pot {expected_state['main_pot']}, got {betting.get_main_pot_amount()}"
    
    if "side_pots" in expected_state:
        assert len(betting.pot.side_pots) == len(expected_state["side_pots"]), \
            f"Expected {len(expected_state['side_pots'])} side pots, got {len(betting.pot.side_pots)}"
        for i, (actual, expected) in enumerate(zip(betting.pot.side_pots, expected_state["side_pots"])):
            assert actual.amount == expected["amount"], \
                f"Side pot {i} amount: expected {expected['amount']}, got {actual.amount}"
            if "eligible_players" in expected:
                assert actual.eligible_players == set(expected["eligible_players"]), \
                    f"Side pot {i} eligible players don't match"
                
# def test_award_pots_single_winner(limit_betting):
#     """Test awarding main pot to single winner via BettingManager."""
#     p1 = Player("P1", "Alice", 100)
#     p2 = Player("P2", "Bob", 100)
#     limit_betting.place_bet(p1.id, 10, 100)
#     limit_betting.place_bet(p2.id, 10, 100)
#     assert limit_betting.get_total_pot() == 20

#     initial_stack = p1.stack
#     limit_betting.award_pots([p1])
#     assert p1.stack == initial_stack + 20
#     assert limit_betting.get_total_pot() == 0

# def test_award_pots_split_pot(limit_betting):
#     """Test splitting main pot among winners."""
#     p1 = Player("P1", "Alice", 100)
#     p2 = Player("P2", "Bob", 100)
#     p3 = Player("P3", "Charlie", 100)
#     limit_betting.place_bet(p1.id, 10, 100)
#     limit_betting.place_bet(p2.id, 10, 100)
#     limit_betting.place_bet(p3.id, 10, 100)
#     assert limit_betting.get_total_pot() == 30

#     initial_stacks = [p.stack for p in [p1, p2, p3]]
#     limit_betting.award_pots([p1, p2])  # P3 loses
#     assert p1.stack == initial_stacks[0] + 15  # 30 // 2
#     assert p2.stack == initial_stacks[1] + 15
#     assert p3.stack == initial_stacks[2]  # No win
#     assert limit_betting.get_total_pot() == 0

# def test_award_pots_side_pot(limit_betting):
#     """Test awarding a side pot in Limit betting."""
#     p1 = Player("P1", "Alice", 100)
#     p2 = Player("P2", "Bob", 100)
#     p3 = Player("P3", "Charlie", 5)  # Smaller stack for all-in
#     limit_betting.place_bet(p1.id, 10, 100)  # Small bet
#     limit_betting.place_bet(p2.id, 10, 100)  # Small bet
#     limit_betting.place_bet(p3.id, 5, 5)     # All-in, less than 10
#     assert limit_betting.get_total_pot() == 25  # 10 + 10 + 5
#     assert limit_betting.get_main_pot_amount() == 15  # 5 × 3
#     assert limit_betting.get_side_pot_count() == 1
#     assert limit_betting.get_side_pot_amount(0) == 10  # (10-5) × 2

#     initial_stack = p1.stack  # Should be 90 after betting 10
#     limit_betting.award_pots([p1], side_pot_index=0)
#     assert p1.stack == initial_stack + 10  # Wins side pot
#     assert limit_betting.get_side_pot_amount(0) == 0
#     assert limit_betting.get_total_pot() == 15  # Main pot remains

# def test_award_pots_no_winners(limit_betting):
#     """Test no-op when no winners provided."""
#     p1 = Player("P1", "Alice", 100)
#     limit_betting.place_bet(p1.id, 10, 100)
#     initial_stack = p1.stack
#     limit_betting.award_pots([])
#     assert p1.stack == initial_stack
#     assert limit_betting.get_total_pot() == 10                