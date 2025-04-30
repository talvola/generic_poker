"""Unit tests for Pot class."""
import pytest
from generic_poker.game.game import Game
from generic_poker.game.table import Player
from generic_poker.game.game_state import PlayerAction, GameState
from generic_poker.config.loader import BettingStructure

from tests.test_helpers import load_rules_from_file

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
        force=True
    )

def test_declare_action():
    rules = load_rules_from_file('straight_declare')
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        auto_progress=False)
    game.add_player("BTN", "Alice", 500)
    game.add_player("SB", "Bob", 500)
    game.add_player("BB", "Charlie", 500)
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING    
    game._next_step()  # Deal cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    game._next_step()  # Move to initial bet
    assert game.current_step == 2
    assert game.state == GameState.BETTING    
    game.player_action('BTN', PlayerAction.CALL, 10)
    game.player_action('SB', PlayerAction.CALL, 10)
    game.player_action('BB', PlayerAction.CHECK)
    # move to declare
    game._next_step()

    # we are at declare now
    assert game.current_step == 3
    assert game.state == GameState.DRAWING
    player = game.table.players["SB"]
    declaration_data = [{"pot_index": -1, "declaration": "high"}]
    result = game.player_action(player.id, PlayerAction.DECLARE, declaration_data=declaration_data)
    assert result.success
    assert game.action_handler.pending_declarations[player.id] == declaration_data    
