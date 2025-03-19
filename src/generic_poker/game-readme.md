# Game Class Documentation

## Overview

The `Game` class is the central controller for a poker game, managing game flow, state transitions, player actions, and interactions with the `Table` and `BettingManager`. It uses a `GameRules` object (parsed from JSON) to define the variant’s rules, supporting a wide range of poker games like Texas Hold’em, Seven-Card Stud, and beyond.

This class is designed for flexibility, handling blinds-based games (e.g., Hold’em), bring-in games (e.g., Stud), and future variants with draw or custom steps. It provides a robust API for starting hands, processing player actions, and retrieving game state or results.

## Key Attributes

- **`rules: GameRules`** - Defines the poker variant’s structure (steps, betting, showdown).
- **`table: Table`** - Manages players, cards, and positions.
- **`betting: BettingManager`** - Handles bets, pots, and round completion.
- **`state: GameState`** - Current state (e.g., `BETTING`, `DEALING`, `COMPLETE`).
- **`current_step: int`** - Index of the current step in `rules.gameplay`.
- **`current_player: Optional[Player]`** - Player to act next (or `None`).
- **`last_hand_result: Optional[GameResult]`** - Stores the last hand’s outcome.

## Creating a Game

```python
from generic_poker.config.loader import GameRules, BettingStructure
from generic_poker.game.game import Game
import json

# Define Texas Hold'em rules
holdem_rules = """
{
  "game": "Texas Hold'em",
  "players": {"min": 2, "max": 9},
  "deck": {"type": "standard", "cards": 52},
  "forcedBets": {"style": "blinds"},
  "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
  "gamePlay": [
    {"bet": {"type": "blinds"}, "name": "Post Blinds"},
    {"deal": {"location": "player", "cards": [{"number": 2, "state": "face down"}]}, "name": "Deal Hole Cards"},
    {"bet": {"type": "small"}, "name": "Pre-Flop Bet"},
    {"deal": {"location": "community", "cards": [{"number": 3, "state": "face up"}]}, "name": "Deal Flop"},
    {"bet": {"type": "small"}, "name": "Post-Flop Bet"},
    {"deal": {"location": "community", "cards": [{"number": 1, "state": "face up"}]}, "name": "Deal Turn"},
    {"bet": {"type": "big"}, "name": "Turn Bet"},
    {"deal": {"location": "community", "cards": [{"number": 1, "state": "face up"}]}, "name": "Deal River"},
    {"bet": {"type": "big"}, "name": "River Bet"},
    {"showdown": {"type": "final"}, "name": "Showdown"}
  ],
  "showdown": {"order": "clockwise", "startingFrom": "dealer", "bestHand": [{"evaluationType": "high", "anyCards": 5}]}
}
"""

# Create a Limit Hold'em game
game = Game(
    rules=GameRules.from_json(holdem_rules),
    structure=BettingStructure.LIMIT,
    small_bet=10,  # Small bet size
    big_bet=20,    # Big bet size
    min_buyin=200,
    max_buyin=1000,
    auto_progress=True  # Auto-advance steps after actions
)

# Define Seven-Card Stud rules
stud_rules = """
{
  "game": "Seven Card Stud",
  "players": {"min": 2, "max": 8},
  "deck": {"type": "standard", "cards": 52},
  "forcedBets": {"style": "bring-in", "rule": "low card"},
  "bettingStructures": ["Limit"],
  "gamePlay": [
    {"bet": {"type": "antes"}, "name": "Post Antes"},
    {"deal": {"location": "player", "cards": [{"number": 2, "state": "face down"}, {"number": 1, "state": "face up"}]}, "name": "Deal Third Street"},
    {"bet": {"type": "bring-in"}, "name": "Bring-In"},
    {"bet": {"type": "small"}, "name": "Third Street Bet"},
    {"deal": {"location": "player", "cards": [{"number": 1, "state": "face up"}]}, "name": "Deal Fourth Street"},
    {"bet": {"type": "small"}, "name": "Fourth Street Bet"},
    {"deal": {"location": "player", "cards": [{"number": 1, "state": "face up"}]}, "name": "Deal Fifth Street"},
    {"bet": {"type": "big"}, "name": "Fifth Street Bet"},
    {"deal": {"location": "player", "cards": [{"number": 1, "state": "face up"}]}, "name": "Deal Sixth Street"},
    {"bet": {"type": "big"}, "name": "Sixth Street Bet"},
    {"deal": {"location": "player", "cards": [{"number": 1, "state": "face down"}]}, "name": "Deal Seventh Street"},
    {"bet": {"type": "big"}, "name": "Seventh Street Bet"},
    {"showdown": {"type": "final"}, "name": "Showdown"}
  ],
  "showdown": {"order": "clockwise", "startingFrom": "dealer", "bestHand": [{"evaluationType": "high", "anyCards": 5}]}
}
"""

# Create a Limit Stud game
stud_game = Game(
    rules=GameRules.from_json(stud_rules),
    structure=BettingStructure.LIMIT,
    small_bet=10,
    big_bet=20,
    ante=1,
    bring_in=3,
    min_buyin=200,
    max_buyin=1000
)
```

- **`rules: GameRules`** - Defines the poker variant’s structure (steps, betting, showdown).
- **`table: Table`** - Manages players, cards, and positions.
- **`betting: BettingManager`** - Handles bets, pots, and round completion.
- **`state: GameState`** - Current state (e.g., `BETTING`, `DEALING`, `COMPLETE`).
- **`current_step: int`** - Index of the current step in `rules.gameplay`.
- **`current_player: Optional[Player]`** - Player to act next (or `None`).
- **`last_hand_result: Optional[GameResult]`** - Stores the last hand’s outcome.

- **Betting Structure**: Use `LIMIT`, `NO_LIMIT`, or `POT_LIMIT` as allowed by `rules.bettingStructures`.
- **Forced Bets**: For blinds games, set `small_blind`/`big_blind`; for Stud, set `ante`/`bring_in`.
- **Auto-Progress**: If ``True``, steps advance automatically after actions complete a round.

## Managing Players

```python
# Add players
game.add_player("p1", "Alice", 500)
game.add_player("p2", "Bob", 500)
game.add_player("p3", "Charlie", 500)

# Remove a player
game.remove_player("p3")
```

- Players are added to `self.table` with a unique ID, name, and buy-in (within `min_buyin`/`max_buyin`).
- If player count drops below `rules.min_players`, `state` reverts to `WAITING`.

## Starting a Hand

```python
# Start a new hand
game.start_hand()  # Raises ValueError if too few players
```

- Resets `table` and `betting`, sets `current_step = 0`, and processes the first step (e.g., posting blinds or antes).
- With `auto_progress=True`, advances to the next step (e.g., dealing cards).

## Player Actions

```python
# Get valid actions for current player
player_id = game.current_player.id
actions = game.get_valid_actions(player_id)
# Example: [(PlayerAction.FOLD, None, None), (PlayerAction.CALL, 10, 10), (PlayerAction.RAISE, 20, 20)]

# Format for display
display_actions = game.format_actions_for_display(player_id)
# Example: ["Fold", "Call $10 (+$5)", "Raise to $20 (+$15)"]

# Perform an action
result = game.player_action(player_id, PlayerAction.CALL, 10)
# Returns ActionResult(success=True, state_changed=False)
```
* `get_valid_actions`: Returns a list of `(action, min_amount, max_amount)` tuples:
- `FOLD`/`CHECK`: `(action, None, None)`
- `CALL`: `(CALL, total_amount, total_amount)`
- `BET`/`RAISE`: `(action, min_amount, max_amount)` (equal in Limit games)
- `BRING_IN`: `(BRING_IN, bring_in_amount, bring_in_amount)`
* `format_actions_for_display`: Converts actions to readable strings, showing total and additional chip amounts.
* `player_action`: Processes the action, updating `betting` and `table`. Returns `ActionResult`:
- `success`: True if valid.
- `error`: Error message if failed (e.g., "Not your turn").
- `state_changed`: True if the round ends (triggers `_next_step` if `auto_progress=True`).

## Game Information

```python
# Get a formatted description of the game
description = game.get_game_description()
# Example: "$10/$20 Limit Texas Hold'em"

# Get detailed table information
info = game.get_table_info()
# Returns a dictionary with:
# - game_description: Formatted game description
# - player_count: Number of players at the table
# - active_players: Number of players in the current hand
# - min_buyin: Minimum buy-in amount
# - max_buyin: Maximum buy-in amount
# - avg_stack: Average stack size
# - pot_size: Current pot size

# String representation
print(game)  # Uses get_game_description()
```

* Useful for UI display or logging; follows casino-style naming (e.g., "$1/$2 No-Limit Hold’em").

## Game States

The game can be in one of these states, accessible via `game.state`:

- `GameState.WAITING`: Waiting for players to join
- `GameState.DEALING`: Cards being dealt
- `GameState.BETTING`: Betting round in progress
- `GameState.DRAWING`: Draw/discard in progress
- `GameState.SHOWDOWN`: Evaluating hands (transient, moves to `COMPLETE`).
- `GameState.COMPLETE`: Hand complete

## Manual Progression

For `auto_progress=False`:

```python
game.start_hand()  # Stops at first betting step
game.player_action("p1", PlayerAction.CALL, 10)
if result.state_changed:
    game._next_step()  # Advance manually
game.process_current_step()  # Process current step explicitly
```

## Showdown and Results

```python
# After hand completes
results = game.get_hand_results()
# GameResult(pots=[PotResult(amount=60, winners=['SB'], ...)], hands={'SB': [HandResult(...)]}, ...)

print(results)
# Showdown Results:
# Game Result (Complete: True)
# Total pot: $60
# Pot Results:
# Unspecified Pot Division:
# - Main pot: $60 - Won by SB
# Hand:
#     Winning Hands:
#         - Player SB: Four of a Kind, Four Queens (...)
#     Losing Hands:
#         - Player BTN: Two Pair, Kings and Queens (...)
#         - Player BB: Full House, Queens Full of Jacks (...)
```

* Automatically evaluates hands, awards pots (main and side), and handles splits based on `rules.showdown`.
* `GameResult` provides detailed pot and hand outcomes.

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
