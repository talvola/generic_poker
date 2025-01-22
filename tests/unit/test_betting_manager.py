import pytest
from generic_poker.game.betting import (
    BettingManager, NoLimitBettingManager, LimitBettingManager, 
    PotLimitBettingManager, BetType, PlayerBet
)
from generic_poker.config.loader import BettingStructure

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
    return NoLimitBettingManager(small_bet=10)

@pytest.fixture
def limit_betting():
    """Create a Limit betting manager with small bet 10, big bet 20."""
    return LimitBettingManager(small_bet=10, big_bet=20)

def test_basic_no_limit_betting(nl_betting):
    """Test basic no-limit betting sequence without all-ins."""
    # Setup initial state (simulate posting blinds)
    nl_betting.place_bet("SB", 5, 500, is_forced=True)  # Small blind
    nl_betting.place_bet("BB", 10, 500, is_forced=True) # Big blind
    
    # Verify initial state
    assert nl_betting.pot.total == 15
    assert nl_betting.current_bet == 10
    
    # BTN calls
    nl_betting.place_bet("BTN", 10, 500)
    assert nl_betting.pot.total == 25
    assert nl_betting.current_bets["BTN"].amount == 10
    
    # SB completes
    nl_betting.place_bet("SB", 10, 495)  # 495 because already posted 5
    assert nl_betting.pot.total == 30
    assert nl_betting.current_bets["SB"].amount == 10

def test_simple_all_in_nl(nl_betting):
    """Test simple all-in and call sequence."""
    # SB with 5000 goes all-in
    nl_betting.place_bet("SB", 5000, 5000)
    assert nl_betting.pot.total == 5000
    assert nl_betting.pot.main_pot.amount == 5000
    assert len(nl_betting.pot.side_pots) == 0
    
    # BB with 1000 calls all-in
    nl_betting.place_bet("BB", 1000, 1000)
    
    # Should create:
    # - Main pot: 2000 (1000 each that both can win)
    # - Side pot: 4000 (SB's excess)
    assert nl_betting.pot.main_pot.amount == 2000, "Main pot should have 1000 from each"
    assert nl_betting.pot.main_pot.cap_amount == 1000, "Main pot capped at BB's all-in"
    assert nl_betting.pot.main_pot.eligible_players == {"SB", "BB"}
    
    assert len(nl_betting.pot.side_pots) == 1, "Should have one side pot"
    side_pot = nl_betting.pot.side_pots[0]
    assert side_pot.amount == 4000, "Side pot should have SB's excess"
    assert side_pot.eligible_players == {"SB"}
    
    assert nl_betting.pot.total == 6000

def test_limit_bet_sizes(limit_betting):
    """Test bet size restrictions in limit betting."""
    # Post blinds
    limit_betting.place_bet("SB", 5, 500, is_forced=True)
    limit_betting.place_bet("BB", 10, 500, is_forced=True)
    
    # In limit, first two rounds use small bet (10)
    assert limit_betting.get_min_bet("BTN", BetType.BIG) == 10
    assert limit_betting.get_max_bet("BTN", BetType.BIG, 500) == 10
    
    # Make some bets to get to next round
    limit_betting.place_bet("BTN", 10, 500)
    limit_betting.place_bet("SB", 10, 495)
    limit_betting.place_bet("BB", 10, 490)
    limit_betting.new_round()
    
    # Later rounds use big bet (20)
    limit_betting.betting_round = 2  # Simulate later round
    assert limit_betting.get_min_bet("BTN", BetType.BIG) == 20
    assert limit_betting.get_max_bet("BTN", BetType.BIG, 500) == 20

def test_nl_min_raise_progression(nl_betting):
    """Test minimum raise requirements at each step."""
    # Post blinds
    nl_betting.place_bet("SB", 5, 500, is_forced=True)
    nl_betting.place_bet("BB", 10, 500, is_forced=True)
    
    # At this point:
    # - Current bet is 10 (BB)
    # - No raises yet
    min_bet = nl_betting.get_min_bet("BTN", BetType.BIG)
    assert min_bet == 20, "First raise should be BB (10) + BB (10)"
    
    # BTN min-raises to 20
    nl_betting.place_bet("BTN", 20, 500)
    # Now:
    # - Current bet is 20
    # - Last raise was 10 (20 - 10)
    min_bet = nl_betting.get_min_bet("SB", BetType.BIG)
    assert min_bet == 30, "After min-raise, next min is current (20) + previous raise (10)"
    
    # SB raises to 50 (a raise of 30)
    nl_betting.place_bet("SB", 50, 495)
    # Now:
    # - Current bet is 50
    # - Last raise was 30 (50 - 20)
    min_bet = nl_betting.get_min_bet("BB", BetType.BIG)
    assert min_bet == 80, "After 30 raise, next min is current (50) + previous raise (30)"
    
    # BB re-raises to 100 (a raise of 50)
    nl_betting.place_bet("BB", 100, 490)
    # Now:
    # - Current bet is 100
    # - Last raise was 50 (100 - 50)
    min_bet = nl_betting.get_min_bet("BTN", BetType.BIG)
    assert min_bet == 150, "After 50 raise, next min is current (100) + previous raise (50)"
    
    print(f"Current bet: {nl_betting.current_bet}")
    print(f"Last raise size: {nl_betting.last_raise_size}")
    print(f"Current bets: {[(p, b.amount) for p, b in nl_betting.current_bets.items()]}")
    print(f"Pot total: {nl_betting.pot.total}")    

def test_nl_bet_size_validation(nl_betting):
    """Test no-limit bet size validation."""
    nl_betting.place_bet("SB", 5, 500, is_forced=True)
    nl_betting.place_bet("BB", 10, 500, is_forced=True)
    
    # Min raise should be BB size (10)
    min_bet = nl_betting.get_min_bet("BTN", BetType.BIG)
    assert min_bet == 20  # Current bet (10) + min raise (10)
    
    # Can raise up to stack size
    max_bet = nl_betting.get_max_bet("BTN", BetType.BIG, 500)
    assert max_bet == 500
    
    # After a larger raise, min raise increases
    nl_betting.place_bet("BTN", 50, 500)  # Raise to 50
    min_bet = nl_betting.get_min_bet("SB", BetType.BIG)
    assert min_bet == 90  # Current bet (50) + previous raise (40)

def test_nl_bet_size_validation(nl_betting):
    """Test no-limit bet size validation."""
    nl_betting.place_bet("SB", 5, 500, is_forced=True)
    nl_betting.place_bet("BB", 10, 500, is_forced=True)
    
    # Min raise should be BB size (10)
    min_bet = nl_betting.get_min_bet("BTN", BetType.BIG)
    assert min_bet == 20  # Current bet (10) + min raise (10)
    
    # Can raise up to stack size
    max_bet = nl_betting.get_max_bet("BTN", BetType.BIG, 500)
    assert max_bet == 500
    
    # After a larger raise, min raise increases
    nl_betting.place_bet("BTN", 50, 500)  # Raise to 50
    min_bet = nl_betting.get_min_bet("SB", BetType.BIG)
    assert min_bet == 90  # Current bet (50) + previous raise (40)

def test_all_in_side_pot_creation(nl_betting):
    """Test side pot creation with all-in bets."""
    # SB with 5000 goes all-in
    nl_betting.place_bet("SB", 5000, 5000)
    assert nl_betting.pot.total == 5000
    assert nl_betting.pot.main_pot.amount == 5000
    assert len(nl_betting.pot.side_pots) == 0
    
    # BB with 1000 calls all-in
    nl_betting.place_bet("BB", 1000, 1000)
    
    # Should create:
    # - Main pot: 2000 (1000 each that both can win)
    # - Side pot: 4000 (SB's excess that only they can win)
    assert nl_betting.pot.main_pot.amount == 2000, "Main pot should contain amount both players can win"
    assert len(nl_betting.pot.side_pots) == 1, "Should create side pot for excess"
    assert nl_betting.pot.side_pots[0].amount == 4000, "Side pot should contain SB's excess"
    assert nl_betting.pot.total == 6000
    
    # Verify pot eligibility
    assert nl_betting.pot.main_pot.eligible_players == {"SB", "BB"}
    assert nl_betting.pot.side_pots[0].eligible_players == {"SB"}
    
    # Verify all-in status
    assert nl_betting.current_bets["SB"].is_all_in
    assert nl_betting.current_bets["BB"].is_all_in

# this test should be move to Game class test
# def test_all_in_return(nl_betting):
#     """Test returning excess chips when calling an all-in bet."""
#     # Setup without blinds for clarity
#     # SB with 5000, BB with 1000
#     nl_betting.place_bet("SB", 5000, 5000)  # SB goes all-in
#     assert nl_betting.pot.total == 5000
    
#     # BB calls with their entire 1000
#     nl_betting.place_bet("BB", 1000, 1000)  # BB calls all-in
    
#     # Should only create pot of 2000 (1000 from each)
#     assert nl_betting.pot.total == 2000
#     assert nl_betting.pot.main_pot.amount == 2000
#     assert len(nl_betting.pot.side_pots) == 0

def test_side_pots_different_stacks(nl_betting):
    """Test side pot creation with different stack sizes."""
    # Initial stacks:
    # P1: 1000
    # P2: 500
    # P3: 250
    # P4: 100
    
    # P1 raises to 400
    nl_betting.place_bet("P1", 400, 1000)
    assert nl_betting.pot.total == 400
    assert nl_betting.pot.main_pot.amount == 400
    assert len(nl_betting.pot.side_pots) == 0
    
    # P2 calls 400
    nl_betting.place_bet("P2", 400, 500)
    assert nl_betting.pot.total == 800
    assert nl_betting.pot.main_pot.amount == 800
    assert len(nl_betting.pot.side_pots) == 0
    
    # P3 all-in for 250
    nl_betting.place_bet("P3", 250, 250)
    assert nl_betting.current_bets["P3"].is_all_in

    # After P3's all-in:
    # Main pot: $750 ($250 × 3) - capped at 250
    # Side pot A: $300 ($150 excess from P1 and P2)
    assert nl_betting.pot.main_pot.amount == 750, "Main pot should have $250 from each"
    assert nl_betting.pot.main_pot.capped
    assert nl_betting.pot.main_pot.cap_amount == 250
    assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}

    assert len(nl_betting.pot.side_pots) == 1
    first_side = nl_betting.pot.side_pots[0]
    assert first_side.amount == 300, "Side pot should have $150 each from P1,P2"
    assert first_side.eligible_players == {"P1", "P2"}
    
    # P4 all-in for 100
    nl_betting.place_bet("P4", 100, 100)
    assert nl_betting.current_bets["P4"].is_all_in

    # After P4's all-in:
    # Main pot: $400 ($100 × 4)
    # Two side pots totaling $750 ($450 + $300)
    assert nl_betting.pot.main_pot.amount == 400, "Main pot should have $100 from each"
    assert nl_betting.pot.main_pot.cap_amount == 100
    assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3", "P4"}

    assert len(nl_betting.pot.side_pots) == 2, "Should have two side pots"
    
    # Verify side pots exist with correct amounts and eligibility
    assert any(pot.amount == 450 and pot.eligible_players == {"P1", "P2", "P3"} 
              for pot in nl_betting.pot.side_pots), "Should have a $450 side pot for P1,P2,P3"
    assert any(pot.amount == 300 and pot.eligible_players == {"P1", "P2"}
              for pot in nl_betting.pot.side_pots), "Should have a $300 side pot for P1,P2"
    
    # Total pot should match all bets
    assert nl_betting.pot.total == 1150, "Total should be 400 + 400 + 250 + 100" 

def test_pot_limit_max_bet(pot_limit_betting):
    """Test pot-limit betting restrictions."""
    # Post blinds
    pot_limit_betting.place_bet("SB", 5, 500, is_forced=True)
    pot_limit_betting.place_bet("BB", 10, 500, is_forced=True)
    
    # Calculating BTN's max bet:
    # Current pot = 15
    # To call = 10
    # Pot after call = 25 (15 + 10)
    # Max raise = 25 (pot size after call)
    # Total max bet = current bet (10) + max raise (25) = 35
    max_bet = pot_limit_betting.get_max_bet("BTN", BetType.BIG, 500)
    assert max_bet == 35, "Max bet should be current bet (10) + pot size after call (25)"
    
    # Make a pot-sized raise
    pot_limit_betting.place_bet("BTN", 35, 500)
    
    # Calculating SB's max bet:
    # Current pot = 50 (15 + BTN's 35)
    # To call = 30 (from 5 to 35)
    # Pot after call = 80 (50 + 30)
    # Max raise = 80 (pot size after call)
    # Total max bet = current bet (35) + max raise (80) = 115
    max_bet = pot_limit_betting.get_max_bet("SB", BetType.BIG, 495)
    assert max_bet == 115, "Max bet should be current bet (35) + pot size after call (80)"
    
    # Add logging to show calculation steps
    logger.debug("\nPot Limit Calculation for SB:")
    logger.debug(f"Current pot: ${pot_limit_betting.pot.total}")
    logger.debug(f"Current bet: ${pot_limit_betting.current_bet}")
    logger.debug(f"SB current bet: ${pot_limit_betting.current_bets.get('SB', PlayerBet()).amount}")
    logger.debug(f"To call: ${pot_limit_betting.current_bet - pot_limit_betting.current_bets.get('SB', PlayerBet()).amount}")
    logger.debug(f"Pot after call would be: ${pot_limit_betting.pot.total + (pot_limit_betting.current_bet - pot_limit_betting.current_bets.get('SB', PlayerBet()).amount)}")

def test_multiple_small_all_ins(nl_betting):
    """Test multiple all-ins where each is smaller than previous."""
    # Initial stacks:
    # P1: 400
    # P2: 300
    # P3: 200
    # P4: 100
    
    nl_betting.place_bet("P1", 400, 400)  # P1 all-in
    assert nl_betting.pot.total == 400
    assert nl_betting.pot.main_pot.amount == 400
    
    # After P2's all-in for 300:
    # Main: 600 (300 each from P1,P2)
    # Side 1: 100 (P1's excess)
    nl_betting.place_bet("P2", 300, 300)  # P2 all-in
    assert nl_betting.pot.main_pot.amount == 600, "Main pot should have 300 each"
    assert nl_betting.pot.main_pot.cap_amount == 300
    assert len(nl_betting.pot.side_pots) == 1
    assert nl_betting.pot.side_pots[0].amount == 100, "Side pot should have P1's excess"
    assert nl_betting.pot.side_pots[0].eligible_players == {"P1"}
    
    # After P3's all-in for 200:
    # Main: 600 (200 each from P1,P2,P3)
    # Side 1: 200 (100 each from P1,P2 for 200->300)
    # Side 2: 100 (P1's excess 300->400)
    nl_betting.place_bet("P3", 200, 200)  # P3 all-in
    assert nl_betting.pot.main_pot.amount == 600, "Main pot should have 200 each from three players"
    assert nl_betting.pot.main_pot.cap_amount == 200
    assert len(nl_betting.pot.side_pots) == 2
    
    # Verify side pots
    side_pot_specs = [
        (200, {"P1", "P2"}),  # 100 each from P1,P2 (200->300 level)
        (100, {"P1"}),        # P1's excess (300->400)
    ]
    for amount, players in side_pot_specs:
        assert any(pot.amount == amount and pot.eligible_players == players
                  for pot in nl_betting.pot.side_pots)
    
    # P4 hasn't bet yet - total should be 900
    assert nl_betting.pot.total == 900

def test_all_in_between_active_betting(nl_betting):
    """Test all-in interrupting active betting sequence."""
    # P1 opens for 100
    nl_betting.place_bet("P1", 100, 1000)
    assert nl_betting.pot.main_pot.amount == 100
    assert nl_betting.pot.total == 100
    
    # P2 raises to 300
    nl_betting.place_bet("P2", 300, 1000)
    assert nl_betting.pot.main_pot.amount == 400
    assert nl_betting.pot.total == 400
    
    # P3 all-in for 200
    nl_betting.place_bet("P3", 200, 200)
    assert nl_betting.pot.main_pot.amount == 500  # 100 from P1, $200 from P2 and P3
    # we have to split the main pot since we have an all-in for less than the bet in the main pot, which was $300 
    assert len(nl_betting.pot.side_pots) == 1
    assert nl_betting.pot.side_pots[0].amount == 100  # 100 extra from P2
    
    # P4 calls full amount 300
    nl_betting.place_bet("P4", 300, 1000)
    # main pot bet is $200 from P2 and P3, $100 from P1 and now $200 from P4
    assert nl_betting.pot.main_pot.amount == 700  # 100 x 1 + 200 × 3
    # and the other $100 goes to the side pot
    assert len(nl_betting.pot.side_pots) == 1
    assert nl_betting.pot.side_pots[0].amount == 200  # 100 extra from P2,P4

def test_equal_stack_all_ins(nl_betting):
    """Test multiple all-ins with equal stacks."""
    # All players have 200
    nl_betting.place_bet("P1", 200, 200)  # All-in
    assert nl_betting.pot.total == 200
    
    nl_betting.place_bet("P2", 200, 200)  # All-in
    assert nl_betting.pot.total == 400
    assert nl_betting.pot.main_pot.amount == 400
    assert len(nl_betting.pot.side_pots) == 0
    
    nl_betting.place_bet("P3", 200, 200)  # All-in
    assert nl_betting.pot.total == 600
    assert nl_betting.pot.main_pot.amount == 600
    assert len(nl_betting.pot.side_pots) == 0
    assert nl_betting.pot.main_pot.eligible_players == {"P1", "P2", "P3"}

def test_micro_all_in_under_blind(nl_betting):
    """Test all-in smaller than big blind.
    
    Sequence:
    1. SB posts $5
    2. BB posts $10
    3. BTN all-in for $3
    
    Should result in:
    - Main pot: $9 ($3 from each)
    - Side pot: $9 ($2 more from SB + $7 more from BB)
    """
    # Post blinds
    nl_betting.place_bet("SB", 5, 500, is_forced=True)
    nl_betting.place_bet("BB", 10, 500, is_forced=True)
    assert nl_betting.pot.main_pot.amount == 15
    assert nl_betting.current_bet == 10
    
    # BTN all-in for 3
    nl_betting.place_bet("BTN", 3, 3)
    
    # Main pot should have $3 from each player
    assert nl_betting.pot.main_pot.amount == 9, "Main pot should have $3 × 3"
    assert nl_betting.pot.main_pot.cap_amount == 3
    assert nl_betting.pot.main_pot.eligible_players == {"SB", "BB", "BTN"}
    
    # Single side pot should have excess from SB and BB
    assert len(nl_betting.pot.side_pots) == 1, "Should have one side pot for excess blinds"
    assert nl_betting.pot.side_pots[0].amount == 9, "Side pot should have $2 from SB + $7 from BB"
    assert nl_betting.pot.side_pots[0].eligible_players == {"SB", "BB"}
    
    # Total pot should be $18
    assert nl_betting.pot.total == 18, "Total should be original $15 + $3 from BTN"

# Add more test cases here

@pytest.fixture
def pot_limit_betting():
    """Create a Pot Limit betting manager with small bet of 10."""
    return PotLimitBettingManager(small_bet=10)

def verify_betting_state(betting: BettingManager, expected_state: dict):
    """Helper to verify betting manager state."""
    # Verify pot totals
    assert betting.pot.total == expected_state["total_pot"], \
        f"Expected total pot {expected_state['total_pot']}, got {betting.pot.total}"
    
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
        assert betting.pot.main_pot.amount == expected_state["main_pot"], \
            f"Expected main pot {expected_state['main_pot']}, got {betting.pot.main_pot.amount}"
    
    if "side_pots" in expected_state:
        assert len(betting.pot.side_pots) == len(expected_state["side_pots"]), \
            f"Expected {len(expected_state['side_pots'])} side pots, got {len(betting.pot.side_pots)}"
        for i, (actual, expected) in enumerate(zip(betting.pot.side_pots, expected_state["side_pots"])):
            assert actual.amount == expected["amount"], \
                f"Side pot {i} amount: expected {expected['amount']}, got {actual.amount}"
            if "eligible_players" in expected:
                assert actual.eligible_players == set(expected["eligible_players"]), \
                    f"Side pot {i} eligible players don't match"