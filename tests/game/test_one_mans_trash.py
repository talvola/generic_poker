"""Test One Man's Trash poker variant."""
import pytest
from pathlib import Path

from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.core.deck import Deck
from tests.test_helpers import create_test_game


def test_one_mans_trash_basic():
    """Test basic One Man's Trash game flow."""
    # Load the game configuration
    config_path = Path(__file__).parents[2] / "data" / "game_configs" / "one_mans_trash.json"
    rules = GameRules.from_file(config_path)
    
    # Create game with 3 players
    game = create_test_game(num_players=3, starting_stack=1000, small_bet=10, big_bet=20)
    # Override the rules with the One Man's Trash rules
    game.rules = rules
    
    # Verify initial setup
    assert game.rules.game == "One Man's Trash"
    assert len(game.table.players) == 3
    assert game.small_bet == 10
    assert game.big_bet == 20


def test_one_mans_trash_community_replacement():
    """Test the community card replacement mechanism."""
    # Load the game configuration
    config_path = Path(__file__).parents[2] / "data" / "game_configs" / "one_mans_trash.json"
    rules = GameRules.from_file(config_path)
    
    # Create game with 3 players
    game = create_test_game(num_players=3, starting_stack=1000, small_bet=10, big_bet=20)
    # Override the rules with the One Man's Trash rules
    game.rules = rules
    
    # Test that the configuration loaded correctly
    assert game.rules.game == "One Man's Trash"
    
    # Verify the game has the expected structure
    gameplay_names = [step.name for step in game.rules.gameplay]
    assert "Community Card Replacement" in gameplay_names
    
    # Find the community replacement step
    replacement_step = None
    for step in game.rules.gameplay:
        if step.name == "Community Card Replacement":
            replacement_step = step
            break
    
    assert replacement_step is not None
    assert hasattr(replacement_step, 'action_config')
    assert replacement_step.action_config["cardsToReplace"] == 2
    assert replacement_step.action_config["order"] == "clockwise"
    assert replacement_step.action_config["startingFrom"] == "left_of_dealer"
    
    # Verify that the game can be started without errors
    try:
        game.start_hand()
        # If we get here, the game started successfully
        assert True
    except Exception as e:
        pytest.fail(f"Game failed to start: {e}")


def test_one_mans_trash_config_validation():
    """Test that the One Man's Trash configuration is valid."""
    config_path = Path(__file__).parents[2] / "data" / "game_configs" / "one_mans_trash.json"
    
    # Should not raise any exceptions
    rules = GameRules.from_file(config_path)
    
    # Verify key properties
    assert rules.game == "One Man's Trash"
    assert rules.min_players == 3
    assert rules.max_players == 6
    assert rules.deck_type == "standard"
    assert rules.deck_size == 52
    
    # Verify gameplay sequence includes community replacement
    step_names = [step.name for step in rules.gameplay]
    assert "Community Card Replacement" in step_names
    
    # Verify the replacement step has correct configuration
    replacement_step = next(step for step in rules.gameplay if step.name == "Community Card Replacement")
    assert replacement_step.action_config["cardsToReplace"] == 2
    assert replacement_step.action_config["order"] == "clockwise"
    assert replacement_step.action_config["startingFrom"] == "left_of_dealer"