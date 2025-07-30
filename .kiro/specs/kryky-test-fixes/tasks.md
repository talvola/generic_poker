# Implementation Plan

- [x] 1. Fix Step 6 draw phase player action order


  - Update the test assertion to expect Bob (p2) to act first instead of Alice (p1)
  - Change the player action sequence to start with Bob
  - _Requirements: 1.1, 1.3, 2.1_

- [x] 2. Fix Step 7 third betting round player action order  


  - Update the test assertion to expect Bob (p2) to act first instead of Alice (p1)
  - Change the player action sequence to follow Bob -> Charlie -> Alice order
  - _Requirements: 1.2, 1.3, 2.2_

- [x] 3. Fix Step 9 fourth betting round player action order


  - Update the test assertion to expect Bob (p2) to act first instead of Alice (p1) 
  - Change the player action sequence to follow Bob -> Charlie -> Alice order
  - _Requirements: 1.2, 1.3, 2.3_

- [x] 4. Update test comments to reflect correct hand analysis


  - Fix the comment that incorrectly states "Alice still has highest 3-card hand"
  - Add comments explaining why Bob has the highest hand with pair of kings
  - _Requirements: 2.4_

- [x] 5. Run test to verify all fixes work correctly



  - Execute the specific test to ensure it passes without warnings
  - Verify no "Invalid action - not player's turn" warnings appear
  - Confirm all betting rounds proceed in correct order
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3_