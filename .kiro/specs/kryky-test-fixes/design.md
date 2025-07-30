# Design Document

## Overview

The Kryky test fix involves correcting the player action order expectations in the test to match the actual game behavior. The game correctly implements the "high_hand" betting order rule, but the test has incorrect assertions about which player should act first.

## Architecture

The fix is purely a test correction and does not require changes to the game engine itself. The game logic is working correctly - only the test expectations need to be updated.

## Components and Interfaces

### Test File: `tests/game/test_kryky.py`
- Function: `test_kryky_full_hand_with_showdown()`
- Specific sections that need correction:
  - Step 6: Draw Cards phase
  - Step 7: Third Betting Round  
  - Step 9: Fourth Betting Round

### Game State Analysis
Based on the predetermined deck and dealing order:
- Alice (p1): As, Ks (face up) - high card Ace
- Bob (p2): Kh, Kd (face up) - pair of kings (highest hand)
- Charlie (p3): 2c, Th (face up) - high card Ten (lowest hand)

## Data Models

### Player Action Order
The correct action order should be:
1. Bob (p2) - highest hand with pair of kings
2. Charlie (p3) - middle hand with Ten high
3. Alice (p1) - second highest with Ace high

### Test Assertions to Update
- Change `assert game.current_player.id == "p1"` to `assert game.current_player.id == "p2"`
- Update player action sequence from `("p1", "p2", "p3")` to `("p2", "p3", "p1")`

## Error Handling

The current test fails with:
```
WARNING - Invalid action - not Alice's turn
```

This indicates the game engine is correctly enforcing the betting order, but the test has wrong expectations.

## Testing Strategy

### Validation Steps
1. Verify Bob has the highest visible hand after initial deal
2. Confirm Bob acts first in draw phase (step 6)
3. Confirm Bob acts first in third betting round (step 7)
4. Confirm Bob acts first in fourth betting round (step 9)
5. Ensure all players can complete their actions in the correct sequence

### Test Execution
- Run the specific test: `pytest tests/game/test_kryky.py::test_kryky_full_hand_with_showdown -v`
- Verify no warnings about invalid player turns
- Confirm test passes completely