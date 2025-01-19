"""Tests for pot management and side pot creation."""
import pytest
from generic_poker.game.pot import Pot,BettingLevel
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

def test_find_betting_levels_single_all_in():
    """Test finding betting levels with a single all-in."""
    pot = Pot()
    
    # Setup state
    pot.total_bets = {
        "P1": 100,  # Not all-in
        "P2": 50,   # All-in
        "P3": 100,  # Not all-in
    }
    pot.is_all_in = {"P2": True}
    
    # Check levels from 0
    levels = pot._find_betting_levels(0)
    assert len(levels) == 1
    assert levels[0].start_amount == 0
    assert levels[0].end_amount == 50
    assert levels[0].eligible_players == {"P2"}
    assert levels[0].contribution_per_player == 50    

def test_find_betting_levels_multiple_all_ins():
    """Test finding levels with multiple all-ins at different amounts."""
    pot = Pot()
    
    # Setup state
    pot.total_bets = {
        "P1": 100,  # All-in
        "P2": 25,   # All-in
        "P3": 50,   # All-in
        "P4": 100,  # All-in
    }
    pot.is_all_in = {
        "P1": True,
        "P2": True,
        "P3": True,
        "P4": True
    }
    
    # Check levels from lowest all-in
    levels = pot._find_betting_levels(25)
    assert len(levels) == 2, "Should find two levels: 25-50 and 50-100"
    
    # Check first level (25-50)
    level1 = levels[0]
    assert level1.start_amount == 25
    assert level1.end_amount == 50
    assert level1.eligible_players == {"P1", "P3", "P4"}
    assert level1.contribution_per_player == 25
    
    # Check second level (50-100)
    level2 = levels[1]
    assert level2.start_amount == 50
    assert level2.end_amount == 100
    assert level2.eligible_players == {"P1", "P4"}
    assert level2.contribution_per_player == 50    

def test_find_betting_levels_with_active_players():
    """Test finding levels when some players are still active (not all-in)."""
    pot = Pot()
    
    # Setup state
    pot.total_bets = {
        "P1": 75,   # Not all-in
        "P2": 25,   # All-in
        "P3": 50,   # All-in
        "P4": 75,   # All-in
    }
    pot.is_all_in = {
        "P2": True,
        "P3": True,
        "P4": True
    }
    
    # Check levels from lowest all-in
    levels = pot._find_betting_levels(25)
    assert len(levels) == 2, "Should find two levels despite P1 not being all-in"
    
    # 25-50 level
    level1 = levels[0]
    assert level1.start_amount == 25
    assert level1.end_amount == 50
    assert level1.eligible_players == {"P3", "P4"}
    assert level1.contribution_per_player == 25
    
    # 50-75 level
    level2 = levels[1]
    assert level2.start_amount == 50
    assert level2.end_amount == 75
    assert level2.eligible_players == {"P4"}
    assert level2.contribution_per_player == 25    

def test_create_side_pots_for_levels():
    """Test creation of side pots from betting levels."""
    pot = Pot()
    
    # Create test levels
    level1 = BettingLevel(
        start_amount=25,
        end_amount=50,
        eligible_players={"P1", "P3", "P4"},
        contribution_per_player=25
    )
    
    level2 = BettingLevel(
        start_amount=50,
        end_amount=75,
        eligible_players={"P1", "P4"},
        contribution_per_player=25
    )
    
    # Create side pots
    side_pots = pot._create_side_pots_for_levels([level1, level2])
    
    # Verify results
    assert len(side_pots) == 2
    
    # Check first side pot
    assert side_pots[0].amount == 75  # 25 × 3 players
    assert side_pots[0].eligible_players == {"P1", "P3", "P4"}
    
    # Check second side pot
    assert side_pots[1].amount == 50  # 25 × 2 players
    assert side_pots[1].eligible_players == {"P1", "P4"}

def test_update_main_pot_single_all_in_detailed():
    """Detailed test of main pot calculation with single all-in player."""
    pot = Pot()
    
    # Set up state
    pot.total_bets = {
        "P1": 100,  # Not all-in
        "P2": 25,   # All-in
        "P3": 10    # Not all-in
    }
    pot.is_all_in = {"P2": True}
    
    # Update main pot
    pot._update_main_pot()
    
    # Should be: min(100,25) + 25 + min(10,25) = 25 + 25 + 10 = 60
    # Check each player's contribution separately
    min_all_in = 25  # P2's amount
    p1_contrib = min(100, min_all_in)  # Should be 25
    p2_contrib = 25  # All-in amount
    p3_contrib = min(10, min_all_in)  # Should be 10
    expected_total = p1_contrib + p2_contrib + p3_contrib
    
    assert p1_contrib == 25, f"P1 should contribute {25}, got {p1_contrib}"
    assert p2_contrib == 25, f"P2 should contribute {25}, got {p2_contrib}"
    assert p3_contrib == 10, f"P3 should contribute {10}, got {p3_contrib}"
    assert pot.main_pot == expected_total, f"Expected main pot {expected_total}, got {pot.main_pot}"

def test_update_main_pot():
    """Test main pot calculation with various all-in scenarios."""
    pot = Pot()
    
    # Test with single all-in - others haven't matched
    pot.total_bets = {"P1": 100, "P2": 25, "P3": 10}
    pot.is_all_in = {"P2": True}
    pot._update_main_pot()
    assert pot.main_pot == 60  # P1: min(100,25)=25 + P2: 25 + P3: min(10,25)=10
    
    # Test with multiple all-ins - one player matched, one hasn't
    pot.total_bets = {"P1": 50, "P2": 25, "P3": 50, "P4": 10}
    pot.is_all_in = {"P2": True, "P3": True}
    pot._update_main_pot()
    # Main pot includes only up to lowest all-in amount (25):
    # P1: min(50,25)=25 + P2: 25 + P3: min(50,25)=25 + P4: min(10,25)=10
    assert pot.main_pot == 85  
    
    # Test when everyone has matched or exceeded min all-in
    pot.total_bets = {"P1": 25, "P2": 25, "P3": 25, "P4": 25}
    pot.is_all_in = {"P2": True}
    pot._update_main_pot()
    assert pot.main_pot == 100  # All players contributed exactly 25
    
    # Test with no all-ins
    pot.total_bets = {"P1": 100, "P2": 50, "P3": 75}
    pot.is_all_in = {}
    initial_pot = pot.main_pot
    pot._update_main_pot()
    assert pot.main_pot == initial_pot  # Should not change when no all-ins

def test_empty_levels():
    """Test edge case with no all-ins above current amount."""
    pot = Pot()
    
    pot.total_bets = {"P1": 50, "P2": 25, "P3": 25}
    pot.is_all_in = {"P2": True, "P3": True}
    
    levels = pot._find_betting_levels(25)
    assert len(levels) == 0    

def test_side_pot_creation_timing():
    """
    Test when side pots are created relative to betting actions.
    
    Initial stacks:
    - SB:  60  (posts 5,  55 left)
    - BB:  100 (posts 10, 90 left)
    - BTN: 100 (no blind)
    
    Betting sequence:
    1. BTN calls 10                  -> Main pot 25
    2. SB raises all-in +55 (60 total) -> Main pot 80
    3. BB raises all-in +90 (100 total):
       - 50 to match SB's raise      -> Main pot 180
       - 40 to new side pot          -> Side pot 40 (BB only)
    4. BTN calls:
       - 50 to match SB's raise      -> Main pot stays 180
       - 40 to match BB's raise      -> Side pot grows to 80 (BB, BTN eligible)
    """
    pot = Pot()
    logger.info("\n=== Starting test_side_pot_creation_timing ===")
    
    # Step 1: Post blinds
    logger.info("\nStep 1: Posting blinds")
    pot.add_bet("SB", 5, False)  # Small blind
    pot._debug_state()
    assert pot.main_pot == 5
    assert len(pot.side_pots) == 0
    
    pot.add_bet("BB", 10, False) # Big blind
    pot._debug_state()
    assert pot.main_pot == 15
    assert len(pot.side_pots) == 0
    assert pot.total_bets == {"SB": 5, "BB": 10}
    
    # Step 2: BTN calls big blind
    logger.info("\nStep 2: BTN calls big blind")
    pot.add_bet("BTN", 10, False)
    pot._debug_state()
    assert pot.main_pot == 25
    assert len(pot.side_pots) == 0
    assert pot.total_bets == {"SB": 5, "BB": 10, "BTN": 10}
    
    # Step 3: SB goes all in
    logger.info("\nStep 3: SB goes all-in (+55)")
    pot.add_bet("SB", 55, True)
    pot._debug_state()
    assert pot.main_pot == 80, "Main pot should be 80 after SB all-in"
    assert len(pot.side_pots) == 0, "No side pots should exist yet"
    assert pot.total_bets == {"SB": 60, "BB": 10, "BTN": 10}
    assert pot.is_all_in == {"SB": True}
    
    # Step 4: BB raises all in
    logger.info("\nStep 4: BB goes all-in (+90)")
    pot.add_bet("BB", 90, True)
    pot._debug_state()
    
    # Verify BB all-in state
    assert pot.main_pot == 130, "Main pot should be 130 after BB matches SB's all-in"
    assert len(pot.side_pots) == 1, "Should have one side pot"
    assert pot.side_pots[0].amount == 40, "Side pot should be 40 (BB's excess over SB)"
    assert pot.side_pots[0].eligible_players == {"BB"}, "Only BB should be eligible for first side pot"
    assert pot.total_bets == {"SB": 60, "BB": 100, "BTN": 10}
    assert set(pot.is_all_in.keys()) == {"SB", "BB"}
    assert all(pot.is_all_in.values())
    
    # Step 5: BTN calls BB's all-in
    logger.info("\nStep 5: BTN calls all-in (+90)")
    pot.add_bet("BTN", 90, True)
    pot._debug_state()
    
    # Verify final state
    main_pot_expected = 180  # SB's all-in amount (60) × 3 players
    assert pot.main_pot == main_pot_expected, \
        f"Main pot should be {main_pot_expected}, got {pot.main_pot}"
        
    assert len(pot.side_pots) == 1, \
        f"Should have exactly one side pot, got {len(pot.side_pots)}"
        
    side_pot_expected = 80  # (BB's bet - SB's bet) × 2 players
    assert pot.side_pots[0].amount == side_pot_expected, \
        f"Side pot should be {side_pot_expected}, got {pot.side_pots[0].amount}"
        
    assert pot.side_pots[0].eligible_players == {"BB", "BTN"}, \
        "BB and BTN should be eligible for side pot"
        
    # Verify total contributions
    assert pot.total_bets == {"SB": 60, "BB": 100, "BTN": 100}, \
        "Final total bets incorrect"
    
    # Verify all-in status
    assert pot.is_all_in == {"SB": True, "BB": True, "BTN": True}, \
        "Final all-in status incorrect"
    
    # Verify total pot size
    total_expected = main_pot_expected + side_pot_expected
    assert pot.total == total_expected, \
        f"Total pot should be {total_expected}, got {pot.total}"
        
    logger.info("=== Test completed successfully ===\n")

def test_multiple_all_in_side_pots():
    """Test creation of multiple side pots with different all-in amounts."""
    pot = Pot()
    
    # Initial bets
    pot.add_bet("P1", 10, False)  # Big blind
    pot.add_bet("P2", 5, False)   # Small blind
    pot.add_bet("P3", 10, False)  # Call
    pot.add_bet("P4", 10, False)  # Call
    
    assert pot.main_pot == 35
    
    # P2 goes all-in for 25 total
    pot.add_bet("P2", 20, True)  # Adding 20 to their 5
    
    # P3 goes all-in for 50 total
    pot.add_bet("P3", 40, True)  # Adding 40 to their 10
    
    # P4 goes all-in for 75 total
    pot.add_bet("P4", 65, True)  # Adding 65 to their 10
    
    # P1 calls the maximum
    pot.add_bet("P1", 65, True)  # Adding 65 to their 10
    
    # Verify pot structure
    assert len(pot.side_pots) == 3
    
    # Main pot should have P2's all-in amount from each player
    assert pot.main_pot == 100  # 25 * 4
    
    # First side pot: P3, P4, and P1's contribution between 25 and 50
    assert pot.side_pots[0].amount == 75  # (50-25) * 3
    assert pot.side_pots[0].eligible_players == {"P1", "P3", "P4"}
    
    # Second side pot: P4 and P1's contribution between 50 and 75
    assert pot.side_pots[1].amount == 50  # (75-50) * 2
    assert pot.side_pots[1].eligible_players == {"P1", "P4"}

def test_side_pot_eligibility():
    """Test that side pot eligibility is tracked correctly."""
    pot = Pot()
    
    # Everyone puts in 10
    for player in ["P1", "P2", "P3"]:
        pot.add_bet(player, 10, False)
    
    # P2 goes all-in for 30 more
    pot.add_bet("P2", 30, True)
    
    # P3 goes all-in for 60 more
    pot.add_bet("P3", 60, True)
    
    # P1 calls the maximum
    pot.add_bet("P1", 60, False)
    
    # Verify eligibility
    assert pot.main_pot == 120  # Everyone contributes 40
    assert len(pot.side_pots) == 1
    assert pot.side_pots[0].amount == 60  # P1 and P3's excess over P2
    assert "P2" not in pot.side_pots[0].eligible_players