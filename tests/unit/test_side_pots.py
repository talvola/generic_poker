"""Tests for side pot creation and management."""
import pytest
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.config.loader import BettingStructure
from test_helpers import create_test_game

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

def test_simple_side_pot():
    """
    Test simplest side pot case:
    - Player A (60): goes all-in
    - Player B (100): calls
    - Player C (100): calls
    Should create one main pot that all are eligible for.
    """
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_bet=10,
        player_stacks={
            "BTN": 100,  # Player C
            "SB": 60,   # Player A
            "BB": 100   # Player B
        }
    )
    game.start_hand()
    
    while game.state != GameState.BETTING:
        game._next_step()
        
    # Initial stacks after blinds
    assert game.betting.pot.main_pot == 15  # SB(5) + BB(10)
    assert game.table.players["BTN"].stack == 100
    assert game.table.players["SB"].stack == 55   # 60 - 5
    assert game.table.players["BB"].stack == 90   # 100 - 10
    
    # SB goes all-in with remaining 55
    result = game.player_action("SB", PlayerAction.RAISE, 60)
    assert result.success
    assert game.table.players["SB"].stack == 0
    
    # BB calls 60
    result = game.player_action("BB", PlayerAction.CALL, 60)
    assert result.success
    
    # BTN calls 60
    result = game.player_action("BTN", PlayerAction.CALL, 60)
    assert result.success
    
    # Verify pot
    assert game.betting.pot.main_pot == 180  # 60 * 3
    assert len(game.betting.pot.side_pots) == 0  # No side pots yet

def test_simple_side_pot_with_extra():
    """
    Test side pot with extra betting:
    - Player A (60): all-in
    - Player B (100): raises more
    - Player C (100): calls raise
    Should create main pot (all eligible) and side pot (B & C only).
    """
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_bet=10,
        player_stacks={
            "BTN": 100,  # Player C
            "SB": 60,   # Player A
            "BB": 100   # Player B
        }
    )
    game.start_hand()
    
    while game.state != GameState.BETTING:
        game._next_step()
        
    # SB goes all-in
    result = game.player_action("SB", PlayerAction.RAISE, 60)
    assert result.success
    assert game.table.players["SB"].stack == 0
    
    # BB raises to 80
    result = game.player_action("BB", PlayerAction.RAISE, 80)
    assert result.success
    
    # BTN calls 80
    result = game.player_action("BTN", PlayerAction.CALL, 80)
    assert result.success
    
    # Verify pots
    assert game.betting.pot.main_pot == 180  # 60 * 3
    assert len(game.betting.pot.side_pots) == 1
    assert game.betting.pot.side_pots[0].amount == 40  # (80-60) * 2
    assert len(game.betting.pot.side_pots[0].eligible_players) == 2

def test_uneven_all_in_amounts():
    """
    Test side pots with uneven all-ins:
    - Player A (40): all-in first
    - Player B (60): all-in for more
    - Player C (100): calls everything
    Should create two side pots.
    """
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_bet=10,
        player_stacks={
            "BTN": 100,  # Player C
            "SB": 40,   # Player A
            "BB": 60    # Player B
        }
    )
    game.start_hand()
    
    while game.state != GameState.BETTING:
        game._next_step()
        
    # Detailed debugging of initial state
    print(f"\nInitial pot: {game.betting.pot.main_pot}")
    print(f"Initial stacks: BTN={game.table.players['BTN'].stack}, "
          f"SB={game.table.players['SB'].stack}, "
          f"BB={game.table.players['BB'].stack}")
    
    # SB goes all-in for 40
    result = game.player_action("SB", PlayerAction.RAISE, 40)
    assert result.success
    assert game.table.players["SB"].stack == 0
    
    print(f"\nAfter SB all-in:")
    print(f"Pot: {game.betting.pot.main_pot}")
    print(f"Stacks: BTN={game.table.players['BTN'].stack}, "
          f"SB={game.table.players['SB'].stack}, "
          f"BB={game.table.players['BB'].stack}")
    
    # BB raises all-in to 60
    result = game.player_action("BB", PlayerAction.RAISE, 60)
    assert result.success
    assert game.table.players["BB"].stack == 0
    
    print(f"\nAfter BB all-in:")
    print(f"Pot: {game.betting.pot.main_pot}")
    print(f"Side pots: {len(game.betting.pot.side_pots)}")
    
    # BTN calls
    result = game.player_action("BTN", PlayerAction.CALL, 60)
    assert result.success
    
    # Verify pot structure
    assert len(game.betting.pot.side_pots) == 2
    
    # Main pot should have 40 from each player (120 total)
    assert game.betting.pot.main_pot == 120
    
    # First side pot: BB and BTN contribute 20 more each (40 total)
    assert game.betting.pot.side_pots[0].amount == 40
    assert len(game.betting.pot.side_pots[0].eligible_players) == 2
    assert "BB" in game.betting.pot.side_pots[0].eligible_players
    assert "BTN" in game.betting.pot.side_pots[0].eligible_players