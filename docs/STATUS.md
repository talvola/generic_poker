# Project Status

> Single source of truth for project state. Updated as work progresses.
> Last updated: 2026-02-16

## Architecture Overview

### Core Engine (`src/generic_poker/`)

Rule-driven poker engine where variants are defined by JSON configs, not code. Supports 192+ variants.

| Component | File | Purpose |
|-----------|------|---------|
| Game | `game/game.py` | Central controller: game flow, state transitions, player actions |
| Table | `game/table.py` | Players, seating, dealer/blind positions, card distribution |
| BettingManager | `game/betting.py` | Betting rounds, pot management (main/side), action validation |
| GameRules | `config/loader.py` | Parses JSON configs defining game variants |
| HandEvaluator | `evaluation/evaluator.py` | Hand evaluation via pre-computed rankings (O(1) lookups) |
| Card/Deck | `core/` | Card primitives (Card, Rank, Suit, Visibility) |

**Status: Solid.** Core engine works well. Don't modify unless fixing a specific bug.

### Online Platform (`src/online_poker/`)

Flask/SocketIO multiplayer web platform.

| Service | File | Quality | Notes |
|---------|------|---------|-------|
| GameOrchestrator | `services/game_orchestrator.py` | 8/10 | Coordinates game lifecycle |
| GameStateManager | `services/game_state_manager.py` | 8/10 | Phase detection and hand results working |
| WebSocketManager | `services/websocket_manager.py` | 7/10 | Works but has responsibility leaks (game logic mixed in) |
| PlayerActionManager | `services/player_action_manager.py` | 8/10 | Solid, minor timeout config issues |
| DisconnectManager | `services/disconnect_manager.py` | 8/10 | Uses RLock to prevent deadlocks |
| TableAccessManager | `services/table_access_manager.py` | 9/10 | Clean, mostly complete |
| TableManager | `services/table_manager.py` | 9/10 | Clean |

### Frontend

| File | Lines | Quality | Notes |
|------|-------|---------|-------|
| `static/js/table.js` | 1,577 | 8/10 | Core module, uses GameStateStore + 7 extracted modules |
| `static/js/table/` | ~850 | 8/10 | 7 modules: card-utils, modals, chat, timer, bet-controls, responsive, showdown |
| `static/js/table/game-state-store.js` | ~35 | 9/10 | Centralized state management |
| `static/js/lobby.js` | 1,033 | 8/10 | Clean, well-organized |
| `static/css/table.css` | ~2,950 | 9/10 | Well-organized, good responsive design |
| `static/css/lobby.css` | 1,817 | 8/10 | Clean |

---

## Feature Status

### Working

- Core poker engine (192+ variants, hand evaluation, betting logic)
- User authentication and session management
- Table creation and lobby (browse, filter, join)
- WebSocket real-time communication
- Card rendering and seat positioning (own cards + opponent card backs)
- Chat system (messaging + game action log)
- Responsive CSS layout
- Ready system (players ready up, hand starts)
- Betting actions: fold, check, call, bet, raise
- Draw/discard actions with card selection UI (5-Card Draw, Badugi, Triple Draw, etc.)
- Game auto-progression through dealing/betting rounds
- Showdown display (reveal cards, announce winner, award pot)
- Hand completion and next hand cycle
- Deck shuffling between hands
- Table rejoin after leaving
- Leave/rejoin lifecycle (mid-hand leave auto-folds, deferred removal, session cleanup)
- Lobby filter dropdowns (variant, stakes, structure, players)
- WebSocket table join with buy-in validation and seat selection
- Centralized game state store (GameStateStore)
- Error notifications for failed fetch calls
- Turn timer countdown visible on active player's seat (all players see it)
- 166 game variants available in lobby (dynamically loaded, grouped by category)
- Game config `category` field for UI grouping (8 families)
- Data-driven community card layout (linear layout auto-inferred for ~160 games, draw games hide community area)
- Granular card display scaling (3-4 cards, 5-6 cards, 7-8 cards with overlap)

### Remaining Issues

| # | Issue | Priority | Description |
|---|-------|----------|-------------|
| ~~1~~ | ~~Bot fold bug~~ | ~~DONE~~ | ~~Fixed: never fold when check available~~ |
| ~~2~~ | ~~Debug prints~~ | ~~DONE~~ | ~~Removed 7 debug prints, replaced with proper logging~~ |
| 3 | Hardcoded timeouts | LOW | 30s action, 10min disconnect timeouts not configurable |
| 4 | Debug deck option | LOW | No way to use fixed/unseeded deck for testing |
| ~~5~~ | ~~3+ player games~~ | ~~DONE~~ | ~~Engine, CSS, rendering all support 3+ players~~ |
| ~~6~~ | ~~Draw/discard actions~~ | ~~DONE~~ | ~~Card selection UI, backend plumbing, 65 draw games playable~~ |
| 7 | Card passing | MEDIUM | Required for pass-card variants |
| 8 | Hand history display | LOW | Not implemented |
| 9 | Mobile optimization | LOW | Chat panel toggle works but needs testing |
| 10 | Admin interface | LOW | Not implemented |
| 11 | Stud game UI | MEDIUM | Per-player up/down cards, 7+ cards per player |

---

## Testing

### Test Counts (2026-02-16)

| Layer | Tests | Status |
|-------|-------|--------|
| Python unit + integration | 814 | All passing |
| Smoke test (all 192 variants) | 345 | 333 pass, 12 xfail (known bugs) |
| Socket.IO integration | 33 | All passing (in `test_socketio_integration.py`) |
| Playwright E2E | 26 | All passing (4 spec files) |
| **Total** | **1,159** | **All passing** |

### Test Layers

```
Layer 0: Smoke Tests (all 192 variants)
  - Parametrized: loads each config, creates game, plays a hand passively
  - Catches crashes, infinite loops, missing implementations
  - tests/game/test_all_variants_smoke.py
  - 26 unsupported (unimplemented actions), 13 xfail (engine bugs)

Layer 1: Python Integration Tests (engine + services)
  - Drive game engine directly: game.start_hand(), game.player_action()
  - No WebSocket, no browser needed. Fast (< 1 second per test)
  - tests/integration/test_gameplay_integration.py
  - Use this for 90% of bug fixes

Layer 2: Socket.IO Integration Tests (WebSocket events)
  - flask_socketio.test_client (Python, no browser)
  - tests/integration/test_socketio_integration.py
  - 9 tests covering connect, join, ready, fold, call/check, full hand, broadcasts

Layer 3: E2E Browser Tests (visual verification)
  - Playwright with multi-user fixtures
  - tests/e2e/specs/ (4 spec files, 26 tests)
  - Covers preflop betting, fold/cycle, full hand to showdown, UI elements
```

### Development Workflow for Bug Fixes

1. Reproduce with a Python integration test (Layer 1)
2. Fix the server-side code
3. Verify the test passes
4. If UI rendering bug, also verify in browser (Layer 3)
5. If WebSocket event bug, add Socket.IO test (Layer 2)

---

## Completed Phases

### Phase 0: Testing Foundation
- Verified 768 existing tests pass, fixed 2 failing unit tests
- Fixed `disconnect_manager.py` deadlock (Lock → RLock)
- Fixed PlayerAction enum value casing
- Added 9 Socket.IO integration tests

### Phase 1: Core Gameplay (2-Player Texas Hold'em)
- Fixed blind deduction display, community cards structure
- Implemented hand result processing
- Fixed showdown display, table rejoin
- Fixed deck shuffling between hands
- Fixed action double-send bug (WebSocket broadcast loop)
- Added Playwright regression suite (26 tests)

### Phase 2: UI Refactoring
- Split table.js into 7 modules + core (2,462 → 1,577 + 850 lines)
- Created centralized GameStateStore
- Added error handling and user feedback (notifications on failed fetches)
- Fixed action panel width stability
- Fixed table shape (oval → rounded rectangle matching seat selection)
- Fixed chat toggle (added collapsed CSS) and mobile panel toggle
- Fixed lobby filter bug (tables disappearing permanently)
- Fixed lobby race condition (loadTables before socket connected)
- Fixed WebSocket join handlers (buy-in, seat selection, bankroll validation)

---

## Known Engine Bugs (from smoke test)

Found by `tests/game/test_all_variants_smoke.py`. All marked `xfail` so test suite stays green.

| Game | Bug | Location |
|------|-----|----------|
| 2_or_5_omaha_8, 2_or_5_omaha_8_with_draw | `TypeError: int + list` in showdown | `showdown_manager.py:1645` |
| canadian_stud | `soko_high` evaluation requires exactly 5 cards | `evaluator.py` |
| london_lowball | `a6_low` evaluation requires exactly 5 cards | `evaluator.py` |
| razzaho | `a5_low` evaluation requires exactly 5 cards | `evaluator.py` |
| razzbadeucey, super_razzbadeucey | `badugi_ah` evaluation requires exactly 4 cards | `evaluator.py` |
| omaha_321_hi_hi | `NoneType.cards` AttributeError in showdown | `showdown_manager.py:1472` |
| one_mans_trash | Drawing phase stuck (DRAW returns no valid actions) | `player_action_handler.py` |
| stampler, stumpler, 5_card_stampler, 6_card_stampler | Chip conservation failure (ante handling) | `betting.py` / `game.py` |

### Unsupported Games (26 — require unimplemented actions)

These games use `expose`, `pass`, `declare`, `separate`, or `choose` actions that haven't been implemented yet. They are skipped entirely in the smoke test.

```
3_hand_hold_em, 3_hand_hold_em_8, 5_card_shodugi, 6_card_shodugi,
7_card_flip, 7_card_flip_8, 7_card_stud_hilo_declare, cowpie,
crazy_sohe, double_hold_em, italian_poker, kentrel, lazy_sohe,
mexican_poker, paradise_road_pickem, pass_the_pineapple, sheshe,
showmaha, showmaha_8, sohe, sohe_311, straight_7card_declare,
straight_9card_declare, straight_declare, studaha, tahoe_pitch_roll
```

---

## Historical Bugs (Fixed)

See `docs/BACKLOG.md` for the complete bug tracking list with statuses.
