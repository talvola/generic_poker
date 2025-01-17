"""Helper functions and fixtures for poker game tests."""
import json
from typing import Dict, List, Optional

from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game
from generic_poker.config.loader import BettingStructure
from generic_poker.core.card import Card

DEFAULT_RULES = {
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

def load_test_rules() -> GameRules:
    """Load default test rules."""
    return GameRules.from_json(json.dumps(DEFAULT_RULES))

def create_test_game(
    num_players: int = 3,
    mock_hands: Optional[Dict[str, List[Card]]] = None,
    small_bet: int = 10,
    big_bet: int = 20,
    starting_stack: int = 500
) -> Game:
    """
    Create a test game with specified number of players and optional preset hands.
    
    Args:
        num_players: Number of players (2 or 3)
        mock_hands: Optional dict mapping player IDs to their test hands
        small_bet: Size of small bet (default 10)
        big_bet: Size of big bet (default 20)
        starting_stack: Starting stack for each player (default 500)
        
    Returns:
        Configured game instance
    """
    if num_players not in (2, 3):
        raise ValueError("Only 2 or 3 player games supported for testing")
        
    game = Game(
        rules=load_test_rules(),
        structure=BettingStructure.LIMIT,
        small_bet=small_bet,
        big_bet=big_bet,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False  # Don't automatically progress to next step
    )
    
    # Add players based on num_players
    if num_players >= 3:
        game.add_player("BTN", "Alice", starting_stack)  # Button
    game.add_player("SB", "Bob", starting_stack)     # Small Blind
    game.add_player("BB", "Charlie", starting_stack) # Big Blind
    
    if mock_hands:
        # Replace the deal step to use our test hands
        def mock_deal(self, config):
            for pid, hand in mock_hands.items():
                self.table.players[pid].hand.clear()
                self.table.players[pid].hand.add_cards(hand)
        game._handle_deal = mock_deal.__get__(game)
    
    return game