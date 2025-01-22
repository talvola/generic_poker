import pytest
from typing import List, Dict, Any, Tuple, Optional
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

class BettingScenario:
    """
    Represents a betting scenario to test.
    
    Note: expected_stacks and expected_pot are the expected values
    after betting completes but before showdown.
    """
    def __init__(
        self,
        name: str,
        actions: List[Tuple[str, PlayerAction, int]],
        expected_stacks: Dict[str, int],
        expected_pot: int,
        num_players: int = 3,
        pot_progression: Optional[List[int]] = None  # Add intermediate pot amounts
    ):
        self.name = name
        self.actions = actions
        self.expected_stacks = expected_stacks
        self.expected_pot = expected_pot
        self.num_players = num_players
        # If pot_progression not provided, only check final pot amount
        self.pot_progression = pot_progression or [expected_pot]

# Test scenarios
SCENARIOS = [
    BettingScenario(
        name="Basic call sequence",
        actions=[
            ("BTN", PlayerAction.CALL, 10),   # Button calls
            ("SB", PlayerAction.CALL, 10),    # SB completes
            ("BB", PlayerAction.CHECK, 10),    # BB checks
        ],
        expected_stacks={
            "BTN": 490,  # Started 500, bet 10
            "SB": 490,   # Started 500, bet 5+5
            "BB": 490,   # Started 500, bet 10
        },
        expected_pot=30,
        pot_progression=[15, 25, 30, 30]  # Initial, after BTN, after SB, after BB
    ),
    
    BettingScenario(
        name="SB raises sequence",
        actions=[
            ("BTN", PlayerAction.CALL, 10),   # Button calls (pot: 15->25)
            ("SB", PlayerAction.RAISE, 20),   # SB raises to 20 (pot: 25->40)
            ("BB", PlayerAction.CALL, 20),    # BB calls raise (pot: 40->50)
            ("BTN", PlayerAction.CALL, 20),   # BTN calls raise (pot: 50->60)
        ],
        expected_stacks={
            "BTN": 480,  # -10, -10
            "SB": 480,   # -5, -15
            "BB": 480,   # -10, -10
        },
        expected_pot=60,
        pot_progression=[15, 25, 40, 50, 60]
    ),
    
    BettingScenario(
        name="Multiple raises",
        actions=[
            ("BTN", PlayerAction.RAISE, 20),  # BTN raises to 20 (pot: 15->35)
            ("SB", PlayerAction.RAISE, 30),   # SB raises to 30 (pot: 35->60)
            ("BB", PlayerAction.CALL, 30),    # BB calls 30 (pot: 60->80)
            ("BTN", PlayerAction.CALL, 30),   # BTN calls 30 (pot: 80->90)
        ],
        expected_stacks={
            "BTN": 470,  # -20, -10
            "SB": 470,   # -5, -25
            "BB": 470,   # -10, -20
        },
        expected_pot=90,
        pot_progression=[15, 35, 60, 80, 90]
    ),
    
    BettingScenario(
        name="Heads up - button calls",
        actions=[
            ("SB", PlayerAction.CALL, 10),   # Button/SB calls BB (pot: 15->20)
            ("BB", PlayerAction.CHECK, 10),   # BB checks
        ],
        expected_stacks={
            "SB": 490,   # Started 500, -5 (blind), -5 (complete)
            "BB": 490,   # Started 500, -10 (blind)
        },
        expected_pot=20,
        num_players=2,
        pot_progression=[15, 20, 20]  # Initial, after SB call, after BB check
    ),
    
    BettingScenario(
        name="Heads up - button raises",
        actions=[
            ("SB", PlayerAction.RAISE, 20),  # Button/SB raises to 20 (pot: 15->30)
            ("BB", PlayerAction.CALL, 20),   # BB calls raise (pot: 30->40)
        ],
        expected_stacks={
            "SB": 480,   # Started 500, -5 (blind), -15 (raise)
            "BB": 480,   # Started 500, -10 (blind), -10 (call)
        },
        expected_pot=40,
        num_players=2,
        pot_progression=[15, 30, 40]
    ),
    
    BettingScenario(
        name="Heads up - BB 3-bets",
        actions=[
            ("SB", PlayerAction.RAISE, 20),  # Button/SB raises to 20 (pot: 15->30)
            ("BB", PlayerAction.RAISE, 30),  # BB re-raises to 30 (pot: 30->50)
            ("SB", PlayerAction.CALL, 30),   # SB calls (pot: 50->60)
        ],
        expected_stacks={
            "SB": 470,   # Started 500, -5 (blind), -25 (raise & call)
            "BB": 470,   # Started 500, -10 (blind), -20 (raise)
        },
        expected_pot=60,
        num_players=2,
        pot_progression=[15, 30, 50, 60]
    ),
    
    BettingScenario(
        name="Heads up - BB folds to raise",
        actions=[
            ("SB", PlayerAction.RAISE, 20),  # Button/SB raises to 20 (pot: 15->30)
            ("BB", PlayerAction.FOLD, 0),    # BB folds, loses blind
        ],
        expected_stacks={
            "SB": 510,   # Started 500, -5 (blind), -15 (raise), +30 (won pot)
            "BB": 490,   # Started 500, -10 (blind, lost)
        },
        expected_pot=30,
        num_players=2,
        pot_progression=[15, 30, 30]
    ),

    BettingScenario(
        name="Simple all-in and call",
        actions=[
            ("BTN", PlayerAction.ALL_IN, 100),  # Button goes all-in
            ("SB", PlayerAction.CALL, 100),     # SB calls all-in
            ("BB", PlayerAction.FOLD, 0),       # BB folds
        ],
        expected_stacks={
            "BTN": 0,    # Started 500, all-in for 100
            "SB": 400,   # Started 500, -5 (blind), -95 (call)
            "BB": 490,   # Started 500, lost 10 blind
        },
        expected_pot=205,  # 100 + 100 + 5
        pot_progression=[15, 115, 205, 205]
    ),

    BettingScenario(
        name="Sequential all-ins creating side pots",
        actions=[
            ("BTN", PlayerAction.ALL_IN, 25),   # Button all-in for 25
            ("SB", PlayerAction.ALL_IN, 50),    # SB all-in for 50
            ("BB", PlayerAction.ALL_IN, 75),    # BB all-in for 75
        ],
        expected_stacks={
            "BTN": 0,    # Started with 25
            "SB": 0,     # Started with 50
            "BB": 0,     # Started with 75
        },
        expected_pot=150,  # 25 + 50 + 75
        pot_progression=[15, 40, 90, 150]  # Track main pot growth
    ),

    BettingScenario(
        name="Active betting then all-in",
        actions=[
            ("BTN", PlayerAction.RAISE, 20),    # BTN raises to 20
            ("SB", PlayerAction.RAISE, 40),     # SB raises to 40
            ("BB", PlayerAction.ALL_IN, 60),    # BB all-in for 60
            ("BTN", PlayerAction.CALL, 60),     # BTN calls
            ("SB", PlayerAction.CALL, 60),      # SB calls
        ],
        expected_stacks={
            "BTN": 440,  # Started 500, -60
            "SB": 440,   # Started 500, -5 blind, -55
            "BB": 0,     # Started 60, all-in
        },
        expected_pot=180,  # 60 + 60 + 60
        pot_progression=[15, 35, 75, 135, 175, 180]
    ),

    BettingScenario(
        name="Multiple all-ins with side pot betting",
        actions=[
            ("BTN", PlayerAction.ALL_IN, 40),   # BTN all-in for 40
            ("SB", PlayerAction.RAISE, 80),     # SB raises to 80
            ("BB", PlayerAction.ALL_IN, 60),    # BB all-in for less
            ("SB", PlayerAction.CALL, 60),      # SB matches BB's all-in
        ],
        expected_stacks={
            "BTN": 0,    # Started with 40
            "SB": 440,   # Started 500, -60
            "BB": 0,     # Started with 60
        },
        expected_pot=160,  # 40 + 60 + 60
        pot_progression=[15, 55, 135, 155, 160]
    )    
]

def verify_pot_state(game: Game, expected_total: int, step_description: str):
    """Verify pot amounts and structure."""
    actual_total = game.betting.pot.total
    assert actual_total == expected_total, \
        f"{step_description}: Expected total pot {expected_total}, got {actual_total}"
    
    # Log detailed pot structure
    print(f"\nPot structure after {step_description}:")
    print(f"Main pot: ${game.betting.pot.main_pot}")
    for i, side_pot in enumerate(game.betting.pot.side_pots):
        print(f"Side pot {i}: ${side_pot.amount}")
        print(f"  Eligible players: {side_pot.eligible_players}")
        print(f"  Capped: {side_pot.capped}")
        if side_pot.capped:
            print(f"  Cap amount: {side_pot.cap_amount}")

@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_betting_scenario(scenario: BettingScenario):
    """Test a betting scenario."""
    game = create_test_game(scenario.num_players)
    game.start_hand()
    
    while game.state != GameState.BETTING:
        game._next_step()
    
    # Verify initial pot
    verify_pot_state(game, scenario.pot_progression[0], "Initial state")
    
    for i, (player_id, action, amount) in enumerate(scenario.actions):
        print(f"\nExecuting {player_id} {action.value} {amount}")
        
        assert game.current_player == player_id, \
            f"Expected {player_id}'s turn, but was {game.current_player}'s"
        
        result = game.player_action(player_id, action, amount)
        assert result.success, f"Action failed: {result.error}"
        
        # Verify pot state after this action
        expected_pot = scenario.pot_progression[i + 1]
        verify_pot_state(game, expected_pot, f"After {player_id} {action.value}")
        
        if action != PlayerAction.FOLD:
            current_bet = game.betting.current_bets.get(player_id, None)
            assert current_bet is not None, f"No bet recorded for {player_id}"
            if action != PlayerAction.CHECK:
                assert current_bet.amount == amount, \
                    f"Expected bet of {amount} for {player_id}, got {current_bet.amount}"
                if current_bet.is_all_in:
                    print(f"Player {player_id} is all-in")
        
        last_action = i == len(scenario.actions) - 1
        if result.state_changed or last_action:
            # Verify final stacks and pot structure
            for player_id, expected_stack in scenario.expected_stacks.items():
                actual_stack = game.table.players[player_id].stack
                assert actual_stack == expected_stack, \
                    f"Expected {player_id} to have {expected_stack}, got {actual_stack}"
            
            verify_pot_state(game, scenario.expected_pot, "Final state")
            break
