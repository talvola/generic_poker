def test_simple_side_pot():
    """
    Test three players with different stack sizes all going all-in.
    
    Initial stacks:
    - P1: $300
    - P2: $500
    - P3: $800
    
    Betting sequence:
    1. P1 all-in $300
    2. P2 calls $300, raises $200 (all-in at $500)
    3. P3 must just call $500 total (no raise possible)
       - $300 to main pot
       - $200 to side pot
    
    Results:
    - Main pot: $900 (300 × 3 players) - all players eligible
    - Side pot: $400 (200 × 2 players) - only P2 and P3 eligible
    """
    actions = [
        BettingAction("P1", 300, "all-in", 300, 0),     # P1 all-in
        BettingAction("P2", 300, "call", 300, 200),     # P2 calls P1
        BettingAction("P2", 200, "all-in", 500, 0),     # P2 raises and all-in
        BettingAction("P3", 500, "call", 500, 300)      # P3 can only call
    ]
    
    structure = SidePotCalculator.calculate_pots(actions)
    
    # Main pot should have everyone's first $300
    assert structure.main_pot == 900, "Main pot should be 3 × 300"
    assert structure.main_pot_players == {"P1", "P2", "P3"}
    
    # One side pot for betting between $300 and $500
    assert len(structure.side_pots) == 1, "Should have one side pot"
    side_pot = structure.side_pots[0]
    assert side_pot.amount == 400, "Side pot should be 2 × 200"
    assert side_pot.eligible_players == {"P2", "P3"}

def test_sequential_all_ins():
    """
    Test sequence of all-ins where each player raises before going all-in.
    
    Initial stacks:
    - P1: $25
    - P2: $50
    - P3: $75
    
    Betting sequence:
    1. P1 all-in $25
    2. P2 calls $25, raises $25 (all-in at $50)
    3. P3 calls $50, raises $25 (all-in at $75)
    
    Results:
    - Main pot: $75 (25 × 3) - all eligible
    - Side pot: $75 (P2's 25 + P3's 50) - P2, P3 eligible
    """
    actions = [
        BettingAction("P1", 25, "all-in", 25, 0),     # P1 all-in
        BettingAction("P2", 25, "call", 25, 25),      # P2 calls P1
        BettingAction("P2", 25, "all-in", 50, 0),     # P2 raises and all-in
        BettingAction("P3", 50, "call", 50, 25),      # P3 calls P2
        BettingAction("P3", 25, "all-in", 75, 0)      # P3 can raise as P2 acted
    ]
    
    structure = SidePotCalculator.calculate_pots(actions)
    
    # Main pot has everyone's minimum contribution
    assert structure.main_pot == 75, "Main pot should be 3 × 25"
    assert structure.main_pot_players == {"P1", "P2", "P3"}
    
    # One side pot for all betting above P1's all-in
    assert len(structure.side_pots) == 1, "Should have one side pot"
    side_pot = structure.side_pots[0]
    assert side_pot.amount == 75, "Side pot should be all betting above 25"
    assert side_pot.eligible_players == {"P2", "P3"}

def test_complex_side_pot_p1_p2():
    """
    Test four players with different stack sizes all going all-in.
    
    Initial stacks:
    - P1: $300
    - P2: $500
    - P3: $900
    - P4: $1000
    
    Betting sequence:
    1. P1 all-in $300
    2. P2 calls $300, raises $200 (all-in at $500)
    
    Results:
    - Main pot: $600 (300 × 2 players) - all players eligible
    - First side pot: $200 (200 × 1 players) - P2 created
    """
    actions = [
        BettingAction("P1", 300, "all-in", 300, 0),     # P1 all-in
        BettingAction("P2", 300, "call", 300, 200),     # P2 calls P1
        BettingAction("P2", 200, "all-in", 500, 0)     # P2 raises and all-in
        
    ]
    
    structure = SidePotCalculator.calculate_pots(actions)
    
    # Main pot should have everyone's first $300
    assert structure.main_pot == 600, "Main pot should be 2 × 300"
    assert structure.main_pot_players == {"P1", "P2"}
    
    # First side pot
    assert len(structure.side_pots) == 1, "Should have two side pots"
    first_side_pot = structure.side_pots[0]
    assert first_side_pot.amount == 200, "First side pot should be 1 × 200"
    assert first_side_pot.eligible_players == {"P2"}

def test_complex_side_pot_p1_p2_p3():
    """
    Test four players with different stack sizes all going all-in.
    
    Initial stacks:
    - P1: $300
    - P2: $500
    - P3: $900
    - P4: $1000
    
    Betting sequence:
    1. P1 all-in $300
    2. P2 calls $300, raises $200 (all-in at $500)
    3. P3 calls $500, raises $400 (all-in at $900)
    
    Results:
    - Main pot: $900 (300 × 3 players) - all players eligible
    - First side pot: $400 (200 × 2 players) - P2, P3 eligible
    """
    actions = [
        BettingAction("P1", 300, "all-in", 300, 0),     # P1 all-in
        BettingAction("P2", 300, "call", 300, 200),     # P2 calls P1
        BettingAction("P2", 200, "all-in", 500, 0),    # P2 raises and all-in
        BettingAction("P3", 300, "call", 300, 600),     # P3 calls P1 (main pot)
        BettingAction("P3", 200, "call", 500, 400),     # P3 calls P2 (first side pot)
        BettingAction("P3", 400, "all-in", 900, 0)     # P3 raises and all-in (creates second side pot)
    ]
    
    structure = SidePotCalculator.calculate_pots(actions)
    
    # Main pot should have everyone's first $300
    assert structure.main_pot == 900, "Main pot should be 2 × 300"
    assert structure.main_pot_players == {"P1", "P2", "P3"}
    
    # two side pots
    assert len(structure.side_pots) == 2, "Should have two side pots"

    # First side pot
    first_side_pot = structure.side_pots[0]
    assert first_side_pot.amount == 400, "First side pot should be 2 × 200"
    assert first_side_pot.eligible_players == {"P2","P3"}    

    # Second side pot for betting between $500 and $900
    second_side_pot = structure.side_pots[1]
    assert second_side_pot.amount == 400, "Second side pot should be 1 × 400"
    assert second_side_pot.eligible_players == {"P3"}    

def test_complex_side_pot():
    """
    Test four players with different stack sizes all going all-in.
    
    Initial stacks:
    - P1: $300
    - P2: $500
    - P3: $900
    - P4: $1000
    
    Betting sequence:
    1. P1 all-in $300
    2. P2 calls $300, raises $200 (all-in at $500)
    3. P3 calls $500, raises $400 (all-in at $900)
    4. P4 must call $900 total (no raise possible)
       - $300 to main pot
       - $200 to first side pot
       - $400 to second side pot
    
    Results:
    - Main pot: $1,200 (300 × 4 players) - all players eligible
    - First side pot: $600 (200 × 3 players) - P2, P3, P4 eligible
    - Second side pot: $800 (400 × 2 players) - P3, P4 eligible
    """
    actions = [
        BettingAction("P1", 300, "all-in", 300, 0),     # P1 all-in
        BettingAction("P2", 300, "call", 300, 200),     # P2 calls P1
        BettingAction("P2", 200, "all-in", 500, 0),     # P2 raises and all-in
        BettingAction("P3", 300, "call", 300, 600),     # P3 calls P1
        BettingAction("P3", 200, "call", 500, 400),     # P3 calls P2
        BettingAction("P3", 400, "all-in", 900, 0),     # P3 raises and all-in
        BettingAction("P4", 900, "call", 900, 100)      # P4 calls the total
    ]
    
    structure = SidePotCalculator.calculate_pots(actions)
    
    # Main pot should have everyone's first $300
    assert structure.main_pot == 1200, "Main pot should be 4 × 300"
    assert structure.main_pot_players == {"P1", "P2", "P3", "P4"}
    
    # First side pot for betting between $300 and $500
    assert len(structure.side_pots) == 2, "Should have two side pots"
    first_side_pot = structure.side_pots[0]
    assert first_side_pot.amount == 600, "First side pot should be 3 × 200"
    assert first_side_pot.eligible_players == {"P2", "P3", "P4"}
    
    # Second side pot for betting between $500 and $900
    second_side_pot = structure.side_pots[1]
    assert second_side_pot.amount == 800, "Second side pot should be 2 × 400"
    assert second_side_pot.eligible_players == {"P3", "P4"}

def test_side_pot_calculator():
    """
    Test side pot creation with different eligibility at each level.
    
    Betting sequence:
    1. P2 all-in for $50
    2. P3 calls $50, raises $25 (to $75)
    3. P1 calls $75, raises $25 (to $100)
    
    Should create:
    - Main pot: Everyone's first $50
    - Side pot 1: P1 and P3's betting from $50-$75
    - Side pot 2: Only P1's betting from $75-$100
    """
    contributions = [
        PotContribution("P1", 100, True, 100),
        PotContribution("P2", 50, True, 50),
        PotContribution("P3", 75, True, 75)
    ]
    
    structure = SidePotCalculator.calculate_pots(contributions)
    
    # Main pot (everyone contributes minimum amount)
    assert structure.main_pot == 150, "Main pot should be 3 × 50"
    assert structure.main_pot_players == {"P1", "P2", "P3"}
    
    # Should have two side pots
    assert len(structure.side_pots) == 2, "Should have two side pots"
    
    # First side pot (P1 and P3 contributing 25 each)
    first_side = structure.side_pots[0]
    assert first_side.amount == 50, "First side pot should be 2 × 25"
    assert first_side.eligible_players == {"P1", "P3"}
    
    # Second side pot (only P1 contributing final 25)
    second_side = structure.side_pots[1]
    assert second_side.amount == 25, "Second side pot should be 1 × 25"
    assert second_side.eligible_players == {"P1"}

def test_all_in_below_current_bet():
    """
    Test player going all-in for less than current bet.
    P1 bets 100
    P2 all-in for 50
    P3 calls 100
    """
    contributions = [
        PotContribution("P1", 100, False, 200),  # Not all-in
        PotContribution("P2", 50, True, 50),     # All-in below current bet
        PotContribution("P3", 100, False, 150)   # Calls full amount
    ]
    
    structure = SidePotCalculator.calculate_pots(contributions)
    
    # Main pot should be lowest all-in amount × number of players
    assert structure.main_pot == 150  # 50 × 3
    assert structure.main_pot_players == {"P1", "P2", "P3"}
    
    # One side pot for amounts above P2's all-in
    assert len(structure.side_pots) == 1
    side_pot = structure.side_pots[0]
    assert side_pot.amount == 100  # (100-50) × 2 players
    assert side_pot.eligible_players == {"P1", "P3"}

def test_multiple_players_same_all_in():
    """
    Test multiple players going all-in for the same amount.
    P1 all-in for 50
    P2 all-in for 50
    P3 all-in for 100
    """
    contributions = [
        PotContribution("P1", 50, True, 50),
        PotContribution("P2", 50, True, 50),
        PotContribution("P3", 100, True, 100)
    ]
    
    structure = SidePotCalculator.calculate_pots(contributions)
    
    # Main pot includes all players at lowest all-in amount
    assert structure.main_pot == 150  # 50 × 3
    assert structure.main_pot_players == {"P1", "P2", "P3"}
    
    # One side pot for P3's excess
    assert len(structure.side_pots) == 1
    side_pot = structure.side_pots[0]
    assert side_pot.amount == 50  # (100-50) × 1
    assert side_pot.eligible_players == {"P3"}

def test_active_players_between_all_ins():
    """
    Test handling of active players between all-ins where eligibility doesn't change.
    
    Betting sequence:
    1. P1 all-in for $25
    2. P2 calls $25, raises $25 (to $50, not all-in)
    3. P3 calls $50, raises $25 (to $75)
    4. P2 calls additional $25 (to $75)
    
    Should create:
    - Main pot: Everyone's first $25
    - Single side pot: All betting above $25 (P2 and P3 only)
    """
    contributions = [
        PotContribution("P1", 25, True, 25),
        PotContribution("P2", 75, True, 75),
        PotContribution("P3", 75, True, 75)
    ]
    
    structure = SidePotCalculator.calculate_pots(contributions)
    
    assert structure.main_pot == 75, "Main pot should be 3 × 25"
    assert structure.main_pot_players == {"P1", "P2", "P3"}
    
    # One combined side pot for all betting above P1's all-in
    assert len(structure.side_pots) == 1, "Should have one side pot"
    side_pot = structure.side_pots[0]
    assert side_pot.amount == 100, "Side pot should be remaining bets from P2 and P3"
    assert side_pot.eligible_players == {"P2", "P3"}
    
def test_pot_tracking():
    # Test just the contribution tracking
    pot = Pot()
    pot.add_contribution(PotContribution("P1", 50, True, 50))
    structure = pot.get_pot_structure()
    assert structure.main_pot == 50
    