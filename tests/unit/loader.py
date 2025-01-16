"""Unit tests for game configuration loading and validation."""
import pytest
from pathlib import Path
import json

from generic_poker.config.loader import GameRules, BettingStructure, GameActionType


@pytest.fixture
def straight_poker_config():
    """Sample configuration for Straight Poker."""
    return {
        "game": "Straight Poker",
        "players": {
            "min": 2,
            "max": 9
        },
        "deck": {
            "type": "standard",
            "cards": 52
        },
        "bettingStructures": [
            "Limit",
            "No Limit",
            "Pot Limit"
        ],
        "gamePlay": [
            {
                "bet": {
                    "type": "blinds"
                },
                "name": "Post Blinds"
            },
            {
                "deal": {
                    "location": "player",
                    "cards": [
                        {
                            "number": 5,
                            "state": "face down"
                        }
                    ]
                },
                "name": "Deal Hole Cards"
            },
            {
                "bet": {
                    "type": "small"
                },
                "name": "Initial Bet"
            },
            {
                "showdown": {
                    "type": "final"
                },
                "name": "Showdown"
            }
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [
                {
                    "evaluationType": "high",
                    "anyCards": 5
                }
            ]
        }
    }


def test_load_valid_config(straight_poker_config):
    """Test loading a valid configuration."""
    rules = GameRules.from_json(json.dumps(straight_poker_config))
    assert rules.game == "Straight Poker"
    assert rules.min_players == 2
    assert rules.max_players == 9
    assert rules.deck_type == "standard"
    assert rules.deck_size == 52
    assert set(rules.betting_structures) == {
        BettingStructure.LIMIT,
        BettingStructure.NO_LIMIT,
        BettingStructure.POT_LIMIT
    }
    assert len(rules.gameplay) == 4


def test_invalid_deck_type():
    """Test validation of invalid deck type."""
    config = {
        "game": "Test Game",
        "players": {"min": 2, "max": 4},
        "deck": {
            "type": "invalid_type",
            "cards": 52
        },
        "bettingStructures": ["Limit"],
        "gamePlay": [],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all",
            "bestHand": [{"evaluationType": "high"}]
        }
    }
    with pytest.raises(ValueError, match="Invalid deck type"):
        GameRules.from_json(json.dumps(config))


def test_invalid_player_count():
    """Test validation of invalid player counts."""
    config = {
        "game": "Test Game",
        "players": {"min": 1, "max": 4},  # Min should be at least 2
        "deck": {
            "type": "standard",
            "cards": 52
        },
        "bettingStructures": ["Limit"],
        "gamePlay": [],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all",
            "bestHand": [{"evaluationType": "high"}]
        }
    }
    with pytest.raises(ValueError, match="Minimum players must be at least 2"):
        GameRules.from_json(json.dumps(config))


def test_too_many_cards():
    """Test validation of games requiring too many cards."""
    config = {
        "game": "Test Game",
        "players": {"min": 2, "max": 10},
        "deck": {
            "type": "standard",
            "cards": 52
        },
        "bettingStructures": ["Limit"],
        "gamePlay": [
            {
                "name": "Deal Cards",
                "deal": {
                    "location": "player",
                    "cards": [{"number": 6, "state": "face down"}]
                }
            }
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all",
            "bestHand": [{"evaluationType": "high"}]
        }
    }
    with pytest.raises(ValueError, match="Game requires .* cards but deck only has"):
        GameRules.from_json(json.dumps(config))


def test_gameplay_step_parsing():
    """Test correct parsing of different gameplay step types."""
    config = {
        "game": "Test Game",
        "players": {"min": 2, "max": 4},
        "deck": {
            "type": "standard",
            "cards": 52
        },
        "bettingStructures": ["Limit"],
        "gamePlay": [
            {
                "name": "Bet Step",
                "bet": {"type": "small"}
            },
            {
                "name": "Deal Step",
                "deal": {
                    "location": "player",
                    "cards": [{"number": 1, "state": "face down"}]
                }
            },
            {
                "name": "Draw Step",
                "draw": {
                    "cards": [{"number": 1, "state": "face down"}]
                }
            }
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all",
            "bestHand": [{"evaluationType": "high"}]
        }
    }
    
    rules = GameRules.from_json(json.dumps(config))
    steps = rules.gameplay
    
    assert len(steps) == 3
    assert steps[0].action_type == GameActionType.BET
    assert steps[1].action_type == GameActionType.DEAL
    assert steps[2].action_type == GameActionType.DRAW