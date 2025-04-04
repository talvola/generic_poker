"""Tests for No Limit and Pot Limit betting behavior."""
import pytest
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.config.loader import GameRules, BettingStructure
from tests.test_helpers import create_test_game

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

class BettingScenario:
    """Test scenario for betting sequences."""
    def __init__(
        self,
        name: str,
        actions: list[tuple[str, PlayerAction, int]],
        expected_stacks: dict[str, int],
        expected_pot: int,
        num_players: int = 3,
        pot_progression: list[int] | None = None
    ):
        self.name = name
        self.actions = actions
        self.expected_stacks = expected_stacks
        self.expected_pot = expected_pot
        self.num_players = num_players
        self.pot_progression = pot_progression or [expected_pot]

def test_nl_minimum_raise():
    """Test minimum raise rules in No Limit."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_blind=5,
        big_blind=10
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'

    # Check valid actions for button (Alice)
    valid_actions = game.get_valid_actions("BTN")

    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions  # call the blinds for $10
    assert (PlayerAction.RAISE, 20, 500) in valid_actions  # minimum raise after blinds is double the amount of big blind

    # Initial state should have BB=10
    assert game.betting.current_bet == 10
    
    # BTN raise to 20 (minimum raise is BB + BB = 20)
    result = game.player_action("BTN", PlayerAction.RAISE, 20)
    assert result.success
    assert game.betting.current_bet == 20
    
    # Invalid raise attempts by SB
    result = game.player_action("SB", PlayerAction.RAISE, 25)  # Too small
    assert not result.success
    
    # Valid raise to 40 (previous raise was 10, so new raise must be at least 10 more)
    result = game.player_action("SB", PlayerAction.RAISE, 40)
    assert result.success
    assert game.betting.current_bet == 40

def test_nl_all_in_less_than_minimum():
    """Test all-in bets that are less than minimum raise."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_blind=5,
        big_blind=10,
        starting_stack=25  # Small stack to force all-ins
    )
    game.start_hand()

    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'

    # Initial stacks after blinds (SB posts 5, BB posts 10)
    assert game.betting.get_main_pot_amount()  == 15  # SB (5) + BB (10)
    assert game.table.players["BTN"].stack == 25
    assert game.table.players["SB"].stack == 20  # 25 - 5 blind
    assert game.table.players["BB"].stack == 15  # 25 - 10 blind

    # BTN raises to 20
    result = game.player_action("BTN", PlayerAction.RAISE, 20)
    assert result.success
    assert game.betting.current_bet == 20

    # Verify stack updates
    assert game.table.players["BTN"].stack == 5   # 25 - 20
    assert game.betting.get_main_pot_amount()  == 35        # 15 + 20

    # SB all-in for 25 (correct all-in raise)
    result = game.player_action("SB", PlayerAction.RAISE, 25)
    assert result.success
    assert game.table.players["SB"].stack == 0    # SB is all-in
    assert game.betting.get_main_pot_amount()  == 55        # 35 + 20

    # BB can only call 15 more or fold - no raise possible with only 15 left
    result = game.player_action("BB", PlayerAction.CALL, 25)  # Call SB's all-in
    assert result.success
    assert game.table.players["BB"].stack == 0    # BB used their last 15 to call
    assert game.betting.get_main_pot_amount()  == 70        # 55 + 15

    # Final stacks check
    assert game.table.players["BTN"].stack == 5
    assert game.table.players["SB"].stack == 0
    assert game.table.players["BB"].stack == 0

    # Final pot check
    assert game.betting.get_main_pot_amount() == 70  # Total pot after all actions

def test_pot_limit_maximum_bet():
    """Test pot-size bet calculations in Pot Limit."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.POT_LIMIT,
        small_blind=5,
        big_blind=10
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'
        
    # Initial pot is 15 (SB=5 + BB=10)
    assert game.betting.get_main_pot_amount() == 15
    
    # Try to raise more than pot limit
    result = game.player_action("BTN", PlayerAction.RAISE, 36)  # More than max of 35
    assert not result.success
    
    # Verify maximum raise is allowed
    result = game.player_action("BTN", PlayerAction.RAISE, 35)  # Max valid raise
    assert result.success
    
    # Verify final amounts
    assert game.betting.current_bet == 35
    assert game.betting.get_main_pot_amount() == 50  # Initial 15 + BTN's 25 more
    assert game.table.players["BTN"].stack == 465  # Started 500, put in 35

def test_pot_limit_initial_raise():
    """Test basic pot limit raise calculation."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.POT_LIMIT,
        small_blind=5,
        big_blind=10
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'
        
    # Initial state
    assert game.betting.get_main_pot_amount() == 15  # SB(5) + BB(10)
    assert game.table.players["BTN"].stack == 500
    assert game.table.players["SB"].stack == 495  # After 5 blind
    assert game.table.players["BB"].stack == 490  # After 10 blind
    
    # BTN raise calculation:
    # - Current pot: 15
    # - After BTN's call (10): 25
    # - Can raise by size of pot (25)
    # - Total bet: 35 (10 call + 25 raise)
    
    # Try various raises
    result = game.player_action("BTN", PlayerAction.RAISE, 36)  # Too much
    assert not result.success
    
    result = game.player_action("BTN", PlayerAction.RAISE, 34)  # Valid but not max
    assert result.success
    assert game.betting.current_bet == 34
    assert game.betting.get_main_pot_amount() == 49  # 15 + 34
    assert game.table.players["BTN"].stack == 466  # 500 - 34
    
    # Now SB acts:
    # - Current pot: 49
    # - To call: 29 (34 - 5 already in)
    # - After call pot would be: 78
    # - Can raise by 78 more
    # - Total max bet: 112 (34 current bet + 78 raise)
    result = game.player_action("SB", PlayerAction.RAISE, 113)  # Too much
    assert not result.success
    
    result = game.player_action("SB", PlayerAction.RAISE, 112)  # Maximum allowed
    assert result.success
    assert game.betting.current_bet == 112
    assert game.betting.get_main_pot_amount() == 156  # 49 + 107 (112-5 already in)

def test_pot_limit_multiple_raises():
    """Test a sequence of pot limit raises."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.POT_LIMIT,
        small_blind=5,
        big_blind=10,
        starting_stack=1000  # Need bigger stacks for multiple raises
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'
        
    # Initial pot: 15
    # BTN max raise to 35
    result = game.player_action("BTN", PlayerAction.RAISE, 35)
    assert result.success
    assert game.betting.get_main_pot_amount() == 50  # 15 + 35
    
    # SB can now:
    # - Current pot: 50
    # - To call: 30 (35 - 5 in)
    # - After call: 80
    # - Can raise by 80
    # - Max bet: 115 (35 + 80)
    result = game.player_action("SB", PlayerAction.RAISE, 115)
    assert result.success
    assert game.betting.get_main_pot_amount() == 160  # 50 + 110 (115-5)
    
    # BB can now:
    # - Current pot: 160
    # - To call: 105 (115 - 10 in)
    # - After call: 265
    # - Can raise by 265
    # - Max bet: 380 (115 + 265)
    result = game.player_action("BB", PlayerAction.RAISE, 380)
    assert result.success
    assert game.betting.get_main_pot_amount() == 530  # 160 + 370 (380-10)

def test_pot_limit_small_raises():
    """Test minimum raises in pot limit."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.POT_LIMIT,
        small_blind=5,
        big_blind=10
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'
        
    # Minimum raise should be double the previous bet
    result = game.player_action("BTN", PlayerAction.RAISE, 19)  # Less than min
    assert not result.success
    
    result = game.player_action("BTN", PlayerAction.RAISE, 20)  # Min raise
    assert result.success
    assert game.betting.current_bet == 20

def test_pot_limit_all_in_under_max():
    """Test all-in bets under the pot limit maximum."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.POT_LIMIT,
        small_blind=5,
        big_blind=10,
        player_stacks={
            "BTN": 30,
            "SB": 495,
            "BB": 490
        }
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'
        
    # BTN only has 30, pot limit would allow 35
    result = game.player_action("BTN", PlayerAction.RAISE, 30)  # All-in
    assert result.success
    assert game.betting.current_bet == 30
    assert game.table.players["BTN"].stack == 0
    
    # SB now betting - pot is 45, max raise higher
    result = game.player_action("SB", PlayerAction.RAISE, 90)
    assert result.success

def test_pot_limit_edge_cases():
    """Test edge cases and unusual situations."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.POT_LIMIT,
        small_blind=5,
        big_blind=10
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'
        
    # Try to raise less than BB
    result = game.player_action("BTN", PlayerAction.RAISE, 15)
    assert not result.success
    
    # Try exactly pot size bet
    result = game.player_action("BTN", PlayerAction.RAISE, 35)
    assert result.success
    
    # Verify all numbers exactly
    assert game.betting.current_bet == 35
    assert game.betting.get_main_pot_amount() == 50
    
    # Detailed position of each player
    assert game.table.players["BTN"].stack == 465  # 500 - 35
    assert game.table.players["SB"].stack == 495  # No change yet
    assert game.table.players["BB"].stack == 490  # No change yet            

def test_side_pots_all_in():
    """Test side pot creation with multiple all-ins."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_blind=5,
        big_blind=10,
        player_stacks={
            "BTN": 100,
            "SB": 40,
            "BB": 60
        }
    )
    game.start_hand()
    
    # Move to dealing, then betting phase
    game._next_step()
    game._next_step()
    
    assert game.current_player.id == 'BTN'
        
    # BTN raises to 30
    result = game.player_action("BTN", PlayerAction.RAISE, 30)
    assert result.success
    
    # SB all-in for 40
    result = game.player_action("SB", PlayerAction.RAISE, 40)
    assert result.success
    
    # BB all-in for 60
    result = game.player_action("BB", PlayerAction.RAISE, 60)
    assert result.success
    
    # BTN calls 60
    result = game.player_action("BTN", PlayerAction.CALL, 60)
    assert result.success
       
    # Verify pot structure
    assert game.betting.get_side_pot_count() == 1
    # Main pot has $40 from SB, $40 fro mBB, $40 from BTN
    assert game.betting.get_main_pot_amount() == 120
    # Side pot: BB and BTN contribute 20 more each (40 total)
    assert game.betting.get_side_pot_amount(0) == 40
