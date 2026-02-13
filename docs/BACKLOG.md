# Backlog

> Prioritized task list. Work top-to-bottom within each phase.
> Phase 1 is the current focus: get 2-player Texas Hold'em working end-to-end.
> Last updated: 2026-02-12

---

## Phase 0: Testing Foundation

Before fixing bugs, ensure we can verify fixes properly.

| # | Task | Files | Status |
|---|------|-------|--------|
| 0.1 | Verify existing integration tests pass | `tests/integration/` | TODO |
| 0.2 | Add Socket.IO integration test for 2-player hand | `tests/integration/` | TODO |

**0.2 details:** Use `flask_socketio.test_client` to test join_table, player_ready, game_state_update, player_action events. No browser needed. Pattern:

```python
socketio_test_client = socketio.test_client(app, flask_test_client=http_client)
socketio_test_client.emit('join_table', {'table_id': table_id})
received = socketio_test_client.get_received()
assert any(msg['name'] == 'game_state_update' for msg in received)
```

---

## Phase 1: Core Gameplay (2-Player Texas Hold'em)

Goal: One complete hand works perfectly - deal, bet, flop, bet, turn, bet, river, bet, showdown, pot awarded, next hand.

| # | Task | Key Files | Status |
|---|------|-----------|--------|
| 1.1 | Fix blind deduction display (pot shows correct total, stacks reduced) | `game_state_manager.py`, `table.js` | TODO |
| 1.2 | Fix community cards structure and phase detection | `game_state_manager.py` | TODO |
| 1.3 | Show opponent card backs (face-down cards visible) | `table.js`, `table.css` | TODO |
| 1.4 | Implement hand result processing (winners, pot distribution) | `game_state_manager.py` | TODO |
| 1.5 | Show game actions in action log (blinds, bets, folds) | `websocket_manager.py`, `table.js` | TODO |
| 1.6 | Fix showdown display (reveal cards, announce winner, award pot) | `table.js`, `websocket_manager.py` | TODO |
| 1.7 | Fix table rejoin after leaving | `lobby_routes.py`, `table_access_manager.py` | TODO |
| 1.8 | Verify full hand cycle end-to-end | All services | TODO |

### Task Details

**1.2 - Community cards structure:**
`_get_game_phase()` at `game_state_manager.py:414` calls `community_cards.get('board', [])` but `_get_community_cards()` returns keys `flop1`, `flop2`, `flop3`, `turn`, `river`. This mismatch causes phase detection to always default to PREFLOP during betting rounds.

**1.4 - Hand result processing:**
`process_hand_completion()` at `game_state_manager.py:708` is stubbed. Lines 716-719 return empty `winners = []`, empty `pot_distribution = {}`, empty `player_hands = {}`. The core engine already computes results via `game.get_hand_results()` - this method just needs to read and serialize them.

---

## Phase 2: UI Refactoring

After gameplay works, make the frontend maintainable.

| # | Task | Key Files | Status |
|---|------|-----------|--------|
| 2.1 | Split table.js into modules (state, socket, renderer, actions) | `static/js/` | TODO |
| 2.2 | Create centralized game state store | `static/js/state.js` | TODO |
| 2.3 | Add error handling and user feedback | `static/js/`, `templates/` | TODO |
| 2.4 | Fix action panel width stability | `table.css` | TODO |

---

## Phase 3: Polish & Extended Gameplay

| # | Task | Status |
|---|------|--------|
| 3.1 | Fix bot decision logic (don't fold when check available) | TODO |
| 3.2 | Support 3+ player games | TODO |
| 3.3 | Add player timeout countdown UI | TODO |
| 3.4 | Implement draw/discard actions | TODO |
| 3.5 | Implement card passing | TODO |
| 3.6 | Add hand history display | TODO |
| 3.7 | Mobile optimization pass | TODO |

---

## Phase 4: Production Readiness

| # | Task | Status |
|---|------|--------|
| 4.1 | Unify timeout systems (action, disconnect, ready) | TODO |
| 4.2 | Make hardcoded constants configurable | TODO |
| 4.3 | Remove debug print statements from routes | TODO |
| 4.4 | Sync game engine state with database after each hand | TODO |
| 4.5 | Add rate limiting | TODO |
| 4.6 | Admin interface | TODO |

---

## Phase 5: Game Engine Validation

Goal: Systematically verify that all JSON config features work and establish a workflow
for adding new variants. See `docs/GAME_VALIDATION.md` for full details.

| # | Task | Key Files | Status |
|---|------|-----------|--------|
| 5.1 | Create parametrized smoke test for all 192 variants | `tests/game/` | TODO |
| 5.2 | Add tests for rare-feature games (roll_die, choose, remove) | `tests/game/` | TODO |
| 5.3 | Implement `all_exposed`/`any_exposed`/`none_exposed` conditions | `game.py:531` | TODO |
| 5.4 | Implement `separate.hand_comparison` if needed | `player_action_handler.py` | TODO |
| 5.5 | Build "can this game be implemented?" assessment skill | `.claude/` | TODO |
| 5.6 | Build "implement new game variant" skill | `.claude/` | TODO |

**5.1 details:** A single parametrized test that loads each config, creates a game with
minimum players, and plays a hand to completion (everyone checks/calls). Should catch
crashes, infinite loops, and missing implementations. ~126 variants currently have no
end-to-end test.

**5.5-5.6 details:** Claude Code skills that:
- 5.5: Given a game description URL, analyze rules and determine if implementable with
  JSON-only or needs code changes. Check against the feature matrix.
- 5.6: Walk through implementing a new variant - create config, write test, run test.
  For code-change variants, identify what engine changes are needed.

---

## Open Bugs from Earlier Testing

These are bugs found during `.kiro` testing sessions that may or may not still be relevant. Verify before working on them.

| Bug | Priority | Description | Status |
|-----|----------|-------------|--------|
| T001 | High | Private table join with invite code fails | Open (may be fixed) |
| T002 | High | Buy-in amount not applied correctly (uses minimum) | Open |
| T003 | Medium | Seat selection ignored during join | Open |
| T004 | Medium | Chat messages area not visible | Open (may be fixed) |
| T005 | Critical | Insufficient bankroll check not working | Open |
| T006 | Medium | Lobby shows 0 tables after redirect | Open |
| G006 | High | 404 for available-actions API endpoint | Open (may be fixed) |
