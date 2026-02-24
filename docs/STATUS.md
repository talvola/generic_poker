# Project Status

> Single source of truth for project state. Updated as work progresses.
> Last updated: 2026-02-23

## Architecture Overview

### Core Engine (`src/generic_poker/`)

Rule-driven poker engine where variants are defined by JSON configs, not code. Supports 293+ variants.

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
| BotActionService | `services/bot_action_service.py` | 8/10 | Background bot loop, per-table locking |
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

- Core poker engine (293+ variants, hand evaluation, betting logic, all 3 forced bet styles verified)
- Antes-only "flip" game support (9-Card Omaha)
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
- All 293 game variants available in lobby (dynamically loaded, grouped by category)
- Game config `category` field for UI grouping (8 families)
- Data-driven community card layout (linear, multi-row, branching, grid)
- Multi-row layout for double board, scarney, kryky games (~12 configs)
- Branching layout for chowaha, omaha 3-2-1, tapiola games (~12 configs)
- Grid layout for tic-tac, criss-cross, banco games (~7 configs)
- Granular card display scaling (3-4 cards, 5-6 cards, 7-8 cards with overlap)
- DECLARE action (hi/lo declare UI for 5 games)
- CHOOSE action (variant selection UI for paradise_road_pickem)
- Parametrized E2E smoke tests (15 variants covering all action types and community layouts)
- Hand history display (DB persistence, API, modal with expandable details)
- Bot support: "Fill with Bot Players" fills empty seats, bots handle all 293 variants (all action types)

### Remaining Issues

| # | Issue | Priority | Description |
|---|-------|----------|-------------|
| ~~3~~ | ~~Hardcoded timeouts~~ | ~~LOW~~ | ~~Fixed: all timeouts and limits configurable via env vars~~ |
| 4 | Debug deck option | LOW | No way to use fixed/unseeded deck for testing |
| 9 | Mobile optimization | LOW | Deferred to Phase 7 |
| ~~10~~ | ~~Admin interface~~ | ~~LOW~~ | ~~Implemented: dashboard, user/table/variant management~~ |

---

## Testing

### Test Counts (2026-02-23)

| Layer | Tests | Status |
|-------|-------|--------|
| Python unit + integration | 724 | All passing |
| Smoke test (all 293 variants) | 586 | All passing (0 unsupported, 0 xfail) |
| Playwright E2E | 57 | All passing (9 spec files) |
| **Total** | **~1,546** | **All passing** |

### Test Layers

```
Layer 0: Smoke Tests (all 293 variants)
  - Parametrized: loads each config, creates game, plays a hand passively
  - Catches crashes, infinite loops, missing implementations
  - All 293 games pass (0 unsupported, 0 xfail)
  - tests/game/test_all_variants_smoke.py

Layer 1: Python Integration Tests (engine + services)
  - Drive game engine directly: game.start_hand(), game.player_action()
  - No WebSocket, no browser needed. Fast (< 1 second per test)
  - tests/integration/test_gameplay_integration.py
  - Use this for 90% of bug fixes

Layer 2: Socket.IO Integration Tests (WebSocket events, included in Layer 1 count)
  - flask_socketio.test_client (Python, no browser)
  - tests/integration/test_socketio_integration.py
  - Tests covering connect, join, ready, fold, call/check, full hand, broadcasts

Layer 3: E2E Browser Tests (visual verification)
  - Playwright with multi-user fixtures
  - tests/e2e/specs/ (9 spec files, 57 tests)
  - Original 6 specs: preflop betting, fold/cycle, full hand, UI elements, 3-player, Omaha
  - variant-smoke.spec.ts: 15 representative variants (betting, draw, expose, declare, choose, separate)
  - draw-actions.spec.ts: 4 draw/discard UI verification tests
  - special-actions.spec.ts: 4 declare/expose/separate/choose UI tests
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
- Added Playwright regression suite (34 tests across 6 spec files)

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

All 13 previously-buggy games fixed (2026-02-17). Zero xfails remaining.

Fixes applied:
- **2 games** (2_or_5_omaha_8 variants): `int + list` TypeError — added list handling for holeCards/communityCards in showdown odd-chip logic
- **5 games** (canadian_stud, london_lowball, razzaho, razzbadeucey, super_razzbadeucey): Evaluation card count errors — bring-in fallback to generic N-card eval types + combinatorial best-of-N selection when visible cards exceed evaluator hand size
- **1 game** (omaha_321_hi_hi): Config name mismatch — `usesUnusedFrom: "High Hand"` referenced non-existent config name `"High"`
- **1 game** (one_mans_trash): Drawing stuck — smoke test didn't handle REPLACE_COMMUNITY action + config had wrong communityCards count (5→3)
- **4 games** (stampler/stumpler variants): Chip conservation — `_award_special_pot()` created PotResult records but never called `betting.award_pots()` to transfer chips

### Unsupported Games

None — all 293 game variants are now fully supported. All action types (expose, pass, declare, separate, choose) implemented.

### Pagat.com Cross-Reference (2026-02-18)

Cross-referenced our configs against 352 Pagat.com poker variants. See `docs/PAGAT_CROSS_REFERENCE.md`.

- **45 of our games** match Pagat variants (42 had Pagat URLs added to their references)
- **~38 Pagat games** could be added with config-only changes (no engine modifications)
- **~47 Pagat games** need new engine features (Buy, Dynamic Wilds, No Peek, etc.)
- **~57 Pagat games** are out of scope (guts/match games, non-poker)
- **6 new engine features** identified, prioritized by casino relevance (see `docs/BACKLOG.md` Phase 6)

---

## Historical Bugs (Fixed)

See `docs/BACKLOG.md` for the complete bug tracking list with statuses.
