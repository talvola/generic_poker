# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

A generic poker engine with a configurable game rules system supporting 100+ poker variants through JSON configuration. The project has two main components:

1. **generic_poker** (`src/generic_poker/`) - Core poker engine: game logic, hand evaluation, betting management
2. **online_poker** (`src/online_poker/`) - Flask/SocketIO web platform for multiplayer online poker

## Quick Reference

### Essential Commands

```bash
# Environment
source env/bin/activate
pip install -e ".[test]"

# Run application
python app.py                    # Full web app at http://localhost:5000
python run_server.py             # Demo server (lobby only)

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
| GameManager | Manages active game instances per table |
| PlayerSessionManager | Tracks player connections and sessions |
| WebSocketManager | Real-time SocketIO communication |
| DisconnectManager | Player disconnects/timeouts |
| TableManager | Table creation and lifecycle |

**Routes:** `auth_routes.py`, `lobby_routes.py`, `table_routes.py`, `game_routes.py`

**Models:** `models/` - SQLAlchemy models (User, Table, GameSession, etc.)

### Web Interface (`static/`, `templates/`)

| File | Purpose |
|------|---------|
| `table.js` | Game UI: WebSocket events, card rendering, actions |
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

## Known Bugs

See `.kiro/specs/online-poker-platform/bugs.md` for full tracking.

| Bug | Priority | Description |
|-----|----------|-------------|
| #001 | High | SimpleBot folds when check is available |
| #002 | Medium | Action panel width changes cause layout shift |
| #006 | High | Player's own cards intermittently disappear |

## Testing Notes

- Fixtures in `tests/test_helpers.py`
- **Integration tests do NOT require a running server** - use Flask test client
- Integration tests create own Flask app with in-memory SQLite

**Common issues:**
- Patch path must match actual import location (not class definition location)
- Static methods: use `ClassName._method()` not `self._method()`
- Mock session objects: explicitly set mock methods to avoid async warnings

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

## Development Workflow

### Test-Driven (Recommended)

```bash
# Run tests during development
pytest tests/unit/test_file.py -v -x  # Stop on first failure

# Full suite before committing
pytest
```

### Manual Testing

```bash
# Terminal 1: Server
python app.py

# Terminal 2: Watch logs
tail -f poker_platform.log

# Browser: Multiple tabs/incognito for multiplayer testing
```

### Debugging

```bash
# Enable debug logging in code
logging.basicConfig(level=logging.DEBUG)

# Search logs
grep -i "error\|exception" poker_platform.log | tail -30

# With context
grep -A 5 -B 5 "KeyError" poker_platform.log
```

## Common Tasks

### Adding a New Poker Variant

1. Create JSON config in `data/game_configs/`
2. Define gamePlay steps (bet/deal sequence)
3. Specify showdown rules and evaluation type
4. Test with unit tests

### Debugging Game Flow

1. Check `poker_platform.log`
2. Use browser DevTools for WebSocket messages (Network tab → WS filter)
3. Game state logged at each step transition

## Project Status

**Implemented:**
- Core poker engine with 100+ variants
- User authentication and session management
- Table creation, joining, lobby
- Real-time WebSocket gameplay
- Basic betting actions (fold, check, call, bet, raise)
- Showdown and pot distribution
- Chat system

**In Progress:**
- Advanced actions (draw, expose, pass cards)
- Bot player improvements
- Hand history export
- Admin interface

**Full task list:** `.kiro/specs/online-poker-platform/tasks.md`

## Additional Documentation

| Document | Purpose |
|----------|---------|
| `DEVELOPMENT.md` | Detailed development workflow, debugging tips |
| `data/schemas/README.md` | Complete JSON config schema documentation |
| `.kiro/specs/online-poker-platform/requirements.md` | Full requirements specification |
| `.kiro/specs/online-poker-platform/design.md` | Architecture design document |
| `.kiro/specs/online-poker-platform/bugs.md` | Bug tracking |
| `src/generic_poker/*-readme.md` | Component-specific API documentation |
