import pytest
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.evaluator import EvaluationType
from generic_poker.evaluation.hand_description import HandDescriber

def test_high_hand_description():
    describer = HandDescriber(EvaluationType.HIGH)
    # Test for a Royal Flush
    cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.TEN, Suit.SPADES)
    ]
    assert describer.describe_hand(cards) == "Royal Flush"
    assert describer.describe_hand_detailed(cards) == "Royal Flush"

def test_full_house_description():
    describer = HandDescriber(EvaluationType.HIGH)
    # Test for a Full House (Aces over Kings)
    cards = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.ACE, Suit.CLUBS),
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.KING, Suit.DIAMONDS)
    ]
    assert describer.describe_hand(cards) == "Full House"
    assert describer.describe_hand_detailed(cards) == "Full House, Aces over Fours"

def test_pip_hand_description():
    describer = HandDescriber(EvaluationType.GAME_49)
    # Test for pip-based hand evaluation (sum of pips = 49)
    cards = [
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.TEN, Suit.HEARTS),
        Card(Rank.TEN, Suit.CLUBS),
        Card(Rank.TEN, Suit.DIAMONDS),
        Card(Rank.NINE, Suit.SPADES)
    ]
    assert describer.describe_hand(cards) == "49"
    assert describer.describe_hand_detailed(cards) == "49"

if __name__ == "__main__":
    pytest.main()