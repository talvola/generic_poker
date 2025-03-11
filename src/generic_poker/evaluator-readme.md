# Hand Evaluator Documentation

## Overview

The `HandEvaluator` class provides a unified interface for evaluating poker hands across various game variants. It supports different evaluation types (high hands, lowball, badugi, etc.) and handles hand comparison to determine winners.

The evaluation system is built around pre-computed rankings stored in CSV files, allowing for fast and accurate hand evaluation even for complex variants.

## Evaluation Types

The system supports multiple evaluation types defined in the `EvaluationType` enum:

```python
class EvaluationType(str, Enum):
    """Types of poker hand evaluation."""
    HIGH = 'high'                # Traditional high-hand poker
    HIGH_WILD = 'high_wild'      # High-hand with wild cards
    LOW_A5 = 'a5_low'            # A-5 lowball (Ace to Five)
    LOW_27 = '27_low'            # 2-7 lowball (Deuce to Seven)
    LOW_A5_HIGH = 'a5_low_high'  # A-5 lowball, but highest unpaired hand
    BADUGI = 'badugi'            # Badugi
    BADUGI_AH = 'badugi_ah'      # Badugi with ace high
    HIDUGI = 'hidugi'            # Hi-Dugi
    HIGH_36CARD = '36card_ffh_high'  # 36-card deck high hands
    HIGH_20CARD = '20card_high'      # 20-card deck high hands
    GAME_49 = '49'              # Pip count games
    GAME_58 = '58'
    GAME_6 = '6'
    GAME_ZERO = 'zero'
    GAME_ZERO_6 = 'zero_6'
    GAME_21 = '21'
    GAME_21_6 = '21_6'
    LOW_PIP_6 = 'low_pip_6_cards'
```

Each evaluation type corresponds to a specific set of rules for determining hand strength.

## Basic Usage

```python
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.evaluator import evaluator, EvaluationType

# Create a hand
hand = [
    Card(Rank.ACE, Suit.SPADES),
    Card(Rank.KING, Suit.SPADES),
    Card(Rank.QUEEN, Suit.SPADES),
    Card(Rank.JACK, Suit.SPADES),
    Card(Rank.TEN, Suit.SPADES)
]

# Evaluate the hand
result = evaluator.evaluate_hand(hand, EvaluationType.HIGH)

# Get the hand description
print(f"Hand rank: {result.rank}")  # 1 for royal flush
print(f"Description: {result.description}")  # "Royal Flush"
```

## Comparing Hands

The evaluator makes it easy to compare two hands to determine a winner:

```python
hand1 = [
    Card(Rank.ACE, Suit.SPADES),
    Card(Rank.ACE, Suit.HEARTS),
    Card(Rank.ACE, Suit.CLUBS),
    Card(Rank.KING, Suit.SPADES),
    Card(Rank.KING, Suit.HEARTS)
]

hand2 = [
    Card(Rank.KING, Suit.CLUBS),
    Card(Rank.KING, Suit.DIAMONDS),
    Card(Rank.KING, Suit.HEARTS),
    Card(Rank.JACK, Suit.CLUBS),
    Card(Rank.JACK, Suit.DIAMONDS)
]

comparison = evaluator.compare_hands(hand1, hand2, EvaluationType.HIGH)

if comparison > 0:
    print("Hand 1 wins")
elif comparison < 0:
    print("Hand 2 wins")
else:
    print("Tie")
```

The `compare_hands` method returns:
- `1` if the first hand wins
- `-1` if the second hand wins
- `0` if the hands are tied

## Hand Results

The evaluator returns a `HandResult` object with detailed information about the hand:

```python
@dataclass
class HandResult:
    """Result of hand evaluation."""
    rank: int                       # Primary rank of hand (1=best)
    ordered_rank: Optional[int] = None  # Secondary ordering within rank
    description: Optional[str] = None   # Human-readable description
    cards_used: Optional[List[Card]] = None  # Cards that make up the hand
    sources: Optional[List[str]] = None  # Where each card came from
```

- `rank`: Primary classification (e.g., 1 for straight flush, 2 for four of a kind)
- `ordered_rank`: Secondary ordering within the same rank (e.g., ordering among all straight flushes)
- `description`: Human-readable description of the hand

## Finding Best Hands

When evaluating hands with both hole cards and community cards, you may need to find the best possible combination:

```python
def find_best_hand(hole_cards, community_cards, eval_type, required_hole=0, required_community=0):
    """Find the best possible hand given hole and community cards."""
    import itertools
    
    best_hand = None
    
    # Determine how to combine cards based on requirements
    if required_hole > 0 and required_community > 0:
        # Games like Greek Hold'em with specific requirements
        hole_combos = list(itertools.combinations(hole_cards, required_hole))
        community_combos = list(itertools.combinations(community_cards, required_community))
        
        for hole_combo in hole_combos:
            for comm_combo in community_combos:
                hand = list(hole_combo) + list(comm_combo)
                
                if best_hand is None:
                    best_hand = hand
                elif evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                    best_hand = hand
    else:
        # Games like Texas Hold'em with best 5 of 7
        all_cards = hole_cards + community_cards
        target_size = 5  # Standard 5-card hand
        
        for combo in itertools.combinations(all_cards, target_size):
            hand = list(combo)
            
            if best_hand is None:
                best_hand = hand
            elif evaluator.compare_hands(hand, best_hand, eval_type) > 0:
                best_hand = hand
    
    return best_hand
```

## Sorting Cards

The evaluator includes a `sort_cards` method to arrange cards according to the evaluation type's rules:

```python
# Sort cards according to evaluation rules
sorted_hand = evaluator.sort_cards(hand, EvaluationType.HIGH)
```

This is useful for displaying hands in a normalized format, such as showing a full house with three of a kind followed by the pair.

## Hand Qualifiers

Some games require hands to meet minimum strength requirements (qualifiers):

```python
# Evaluate a hand with a qualifier
# Hand must be at least a pair of jacks (rank 9) to qualify
qualifier = [9, None]  # [rank, ordered_rank]
result = evaluator.evaluate_hand(hand, EvaluationType.HIGH, qualifier=qualifier)

# If the hand doesn't qualify, result.rank will be 0
if result.rank == 0:
    print("Hand does not qualify")
```

## Architecture

The evaluation system uses a hierarchical approach:

1. `HandEvaluator`: Main interface that manages evaluation types
2. `BaseEvaluator`: Abstract base class for specific evaluation strategies
3. Concrete evaluators: Implementations for different game variants

The system is designed for extensibility, allowing new poker variants to be added by creating new evaluator implementations and ranking files.

## Performance Considerations

Hand evaluation uses pre-computed rankings stored in CSV files, which are cached for performance. This approach offers several benefits:

1. Fast evaluation: O(1) lookup time for most evaluations
2. Accurate rankings: Handles complex ordering rules correctly
3. Extensible: New variants can be added by creating new ranking files

For games with large card combinations (like finding the best 5 of 7 cards), performance can be affected by the combinatorial explosion. In these cases, consider optimizing the search space where possible.
