# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

A generic poker engine with a configurable game rules system supporting 100+ poker variants through JSON configuration. The project has two main components:

1. **generic_poker** (`src/generic_poker/`) - Core poker engine: game logic, hand evaluation, betting management
2. **online_poker** (`src/online_poker/`) - Flask/SocketIO web platform for multiplayer online poker

**Current focus:** Get 2-player Texas Hold'em working end-to-end. See `docs/BACKLOG.md` for prioritized tasks.

## Quick Reference

### Essential Commands

```bash
# Environment
source env/bin/activate
pip install -e ".[test]"

# Run application
python app.py                    # Full web app at http://localhost:5000

# Testing
pytest                           # All tests
pytest tests/unit/               # Unit tests only
pytest tests/integration/        # Integration tests only
pytest path/to/test.py::TestClass::test_method  # Specific test
pytest -v -x --tb=short          # Verbose, stop on first failure

# Database
python tools/init_db.py          # Initialize schema
python tools/seed_db.py          # Seed test data
python tools/reset_db.py         # Full reset (init + seed)
```

### Test Credentials (after seeding)

| Username  | Password | Bankroll |
|-----------|----------|----------|
| testuser  | password | $800     |
| alice     | password | $1000    |
| bob       | password | $1500    |
| charlie   | password | $500     |
| diana     | password | $2000    |

## Architecture

### Core Engine (`src/generic_poker/`)

Uses a **rule-driven architecture** where poker variants are defined by JSON configs rather than code.

| Component | Location | Purpose |
|-----------|----------|---------|
| **Game** | `game/game.py` | Central controller: game flow, state transitions, player actions |
| **Table** | `game/table.py` | Players, seating, dealer/blind positions, card distribution |
| **BettingManager** | `game/betting.py` | Betting rounds, pot management (main/side), action validation |
| **GameRules** | `config/loader.py` | Parses JSON configs defining game variants |
| **HandEvaluator** | `evaluation/evaluator.py` | Hand evaluation via pre-computed rankings (O(1) lookups) |
| **Card/Deck** | `core/` | Card primitives (Card, Rank, Suit, Visibility) |

**Game Flow:**
1. Initialize with GameRules (from JSON) and betting structure
2. `start_hand()` resets state, processes first step (blinds/antes)
3. Progress through steps: DEAL → BET → DEAL → BET → ... → SHOWDOWN
4. `auto_progress=True` automatically advances when betting rounds complete
5. Showdown evaluates hands and awards pots

### Online Platform (`src/online_poker/`)

Flask/SocketIO multiplayer platform.

**Service Layer:**
| Service | Purpose |
|---------|---------|
| GameOrchestrator | Coordinates game lifecycle and service interactions |
| GameStateManager | Generates serialized game state views for clients |
| PlayerActionManager | Processes player actions, validates, advances game |
| WebSocketManager | Real-time SocketIO communication |
| DisconnectManager | Player disconnects/timeouts |
| TableManager / TableAccessManager | Table creation, joining, lifecycle |

**Routes:** `auth_routes.py`, `lobby_routes.py`, `table_routes.py`, `game_routes.py`

**Models:** `models/` - SQLAlchemy models (User, Table, GameSession, etc.)

### Web Interface (`static/`, `templates/`)

| File | Purpose |
|------|---------|
| `table.js` | Game UI: WebSocket events, card rendering, actions (2,462 lines - monolithic) |
| `table.css` | Table styling, seat layouts, cards |
| `lobby.js` | Lobby: browsing, filtering, creating tables |

## Game Configuration System

Poker variants are defined in `data/game_configs/*.json`. Example structure:

```json
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
    ...
  ],
  "showdown": {"order": "clockwise", "startingFrom": "dealer", "bestHand": [...]}
}
```

**Full schema documentation:** `data/schemas/README.md`

### Key Schema Elements

**Deck Types:** `standard` (52), `short_6a` (36), `short_ta` (20), `short_27_ja` (40)

**Forced Bet Styles:** `blinds`, `bring-in`, `antes_only`

**Betting Order:** `after_big_blind`, `bring_in`, `dealer`, `high_hand`

**GamePlay Actions:**
- `bet` - Betting rounds (blinds, antes, small, big, bring-in)
- `deal` - Deal cards (player or community, face up/down)
- `draw` - Draw replacement cards
- `discard` - Discard cards
- `expose` - Expose face-down cards
- `pass` - Pass cards to other players
- `declare` - Hi-lo declaration
- `showdown` - Final hand evaluation

### Evaluation Types

| Type | Description |
|------|-------------|
| `high` | Traditional high-hand poker |
| `a5_low` | A-5 lowball (ace low, straights/flushes don't count) |
| `27_low` | 2-7 lowball (ace high, straights/flushes count) |
| `badugi` | Badugi (4-card, different suits) |
| `high_wild` | High with wild cards (five of a kind possible) |
| `49`, `zero`, `6` | Pip-count games |
| `21` | Closest to 21 |

## Key Implementation Details

### Hand Evaluation
- Pre-computed rankings in `data/hand_rankings/*.csv.gz`
- Cached on first load for O(1) evaluation
- EvaluationType enum controls evaluation method
- Best 5-of-7: combinatorial search comparing all possibilities

### Betting Logic
- BettingManager tracks bets, pots, eligible players per round
- Side pots created automatically for all-in players
- Hand ends immediately when only one player remains
- **CRITICAL:** Don't call `_next_step()` after state is COMPLETE

### State Management
- Game states: WAITING, DEALING, BETTING, SHOWDOWN, COMPLETE
- GameStateManager generates player-specific views (hide others' hole cards)
- WebSocket pushes state updates to clients

### Player Actions
```python
# Get valid actions
actions = game.get_valid_actions(player_id)  # [(action, min_amount, max_amount), ...]

# Process action
result = game.player_action(player_id, action, amount)  # Returns ActionResult
```

## Testing Strategy

All game logic lives server-side. The UI is a rendering layer. This means the entire game can be driven and tested without a browser.

### Test Layers

```
Layer 1: Python Integration Tests (90% of testing)
  - Drive game engine directly: game.start_hand(), game.player_action()
  - No WebSocket, no browser. Fast (< 1 second per test)
  - tests/integration/test_gameplay_integration.py

Layer 2: Socket.IO Integration Tests (WebSocket validation)
  - flask_socketio.test_client (Python, no browser)
  - Tests WebSocket events produce correct state broadcasts
  - tests/integration/test_socketio_integration.py

Layer 3: E2E Browser Tests (visual verification only)
  - Playwright with multi-user fixtures
  - Slow (~10-30 seconds per test)
  - tests/e2e/specs/
```

### Bug Fix Workflow

1. Reproduce with a Python integration test (Layer 1)
2. Fix the server-side code
3. Verify the test passes
4. If UI rendering bug, also verify in browser
5. If WebSocket event bug, add Socket.IO test (Layer 2)

### Testing Notes

- Fixtures in `tests/test_helpers.py`
- **Integration tests do NOT require a running server** - use Flask test client
- Integration tests create own Flask app with in-memory SQLite

**Common issues:**
- Patch path must match actual import location (not class definition location)
- Static methods: use `ClassName._method()` not `self._method()`
- Mock session objects: explicitly set mock methods to avoid async warnings

### Socket.IO Testing Patterns

Flask-Login caches `current_user` in `flask.g._login_user`, which persists across SocketIO handlers
within a shared app context. Without patching, all handlers see the most recently connected user.

```python
# Required patch for multi-user SocketIO tests (already in test_socketio_integration.py)
def _patch_socketio_user_loading(socketio_instance):
    original = socketio_instance._handle_event
    def patched_handle_event(handler, message, namespace, sid, *args):
        def clearing_handler(*a, **kw):
            g.pop('_login_user', None)
            return original_handler(*a, **kw)
        original_handler = handler
        return original(clearing_handler, message, namespace, sid, *args)
    socketio_instance._handle_event = patched_handle_event
```

**Key test setup requirements:**
- Use `StaticPool` for in-memory SQLite so HTTP and SocketIO handlers share same DB
- Register `auth_bp` (with `/auth` prefix) and `lobby_bp` (contains `/api/tables/` join endpoints)
- `table_bp` is NOT needed for tests — join/seat endpoints are in `lobby_bp`
- The leave endpoint uses SocketIO event `leave_table`, not HTTP

### Core Engine Data Structures

These are commonly needed when working on GameStateManager or tests:

```python
# Community cards: dict with named keys, NOT a 'board' array
game.table.community_cards  # {'default': [Card, Card, ...]}
# GameStateManager._get_community_cards() returns {flop1: "Ts", flop2: "9s", ...}

# Player bets: NOT on Player object, tracked in BettingManager
game.betting.current_bets[player_id]  # PlayerBet(amount, has_acted, posted_blind, is_all_in)

# Player class has: id, name, stack, position, hand, is_active
# Player does NOT have: current_bet, has_folded

# Hand results from engine
game.get_hand_results()  # Returns GameResult with .pots, .hands, .winning_hands, .winners
```

## Database

SQLAlchemy with SQLite (dev) or PostgreSQL (prod). Models in `src/online_poker/models/`.

**Database location:** `instance/poker_platform.db` (Flask instance folder convention)

```bash
# Inspect database
sqlite3 instance/poker_platform.db
.tables
SELECT username, bankroll FROM users;
SELECT name, variant, betting_structure FROM poker_tables;
.quit
```

## API Route Structure

Auth blueprint registered with `/auth` prefix:
- HTML: `/auth/login`, `/auth/register`, `/auth/logout`
- API: `/auth/api/register`, `/auth/api/login`, `/auth/api/logout`, `/auth/me`, `/auth/check-auth`

## Important File Locations

| Type | Location |
|------|----------|
| Game configs | `data/game_configs/*.json` |
| Hand rankings | `data/hand_rankings/*.csv.gz` |
| Config schema docs | `data/schemas/README.md` |
| Main app | `app.py` |
| Core engine | `src/generic_poker/` |
| Web platform | `src/online_poker/` |
| Static assets | `static/js/`, `static/css/` |
| Templates | `templates/` |
| Database | `instance/poker_platform.db` |
| Logs | `poker_platform.log` |

## Project Status & Planning

| Document | Purpose |
|----------|---------|
| `docs/STATUS.md` | **Current project status**, open bugs, service quality, testing state |
| `docs/BACKLOG.md` | **Prioritized task backlog** organized in phases |
| `docs/GAME_VALIDATION.md` | **Game config feature matrix**, variant testing strategy, new game workflow |
| `DEVELOPMENT.md` | Development workflow, debugging tips |
| `data/schemas/README.md` | Complete JSON config schema documentation |
| `src/generic_poker/*-readme.md` | Component-specific API documentation |

> **Note:** `.kiro/specs/online-poker-platform/` contains historical planning docs from earlier development. The current source of truth for status and tasks is `docs/STATUS.md` and `docs/BACKLOG.md`.
