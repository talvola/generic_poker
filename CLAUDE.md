# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

A generic poker engine with a configurable game rules system supporting 100+ poker variants through JSON configuration. The project has two main components:

1. **generic_poker** (`src/generic_poker/`) - Core poker engine: game logic, hand evaluation, betting management
2. **online_poker** (`src/online_poker/`) - Flask/SocketIO web platform for multiplayer online poker

**Current focus:** opening the site to more players. **Work is tracked in GitHub Issues**
(`gh issue list`), not in the repo docs — file findings there and reference them in commits
("Fixes #N"). `docs/BACKLOG.md` / `docs/STATUS.md` are historical context.

## Quick Reference

### Essential Commands

```bash
# Environment
source env/bin/activate
pip install -e ".[test]"
pip install -e ".[dev]"           # Includes ruff, bandit, pre-commit

# Run application
python app.py                    # Full web app at http://localhost:5000

# Testing
pytest                           # All tests
pytest tests/unit/               # Unit tests only
pytest tests/integration/        # Integration tests only
pytest path/to/test.py::TestClass::test_method  # Specific test
pytest -v -x --tb=short          # Verbose, stop on first failure
npx playwright test --config tests/e2e/playwright.config.ts  # E2E (reset DB first: echo "yes" | python tools/reset_db.py; start `python app.py` yourself — the config's webServer command fails under sh)

# Bot arena — offline A/B of bot types; chip-conservation checks here found 3 engine bugs
python tools/bot_arena.py --variant omaha_8 --structure Limit --hands 200 --seed 42

# Code Quality
ruff check src/                  # Lint (errors block commits via pre-commit)
ruff check src/ --fix            # Auto-fix lint issues
ruff format src/                 # Format code (runs on commit via pre-commit)
pre-commit run --all-files       # Run all pre-commit hooks manually
pip-audit                        # Check dependencies for vulnerabilities

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
| MonteCarloBot | Default bot (`BOT_TYPE=mc`): MC equity for betting, SimpleBot fallback for draws/exotics |
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

**Frontend invariants (table.js):** Seats/panels are rebuilt via innerHTML on EVERY state
broadcast (~constantly on bot tables). Never bind listeners to card/seat elements — use
delegated listeners on `document`. Never store selection state only in DOM classes — keep
it on the PokerTable instance and re-apply after renders. Never replace `#action-panel`
innerHTML — the showdown strip renders into the sibling `#showdown-panel`.
Player objects carry `user_id` (the engine player id), NOT `id` — `player.id` is `undefined`.
Use `player.user_id` for seat ids/comparisons and `player.is_current_player` for the turn
highlight (both server-computed). Because seats re-render constantly, probing a seat's
computed style after a manual `classList`/`style` change is unreliable — verify CSS on a
fresh isolated element instead.
Note: many tracked files are CRLF — JS/CSS, `CLAUDE.md`, `src/online_poker/config.py`. A
Python-scripted rewrite normalizes them to LF and buries a 30-line edit in a 1300-line diff.
Check `file <path>` first; if you slip, re-run a `\n`→`\r\n` pass before committing.

**Lobby invariants (lobby.js/lobby.css):** The lobby is served at `/` (`/lobby` 404s) and
exposes `window.lobby` (the table page exposes `window.pokerTable`). Variants + mixed games
come from `GET /table/variants` — each entry has `display_name`/`category`, and mixes carry
`is_mixed`/`rotation`/`rotation_letters`. `lobby.css` does NOT load `table.css`, so mirror any
shared styles; lobby modals render on a WHITE background (felt-oriented light-on-translucent
styles won't translate). Owner-only UI (e.g. the Edit button) is gated on
`table.creator_id === window.currentUserId` (the id is exposed in lobby.html). Inject server
values into inline `<script>` with Jinja `| tojson`, never `'"' + x + '"' | safe`.

**Responsive layout invariants (table.css/table.js):** Seat-position CSS exists only for
`data-max-players` 2/6/9 (bucketed in table.html). The hero's own seat gets `.hero-seat`
(own cards render larger); its selectors outrank media-query card rules, so each breakpoint
needs its own hero overrides. Bottom-row seats (2-max pos 1, 6-max pos 2-3, 9-max pos 3-5)
are `column-reverse` — cards above the info panel, on the felt. The dealer button is
positioned by JS inline styles (`updateDealerButton()`, anchored to `.player-info`); the
`.dealer-button[data-position]` CSS rules are dead code. Tablet-portrait breakpoint is
431-1100px — 13" iPads are 1024-1032px wide in portrait, so don't cap tablet queries at
1024px. Rotate prompt is phone-only (≤430px).

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

### Mixed Games (HORSE, 8/10-Game, HOSE, SHOE)

A new mix = one `data/mixed_game_configs/<name>.json` referencing existing variant config stems
(plus per-variant `bettingStructure`/`letter`). `TableManager.get_available_mixed_games()`
dir-globs the folder, so a new mix appears in the lobby with no code change or restart. The
rotation engine (orbit swap, stack/seat/button preservation, NL/PL-from-Limit derivation) lives
in `GameSession` and is complete.

**Custom mixes (9.3) + Dealer's Choice (9.4):** user-authored mixes are stored inline as
`MixedGameConfig` JSON on `PokerTable.custom_mix_config` (no file). `TableManager.get_table_mixed_config(table)`
resolves inline JSON, else the file. Dealer's Choice = the same menu + a `dealersChoice` flag
(button player picks each orbit; bot dealers auto-pick) — reuses `custom_mix_config`, no new column.
⚠️ The FIRST orbit of any mix must be built with `create_game_instance_for_variant(first_leg)`,
NOT the table's base structure — else an NL/PL-first leg wrongly plays as Limit (file mixes mask
this since their first leg is always Limit). Only 9.5 (custom variant authoring) remains.

**Custom variants (9.5):** per-user `CustomVariant` library; table creation copies the config
inline onto `PokerTable.custom_variant_config` with `variant="custom_variant"` sentinel (never a
file path — safe to shadow official stems). Resolve rules via
`TableManager.get_table_variant_rules(table)` (NOT `get_variant_rules(table.variant)`) anywhere
a table's variant becomes GameRules. Validation pipeline in `services/variant_authoring.py`
ends with seeded smoke-play (bot hands per structure) — it caught a real PL engine bug on day
one; keep it on for saves. UI surfaces show `variant_display` (server-computed), never the raw
sentinel.

### Key Schema Elements

**Deck Types:** `standard` (52), `short_6a` (36), `short_ta` (20), `short_27_ja` (40)

**Forced Bet Styles:** `blinds`, `bring-in`, `antes_only`, `bomb` (bomb pot: everyone antes, no
preflop bet, deal straight to flop — same ante collection as `antes_only` but betting order
defaults to `dealer`/`dealer` instead of stud `high_hand`; "no preflop bet" is config-only —
the gameplay array just omits the preflop bet step)

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

### Import Paths (CRITICAL)
- Inside `src/online_poker/`, ALWAYS use relative imports (`from ..database import db`)
- NEVER `from online_poker.X import ...` — both `online_poker.*` and `src.online_poker.*`
  are importable, so absolute imports load a SECOND module copy with its own SQLAlchemy
  `db` not bound to Flask → DB writes fail silently ("Flask app is not registered with
  this SQLAlchemy instance"). This caused lost cashouts and an empty transactions table.

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
- **CRITICAL:** Online games run `auto_progress=False`, so showdown completion happens in
  `_next_step()` AFTER `process_player_action` returns. Any "hand finished" side effect
  (counters, DB sync, cleanup) must live in `PlayerActionManager._handle_hand_completion()`
  — the single point hit by all completion paths (fold-win, human action, bot action).
- websocket_manager `_start_hand_when_ready` / `_begin_hand` use FUNCTION-LOCAL imports
  (`TableAccessManager`, `Position`, `BotActionService`) — extracted helpers need their own.
- Valid-action tuple amounts are TOTALS (player's total bet after the action), not deltas.
  Incremental call cost = `game.betting.get_additional_required(player_id)`.
- No server-side auto-action by default: both the action timeout AND disconnect auto-fold
  are gated by `ACTION_TIMEOUT_ENABLED` (false unless set). Don't hunt a phantom auto-check.
- Both human and bot actions flow through `GameSession.process_player_action` — the single
  choke point for per-action hooks (e.g. seat action badges via `player_last_actions`).

### Betting Caps (6.2.13) — two distinct, structure-aware table settings
- **Limit raise cap** (per street): `betting.max_raises` (bet + N; default 3, or 4 for
  two-round draw/lowball), `betting.raise_cap_enabled` (False = unlimited), unlimited heads-up.
  Per-table override via Game `max_raises_override` / `unlimited_raises`.
- **Per-hand money cap** (NL/PL "cap game"): Game `hand_cap` (chips). `betting.effective_stack(
  pid, real_stack) = min(real_stack, hand_cap − hand_contributed[pid])` is the single clamp —
  threaded through `get_max_bet`/`validate_bet`/`place_bet` all-in + the direct `player.stack`
  reads in `player_action_handler`. A capped-out player (chips left, cap hit) is all-in via
  `betting.can_act()` (used by `round_complete`/`_live_player_count`/`skip_betting_players_
  unable_to_act`). **`effective_stack` returns the real stack when `hand_cap=0`, so non-cap
  play is unchanged** — keep it that way when touching betting.
- Table surface: `PokerTable.raise_cap_override` / `hand_cap_bb` (BB→chips in
  `create_game_instance`). New columns → `reset_db.py` locally; fresh deploys get them.
- ⚠️ Chip-conservation footgun (cost me an hour): calling `game._next_step()` after the hand
  is already `COMPLETE` double-awards the pot. Any passive/sim loop MUST guard
  `if res.advance_step and game.state != COMPLETE`. This is NOT an engine bug.

### Debug Deck (T009) — reproduce deal scenarios on demand
- Engine: `Deck(rng=...)` for reproducible shuffles; `Deck.set_stack(cards)` (engine-reusable
  MockDeck pattern); `Table.set_stacked_deck(cards, repeat=)`, `set_deck_seed(seed)`,
  `clear_stacked_deck()`. A stacked deck survives `clear_hands()` (deck rebuilt via
  `Table._build_deck()`) and `start_hand(shuffle_deck=True)` skips shuffle when
  `table.deck_is_stacked`. One-shot stack consumed after one hand; `repeat=True` persists.
- Online: admin-gated `/api/debug/tables/<id>/stacked-deck|seed|deck-status` (`debug_routes.py`),
  gated by `DEBUG_ALLOW_STACKED_DECK` (on in dev/testing, **off in production → 404**). Needs an
  admin user (`tools/make_admin.py`). Workflow: open table (session created) → POST cards → Ready.

### Stud Street Chat Announcements (8.4)
- `services/stud_announcer.py::build_street_announcement(game)` is a pure fn over the engine
  Game (unit-testable, no WS). `WebSocketManager.broadcast_game_state_update` (the single
  broadcast choke point) calls `_maybe_announce_stud_street`, announce-once keyed on
  `(hands_played, current_step)`. Street label derived from the betting round's index in
  gameplay (stud configs name betting steps inconsistently, so don't parse step names).

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

E2E flake pattern: a single test (Badugi multi-draw, SOHE separate) can fail in the full
run but pass in isolation — re-run with `-g "<test name>"` before investigating.
Integration-test isolation: running multiple Flask integration test *files* together can
fail (each `db.init_app`s its own app) while each passes alone — re-run the file in
isolation to confirm it's fixture interference, not your code.
Debugging live/deployed UI: drive it with Playwright — log in via page-context `fetch`
(`/auth/api/login`, keeps cookies), create+join a table via the API, navigate to
`/table/<id>`, click `#ready-btn`, then sample `window.pokerTable.store` / the DOM. The only
way to reproduce bugs that need real bot play.
- Playwright synthetic events need `{bubbles:true}` (`new Event('change',{bubbles:true})`) for
  DELEGATED listeners — a bare `new Event('change')` doesn't bubble, so the handler never fires.
- Start the dev app with Bash `run_in_background:true`, NOT `(python app.py &)` — a backgrounded
  subshell inside a tool call gets killed when the call returns (exit 144).
- `store` keys: `gameState, currentUser, players, isMyTurn, validActions, potAmount,
  handNumber, tableId`. `store.players` is an OBJECT keyed by id (`.find` throws — use
  `Object.values`), and entries use `username`/`chip_stack`, not `name`/`stack`.
- Action buttons have NO ids — `#action-panel button.fold|.call|.raise` (`#ready-btn` does).
- `POST /api/tables` returns `table_id` at the TOP level, not `table.id`.

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

**Manual UI verification with bots (no E2E needed):** log in via browser, then
`POST /api/tables` (create) and `POST /api/tables/<id>/join` with
`{buy_in_amount, seat_number}`, navigate to `/table/<id>`, click `#ready-btn` —
bots fill and play automatically. Note: `/api/tables` works; `/api/tables/`
(trailing slash) 404s. Resize viewport to device sizes (iPad 11" 834×1194,
13" 1032×1376) for layout checks.
- `POST /api/tables` body quirks: `betting_structure` must be LOWERCASE
  (`limit`/`no-limit`/`pot-limit`) — capitalized falls through to the blinds
  branch and 400s. Stakes keys are structure-specific: Limit `{small_bet,
  big_bet, ante}`, blinds games `{small_blind, big_blind}`. Cap fields:
  `raise_cap_override` (Limit), `hand_cap_bb` (NL/PL). For a mixed game pass the
  mix name as `variant`; the rotation config drives per-hand structure.

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

# Player at a seat: game.table.get_player_in_seat(seat_num). button_seat is an int.
# The engine Table (table.py:141) has NO .seats dict — `table.seats` belongs to the
# unrelated TableLayout class in the same file (a footgun; cost an hour in 9.4).

# Hand results from engine
game.get_hand_results()  # Returns GameResult with .pots, .hands, .winning_hands, .winners
```

## Database

SQLAlchemy with SQLite (dev) or PostgreSQL (prod). Models in `src/online_poker/models/`.

**Database location:** `instance/poker_platform.db` (Flask instance folder convention)

```bash
# Inspect local dev database
sqlite3 instance/poker_platform.db
.tables
SELECT username, bankroll FROM users;
SELECT name, variant, betting_structure FROM poker_tables;
.quit
```

### Running Database Operations on Production (Neon)

Production Postgres is **Neon** — project `generic-poker` (`late-wave-39283598`), AWS
**us-west-2**, chosen to match the Render web service's region so queries stay ~1-3ms
(a us-east-1 project would cost ~70ms per round trip). No expiry, unlike the old free
Render Postgres.

**Neon is reachable from WSL** (Render Postgres never was), so prod DB work no longer has
to be smuggled through a deploy:

```bash
export DATABASE_URL='<neon -pooler URL, sslmode=require>'
python -c "from app import create_app; create_app()"   # create_all for new tables
python tools/migrate_schema.py                          # idempotent ALTERs + CREATE TABLE IF NOT EXISTS
python tools/manage_user.py --username someuser --bankroll 2000
```

Connection string: Neon console, or the REST API with a `NEON_API_KEY`
(`GET /api/v2/projects/late-wave-39283598/connection_uri`). Erik's key is a file in
OneDrive (`generic-poker-neon.txt`), deliberately not in the repo or `~/.bashrc`.

`build.sh` runs `tools/migrate_schema.py` on every deploy (it no longer seeds — seeding
created `testuser`/`password` as an admin on prod; `seed_db.py` now refuses under
`FLASK_ENV=production`, and `tools/retire_seed_users.py` retires those accounts). **A column
added to a model needs a line in `migrate_schema.py`'s `ADD_COLUMNS`** — `create_all()`
creates missing tables but NEVER adds a column to an existing one. Prefer editing that
script over adding inline python to `build.sh` (it used to hold 130 lines of it).

**Neon specifics that bite:**
- `DATABASE_URL` is the **`-pooler`** host (PgBouncer, transaction mode): no session-level
  `pg_advisory_lock`, no `LISTEN/NOTIFY`, no session `SET` persistence. Nothing here uses
  them — keep it that way (a leaked session advisory lock is what bit the gamefinder repo).
- The compute **scales to zero after 5 min idle**; the first query then pays a ~500ms wake,
  and idle connections were dropped — that's what `pool_pre_ping` in `_engine_options()`
  (`config.py`) is for. Render free already cold-starts ~60s, so the wake is noise.
- `psycopg2` is a C extension whose sockets `eventlet.monkey_patch()` cannot patch, so
  `wsgi.py` calls `psycogreen.eventlet.patch_psycopg()` — without it every query blocks the
  single eventlet worker (and therefore every other player) for the whole round trip. Keep
  that call above the `create_app` import.
- Usage via the Neon MCP: `list_projects` → `quota_reset_at`, `describe_project` →
  `data_transfer_bytes`. **Those counters lag by hours** — an early 0 means "not aggregated
  yet", not "no usage". Quota (300 CU-h, 500 GB egress/mo, Launch plan) is SHARED with the
  gamefinder project.

Cleaning up a table: reuse `tools/seed_db.py::delete_table(table)` — it cashes out seated
players and deletes dependents in FK-safe order. Don't hand-roll DELETEs.

**Writing a new one-off DB script:**
```python
# tools/my_script.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app
from src.online_poker.database import db
from src.online_poker.models.user import User  # or any model

app, _ = create_app()
with app.app_context():
    # do your query/update here
    db.session.commit()
```
Run it locally with `DATABASE_URL` pointed at Neon. Only add it to `build.sh` if it must run
on every deploy.

## API Route Structure

Auth blueprint registered with `/auth` prefix:
- HTML: `/auth/login`, `/auth/register`, `/auth/logout`
- API: `/auth/api/register`, `/auth/api/login`, `/auth/api/logout`, `/auth/me`, `/auth/check-auth`

Edit a table after creation: `PUT /table/<id>/settings` (creator-only,
`TableManager.update_table_settings`) edits name/is_private/allow_bots. The lobby "Edit" button
(shown on owner cards) wires to it. Flipping `allow_bots` on fills empty seats the next time the
table page loads (the page emits `fill_bots` on connect; the server gates it on the flag).

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

## Deployment (Render)

Hosted on Render (free tier) with auto-deploy from GitHub.

**Architecture:** Web Service (Flask+SocketIO via gunicorn+eventlet) + PostgreSQL database.

**Key files:**
| File | Purpose |
|------|---------|
| `render.yaml` | Render blueprint — defines web service + Postgres |
| `wsgi.py` | Production entry point (eventlet monkey-patch + gunicorn) |
| `build.sh` | Build script (install deps, create tables, migrate schema; no seeding) |
| `requirements.txt` | Pinned Python dependencies for production |

**Start command:** `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT wsgi:app`

**Environment variables (set in Render dashboard):**
- `DATABASE_URL` — Postgres connection string (Neon pooled endpoint)
- `FLASK_ENV` — `production` (honored: `wsgi.py` calls `create_app(get_config())`, so
  `ProductionConfig` really loads — Secure cookies, no dev `SECRET_KEY` fallback)
- `SECRET_KEY` — auto-generated; `create_app` refuses to start without one
- `PYTHON_VERSION` — `3.10.12`
- Optional: `CORS_ORIGINS` (comma list; prod defaults to the site's own origin),
  `SOCKETIO_LOGGING`, `ENABLE_TEST_ROUTES` (unauth `/api/test/*`; dev/testing only),
  `TABLE_CLEANUP_INTERVAL_MINUTES` (empty-table sweep, 0 = off), `BANKROLL_RELOAD_THRESHOLD`
  / `BANKROLL_RELOAD_COOLDOWN_HOURS` (play-money reload).

**Deploys wipe live games:** a Render deploy restarts the single worker, and every game session
(bots included) lives in memory — hands in progress die, seats persist in the DB. The table
socket re-requests bots + ready status on reconnect so a bots table resumes by itself, but
**don't push while someone is testing**. E2E gotcha: `playwright.config.ts`'s `webServer`
uses `source` and fails under `sh` (exit 127) — start `python app.py` yourself first
(`reuseExistingServer`). Two fold-and-cycle E2E specs fail on the pre-2026-09 baseline too
(issue #14); the 7-Card Stud smoke is a flake that passes alone.

**Request hygiene (2026-09 onboarding pass):** a `before_request` hook in `app.py` 403s any
POST/PUT/DELETE whose `Origin` host isn't ours (or `Sec-Fetch-Site: cross-site`) — a token-less
CSRF check. curl/test clients send no Origin and pass; a browser on another origin doesn't.
Bots hold seats only in memory: `TableAccessManager.get_bot_seats()` merges them into seat
availability and a human joining a bot-held seat evicts the bot (`evict_bot_from_seat`). Busting
sends `player_busted` to that user (rebuy / reload / leave modal). CSS gotcha: `.btn` sets
`display`, so `hidden` on a button does nothing without a `.btn[hidden]{display:none}` rule.

**Changing an env var does NOT trigger a deploy** — PUT the value, then POST
`/v1/services/<id>/deploys` explicitly. Always use the single-key form
`/env-vars/<KEY>`; the array form replaces ALL vars and would rotate `SECRET_KEY`.

**Render CLI:**
```bash
# Install: download from https://github.com/render-oss/cli/releases
# Auth
render login
render workspace set tea-d6b0cji4d50c73ccmfl0

# Service management
render services --output json                              # List all services
render deploys list srv-d6b0ik86fj8s73bppftg --output json # List deploys
render deploys create srv-d6b0ik86fj8s73bppftg             # Trigger deploy
render logs -r srv-d6b0ik86fj8s73bppftg --limit 100 --output json  # View logs
```

**IDs:**
- Web Service: `srv-d6b0ik86fj8s73bppftg`
- Workspace: `tea-d6b0cji4d50c73ccmfl0`
- Postgres: **Neon**, project `generic-poker` = `late-wave-39283598` (aws-us-west-2, PG 17). No expiry.
  Render Postgres `generic-poker-db-5` (`dpg-d9vkhpb7uimc73ediu70-a`) is DEAD WEIGHT since the 2026-08-24
  cutover — kept only as a rollback path until it self-expires 2026-09-13.

**Known issues:**
- Render's own Postgres handed out `postgres://` URLs, which SQLAlchemy 2.0+ rejects — `_fix_database_url()` in `config.py`/`database.py` still normalizes it (Neon already emits `postgresql://`, so the shim is now belt-and-braces)
- All models must use `String(36)` for IDs (not `UUID(as_uuid=True)`) to work with both SQLite and PostgreSQL
- Free tier spins down after 15 min idle (~60s cold start on next request)
- **NEVER use `fromDatabase` in `render.yaml`** — it silently overrides the manually-set `DATABASE_URL` env var on every deploy. It would now also drag the app back off Neon onto a dead Render DB. `DATABASE_URL` must use `sync: false`.

### Postgres history (why the DB moved)

Production ran on Render's **free** Postgres, which expires every ~30 days and must be
recreated by hand. `db-3` lapsed on 2026-07-09 and took the site down for ten days before
anyone noticed; the free tier also allows only ONE active database, so each renewal meant
deleting the old one first — a fresh DB and a reseed every month, with no way to carry data
across. On **2026-08-24** the app moved to Neon (Launch plan, already paid for the gamefinder
project) and the whole ritual went away: the renewal runbook, the "one active free DB" trap,
and the weekly expiry-watchdog cloud routine are all retired. `git show b9934fd^:CLAUDE.md`
has the old runbook if a Render Postgres is ever needed again.

## Code Quality

### Tools

All configured in `pyproject.toml`. Pre-commit hooks enforce formatting and linting on every commit.

| Tool | Purpose | Config |
|------|---------|--------|
| **Ruff** | Linter + formatter (replaces flake8, autopep8, isort, black) | `[tool.ruff]` in pyproject.toml |
| **Pre-commit** | Git hooks for automated checks on commit | `.pre-commit-config.yaml` |
| **Bandit** | Python security scanner | `[tool.bandit]` in pyproject.toml |
| **pip-audit** | Dependency vulnerability scanner | Run manually: `pip-audit` |

### Rules

- **All new/modified Python code must pass `ruff check` and `ruff format`** — pre-commit hooks enforce this
- Ruff uses 120 char line length, double quotes, Python 3.10+ target
- Import ordering handled automatically by ruff (isort rules)
- SQLAlchemy `== True`/`== False` comparisons are allowed (E712 ignored)
- `print()` allowed in `app.py`, `tools/`, and test files
- Security rules relaxed for `tests/` and `tools/` directories
- Game config JSON files validated against `data/schemas/game.json` schema

### Setup

```bash
pip install -e ".[dev]"          # Install dev tools
pre-commit install               # Set up git hooks (one-time)
```

### Common Commands

```bash
ruff check src/                  # Check for lint errors
ruff check src/ --fix            # Auto-fix what's possible
ruff format src/                 # Format all source code
pre-commit run --all-files       # Run all hooks on entire codebase
pip-audit                        # Check for dependency vulnerabilities
```

## Project Status & Planning

| Document | Purpose |
|----------|---------|
| `docs/STATUS.md` | **Current project status**, open bugs, service quality, testing state |
| `docs/BACKLOG.md` | **Prioritized task backlog** organized in phases |
| `docs/GAME_VALIDATION.md` | **Game config feature matrix**, variant testing strategy, new game workflow |
| `docs/UX_TEST_FINDINGS.md` | UX test report (2026-06) — open UI issues for testers |
| `docs/MONTE_CARLO_BOT_DESIGN.md` | MC bot design, audit findings, phase plan |
| `DEVELOPMENT.md` | Development workflow, debugging tips |
| `data/schemas/README.md` | Complete JSON config schema documentation |
| `src/generic_poker/*-readme.md` | Component-specific API documentation |

> **Note:** The original Kiro IDE spec (`.kiro/`) was removed 2026-06-26 — its open items were migrated to `docs/BACKLOG.md` Phase 10 and its requirements/design docs archived under `docs/archive/`. The current source of truth for status and tasks is `docs/STATUS.md` and `docs/BACKLOG.md`.
