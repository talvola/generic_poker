# Backlog

> Prioritized task list. Work top-to-bottom within each phase.
> Last updated: 2026-02-19

---

## Phase 0: Testing Foundation ✓

Before fixing bugs, ensure we can verify fixes properly.

| # | Task | Files | Status |
|---|------|-------|--------|
| 0.1 | Verify existing integration tests pass | `tests/integration/` | DONE |
| 0.2 | Add Socket.IO integration test for 2-player hand | `tests/integration/` | DONE |

**0.1 result:** 768 tests pass. Fixed 2 failing unit tests in `test_game_state_manager.py` (mock setup issues) and a real bug: `disconnect_manager.py` used `threading.Lock` causing deadlock when `_handle_auto_fold` was called from within `handle_player_disconnect` (changed to `RLock`). Also fixed `websocket_manager.py` using `.upper()` instead of `.lower()` for PlayerAction enum values.

**0.2 result:** 9 Socket.IO integration tests in `tests/integration/test_socketio_integration.py`. Tests cover: connect, join room, ready/hand start, fold, call/check, full hand to showdown, action broadcasts, card hiding. Key patterns for multi-user SocketIO testing:
- Use `StaticPool` for in-memory SQLite so all connections share the same DB
- Patch `_handle_event` to clear `flask.g._login_user` before each handler (Flask-Login caches `current_user` in the app-context-level `g`, which is shared across SocketIO handlers)
- Use `RLock` in disconnect_manager to prevent deadlocks during disconnect handling

---

## Phase 1: Core Gameplay (2-Player Texas Hold'em)

Goal: One complete hand works perfectly - deal, bet, flop, bet, turn, bet, river, bet, showdown, pot awarded, next hand.

| # | Task | Key Files | Status |
|---|------|-----------|--------|
| 1.1 | Fix blind deduction display (pot shows correct total, stacks reduced) | `game_state_manager.py` | DONE |
| 1.2 | Fix community cards structure and phase detection | `game_state_manager.py` | DONE |
| 1.3 | Show opponent card backs (face-down cards visible) | `table.js`, `table.css` | DONE (already implemented) |
| 1.4 | Implement hand result processing (winners, pot distribution) | `game_state_manager.py`, `websocket_manager.py` | DONE |
| 1.5 | Show game actions in action log (blinds, bets, folds) | `websocket_manager.py`, `table.js` | DONE (already implemented for Hold'em) |
| 1.6 | Fix showdown display (reveal cards, announce winner, award pot) | `table.js`, `websocket_manager.py` | DONE |
| 1.7 | Fix table rejoin after leaving | `websocket_manager.py` | DONE |
| 1.8 | Verify full hand cycle end-to-end | All services | DONE |
| 1.9 | Edge case tests (all-in, split pot, raise sequences) | `tests/game/`, `tests/integration/` | DONE |
| 1.10 | Playwright regression suite for UI | `tests/e2e/specs/` | DONE |

### Task Details

**1.1 result:** `_get_current_bet()` was reading `player.current_bet` but Player class has no such attribute. Fixed to read from `game.betting.current_bets[player_id].amount`. Pot and stacks now correctly reflected in game state after blinds.

**1.2 result:** `_get_game_phase()` used `community_cards.get('board', [])` but `_get_community_cards()` returns `{flop1, flop2, flop3, turn, river}` keys. Fixed to count dict keys. Also fixed `detect_state_changes` and `process_hand_completion` which had the same `board` reference bug.

**1.4 result:** `process_hand_completion()` was stubbed with empty results. Fixed to call `game.get_hand_results()` and serialize the engine's `GameResult`. Also found that `handle_player_action` in `websocket_manager.py` never called `broadcast_hand_complete` - added hand completion check after game state update broadcast.

**1.7 result:** The `handle_leave_table` SocketIO handler in `websocket_manager.py` only updated the DB (via `TableAccessManager.leave_table()`) but never removed the player from the game orchestrator session. Fixed by adding `session.remove_player()` call before DB update and broadcasting updated game state to remaining players. The rejoin flow (leave → HTTP join → connect to room → set ready) works correctly since `_start_hand_when_ready` re-adds players to the session.

---

## Phase 2: UI Refactoring

After gameplay works, make the frontend maintainable.

| # | Task | Key Files | Status |
|---|------|-----------|--------|
| 2.1 | Split table.js into modules (state, socket, renderer, actions) | `static/js/table/` | DONE |
| 2.2 | Create centralized game state store | `static/js/table/game-state-store.js` | DONE |
| 2.3 | Add error handling and user feedback | `static/js/table.js` | DONE |
| 2.4 | Fix action panel width stability | `table.css` | DONE |

### Task Details

**2.1 result:** Split monolithic `table.js` (2,462 lines) into 7 modules + core (1,577 + 850 lines): `card-utils.js`, `modals.js`, `chat.js`, `timer.js`, `bet-controls.js`, `responsive.js`, `showdown.js`. Loaded via `<script>` tags in dependency order. Communication via dependency injection.

**2.2 result:** Created `GameStateStore` class in `game-state-store.js` (~35 lines) that holds all game state (`gameState`, `currentUser`, `players`, `isMyTurn`, `validActions`, `potAmount`, `handNumber`, `tableId`). `update(data)` ingests server data and computes derived state. Modules receive store reference directly instead of closure-based getters. `findPlayerByUserId()` helper replaces repeated lookup patterns.

**2.3 result:** Added `PokerModals.showNotification()` to 3 silent `catch` blocks in `requestGameState()`, `loadAvailableActions()`, and `fetchAndDisplayHandResults()`. Added `response.ok` guards before `.json()` calls on all 4 fetch endpoints.

**2.4 result:** Added `min-height: 80px` to `.action-panel` and `min-height: 50px` + `align-items: center` to `.action-buttons`. Moved `.waiting-message` style from JS-injected `<style>` to `table.css`.

---

## Phase 3: Polish & Extended Gameplay

| # | Task | Status |
|---|------|--------|
| 3.1 | Fix bot decision logic (don't fold when check available) | DONE |
| 3.2 | Support 3+ player games | DONE (verified) |
| 3.3 | Omaha E2E support (many-cards CSS, 4 hole cards in browser) | DONE |
| 3.4 | Proper table leave/rejoin lifecycle | DONE |
| 3.5 | Add player timeout countdown UI | DONE |
| 3.6 | Implement draw/discard actions | DONE |
| 3.7 | Implement card passing | DONE |
| 3.7b | Implement expose/separate actions + card visibility | DONE |
| 3.8 | Add hand history display | DONE |
| ~~3.9~~ | ~~Mobile optimization pass~~ | Moved to Phase 7 |
| 3.10 | Stud game support (7-card stud UI, per-player up/down cards) | DONE (covered by 3.7b card visibility) |
| 3.11 | Community card layout: multi-row boards (double-board, murder, scarney, kryky) | DONE |
| 3.12 | Community card layout: branching/diamond (chowaha, omaha 321, tapiola, bidirectional) | DONE |
| 3.13 | Community card layout: grid/criss-cross (tic-tac, banco, criss-cross) | DONE |
| 3.14 | DECLARE action (hi/lo declare for 5 games) | DONE |
| 3.15 | CHOOSE action (variant selection for paradise_road_pickem) | DONE |
| 3.16 | Parametrized E2E variant smoke tests (15 variants + 8 Tier 2) | DONE |

### Task Details

**3.3 result:** Added dynamic `many-cards` CSS class to `player-cards` div when card count > 2 (activates existing 30px card styling). Created `tests/e2e/specs/omaha.spec.ts` with 4 tests: 4 hole cards visible, opponent card backs, many-cards class applied, full hand to showdown. Also fixed lobby `formatStakes()` case-sensitivity bug (Limit tables showed $0/$0). Also fixed `hand_complete` event missing `hand_number` which caused showdown display dedup to skip hand 2+.

**3.1 result:** Bot had a 30% chance to fold even when check was available (folding a free option is irrational). Fixed weights: fold=0 when check is available, fold=20 when facing a bet. Also increased bet/raise weight from 10→20 for slightly more aggressive play. Added 5 unit tests in `tests/unit/test_simple_bot.py`.

**3.5 result:** Added visual countdown timer bar on the active player's seat. All players see the timer (not just the player whose turn it is). Bar starts green, transitions to yellow at 50%, red at 25%. Timer only restarts when the current player changes (not on every state broadcast). Displays seconds remaining as text. Timer bar sits at the bottom of the `player-info` panel. Changes: `timer.js` (track `currentPlayerId`, render bar on seat), `table.js` (pass player ID, avoid restarting on same player), `table.css` (`.turn-timer-bar`/`.turn-timer-fill`/`.turn-timer-text` styles).

**3.2 result:** Engine, CSS layouts, and rendering already supported 3+ players. Three-player E2E tests exist and pass. No code changes needed — verified working.

**3.6 result:** Connected existing engine draw/discard support through all online platform layers. Added DRAWING phase and DRAW/DISCARD action types to view models. Plumbed `cards` parameter through game_routes → player_action_manager → game_orchestrator → engine (both HTTP and WebSocket paths). Frontend card selection UI: during draw phase, player's cards become clickable, selected cards glow gold and lift up, dynamic "Stand Pat" / "Draw N" button. Added `category` field to game config schema (8 families: Hold'em, Omaha, Stud, Draw, Pineapple, Dramaha, Straight, Other) and all 192 configs. Updated lobby game selector from 7 hardcoded games to 166 dynamically-loaded supported variants grouped by category with `<optgroup>`. Betting structure dropdown now filters to structures the selected game supports. 4 new SocketIO integration tests. 26 unsupported games (expose/pass/declare/separate/choose) filtered out automatically.

**3.4 result:** Implemented leave/rejoin lifecycle with these semantics:
- **Leave mid-hand:** Player is immediately folded (even out-of-turn via direct `is_active=False`), then removed from session after hand completes. Pot awarded correctly. UI shows "Leaving after this hand..." notification and "(leaving)" indicator next to player name.
- **Table drops to 1 player:** Game goes to WAITING state. Remaining player waits for new players + ready.
- **Everyone leaves:** Session deactivated (`is_active=False`). Next join creates fresh session.
- **Disconnect vs Leave:** Intentional leave = immediate fold, no grace period. Network disconnect = 30s reconnect window (existing `disconnect_manager.py` behavior preserved).
- Key files: `game_orchestrator.py` (`pending_leaves`, `mark_player_leaving()`, `process_pending_leaves()`), `websocket_manager.py` (deferred leave handler, `player_leaving` event, stale session cleanup), `player_action_manager.py` (post-hand pending leave processing).
- 4 new SocketIO integration tests: mid-hand leave awards pot, no-hand leave removes immediately, both-leave deactivates session, disconnect behavior preserved.

**3.7 result:** Connected existing engine card passing support through all online platform layers. Added `ActionType.PASS` to view models. Mapped `PlayerAction.PASS` in `GameStateManager`. Added PASS action option creation, card validation (requires exactly N cards), and broadcast message in `PlayerActionManager`. Frontend reuses the existing draw/discard card selection UI — during pass phase, cards become clickable with "Select card(s) to pass" label and "Pass N" submit button. Added `pass_the_pineapple` to smoke test (removed from UNSUPPORTED_GAMES, now 167 supported games). 2 new SocketIO integration tests (3-player pass phase detection, full hand to showdown). 25 unsupported games remaining (expose/declare/separate/choose).

**3.7b result:** Connected engine EXPOSE and SEPARATE actions through all online platform layers. Three-part implementation:
1. **Card visibility infrastructure:** New `_get_player_cards_with_visibility()` method sends per-card face-up/face-down info to opponents. Cards array now supports `null` entries (face-down) alongside card strings (face-up), enabling mixed visibility for stud and post-expose games. Frontend `renderPlayerCards()` renders `null` as card backs.
2. **EXPOSE action:** Added `ActionType.EXPOSE`, action option creation (min/max cards), card count validation, broadcast messages. Frontend reuses draw/discard card selection UI with expose-specific labels. Smoke test handler selects face-down cards.
3. **SEPARATE action:** Added `ActionType.SEPARATE` with `metadata` field on `ActionOption` (carries subset names/counts from `game.current_separate_config`). New `_renderSeparateControls()` UI with sequential subset assignment: cards fill current subset, auto-advance to next, color-coded by subset (blue/green/orange). Post-separation display groups cards by subset with labels. Added `card_subsets` field to `PlayerView`.
- 19 newly-supported games (from 167 → 186 supported, 6 remaining need DECLARE/CHOOSE): 7_card_flip, 7_card_flip_8, kentrel, showmaha, showmaha_8, studaha, tahoe_pitch_roll, mexican_poker (xfail - chip bug), 3_hand_hold_em, 3_hand_hold_em_8, 5_card_shodugi, 6_card_shodugi, cowpie, crazy_sohe, double_hold_em, lazy_sohe, sheshe, sohe, sohe_311.
- 2 new SocketIO integration tests (showmaha expose, double_hold_em separate).
- Key files: `game_state_view.py` (EXPOSE/SEPARATE ActionTypes, metadata, card_subsets), `game_state_manager.py` (visibility method, subset metadata, card_subsets population), `player_action_manager.py` (action options, validation, broadcast), `table.js` (mixed visibility, expose UI, separate UI, subset display), `table.css` (subset colors/labels).

**3.6 addendum (community card layout):** Replaced hardcoded 5-slot Hold'em community card display with data-driven layout system. Backend auto-infers layout type (`linear` or `none`) from game config gameplay steps. `_get_community_cards()` now returns structured `{layout: {type}, cards: {subset: [...]}}` format. Frontend `renderCommunityCards()` dynamically creates card slots based on layout. Draw games hide community area entirely. ~160 games work with auto-inferred linear layout. Future phases need explicit `communityCardLayout` configs for multi-row (6 games), branching (9 games), grid (5 games), criss-cross (4 games). See plan file for details.

**3.11 result:** Added `communityCardLayout` field to 12 game configs (double-board x4, murder, oklahoma, italian_poker, scarney x4, kryky). Implemented `_renderMultiRowLayout()` in table.js — renders labeled horizontal rows stacked vertically, one per board. Added `.board-row` / `.board-row-label` CSS.

**3.12 result:** Added `communityCardLayout` field to 8 game configs (chowaha x2, omaha_321 x3, tapiola_holdem, bidirectional_chowaha x2). Implemented `_renderBranchingLayout()` in table.js — renders rows top-to-bottom with centered subset groups (3 flops → 2 turns → 1 river). Added `.branching-row` / `.subset-group` / `.subset-group-label` CSS.

**3.13 result:** Added `communityCardLayout` field to 7 game configs (tic_tac_holdem, criss_cross x4, banco x2). Implemented `_renderGridLayout()` in table.js — uses CSS Grid to position cards in 2D. Supports both array-based cells (intersection of subsets, e.g., `["Row1","Col1"]`) and string-based cells (single subset, e.g., `"Flop 1.1"`). Added `.grid-layout` / `.grid-cell` CSS.

**3.14 result:** Connected engine DECLARE action through online platform. Added `GamePhase.DECLARING` and `ActionType.DECLARE` to view models. Maps to `DRAWING` engine state with `current_declare_config`. Frontend renders declare buttons (High/Low/Both) from metadata options. `declaration_data` passed through game_routes → player_action_manager → game_orchestrator → engine. 5 declare games now playable: 7_card_stud_hilo_declare, straight_declare, straight_7card_declare, straight_9card_declare, italian_poker.

**3.15 result:** Connected engine CHOOSE action through online platform. Added `ActionType.CHOOSE` to view models. CHOOSE step uses DEALING state with current_player set — fixed auto-advance loops in player_action_manager and websocket_manager to stop when DEALING has a current_player (needs input). Frontend renders variant buttons from metadata options. Fixed tuple unpacking for 4-element CHOOSE tuples. Fixed showdown guard for empty best_hand_configs. 1 game now playable: paradise_road_pickem.

**Net result of 3.11-3.15:** All 192 game configs now supported (0 unsupported, 0 xfails). 384 smoke tests pass. `UNSUPPORTED_ACTIONS` in table_manager.py emptied. 27 game configs got `communityCardLayout` fields.

**3.16 result:** Built parametrized Playwright E2E tests covering 15 representative game variants and 8 Tier 2 UI verification tests. Expanded E2E suite from 26 tests (4 spec files) to 57 tests (9 spec files).
- New spec files: `variant-smoke.spec.ts` (15 tests), `draw-actions.spec.ts` (4 tests), `special-actions.spec.ts` (4 tests)
- New helpers: `variant-data.ts` (variant configs), extended `game-helpers.ts` (`playHandPassively`, `performPassiveAction`, `getActivePlayer`), extended `table-helpers.ts` (Limit stakes, `isMyAction`, `getGamePhase`)
- Variant coverage: Hold'em, Omaha (NL/PL), 7-Card Stud (bring-in), 5-Card Draw, Badugi (3-draw), Crazy Pineapple (discard), Showmaha (expose), SOHE (separate), Straight Declare, Paradise Road Pick'em (choose), Double Board Hold'em (multi-row), Chowaha (branching), Tic-Tac Hold'em (grid), Six Plus (short deck)
- Tier 2 verifies draw controls (stand pat, selectable cards, multi-round draw, forced discard), declare buttons, expose phase, separate subsets, choose buttons
- Fixes: bring-in serialization pipeline, DOM-detach resilience in action handlers, store-based completion detection

**3.8 result:** Hand history feature. Backend: `_save_hand_to_database()` in PlayerActionManager saves completed hands to GameHistory model (players, actions, results, variant, stakes). API: `GET /api/games/tables/<id>/hand-history` returns last N hands. Frontend: "History" button in Game Info section opens modal with hand list. Each hand shows hand #, variant, pot total, winners, timestamp. Click to expand details (players, pot breakdown, winning hands). In-session hands captured from `hand_complete` events for immediate availability before DB query.

**Phase 3 complete.** All items done except mobile (moved to Phase 7).

---

## Phase 4: Production Readiness

| # | Task | Status |
|---|------|--------|
| 4.1 | Unify timeout systems (action, disconnect, ready) | DONE |
| 4.2 | Make hardcoded constants configurable | DONE |
| 4.3 | Remove debug print statements from routes | DONE |
| 4.3b | Review and reduce core engine logging (excessive debug logs accumulated over time) | DONE |
| 4.4 | Sync game engine state with database after each hand | TODO |
| 4.5 | Add rate limiting | TODO |
| 4.6 | Admin interface | TODO |

### Task Details

**4.1 result:** Unified all timeout/duration constants into `config.py` with env-var overrides: `ACTION_TIMEOUT_ENABLED`, `ACTION_TIMEOUT_SECONDS` (30s), `DISCONNECT_AUTO_FOLD_SECONDS` (30s), `DISCONNECT_REMOVAL_MINUTES` (10m), `TABLE_INACTIVE_TIMEOUT` (30m). `disconnect_manager.py`, `player_action_manager.py`, and `game_state_manager.py` all read from Flask config instead of hardcoded values.

**4.2 result:** Made remaining hardcoded constants configurable via env vars in `config.py`:
- Auth sessions: `SESSION_TIMEOUT_HOURS` (24), `REMEMBER_ME_DAYS` (30), `RESET_TOKEN_EXPIRY_HOURS` (1) — `auth_service.py` class constants removed, now reads `current_app.config.get()` with safe defaults.
- Cleanup routes: `game_routes.py` and `table_routes.py` cleanup endpoints now fall back to `TABLE_INACTIVE_TIMEOUT` from config instead of hardcoded `30`.
- Time to act: `game_state_manager.py` `_get_time_to_act()` reads `ACTION_TIMEOUT_SECONDS` from Flask config.
- Hand history: `HAND_HISTORY_DEFAULT_LIMIT` (20), `HAND_HISTORY_MAX_LIMIT` (100) — `game_routes.py` hand history endpoint reads from config.
- **Not changed (intentionally):** Bot weights (demo-only), action history buffer (internal), min-player constants (game rules).

---

## Phase 5: Game Engine Validation

Goal: Systematically verify that all JSON config features work and establish a workflow
for adding new variants. See `docs/GAME_VALIDATION.md` for full details.

| # | Task | Key Files | Status |
|---|------|-----------|--------|
| 5.1 | Create parametrized smoke test for all 192 variants | `tests/game/` | DONE |
| 5.1b | Migrate inline config tests to file-based loading | `tests/game/` | DONE |
| 5.2 | Add tests for rare-feature games (roll_die, choose, remove) | `tests/game/` | TODO |
| 5.3 | Implement `all_exposed`/`any_exposed`/`none_exposed` conditions | `game.py:531` | TODO |
| 5.4 | Implement `separate.hand_comparison` if needed | `player_action_handler.py` | TODO |
| 5.5 | Build "can this game be implemented?" assessment skill | `.claude/` | TODO |
| 5.6 | Build "implement new game variant" skill | `.claude/` | TODO |
| 5.7 | Fix known engine bugs (13 games, see STATUS.md) | `showdown_manager.py`, `evaluator.py` | DONE |

**5.1 result:** `tests/game/test_all_variants_smoke.py` — parametrized smoke test for all 192 configs.
Two test functions: `test_variant_config_loads` (all 192 parse correctly) and `test_variant_loads_and_plays`
(all 192 games play a hand to completion passively). 0 unsupported, 0 xfail. Total: 384 passed.

**5.1b result:** Migrated 12 test files from inline JSON game configs to `load_rules_from_file()`.
Removed 1,307 lines of duplicated config data. All tests pass with file-based loading.

**5.7 result:** All 13 engine bugs fixed. Zero xfails remaining. Key fixes:
- `showdown_manager.py`: List handling for holeCards/communityCards in odd-chip logic (2 games)
- `bringin.py`: Fallback to generic N-card eval types for exotic bring-in evaluations (5 games)
- `table.py`: Combinatorial best-of-N card selection when visible cards exceed evaluator hand size (5 games)
- `omaha_321_hi_hi.json`: Config name mismatch fix (1 game)
- `one_mans_trash.json`: communityCards 5→3, smoke test REPLACE_COMMUNITY handler (1 game)
- `showdown_manager.py`: `_award_special_pot()` now calls `betting.award_pots()` to transfer chips (4 games)

**5.5-5.6 details:** Claude Code skills that:
- 5.5: Given a game description URL, analyze rules and determine if implementable with
  JSON-only or needs code changes. Check against the feature matrix.
- 5.6: Walk through implementing a new variant - create config, write test, run test.
  For code-change variants, identify what engine changes are needed.

---

## Phase 6: Pagat.com Variant Expansion

Goal: Expand game library based on cross-reference with Pagat.com poker variants.
See `docs/PAGAT_CROSS_REFERENCE.md` for the full analysis (352 Pagat variants vs our 192 configs).

### 6.1 Config-Only New Games (~38 games, no engine changes needed)

These games use existing engine features and only need a new JSON config file.

| # | Task | Status |
|---|------|--------|
| 6.1.1 | Tahoe / Wichita Hold'em (3 hole cards, use 2) | TODO |
| 6.1.2 | Iron Cross (community in + shape) | TODO |
| 6.1.3 | Low Chicago (lowest spade wins half) | TODO |
| 6.1.4 | 5-Card Stud Hi-Lo | TODO |
| 6.1.5 | Royal Hold'em (T-A only, short deck) | TODO |
| 6.1.6 | Sviten Special (Scandinavian Dramaha variant) | TODO |
| 6.1.7 | 7-Card Draw | TODO |
| 6.1.8 | Double Draw Lowball (2-draw variant) | TODO |
| 6.1.9 | Blind Hold'em / Blind Omaha (all face-down community) | TODO |
| 6.1.10 | Round the World (Cincinnati variant) | TODO |
| 6.1.11 | Remaining ~28 config-only games from Pagat analysis | TODO |

### 6.2 New Engine Features

Features prioritized by casino relevance and games unlocked. Each unlocks multiple new variants.

| # | Feature | Games Unlocked | Casino Relevance | Difficulty | Status |
|---|---------|---------------|-----------------|------------|--------|
| 6.2.1 | Mixed Game Rotation (HORSE, 8 Game Mix, Dealer's Choice) | ~10 | Very High | Medium | TODO |
| 6.2.2 | Buy Your Card (pay chips to acquire/replace cards) | ~19 | Medium | Medium-Hard | TODO |
| 6.2.3 | Dynamic Wild Cards (event-triggered wild changes) | ~12 | Medium | Hard | TODO |
| 6.2.4 | Enhanced Pass Mechanics (multi-round, accept/reject) | ~8 | Low-Medium | Easy-Medium | TODO |
| 6.2.5 | No Peek Mechanic (blind card reveal game mode) | ~4 | Low | Hard | TODO |
| 6.2.6 | Inverted Visibility / Indian Poker (cards visible to opponents only) | ~2 | Very Low | Medium | TODO |

**6.2.1 details:** Orchestration layer above Game that rotates through configs (e.g., HORSE = Hold'em → Omaha 8 → Razz → 7-Stud → 7-Stud 8). Handles blind/ante transitions between variants. All individual games already work.

**6.2.2 details:** New `PlayerAction.BUY` action. Config schema: `{"buy": {"cost": "fixed", "amount": 50, "trigger": "rank", "ranks": ["3"]}}`. Fixed-cost buys are easiest; auction variants need bidding sub-rounds.

**6.2.3 details:** Wild cards currently static (set at game start). Need event hooks on card deals, per-player wild tracking ("low hole wild"), re-evaluation when wilds change. Config: `{"wildCardRule": {"type": "follow", "trigger": "queen"}}`.

**6.2.4 details:** Our PASS action exists but may need: configurable pass count per round, multi-round sequences (pass 3→2→1), accept/reject mechanics, pass to specific player.

**6.2.5 details:** Completely different game flow — all cards dealt face down, sequential reveal loop with "beat or fold". Needs new step type `{"nopeek": {"cards": 7}}`.

**6.2.6 details:** New `Visibility.FACE_OUT` enum — cards visible to all OTHER players but hidden from owner. `GameStateManager` flips visibility logic for this type.

### 6.3 Pagat URL Documentation (DONE)

| # | Task | Status |
|---|------|--------|
| 6.3.1 | Add Pagat URLs to 42 matching game configs | DONE |
| 6.3.2 | Create Pagat cross-reference analysis document | DONE |

**6.3.1 result:** Added Pagat.com URLs as reference objects to 42 game config JSON files. 45 total matches (3 already had Pagat refs: kryky, one_mans_trash, texas_reach_around). Remaining 147 configs have no Pagat match (community-invented or hi-lo variants of games Pagat only covers in high-only form).

**6.3.2 result:** `docs/PAGAT_CROSS_REFERENCE.md` — 515-line analysis with three sections: (1) Games we support with Pagat matches (45), (2) Pagat games we don't support categorized by feasibility (~38 config-only, ~47 need features, ~57 out of scope), (3) Missing features summary prioritized by casino relevance and games unlocked.

---

## Phase 7: Mobile Optimization

Goal: Make the app fully playable on phones and tablets. This is a large effort touching layout, controls, and touch interactions.

| # | Task | Status |
|---|------|--------|
| 7.1 | Audit table layout on mobile viewports (phone portrait/landscape, tablet) | TODO |
| 7.2 | Fix card/seat sizing and positioning for small screens | TODO |
| 7.3 | Touch-friendly action buttons (sizing, spacing, tap targets) | TODO |
| 7.4 | Touch-friendly bet slider and card selection (draw/discard/expose/separate) | TODO |
| 7.5 | Mobile chat panel (slide-out or collapsible) | TODO |
| 7.6 | Community card layout responsiveness (multi-row, branching, grid on small screens) | TODO |
| 7.7 | Mobile lobby (table list, create table, join flow) | TODO |
| 7.8 | Orientation handling and viewport meta tuning | TODO |

---

## Open Bugs from Earlier Testing

These are bugs found during `.kiro` testing sessions that may or may not still be relevant. Verify before working on them.

| Bug | Priority | Description | Status |
|-----|----------|-------------|--------|
| T001 | High | Private table join with invite code fails | Fixed (buy-in/seat now passed in WS handler) |
| T002 | High | Buy-in amount not applied correctly (uses minimum) | Fixed (WS handlers now read buy_in_amount from client) |
| T003 | Medium | Seat selection ignored during join | Fixed (WS handlers now pass seat_number) |
| T004 | Medium | Chat messages area not visible | Fixed (added .collapsed CSS, fixed mobile panel toggle) |
| T005 | Critical | Insufficient bankroll check not working | Fixed (WS handlers now validate bankroll before join) |
| T006 | Medium | Lobby shows 0 tables after redirect | Fixed (loadTables() added to socket connect handler) |
| G006 | High | 404 for available-actions API endpoint | Not a bug (route works, url_prefix override is correct) |
| T007 | Medium | Gameplay table shape (oval) doesn't match seat selection screen (rounded rectangle) — should use consistent rounded-rectangle shape | Fixed (border-radius: 50% → 250px) |
| T008 | Critical | Deck not shuffled between hands — same cards dealt every hand. `start_hand()` must shuffle by default | Fixed |
| T009 | Low | Add debug option for fixed/unseeded deck (useful for testing specific scenarios). Could be server flag, config option, or admin toggle. Similar to test fixtures in `tests/game/` | Open |
