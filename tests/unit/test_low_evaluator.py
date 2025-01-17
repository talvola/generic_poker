"""Tests for A-5 and 2-7 low hand evaluation."""
import pytest
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.evaluator import HandEvaluator, EvaluationType

def create_cards(card_strs: list[str]) -> list[Card]:
    """Helper to create cards from strings like '2h', 'As', etc."""
    cards = []
    for card_str in card_strs:
        rank = card_str[0].upper()
        suit = card_str[1].lower()
        cards.append(Card(Rank(rank), Suit(suit)))
    return cards

def test_a5_low_hand_sorting():
    """Test that A-5 Low hands are sorted correctly."""
    evaluator = HandEvaluator()
    a5_evaluator = evaluator.get_evaluator(EvaluationType.LOW_A5)
    
    # Test wheel (A-5 is best possible hand)
    cards = create_cards(['As', 'Kh', '5d', '3c', '2h'])
    sorted_cards = a5_evaluator._sort_cards(cards)
    assert [c.rank.value for c in sorted_cards] == ['K', '5', '3', '2', 'A']
    
    # Test high cards (K-8 should be at end)
    cards = create_cards(['Ks', 'Th', '8d', '4c', '2h'])
    sorted_cards = a5_evaluator._sort_cards(cards)
    assert [c.rank.value for c in sorted_cards] == ['K', 'T', '8', '4', '2']

def test_a5_low_evaluation():
    """Test evaluation of A-5 Low hands."""
    evaluator = HandEvaluator()
    
    # Best possible hand: A-2-3-4-5
    wheel = create_cards(['As', '2h', '3d', '4c', '5h'])
    result = evaluator.evaluate_hand(wheel, EvaluationType.LOW_A5)
    assert result.rank == 1  # High card (best in lowball)
    
    # 7-6-4-3-2 is worse than wheel
    seven_low = create_cards(['7s', '6h', '4d', '3c', '2h'])
    result = evaluator.evaluate_hand(seven_low, EvaluationType.LOW_A5)
    assert result.rank == 1  # Still high card
    assert result.ordered_rank is not None
    assert result.ordered_rank > 1  # But worse than wheel
    
    # Pair of 2s
    pair = create_cards(['2s', '2h', '3d', '4c', '5h'])
    result = evaluator.evaluate_hand(pair, EvaluationType.LOW_A5)
    assert result.rank == 2  # One pair (worse than any no-pair hand)

def test_a5_low_hand_comparison():
    """Test comparing A-5 Low hands."""
    evaluator = HandEvaluator()
    
    # Wheel vs 7-low
    wheel = create_cards(['As', '2h', '3d', '4c', '5h'])
    seven_low = create_cards(['7s', '6h', '4d', '3c', '2h'])
    
    # Wheel should win (lower is better)
    comparison = evaluator.compare_hands(wheel, seven_low, EvaluationType.LOW_A5)
    assert comparison == 1
    
    # Pair vs high card
    pair = create_cards(['2s', '2h', '3d', '4c', '5h'])
    high_card = create_cards(['8s', '6h', '4d', '3c', '2h'])
    
    # High card should win (pairs are bad)
    comparison = evaluator.compare_hands(high_card, pair, EvaluationType.LOW_A5)
    assert comparison == 1

def test_a5_low_invalid_hands():
    """Test that straights and flushes don't count in A-5 Low."""
    evaluator = HandEvaluator()
    
    # Straight
    straight = create_cards(['5s', '4h', '3d', '2c', 'Ah'])
    result = evaluator.evaluate_hand(straight, EvaluationType.LOW_A5)
    
    # Should be evaluated as A-5 high card hand (best possible)
    assert result.rank == 1
    assert result.ordered_rank == 1
    
    # Flush
    flush = create_cards(['2s', '3s', '4s', '5s', '7s'])
    result = evaluator.evaluate_hand(flush, EvaluationType.LOW_A5)
    
    # Should be evaluated as 7-high
    assert result.rank == 1  # Still high card
    assert result.ordered_rank is not None
    assert result.ordered_rank > 1  # Worse than wheel