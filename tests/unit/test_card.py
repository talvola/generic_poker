"""Tests for card module."""
import pytest
from generic_poker.core.card import (
    Card, Rank, Suit, Visibility, WildType
)


def test_card_creation():
    """Test basic card creation."""
    card = Card(Rank.ACE, Suit.SPADES)
    assert card.rank == Rank.ACE
    assert card.suit == Suit.SPADES
    assert card.visibility == Visibility.FACE_DOWN
    assert not card.is_wild
    assert card.wild_type is None


def test_card_string_representation():
    """Test string conversion of cards."""
    card = Card(Rank.ACE, Suit.SPADES)
    assert str(card) == "As"
    
    card = Card(Rank.TEN, Suit.HEARTS)
    assert str(card) == "Th"
    
    # Test Joker
    joker = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
    assert str(joker) == "*j"


def test_card_equality():
    """Test card equality comparison."""
    card1 = Card(Rank.ACE, Suit.SPADES)
    card2 = Card(Rank.ACE, Suit.SPADES, visibility=Visibility.FACE_UP)
    card3 = Card(Rank.ACE, Suit.HEARTS)
    
    assert card1 == card2  # Visibility doesn't affect equality
    assert card1 != card3  # Different suits are not equal
    assert card1 != "As"  # Different types are not equal


def test_card_visibility():
    """Test card visibility changes."""
    card = Card(Rank.ACE, Suit.SPADES)
    assert card.visibility == Visibility.FACE_DOWN
    
    card.flip()
    assert card.visibility == Visibility.FACE_UP
    
    card.flip()
    assert card.visibility == Visibility.FACE_DOWN


def test_wild_card_handling():
    """Test wild card functionality."""
    card = Card(Rank.TWO, Suit.SPADES)
    assert not card.is_wild
    
    # Make card wild
    card.make_wild(WildType.NAMED)
    assert card.is_wild
    assert card.wild_type == WildType.NAMED
    
    # Clear wild status
    card.clear_wild()
    assert not card.is_wild
    assert card.wild_type is None


@pytest.mark.parametrize("card_str,expected_rank,expected_suit,expected_wild", [
    ("As", Rank.ACE, Suit.SPADES, False),
    ("2h", Rank.TWO, Suit.HEARTS, False),
    ("Td", Rank.TEN, Suit.DIAMONDS, False),
    ("Kc", Rank.KING, Suit.CLUBS, False),
    ("*j", Rank.JOKER, Suit.JOKER, True),
])
def test_card_from_string(card_str, expected_rank, expected_suit, expected_wild):
    """Test creating cards from string representation."""
    card = Card.from_string(card_str)
    assert card.rank == expected_rank
    assert card.suit == expected_suit
    assert card.is_wild == expected_wild


@pytest.mark.parametrize("invalid_str", [
    "",           # Empty string
    "A",          # Missing suit
    "AsH",        # Too long
    "Xx",         # Invalid rank
    "Ax",         # Invalid suit
    "*x",         # Invalid joker format
])
def test_card_from_string_invalid(invalid_str):
    """Test error handling for invalid card strings."""
    with pytest.raises(ValueError):
        Card.from_string(invalid_str)