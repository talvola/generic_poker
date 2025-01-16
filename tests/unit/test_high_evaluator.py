"""Tests for high-hand poker evaluation."""
import pytest
from pathlib import Path

from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.evaluator import HandEvaluator, EvaluationType
from generic_poker.evaluation.eval_types.high import HighHandEvaluator


@pytest.fixture
def evaluator():
    """Create a hand evaluator instance."""
    return HandEvaluator()


@pytest.fixture
def sample_hands():
    """Sample poker hands for testing."""
    return {
        'royal_flush': [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.TEN, Suit.HEARTS),
        ],
        'straight_flush': [
            Card(Rank.NINE, Suit.SPADES),
            Card(Rank.EIGHT, Suit.SPADES),
            Card(Rank.SEVEN, Suit.SPADES),
            Card(Rank.SIX, Suit.SPADES),
            Card(Rank.FIVE, Suit.SPADES),
        ],
        'four_of_a_kind': [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
        ],
        'full_house': [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.KING, Suit.CLUBS),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
        ],
        'flush': [
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.JACK, Suit.CLUBS),
            Card(Rank.NINE, Suit.CLUBS),
            Card(Rank.SIX, Suit.CLUBS),
            Card(Rank.THREE, Suit.CLUBS),
        ],
        'straight': [
            Card(Rank.NINE, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.SEVEN, Suit.DIAMONDS),
            Card(Rank.SIX, Suit.SPADES),
            Card(Rank.FIVE, Suit.HEARTS),
        ],
        'three_of_a_kind': [
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.QUEEN, Suit.CLUBS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.NINE, Suit.DIAMONDS),
        ],
        'two_pair': [
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.JACK, Suit.DIAMONDS),
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.TEN, Suit.CLUBS),
            Card(Rank.NINE, Suit.SPADES),
        ],
        'one_pair': [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.CLUBS),
            Card(Rank.JACK, Suit.SPADES),
        ],
        'high_card': [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.FIVE, Suit.SPADES),
        ],
    }


def test_hand_sorting(evaluator):
    """Test that cards are sorted correctly."""
    high_evaluator = evaluator.get_evaluator(EvaluationType.HIGH)
    
    unsorted = [
        Card(Rank.THREE, Suit.HEARTS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.THREE, Suit.CLUBS),
        Card(Rank.KING, Suit.CLUBS),
    ]
    
    sorted_cards = high_evaluator._sort_cards(unsorted)
    
    # Should be sorted by rank (descending) first, then suit (bridge order: s,h,d,c)
    assert sorted_cards[0].rank == Rank.ACE and sorted_cards[0].suit == Suit.SPADES
    assert sorted_cards[1].rank == Rank.KING and sorted_cards[1].suit == Suit.DIAMONDS
    assert sorted_cards[2].rank == Rank.KING and sorted_cards[2].suit == Suit.CLUBS
    assert sorted_cards[3].rank == Rank.THREE and sorted_cards[3].suit == Suit.HEARTS
    assert sorted_cards[4].rank == Rank.THREE and sorted_cards[4].suit == Suit.CLUBS

def test_string_conversion(evaluator):
    """Test conversion of cards to string format."""
    high_evaluator = evaluator.get_evaluator(EvaluationType.HIGH)
    
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.TEN, Suit.HEARTS),
    ]
    
    hand_str = high_evaluator._cards_to_string(cards)
    assert hand_str == "AhKhQhJhTh"


def test_hand_rankings(evaluator, sample_hands):
    """Test that hands are ranked correctly relative to each other."""
    expected_order = [
        'royal_flush',
        'straight_flush',
        'four_of_a_kind',
        'full_house',
        'flush',
        'straight',
        'three_of_a_kind',
        'two_pair',
        'one_pair',
        'high_card'
    ]
    
    # Compare each hand to the next one in the list
    for i in range(len(expected_order) - 1):
        hand1 = sample_hands[expected_order[i]]
        hand2 = sample_hands[expected_order[i + 1]]
        
        result = evaluator.compare_hands(hand1, hand2, EvaluationType.HIGH)
        assert result == 1, f"{expected_order[i]} should beat {expected_order[i + 1]}"


def test_same_rank_ordering(evaluator):
    """Test ordering within the same rank (e.g., different straight flushes)."""
    higher_straight = [
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.TEN, Suit.HEARTS),
        Card(Rank.NINE, Suit.HEARTS),
    ]
    
    lower_straight = [
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.NINE, Suit.SPADES),
        Card(Rank.EIGHT, Suit.SPADES),
    ]
    
    result = evaluator.compare_hands(higher_straight, lower_straight, EvaluationType.HIGH)
    assert result == 1, "Higher straight flush should win"


def test_invalid_hand_size():
    """Test that invalid hand sizes are rejected."""
    evaluator = HandEvaluator()
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
    ]
    
    with pytest.raises(ValueError, match="requires exactly 5 cards"):
        evaluator.evaluate_hand(cards, EvaluationType.HIGH)