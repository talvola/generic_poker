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
- **Testing**: Verified fix with unit tests and custom test cases

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

### Bug #006 - No Visual Indication When Players Fold
- **Priority**: Medium
- **Status**: Open
- **Description**: When a player folds, there is no visual indication in the UI that they are no longer active in the hand
- **Steps to Reproduce**: 
  1. Start a hand with multiple players
  2. Have a player fold during any betting round
  3. Observe that folded player's seat looks identical to active players
- **Expected Behavior**: Folded players should have visual indicators such as mucked (removed) cards and grayed-out player information
- **Actual Behavior**: No visual distinction between active and folded players during hand
- **Related Task**: Task 8.3 (Player betting action system), Task 8.9 (Advanced card display system)
- **Notes**: Should implement card mucking (removal) and player seat styling changes (graying out, "FOLDED" indicator, etc.)
- **Description**: Action panel changes width when switching between waiting message and action buttons, causing table layout to shift
- **Steps to Reproduce**: 
  1. Observe action panel with "Waiting for your turn..." message
  2. Player's turn arrives and action buttons appear
  3. Panel width changes and table shifts left
- **Expected Behavior**: Action panel should maintain consistent width regardless of content
- **Actual Behavior**: Panel resizes horizontally, causing table display to move and reposition
- **Related Task**: Task 8.3 (Display player betting choices)
- **Notes**: Likely caused by centering behavior and lack of fixed width on action panel. Affects user experience with jarring layout shifts. 

---

## Resolved Bugs

(Bugs will be moved here when fixed)

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