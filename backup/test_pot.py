import pytest
from generic_poker.game.pot import Pot, ActivePotNew, BetInfo

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

def test_sequential_all_ins():
    """
    Test sequence of all-ins where each creates new pot boundary.
    Initial stacks:
    - P1: $25
    - P2: $50
    - P3: $75
    After each action:
    1. P1 all-in $25:
       - Main pot: $25, capped at $25
    2. P2 all-in $50:
       - Main pot: $50 ($25 each), capped at $25
       - Side pot 1: $25 (P2 only), capped at $25
    3. P3 all-in $75:
       - Main pot: $75 ($25 each), capped at $25
       - Side pot 1: $50 (P2, P3), capped at $25
       - Side pot 2: $25 (P3 only), capped at $25
    """
    pot = Pot()
    
    # P1 all-in $25
    pot.add_bet("P1", 25, True, 25)
    pot._validate_pot_state()  # Validate after each action
    assert pot.main_pot.amount == 25
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 25
    assert len(pot.side_pots) == 0
    assert pot.total == 25, "Total pot should match all contributions"
    
    # P2 all-in $50
    pot.add_bet("P2", 50, True, 50)
    pot._validate_pot_state()
    assert pot.main_pot.amount == 50, "Main pot should have $25 from each"
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 25
    
    assert len(pot.side_pots) == 1
    first_side = pot.side_pots[0]
    assert first_side.amount == 25, "Side pot should have P2's excess $25"
    assert first_side.capped
    assert first_side.cap_amount == 25
    assert first_side.eligible_players == {"P2"}
    assert pot.total == 75, "Total pot should be $75 ($25 P1 + $50 P2)"
    
    # P3 all-in $75
    pot.add_bet("P3", 75, True, 75)
    pot._validate_pot_state()
    assert pot.main_pot.amount == 75, "Main pot should have $25 from each"
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 25
    
    assert len(pot.side_pots) == 2, "Should have two side pots"
    
    first_side = pot.side_pots[0]
    assert first_side.amount == 50, "First side pot should have $25 each from P2,P3"
    assert first_side.capped
    assert first_side.cap_amount == 25
    assert first_side.eligible_players == {"P2", "P3"}
    
    second_side = pot.side_pots[1]
    assert second_side.amount == 25, "Second side pot should have P3's final $25"
    assert second_side.capped
    assert second_side.cap_amount == 25
    assert second_side.eligible_players == {"P3"}
    
    assert pot.total == 150, "Total pot should be $150 ($25 P1 + $50 P2 + $75 P3)"
    
    # Final validation
    for player_id, is_all_in in pot.is_all_in.items():
        assert is_all_in, f"Player {player_id} should be marked as all-in"
        assert player_id not in pot.main_pot.active_players, f"All-in player {player_id} should not be in active players"
        for side_pot in pot.side_pots:
            assert player_id not in side_pot.active_players, f"All-in player {player_id} should not be in any side pot's active players"

def test_simple_betting_no_all_in():
    """
    Test simple betting sequence with no all-ins.
    - P1: bets 10
    - P2: calls 10
    - P3: raises to 20
    - P1: calls 10 more
    - P2: calls 10 more
    
    Should maintain a single pot with no caps.
    """
    pot = Pot()
    
    # P1 initial bet
    pot.add_bet("P1", 10, False, 100)
    assert pot.main_pot.amount == 10
    assert not pot.main_pot.capped
    assert pot.main_pot.current_bet == 10
    assert pot.main_pot.eligible_players == {"P1"}
    assert len(pot.side_pots) == 0
    
    # P2 calls
    pot.add_bet("P2", 10, False, 100)
    assert pot.main_pot.amount == 20
    assert not pot.main_pot.capped
    assert pot.main_pot.current_bet == 10
    assert pot.main_pot.eligible_players == {"P1", "P2"}
    assert len(pot.side_pots) == 0
    
    # P3 raises
    pot.add_bet("P3", 20, False, 100)
    assert pot.main_pot.amount == 40
    assert not pot.main_pot.capped
    assert pot.main_pot.current_bet == 20
    assert pot.main_pot.eligible_players == {"P1", "P2", "P3"}
    assert len(pot.side_pots) == 0
    
    # P1 calls raise
    pot.add_bet("P1", 10, False, 90)
    assert pot.main_pot.amount == 50
    assert not pot.main_pot.capped
    assert pot.main_pot.eligible_players == {"P1", "P2", "P3"}
    
    # P2 calls raise
    pot.add_bet("P2", 10, False, 90)
    assert pot.main_pot.amount == 60
    assert not pot.main_pot.capped
    assert pot.main_pot.eligible_players == {"P1", "P2", "P3"}
    assert len(pot.side_pots) == 0

def test_all_in_below_current_bet():
    """
    Test scenario where player goes all-in for less than current bet.
    
    Initial stacks:
    - P1: $100
    - P2: $100
    - P3: $40
    
    Sequence:
    1. P1 bets $50
    2. P2 calls $50
    3. P3 all-in for $40
    
    Should result in:
    - Main pot: $120 ($40 from each)
    - Side pot: $20 ($10 excess from P1 and P2)
    """
    pot = Pot()
    
    # P1 bets 50
    pot.add_bet("P1", 50, False, 100)
    assert pot.main_pot.amount == 50
    assert not pot.main_pot.capped
    assert pot.main_pot.current_bet == 50
    
    # P2 calls 50
    pot.add_bet("P2", 50, False, 100)
    assert pot.main_pot.amount == 100
    assert not pot.main_pot.capped
    assert pot.main_pot.current_bet == 50
    
    # P3 all-in for 40
    pot.add_bet("P3", 40, True, 40)
    assert pot.main_pot.amount == 120, "Main pot should have $40 from each"
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 40
    
    assert len(pot.side_pots) == 1
    side_pot = pot.side_pots[0]
    assert side_pot.amount == 20, "Side pot should have $10 excess from P1 and P2"
    assert side_pot.eligible_players == {"P1", "P2"}

def test_mixed_betting_with_all_in():
    """
    Test complex scenario mixing regular betting with all-ins.
    
    Initial stacks:
    - P1: $100
    - P2: $60
    - P3: $100
    - P4: $100
    
    Sequence:
    1. P1 bets $20
    2. P2 raises all-in to $60
    3. P3 calls $60
    4. P4 raises to $100
    5. P1 calls $80 more
    6. P3 calls $40 more
    
    Final state:
    - Main pot: $240 ($60 from each)
    - Side pot: $160 ($40 each from P1, P3, P4)
    """
    pot = Pot()
    
    # P1 bets 20
    pot.add_bet("P1", 20, False, 100)
    assert pot.main_pot.amount == 20
    assert not pot.main_pot.capped
    
    # P2 raises all-in to 60
    pot.add_bet("P2", 60, True, 60)
    assert pot.main_pot.amount == 80
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 60
    
    # P3 calls 60
    pot.add_bet("P3", 60, False, 100)
    assert pot.main_pot.amount == 140
    assert pot.main_pot.cap_amount == 60
    
    # P4 raises to 100
    pot.add_bet("P4", 100, True, 100)
    assert pot.main_pot.amount == 200, "Main pot should have $60 from P1,P2,P3,P4"
    assert len(pot.side_pots) == 1, "Should have one side pot"
    assert pot.side_pots[0].amount == 40, "Side pot should have $40 excess from P4"
    assert pot.side_pots[0].eligible_players == {"P4"}, "Only P4 eligible for side pot initially"
    assert pot.side_pots[0].capped, "Side pot should be capped since P4 is all-in"
    assert pot.side_pots[0].cap_amount == 40, "Side pot cap should be P4's excess $40"
  
    
    # P1 calls 80 more
    pot.add_bet("P1", 80, False, 80)
    assert pot.main_pot.amount == 240
    assert pot.side_pots[0].amount == 80
    
    # P3 calls 40 more
    pot.add_bet("P3", 40, False, 40)
    assert pot.main_pot.amount == 240
    assert pot.side_pots[0].amount == 120
    assert pot.side_pots[0].eligible_players == {"P1", "P3", "P4"}

def test_handle_bet_above_all_in():
    """
    Test handling bet that exceeds an all-in amount.
    
    Scenario:
    1. P1 all-in for 25
    2. P2 bets 50
    
    Should result in:
    - Main pot: 50 (25 from each)
    - Side pot: 25 (P2's excess)
    """
    pot = Pot()
    
    # P1 bets 20
    pot.add_bet("P1", 25, True, 25)
    assert pot.main_pot.amount == 25
    assert pot.main_pot.capped
    
    # P2 raises all-in to 60
    pot.add_bet("P2", 50, True, 50)
    assert pot.main_pot.amount == 50
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 25
    assert pot.main_pot.eligible_players == {"P1", "P2"}

    assert len(pot.side_pots) == 1
    assert pot.side_pots[0].amount == 25, "Side pot should have P2's excess"
    assert pot.side_pots[0].eligible_players == {"P2"}

def test_add_bet_sequence():
    """
    Test complete bet sequence using add_bet.
    
    Scenario (from failing test):
    1. P1 bets 100
    2. P2 all-in for 50
    3. P3 calls 100
    """
    pot = Pot()
    
    # P1 bets 100
    pot.add_bet("P1", 100, False, 200)
    
    assert pot.main_pot.amount == 100
    assert len(pot.side_pots) == 0
    
    # P2 all-in for 50
    pot.add_bet("P2", 50, True, 50)
    
    assert pot.main_pot.amount == 100, "Main pot should have 50 from each"
    assert len(pot.side_pots) == 1
    assert pot.side_pots[0].amount == 50, "Side pot should have P1's excess"
    
    # Log state before P3's bet
    logger.debug("\nBefore P3's bet:")
    logger.debug(f"Main pot: {pot.main_pot.amount}")
    logger.debug(f"Side pots: {[(i, p.amount) for i, p in enumerate(pot.side_pots)]}")
    logger.debug(f"Total bets: {pot.total_bets}")
    
    # P3 calls 100
    pot.add_bet("P3", 100, False, 150)
    
    # Log final state
    logger.debug("\nFinal state:")
    logger.debug(f"Main pot: {pot.main_pot.amount}")
    logger.debug(f"Side pots: {[(i, p.amount) for i, p in enumerate(pot.side_pots)]}")
    logger.debug(f"Total bets: {pot.total_bets}")
    
    assert pot.main_pot.amount == 150  # 50 × 3
    assert len(pot.side_pots) == 1
    assert pot.side_pots[0].amount == 100  # (100-50) × 2 from P1 and P3

def test_multi_player_all_in_scenario():
    """
    Test complex scenario with multiple all-ins and side pots.
    
    Initial stacks:
    - P1: $300
    - P2: $500
    - P3: $900
    - P4: $1000
    
    Betting sequence:
    1. P1 all-in for $300
    2. P2 all-in for $500
    3. P3 all-in for $900
    4. P4 calls $900
    """
    pot = Pot()
    
    # P1 goes all-in for $300
    pot.add_bet("P1", 300, True, 300)
    
    assert pot.main_pot.amount == 300
    assert pot.main_pot.current_bet == 300
    assert pot.main_pot.eligible_players == {"P1"}
    assert len(pot.side_pots) == 0
    assert pot.total == 300
    
    # P2 goes all-in for $500
    # - $300 matches P1's bet in main pot
    # - $200 creates first side pot
    pot.add_bet("P2", 500, True, 500)
    
    assert pot.main_pot.amount == 600, "Main pot should have P1 and P2's $300"
    assert pot.main_pot.current_bet == 300
    assert pot.main_pot.eligible_players == {"P1", "P2"}
    
    assert len(pot.side_pots) == 1, "Should have one side pot"
    first_side = pot.side_pots[0]
    assert first_side.amount == 200, "Side pot should have P2's extra $200"
    assert first_side.current_bet == 200
    assert first_side.eligible_players == {"P2"}
    
    assert pot.total == 800
    
    # P3 goes all-in for $900
    # - $300 to main pot
    # - $200 to first side pot
    # - $400 creates second side pot
    pot.add_bet("P3", 900, True, 900)
    
    assert pot.main_pot.amount == 900, "Main pot should have 3 × $300"
    assert pot.main_pot.eligible_players == {"P1", "P2", "P3"}
    
    assert len(pot.side_pots) == 2, "Should have two side pots"
    
    first_side = pot.side_pots[0]
    assert first_side.amount == 400, "First side pot should have 2 × $200"
    assert first_side.eligible_players == {"P2", "P3"}
    
    second_side = pot.side_pots[1]
    assert second_side.amount == 400, "Second side pot should have P3's extra $400"
    assert second_side.eligible_players == {"P3"}
    
    assert pot.total == 1700
    
    # P4 calls $900
    # - $300 to main pot
    # - $200 to first side pot
    # - $400 to second side pot
    pot.add_bet("P4", 900, False, 1000)
    
    assert pot.main_pot.amount == 1200, "Main pot should have 4 × $300"
    assert pot.main_pot.eligible_players == {"P1", "P2", "P3", "P4"}
    
    assert len(pot.side_pots) == 2
    
    first_side = pot.side_pots[0]
    assert first_side.amount == 600, "First side pot should have 3 × $200"
    assert first_side.eligible_players == {"P2", "P3", "P4"}
    
    second_side = pot.side_pots[1]
    assert second_side.amount == 800, "Second side pot should have 2 × $400"
    assert second_side.eligible_players == {"P3", "P4"}
    
    assert pot.total == 2600



def test_same_level_all_ins():
    """
    Test multiple players all-in at same amount.
    
    P1, P2 both all-in for $50
    P3 all-in for $100
    
    All-in levels should be [50, 100] not [50, 50, 100]
    """
    pot = Pot()
    
    # P1 all-in at 50
    pot.add_bet("P1", 50, True, 50)
    assert pot.main_pot.amount == 50
    assert len(pot.side_pots) == 0
    
    # P2 also all-in at 50
    pot.add_bet("P2", 50, True, 50)
    assert pot.main_pot.amount == 100  # 2 × 50
    assert len(pot.side_pots) == 0  # No side pot needed
    
    # P3 all-in at higher amount
    pot.add_bet("P3", 100, True, 100)
    assert pot.main_pot.amount == 150  # 3 × 50
    assert len(pot.side_pots) == 1
    assert pot.side_pots[0].amount == 50  # P3's excess only


def test_active_players_between_all_ins():
    """
    Test active betting followed by all-ins.
    
    Initial stacks:
    - P1: $25
    - P2: $100
    - P3: $75
    
    After each action:
    1. P1 all-in $25:
       - Main pot: $25, capped at $25
    2. P2 bet $50:
       - Main pot: $50 ($25 each), capped at $25
       - Side pot 1: $25 (P2), not capped
    3. P3 all-in $75:
       - Main pot: $75 ($25 each), capped at $25
       - Side pot 1: $75 (P2,P3), not capped
    4. P2 all-in $25:
       - Main pot: $75 ($25 each), capped at $25
       - Side pot 1: $100 ($50 each P2,P3), capped at $75
    """
    pot = Pot()
    
    # P1 all-in $25
    pot.add_bet("P1", 25, True, 25)
    assert pot.main_pot.amount == 25
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 25
    assert len(pot.side_pots) == 0
    
    # P2 bet $50 (not all-in)
    pot.add_bet("P2", 50, False, 100)
    assert pot.main_pot.amount == 50, "Main pot should have $25 from each"
    assert pot.main_pot.capped
    assert pot.main_pot.cap_amount == 25
    
    assert len(pot.side_pots) == 1
    first_side = pot.side_pots[0]
    assert first_side.amount == 25
    assert not first_side.capped, "Side pot not capped as P2 not all-in"
    assert first_side.eligible_players == {"P2"}
    
    # P3 all-in $75
    pot.add_bet("P3", 75, True, 75)
    assert pot.main_pot.amount == 75, "Main pot should have $25 from each"
    assert pot.main_pot.capped
    
    assert len(pot.side_pots) == 1
    first_side = pot.side_pots[0]
    assert first_side.amount == 75, "Side pot gets all excess above $25"
    assert first_side.eligible_players == {"P2", "P3"}
    assert first_side.capped, "Side pot should be capped since P3 is all-in"
    assert first_side.cap_amount == 50, "Cap is P3's contribution above main pot"
        
    # P2 calls $25
    pot.add_bet("P2", 25, False, 50)
    assert pot.main_pot.amount == 75, "Main pot unchanged"
    assert pot.main_pot.capped
    
    assert len(pot.side_pots) == 1
    first_side = pot.side_pots[0]
    assert first_side.amount == 100, "Side pot has all betting above main pot"
    assert first_side.eligible_players == {"P2", "P3"}
    assert first_side.capped, "Side pot remains capped at P3's all-in level"
    assert first_side.cap_amount == 50, "Cap remains at P3's contribution above main pot"
