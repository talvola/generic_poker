# Known Issues and Bugs

This document tracks bugs and issues discovered during testing and development that are not immediately addressed.

## Bug Tracking Format

For each bug, include:
- **Bug ID**: Unique identifier
- **Priority**: Critical/High/Medium/Low
- **Status**: Open/In Progress/Resolved
- **Description**: Clear description of the issue
- **Steps to Reproduce**: How to trigger the bug
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Related Task**: Reference to task where bug was found
- **Notes**: Additional context or workarounds

---

## Open Bugs

### Bug #001 - Bot Folding When Check Available
- **Priority**: High
- **Status**: Open
- **Description**: SimpleBot chooses to fold when check is available, which is illogical poker behavior
- **Steps to Reproduce**: 
  1. Bot player has actions ['fold', 'check', 'bet']
  2. Bot randomly selects fold action
- **Expected Behavior**: Bot should never fold when check is available (no additional cost)
- **Actual Behavior**: Bot randomly selects fold from available actions including check
- **Related Task**: Task 6 (Bot implementation - simplified version)
- **Notes**: Bot should prioritize check over fold when both are available. Current random selection doesn't consider poker logic.

### Bug #002 - Action Panel Width Changes Cause Layout Shift
- **Priority**: Medium
- **Status**: Open
- **Description**: Action panel changes width when switching between waiting message and action buttons, causing table layout to shift
- **Steps to Reproduce**: 
  1. Observe action panel with "Waiting for your turn..." message
  2. Player's turn arrives and action buttons appear
  3. Panel width changes and table shifts left
- **Expected Behavior**: Action panel should maintain consistent width regardless of content
- **Actual Behavior**: Panel resizes horizontally, causing table display to move and reposition
- **Related Task**: Task 8.3 (Display player betting choices)
- **Notes**: Likely caused by centering behavior and lack of fixed width on action panel. Affects user experience with jarring layout shifts.

### Bug #003 - Showdown Modal Blocks Table View
- **Priority**: Medium
- **Status**: Resolved
- **Description**: Showdown results displayed in modal overlay that blocked the entire screen, preventing users from seeing the table
- **Steps to Reproduce**: 
  1. Play a hand to completion (showdown)
  2. Showdown results appear in modal overlay
  3. Entire screen is blacked out, table not visible
- **Expected Behavior**: Users should be able to see the table while showdown results are displayed
- **Actual Behavior**: Modal overlay blocked entire screen with dark background
- **Related Task**: Task 8.5 (Showdown display system)
- **Resolution**: Changed showdown display from modal overlay to container below table. Results now appear in a styled container that doesn't block the table view.
- **Files Modified**: templates/table.html, static/css/table.css, static/js/table.js

### Bug #004 - Hand Continues After All But One Player Fold
- **Priority**: High
- **Status**: Resolved
- **Description**: When all players except one have folded, the hand should end immediately and award the pot to the remaining player. Instead, the game continues to deal additional cards and betting rounds.
- **Steps to Reproduce**: 
  1. Start a hand with multiple players
  2. Have all players except one fold during any betting round
  3. Observe that game continues to next dealing/betting phase instead of ending
- **Expected Behavior**: Hand should end immediately when only one player remains, pot should be awarded, and next hand should begin
- **Actual Behavior**: Game continues dealing cards and progressing through betting rounds even with only one player
- **Related Task**: Task 8.2 (Game state management and hand flow)
- **Evidence**: Log shows "All but one player folded - hand complete" but then "Processing step 5: Deal Turn" continues
- **Notes**: This is a core poker rule violation - hands must end when only one player remains
- **Root Cause**: Game engine's `auto_progress=True` was calling `_next_step()` even after fold detection set game state to COMPLETE, overriding the completion state
- **Resolution**: Modified `player_action` method in `game.py` to check `self.state != GameState.COMPLETE` before calling `_next_step()`
- **Files Modified**: src/generic_poker/game/game.py, src/web/server.py, src/online_poker/services/game_manager.py
- **Testing**: 
  - ✅ Unit test `tests/unit/test_betting_flow.py::test_all_fold_to_one` passes
  - ✅ All related betting flow tests pass (6/6 tests)
  - ✅ No regressions detected in betting manager tests
  - ✅ Fix verified to work correctly in all fold scenarios
  - ✅ Game state properly transitions to COMPLETE when only one player remains



### Bug #006 - Player's Own Cards Disappear After Actions
- **Priority**: High
- **Status**: Resolved
- **Description**: A player's own hole cards intermittently disappear and reappear after each player action (bet, check, fold, etc.), showing empty card slots instead
- **Steps to Reproduce**:
  1. Join a table and receive hole cards
  2. Observe that your cards are initially visible
  3. Make any action (bet, check) or wait for other players to act
  4. Observe that your own cards disappear, showing dotted empty card outlines
  5. Cards may reappear after subsequent actions
- **Expected Behavior**: A player's own hole cards should remain visible at all times throughout the hand
- **Actual Behavior**: Player's cards intermittently disappear after game state updates, showing empty card slots
- **Related Task**: Task 8.3.1 (Basic player card visibility)
- **Evidence**: Screenshots show test9's cards visible in first image, disappeared in second image despite being the same player
- **Root Cause**: Multiple issues in game state management and JavaScript:
  1. `_get_current_player` was checking wrong path (`session.game.table.current_player` instead of `session.game.current_player`)
  2. `_get_player_cards` was checking `player.cards` instead of `player.hand.cards`
  3. JavaScript was using `player.stack` but server sends `chip_stack`
  4. JavaScript expected seat-indexed player object but received array
  5. `current_user` was not being sent from server to client
- **Resolution**: Fixed all path references and data format mismatches between server and client
- **Files Modified**:
  - src/online_poker/services/game_state_manager.py (fixed `_get_current_player`, `_get_player_cards`)
  - src/online_poker/models/game_state_view.py (added `current_user` to output)
  - static/js/table.js (fixed property names, array-to-object conversion)


 

### Bug #009 - Unit Test Failure in GameStateManager
- **Priority**: Medium
- **Status**: Resolved
- **Description**: Unit test `test_get_valid_actions_current_player` was failing due to incorrect patching path and `self` reference in static method
- **Steps to Reproduce**: 
  1. Run `pytest tests/unit/test_game_state_manager.py::TestGameStateManager::test_get_valid_actions_current_player`
  2. Test fails with AttributeError about missing `player_action_manager` attribute
  3. After fixing patch, test fails with NameError about `self` not being defined
- **Expected Behavior**: Unit test should pass successfully
- **Actual Behavior**: Test failed with patching and static method reference errors
- **Related Task**: General code quality and testing
- **Root Cause**: 
  1. Test was patching `online_poker.services.game_state_manager.player_action_manager` but the import is done locally inside the method
  2. Static method `generate_game_state_view` was calling `self._convert_action_option` instead of `GameStateManager._convert_action_option`
- **Resolution**: 
  1. Fixed test patch path to `online_poker.services.player_action_manager.player_action_manager`
  2. Changed `self._convert_action_option` to `GameStateManager._convert_action_option` in static method
- **Files Modified**: 
  - tests/unit/test_game_state_manager.py (fixed patch path)
  - src/online_poker/services/game_state_manager.py (fixed static method reference)
- **Testing**: All 27 tests in test_game_state_manager.py now pass

### Bug #010 - Hanging Unit Test in WebSocketManager
- **Priority**: Medium
- **Status**: Resolved
- **Description**: Unit test `test_handle_table_disconnect` was hanging indefinitely and never completing
- **Steps to Reproduce**: 
  1. Run `pytest tests/unit/test_websocket_manager.py::TestWebSocketManager::test_handle_table_disconnect`
  2. Test hangs and never finishes
- **Expected Behavior**: Unit test should complete quickly and pass
- **Actual Behavior**: Test hangs indefinitely, requiring manual termination
- **Related Task**: General code quality and testing
- **Root Cause**: Test was patching incorrect import paths - it was trying to patch `PlayerSessionManager.handle_player_disconnect` but the actual code imports and calls `disconnect_manager.handle_player_disconnect`
- **Resolution**: Fixed all patch paths in websocket manager tests to match the actual imports:
  1. Changed `PlayerSessionManager.handle_player_disconnect` to `disconnect_manager.handle_player_disconnect`
  2. Updated patch paths to target the actual modules rather than non-existent nested imports
  3. Added proper mocking for all dependencies (game_orchestrator, GameStateManager)
- **Files Modified**: 
  - tests/unit/test_websocket_manager.py (fixed patch paths for disconnect and reconnect tests)
- **Testing**: All 19 tests in test_websocket_manager.py now pass quickly

---

## Resolved Bugs

### Bug #T001 - Private Table Join With Invite Code Fails
- **Priority**: High
- **Status**: Resolved
- **Description**: When joining a private table using an invite code, the join request failed with "Invalid table" error
- **Steps to Reproduce**:
  1. Create a private table
  2. Copy the invite code
  3. Click "Join Private Table" in lobby
  4. Enter the invite code
  5. Observe error "Invalid table"
- **Expected Behavior**: Should successfully join the private table
- **Actual Behavior**: Join failed with "Invalid table" error
- **Root Cause**: The `get_table_by_invite_code` method in TableManager was missing - it was referenced but never implemented
- **Resolution**: Implemented the `get_table_by_invite_code` method in TableManager to query tables by their invite code
- **Files Modified**: src/online_poker/services/table_manager.py

### Bug #T002 - Buy-in Amount Ignored, Always Uses Minimum
- **Priority**: High
- **Status**: Resolved
- **Description**: When joining a table and selecting a custom buy-in amount, the server always used the minimum buy-in instead
- **Steps to Reproduce**:
  1. Join a table with buy-in range $40-$200
  2. Set buy-in slider to $100
  3. Click Join Table
  4. Observe that player joins with $40 (minimum) instead of $100
- **Expected Behavior**: Player should join with the selected buy-in amount ($100)
- **Actual Behavior**: Player always joins with minimum buy-in ($40)
- **Root Cause**: The lobby.js was sending `buyin_amount` but the server expected `buy_in`. Additionally, the route handler was using `min_buy_in` as a fallback default
- **Resolution**: Fixed the parameter name in table_routes.py to accept `buyin_amount` from the client
- **Files Modified**: src/online_poker/routes/table_routes.py

### Bug #T003 - Seat Selection Ignored During Join
- **Priority**: Medium
- **Status**: Resolved
- **Description**: When selecting a specific seat to join at a table, the selection was ignored and player was auto-assigned
- **Steps to Reproduce**:
  1. Open join dialog for a table
  2. Click on a specific seat (e.g., Seat 5)
  3. Click Join Table
  4. Observe that player is placed in a different seat
- **Expected Behavior**: Player should be seated at the selected seat
- **Actual Behavior**: Player was auto-assigned to first available seat
- **Root Cause**: The seat selection click handler was updating the UI but not setting the form value correctly. The radio button for seat selection wasn't being properly toggled.
- **Resolution**: Fixed the seat click handler to properly set the selectedSeat value and update the radio button state
- **Files Modified**: static/js/lobby.js

### Bug #T004 - Chat Messages Not Displaying
- **Priority**: Medium
- **Status**: Resolved
- **Description**: Chat messages sent by players were not appearing in the chat area. Messages were sent but never displayed.
- **Steps to Reproduce**:
  1. Join a table
  2. Type a message in the chat input
  3. Click Send
  4. Observe that no message appears in the chat area
- **Expected Behavior**: Chat messages should appear in the chat area with username and timestamp
- **Actual Behavior**: Messages were not displayed at all
- **Root Cause**: Multiple issues found:
  1. WebSocket event name mismatch - server listened for `'send_chat'` but client emitted `'chat_message'`
  2. UUID type mismatch - ChatService expected UUID objects but received strings
  3. Spam filter pattern `^[A-Z\s!]+$` with `re.IGNORECASE` was blocking all messages
  4. JavaScript expected `data.timestamp` but server sent `created_at`
  5. User relationship not loading - UUID to string conversion needed for query
- **Resolution**: Fixed all five issues:
  1. Changed server event handler from `'send_chat'` to `'chat_message'`
  2. Added UUID conversion before calling ChatService
  3. Removed `re.IGNORECASE` from spam pattern matching
  4. Fixed JavaScript to handle both `timestamp` and `created_at` field names
  5. Fixed `to_dict()` in ChatMessage model to convert UUID to string before querying User
- **Files Modified**:
  - src/online_poker/services/websocket_manager.py (event name, UUID conversion)
  - src/online_poker/services/chat_service.py (spam filter)
  - static/js/table.js (timestamp field handling)
  - src/online_poker/models/chat.py (username lookup)

### Bug #011 - Double Card Dealing (4 Cards Instead of 2)
- **Priority**: High
- **Status**: Resolved
- **Description**: Texas Hold'em was dealing 4 cards instead of 2 to each player when starting a hand
- **Resolution**: Removed redundant `process_current_step()` call from websocket_manager.py - `_next_step()` already calls it internally
- **Files Modified**: src/online_poker/services/websocket_manager.py

### Bug #006 - Player's Own Cards Disappear After Actions
- **Priority**: High
- **Status**: Resolved
- **Description**: Player's hole cards intermittently disappeared after game state updates
- **Resolution**: Fixed multiple path reference issues in game_state_manager.py and data format mismatches in table.js
- **Files Modified**: src/online_poker/services/game_state_manager.py, src/online_poker/models/game_state_view.py, static/js/table.js

### Bug #007 - No Visual Indicator for Folded Players
- **Priority**: Medium
- **Status**: Resolved
- **Description**: When players fold, there is no visual indication in the UI to show they are no longer active in the hand
- **Resolution**: Implemented comprehensive folded player visual indicators including card mucking, visual styling, folded indicator badge, and improved game state detection
- **Files Modified**: static/js/table.js, static/css/table.css, src/online_poker/services/game_state_manager.py

### Bug #010 - Hanging Unit Test in WebSocketManager
- **Priority**: Medium
- **Status**: Resolved
- **Description**: Unit test `test_handle_table_disconnect` was hanging indefinitely and never completing
- **Resolution**: Fixed incorrect patch paths in websocket manager tests to match actual imports and dependencies
- **Files Modified**: tests/unit/test_websocket_manager.py

### Bug #011 - Double Card Dealing (4 Cards Instead of 2)
- **Priority**: High
- **Status**: Resolved
- **Description**: Texas Hold'em was dealing 4 cards instead of 2 to each player when starting a hand
- **Steps to Reproduce**:
  1. Create a Texas Hold'em table
  2. Have two players join and click Ready
  3. Observe that each player receives 4 hole cards instead of 2
- **Expected Behavior**: Each player should receive exactly 2 hole cards for Texas Hold'em
- **Actual Behavior**: Each player receives 4 cards (the deal step was being executed twice)
- **Root Cause**: In `websocket_manager.py`'s `_start_hand_when_ready` method, both `game._next_step()` and `game.process_current_step()` were being called in the advancement loop. However, `_next_step()` already calls `process_current_step()` internally, resulting in each step being processed twice.
- **Resolution**: Removed the redundant `game.process_current_step()` call from the while loop
- **Files Modified**: src/online_poker/services/websocket_manager.py (line ~906)
- **Related Code**:
  ```python
  # Before (buggy):
  while game.current_player is None and game.state != game.state.COMPLETE:
      game._next_step()
      if game.current_step >= len(game.rules.gameplay):
          break
      game.process_current_step()  # DUPLICATE - _next_step already calls this

  # After (fixed):
  while game.current_player is None and game.state != game.state.COMPLETE:
      game._next_step()  # This already calls process_current_step() internally
      if game.current_step >= len(game.rules.gameplay):
          break
  ```

### Bug #005 - Showdown Chat Messages Loop Infinitely
- **Priority**: High
- **Status**: Resolved
- **Description**: After showdown, the same winner messages are repeatedly added to chat every 5 seconds in an infinite loop
- **Resolution**: Added hand number tracking to prevent displaying showdown results multiple times for the same hand, and removed duplicate event handlers
- **Files Modified**: static/js/table.js

---

## Bug Categories

### UI/UX Issues
- Visual display problems
- User interaction issues
- Responsive design problems

### Game Logic Issues
- Incorrect hand evaluation
- State management problems
- Rule enforcement bugs

### Performance Issues
- Slow response times
- Memory leaks
- Network-related problems

### Integration Issues
- Frontend-backend communication
- Database synchronization
- Third-party service integration