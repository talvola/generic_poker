# Testing Issues Log

This document tracks issues discovered during manual and automated testing of completed features.

## Testing Session: 2026-01-21 (Gameplay Testing - Phase 2)

### Test Environment
- Server: Flask development server on localhost:5000
- Browser: Playwright-controlled Chromium (2 tabs for multiplayer)
- Database: Fresh SQLite with seeded test data
- Test accounts: alice, bob (password: "password")
- Table: Texas Hold'em - Micro Stakes ($1/$2 No Limit)

### Session Summary
Testing Phase 1 (Login/Join) completed successfully. Phase 2 (Ready/Hand Start) revealed critical bugs preventing gameplay.

**Bugs Fixed This Session:**
- #G001 - Card Rendering: FIXED - Added `parseCardString()` function to handle server format
- #G002 - Action Panel: FIXED - Fixed game_phase detection, API call override removed (uses WebSocket data only)
- #G004 - Pot Display: FIXED - Updated `_get_pot_info()` to include current_bets (blinds)
- #G005 - Player Join Updates: FIXED - Added `_generate_waiting_state()` for pre-session player list
- #G007 - Fold Status Persistence: FIXED - Added `player.is_active = True` reset in `table.py:clear_hands()`
- Backend: Fixed `ActionResult.message` attribute error in game_orchestrator.py
- Backend: Fixed call action amount handling (case-sensitivity issue)
- Frontend: Fixed timer going negative (clear existing interval before starting new one)

**Verified Working:**
- Players can see their hole cards (A♠, Q♠ format)
- Action buttons appear (Fold, Call $2, Raise)
- Call action works and turn advances to next player
- Pot displays blind amounts correctly ($3 for $1/$2 blinds)
- Timer no longer goes negative
- Fold status resets correctly between hands (core engine verified)
- Full hand plays through to showdown (core engine verified)

---

## Testing Session: 2026-01-21 (Initial)

### Test Environment
- Server: Flask development server on localhost:5000
- Browser: Playwright-controlled Chromium
- Database: Fresh SQLite with seeded test data
- Test accounts: testuser, alice, bob, charlie, diana (password: "password")

---

## Issues Found (Gameplay Testing Session)

### Issue #G001 - Player's Own Hole Cards Show as Card Backs
- **Priority**: Critical
- **Status**: FIXED
- **Feature**: Card Rendering (Task 8.3)
- **Description**: When a hand starts, players see their own hole cards as card backs (🂠) instead of actual card faces. This makes gameplay impossible as players cannot see their own cards.
- **Steps to Reproduce**:
  1. Join table with two players (alice, bob)
  2. Both click Ready
  3. Hand starts automatically
  4. Observe that your own cards show as blue card backs
- **Expected Behavior**: Player's own hole cards should display face-up (e.g., A♠, Q♠)
- **Actual Behavior**: Cards show as 🂠 (card back emoji/symbol)
- **Server Data**: Server correctly sends card data (e.g., `"cards":["As","Qs"]`)
- **Root Cause**: Frontend JavaScript not rendering card data correctly - possibly wrong path or field name
- **Related**: Bug #006 was marked resolved but issue persists

### Issue #G002 - Action Panel Not Appearing
- **Priority**: Critical
- **Status**: PARTIALLY FIXED (Action buttons appear, but API override issue remains)
- **Feature**: Betting Actions (Task 8.3)
- **Description**: When it's a player's turn, no action buttons (Fold/Call/Raise) appear despite debug info showing valid actions are available.
- **Steps to Reproduce**:
  1. Start a hand with two players
  2. Observe debug panel shows "My Turn: Yes" and valid actions
  3. No Fold/Call/Raise buttons visible anywhere on screen
- **Expected Behavior**: Action panel with Fold, Call ($2), Raise buttons should appear
- **Actual Behavior**: No action buttons visible; only Ready button panel shows
- **Server Data**: Server sends valid_actions: `[{"action_type":"fold"...}, {"action_type":"call", "min_amount":2...}, {"action_type":"raise"...}]`
- **Console Error**: `Failed to load available actions: 404 NOT FOUND` for `/api/table/{id}/available-actions`

### Issue #G003 - Ready Panel Persists During Active Hand
- **Priority**: Medium
- **Status**: Open
- **Feature**: Game State UI (Task 8.2)
- **Description**: The "Ready" panel with player checkboxes continues to display even after a hand has started, showing "0/2 players ready" during active gameplay.
- **Steps to Reproduce**:
  1. Both players click Ready
  2. Hand starts ("All players ready - starting hand...")
  3. Ready panel still visible with all players showing as not ready
- **Expected Behavior**: Ready panel should be hidden during active hand
- **Actual Behavior**: Ready panel shows throughout the hand with incorrect status

### Issue #G004 - Pot Not Reflecting Posted Blinds
- **Priority**: High
- **Status**: Open
- **Feature**: Pot Display (Task 8.4)
- **Description**: After blinds are posted, the pot display still shows $0 instead of the blind amounts ($3 for $1/$2).
- **Steps to Reproduce**:
  1. Start a hand at $1/$2 table
  2. Observe pot display shows $0
  3. Server logs show blinds were processed internally
- **Expected Behavior**: Pot should show $3 (SB $1 + BB $2)
- **Actual Behavior**: Pot shows $0
- **Server Data**: `"pot_info":{"main_pot":0, "total_pot":0}` - serialization issue

### Issue #G005 - Player Join Not Rendering for Other Players
- **Priority**: High
- **Status**: FIXED
- **Feature**: Real-time Updates (Task 5.1)
- **Description**: When a second player joins the table, their seat doesn't update on the first player's view. Shows "Click to join" instead of the player's info.
- **Steps to Reproduce**:
  1. Alice joins table (sees herself in Seat 1)
  2. Bob joins table in a second browser
  3. Alice's view still shows Seat 2 as "Click to join"
- **Expected Behavior**: Alice should see Bob appear in Seat 2 immediately
- **Actual Behavior**: Seat 2 shows empty on Alice's view
- **Console Error**: `TypeError: Cannot read properties of undefined (reading 'username')` in handlePlayerJoin
- **Root Cause**: `GameStateManager.generate_game_state_view()` returned `None` when no game session existed (before hand starts). This prevented existing players from receiving updated player lists when new players joined.
- **Fix**: Added `_generate_waiting_state()` method in GameStateManager that returns a valid GameStateView with player list and game_phase="waiting" when no session exists but players are at the table.

### Issue #G006 - 404 Error for Available Actions API
- **Priority**: High
- **Status**: Open
- **Feature**: Action API (Task 8.3)
- **Description**: The frontend attempts to fetch available actions from `/api/table/{id}/available-actions` but this endpoint returns 404.
- **Steps to Reproduce**:
  1. Start a hand
  2. Observe browser console
  3. See repeated 404 errors for available-actions endpoint
- **Expected Behavior**: Endpoint should exist and return valid actions
- **Actual Behavior**: 404 NOT FOUND, followed by JSON parse error
- **Console Error**: `Failed to load resource: 404` then `SyntaxError: Unexpected token '<'`

### Issue #G007 - Fold Status Persists Across Hands
- **Priority**: Critical
- **Status**: FIXED
- **Feature**: Game State Management (Task 8.2)
- **Description**: When a player folds in one hand, their `is_active` status remains `False` in subsequent hands, preventing them from being dealt cards or taking actions.
- **Steps to Reproduce**:
  1. Start a hand with two players
  2. Have one player fold (or time out, triggering auto-fold)
  3. Start a new hand
  4. Observe the player who folded still shows "FOLDED" status
  5. Player is not dealt cards and cannot act
- **Expected Behavior**: Fold status should reset at the start of each new hand
- **Actual Behavior**: Player's `is_active=False` persists, making them unable to participate
- **Root Cause**: The `Table.clear_hands()` method reset cards and deck but did not reset `player.is_active = True`
- **Fix**: Added `player.is_active = True` in `src/generic_poker/game/table.py:clear_hands()` method
- **Verification**: Core engine test confirms players can fold in hand 1, then participate fully in hand 2

### Issue #G008 - Game Not Auto-Progressing After Betting Round
- **Priority**: Critical
- **Status**: FIXED
- **Feature**: Game Flow (Task 8.3)
- **Description**: After preflop betting completes (SB calls, BB checks), the game does not auto-progress to deal the flop. Players can keep checking indefinitely at preflop.
- **Steps to Reproduce**:
  1. Start a 2-player hand at Texas Hold'em table
  2. Alice (SB/BTN) calls the big blind ($2)
  3. Bob (BB) checks
  4. Game should deal flop, but instead allows more checks at preflop
- **Expected Behavior**: After preflop betting round completes, flop should be dealt automatically
- **Actual Behavior**: Game stays at preflop phase, allowing unlimited checks
- **Root Cause**: When online games use `auto_progress=False`, the game engine doesn't automatically advance to the next step after a betting round completes. The WebSocket handler and PlayerActionManager weren't checking `result.advance_step` and calling `game._next_step()` to manually advance.
- **Fix**: Added logic in both `websocket_manager.py` and `player_action_manager.py` to:
  1. Check if `result.advance_step` is True after processing a player action
  2. Call `game._next_step()` to advance the game
  3. Continue advancing through DEALING states (which don't require player input) until we're back in a state that needs player input or the game completes
- **Files Changed**:
  - `src/online_poker/services/websocket_manager.py` - Added advancement logic in `handle_player_action`
  - `src/online_poker/services/player_action_manager.py` - Added advancement logic in `process_player_action`
- **Tests Added**: `tests/integration/test_gameplay_integration.py::TestPreflopBettingAndProgression` with 3 tests verifying:
  - Preflop betting completes correctly and flop is dealt
  - Pot and stack amounts are tracked correctly
  - `advance_step` flag is returned correctly when betting round completes
- **Verification**: All 19 integration gameplay tests pass

---

## Multi-Player Testing Summary (2026-01-21)

### Testing Approach
Successfully implemented multi-player browser testing using Playwright's separate browser contexts (`browser.newContext()`). Each context has isolated cookie storage, allowing two different users to be logged in simultaneously.

### What Works
- Separate browser contexts for isolated sessions
- Login/logout for multiple users in parallel
- Navigating to same table from different contexts
- Getting user IDs from game state API (`current_user.id`)
- Sending actions via API with correct authentication cookies
- Actions are processed and state updates correctly
- Pot updates reflect actions (blinds + calls)

### API Field Names
- Actions endpoint returns `action_type` not `type`
- Amount field is `default_amount` or `min_amount`
- Game phase is `game_phase` not `phase`
- Pot is `pot_info.total_pot`

### Test Code Pattern
```javascript
const browser = page.context().browser();
const bobContext = await browser.newContext();  // Isolated cookies
const bobPage = await bobContext.newPage();
// Each page can login as different user
// Use page.evaluate() to make authenticated API calls
```

---

## Issues Found (Initial Session)

### Issue #T001 - Private Table Join with Invite Code Fails
- **Priority**: High
- **Status**: Open
- **Feature**: Private Table Support (Task 3.2)
- **Description**: Attempting to join a private table using a valid invite code shows error "Invite code required for private table" even when the code is entered correctly.
- **Steps to Reproduce**:
  1. Log in as any user
  2. Click "Join Private Table" button in lobby
  3. Enter valid invite code (e.g., "W0MPVC11" from seed data)
  4. Clear password field (table has no password)
  5. Click "Join Table"
- **Expected Behavior**: User should be able to join the private table
- **Actual Behavior**: Error message "Invite code required for private table" appears
- **Possible Causes**:
  - Invite code validation may be case-sensitive
  - Form submission may not be sending the invite code correctly
  - API endpoint may have a validation bug

### Issue #T002 - Buy-in Amount Not Applied Correctly
- **Priority**: High
- **Status**: Open
- **Feature**: Table Joining (Task 4.2)
- **Description**: When joining a table, the selected buy-in amount is not applied. User selected $80 buy-in but only $40 was deducted from bankroll and added to table stack.
- **Steps to Reproduce**:
  1. Log in as testuser (bankroll: $800)
  2. Join "Test Hold'em Table"
  3. Buy-in modal shows default $80 (range $40-$200)
  4. Click "Join Table" without changing amount
- **Expected Behavior**: $80 should be deducted from bankroll, player should have $80 stack
- **Actual Behavior**: Only $40 deducted (bankroll: $760), stack shows $40
- **Notes**: The minimum buy-in ($40) appears to be applied regardless of selected amount

### Issue #T003 - Seat Selection Ignored During Join
- **Priority**: Medium
- **Status**: Open
- **Feature**: Seat Assignment (Task 8.1)
- **Description**: When manually selecting a seat during table join, the selection is ignored and player is assigned to Seat 1 instead.
- **Steps to Reproduce**:
  1. Join a table via lobby
  2. In the join modal, click "Seat 3" to select it (shows checkmark)
  3. Click "Join Table"
- **Expected Behavior**: Player should be seated in Seat 3
- **Actual Behavior**: Player is seated in Seat 1
- **Notes**: Auto-assign radio button was not selected; manual seat selection appeared to work (showed checkmark) but was ignored

### Issue #T004 - Chat Messages Area Not Visible
- **Priority**: Medium
- **Status**: Open
- **Feature**: Chat System (Task 5.3)
- **Description**: The table chat panel does not display a messages area. Only the header, toggle button, input field, and send button are visible. Sent messages are not displayed.
- **Steps to Reproduce**:
  1. Join a table
  2. Type a message in the chat input
  3. Click "Send"
- **Expected Behavior**: Message should appear in a chat messages area
- **Actual Behavior**: No messages area is visible; sent messages disappear
- **Notes**: The chat container may be missing the messages display element or it may have CSS issues (height: 0, display: none, etc.)

### Issue #T005 - Insufficient Bankroll Check Not Working
- **Priority**: Critical
- **Status**: Open
- **Feature**: Table Joining (Task 4.2)
- **Description**: Users with insufficient bankroll can still join tables. The bankroll validation check in the API does not prevent joining.
- **Steps to Reproduce**:
  1. Create user with bankroll of $10
  2. Try to join table with minimum buy-in of $40
  3. Join succeeds instead of failing
- **Expected Behavior**: API should return 400 error "Insufficient bankroll"
- **Actual Behavior**: API returns 200 OK and allows the join
- **Automated Test**: `tests/integration/test_table_join_integration.py::TestBuyInHandling::test_insufficient_bankroll_rejected`
- **Root Cause**: The `TableAccessManager.join_table()` method may not be properly checking bankroll or the check happens after the response is returned

### Issue #T006 - Lobby Shows 0 Tables After Redirect
- **Priority**: Medium
- **Status**: Open
- **Feature**: Lobby Display (Task 7.1)
- **Description**: After certain navigation actions, the lobby shows "0 tables found" even when tables exist. Refreshing or reconnecting resolves the issue.
- **Steps to Reproduce**:
  1. Log in as alice in second browser tab
  2. Try to navigate directly to a table URL
  3. Get redirected back to lobby
  4. Lobby shows "0 tables found"
- **Expected Behavior**: Lobby should display all active tables
- **Actual Behavior**: Lobby shows empty state until refresh
- **Notes**: May be related to WebSocket connection state or table list not being refreshed on page load

---

## Features Working Correctly

### Authentication (Tasks 2.1, 2.2)
- [x] Login with username/password works
- [x] Session persists across page navigation
- [x] User bankroll displayed correctly after login
- [x] Logout link available when logged in
- [x] Login form pre-fills credentials (browser autofill)

### Table Creation (Task 3.1)
- [x] Create table modal opens correctly
- [x] All game variants available (Texas Hold'em, Omaha, etc.)
- [x] Betting structure selection (No Limit, Pot Limit, Limit)
- [x] Max players configuration
- [x] Stakes configuration (small/big blind)
- [x] Private table checkbox
- [x] Allow bots checkbox
- [x] Table appears in lobby after creation
- [x] Table shows correct configuration details

### Lobby Display (Task 7.1)
- [x] Tables displayed with correct information
- [x] Filter dropdowns functional
- [x] Join/Spectate/Details buttons visible
- [x] Table status (Waiting/Playing) accurate
- [x] Player count accurate
- [x] Private tables hidden from public listing

### Ready System (Task 5.1 - WebSocket)
- [x] Ready button toggles correctly
- [x] Ready count updates ("0/1 players ready" -> "1/1 players ready")
- [x] Ready indicator shows checkmark for ready players
- [x] "Need at least 2 players to start" message displayed

### Table Interface (Task 7.2)
- [x] Table layout renders correctly
- [x] Empty seats show "Click to join"
- [x] Player seat shows username, stack, "You" indicator
- [x] Dealer button (D) displayed
- [x] Pot amount displayed
- [x] Community cards area visible
- [x] Leave Table button available
- [x] Back to Lobby link works
- [x] Debug info panel available
- [x] Game info panel shows hand number, players, time bank

### Bankroll Management (Task 2.3)
- [x] Bankroll deducted on table join
- [x] Bankroll displayed correctly in header

---

## Test Coverage Summary

| Feature Area | Status | Issues |
|--------------|--------|--------|
| Authentication | Pass | None |
| Table Creation | Pass | None |
| Lobby Display | Partial | #T006 |
| Private Tables | Fail | #T001 |
| Table Joining | Partial | #T002, #T003, #T005 |
| Bankroll Validation | Fail | #T005 (Critical) |
| Seat Selection | Fail | #T003 |
| Ready System | Pass | None |
| Chat System | Fail | #T004 |
| Spectator Mode | Pass | None |
| Card Rendering | Pass | #G001 (FIXED) |
| Action Panel | Pass | #G002 (FIXED) |
| Pot Display | Pass | #G004 (FIXED) |
| Real-time Updates | Pass | #G005 (FIXED) |
| **Game Flow** | **Partial** | Needs verification |
| **Betting Actions** | **Partial** | Call works, needs full test |
| **Showdown** | **Not Tested** | Needs testing |

## Automated Test Results

Integration tests created: `tests/integration/test_table_join_integration.py`

| Test Class | Tests | Passed | Failed |
|------------|-------|--------|--------|
| TestPublicTableJoining | 4 | 4 | 0 |
| TestPrivateTableJoining | 4 | 3 | 1 |
| TestBuyInHandling | 2 | 1 | 1 |
| TestSeatSelection | 1 | 1 | 0 |
| TestTableListFiltering | 2 | 2 | 0 |
| TestSpectatorMode | 3 | 3 | 0 |
| **Total** | **16** | **14** | **2** |

### Failing Tests
1. `test_join_private_table_with_valid_invite_code` - Private table join with valid code fails
2. `test_insufficient_bankroll_rejected` - Insufficient bankroll check not enforced

---

## Recommendations

### Critical Blockers (Must Fix for Gameplay)

1. **#G001 - Card Rendering**: Players cannot see their own cards. Server sends correct data but frontend doesn't render it.
   - Check `updatePlayerCards()` function in table.js
   - Verify card data path matches server response structure

2. **#G002 - Action Panel**: No way to take betting actions. Missing `/api/table/{id}/available-actions` endpoint or wrong URL.
   - Implement missing API endpoint OR
   - Fix frontend to use WebSocket-provided valid_actions instead

3. **#G004 - Pot Display**: Blinds posted but pot shows $0. Serialization issue in GameStateManager.
   - Check `_get_pot_info()` method
   - Verify pot amounts are being read from correct game state path

### High Priority Fixes

4. **#G005 - Player Join Updates**: Other players don't appear on existing player's view.
   - Fix `handlePlayerJoin` in table.js - TypeError on undefined username
   - Ensure player data structure matches expected format

5. **#G006 - Available Actions API**: 404 error for API endpoint.
   - Either implement `/api/table/{id}/available-actions` endpoint
   - Or remove the fetch call and rely on WebSocket data

### Medium Priority Fixes

6. **#G003 - Ready Panel Visibility**: Hide during active hand
7. **#T002, #T003** - Buy-in and seat selection issues

### Testing Status

- **Phase 1 (Login/Join)**: ✅ Passed
- **Phase 2 (Ready/Start)**: ⚠️ Hand starts but cards don't display
- **Phase 3 (Pre-flop Betting)**: ❌ Blocked - no action panel
- **Phase 4-5 (Flop/Turn/River)**: ❌ Blocked
- **Phase 6 (Showdown)**: ❌ Blocked

### Next Steps

1. Fix critical rendering issues (#G001, #G002) first
2. Re-test Phase 3 once action panel works
3. Continue through remaining phases
4. Create automated E2E tests for full game flow
