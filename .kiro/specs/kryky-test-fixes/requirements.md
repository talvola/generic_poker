# Requirements Document

## Introduction

Fix the Kryky poker variant test to correctly reflect the betting order rules. The test currently has incorrect expectations about which player should act first in the draw and betting rounds after the initial deal. According to the game rules, the player with the highest visible hand should act first in all betting rounds, but the test expects Alice to act first when Bob actually has the highest hand with a pair of kings.

## Requirements

### Requirement 1

**User Story:** As a developer testing the Kryky poker variant, I want the test to correctly validate the betting order, so that the game implementation follows the proper rules.

#### Acceptance Criteria

1. WHEN the draw phase begins THEN the player with the highest visible hand SHALL act first
2. WHEN any betting round occurs THEN the player with the highest visible hand SHALL act first
3. WHEN Bob has a pair of kings (Kh, Kd) and other players have lower hands THEN Bob SHALL be the first to act

### Requirement 2

**User Story:** As a developer, I want the test assertions to match the actual game behavior, so that the test passes and validates correct functionality.

#### Acceptance Criteria

1. WHEN the test reaches step 6 (draw phase) THEN it SHALL expect Bob (p2) to act first
2. WHEN the test reaches step 7 (third betting round) THEN it SHALL expect Bob (p2) to act first  
3. WHEN the test reaches step 9 (fourth betting round) THEN it SHALL expect Bob (p2) to act first
4. WHEN players act in sequence THEN the order SHALL be Bob, Charlie, Alice based on hand strength