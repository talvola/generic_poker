"""Tests for ShowdownManager class."""
import pytest
from unittest.mock import Mock, patch
import itertools

from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.evaluation.evaluator import EvaluationType, evaluator
from generic_poker.game.table import Player, Table, PlayerHand
from generic_poker.game.showdown_manager import ShowdownManager  # Adjust import as needed
from generic_poker.config.loader import GameRules

@pytest.fixture
def mock_player():
    """Create a mock player for testing."""
    player = Mock(spec=Player)
    player.id = "p1"
    player.name = "TestPlayer"
    
    # Create a player hand
    hand = PlayerHand()
    
    # Add cards first
    hand.add_card(Card(Rank.ACE, Suit.SPADES))
    hand.add_card(Card(Rank.KING, Suit.SPADES))
    hand.add_card(Card(Rank.QUEEN, Suit.HEARTS))
    hand.add_card(Card(Rank.JACK, Suit.HEARTS))
    hand.add_card(Card(Rank.TEN, Suit.CLUBS))
    
    # Then set visibility separately
    hand.cards[0].visibility = Visibility.FACE_DOWN  # Ace of Spades
    hand.cards[1].visibility = Visibility.FACE_DOWN  # King of Spades
    hand.cards[2].visibility = Visibility.FACE_UP    # Queen of Hearts
    hand.cards[3].visibility = Visibility.FACE_UP    # Jack of Hearts
    hand.cards[4].visibility = Visibility.FACE_DOWN  # Ten of Clubs
    
    # Create a subset
    hand.subsets["TestSubset"] = [
        hand.cards[0],  # Ace of Spades
        hand.cards[1]   # King of Spades
    ]
    
    player.hand = hand
    return player

@pytest.fixture
def mock_community_cards():
    """Create mock community cards for testing."""
    return {
        "default": [
            Card(Rank.NINE, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.DIAMONDS),
            Card(Rank.SIX, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.DIAMONDS)
        ],
        "Board1": [
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.FOUR, Suit.CLUBS),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.SIX, Suit.CLUBS)
        ]
    }

@pytest.fixture
def mock_table():
    """Create a mock table for testing."""
    return Mock(spec=Table)

@pytest.fixture
def mock_betting():
    """Create a mock betting manager for testing."""
    betting = Mock()
    betting.get_main_pot_amount.return_value = 100
    betting.get_side_pot_count.return_value = 0
    return betting

@pytest.fixture
def mock_rules():
    """Create mock game rules for testing."""
    rules = Mock(spec=GameRules)
    rules.showdown = Mock()
    return rules

@pytest.fixture
def showdown_manager(mock_table, mock_betting, mock_rules):
    """Create a ShowdownManager instance for testing."""
    return ShowdownManager(mock_table, mock_betting, mock_rules)

class TestShowdownManager:
    """Tests for the ShowdownManager class."""
    
    def test_find_best_hand_with_hole_cards_only(self, showdown_manager, mock_player):
        """Test finding best hand with only hole cards (e.g., 5-card stud)."""
        # Simple case: just use all hole cards
        showdown_rules = {}
        
        best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
            mock_player, {}, showdown_rules, EvaluationType.HIGH
        )
        
        # Should return all hole cards
        assert len(best_hand) == 5
        assert len(used_hole_cards) == 5
        assert best_hand == mock_player.hand.get_cards()
        assert used_hole_cards == mock_player.hand.get_cards()
    
    def test_find_best_hand_with_specific_hole_subset(self, showdown_manager, mock_player):
        """Test finding best hand with a specific hole card subset."""
        # Use a specific subset
        showdown_rules = {
            "hole_subset": "TestSubset"
        }
        
        best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
            mock_player, {}, showdown_rules, EvaluationType.HIGH
        )
        
        # Should return cards from the specified subset
        assert len(best_hand) == 2
        assert len(used_hole_cards) == 2
        assert best_hand == mock_player.hand.get_subset("TestSubset")
        assert used_hole_cards == mock_player.hand.get_subset("TestSubset")
    
    def test_find_best_hand_with_card_state_filter(self, showdown_manager, mock_player):
        """Test finding best hand filtered by card state (face up/down)."""
        # Filter to face-down cards only
        showdown_rules = {
            "cardState": "face down"
        }
        
        best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
            mock_player, {}, showdown_rules, EvaluationType.HIGH
        )
        
        # Should return only face-down cards
        assert len(best_hand) == 3
        assert all(card.visibility == Visibility.FACE_DOWN for card in best_hand)
        
        # Filter to face-up cards only
        showdown_rules = {
            "cardState": "face up"
        }
        
        best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
            mock_player, {}, showdown_rules, EvaluationType.HIGH
        )
        
        # Should return only face-up cards
        assert len(best_hand) == 2
        assert all(card.visibility == Visibility.FACE_UP for card in best_hand)
    
    def test_find_best_hand_with_community_cards(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using hole cards and community cards (e.g., Hold'em)."""
        # Use 2 hole cards and 3 community cards (e.g., Hold'em)
        showdown_rules = {
            "holeCards": 2,
            "communityCards": 3
        }
        
        # Patch evaluator.compare_hands to always return 1 for the first combination
        # This simplifies testing by making a specific hand always the "best"
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )
        
        # Should have correct number of cards
        assert len(best_hand) == 5  # 2 hole + 3 community
        assert len(used_hole_cards) == 2  # 2 hole cards used
    
    def test_find_best_hand_with_any_cards(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using any cards configuration."""
        # Use any 5 cards from hole and community
        showdown_rules = {
            "anyCards": 5
        }
        
        # Patch evaluator to make testing deterministic
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )
        
        # Should have correct number of cards
        assert len(best_hand) == 5
    
    def test_find_best_hand_with_combinations(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using combinations configuration."""
        # Define multiple combinations of hole/community cards
        showdown_rules = {
            "combinations": [
                {"holeCards": 2, "communityCards": 3},
                {"holeCards": 3, "communityCards": 2}
            ]
        }
        
        # Patch evaluator to make testing deterministic
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )
        
        # Should have correct number of cards (5 total)
        assert len(best_hand) == 5
    
    def test_find_best_hand_with_community_combinations(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using community card combinations."""
        # Use combinations of community card subsets
        showdown_rules = {
            "holeCards": 2,
            "communityCardCombinations": [
                ["default"],
                ["Board1"]
            ],
            "totalCards": 5
        }
        
        # Patch evaluator to make testing deterministic
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )
        
        # Should have correct number of cards (5 total)
        assert len(best_hand) == 5
        assert len(used_hole_cards) == 2  # 2 hole cards used
    
    def test_handle_not_enough_cards(self, showdown_manager, mock_player):
        """Test handling case where not enough cards are available."""
        # Requirement is more than available
        showdown_rules = {
            "holeCards": 7,  # Player only has 5
            "communityCards": 0
        }
        
        best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
            mock_player, {}, showdown_rules, EvaluationType.HIGH
        )
        
        # Should return empty lists when not enough cards
        assert best_hand == []
        assert used_hole_cards == []
    
    def test_handle_zero_cards_with_pip_value(self, showdown_manager, mock_player):
        """Test handling zero cards case with pip value for specialized games."""
        # Empty hand allowed with pip value (for games like Scarney)
        showdown_rules = {
            "minimumCards": 0,
            "zeroCardsPipValue": 0
        }
        
        # Mock the player's hand to return empty list
        empty_hand = PlayerHand()  # Create an actual empty hand
        with patch.object(mock_player, 'hand', empty_hand):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, {}, showdown_rules, EvaluationType.LOW_PIP_6
            )
        
        # Should return empty lists for zero-card hands
        assert best_hand == []
        assert used_hole_cards == []
    
    def test_hole_cards_list_with_options(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand with multiple hole/community card options."""
        # Multiple options for hole/community combinations
        showdown_rules = {
            "holeCards": [2, 3, 4],
            "communityCards": [3, 2, 1]
        }
        
        # Patch evaluator to make testing deterministic
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )
        
        # Should have correct total cards (5)
        assert len(best_hand) == 5
    
    def test_all_hole_cards_special_case(self, showdown_manager, mock_player, mock_community_cards):
        """Test using 'all' hole cards special case."""
        # Use all hole cards and fill with community cards
        showdown_rules = {
            "holeCards": "all",  # Special case
            "communityCards": 0  # Will be calculated dynamically
        }
        
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )
        
        # Get the actual cards from the hand
        all_cards = mock_player.hand.get_cards()
        
        # Should use all 5 hole cards
        assert len(best_hand) == 5
        assert len(used_hole_cards) == 5
        assert all(card in all_cards for card in best_hand)
    
    def test_with_wild_cards(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand with wild cards."""
        # Define wild card rules
        showdown_rules = {
            "holeCards": 2,
            "communityCards": 3,
            "wildCards": [
                {
                    "type": "rank",
                    "rank": "ACE",
                    "role": "wild"
                }
            ]
        }
        
        # Patch apply_wild_cards method to verify it's called
        with patch.object(showdown_manager, 'apply_wild_cards') as mock_apply_wild:
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )
            
            # Verify wild card rules were applied
            mock_apply_wild.assert_called_once()
    
    def test_padding_option(self, showdown_manager, mock_player):
        """Test finding best hand with padding option."""
        # Use hole cards with padding (for short-handed variants)
        showdown_rules = {
            "holeCards": 7,  # More than available
            "communityCards": 0,
            "padding": True  # Allow partial hands
        }
        
        # Mock compare_hands to ensure best_hand is set
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, {}, showdown_rules, EvaluationType.HIGH
            )
        
        # With padding, should return whatever cards are available
        # Get the actual cards from the hand
        all_cards = mock_player.hand.get_cards()
        
        # Should return all available cards with padding
        assert len(best_hand) == len(all_cards)  # All hole cards
        assert all(card in all_cards for card in best_hand)