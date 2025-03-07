# BettingManager Class Documentation

## Overview

The `BettingManager` class hierarchy provides implementations for different poker betting structures (Limit, No-Limit, and Pot-Limit). It handles bet validation, tracking, and enforcing the rules specific to each betting style.

## Creating a BettingManager

The recommended way to create a betting manager is through the factory function:

```python
from generic_poker.game.betting import create_betting_manager, BettingStructure

# Create a No-Limit betting manager with small bet of 10
nl_betting = create_betting_manager(BettingStructure.NO_LIMIT, small_bet=10)

# Create a Limit betting manager with small bet of 10, big bet of 20
limit_betting = create_betting_manager(BettingStructure.LIMIT, small_bet=10, big_bet=20)

# Create a Pot-Limit betting manager with small bet of 10
pot_limit_betting = create_betting_manager(BettingStructure.POT_LIMIT, small_bet=10)
```

## Key Methods

### Placing Bets

```python
betting.place_bet(player_id, amount, stack, is_forced=False)
```

Place a bet for a player.

**Parameters:**
- `player_id` (str): ID of betting player
- `amount` (int): Total amount player will have bet in this round after this action
- `stack` (int): Player's chip stack before this bet
- `is_forced` (bool): Whether this is a forced bet (blind/ante)

**Example:**
```python
# Post blinds
betting.place_bet("SB", 5, 500, is_forced=True)
betting.place_bet("BB", 10, 500, is_forced=True)

# UTG calls
betting.place_bet("UTG", 10, 1000)

# MP raises to 30
betting.place_bet("MP", 30, 1000)
```

### Getting Bet Requirements

```python
# Get minimum bet amount (to call)
min_bet = betting.get_min_bet(player_id, BetType.BIG)

# Get additional chips required to call
additional = betting.get_additional_required(player_id)

# Get minimum raise amount
min_raise = betting.get_min_raise(player_id)

# Get maximum bet amount
max_bet = betting.get_max_bet(player_id, BetType.BIG, stack)
```

These methods provide information about betting requirements:

- `get_min_bet()`: Returns the total amount required to make a valid bet (call)
- `get_additional_required()`: Returns additional chips needed to call
- `get_min_raise()`: Returns the minimum amount required for a valid raise
- `get_max_bet()`: Returns the maximum amount a player can bet

**Note:** All bet amount methods return the *total* amount a player must have bet, not just the additional chips needed. These values can be directly used as the `amount` parameter in `place_bet()`.

### Starting a New Betting Round

```python
betting.new_round(preserve_current_bet=False)
```

Start a new betting round.

**Parameters:**
- `preserve_current_bet` (bool): If True, continue current round (e.g., blinds to betting), preserving bet amount and blind bets; if False, start a new round

**Example:**
```python
# After flop is dealt
betting.new_round()

# Starting first betting round after blinds
betting.new_round(preserve_current_bet=True)
```

### Awarding Pots

```python
betting.award_pots(winners, side_pot_index=None)
```

Award main or specified side pot to winners, updating player stacks.

**Parameters:**
- `winners` (List[Player]): List of Player objects who won the pot
- `side_pot_index` (Optional[int]): Index of side pot to award; if None, awards the main pot

**Example:**
```python
# Award main pot to player1
betting.award_pots([player1])

# Award first side pot to player2
betting.award_pots([player2], side_pot_index=0)
```

### Getting Pot Information

```python
# Get total pot amount
total = betting.get_total_pot()

# Get main pot amount
main_pot = betting.get_main_pot_amount()

# Get number of side pots
num_side_pots = betting.get_side_pot_count()

# Get amount in a specific side pot
side_pot = betting.get_side_pot_amount(index)

# Get eligible players for a side pot
eligible = betting.get_side_pot_eligible_players(index)
```

## Betting Style Implementations

### LimitBettingManager

- Enforces fixed bet sizes (small bet and big bet)
- Typically uses small bet for first two rounds, big bet for later rounds
- Allows exactly one raise size per betting action

### NoLimitBettingManager

- Allows bets of any size up to a player's stack
- Enforces minimum raise rule: must raise by at least the previous raise amount
- Tracks last raise size to enforce minimum re-raises

### PotLimitBettingManager

- Allows bets up to the size of the pot
- Maximum bet = current bet + pot after call
- Enforces same minimum raise rules as No-Limit

## Round Management

The betting manager tracks the current betting round and maintains the pot structure. You can check if a betting round is complete:

```python
is_complete = betting.round_complete()
```

This returns true when all active players have acted and all bets are equal.
