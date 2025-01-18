"""Tests for deck implementation."""
import pytest
from generic_poker.core.deck import Deck, DeckType
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
    assert card is not None, "Expected a card but got None"
    assert isinstance(card, Card)
    assert card.visibility == Visibility.FACE_DOWN

    # Deal face up card
    card = deck.deal_card(face_up=True)
    assert card is not None, "Expected a card but got None"
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

def test_dealing_more_cards_than_available():
    """Test dealing more cards than the deck contains."""
    deck = Deck()
    cards = deck.deal_cards(60)  # More than 52 cards
    assert len(cards) == 52
    assert deck.size == 0

def test_shuffling_empty_deck():
    """Test shuffling an empty deck."""
    deck = Deck()
    deck.clear()
    try:
        deck.shuffle()
    except Exception as e:
        pytest.fail(f"Shuffling empty deck raised an exception: {e}")
    assert deck.size == 0

def test_adding_duplicate_cards():
    """Test adding the same card multiple times."""
    deck = Deck()
    deck.clear()

    card = Card(Rank.KING, Suit.HEARTS)
    deck.add_card(card)
    deck.add_card(card)  # Add duplicate

    assert deck.size == 2
    assert deck.get_cards().count(card) == 2

def test_removing_card_not_in_deck():
    """Test removing a card that doesn't exist in the deck."""
    deck = Deck()
    card_not_in_deck = Card(Rank.TEN, Suit.CLUBS)
    
    deck.clear()  # Ensure deck is empty

    with pytest.raises(ValueError, match=str(card_not_in_deck)):
        deck.remove_card(card_not_in_deck)

def test_deal_all_cards_face_up():
    """Test dealing all cards face up."""
    deck = Deck()
    cards = deck.deal_cards(52, face_up=True)
    
    assert all(card.visibility == Visibility.FACE_UP for card in cards)
    assert deck.size == 0

def test_deck_initialization_unique_cards():
    """Test deck has all unique cards upon initialization."""
    deck = Deck()
    card_set = set(str(card) for card in deck.get_cards())
    
    assert len(card_set) == 52  # Ensure no duplicates

def test_multiple_shuffles():
    """Test that shuffling multiple times changes deck order."""
    deck = Deck()
    original_order = deck.get_cards().copy()

    deck.shuffle()
    first_shuffle = deck.get_cards().copy()
    
    deck.shuffle()
    second_shuffle = deck.get_cards().copy()

    assert original_order != first_shuffle
    assert first_shuffle != second_shuffle

def test_add_remove_multiple_cards():
    """Test adding and removing multiple cards."""
    deck = Deck()
    deck.clear()

    cards_to_add = [
        Card(Rank.TWO, Suit.HEARTS),
        Card(Rank.THREE, Suit.CLUBS),
        Card(Rank.FOUR, Suit.SPADES)
    ]

    deck.add_cards(cards_to_add)
    assert deck.size == 3

    removed_cards = deck.remove_cards(cards_to_add)
    assert deck.size == 0
    assert removed_cards == cards_to_add

def test_short_ta_deck_initialization():
    """Test initialization of SHORT_TA deck (Royal Hold'em)."""
    deck = Deck(deck_type=DeckType.SHORT_TA)
    assert deck.size == 20  # 5 ranks × 4 suits

    valid_ranks = {Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE}
    for card in deck.get_cards():
        assert card.rank in valid_ranks
        assert card.suit in {Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES}

    # Ensure no duplicate cards
    assert len(set(str(card) for card in deck.get_cards())) == 20


def test_short_6a_deck_initialization():
    """Test initialization of SHORT_6A deck (Six-Plus Hold'em)."""
    deck = Deck(deck_type=DeckType.SHORT_6A)
    assert deck.size == 36  # 9 ranks (6-A) × 4 suits

    invalid_ranks = {Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE}
    for card in deck.get_cards():
        assert card.rank not in invalid_ranks
        assert card.suit in {Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES}

    # Ensure no duplicate cards
    assert len(set(str(card) for card in deck.get_cards())) == 36


def test_short_ta_deck_shuffling():
    """Test shuffling SHORT_TA deck changes the order."""
    deck = Deck(deck_type=DeckType.SHORT_TA)
    original_order = deck.get_cards().copy()
    deck.shuffle()
    assert deck.get_cards() != original_order  # Order should be different


def test_short_6a_deck_shuffling():
    """Test shuffling SHORT_6A deck changes the order."""
    deck = Deck(deck_type=DeckType.SHORT_6A)
    original_order = deck.get_cards().copy()
    deck.shuffle()
    assert deck.get_cards() != original_order  # Order should be different


def test_dealing_short_ta_deck():
    """Test dealing all cards from SHORT_TA deck."""
    deck = Deck(deck_type=DeckType.SHORT_TA)
    cards = deck.deal_cards(20)
    assert len(cards) == 20
    assert deck.size == 0
    assert len(set(str(card) for card in cards)) == 20  # No duplicates


def test_dealing_short_6a_deck():
    """Test dealing all cards from SHORT_6A deck."""
    deck = Deck(deck_type=DeckType.SHORT_6A)
    cards = deck.deal_cards(36)
    assert len(cards) == 36
    assert deck.size == 0
    assert len(set(str(card) for card in cards)) == 36  # No duplicates