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

### Bug #005 - Showdown Chat Messages Loop Infinitely
- **Priority**: High
- **Status**: Open
- **Description**: After showdown, the same winner messages are repeatedly added to chat every 5 seconds in an infinite loop
- **Steps to Reproduce**: 
  1. Complete a hand to showdown
  2. Observe chat messages showing winner information
  3. Wait and observe the same messages being added repeatedly
- **Expected Behavior**: Showdown results should be displayed once in chat when hand completes
- **Actual Behavior**: Same showdown messages (winner, pot collection, summary) are added to chat repeatedly every few seconds
- **Related Task**: Task 8.5 (Showdown display system)
- **Evidence**: HTML shows multiple identical showdown messages with different timestamps
- **Notes**: Also shows empty card arrays "[]" instead of actual cards in winner display

### Bug #006 - Player's Own Cards Disappear After Actions
- **Priority**: High
- **Status**: Open
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
- **Notes**: This affects the fundamental gameplay experience as players cannot see their own cards consistently


 

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