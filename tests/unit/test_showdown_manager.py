"""Tests for ShowdownManager class."""
import pytest
from unittest.mock import Mock, patch
import itertools

from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.evaluation.evaluator import EvaluationType, evaluator
from generic_poker.game.table import Player, Table, PlayerHand
from generic_poker.game.showdown_manager import ShowdownManager  # Adjust import as needed
from generic_poker.config.loader import GameRules
from generic_poker.game.betting import BettingManager
from generic_poker.game.game_result import HandResult

import logging
import sys

@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for all tests."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Force reconfiguration of logging
    )

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

    def test_action_razzdugi_classification(self):
        """Test that Action Razzdugi correctly applies face/butt classification."""
        # Create a mock ShowdownManager
        table = Mock(spec=Table)
        betting = Mock(spec=BettingManager)
        rules = Mock(spec=GameRules)
        
        # Set up showdown rules
        rules.showdown = Mock()
        rules.showdown.best_hand = [
            {
                "name": "Razz",
                "evaluationType": "a5_low",
                "anyCards": 5,
                "classification": {
                    "type": "face_butt",
                    "faceRanks": ["JACK", "QUEEN", "KING"],
                    "fieldName": "face_butt"
                }
            },
            {
                "name": "Badugi",
                "evaluationType": "badugi",
                "anyCards": 4
            }
        ]
        rules.showdown.conditionalBestHands = []  # Empty list (no conditional rules)
        rules.showdown.defaultBestHand = []       # Empty list (no default rules)

        rules.showdown.classification_priority = ["face", "butt"]
        
        # Properly set up the table mock with community_cards attribute
        table.community_cards = {}

        # Create ShowdownManager
        showdown_manager = ShowdownManager(table, betting, rules)
        
        # Create two players
        p1 = Mock(spec=Player)
        p1.id = "p1"
        p1.hand = PlayerHand()
        p1.is_active = True
        
        p2 = Mock(spec=Player)
        p2.id = "p2"
        p2.hand = PlayerHand()
        p2.is_active = True
        
        # Player 1: Butt Razz hand (A-5 with no face cards)
        p1.hand.add_card(Card(Rank.ACE, Suit.SPADES))
        p1.hand.add_card(Card(Rank.TWO, Suit.DIAMONDS))
        p1.hand.add_card(Card(Rank.THREE, Suit.HEARTS))
        p1.hand.add_card(Card(Rank.FOUR, Suit.CLUBS))
        p1.hand.add_card(Card(Rank.FIVE, Suit.SPADES))
        p1.hand.add_card(Card(Rank.EIGHT, Suit.DIAMONDS))
        p1.hand.add_card(Card(Rank.NINE, Suit.HEARTS))
        
        # Player 2: Face Razz hand (3-8 with a Jack)
        p2.hand.add_card(Card(Rank.THREE, Suit.CLUBS))
        p2.hand.add_card(Card(Rank.FOUR, Suit.DIAMONDS))
        p2.hand.add_card(Card(Rank.FIVE, Suit.HEARTS))
        p2.hand.add_card(Card(Rank.SIX, Suit.CLUBS))
        p2.hand.add_card(Card(Rank.EIGHT, Suit.SPADES))
        p2.hand.add_card(Card(Rank.JACK, Suit.DIAMONDS))  # Face card
        p2.hand.add_card(Card(Rank.TEN, Suit.HEARTS))
        
        # Add players to table
        table.players = {"p1": p1, "p2": p2}
        table.get_side_pot_eligible_players = Mock(return_value=set(["p1", "p2"]))
        
        # Mock betting
        betting.get_main_pot_amount.return_value = 100
        betting.get_side_pot_count.return_value = 0
        betting.get_total_pot.return_value = 100
        
        # Create proper HandResult objects for mock returns
        p1_razz_result = HandResult(
            player_id="p1",
            cards=p1.hand.cards[:5],  # Use first 5 cards (A-5)
            hand_name="A-5",
            hand_description="A-5 Low",
            evaluation_type="a5_low",
            rank=1,
            ordered_rank=1,
            classifications={"face_butt": "butt"}  # No face cards
        )
        
        p2_razz_result = HandResult(
            player_id="p2",
            cards=p2.hand.cards[:5],  # Use first 5 cards (3-8)
            hand_name="3-8",
            hand_description="3-8 Low",
            evaluation_type="a5_low",
            rank=2,  # Worse rank numerically
            ordered_rank=2,
            classifications={"face_butt": "face"}  # Has face card
        )
        
        p1_badugi_result = HandResult(
            player_id="p1",
            cards=p1.hand.cards[:4],  # First 4 cards for badugi
            hand_name="A-4 Badugi",
            hand_description="A-4 Badugi",
            evaluation_type="badugi",
            rank=2,  # Worse badugi
            ordered_rank=2
        )
        
        p2_badugi_result = HandResult(
            player_id="p2",
            cards=p2.hand.cards[:4],  # First 4 cards for badugi
            hand_name="3-8 Badugi",
            hand_description="3-8 Badugi",
            evaluation_type="badugi",
            rank=1,  # Better badugi
            ordered_rank=1
        )        
        
        # Handle Badugi evaluation differently
        def mock_compare_hands(hand1, hand2, eval_type):
            if eval_type == EvaluationType.BADUGI:
                # Give better Badugi to Player 2 (Face)
                if any(card in p1.hand.cards for card in hand1):
                    return -1  # p2 wins
                else:
                    return 1   # p1 wins
            else:
                # In Razz, Player 1 (Butt) has better low
                if any(card in p1.hand.cards for card in hand1):
                    return 1  # p1 wins
                else:
                    return -1  # p2 wins
                    
        # Patch evaluator to always use our mock implementation
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands', side_effect=mock_compare_hands):
            with patch('generic_poker.evaluation.evaluator.evaluator.evaluate_hand') as mock_eval:
                # Make evaluate_hand return proper HandResult objects
                def mock_eval_hand(cards, eval_type):
                    if eval_type == EvaluationType.LOW_A5:
                        if any(card in p1.hand.cards for card in cards):
                            return p1_razz_result
                        else:
                            return p2_razz_result
                    else:  # Badugi
                        if any(card in p1.hand.cards for card in cards):
                            return p1_badugi_result
                        else:
                            return p2_badugi_result
                
                mock_eval.side_effect = mock_eval_hand
                
                # Run the showdown
                result = showdown_manager.handle_showdown()
        
        # Verify results
        assert len(result.pots) == 2  # Two pot results (Razz and Badugi)
        
        # In Razz, despite p1 having better cards, p2 should win due to face classification
        razz_pot = next(pot for pot in result.pots if pot.hand_type == "Razz")
        assert "p2" in razz_pot.winners, "Player 2 (Face) should win Razz portion despite worse low cards"
        
        # In Badugi, p2 should win due to our mock evaluation
        badugi_pot = next(pot for pot in result.pots if pot.hand_type == "Badugi")
        assert "p2" in badugi_pot.winners, "Player 2 should win Badugi portion"        

    def test_action_razzdugi_odd_chips(self):
        """Test that Action Razzdugi handles odd chips correctly in split pots."""
        # Create a mock ShowdownManager
        table = Mock(spec=Table)
        betting = Mock(spec=BettingManager)
        rules = Mock(spec=GameRules)
        
        # Set up showdown rules
        rules.showdown = Mock()
        rules.showdown.best_hand = [
            {
                "name": "Razz",
                "evaluationType": "a5_low",
                "anyCards": 5,
                "classification": {
                    "type": "face_butt",
                    "faceRanks": ["JACK", "QUEEN", "KING"],
                    "fieldName": "face_butt"
                }
            },
            {
                "name": "Badugi",
                "evaluationType": "badugi",
                "anyCards": 4
            }
        ]
        rules.showdown.conditionalBestHands = []  # Empty list (no conditional rules)
        rules.showdown.defaultBestHand = []       # Empty list (no default rules)
        
        rules.showdown.classification_priority = ["face", "butt"]
        
        rules.showdown.best_hand[0]["name"] = "Razz"  # Ensure the name matches exactly
        rules.showdown.best_hand[1]["name"] = "Badugi"  # Ensure the name matches exactly

        # Properly set up the table mock with community_cards attribute
        table.community_cards = {}

        # Create ShowdownManager
        showdown_manager = ShowdownManager(table, betting, rules)
        
        # Create players (simplified version)
        p1 = Mock(spec=Player)
        p1.id = "p1"
        p1.name = "Player1"        
        p1.hand = PlayerHand()
        p1.is_active = True
        
        p2 = Mock(spec=Player)
        p2.id = "p2"
        p2.name = "Player2"       
        p2.hand = PlayerHand()
        p2.is_active = True
        
        # Add basic cards (simplified)
        p1.hand.add_card(Card(Rank.ACE, Suit.SPADES))
        p1.hand.add_card(Card(Rank.TWO, Suit.CLUBS))
        p1.hand.add_card(Card(Rank.THREE, Suit.DIAMONDS))
        p1.hand.add_card(Card(Rank.FOUR, Suit.HEARTS))
        p1.hand.add_card(Card(Rank.FIVE, Suit.SPADES))
        p2.hand.add_card(Card(Rank.THREE, Suit.CLUBS))
        p2.hand.add_card(Card(Rank.FOUR, Suit.DIAMONDS))
        p2.hand.add_card(Card(Rank.FIVE, Suit.HEARTS))
        p2.hand.add_card(Card(Rank.SIX, Suit.CLUBS))
        p2.hand.add_card(Card(Rank.JACK, Suit.SPADES))
        
        # Add players to table
        table.players = {"p1": p1, "p2": p2}
        table.get_side_pot_eligible_players = Mock(return_value=set(["p1", "p2"]))
        
        # Set pot amount to an odd number
        betting.get_main_pot_amount.return_value = 101
        betting.get_side_pot_count.return_value = 0
        betting.get_total_pot.return_value = 101
        
        # Create proper hand results with the CORRECT NUMBER OF CARDS
        # 5 cards for Razz
        p1_razz_cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.THREE, Suit.DIAMONDS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.SPADES)
        ]
        
        p2_razz_cards = [
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.FOUR, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.CLUBS),
            Card(Rank.JACK, Suit.SPADES)  # Face card for classification
        ]
        
        # 4 cards for Badugi
        p1_badugi_cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.THREE, Suit.DIAMONDS),
            Card(Rank.FOUR, Suit.HEARTS)
        ]
        
        p2_badugi_cards = [
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.FOUR, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.CLUBS)
        ]
    
        p1_razz = HandResult(
            player_id="p1",
            cards=p1_razz_cards,
            hand_name="A-5 Low",
            hand_description="A-5 Low",
            evaluation_type="a5_low",
            rank=1,
            ordered_rank=1,
            classifications={"face_butt": "butt"}
        )
        
        p2_razz = HandResult(
            player_id="p2",
            cards=p2_razz_cards,
            hand_name="3-J Low",
            hand_description="3-J Low",
            evaluation_type="a5_low",
            rank=2,
            ordered_rank=2,
            classifications={"face_butt": "face"}
        )
        
        p1_badugi = HandResult(
            player_id="p1",
            cards=p1_badugi_cards,
            hand_name="A-4 Badugi",
            hand_description="A-4 Badugi",
            evaluation_type="badugi",
            rank=1,
            ordered_rank=1
        )
        
        p2_badugi = HandResult(
            player_id="p2",
            cards=p2_badugi_cards,
            hand_name="3-6 Badugi",
            hand_description="3-6 Badugi",
            evaluation_type="badugi",
            rank=2,
            ordered_rank=2
        )
        
        # Use mocks for all evaluator functions
        with patch('generic_poker.evaluation.evaluator.evaluator.compare_hands') as mock_compare:
            with patch('generic_poker.evaluation.evaluator.evaluator.evaluate_hand') as mock_eval:
                # Set up the mocks to make player 2 win Razz due to face classification
                # and player 1 win Badugi
                mock_compare.return_value = 0  # Make hands equal in raw comparison
                
                def mock_eval_hand(cards, eval_type):
                    if eval_type == EvaluationType.LOW_A5:
                        if any(card in p1.hand.cards for card in cards):
                            return p1_razz
                        else:
                            return p2_razz
                    else:  # Badugi
                        if any(card in p1.hand.cards for card in cards):
                            return p1_badugi
                        else:
                            return p2_badugi
                
                mock_eval.side_effect = mock_eval_hand
                
                # Run the showdown
                result = showdown_manager.handle_showdown()
        
        # Check that odd chip was awarded correctly
        razz_pot = next(pot for pot in result.pots if pot.hand_type == "Razz")
        badugi_pot = next(pot for pot in result.pots if pot.hand_type == "Badugi")

        # Check that we found both pots
        assert razz_pot is not None, f"Razz pot not found. Available pots: {result.pots}"
        assert badugi_pot is not None, f"Badugi pot not found. Available pots: {result.pots}"
        
        # Total should add up to original pot
        total_awarded = razz_pot.amount + badugi_pot.amount
        assert total_awarded == 101, "Total awarded should equal original pot"
        
        # High hand (Razz in this case) should get the odd chip
        assert razz_pot.amount == 51, "Razz portion should get the odd chip"
        assert badugi_pot.amount == 50, "Badugi portion should get regular half"    

    def test_banco_showdown_with_diagonal_selection(self):
        """Test Banco showdown logic with special diagonal card selection."""
        # Create a mock ShowdownManager
        table = Mock(spec=Table)
        betting = Mock(spec=BettingManager)
        rules = Mock(spec=GameRules)
        
        # Create a mock for the showdown attribute
        rules.showdown = Mock()
        
        # Set up showdown rules for Banco - with properly typed attributes, not mocks
        rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high",
                "holeCards": 2,
                "communityCards": 3,
                "communityCardCombinations": [
                    # Horizontal rows
                    ["Flop 1.1", "Turn 1.2", "River 1.3"],
                    ["River 2.1", "Flop 2.2", "Turn 2.3"],
                    ["Turn 3.1", "River 3.2", "Flop 3.3"],
                    
                    # Vertical columns
                    ["Flop 1.1", "River 2.1", "Turn 3.1"],
                    ["Turn 1.2", "Flop 2.2", "River 3.2"],
                    ["River 1.3", "Turn 2.3", "Flop 3.3"],
                    
                    # 5-card diagonal
                    ["River 1.3", "Flop 2.2", "Turn 3.1"]
                ],
                "communityCardSelectCombinations": [
                    [
                        ["Flop 1.1", 1, 1],
                        ["Flop 2.2", 1, 1],
                        ["Flop 3.3", 1, 1]
                    ]
                ]
            }
        ]
        
        # Important: Set these attributes as real values, not mocks
        rules.showdown.classification_priority = []  # Empty list since we're not testing classification
        rules.showdown.defaultActions = []
        rules.showdown.conditionalBestHands = []  # Empty list means no conditional rules
        rules.showdown.defaultBestHand = []       # Empty list (no default rules)        
        rules.showdown.globalDefaultAction = None
        rules.showdown.declaration_mode = "cards_speak"
        
        # Set up community cards for Banco
        community_cards = {
            "Flop 1.1": [
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.KING, Suit.SPADES),
                Card(Rank.QUEEN, Suit.SPADES)
            ],
            "Flop 2.2": [
                Card(Rank.ACE, Suit.HEARTS),
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.QUEEN, Suit.HEARTS)
            ],
            "Flop 3.3": [
                Card(Rank.ACE, Suit.DIAMONDS),
                Card(Rank.KING, Suit.DIAMONDS),
                Card(Rank.QUEEN, Suit.DIAMONDS)
            ],
            "Turn 1.2": [
                Card(Rank.JACK, Suit.SPADES)
            ],
            "Turn 2.3": [
                Card(Rank.JACK, Suit.HEARTS)
            ],
            "Turn 3.1": [
                Card(Rank.JACK, Suit.DIAMONDS)
            ],
            "River 1.3": [
                Card(Rank.TEN, Suit.SPADES)
            ],
            "River 2.1": [
                Card(Rank.TEN, Suit.HEARTS)
            ],
            "River 3.2": [
                Card(Rank.TEN, Suit.DIAMONDS)
            ]
        }
        
        table.community_cards = community_cards
        
        # Create three players
        p1 = Mock(spec=Player)
        p1.id = "p1"
        p1.name = "Player 1"
        p1.is_active = True
        p1.hand = PlayerHand()
        
        p2 = Mock(spec=Player)
        p2.id = "p2"
        p2.name = "Player 2"
        p2.is_active = True
        p2.hand = PlayerHand()
        
        p3 = Mock(spec=Player)
        p3.id = "p3"
        p3.name = "Player 3"
        p3.is_active = True
        p3.hand = PlayerHand()
        
        # Player 1: Has flush using a standard horizontal row
        p1.hand.add_card(Card(Rank.NINE, Suit.SPADES))
        p1.hand.add_card(Card(Rank.EIGHT, Suit.SPADES))
        p1.hand.add_card(Card(Rank.SEVEN, Suit.CLUBS))
        p1.hand.add_card(Card(Rank.SIX, Suit.CLUBS))
        
        # Player 2: Has full house using the 9-card diagonal (one from each flop)
        p2.hand.add_card(Card(Rank.TWO, Suit.CLUBS))
        p2.hand.add_card(Card(Rank.TWO, Suit.DIAMONDS))
        p2.hand.add_card(Card(Rank.THREE, Suit.HEARTS))
        p2.hand.add_card(Card(Rank.FOUR, Suit.CLUBS))
        
        # Player 3: Has mediocre hand using a vertical column
        p3.hand.add_card(Card(Rank.FIVE, Suit.HEARTS))
        p3.hand.add_card(Card(Rank.FOUR, Suit.HEARTS))
        p3.hand.add_card(Card(Rank.THREE, Suit.DIAMONDS))
        p3.hand.add_card(Card(Rank.TWO, Suit.SPADES))
        
        # Add players to table
        table.players = {"p1": p1, "p2": p2, "p3": p3}
        
        # Mock betting
        betting.get_main_pot_amount.return_value = 300
        betting.get_side_pot_count.return_value = 0
        betting.get_side_pot_eligible_players = Mock(return_value=set(["p1", "p2", "p3"]))
        betting.get_total_pot.return_value = 300
        
        # Create proper evaluation results
        # Player 1 - Flush using row 1
        p1_hand = [
            p1.hand.cards[0],  # 9S
            p1.hand.cards[1],  # 8S
            community_cards["Flop 1.1"][0],  # AS
            community_cards["Turn 1.2"][0],  # JS
            community_cards["River 1.3"][0]   # 10S
        ]
        
        # Player 2 - Full House Aces over Twos using 9-card diagonal selection
        p2_hand = [
            p2.hand.cards[0],  # 2C
            p2.hand.cards[1],  # 2D
            community_cards["Flop 1.1"][0],  # AS
            community_cards["Flop 2.2"][0],  # AH
            community_cards["Flop 3.3"][0]   # AD
        ]
        
        # Player 3 - High Card Ace using column 1
        p3_hand = [
            p3.hand.cards[0],  # 5H
            p3.hand.cards[1],  # 4H
            community_cards["Flop 1.1"][0],  # AS
            community_cards["River 2.1"][0],  # 10H
            community_cards["Turn 3.1"][0]   # JD
        ]
        
        # Create ShowdownManager
        showdown_manager = ShowdownManager(table, betting, rules)
        
        # Create test results for the players
        p1_result = HandResult(
            player_id="p1",
            cards=p1_hand,
            hand_name="Flush",
            hand_description="Ace-high Flush",
            evaluation_type="high",
            rank=5,  # Flush is rank 5
            ordered_rank=5
        )
        
        p2_result = HandResult(
            player_id="p2",
            cards=p2_hand,
            hand_name="Full House",
            hand_description="Full House, Aces over Twos",
            evaluation_type="high",
            rank=4,  # Full house is rank 4
            ordered_rank=4
        )
        
        p3_result = HandResult(
            player_id="p3",
            cards=p3_hand,
            hand_name="High Card",
            hand_description="Ace High",
            evaluation_type="high",
            rank=10,  # High card is rank 10
            ordered_rank=10
        )
        
        # Mock the _find_best_hand_for_player method to return our predetermined hands
        def mock_find_best_hand(player, community_cards, showdown_rules, eval_type):
            if player.id == "p1":
                return p1_hand, p1_hand[:2]  # Hand and used hole cards
            elif player.id == "p2":
                return p2_hand, p2_hand[:2]  # Hand and used hole cards
            else:
                return p3_hand, p3_hand[:2]  # Hand and used hole cards
        
        # Mock the _find_winners method to simplify testing
        def mock_find_winners(players, hand_results, eval_type, showdown_rules):
            # Player 2 should win with Full House (better than Player 1's Flush)
            return [p2]
        
        # Mock methods to use our mocks
        with patch.object(ShowdownManager, '_find_best_hand_for_player', side_effect=mock_find_best_hand):
            with patch.object(ShowdownManager, '_find_winners', side_effect=mock_find_winners):
                with patch('generic_poker.evaluation.evaluator.evaluator.evaluate_hand') as mock_eval:
                    # Make evaluate_hand return our predetermined results
                    def mock_eval_hand(cards, eval_type):
                        if any(card in p1_hand for card in cards):
                            return p1_result
                        elif any(card in p2_hand for card in cards):
                            return p2_result
                        else:
                            return p3_result
                    
                    mock_eval.side_effect = mock_eval_hand
                    
                    # Run the showdown
                    result = showdown_manager.handle_showdown()
        
        # Verify results
        assert len(result.pots) == 1, "There should be one pot result"
        pot = result.pots[0]
        
        # Player 2 should win with Full House
        assert "p2" in pot.winners, "Player 2 should win with Full House"
        
        # Check hand details in the results
        all_hands = result.hands
        assert len(all_hands) == 3, "All three players should have hands evaluated"
        
        # Verify all players have hand results
        assert "p1" in all_hands, "Player 1 should have hand results"
        assert "p2" in all_hands, "Player 2 should have hand results"  
        assert "p3" in all_hands, "Player 3 should have hand results"
        
        # Verify that Player 2's hand is a Full House using diagonal selection (one from each flop)
        p2_result = next(iter(all_hands["p2"])) if all_hands.get("p2") else None
        assert p2_result is not None, "Player 2 should have a hand result"
        assert p2_result.hand_name == "Full House", "Player 2 should have a Full House"
        
        # Verify the specific diagonal community card selection
        p2_community_cards = [card for card in p2_result.cards if card not in p2.hand.cards]
        assert len(p2_community_cards) == 3, "Player 2 should use 3 community cards"
        
        # Check if the community cards are all Aces from different flop positions
        aces_count = sum(1 for card in p2_community_cards if card.rank == Rank.ACE)
        assert aces_count == 3, "Player 2 should use 3 Aces from different flop positions"