# Project Status

> Single source of truth for project state. Updated as work progresses.
> Last updated: 2026-02-12

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

| Service | File | Quality | Key Issues |
|---------|------|---------|------------|
| GameOrchestrator | `services/game_orchestrator.py` | 8/10 | Delegates hand starting to WebSocket handler |
| GameStateManager | `services/game_state_manager.py` | 6/10 | Broken phase detection, stubbed hand results |
| WebSocketManager | `services/websocket_manager.py` | 7/10 | Works but has responsibility leaks (game logic mixed in) |
| PlayerActionManager | `services/player_action_manager.py` | 8/10 | Solid, minor timeout config issues |
| DisconnectManager | `services/disconnect_manager.py` | 8/10 | Import bug (line 300), hardcoded timeouts |
| TableAccessManager | `services/table_access_manager.py` | 9/10 | Clean, mostly complete |
| TableManager | `services/table_manager.py` | 9/10 | Clean |

### Frontend

| File | Lines | Quality | Notes |
|------|-------|---------|-------|
| `static/js/table.js` | 2,462 | 6/10 | Monolithic, needs splitting into modules |
| `static/js/lobby.js` | 1,033 | 8/10 | Clean, well-organized |
| `static/css/table.css` | 2,935 | 9/10 | Well-organized, good responsive design |
| `static/css/lobby.css` | 1,817 | 8/10 | Clean |

---

## Feature Status

### Working

- Core poker engine (192+ variants, hand evaluation, betting logic)
- User authentication and session management
- Table creation and lobby (browse, filter, join)
- WebSocket real-time communication (basic)
- Card rendering and seat positioning (own cards)
- Chat system (basic messaging)
- Responsive CSS layout
- Ready system (players ready up, hand starts)
- Betting actions: fold, check, call, bet, raise
- Game auto-progression through dealing/betting rounds
- Fold status resets between hands
- Python integration tests can drive full game hands

### Broken / Incomplete

These are the active issues blocking a working 2-player Texas Hold'em game.

| # | Bug | Priority | Description | Key Files |
|---|-----|----------|-------------|-----------|
| 1 | Blind deduction display | HIGH | Pot/stacks may not reflect blinds correctly in UI | `game_state_manager.py`, `table.js` |
| 2 | Community cards structure | HIGH | `_get_game_phase()` uses `community_cards.get('board', [])` but cards are stored as `flop1/flop2/flop3/turn/river` keys | `game_state_manager.py:414` |
| 3 | Opponent card backs | HIGH | Other players' face-down cards not rendered (empty seats) | `table.js`, `table.css` |
| 4 | Hand result processing | HIGH | `process_hand_completion()` returns empty winners/pot_distribution | `game_state_manager.py:708-737` |
| 5 | Game actions in chat | MEDIUM | Blinds, bets, folds not shown in action log | `websocket_manager.py`, `table.js` |
| 6 | Showdown display | HIGH | Cards not revealed, winner not announced, pot not awarded visually | `table.js`, `websocket_manager.py` |
| 7 | Table rejoin | MEDIUM | Cannot rejoin table after leaving | `lobby_routes.py`, `table_access_manager.py` |
| 8 | Bot fold bug | LOW | SimpleBot folds when check is available | Bot logic |
| 9 | Action panel width | LOW | Panel width shifts causing layout jitter | `table.css` |
| 10 | Debug prints | LOW | 7 debug print statements in `lobby_routes.py` create_table | `lobby_routes.py:73-155` |
| 11 | Disconnect import | LOW | Double-reference import in `disconnect_manager.py:300` | `disconnect_manager.py` |
| 12 | Hardcoded timeouts | LOW | 30s action, 10min disconnect timeouts not configurable | `disconnect_manager.py` |

### Not Started

- Draw/discard actions (required for draw poker variants)
- Card passing (required for pass-card variants)
- Hand history display
- Admin interface
- Rate limiting
- Mobile optimization testing
- Socket.IO integration tests (Layer 2 testing)

---

## Testing

### Test Layers

```
Layer 1: Python Integration Tests (engine + services)
  - Drive game engine directly: game.start_hand(), game.player_action()
  - No WebSocket, no browser needed. Fast (< 1 second per test)
  - EXISTS: tests/integration/test_gameplay_integration.py
  - Use this for 90% of bug fixes

Layer 2: Socket.IO Integration Tests (WebSocket events)
  - Use flask_socketio.test_client (Python, no browser)
  - Test WebSocket events produce correct state broadcasts
  - MISSING - needs to be built

Layer 3: E2E Browser Tests (visual verification)
  - Playwright with multi-user fixtures
  - Slow (~10-30 seconds per test)
  - EXISTS: tests/e2e/specs/preflop-betting.spec.ts
  - Use sparingly - for visual/UX validation only
```

### Existing Integration Tests

| File | Coverage |
|------|----------|
| `test_auth_integration.py` | Registration, login, session management |
| `test_game_config.py` | JSON config validation, schema compliance |
| `test_gameplay_integration.py` | Full gameplay flow, betting, state progression |
| `test_table_join_integration.py` | Public/private join, buy-in, seat selection |
| `test_transaction_integration.py` | Bonus transactions, cash out, insufficient funds |

### Development Workflow for Bug Fixes

1. Reproduce with a Python integration test (Layer 1)
2. Fix the server-side code
3. Verify the test passes
4. If UI rendering bug, also verify in browser (Layer 3)
5. If WebSocket event bug, add Socket.IO test (Layer 2)

---

## Historical Bugs (Fixed)

These bugs from `.kiro/specs/online-poker-platform/bugs.md` have been resolved:

| Bug | Description | Fix |
|-----|-------------|-----|
| G001 | Cards not rendering | Fixed card data path in table.js |
| G002 | Action panel not showing | Fixed to use WebSocket-provided valid_actions |
| G003 | Ready panel visible during play | Hidden during active hand |
| G004 | Pot shows $0 after blinds | Fixed `_get_pot_info()` serialization |
| G005 | Player join not updating other views | Added `_generate_waiting_state()` |
| G007 | Fold status persists across hands | Added `player.is_active = True` in `clear_hands()` |
| G008 | Game not auto-progressing after betting | Added `_next_step()` calls in action handlers |
