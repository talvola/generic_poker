import pytest
from generic_poker.game.pot import Pot

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

def test_side_pot_basic_two_players():
    """
    Test simple side pot creation with two players.
    P1 all-in for 50
    P2 all-in for 100
    Should create one side pot of 50 eligible for P2.
    """
    pot = Pot()
    current = pot.round_pots[-1]
    
    # Initial bets
    pot.add_bet("P1", 50, True, 50)
    pot.add_bet("P2", 100, True, 100)
    
    assert current.main_pot.amount == 100  # 50 × 2
    assert len(current.side_pots) == 1
    assert current.side_pots[0].amount == 50  # Extra 50 from P2
    assert current.side_pots[0].eligible_players == {"P2"}

def test_side_pot_three_players_sequential_all_ins():
    """
    Test three players going all-in sequentially.
    P1 all-in for 25
    P2 all-in for 50
    P3 all-in for 75
    Should create two side pots.
    """
    pot = Pot()
    current = pot.round_pots[-1]

    logger.debug("\n=== Starting sequential all-in test ===")
    
    logger.debug("\nStep 1: P1 all-in for 25")
    pot.add_bet("P1", 25, True, 25)
    
    logger.debug("\nStep 2: P2 all-in for 50")
    pot.add_bet("P2", 50, True, 50)
    
    logger.debug("\nStep 3: P3 all-in for 75")
    pot.add_bet("P3", 75, True, 75)
    
    # Main pot should be P1's all-in amount × 3 players
    assert current.main_pot.amount == 75, f"Expected main pot 75, got {pot.main_pot} (25 × 3)"
    
    # Should have two side pots
    assert len(current.side_pots) == 2, \
        f"Expected 2 side pots, got {len(current.side_pots)}\n" + \
        "\n".join(f"Side pot {i}: amount={p.amount}, eligible={p.eligible_players}" 
                 for i, p in enumerate(current.side_pots))
    
    # First side pot (25-50 level) - P2 and P3's contributions
    first_pot = current.side_pots[0]
    assert first_pot.amount == 50, \
        f"First side pot should be 50, got {first_pot.amount} ((50-25) × 2)"
    assert first_pot.eligible_players == {"P2", "P3"}, \
        f"First pot eligibility wrong: {first_pot.eligible_players}"
    
    # Second side pot (50-75 level) - just P3's contribution
    second_pot = current.side_pots[1]
    assert second_pot.amount == 25, \
        f"Second side pot should be 25, got {second_pot.amount} ((75-50) × 1)"
    assert second_pot.eligible_players == {"P3"}, \
        f"Second pot eligibility wrong: {second_pot.eligible_players}"
        
    logger.debug("\n=== Test complete ===")

def test_side_pot_active_players_between_all_ins():
    """
    Test handling of active players between all-ins.
    P1 all-in for 25
    P2 calls 50 (not all-in)
    P3 all-in for 75
    P2 calls additional 25
    Should handle P2's intermediate state correctly.
    """
    pot = Pot()
    current = pot.round_pots[-1]
    
    pot.add_bet("P1", 25, True, 25)
    pot.add_bet("P2", 50, False, 75)  # Not all-in yet
    pot.add_bet("P3", 75, True, 75)
    pot.add_bet("P2", 75, True, 25)   # Now all-in
    
    assert current.main_pot.amount == 75  # 25 × 3
    assert len(current.side_pots) == 1
    
    # First side pot (25-50)
    assert current.side_pots[0].amount == 100
    assert current.side_pots[0].eligible_players == {"P2", "P3"}

def test_side_pot_multiple_players_same_all_in_amount():
    """
    Test multiple players going all-in for the same amount.
    P1 all-in for 50
    P2 all-in for 50
    P3 all-in for 100
    Should create one side pot with P3 eligible.
    """
    pot = Pot()
    current = pot.round_pots[-1]
    
    pot.add_bet("P1", 50, True, 50)
    pot.add_bet("P2", 50, True, 50)
    pot.add_bet("P3", 100, True, 100)
    
    assert current.main_pot.amount == 150  # 50 × 3
    assert len(current.side_pots) == 1
    assert current.side_pots[0].amount == 50  # (100-50) × 1
    assert current.side_pots[0].eligible_players == {"P3"}

def test_side_pot_all_in_below_current_bet():
    """
    Test player going all-in for less than current bet.
    P1 bets 100
    P2 all-in for 50
    P3 calls 100
    Should create main pot at P2's all-in and side pot for rest.
    """
    pot = Pot()
    current = pot.round_pots[-1]
   
    pot.add_bet("P1", 100, False, 500)
    pot.add_bet("P2", 50, True, 50)
    pot.add_bet("P3", 100, False, 500)
    
    assert current.main_pot.amount == 150  # 50 × 3
    assert len(current.side_pots) == 1
    assert current.side_pots[0].amount == 100  # (100-50) × 2
    assert current.side_pots[0].eligible_players == {"P1", "P3"}

def test_pot_total_calculation():
    """Test total pot calculation includes main pot and all side pots."""
    pot = Pot()
    current = pot.round_pots[-1]
  
    # Create some complex pot scenario
    pot.add_bet("P1", 25, True, 25)
    pot.add_bet("P2", 50, True, 50)
    pot.add_bet("P3", 75, True, 75)
    
    expected_total = (
        current.main_pot.amount +  # 25 × 3 = 75
        current.side_pots[0].amount +  # (50-25) × 2 = 50
        current.side_pots[1].amount    # (75-50) × 1 = 25
    )
    assert pot.total == expected_total
    assert pot.total == 150  # 75 + 50 + 25

