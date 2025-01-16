"""Tests for player hand implementation."""
import pytest
from generic_poker.core.hand import PlayerHand
from generic_poker.core.card import Card, Rank, Suit, Visibility


@pytest.fixture
def sample_cards():
    """Create a set of sample cards for testing."""
    return [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS)
    ]


def test_hand_initialization():
    """Test creating empty hand."""
    hand = PlayerHand()
    assert hand.size == 0
    assert hand.get_cards() == []
    assert str(hand) == "Empty hand"


def test_adding_removing_cards(sample_cards):
    """Test adding and removing cards from hand."""
    hand = PlayerHand()
    
    # Add cards
    for card in sample_cards:
        hand.add_card(card)
    assert hand.size == len(sample_cards)
    
    # Remove a card
    removed = hand.remove_card(sample_cards[0])
    assert removed == sample_cards[0]
    assert hand.size == len(sample_cards) - 1
    
    # Try to remove card not in hand
    with pytest.raises(ValueError):
        hand.remove_card(sample_cards[0])


def test_visibility_management(sample_cards):
    """Test managing card visibility."""
    hand = PlayerHand()
    hand.add_cards(sample_cards)
    
    # Initially all cards face down
    assert len(hand.get_cards(visible_only=True)) == 0
    
    # Show all cards
    hand.show_all()
    visible_cards = hand.get_cards(visible_only=True)
    assert len(visible_cards) == len(sample_cards)
    
    # Hide all cards
    hand.hide_all()
    assert len(hand.get_cards(visible_only=True)) == 0


def test_hand_subsets(sample_cards):
    """Test hand subset management."""
    hand = PlayerHand()
    hand.add_cards(sample_cards)
    
    # Add cards to subsets
    hand.add_to_subset(sample_cards[0], "high")
    hand.add_to_subset(sample_cards[1], "high")
    hand.add_to_subset(sample_cards[2], "low")
    
    # Check subsets
    high_cards = hand.get_subset("high")
    assert len(high_cards) == 2
    assert sample_cards[0] in high_cards
    assert sample_cards[1] in high_cards
    
    low_cards = hand.get_subset("low")
    assert len(low_cards) == 1
    assert sample_cards[2] in low_cards
    
    # Remove from subset
    hand.remove_from_subset(sample_cards[0], "high")
    assert len(hand.get_subset("high")) == 1
    
    # Clear subsets
    hand.clear_subsets()
    assert len(hand.get_subset("high")) == 0
    assert len(hand.get_subset("low")) == 0
    
    # Cards should still be in hand
    assert hand.size == len(sample_cards)


def test_string_representation(sample_cards):
    """Test hand string representation."""
    hand = PlayerHand()
    hand.add_cards(sample_cards)
    
    # All cards hidden
    assert "**" in str(hand)
    assert str(sample_cards[0]) not in str(hand)
    
    # Show some cards
    sample_cards[0].visibility = Visibility.FACE_UP
    assert str(sample_cards[0]) in str(hand)
    assert "**" in str(hand)  # Other cards still hidden


def test_clearing_hand(sample_cards):
    """Test clearing all cards from hand."""
    hand = PlayerHand()
    hand.add_cards(sample_cards)
    
    # Add to subset
    hand.add_to_subset(sample_cards[0], "high")
    
    # Clear hand
    hand.clear()
    assert hand.size == 0
    assert hand.get_cards() == []
    assert hand.get_subset("high") == []