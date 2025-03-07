# Pot Class Documentation

## Overview

The `Pot` class manages the poker pot structure, including the main pot and side pots. It handles complex scenarios such as all-in bets, multi-way pots, and pot distribution across multiple betting rounds.

## Creating a Pot

```python
from generic_poker.game.pot import Pot

# Create a new empty pot
pot = Pot()
```

The `Pot` class automatically initializes with a main pot and no side pots. It tracks the current betting round and manages all bet contributions.

## Key Methods

### Adding Bets

```python
pot.add_bet(player_id, total_amount, is_all_in, stack_before)
```

Adds a bet to the pot structure, potentially creating side pots as needed.

**Parameters:**
- `player_id` (str): Unique identifier for the player
- `total_amount` (int): Total amount the player will have contributed after this action
- `is_all_in` (bool): Whether this bet puts the player all-in
- `stack_before` (int): Player's chip stack before making this bet

**Example:**
```python
# Player P1 opens for 100
pot.add_bet("P1", 100, False, 1000)

# Player P2 calls
pot.add_bet("P2", 100, False, 900)

# Player P3 goes all-in for 75
pot.add_bet("P3", 75, True, 75)
```

### Ending a Betting Round

```python
pot.end_betting_round()
```

Ends the current betting round and prepares for the next one. This preserves the pot structure from the current round and creates a new round for further betting.

**Example:**
```python
# End the preflop betting round
pot.end_betting_round()

# Now we're in the flop betting round
pot.add_bet("P1", 50, False, 900)
```

### Awarding Pots to Winners

```python
pot.award_to_winners(winners, side_pot_index=None)
```

Awards the main pot or a specific side pot to the winners.

**Parameters:**
- `winners` (List[Player]): List of Player objects who won the pot
- `side_pot_index` (Optional[int]): Index of side pot to award; if None, awards the main pot

**Example:**
```python
# Award main pot to P1
pot.award_to_winners([player1])

# Award first side pot to P2
pot.award_to_winners([player2], side_pot_index=0)
```

## Properties

### Total Pot Size

```python
pot_size = pot.total
```

Returns the total amount in all pots (main pot + all side pots) in the current round.

### Pot Structure Information

The pot structure can be accessed via the `round_pots` attribute, which contains:
- `main_pot`: The main pot for the round
- `side_pots`: A list of side pots for the round
- `round_number`: The betting round number

Each pot (main or side) includes:
- `amount`: Total chips in the pot
- `eligible_players`: Set of player IDs who can win this pot
- `active_players`: Set of player IDs who can still bet in this pot
- `player_bets`: Dictionary mapping player IDs to their contributions

## Side Pot Handling

The `Pot` class automatically handles side pot creation when players go all-in:

1. When a player cannot match the current bet, a side pot is created
2. The main pot is capped at what the all-in player can contest
3. Excess chips go into side pots that exclude the all-in player

In multi-way all-in scenarios, multiple side pots may be created, each with different eligible players.

## Multi-Round Support

The pot tracks bets across multiple betting rounds (preflop, flop, turn, river). Each round has its own pot structure, but the total pot accumulates across all rounds.

After calling `end_betting_round()`, the pot structure is preserved, and a new betting round begins, allowing players to bet anew while maintaining their eligibility for previous pots.
