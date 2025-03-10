# HandDescriber Class Documentation

## Overview

The `HandDescriber` class provides human-readable descriptions of poker hands. It supports both basic descriptions (e.g., "Full House") and detailed descriptions (e.g., "Full House, Aces over Kings") across various poker variants and evaluation types.

## Creating a HandDescriber

```python
from generic_poker.evaluation.hand_description import HandDescriber
from generic_poker.evaluation.evaluator import EvaluationType

# Create a describer for standard high poker
high_describer = HandDescriber(EvaluationType.HIGH)

# Create a describer for A-5 lowball
low_describer = HandDescriber(EvaluationType.LOW_A5)

# Create a describer for pip-count games
pip_describer = HandDescriber(EvaluationType.GAME_49)
```

## Key Methods

### Basic Hand Description

```python
# Get a basic description of a poker hand
cards = [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES), 
         Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.SPADES), 
         Card(Rank.TEN, Suit.SPADES)]
description = describer.describe_hand(cards)  # Returns "Royal Flush"
```

The `describe_hand()` method returns a simple classification of the hand (e.g., "Full House", "Two Pair", "Flush").

### Detailed Hand Description

```python
# Get a detailed description of a poker hand
cards = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.CLUBS), 
         Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS), 
         Card(Rank.KING, Suit.DIAMONDS)]
description = describer.describe_hand_detailed(cards)  # Returns "Full House, Aces over Kings"
```

The `describe_hand_detailed()` method returns a more detailed description that includes specifics about the hand:
- Full House: "Full House, Aces over Kings"
- Four of a Kind: "Four Aces"
- Three of a Kind: "Three Queens"
- Two Pair: "Two Pair, Aces and Kings"
- Pair: "Pair of Queens"
- High Card: "Ace High"
- Straight: "Ace-high Straight"
- Flush: "King-high Flush"
- Straight Flush: "King-high Straight Flush"

## Supported Poker Variants

The HandDescriber supports a wide range of poker variants through different evaluation types:

- **Standard High Poker**: EvaluationType.HIGH
- **Lowball Variants**: EvaluationType.LOW_A5, EvaluationType.LOW_27
- **Badugi and Variants**: EvaluationType.BADUGI, EvaluationType.BADUGI_AH, EvaluationType.HIDUGI
- **Pip-Count Games**: EvaluationType.GAME_49, EvaluationType.GAME_6, EvaluationType.GAME_ZERO
- **Blackjack-Style**: EvaluationType.GAME_21, EvaluationType.GAME_21_6
- **Short Deck Variants**: EvaluationType.HIGH_36CARD, EvaluationType.HIGH_20CARD

## Rank Ordering

The HandDescriber respects the proper rank ordering for each evaluation type. For example:
- In high poker, Ace is the highest rank
- In A-5 lowball, Ace is the lowest rank
- In 2-7 lowball, Ace is high and 2 is low

The appropriate ordering is used when determining the highest card in a hand and when sorting pairs in descriptions like "Two Pair, Aces and Kings".

## Description Files

The class attempts to load hand descriptions from CSV files in the `data/hand_descriptions/` directory. If a description file isn't available, it falls back to basic descriptions.

For pip-count games (like '49'), the description is simply the pip count (e.g., "49").

## Usage Example

```python
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.hand_description import HandDescriber
from generic_poker.evaluation.evaluator import EvaluationType

# Create a hand describer for high poker
describer = HandDescriber(EvaluationType.HIGH)

# Create a full house hand
full_house = [
    Card(Rank.ACE, Suit.HEARTS),
    Card(Rank.ACE, Suit.CLUBS),
    Card(Rank.ACE, Suit.SPADES),
    Card(Rank.KING, Suit.HEARTS),
    Card(Rank.KING, Suit.DIAMONDS)
]

# Get descriptions
basic = describer.describe_hand(full_house)  # "Full House"
detailed = describer.describe_hand_detailed(full_house)  # "Full House, Aces over Kings"

print(f"Basic: {basic}")
print(f"Detailed: {detailed}")
```

In an interactive game or poker application, this provides players with clear, natural-language descriptions of their hands.
