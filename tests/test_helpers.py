"""Test helper functions and fixtures."""
from pathlib import Path
from typing import List, Dict, Optional
import json

from generic_poker.config.loader import GameRules, BettingStructure
from generic_poker.game.game import Game
from generic_poker.core.card import Card


def load_test_rules() -> GameRules:
    """Load default test rules."""
    rules = {
        "game": "Straight Poker",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 5, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"bet": {"type": "small"}, "name": "Initial Bet"},
            {"showdown": {"type": "final"}, "name": "Showdown"}
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}]
        }
    }
    return GameRules.from_json(json.dumps(rules))

def load_rules_from_file(game: str) -> GameRules:
    """Load Straight Poker game rules."""
    game_file = game + '.json'
    rules_path = Path(__file__).parents[1] / 'data' / 'game_configs' / game_file
    with open(rules_path) as f:
        return GameRules.from_json(f.read())

def create_test_game(
    num_players: int = 3,
    structure: BettingStructure = BettingStructure.LIMIT,
    small_bet: int = 10, # for Limit games
    big_bet: Optional[int] = None,
    small_blind: int = 5, # use for No/Pot-Limit games
    big_blind: int = 10, # use for No/Pot-Limit games
    starting_stack: int = 500,
    player_stacks: Optional[Dict[str, int]] = None,
    mock_hands: Optional[Dict[str, List[Card]]] = None,
    auto_progress: bool = False
) -> Game:
    """
    Create a test game with specified configuration.
    
    Args:
        num_players: Number of players (2 or 3)
        structure: Betting structure to use
        small_bet: Size of small bet
        big_bet: Size of big bet (defaults to 2x small bet)
        starting_stack: Default stack size for players
        player_stacks: Optional specific stacks per player
        mock_hands: Optional preset hands for testing
    """
    rules = load_test_rules()

    # Set min_buyin to accommodate specified stacks
    min_stack = starting_stack
    if player_stacks:
        min_stack = min(player_stacks.values())

    game = Game(
        rules=rules,
        structure=structure,
        small_bet=small_bet,
        big_bet=big_bet or (small_bet * 2),
        small_blind=small_blind,
        big_blind=big_blind,
        min_buyin=min(20, min_stack),  # Allow small stacks for testing
        max_buyin=1000,
        auto_progress=auto_progress
    )
    
    # Add players with specified stacks
    stacks = player_stacks or {}
    if num_players >= 3:
        game.add_player("BTN", "Alice", stacks.get("BTN", starting_stack))
        game.add_player("SB", "Bob", stacks.get("SB", starting_stack))
        game.add_player("BB", "Charlie", stacks.get("BB", starting_stack))
    elif num_players == 2:
        game.add_player("SB", "Bob", stacks.get("SB", starting_stack))
        game.add_player("BB", "Charlie", stacks.get("BB", starting_stack))
    
    # Set up mock hands if provided
    if mock_hands:
        def mock_deal(self, config):
            for pid, hand in mock_hands.items():
                self.table.players[pid].hand.clear()
                self.table.players[pid].hand.add_cards(hand)
        game._handle_deal = mock_deal.__get__(game)
    
    return game