"""Tests for No Limit and Pot Limit betting behavior."""
import pytest
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.config.loader import GameRules, BettingStructure
from test_helpers import create_test_game

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
        small_bet=10  # This is the minimum bet size
    )
    game.start_hand()
    
    # Move to betting phase
    while game.state != GameState.BETTING:
        game._next_step()
    
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
        small_bet=10,
        starting_stack=25  # Small stack to force all-ins
    )
    game.start_hand()
    
    # Move to betting
    while game.state != GameState.BETTING:
        game._next_step()
        
    # BTN raise to 20
    result = game.player_action("BTN", PlayerAction.RAISE, 20)
    assert result.success
    
    # SB all-in for 15 (less than min raise but allowed because it's all-in)
    result = game.player_action("SB", PlayerAction.RAISE, 15)
    assert result.success
    assert game.betting.current_bet == 20  # Original raise still sets the mark
    
    # BB can still re-raise to 40 because BTN's raise set the increment
    result = game.player_action("BB", PlayerAction.RAISE, 40)
    assert result.success

def test_pot_limit_maximum_bet():
    """Test pot-size bet calculations in Pot Limit."""
    game = create_test_game(
        num_players=3,
        structure=BettingStructure.POT_LIMIT,
        small_bet=10
    )
    game.start_hand()
    
    # Move to betting
    while game.state != GameState.BETTING:
        game._next_step()
        
    # Initial pot is 15 (SB=5 + BB=10)
    # Maximum raise is: pot(15) + BB(10) + call(10) = 35
    assert game.betting.pot.main_pot == 15
    
    # Try to raise more than pot limit
    result = game.player_action("BTN", PlayerAction.RAISE, 40)
    assert not result.success
    
    # Valid pot limit raise
    result = game.player_action("BTN", PlayerAction.RAISE, 35)
    assert result.success
    
    # New pot is 50, max raise is: pot(50) + current_bet(35) + call(35) = 120
    assert game.betting.pot.main_pot == 50

def test_side_pots_all_in():
    """Test side pot creation with multiple all-ins."""
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
    
    # Move to betting
    while game.state != GameState.BETTING:
        game._next_step()
        
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
    assert len(game.betting.pot.side_pots) == 2
    # Main pot should have 40 from each player (120 total)
    assert game.betting.pot.main_pot == 120
    # First side pot: BB and BTN contribute 20 more each (40 total)
    assert game.betting.pot.side_pots[0].amount == 40
    # Second side pot: BTN matches BB's last 20
    assert game.betting.pot.side_pots[1].amount == 20