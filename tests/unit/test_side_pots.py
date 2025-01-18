"""Tests for complex betting scenarios including all-ins and side pots."""
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

def print_betting_state(game: Game, msg: str):
    """Helper to print detailed betting state."""
    print(f"\n{msg}:")
    print("─" * 50)
    print(f"Pot: {game.betting.pot.main_pot}")
    print(f"Current bet: {game.betting.current_bet}")
    print("\nBetting history:")
    for pid, bet in game.betting.current_bets.items():
        player = game.table.players[pid]
        print(f"  {pid:3s}: bet={bet.amount:3d}, stack={player.stack:3d}, "
              f"{'blind ' if bet.posted_blind else ''}"
              f"{'all-in ' if bet.is_all_in else ''}"
              f"{'acted ' if bet.has_acted else 'not acted'}")
    print("─" * 50)


def test_simple_side_pot():
    """
    Test simplest all-in scenario.
    
    Initial stacks:
    - BTN: 100
    - SB: 60   (60 - 5 = 55 available)
    - BB: 100  (100 - 10 = 90 available)
    
    Betting sequence:
    1. BTN calls 10 (puts in 10)
    2. SB raises all-in (adds 55 to their 5 = 60 total)
    3. BB calls (adds 50 to their 10 = 60 total)
    4. BTN calls (adds 50 to their 10 = 60 total)
    
    Final state:
    - Each player has contributed exactly 60
    - Total pot should be 180
    - No side pots (everyone put in same amount)
    """
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_bet=10,
        player_stacks={
            "BTN": 100,
            "SB": 60,   
            "BB": 100   
        }
    )
    game.start_hand()
    
    while game.state != GameState.BETTING:
        game._next_step()

    # Initial state (after blinds)
    print_betting_state(game, "Initial state")
    assert game.betting.pot.main_pot == 15, "Pot should be SB(5) + BB(10)"
    assert game.table.players["BTN"].stack == 100, "BTN shouldn't post blind"
    assert game.table.players["SB"].stack == 55, "SB should have posted 5"
    assert game.table.players["BB"].stack == 90, "BB should have posted 10"
    
    # BTN calls 10
    result = game.player_action("BTN", PlayerAction.CALL, 10)
    assert result.success, "BTN's call should succeed"
    print_betting_state(game, "After BTN calls")
    assert game.betting.pot.main_pot == 25, "Pot should include BTN's call"
    assert game.table.players["BTN"].stack == 90, "BTN stack reduced by call"
    
    # Verify SB's valid actions
    valid_actions = game.get_valid_actions("SB")
    print("\nValid actions for SB:")
    for action, min_amount, max_amount in valid_actions:
        print(f"- {action}: min={min_amount}, max={max_amount}")
    
    # SB raises all-in (adding 55 to their 5 blind for total 60)
    result = game.player_action("SB", PlayerAction.RAISE, 55)
    assert result.success, "SB's all-in raise should succeed"
    print_betting_state(game, "After SB all-in raise")
    assert game.betting.current_bet == 60, "Current bet should be SB's total (55 + 5 blind)"
    assert game.table.players["SB"].stack == 0, "SB should be all-in"
    
    # Track incremental betting
    assert game.betting.current_bets["SB"].amount == 60, "SB total bet wrong"
    assert game.betting.pot.main_pot == 80, "Pot wrong after SB raise"
    
    # BB calls 60 (adds 50 to their 10)
    result = game.player_action("BB", PlayerAction.CALL, 60)
    assert result.success, "BB's call should succeed"
    print_betting_state(game, "After BB calls")
    assert game.betting.current_bets["BB"].amount == 60, "BB total bet wrong"
    assert game.table.players["BB"].stack == 40, "BB stack wrong after call"
    assert game.betting.pot.main_pot == 130, "Pot wrong after BB call"
    
    # BTN calls 60 (adds 50 to their 10)
    result = game.player_action("BTN", PlayerAction.CALL, 60)
    assert result.success, "BTN's call should succeed"
    print_betting_state(game, "After BTN calls")
    
    # Final state verification
    assert game.betting.current_bet == 60, "Final current bet should be 60"
    assert game.betting.pot.main_pot == 180, "Final pot should be 180 (60 * 3)"
    assert len(game.betting.pot.side_pots) == 0, "Should be no side pots"
    
    # Verify final stacks
    assert game.table.players["BTN"].stack == 40, "BTN final stack wrong"
    assert game.table.players["SB"].stack == 0, "SB should be all-in"
    assert game.table.players["BB"].stack == 40, "BB final stack wrong"
    
    # Verify all players put in exactly 60
    for pid, bet in game.betting.current_bets.items():
        assert bet.amount == 60, f"Player {pid} total bet should be 60"

def test_side_pot_with_extra():
    """
    Test side pot creation when betting continues after an all-in.
    
    Initial stacks:
    - BTN: 100
    - SB: 60   (60 - 5 = 55 available)
    - BB: 100  (100 - 10 = 90 available)
    
    Betting sequence:
    1. BTN calls 10
    2. SB raises all-in (adds 55 to their 5 = 60 total)
    3. BB raises to 80 (20 more than SB's all-in)
    4. BTN calls 80
    """
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_bet=10,
        player_stacks={
            "BTN": 100,
            "SB": 60,   
            "BB": 100   
        }
    )
    game.start_hand()
    
    while game.state != GameState.BETTING:
        game._next_step()

    print_betting_state(game, "Initial state")
    assert game.betting.pot.main_pot == 15
    
    # BTN calls 10
    result = game.player_action("BTN", PlayerAction.CALL, 10)
    assert result.success
    print_betting_state(game, "After BTN calls")
    
    # Before SB acts, show valid actions
    valid_actions = game.get_valid_actions("SB")
    print("\nValid actions for SB:")
    for action, min_amount, max_amount in valid_actions:
        print(f"- {action}: min={min_amount}, max={max_amount}")
    
    # SB raises all-in (adding 55 to their 5 blind)
    result = game.player_action("SB", PlayerAction.RAISE, 55)
    assert result.success
    print_betting_state(game, "After SB all-in")
    
    # Before BB acts, show valid actions
    valid_actions = game.get_valid_actions("BB")
    print("\nValid actions for BB:")
    for action, min_amount, max_amount in valid_actions:
        print(f"- {action}: min={min_amount}, max={max_amount}")
    
    # Calculate minimum raise increment
    print("\nRaise calculation:")
    print(f"Previous bet: {game.betting.current_bet}")
    print(f"BB has in: {game.betting.current_bets['BB'].amount}")
    print(f"BB stack: {game.table.players['BB'].stack}")
    print(f"Last raise size: {game.betting.last_raise_size}")
    
    # BB can either:
    # 1. Fold
    # 2. Call 60
    # 3. Raise to at least 115 (but only has 90 total, so must go all-in)
    result = game.player_action("BB", PlayerAction.RAISE, 100)  # All-in
    assert result.success
    print_betting_state(game, "After BB all-in raise")
   
    # BTN calls 80
    result = game.player_action("BTN", PlayerAction.CALL, 80)
    assert result.success
    print_betting_state(game, "After BTN calls")
    
    # Verify final state
    # Main pot of 180 (60 from each player)
    assert game.betting.pot.main_pot == 180
    
    # Side pot of 80 (BB and BTN each put in 40 more)
    assert len(game.betting.pot.side_pots) == 1
    assert game.betting.pot.side_pots[0].amount == 80
    eligible = game.betting.pot.side_pots[0].eligible_players
    assert len(eligible) == 2
    assert "BB" in eligible and "BTN" in eligible
    
    # Total pot should be 260
    assert game.betting.pot.total == 260
    
    # Final stacks
    assert game.table.players["BTN"].stack == 0   # All-in
    assert game.table.players["SB"].stack == 0    # All-in
    assert game.table.players["BB"].stack == 0    # All-in

def test_uneven_all_in_amounts():
    """
    Test side pots with uneven all-ins:
    Action order: BTN -> SB -> BB
    BTN calls, SB all-in small, BB all-in bigger, BTN calls all.
    Should create two side pots.
    """
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.NO_LIMIT,
        small_bet=10,
        player_stacks={
            "BTN": 100,
            "SB": 40,
            "BB": 60
        }
    )
    game.start_hand()
    
    while game.state != GameState.BETTING:
        game._next_step()
        
    # Initial state
    assert game.betting.pot.main_pot == 15  # SB(5) + BB(10)
    assert game.table.players["BTN"].stack == 100
    assert game.table.players["SB"].stack == 35   # 40 - 5
    assert game.table.players["BB"].stack == 50   # 60 - 10
    
    # BTN calls 10
    result = game.player_action("BTN", PlayerAction.CALL, 10)
    assert result.success
    assert game.table.players["BTN"].stack == 90
    
    # SB goes all-in for 40 total (35 more)
    result = game.player_action("SB", PlayerAction.RAISE, 40)
    assert result.success
    assert game.table.players["SB"].stack == 0
    
    # BB raises all-in to 60
    result = game.player_action("BB", PlayerAction.RAISE, 60)
    assert result.success
    assert game.table.players["BB"].stack == 0
    
    # BTN calls 60
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
    
    # Final stacks
    assert game.table.players["BTN"].stack == 40  # 100 - 60
    assert game.table.players["SB"].stack == 0    # All-in
    assert game.table.players["BB"].stack == 0    # All-in