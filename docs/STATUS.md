# Project Status

> Single source of truth for project state. Updated as work progresses.
> Last updated: 2026-02-14

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
- Game auto-progression through dealing/betting rounds
- Showdown display (reveal cards, announce winner, award pot)
- Hand completion and next hand cycle
- Deck shuffling between hands
- Table rejoin after leaving
- Lobby filter dropdowns (variant, stakes, structure, players)
- WebSocket table join with buy-in validation and seat selection
- Centralized game state store (GameStateStore)
- Error notifications for failed fetch calls

### Remaining Issues

| # | Issue | Priority | Description |
|---|-------|----------|-------------|
| 1 | Bot fold bug | LOW | SimpleBot folds when check is available |
| 2 | Debug prints | LOW | 7 debug print statements in `lobby_routes.py` create_table |
| 3 | Hardcoded timeouts | LOW | 30s action, 10min disconnect timeouts not configurable |
| 4 | Debug deck option | LOW | No way to use fixed/unseeded deck for testing |
| 5 | 3+ player games | MEDIUM | Untested with more than 2 players |
| 6 | Draw/discard actions | MEDIUM | Required for draw poker variants |
| 7 | Card passing | MEDIUM | Required for pass-card variants |
| 8 | Hand history display | LOW | Not implemented |
| 9 | Mobile optimization | LOW | Chat panel toggle works but needs testing |
| 10 | Admin interface | LOW | Not implemented |

---

## Testing

### Test Counts (2026-02-14)

| Layer | Tests | Status |
|-------|-------|--------|
| Python unit + integration | 801 | All passing |
| Socket.IO integration | 9 | All passing (in `test_socketio_integration.py`) |
| Playwright E2E | 26 | All passing (4 spec files) |

### Test Layers

```
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

## Historical Bugs (Fixed)

See `docs/BACKLOG.md` for the complete bug tracking list with statuses.
