"""Tests for deck implementation."""
import pytest
from generic_poker.core.deck import Deck
from generic_poker.core.card import Card, Rank, Suit, Visibility


def test_deck_initialization():
    """Test basic deck creation."""
    deck = Deck()
    assert deck.size == 52  # Using size property instead of len()
    assert not any(card.is_wild for card in deck.get_cards())


def test_deck_with_jokers():
    """Test deck creation with jokers."""
    deck = Deck(include_jokers=True)  # Changed from num_jokers
    assert deck.size == 54
    
    # Check jokers
    jokers = [c for c in deck.get_cards() if c.rank == Rank.JOKER]
    assert len(jokers) == 2
    assert all(j.is_wild for j in jokers)


def test_dealing_cards():
    """Test dealing cards from deck."""
    deck = Deck()
    initial_size = deck.size
    
    # Deal one card
    card = deck.deal_card()  # Changed from draw
    assert isinstance(card, Card)
    assert deck.size == initial_size - 1
    assert card.visibility == Visibility.FACE_DOWN
    
    # Deal face up card
    card = deck.deal_card(face_up=True)
    assert card.visibility == Visibility.FACE_UP
    
    # Deal multiple cards
    cards = deck.deal_cards(5)  # Changed from draw_cards
    assert len(cards) == 5
    assert deck.size == initial_size - 7  # 2 single deals + 5 cards


def test_dealing_empty_deck():
    """Test dealing from empty deck."""
    deck = Deck()
    
    # Empty the deck
    while deck.deal_card():  # Changed from draw
        pass
        
    assert deck.size == 0
    assert deck.deal_card() is None
    assert deck.deal_cards(5) == []


def test_deck_shuffling():
    """Test deck shuffling."""
    deck1 = Deck()
    deck2 = Deck()
    
    # Get initial order
    initial_cards = deck1.get_cards()
    
    # Shuffle one deck
    deck1.shuffle()
    
    # Compare with unshuffled deck
    assert deck1.get_cards() != deck2.get_cards()
    # Compare sorted strings to ensure same cards are present
    assert sorted(str(c) for c in deck1.get_cards()) == sorted(str(c) for c in deck2.get_cards())


def test_adding_removing_cards():
    """Test adding and removing specific cards."""
    deck = Deck()
    deck.clear()  # Start with empty deck
    
    # Add just the cards we want to test with
    test_card = Card(Rank.ACE, Suit.SPADES)
    deck.add_card(test_card)
    
    # Remove the card
    removed = deck.remove_card(test_card)
    assert removed.rank == test_card.rank and removed.suit == test_card.suit
    assert deck.size == 0
    
    # Try to remove a card from empty deck
    card_not_in_deck = Card(Rank.ACE, Suit.CLUBS)
    with pytest.raises(ValueError):
        deck.remove_card(card_not_in_deck)


def test_clearing_deck():
    """Test clearing all cards from deck."""
    deck = Deck()
    assert deck.size > 0
    
    deck.clear()
    assert deck.size == 0
    assert deck.get_cards() == []