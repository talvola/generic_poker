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
    assert str(joker) == "Rj"


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

def test_make_wild_on_joker():
    """Test that making a Joker wild does not change its wild type."""
    joker = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)

    joker.make_wild(WildType.MATCHING)  # This should have no effect

    assert joker.is_wild
    assert joker.wild_type == WildType.NATURAL  # Should remain NATURAL

def test_joker_visibility_flip():
    """Test flipping Joker's visibility."""
    joker = Card(Rank.JOKER, Suit.JOKER)
    
    assert joker.visibility == Visibility.FACE_DOWN
    joker.flip()
    assert joker.visibility == Visibility.FACE_UP
    joker.flip()
    assert joker.visibility == Visibility.FACE_DOWN

def test_clear_wild_on_non_wild_card():
    """Test clearing wild on a non-wild card does nothing."""
    card = Card(Rank.FIVE, Suit.HEARTS)
    
    card.clear_wild()  # Should not change anything
    assert not card.is_wild
    assert card.wild_type is None

@pytest.mark.parametrize("card_str", ["as", "AS", "As", "aS"])
def test_card_from_string_case_insensitivity(card_str):
    """Test that from_string is case-insensitive."""
    card = Card.from_string(card_str)
    assert card.rank == Rank.ACE
    assert card.suit == Suit.SPADES

def test_wild_card_equality():
    """Test equality of wild cards with different wild types."""
    card1 = Card(Rank.FOUR, Suit.CLUBS, is_wild=True, wild_type=WildType.NAMED)
    card2 = Card(Rank.FOUR, Suit.CLUBS, is_wild=True, wild_type=WildType.MATCHING)
    
    assert card1 == card2  # Equality ignores wild_type

def test_invalid_joker_creation():
    """Test that invalid Joker strings raise errors."""
    with pytest.raises(ValueError):
        Card.from_string("*h")  # Joker must be '*j'

def test_wild_card_string_representation():
    """Test string output of non-Joker wild cards."""
    card = Card(Rank.FIVE, Suit.HEARTS)
    card.make_wild(WildType.NAMED)

    assert str(card) == "5h"  # Wild status shouldn't affect string output


# ── Wild Card Pipeline Tests ─────────────────────────────────────────────────

class TestJokerWildTypeTransitions:
    """Test make_wild transitions for Joker cards (conditional wild support)."""

    def test_joker_natural_to_bug(self):
        """Joker NATURAL -> BUG is allowed (e.g. face-up conditional rule)."""
        joker = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
        joker.make_wild(WildType.BUG)
        assert joker.is_wild
        assert joker.wild_type == WildType.BUG

    def test_joker_natural_to_named(self):
        """Joker NATURAL -> NAMED is allowed (e.g. face-down conditional rule)."""
        joker = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
        joker.make_wild(WildType.NAMED)
        assert joker.is_wild
        assert joker.wild_type == WildType.NAMED

    def test_joker_natural_to_matching_blocked(self):
        """Joker NATURAL -> MATCHING is blocked (protects natural wildness)."""
        joker = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
        joker.make_wild(WildType.MATCHING)
        assert joker.is_wild
        assert joker.wild_type == WildType.NATURAL  # Unchanged

    def test_joker_stays_wild_after_type_change(self):
        """Joker remains is_wild=True through all allowed transitions."""
        joker = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
        joker.make_wild(WildType.BUG)
        assert joker.is_wild is True
        # Note: Once set to BUG, it's no longer NATURAL so the guard doesn't apply
        joker.make_wild(WildType.NAMED)
        assert joker.is_wild is True
        assert joker.wild_type == WildType.NAMED

    def test_non_joker_make_wild(self):
        """Regular cards always accept any wild type."""
        card = Card(Rank.TWO, Suit.SPADES)
        card.make_wild(WildType.NAMED)
        assert card.is_wild
        assert card.wild_type == WildType.NAMED

        card.make_wild(WildType.BUG)
        assert card.wild_type == WildType.BUG

        card.make_wild(WildType.MATCHING)
        assert card.wild_type == WildType.MATCHING


class TestWildCardTransformation:
    """Test that wild cards are correctly transformed for evaluation."""

    def test_named_wild_transforms_to_w(self):
        """NAMED wild card -> W1 in evaluation."""
        from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator
        card = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NAMED)
        evaluator = StandardHandEvaluator.__new__(StandardHandEvaluator)
        result = evaluator._transform_wild_cards([card])
        assert result == ["W1"]

    def test_natural_wild_transforms_to_w(self):
        """NATURAL wild card -> W1 in evaluation."""
        from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator
        card = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NATURAL)
        evaluator = StandardHandEvaluator.__new__(StandardHandEvaluator)
        result = evaluator._transform_wild_cards([card])
        assert result == ["W1"]

    def test_bug_transforms_to_b(self):
        """BUG wild card -> B1 in evaluation."""
        from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator
        card = Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.BUG)
        evaluator = StandardHandEvaluator.__new__(StandardHandEvaluator)
        result = evaluator._transform_wild_cards([card])
        assert result == ["B1"]

    def test_non_wild_card_passes_through(self):
        """Non-wild cards pass through unchanged."""
        from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator
        card = Card(Rank.ACE, Suit.SPADES)
        evaluator = StandardHandEvaluator.__new__(StandardHandEvaluator)
        result = evaluator._transform_wild_cards([card])
        assert result == [card]

    def test_mixed_hand_wild_and_regular(self):
        """Hand with one wild and regular cards transforms correctly."""
        from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator
        cards = [
            Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NAMED),
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
        ]
        evaluator = StandardHandEvaluator.__new__(StandardHandEvaluator)
        result = evaluator._transform_wild_cards(cards)
        assert result[0] == "W1"
        assert result[1] == cards[1]
        assert result[2] == cards[2]

    def test_mixed_w_and_b_transforms(self):
        """Two wilds with different types both transform (W1 + B1)."""
        from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator
        cards = [
            Card(Rank.JOKER, Suit.JOKER, is_wild=True, wild_type=WildType.NAMED),
            Card(Rank.TWO, Suit.SPADES, is_wild=True, wild_type=WildType.BUG),
        ]
        evaluator = StandardHandEvaluator.__new__(StandardHandEvaluator)
        result = evaluator._transform_wild_cards(cards)
        assert "W1" in result
        assert "B1" in result


class TestDeckJokerCount:
    """Test that deck types create the correct number of jokers."""

    def test_short_27_ja_no_extra_jokers(self):
        """SHORT_27_JA deck with 1 joker should have exactly 41 cards."""
        from generic_poker.core.deck import Deck, DeckType
        deck = Deck(include_jokers=1, deck_type=DeckType.SHORT_27_JA)
        assert deck.size == 41  # 10 ranks * 4 suits + 1 joker

    def test_short_27_ja_single_joker(self):
        """SHORT_27_JA deck should have exactly 1 joker card."""
        from generic_poker.core.deck import Deck, DeckType
        deck = Deck(include_jokers=1, deck_type=DeckType.SHORT_27_JA)
        jokers = [c for c in deck.cards if c.rank == Rank.JOKER]
        assert len(jokers) == 1
        assert jokers[0].suit == Suit.JOKER
        assert jokers[0].is_wild is True
        assert jokers[0].wild_type == WildType.NATURAL

    def test_short_27_ja_no_jokers(self):
        """SHORT_27_JA deck without jokers should have exactly 40 cards."""
        from generic_poker.core.deck import Deck, DeckType
        deck = Deck(include_jokers=0, deck_type=DeckType.SHORT_27_JA)
        assert deck.size == 40
        jokers = [c for c in deck.cards if c.rank == Rank.JOKER]
        assert len(jokers) == 0

    def test_short_27_ja_correct_ranks(self):
        """SHORT_27_JA should have 2-7 and J-A (no 8, 9, T)."""
        from generic_poker.core.deck import Deck, DeckType
        deck = Deck(include_jokers=0, deck_type=DeckType.SHORT_27_JA)
        ranks = {c.rank for c in deck.cards}
        assert Rank.EIGHT not in ranks
        assert Rank.NINE not in ranks
        assert Rank.TEN not in ranks
        assert Rank.TWO in ranks
        assert Rank.SEVEN in ranks
        assert Rank.JACK in ranks
        assert Rank.ACE in ranks

    def test_standard_deck_no_jokers_in_ranks(self):
        """Standard deck should not include joker rank in base cards."""
        from generic_poker.core.deck import Deck, DeckType
        deck = Deck(include_jokers=0, deck_type=DeckType.STANDARD)
        assert deck.size == 52
        jokers = [c for c in deck.cards if c.rank == Rank.JOKER]
        assert len(jokers) == 0

