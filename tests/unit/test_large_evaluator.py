import pytest
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.evaluator import HandEvaluator, EvaluationType
from generic_poker.evaluation.eval_types.large import LargeHandEvaluator
from generic_poker.evaluation.hand_description import HandDescriber

def create_cards(card_strs: list[str]) -> list[Card]:
    """Helper to create cards from strings like 'As', 'Kh', etc."""
    return [Card(Rank(card_str[0].upper()), Suit(card_str[1].lower())) for card_str in card_strs]

def test_ne_seven_card_high_evaluation():
    """Test evaluation of a seven-card hand in New England Hold’Em."""
    evaluator = HandEvaluator()
    nehe_evaluator = evaluator.get_evaluator(EvaluationType.NE_SEVEN_CARD_HIGH)

    # Test a Grand Straight Flush (Rank 1, OrderedRank 1)
    cards = create_cards(['As', 'Ks', 'Qs', 'Js', 'Ts', '9s', '8s'])
    result = nehe_evaluator.evaluate(cards)
    assert result.rank == 1, "Should be a Grand Straight Flush"
    assert result.ordered_rank == 1, "Should be the top ordered rank"

    # Test sorting
    unsorted_cards = create_cards(['9s', 'As', 'Qs', 'Ts', 'Ks', 'Js', '8s'])
    sorted_cards = nehe_evaluator._sort_cards(unsorted_cards)
    assert [c.rank.value for c in sorted_cards] == ['A', 'K', 'Q', 'J', 'T', '9', '8'], "Should sort in standard order"

    # Test sample hand retrieval
    sample_hand_str = nehe_evaluator.get_sample_hand(1, 1)
    assert sample_hand_str == 'AsKsQsJsTs9s8s', "Should return a Grand Straight Flush sample"

def test_ne_seven_card_high_detailed_description():
    """Test detailed descriptions for NE_SEVEN_CARD_HIGH hands."""
    describer = HandDescriber(EvaluationType.NE_SEVEN_CARD_HIGH)
    
    # Grand Straight Flush: As-Ks-Qs-Js-Ts-9s-8s
    cards = create_cards(['As', 'Ks', 'Qs', 'Js', 'Ts', '9s', '8s'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ace-high Grand Straight Flush", "Should describe a Grand Straight Flush"    

    # Grand Straight Flush: T-9-8-7-6-5-4
    cards = create_cards(['Ts', '9s', '8s', '7s', '6s', '5s', '4s'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ten-high Grand Straight Flush", "Should describe a Grand Straight Flush"

    # Palace: 7-7-7-7-3-3-3
    cards = create_cards(['7s', '7h', '7d', '7c', '3s', '3h', '3d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Palace, Sevens over Threes", "Should describe a Palace"

    # Long Straight Flush: T-9-8-7-6-5-2
    cards = create_cards(['Ts', '9s', '8s', '7s', '6s', '5s', '2s'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ten-high Long Straight Flush", "Should describe a Long Straight Flush"    

    # Long Straight Flush: K-T-9-8-7-6-5
    cards = create_cards(['Ks', 'Ts', '9s', '8s', '7s', '6s', '5s'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ten-high Long Straight Flush", "Should describe a Long Straight Flush"        

    # Grand Flush: K-Q-8-7-6-5-2
    cards = create_cards(['Ks', 'Qs', '8s', '7s', '6s', '5s', '2s'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "King-high Grand Flush", "Should describe a Grand Flush"       

    # Mansion: 7-7-7-7-3-3-2
    cards = create_cards(['7s', '7h', '7d', '7c', '3s', '3h', '2d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Mansion, Sevens over Threes", "Should describe a Mansion"

    # Straight Flush: K-T-9-8-7-6-4
    cards = create_cards(['Ks', 'Ts', '9s', '8s', '7s', '6s', '4d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ten-high Straight Flush", "Should describe a Straight Flush"      
    
    # Hotel: K-K-K-5-5-5-2
    cards = create_cards(['Ks', 'Kh', 'Kd', '5s', '5h', '5d', '2c'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Hotel, Kings and Fives", "Should describe a Hotel"

    # Villa: K-K-K-5-5-2-2
    cards = create_cards(['Ks', 'Kh', 'Kd', '5s', '5h', '2d', '2c'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Villa, Kings over Fives with Twos", "Should describe a Villa"
    
    # Grand Straight: T-9-8-7-6-5-4
    cards = create_cards(['Ts', '9d', '8c', '7s', '6h', '5s', '4h'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ten-high Grand Straight", "Should describe a Grand Straight"

    # Four of a Kind: 7-7-7-7-5-3-2
    cards = create_cards(['7s', '7h', '7d', '7c', '5s', '3h', '2d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Four Sevens", "Should describe a Four of a Kind"    

    # Long Flush: K-Q-8-7-6-5-2
    cards = create_cards(['Ks', 'Qs', '8s', '7s', '6s', '5s', '2d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "King-high Long Flush", "Should describe a Long Flush"        

    # Long Straight: T-9-8-7-6-5-2
    cards = create_cards(['Ts', '9d', '8c', '7s', '6h', '5s', '2h'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ten-high Long Straight", "Should describe a Long Straight"     

    # Three Pair: K-K-5-5-2-2-6
    cards = create_cards(['Ks', 'Kh', '5d', '5s', '2h', '2d', '6c'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Three Pair, Kings, Fives, and Twos", "Should describe a Three Pair"    

    # Full House: K-K-K-5-5-8-2
    cards = create_cards(['Ks', 'Kh', 'Kd', '5s', '5h', '8d', '2c'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Full House, Kings over Fives", "Should describe a Full House"    

    # Flush: K-Q-8-7-6-5-2
    cards = create_cards(['Ks', 'Qs', '8s', '7s', '6s', '5h', '2d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "King-high Flush", "Should describe a Flush"       

    # Flush: K-Q-8-7-6-5-2
    cards = create_cards(['Kc', 'Qs', '8s', '7s', '6s', '5s', '2d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Queen-high Flush", "Should describe a Flush"   

    # Straight: T-9-8-7-6-4-2
    cards = create_cards(['Ts', '9d', '8c', '7s', '6h', '4s', '2h'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Ten-high Straight", "Should describe a Straight"               

    # Three of a Kind: 7-7-7-6-5-3-2
    cards = create_cards(['7s', '7h', '7d', '6c', '5s', '3h', '2d'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Three Sevens", "Should describe a Three of a Kind"        

    # Two Pair: K-K-5-5-Q-J-6
    cards = create_cards(['Ks', 'Kh', '5d', '5s', 'Qh', 'Jd', '6c'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Two Pair, Kings and Fives", "Should describe a Two Pair"      

    # One Pair: K-K-Q-J-6-5-2
    cards = create_cards(['Ks', 'Kh', 'Qd', 'Js', '6h', '5d', '2c'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "Pair of Kings", "Should describe a Pair"     

    # High Card: K-K-Q-J-6-5-2
    cards = create_cards(['Ks', 'Qd', 'Js', '8d', '6h', '5d', '2c'])
    desc = describer.describe_hand_detailed(cards)
    assert desc == "King High", "Should describe a High Card"     