# Game Configuration Validation & New Variant Workflow

> How to validate that game configs work, assess whether a new game can be implemented,
> and implement new variants.
> Last updated: 2026-02-23

---

## Feature Implementation Matrix

The game engine supports 12+ gameplay action types defined in the JSON schema. Here's what's implemented, tested, and used:

| Feature | Implemented | Test Coverage | Games Using | Notes |
|---------|:-----------:|:-------------:|:-----------:|-------|
| **bet** | YES | Extensive | 246 (100%) | All forced bet styles: blinds, bring-in, antes_only (all 3 verified with tests) |
| **deal** | YES | Extensive | 246 (100%) | Player + community, face up/down, subsets |
| **draw** | YES | High (41 tests) | 41 (21%) | Discard/draw, preserve state, min/max constraints |
| **discard** | YES | High | 44 (21%) | Implicit in draw tests |
| **expose** | YES | Good (11 tests) | 11 (5%) | 7_card_flip, showmaha, studaha, grodnikonda, anaconda, etc. |
| **pass** | YES | Minimal (2 tests) | 2 (1%) | pass_the_pineapple, anaconda |
| **separate** | ~95% | Good (11 tests) | 11 (6%) | sohe, cowpie, sheshe, etc. `hand_comparison` unimplemented |
| **declare** | YES | Good (9 tests) | 9 (4%) | Hi-lo declaration games |
| **replace_community** | YES | Minimal (1 test) | 1 (0.5%) | one_mans_trash only |
| **remove** | Partial | Good (6 tests) | 3 (2%) | Only `lowest_river_card_unless_all_same` criteria |
| **roll_die** | YES | Good (7 tests) | 1 (0.5%) | binglaha only |
| **choose** | YES | Minimal | 2 (1%) | paradise_road_pickem, related variants |
| **showdown** | YES | Extensive | 246 (100%) | All 21+ evaluation types, qualifiers, conditionals |

### Showdown Features

| Feature | Implemented | Games Using |
|---------|:-----------:|:-----------:|
| bestHand (standard) | YES | 240 |
| conditionalBestHands | YES | 6 |
| declaration_mode | YES | 11 |
| classification_priority (face/butt) | YES | 2 |
| defaultActions (no qualifier) | YES | ~30 |
| globalDefaultAction | YES | ~5 |

### Wild Card Support

| Wild Type | Implemented | Notes |
|-----------|:-----------:|-------|
| joker | YES | Standard joker wild |
| rank (e.g., deuces wild) | YES | Named wild cards |
| bug (limited wild) | YES | Ace or straight/flush fill |
| lowest_community | YES | Dynamic wild based on board |
| lowest_hole | YES | Dynamic wild based on player cards |
| last_community_card | YES | Dynamic wild from last dealt card |
| Player-scoped wilds | NO | Schema allows but not implemented (0 games use) |

### Conditional Deal State

| Condition Type | Implemented | Notes |
|----------------|:-----------:|-------|
| board_composition | YES | Color, suit, rank checks on community cards |
| player_choice | YES | Based on game_choices from choose action |
| all_exposed | NO | Placeholder returns True (0 games use) |
| any_exposed | NO | Placeholder returns True (0 games use) |
| none_exposed | NO | Placeholder returns True (0 games use) |

### Known Unimplemented Features

These are defined in the JSON schema (`data/schemas/game.json`) but not implemented in the engine:

1. **`separate.hand_comparison`** - Compare separated hands for ordering. No games use this.
2. **`all_exposed` / `any_exposed` / `none_exposed` conditions** - `game.py:531` has placeholder returning True. No games use these.
3. **Protection options** - Schema allows per-card protection during draw. Structure recognized but not enforced.
4. **Player-scoped wild cards** - `scope: "player"` in schema but evaluator doesn't apply per-player.

---

## Test Coverage

### Current State

| Layer | What | Count | Coverage |
|-------|------|:-----:|----------|
| Schema validation | All configs load and pass JSON schema | 246/246 | `tests/integration/test_game_config.py` |
| Game-specific tests | Predetermined deck, step-by-step assertions | 68/246 | `tests/game/test_*.py` |
| **Gap** | **Configs with no end-to-end test** | **~178** | **No test plays a hand** |

### What `test_game_config.py` Validates

For all 246 configs:
- JSON schema compliance
- GameRules parsing succeeds
- Betting sequence is valid (forced bets come before voluntary bets)
- Card requirements match (showdown needs <= cards dealt)

What it does NOT validate:
- A hand can actually be played to completion
- All game steps execute without errors
- Showdown produces correct results

### What Game-Specific Tests Validate

Each `tests/game/test_*.py` file:
1. Loads the variant config from `data/game_configs/`
2. Creates a `MockDeck` with predetermined cards
3. Sets up 3 players with `auto_progress=False`
4. Calls `game.start_hand()` and manually advances with `game._next_step()`
5. At each betting round, exercises player actions (fold, call, raise, etc.)
6. Verifies showdown results (winners, hand descriptions, pot distribution)

### Proposed: Smoke Test for All Variants

A parametrized test that plays a minimal hand for every config:

```python
@pytest.mark.parametrize("config_file", get_all_config_files())
def test_variant_plays_to_completion(config_file):
    """Verify that a hand can be played to completion for every variant."""
    rules = GameRules.from_file(config_file)
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10, big_bet=20,
        ante=1, bring_in=3,
        min_buyin=100, max_buyin=1000,
        auto_progress=False
    )

    # Add enough players
    for i in range(rules.players.min):
        game.add_player(f"player_{i}", 500)

    game.start_hand()

    max_steps = 100  # Safety limit
    steps = 0
    while game.state != GameState.COMPLETE and steps < max_steps:
        if game.state == GameState.BETTING:
            # Everyone checks/calls through
            while game.current_player:
                actions = game.get_valid_actions(game.current_player)
                # Pick check if available, else call, else fold
                action = pick_simplest_action(actions)
                game.player_action(game.current_player, action[0], action[1])
        elif game.state in (GameState.DEALING, GameState.SHOWDOWN):
            game._next_step()
        # Handle draw/discard/expose/pass/declare/separate
        elif game.state == GameState.PLAYER_ACTION:
            handle_player_action_round(game)
        steps += 1

    assert game.state == GameState.COMPLETE, f"{config_file.stem}: stuck at {game.state} after {steps} steps"
```

This would catch:
- Configs that crash during gameplay
- Infinite loops in game progression
- Missing feature implementations
- Showdown failures

---

## Workflow: Can This Game Be Implemented?

Given a poker game description (e.g., from pagat.com), determine if it can be implemented with just a JSON config or needs engine code changes.

### Step 1: Identify Required Features

Map the game rules to config features:

| Game Mechanic | Config Feature | Implemented? |
|---------------|----------------|:------------:|
| Players are dealt cards | `deal` (location: player) | YES |
| Community cards | `deal` (location: community) | YES |
| Betting rounds | `bet` (type: small/big/blinds/bring-in) | YES |
| Draw/replace cards | `draw` + `discard` | YES |
| Expose cards | `expose` | YES |
| Pass cards to neighbors | `pass` (direction: left/right/across) | YES |
| Split hand into parts | `separate` | ~95% |
| Hi-lo declaration | `declare` | YES |
| Replace community card | `replace_community` | YES |
| Remove board based on criteria | `remove` | Partial |
| Roll die for game mode | `roll_die` | YES |
| Player chooses variant | `choose` | YES |
| Conditional card dealing | `conditional_state` | ~80% |
| Wild cards | `wildCards` section | ~90% |
| Multiple evaluation types | `bestHand` array | YES |
| Conditional hand evaluation | `conditionalBestHands` | YES |

### Step 2: Check Evaluation Types

Does the game need an evaluation type that exists?

Available types: `high`, `a5_low`, `27_low`, `badugi`, `badugi_ah`, `higudi`, `high_wild`, `49`, `zero`, `6`, `low_pip_6`, `21`, `a5_low_high`, `one_card_high_spade`, `two_card_high`, `ne_seven_card_high`, `36card_ffh_high`, `20card_high`, `27_ja_ffh_high_wild_bug`

If the game needs a new evaluation type, that requires code changes in:
- `src/generic_poker/evaluation/evaluator.py`
- Potentially new hand ranking data in `data/hand_rankings/`

### Step 3: Check Deck Type

Available deck types: `standard` (52), `short_6a` (36), `short_ta` (20), `short_27_ja` (40), plus optional jokers.

If the game needs a different deck, that requires code changes in:
- `src/generic_poker/core/deck.py`

### Step 4: Decision Tree

```
Can all game mechanics be expressed with existing config features?
├── YES → JSON-only implementation
│   ├── Create config in data/game_configs/
│   ├── Add test in tests/game/
│   └── Done
└── NO → Identify what's missing
    ├── New gameplay action type → game.py + player_action_handler.py
    ├── New evaluation type → evaluator.py + hand rankings
    ├── New deck type → deck.py
    ├── New conditional type → game.py conditional handling
    └── New wild card behavior → evaluator.py wild card logic
```

---

## Workflow: Implementing a New Game Variant

### JSON-Only (No Code Changes)

1. **Write the config file** in `data/game_configs/new_game.json`
   - Use an existing similar game as a template
   - Reference the schema docs: `data/schemas/README.md`

2. **Validate the config**
   ```bash
   pytest tests/integration/test_game_config.py -v -k "test_all_game_configs"
   ```

3. **Write a game test** in `tests/game/test_new_game.py`
   - Follow the MockDeck pattern from existing tests
   - Test at least: deal, one betting round, showdown
   - Verify correct winners and pot distribution

4. **Run the test**
   ```bash
   pytest tests/game/test_new_game.py -v
   ```

### Requires Code Changes

1. **Identify the gap** (new action type, evaluation type, etc.)
2. **Write a failing test first** that exercises the new feature
3. **Implement the feature** in the appropriate engine file
4. **Write the game config** using the new feature
5. **Write unit tests** for the new engine code
6. **Write the game test** for the variant
7. **Run the full test suite** to verify no regressions
   ```bash
   pytest
   ```

### Test Pattern Template

```python
"""Tests for [game name] end-to-end."""
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck
from tests.test_helpers import load_rules_from_file
from typing import List

class MockDeck(Deck):
    def __init__(self, cards: List[Card]):
        super().__init__(include_jokers=False)
        self.cards.clear()
        for card in reversed(cards):
            self.cards.append(card)

def create_predetermined_deck():
    cards = [
        # Card order: dealt first to last
        # Player 1 hole cards, Player 2 hole cards, Player 3 hole cards
        # Then community cards or subsequent streets
        Card(Rank.ACE, Suit.HEARTS),    # P1 card 1
        Card(Rank.KING, Suit.DIAMONDS), # P2 card 1
        # ... continue for all cards needed
    ]
    return MockDeck(cards)

def setup_test_game():
    rules = load_rules_from_file('new_game')  # matches data/game_configs/new_game.json
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10, big_bet=20,
        ante=1, bring_in=3,
        min_buyin=100, max_buyin=1000,
        auto_progress=False
    )
    game.add_player("alice", 500)
    game.add_player("bob", 500)
    game.add_player("charlie", 500)
    game.table.deck = create_predetermined_deck()
    return game

def test_new_game_basic_flow():
    game = setup_test_game()
    game.start_hand()
    # Step through the game, asserting at each point
    # ...
    assert game.state == GameState.COMPLETE
```

---

## Games Without Dedicated Tests

68 of 246 configs have tests in `tests/game/`. The remaining ~178 pass schema validation
but have no end-to-end test. Priority for adding tests:

### High Priority (use uncommon features)
- ~~Games using `remove` action (3 games)~~ — DONE: `test_oklahoma.py` (6 tests)
- ~~Games using `roll_die` (1 game - binglaha)~~ — DONE: `test_binglaha.py` (7 tests)
- Games using `choose` (2 games - paradise_road_pickem has one)
- Games using `conditional_state` without existing tests
- Games using `conditional_best_hands` without existing tests

### Medium Priority (variations of tested features)
- Hold'em variants without tests
- Stud variants without tests
- Draw variants without tests

### Low Priority (simple variations of well-tested games)
- Games that only differ in betting structure from tested games
- Games that only differ in number of cards dealt
