"""Integration tests for game configuration validation."""
import pytest
from pathlib import Path
import json
import jsonschema

from generic_poker.config.loader import GameRules, GameActionType


@pytest.fixture
def schema():
    """Load the JSON schema for game configurations."""
    schema_path = Path(__file__).parents[2] / "data" / "schemas" / "game.json"
    with open(schema_path) as f:
        return json.load(f)


def test_all_game_configs(schema):
    """Test that all game configurations in data/game_configs are valid."""
    config_dir = Path(__file__).parents[2] / "data" / "game_configs"
    
    # Get all JSON files in the config directory
    config_files = list(config_dir.glob("*.json"))
    assert len(config_files) > 0, "No game configuration files found"
    
    for config_file in config_files:
        # Load and validate against schema
        with open(config_file) as f:
            config = json.load(f)
            
        try:
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            pytest.fail(f"Schema validation failed for {config_file.name}: {e}")
            
        try:
            # Load and validate with our GameRules class
            rules = GameRules.from_file(config_file)
            
            # Additional game-specific validation
            validate_betting_sequence(rules)
            validate_card_requirements(rules)
            
        except ValueError as e:
            pytest.fail(f"GameRules validation failed for {config_file.name}: {e}")


def validate_betting_sequence(rules: GameRules):
    """
    Validate that the betting sequence makes sense.
    
    Args:
        rules: GameRules instance to validate
        
    Raises:
        ValueError: If betting sequence is invalid
    """
    bet_steps = [
        step for step in rules.gameplay 
        if step.action_type == GameActionType.BET
    ]
    
    if not bet_steps:
        raise ValueError("Game must have at least one betting round")
    
    # Check first betting step is blinds/antes if present
    if bet_steps[0].action_config["type"] not in ["blinds", "antes"]:
        raise ValueError("First betting step must be blinds or antes")


def validate_card_requirements(rules: GameRules):
    """
    Validate that card requirements in showdown match cards dealt.
    
    Args:
        rules: GameRules instance to validate
        
    Raises:
        ValueError: If card requirements are inconsistent
    """
    # Count cards dealt to players
    player_cards = sum(
        sum(c["number"] for c in step.action_config["cards"])
        for step in rules.gameplay
        if step.action_type == GameActionType.DEAL 
        and step.action_config["location"] == "player"
    )
    
    # Count community cards
    community_cards = sum(
        sum(c["number"] for c in step.action_config["cards"])
        for step in rules.gameplay
        if step.action_type == GameActionType.DEAL 
        and step.action_config["location"] == "community"
    )
    
    # Validate against showdown requirements
    for hand_rule in rules.showdown.best_hand:
        if "holeCards" in hand_rule:
            if isinstance(hand_rule["holeCards"], int):
                if hand_rule["holeCards"] > player_cards:
                    raise ValueError(
                        f"Showdown requires {hand_rule['holeCards']} hole cards "
                        f"but only {player_cards} are dealt"
                    )
        
        if "communityCards" in hand_rule:
            if isinstance(hand_rule["communityCards"], int):
                if hand_rule["communityCards"] > community_cards:
                    raise ValueError(
                        f"Showdown requires {hand_rule['communityCards']} community cards "
                        f"but only {community_cards} are dealt"
                    )