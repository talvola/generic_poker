# Game Class Documentation

## Overview

The `Game` class controls the flow and state of a poker game, managing players, cards, betting, and game progression according to specified rules. It orchestrates the interaction between the `Table` and `BettingManager` components.

The game rules are defined using a JSON configuration format that allows for a wide variety of poker variants to be implemented. The `GameRules` class parses and validates this configuration.

## Creating a Game

```python
from generic_poker.config.loader import GameRules, BettingStructure
from generic_poker.game.game import Game
import json

# Load game rules from JSON
rules_json = """
{
  "game": "Texas Hold'em",
  "players": {"min": 2, "max": 9},
  "deck": {"type": "standard", "cards": 52},
  "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
  "gamePlay": [
    {"bet": {"type": "blinds"}, "name": "Post Blinds"},
    {"deal": {"location": "player", "cards": [{"number": 2, "state": "face down"}]}, "name": "Deal Hole Cards"},
    {"bet": {"type": "small"}, "name": "Preflop Betting"},
    {"deal": {"location": "community", "cards": [{"number": 3, "state": "face up"}]}, "name": "Deal Flop"},
    {"bet": {"type": "small"}, "name": "Flop Betting"},
    {"deal": {"location": "community", "cards": [{"number": 1, "state": "face up"}]}, "name": "Deal Turn"},
    {"bet": {"type": "big"}, "name": "Turn Betting"},
    {"deal": {"location": "community", "cards": [{"number": 1, "state": "face up"}]}, "name": "Deal River"},
    {"bet": {"type": "big"}, "name": "River Betting"},
    {"showdown": {"type": "final"}, "name": "Showdown"}
  ],
  "showdown": {
    "order": "clockwise",
    "startingFrom": "dealer",
    "cardsRequired": "all cards",
    "bestHand": [{"evaluationType": "high", "anyCards": 5}]
  }
}
"""

# Create a game with No-Limit betting
game = Game(
    rules=GameRules.from_json(rules_json),
    structure=BettingStructure.NO_LIMIT,
    small_bet=10,  # Small blind / minimum bet
    big_bet=None,  # Not needed for No-Limit
    min_buyin=200,
    max_buyin=1000,
    auto_progress=True  # Automatically progress through game steps
)
```

## Adding and Removing Players

```python
# Add a player with ID, name, and buy-in amount
game.add_player("player1", "Alice", 500)
game.add_player("player2", "Bob", 500)
game.add_player("player3", "Charlie", 500)

# Remove a player
game.remove_player("player3")
```

## Starting a Hand

```python
# Start a new hand
game.start_hand()
```

This initializes a new hand, deals cards, posts blinds, and sets up the first betting round.

## Player Actions

```python
# Get valid actions for the current player
valid_actions = game.get_valid_actions(player_id)
# Returns a list of tuples: (action, min_amount, max_amount)
# Example: [(PlayerAction.FOLD, None, None), (PlayerAction.CALL, 10, 10), (PlayerAction.RAISE, 20, 100)]

# Get formatted actions for display
formatted_actions = game.format_actions_for_display(player_id)
# Returns list of formatted strings
# Example: ["Fold", "Call $10 (+$5)", "Raise to $20 (+$15)"]

# Take an action
result = game.player_action(player_id, PlayerAction.CALL, amount=10)
result = game.player_action(player_id, PlayerAction.RAISE, amount=30)
result = game.player_action(player_id, PlayerAction.CHECK)
result = game.player_action(player_id, PlayerAction.FOLD)
```

The `get_valid_actions` method returns a list of tuples with the valid actions the player can take:
- First element is the `PlayerAction` enum value (FOLD, CHECK, CALL, BET, RAISE)
- Second element is the minimum amount for the action (or None for FOLD/CHECK)
- Third element is the maximum amount for the action (or None for FOLD/CHECK, equal to min for CALL)

The `format_actions_for_display` method converts the valid actions into user-friendly strings that include:
- The action name (Fold, Check, Call, Raise to, etc.)
- The total amount to be bet (e.g., "$10")
- The additional amount needed in parentheses (e.g., "(+$5)")

The `player_action` method returns an `ActionResult` with these fields:
- `success`: Boolean indicating if the action was successful
- `error`: Error message if the action failed
- `state_changed`: Boolean indicating if the action completed a betting round

If `state_changed` is True and `auto_progress` is False, you should call `game._next_step()` to move to the next game step.

## Game Description and Information

```python
# Get a formatted description of the game
description = game.get_game_description()
# Example: "$10/$20 Limit Texas Hold'em"

# Get detailed table information
table_info = game.get_table_info()
# Returns a dictionary with:
# - game_description: Formatted game description
# - player_count: Number of players at the table
# - active_players: Number of players in the current hand
# - min_buyin: Minimum buy-in amount
# - max_buyin: Maximum buy-in amount
# - avg_stack: Average stack size
# - pot_size: Current pot size

# The game object can also be directly used in string context
print(f"Current game: {game}")  # Uses __str__ method
```

These methods are useful for displaying game information in UIs, lobbies, or logs. The formatting follows standard casino conventions for describing poker games.

## Game States

The game can be in one of these states, accessible via `game.state`:

- `GameState.WAITING`: Waiting for players to join
- `GameState.DEALING`: Cards being dealt
- `GameState.BETTING`: Betting round in progress
- `GameState.DRAWING`: Draw/discard in progress
- `GameState.SHOWDOWN`: Final showdown
- `GameState.COMPLETE`: Hand complete

## Manual Game Progression

If `auto_progress` is set to `False`, you need to manually control game progression:

```python
# Manual progression through game steps
game._next_step()

# Process current step
game.process_current_step()
```

## Current Player

The player who needs to act is available via `game.current_player`:

```python
current_player_id = game.current_player
```

## Game Step Management

The game progresses through steps defined in the rules:

```python
# Get current step index
current_step = game.current_step

# Get total number of steps
total_steps = len(game.rules.gameplay)
```

## Game Rules Configuration

The `GameRules` class represents a poker game variant's rules as defined in a JSON configuration file. The configuration schema allows defining many poker variants such as Texas Hold'em, Omaha, Seven-Card Stud, and more.

```python
from generic_poker.config.loader import GameRules
from pathlib import Path

# Load rules from file
rules_path = Path('data/game_configs/texas_holdem.json')
rules = GameRules.from_file(rules_path)

# Or parse from JSON string
rules = GameRules.from_json(rules_json)

# Access rules information
game_name = rules.game
min_players = rules.min_players
max_players = rules.max_players
betting_structures = rules.betting_structures
```

The game rules define:
- Minimum and maximum players
- Deck type and size
- Allowed betting structures
- Complete gameplay sequence
- Showdown rules and hand evaluation

Each step in the gameplay sequence is represented by a `GameStep` with:
- Name (e.g., "Deal Hole Cards", "Preflop Betting")
- Action type (BET, DEAL, DRAW, SHOWDOWN, etc.)
- Action configuration (cards to deal, betting rules, etc.)

The schema provides a flexible way to define complex game variants with features like:
- Different deck types (standard 52-card, short decks)
- Various dealing patterns (hole cards, community cards)
- Draw and discard mechanics
- Multiple betting structures
- Complex hand evaluation rules including high/low splits
- Wild cards and qualifiers

For full details on the configuration schema, see the schema documentation.

## Handling Showdowns

The game automatically handles showdowns when the final betting round is complete:

1. Evaluates all active players' hands
2. Awards pots to winners
3. Handles side pots in the correct order
4. Manages split pots when multiple players tie

## Key Design Features

1. **Rule-Driven Gameplay**: Uses a JSON configuration to define game rules, allowing different poker variants
2. **State Machine**: Manages game state transitions
3. **Component Architecture**: Separates concerns between Table, BettingManager, and Game
4. **Player Position Management**: Handles button, blinds, and action order
5. **Automatic Pot Management**: Correctly handles main pot, side pots, and splits
