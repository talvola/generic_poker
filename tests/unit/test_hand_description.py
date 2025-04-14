"""Tests for the HandDescriber class."""
import pytest
from generic_poker.core.card import Card, Rank, Suit, WildType
from generic_poker.evaluation.evaluator import EvaluationType
from generic_poker.evaluation.hand_description import HandDescriber


def test_high_hand_description():
    """Test basic hand descriptions for high poker."""
    describer = HandDescriber(EvaluationType.HIGH)
    
    # Test Royal Flush
    cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.TEN, Suit.SPADES)
    ]
    assert describer.describe_hand(cards) == "Royal Flush"
    assert describer.describe_hand_detailed(cards) == "Royal Flush"
    
    # Test Straight Flush (not royal)
    cards = [
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.TEN, Suit.HEARTS),
        Card(Rank.NINE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Straight Flush"
    assert describer.describe_hand_detailed(cards) == "King-high Straight Flush"

    # Test Four of a Kind
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.ACE, Suit.DIAMONDS),
        Card(Rank.ACE, Suit.CLUBS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Four of a Kind"
    assert describer.describe_hand_detailed(cards) == "Four Aces"

def test_full_house_description():
    """Test detailed description for full house."""
    describer = HandDescriber(EvaluationType.HIGH)
    
    # Test Full House (Aces over Kings)
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.ACE, Suit.CLUBS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.KING, Suit.DIAMONDS)
    ]
    assert describer.describe_hand(cards) == "Full House"
    assert describer.describe_hand_detailed(cards) == "Full House, Aces over Kings"
    
    # Test Full House (Queens over Jacks)
    cards = [
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.CLUBS),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.JACK, Suit.DIAMONDS)
    ]
    assert describer.describe_hand(cards) == "Full House"
    assert describer.describe_hand_detailed(cards) == "Full House, Queens over Jacks"

def test_low_pair_descriptions():
    """Test detailed descriptions for pairs, two pairs, etc."""
    describer = HandDescriber(EvaluationType.HIGH)
    
    # Test Two Pair (Aces and Kings)
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.ACE, Suit.DIAMONDS),
        Card(Rank.KING, Suit.CLUBS),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.QUEEN, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Two Pair"
    assert describer.describe_hand_detailed(cards) == "Two Pair, Aces and Kings"
    
    # Test Two Pair (10s and 7s)
    cards = [
        Card(Rank.TEN, Suit.HEARTS),
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.SEVEN, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.DIAMONDS),
        Card(Rank.FIVE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Two Pair"
    assert describer.describe_hand_detailed(cards) == "Two Pair, Tens and Sevens"
    
    # Test Pair of Queens
    cards = [
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.NINE, Suit.SPADES),
        Card(Rank.FIVE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "One Pair"
    assert describer.describe_hand_detailed(cards) == "Pair of Queens"

def test_low_pair_wild_descriptions():
    """Test detailed descriptions for pairs, two pairs, etc."""
    describer = HandDescriber(EvaluationType.HIGH_WILD)

    bug = Card(Rank.JOKER, Suit.JOKER)  # Define a joker card for wild type
    bug.make_wild(WildType.BUG)  # Set the joker to be a bug
    # Test Pair of Aces using Joker
    cards = [
        Card(Rank.TEN, Suit.HEARTS),
        bug,
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.NINE, Suit.SPADES),
        Card(Rank.ACE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "One Pair"
    assert describer.describe_hand_detailed(cards) == "Pair of Aces"

    wild = Card(Rank.JOKER, Suit.JOKER)  # Define a joker card for wild type
    wild.make_wild(WildType.NATURAL)  # Set the joker to be a wild
    # Test Pair of Aces using Joker
    cards = [
        Card(Rank.TEN, Suit.HEARTS),
        wild,
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.NINE, Suit.SPADES),
        Card(Rank.FIVE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "One Pair"
    assert describer.describe_hand_detailed(cards) == "Pair of Jacks"

def test_high_card_description():
    """Test high card description."""
    describer = HandDescriber(EvaluationType.HIGH)
    
    # Test Ace-high
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.CLUBS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.NINE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "High Card"
    assert describer.describe_hand_detailed(cards) == "Ace High"
    
    # Test Queen-high
    cards = [
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.NINE, Suit.DIAMONDS),
        Card(Rank.SEVEN, Suit.SPADES),
        Card(Rank.FIVE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "High Card"
    assert describer.describe_hand_detailed(cards) == "Queen High"

def test_straight_and_flush_descriptions():
    """Test detailed descriptions for straights and flushes."""
    describer = HandDescriber(EvaluationType.HIGH)
    
    # Test Ace-high Straight
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.CLUBS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.TEN, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Straight"
    assert describer.describe_hand_detailed(cards) == "Ace-high Straight"
    
    # Test King-high Flush
    cards = [
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.NINE, Suit.HEARTS),
        Card(Rank.SEVEN, Suit.HEARTS),
        Card(Rank.FIVE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Flush"
    assert describer.describe_hand_detailed(cards) == "King-high Flush"

def test_straight_wild_description():
    """Test detailed descriptions for straights and flushes."""
    describer = HandDescriber(EvaluationType.HIGH_WILD)
    
    bug = Card(Rank.JOKER, Suit.JOKER)  # Define a joker card for wild type
    bug.make_wild(WildType.BUG)  # Set the joker to be a bug

    # Test Ace-high Straight
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.CLUBS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        bug,
        Card(Rank.TEN, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Straight"
    assert describer.describe_hand_detailed(cards) == "Ace-high Straight"

def test_three_of_kind_description():
    """Test description for three of a kind."""
    describer = HandDescriber(EvaluationType.HIGH)
    
    # Test Three of a Kind (Queens)
    cards = [
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.CLUBS),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.NINE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Three of a Kind"
    assert describer.describe_hand_detailed(cards) == "Three Queens"

def test_three_of_kind_wild_description():
    """Test description for three of a kind."""
    describer = HandDescriber(EvaluationType.HIGH_WILD)
    
    wild = Card(Rank.JOKER, Suit.JOKER)  # Define a joker card for wild type
    wild.make_wild(WildType.NATURAL)  # Set the joker to be a wild

    # Test Three of a Kind (Queens)
    cards = [
        Card(Rank.QUEEN, Suit.HEARTS),
        wild,
        Card(Rank.QUEEN, Suit.CLUBS),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.NINE, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "Three of a Kind"
    assert describer.describe_hand_detailed(cards) == "Three Queens"

def test_five_of_kind_wild_description():
    """Test description for three of a kind."""
    describer = HandDescriber(EvaluationType.HIGH_WILD)
    
    wild = Card(Rank.JOKER, Suit.JOKER)  # Define a joker card for wild type
    wild.make_wild(WildType.NATURAL)  # Set the joker to be a wild

    # Test Three of a Kind (Queens)
    cards = [
        Card(Rank.QUEEN, Suit.HEARTS),
        wild,
        Card(Rank.QUEEN, Suit.CLUBS),
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.QUEEN, Suit.DIAMONDS)
    ]
    assert describer.describe_hand(cards) == "Five of a Kind"
    assert describer.describe_hand_detailed(cards) == "Five Queens"

def test_a5_description():
    """Test detailed descriptions for hands using A-5."""
    describer = HandDescriber(EvaluationType.LOW_A5)
    
    # Test Ace-high Straight - which should be a High Card for King in A-5
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.CLUBS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.TEN, Suit.HEARTS)
    ]
    assert describer.describe_hand(cards) == "High Card"
    assert describer.describe_hand_detailed(cards) == "King High"

# don't have the evaluators for these yet 

# def test_pip_hand_description():
#     """Test pip-based hand description (game 49)."""
#     describer = HandDescriber(EvaluationType.GAME_49)
    
#     # Test pip-based hand (49)
#     cards = [
#         Card(Rank.TEN, Suit.SPADES),
#         Card(Rank.TEN, Suit.HEARTS),
#         Card(Rank.TEN, Suit.CLUBS),
#         Card(Rank.TEN, Suit.DIAMONDS),
#         Card(Rank.NINE, Suit.SPADES)
#     ]
#     assert describer.describe_hand(cards) == "49"
#     assert describer.describe_hand_detailed(cards) == "49"

if __name__ == "__main__":
    pytest.main()