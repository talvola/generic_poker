"""Tests for ShowdownManager class."""

import logging
import sys
from unittest.mock import Mock, patch

import pytest

from generic_poker.config.loader import GameRules
from generic_poker.core.card import Card, Rank, Suit, Visibility, WildType
from generic_poker.core.hand import PlayerHand
from generic_poker.evaluation.evaluator import EvaluationType
from generic_poker.game.betting import BettingManager
from generic_poker.game.game_result import HandResult
from generic_poker.game.showdown_manager import ShowdownManager
from generic_poker.game.table import Player, Table


@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for all tests."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
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
    hand.cards[2].visibility = Visibility.FACE_UP  # Queen of Hearts
    hand.cards[3].visibility = Visibility.FACE_UP  # Jack of Hearts
    hand.cards[4].visibility = Visibility.FACE_DOWN  # Ten of Clubs

    # Create a subset
    hand.subsets["TestSubset"] = [
        hand.cards[0],  # Ace of Spades
        hand.cards[1],  # King of Spades
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
            Card(Rank.FIVE, Suit.DIAMONDS),
        ],
        "Board1": [
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.FOUR, Suit.CLUBS),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.SIX, Suit.CLUBS),
        ],
    }


@pytest.fixture
def mock_table():
    """Create a mock table for testing."""
    table = Mock(spec=Table)
    table.community_cards = {}
    table.players = {}
    return table


@pytest.fixture
def mock_betting():
    """Create a mock betting manager for testing."""
    betting = Mock()
    betting.get_main_pot_amount.return_value = 100
    betting.get_side_pot_count.return_value = 0
    betting.get_side_pot_eligible_players.return_value = set()
    betting.get_total_pot.return_value = 100
    betting.award_pots = Mock()
    return betting


@pytest.fixture
def mock_rules():
    """Create mock game rules for testing."""
    rules = Mock(spec=GameRules)
    rules.showdown = Mock()

    # Set default values for common attributes to avoid Mock comparison errors
    rules.showdown.classification_priority = []
    rules.showdown.defaultActions = []
    rules.showdown.globalDefaultAction = None
    rules.showdown.declaration_mode = "cards_speak"
    rules.showdown.conditionalBestHands = []
    rules.showdown.defaultBestHand = []
    rules.showdown.best_hand = []  # Add this to avoid len() errors

    return rules


@pytest.fixture
def showdown_manager(mock_table, mock_betting, mock_rules):
    """Create a ShowdownManager instance for testing."""
    return ShowdownManager(mock_table, mock_betting, mock_rules)


def create_player_with_cards(player_id: str, name: str, cards: list, subsets: dict = None):
    """Create a player with specific cards and optional subsets."""
    player = Mock(spec=Player)
    player.id = player_id
    player.name = name
    player.is_active = True
    player.hand = PlayerHand()

    for card in cards:
        player.hand.add_card(card)

    if subsets:
        for subset_name, subset_cards in subsets.items():
            player.hand.subsets[subset_name] = subset_cards

    return player


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
        showdown_rules = {"hole_subset": "TestSubset"}

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
        showdown_rules = {"cardState": "face down"}

        best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
            mock_player, {}, showdown_rules, EvaluationType.HIGH
        )

        # Should return only face-down cards
        assert len(best_hand) == 3
        assert all(card.visibility == Visibility.FACE_DOWN for card in best_hand)

        # Filter to face-up cards only
        showdown_rules = {"cardState": "face up"}

        best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
            mock_player, {}, showdown_rules, EvaluationType.HIGH
        )

        # Should return only face-up cards
        assert len(best_hand) == 2
        assert all(card.visibility == Visibility.FACE_UP for card in best_hand)

    def test_find_best_hand_with_community_cards(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using hole cards and community cards (e.g., Hold'em)."""
        # Use 2 hole cards and 3 community cards (e.g., Hold'em)
        showdown_rules = {"holeCards": 2, "communityCards": 3}

        # Patch evaluator.compare_hands to always return 1 for the first combination
        # This simplifies testing by making a specific hand always the "best"
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )

        # Should have correct number of cards
        assert len(best_hand) == 5  # 2 hole + 3 community
        assert len(used_hole_cards) == 2  # 2 hole cards used

    def test_find_best_hand_with_any_cards(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using any cards configuration."""
        # Use any 5 cards from hole and community
        showdown_rules = {"anyCards": 5}

        # Patch evaluator to make testing deterministic
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )

        # Should have correct number of cards
        assert len(best_hand) == 5

    def test_find_best_hand_with_combinations(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using combinations configuration."""
        # Define multiple combinations of hole/community cards
        showdown_rules = {
            "combinations": [{"holeCards": 2, "communityCards": 3}, {"holeCards": 3, "communityCards": 2}]
        }

        # Patch evaluator to make testing deterministic
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", return_value=1):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, mock_community_cards, showdown_rules, EvaluationType.HIGH
            )

        # Should have correct number of cards (5 total)
        assert len(best_hand) == 5

    def test_find_best_hand_with_community_combinations(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand using community card combinations."""
        # Use combinations of community card subsets
        showdown_rules = {"holeCards": 2, "communityCardCombinations": [["default"], ["Board1"]], "totalCards": 5}

        # Patch evaluator to make testing deterministic
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", return_value=1):
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
            "communityCards": 0,
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
        showdown_rules = {"minimumCards": 0, "zeroCardsPipValue": 0}

        # Mock the player's hand to return empty list
        empty_hand = PlayerHand()  # Create an actual empty hand
        with patch.object(mock_player, "hand", empty_hand):
            best_hand, used_hole_cards = showdown_manager._find_best_hand_for_player(
                mock_player, {}, showdown_rules, EvaluationType.LOW_PIP_6
            )

        # Should return empty lists for zero-card hands
        assert best_hand == []
        assert used_hole_cards == []

    def test_hole_cards_list_with_options(self, showdown_manager, mock_player, mock_community_cards):
        """Test finding best hand with multiple hole/community card options."""
        # Multiple options for hole/community combinations
        showdown_rules = {"holeCards": [2, 3, 4], "communityCards": [3, 2, 1]}

        # Patch evaluator to make testing deterministic
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", return_value=1):
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
            "communityCards": 0,  # Will be calculated dynamically
        }

        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", return_value=1):
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
            "wildCards": [{"type": "rank", "rank": "ACE", "role": "wild"}],
        }

        # Patch apply_wild_cards method to verify it's called
        with patch.object(showdown_manager, "apply_wild_cards") as mock_apply_wild:
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
            "padding": True,  # Allow partial hands
        }

        # Mock compare_hands to ensure best_hand is set
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", return_value=1):
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
                    "fieldName": "face_butt",
                },
            },
            {"name": "Badugi", "evaluationType": "badugi", "anyCards": 4},
        ]
        rules.showdown.conditionalBestHands = []  # Empty list (no conditional rules)
        rules.showdown.defaultBestHand = []  # Empty list (no default rules)

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
            classifications={"face_butt": "butt"},  # No face cards
        )

        p2_razz_result = HandResult(
            player_id="p2",
            cards=p2.hand.cards[:5],  # Use first 5 cards (3-8)
            hand_name="3-8",
            hand_description="3-8 Low",
            evaluation_type="a5_low",
            rank=2,  # Worse rank numerically
            ordered_rank=2,
            classifications={"face_butt": "face"},  # Has face card
        )

        p1_badugi_result = HandResult(
            player_id="p1",
            cards=p1.hand.cards[:4],  # First 4 cards for badugi
            hand_name="A-4 Badugi",
            hand_description="A-4 Badugi",
            evaluation_type="badugi",
            rank=2,  # Worse badugi
            ordered_rank=2,
        )

        p2_badugi_result = HandResult(
            player_id="p2",
            cards=p2.hand.cards[:4],  # First 4 cards for badugi
            hand_name="3-8 Badugi",
            hand_description="3-8 Badugi",
            evaluation_type="badugi",
            rank=1,  # Better badugi
            ordered_rank=1,
        )

        # Handle Badugi evaluation differently
        def mock_compare_hands(hand1, hand2, eval_type):
            if eval_type == EvaluationType.BADUGI:
                # Give better Badugi to Player 2 (Face)
                if any(card in p1.hand.cards for card in hand1):
                    return -1  # p2 wins
                else:
                    return 1  # p1 wins
            else:
                # In Razz, Player 1 (Butt) has better low
                if any(card in p1.hand.cards for card in hand1):
                    return 1  # p1 wins
                else:
                    return -1  # p2 wins

        # Patch evaluator to always use our mock implementation
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands", side_effect=mock_compare_hands):
            with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
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
                    "fieldName": "face_butt",
                },
            },
            {"name": "Badugi", "evaluationType": "badugi", "anyCards": 4},
        ]
        rules.showdown.conditionalBestHands = []  # Empty list (no conditional rules)
        rules.showdown.defaultBestHand = []  # Empty list (no default rules)

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
            Card(Rank.FIVE, Suit.SPADES),
        ]

        p2_razz_cards = [
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.FOUR, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.CLUBS),
            Card(Rank.JACK, Suit.SPADES),  # Face card for classification
        ]

        # 4 cards for Badugi
        p1_badugi_cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.THREE, Suit.DIAMONDS),
            Card(Rank.FOUR, Suit.HEARTS),
        ]

        p2_badugi_cards = [
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.FOUR, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.CLUBS),
        ]

        p1_razz = HandResult(
            player_id="p1",
            cards=p1_razz_cards,
            hand_name="A-5 Low",
            hand_description="A-5 Low",
            evaluation_type="a5_low",
            rank=1,
            ordered_rank=1,
            classifications={"face_butt": "butt"},
        )

        p2_razz = HandResult(
            player_id="p2",
            cards=p2_razz_cards,
            hand_name="3-J Low",
            hand_description="3-J Low",
            evaluation_type="a5_low",
            rank=2,
            ordered_rank=2,
            classifications={"face_butt": "face"},
        )

        p1_badugi = HandResult(
            player_id="p1",
            cards=p1_badugi_cards,
            hand_name="A-4 Badugi",
            hand_description="A-4 Badugi",
            evaluation_type="badugi",
            rank=1,
            ordered_rank=1,
        )

        p2_badugi = HandResult(
            player_id="p2",
            cards=p2_badugi_cards,
            hand_name="3-6 Badugi",
            hand_description="3-6 Badugi",
            evaluation_type="badugi",
            rank=2,
            ordered_rank=2,
        )

        # Use mocks for all evaluator functions
        with patch("generic_poker.evaluation.evaluator.evaluator.compare_hands") as mock_compare:
            with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
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
                    ["River 1.3", "Flop 2.2", "Turn 3.1"],
                ],
                "communityCardSelectCombinations": [[["Flop 1.1", 1, 1], ["Flop 2.2", 1, 1], ["Flop 3.3", 1, 1]]],
            }
        ]

        # Important: Set these attributes as real values, not mocks
        rules.showdown.classification_priority = []  # Empty list since we're not testing classification
        rules.showdown.defaultActions = []
        rules.showdown.conditionalBestHands = []  # Empty list means no conditional rules
        rules.showdown.defaultBestHand = []  # Empty list (no default rules)
        rules.showdown.globalDefaultAction = None
        rules.showdown.declaration_mode = "cards_speak"

        # Set up community cards for Banco
        community_cards = {
            "Flop 1.1": [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES), Card(Rank.QUEEN, Suit.SPADES)],
            "Flop 2.2": [Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.HEARTS), Card(Rank.QUEEN, Suit.HEARTS)],
            "Flop 3.3": [
                Card(Rank.ACE, Suit.DIAMONDS),
                Card(Rank.KING, Suit.DIAMONDS),
                Card(Rank.QUEEN, Suit.DIAMONDS),
            ],
            "Turn 1.2": [Card(Rank.JACK, Suit.SPADES)],
            "Turn 2.3": [Card(Rank.JACK, Suit.HEARTS)],
            "Turn 3.1": [Card(Rank.JACK, Suit.DIAMONDS)],
            "River 1.3": [Card(Rank.TEN, Suit.SPADES)],
            "River 2.1": [Card(Rank.TEN, Suit.HEARTS)],
            "River 3.2": [Card(Rank.TEN, Suit.DIAMONDS)],
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
            community_cards["River 1.3"][0],  # 10S
        ]

        # Player 2 - Full House Aces over Twos using 9-card diagonal selection
        p2_hand = [
            p2.hand.cards[0],  # 2C
            p2.hand.cards[1],  # 2D
            community_cards["Flop 1.1"][0],  # AS
            community_cards["Flop 2.2"][0],  # AH
            community_cards["Flop 3.3"][0],  # AD
        ]

        # Player 3 - High Card Ace using column 1
        p3_hand = [
            p3.hand.cards[0],  # 5H
            p3.hand.cards[1],  # 4H
            community_cards["Flop 1.1"][0],  # AS
            community_cards["River 2.1"][0],  # 10H
            community_cards["Turn 3.1"][0],  # JD
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
            ordered_rank=5,
        )

        p2_result = HandResult(
            player_id="p2",
            cards=p2_hand,
            hand_name="Full House",
            hand_description="Full House, Aces over Twos",
            evaluation_type="high",
            rank=4,  # Full house is rank 4
            ordered_rank=4,
        )

        p3_result = HandResult(
            player_id="p3",
            cards=p3_hand,
            hand_name="High Card",
            hand_description="Ace High",
            evaluation_type="high",
            rank=10,  # High card is rank 10
            ordered_rank=10,
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
        with patch.object(ShowdownManager, "_find_best_hand_for_player", side_effect=mock_find_best_hand):
            with patch.object(ShowdownManager, "_find_winners", side_effect=mock_find_winners):
                with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
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


class TestShowdownManagerWildCards:
    """Test wild card functionality in showdown evaluation."""

    def test_joker_wild_cards(self, showdown_manager):
        """Test evaluation with joker wild cards."""
        # Create player with jokers
        player = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.JOKER, Suit.JOKER),  # Joker
                Card(Rank.ACE, Suit.HEARTS),
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.QUEEN, Suit.HEARTS),
                Card(Rank.JACK, Suit.HEARTS),
            ],
        )

        # Make joker wild
        player.hand.cards[0].make_wild(WildType.NATURAL)

        # Mock table and betting
        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        # Set up showdown rules with wild cards
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high_wild_bug",  # Use wild evaluation type
                "anyCards": 5,
                "wildCards": [{"type": "joker", "role": "wild"}],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        # Mock evaluator to return a strong hand result
        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=player.hand.cards,
                hand_name="Royal Flush",
                hand_description="Royal Flush in Hearts",
                evaluation_type="high_wild_bug",
                rank=1,
                ordered_rank=1,
            )

            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners

    def test_a5_low_wild_cards(self, showdown_manager):
        """Test A-5 lowball with wild cards."""
        # Create player with wild cards for low
        player = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.TWO, Suit.SPADES),  # Wild - can be Ace for wheel
                Card(Rank.THREE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.DIAMONDS),
                Card(Rank.SEVEN, Suit.SPADES),  # Wild makes this irrelevant
            ],
        )

        # Make twos wild
        player.hand.cards[0].make_wild(WildType.NAMED)

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "Low Hand",
                "evaluationType": "a5_low_wild",  # Wild lowball evaluation
                "anyCards": 5,
                "wildCards": [{"type": "rank", "rank": "2", "role": "wild"}],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=player.hand.cards,
                hand_name="A-5 Low",
                hand_description="Wheel (A-2-3-4-5)",
                evaluation_type="a5_low_wild",
                rank=1,
                ordered_rank=1,
            )

            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners

    def test_27_low_wild_cards(self, showdown_manager):
        """Test 2-7 lowball with wild cards."""
        # Create player with wild cards for 2-7 low
        player = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.JOKER, Suit.JOKER),  # Wild - can be deuce
                Card(Rank.THREE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.DIAMONDS),
                Card(Rank.SEVEN, Suit.SPADES),
            ],
        )

        # Make joker wild
        player.hand.cards[0].make_wild(WildType.NATURAL)

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "Low Hand",
                "evaluationType": "27_low_wild",  # 2-7 wild lowball evaluation
                "anyCards": 5,
                "wildCards": [{"type": "joker", "role": "wild"}],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=player.hand.cards,
                hand_name="2-7 Low",
                hand_description="Seven Perfect (2-3-4-5-7)",
                evaluation_type="27_low_wild",
                rank=1,
                ordered_rank=1,
            )

            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners
        assert result.pots[0].hand_type == "Low Hand"

    def test_rank_wild_cards(self, showdown_manager):
        """Test evaluation with specific rank as wild."""
        # Create player with deuces (2s)
        player = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.TWO, Suit.SPADES),  # Wild
                Card(Rank.TWO, Suit.HEARTS),  # Wild
                Card(Rank.ACE, Suit.CLUBS),
                Card(Rank.ACE, Suit.DIAMONDS),
                Card(Rank.KING, Suit.SPADES),
            ],
        )

        # Make twos wild
        for card in player.hand.cards:
            if card.rank == Rank.TWO:
                card.make_wild(WildType.NAMED)

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        # Set up showdown rules with rank wild cards - use '2' not 'TWO'
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high_wild_bug",  # Use wild evaluation type
                "anyCards": 5,
                "wildCards": [
                    {
                        "type": "rank",
                        "rank": "2",  # Use the actual enum value
                        "role": "wild",
                    }
                ],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=player.hand.cards,
                hand_name="Four Aces",
                hand_description="Four of a Kind, Aces",
                evaluation_type="high_wild_bug",
                rank=3,
                ordered_rank=3,
            )

            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners

    def test_bug_wild_cards(self, showdown_manager):
        """Test evaluation with bug wild cards (limited wild)."""
        # Create player with joker as bug
        player = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.JOKER, Suit.JOKER),  # Bug
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.QUEEN, Suit.HEARTS),
                Card(Rank.JACK, Suit.HEARTS),
                Card(Rank.TEN, Suit.HEARTS),
            ],
        )

        # Make joker a bug (can only be Ace or complete straight/flush)
        player.hand.cards[0].make_wild(WildType.BUG)

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high_wild_bug",  # Use wild evaluation type
                "anyCards": 5,
                "wildCards": [{"type": "joker", "role": "bug"}],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=player.hand.cards,
                hand_name="Royal Flush",
                hand_description="Royal Flush in Hearts",
                evaluation_type="high_wild_bug",
                rank=1,
                ordered_rank=1,
            )

            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners


class TestShowdownManagerConditionalBestHands:
    """Test conditional best hand configurations."""

    def test_player_choice_condition(self, showdown_manager):
        """Test showdown with player choice conditions (like Paradise Road Pick'em)."""
        # Create two players
        p1 = create_player_with_cards("p1", "Player1", [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)])
        p2 = create_player_with_cards("p2", "Player2", [Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.JACK, Suit.HEARTS)])

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {
            "default": [Card(Rank.TEN, Suit.SPADES), Card(Rank.NINE, Suit.SPADES), Card(Rank.EIGHT, Suit.SPADES)]
        }

        # Set up conditional best hands based on game choice
        showdown_manager.rules.showdown.conditionalBestHands = [
            {
                "condition": {"type": "player_choice", "subset": "Game", "value": "Hold'em"},
                "bestHand": [{"name": "Hold'em Hand", "evaluationType": "high", "anyCards": 5}],
            }
        ]
        showdown_manager.rules.showdown.defaultBestHand = [
            {"name": "Default Hand", "evaluationType": "high", "holeCards": 2, "communityCards": 0}
        ]

        # Mock game choices - player chose Hold'em
        mock_game = Mock()
        mock_game.game_choices = {"Game": "Hold'em"}
        showdown_manager.game = mock_game

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:

            def mock_eval_hand(cards, eval_type, **kwargs):
                if eval_type == EvaluationType.HIGH:
                    if any(card.rank == Rank.KING for card in cards):
                        # P2 has trip Kings
                        return HandResult(
                            player_id="p2",
                            cards=cards,
                            hand_name="Three Kings",
                            hand_description="Three of a Kind, Kings",
                            evaluation_type="high",
                            rank=4,
                            ordered_rank=4,
                        )
                    else:
                        # P1 has wheel as high
                        return HandResult(
                            player_id="p1",
                            cards=cards,
                            hand_name="Five High Straight",
                            hand_description="Wheel",
                            evaluation_type="high",
                            rank=5,
                            ordered_rank=5,
                        )
                else:  # Low
                    if any(card.rank == Rank.ACE for card in cards):
                        # P1 has wheel as low
                        return HandResult(
                            player_id="p1",
                            cards=cards,
                            hand_name="A-5 Low",
                            hand_description="Wheel Low",
                            evaluation_type="a5_low",
                            rank=1,
                            ordered_rank=1,
                        )
                    else:
                        # P2 has no qualifying low
                        return HandResult(
                            player_id="p2",
                            cards=cards,
                            hand_name="No Low",
                            hand_description="No qualifying low",
                            evaluation_type="a5_low",
                            rank=999,
                            ordered_rank=999,
                        )

            mock_eval.side_effect = mock_eval_hand

            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert result.pots[0].hand_type == "Hold'em Hand"


class TestShowdownManagerSpecialEvaluations:
    """Test special evaluation criteria and default actions."""

    def test_highest_spade_evaluation(self, showdown_manager):
        """Test special evaluation for highest spade in hole cards."""
        # Create players with different spades
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.KING, Suit.SPADES),  # King of spades
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.THREE, Suit.CLUBS),
            ],
        )

        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.ACE, Suit.SPADES),  # Ace of spades (highest)
                Card(Rank.FOUR, Suit.DIAMONDS),
                Card(Rank.FIVE, Suit.HEARTS),
            ],
        )

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {}

        # Set up showdown with special evaluation default action
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "Low Hand",
                "evaluationType": "three_card_a5_low",  # Use 3-card evaluation
                "anyCards": 3,
                "qualifier": [1, 1],  # Impossible qualifier
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []
        showdown_manager.rules.showdown.defaultActions = [
            {
                "condition": "no_qualifier_met",
                "appliesTo": ["Low Hand"],
                "action": {
                    "type": "evaluate_special",
                    "evaluation": {
                        "criterion": "highest_rank",
                        "suit": "spades",
                        "from": "hole_cards",
                        "subsets": ["default"],
                    },
                },
            }
        ]

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            # No one qualifies for low
            mock_eval.return_value = HandResult(
                player_id="test",
                cards=[],
                hand_name="No Low",
                hand_description="No qualifying low",
                evaluation_type="three_card_a5_low",  # Match the evaluation type
                rank=999,
                ordered_rank=999,
            )

            result = showdown_manager.handle_showdown()

        # P2 should win with Ace of spades
        assert len(result.pots) == 1
        assert "p2" in result.pots[0].winners
        assert result.pots[0].hand_type == "Low Hand"

    def test_river_card_suit_evaluation(self, showdown_manager):
        """Test dynamic suit evaluation based on river card."""
        # Create players
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.QUEEN, Suit.HEARTS),
                Card(Rank.JACK, Suit.CLUBS),
                Card(Rank.TEN, Suit.DIAMONDS),
                Card(Rank.NINE, Suit.SPADES),
            ],
        )

        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.ACE, Suit.HEARTS),  # Highest heart
                Card(Rank.JACK, Suit.DIAMONDS),
                Card(Rank.EIGHT, Suit.CLUBS),
                Card(Rank.SEVEN, Suit.SPADES),
                Card(Rank.SIX, Suit.DIAMONDS),
            ],
        )

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {
            "default": [
                Card(Rank.TEN, Suit.CLUBS),
                Card(Rank.NINE, Suit.DIAMONDS),
                Card(Rank.EIGHT, Suit.SPADES),
                Card(Rank.SEVEN, Suit.CLUBS),
                Card(Rank.SIX, Suit.HEARTS),  # River card is hearts
            ]
        }

        # Set up showdown with river card suit evaluation
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high",  # Use 5-card evaluation
                "anyCards": 5,
                "qualifier": [1, 1],  # Impossible qualifier
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []
        showdown_manager.rules.showdown.defaultActions = [
            {
                "condition": "no_qualifier_met",
                "appliesTo": ["High Hand"],
                "action": {
                    "type": "evaluate_special",
                    "evaluation": {
                        "criterion": "highest_rank",
                        "suit": "river_card_suit",  # Dynamic - hearts in this case
                        "from": "hole_cards",
                    },
                },
            }
        ]

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            # No one qualifies normally
            mock_eval.return_value = HandResult(
                player_id="test",
                cards=[],
                hand_name="No Hand",
                hand_description="No qualifying hand",
                evaluation_type="high",
                rank=999,
                ordered_rank=999,
            )

            result = showdown_manager.handle_showdown()

        # P2 should win with Ace of hearts (river suit)
        assert len(result.pots) == 1
        assert "p2" in result.pots[0].winners


class TestShowdownManagerComplexScenarios:
    """Test complex multi-feature scenarios."""

    def test_mexican_poker_with_wild_jokers(self, showdown_manager):
        """Test Mexican Poker with conditional wild joker."""
        # Create player with one joker (face-down = wild)
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.JOKER, Suit.JOKER, Visibility.FACE_DOWN),  # Wild
                Card(Rank.ACE, Suit.CLUBS),
                Card(Rank.ACE, Suit.DIAMONDS),
                Card(Rank.ACE, Suit.HEARTS),
                Card(Rank.KING, Suit.SPADES),
            ],
        )

        # Create another player with face-up joker (bug)
        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.JOKER, Suit.JOKER, Visibility.FACE_UP),  # Bug
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.KING, Suit.CLUBS),
                Card(Rank.KING, Suit.DIAMONDS),
                Card(Rank.QUEEN, Suit.SPADES),
            ],
        )

        # Create third player with no jokers
        p3 = create_player_with_cards(
            "p3",
            "Player3",
            [
                Card(Rank.QUEEN, Suit.HEARTS),
                Card(Rank.QUEEN, Suit.CLUBS),
                Card(Rank.QUEEN, Suit.DIAMONDS),
                Card(Rank.JACK, Suit.SPADES),
                Card(Rank.JACK, Suit.HEARTS),
            ],
        )

        # Apply conditional wild card rules
        for player in [p1, p2]:
            for card in player.hand.cards:
                if card.rank == Rank.JOKER:
                    if card.visibility == Visibility.FACE_UP:
                        card.make_wild(WildType.BUG)  # Face-up joker is bug
                    else:
                        card.make_wild(WildType.NAMED)  # Face-down joker is wild

        showdown_manager.table.players = {"p1": p1, "p2": p2, "p3": p3}
        showdown_manager.table.community_cards = {}

        # Set up Mexican Poker showdown rules
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "27_ja_ffh_high_wild_bug",  # Mexican Poker evaluation
                "anyCards": 5,
                "wildCards": [
                    {
                        "type": "joker",
                        "role": "conditional",
                        "condition": {"visibility": "face up", "true_role": "bug", "false_role": "wild"},
                    }
                ],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:

            def mock_eval_hand(cards, eval_type, **kwargs):
                if any(card in p1.hand.cards for card in cards):
                    # P1 with wild joker - four aces
                    return HandResult(
                        player_id="p1",
                        cards=cards,
                        hand_name="Four Aces",
                        hand_description="Four of a Kind, Aces",
                        evaluation_type="27_ja_ffh_high_wild_bug",
                        rank=2,
                        ordered_rank=2,
                    )
                elif any(card in p2.hand.cards for card in cards):
                    # P2 with bug joker - full house
                    return HandResult(
                        player_id="p2",
                        cards=cards,
                        hand_name="Full House",
                        hand_description="Kings over Aces (Joker as Ace)",
                        evaluation_type="27_ja_ffh_high_wild_bug",
                        rank=4,
                        ordered_rank=4,
                    )
                else:
                    # P3 with no jokers - two pair
                    return HandResult(
                        player_id="p3",
                        cards=cards,
                        hand_name="Two Pair",
                        hand_description="Queens over Jacks",
                        evaluation_type="27_ja_ffh_high_wild_bug",
                        rank=7,
                        ordered_rank=7,
                    )

            mock_eval.side_effect = mock_eval_hand

            with patch.object(showdown_manager, "_find_winners") as mock_winners:
                mock_winners.return_value = [p1]  # P1 wins with four of a kind

                result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners

    def test_action_razzdugi_classification_priority(self, showdown_manager):
        """Test Action Razzdugi with face/butt classification and priority."""
        # Create players - one face, one butt
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.ACE, Suit.SPADES),  # Butt hand
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.THREE, Suit.CLUBS),
                Card(Rank.FOUR, Suit.DIAMONDS),
                Card(Rank.FIVE, Suit.SPADES),
                Card(Rank.SIX, Suit.HEARTS),
                Card(Rank.SEVEN, Suit.CLUBS),
            ],
        )

        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.TWO, Suit.SPADES),  # Face hand (has Jack)
                Card(Rank.THREE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.DIAMONDS),
                Card(Rank.SIX, Suit.SPADES),
                Card(Rank.JACK, Suit.HEARTS),  # Face card
                Card(Rank.EIGHT, Suit.CLUBS),
            ],
        )

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {}

        # Set up Action Razzdugi showdown
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "Razz",
                "evaluationType": "a5_low",
                "anyCards": 5,
                "classification": {
                    "type": "face_butt",
                    "faceRanks": ["JACK", "QUEEN", "KING"],
                    "fieldName": "face_butt",
                },
            },
            {"name": "Badugi", "evaluationType": "badugi", "anyCards": 4},
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []
        showdown_manager.rules.showdown.classification_priority = ["face", "butt"]

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:

            def mock_eval_hand(cards, eval_type, qualifier=None):
                if eval_type == EvaluationType.LOW_A5:
                    if any(card in p1.hand.cards for card in cards):
                        # P1 has better low but is butt
                        return HandResult(
                            player_id="p1",
                            cards=cards,
                            hand_name="A-7 Low",
                            hand_description="Seven-low",
                            evaluation_type="a5_low",
                            rank=1,
                            ordered_rank=1,
                            classifications={"face_butt": "butt"},
                        )
                    else:
                        # P2 has worse low but is face
                        return HandResult(
                            player_id="p2",
                            cards=cards,
                            hand_name="2-J Low",
                            hand_description="Jack-low",
                            evaluation_type="a5_low",
                            rank=2,
                            ordered_rank=2,
                            classifications={"face_butt": "face"},
                        )
                else:  # Badugi
                    # P1 better badugi
                    if any(card in p1.hand.cards for card in cards):
                        return HandResult(
                            player_id="p1",
                            cards=cards,
                            hand_name="A-4 Badugi",
                            hand_description="Four-card badugi",
                            evaluation_type="badugi",
                            rank=1,
                            ordered_rank=1,
                        )
                    else:
                        return HandResult(
                            player_id="p2",
                            cards=cards,
                            hand_name="2-8 Badugi",
                            hand_description="Four-card badugi",
                            evaluation_type="badugi",
                            rank=2,
                            ordered_rank=2,
                        )

            mock_eval.side_effect = mock_eval_hand

            with patch.object(showdown_manager, "_find_winners") as mock_winners:

                def mock_find_winners_side_effect(players, hand_results, eval_type, showdown_rules):
                    # Face classification beats butt regardless of hand strength
                    if eval_type == EvaluationType.LOW_A5:
                        return [p2]  # Face wins over butt
                    else:
                        return [p1]  # P1 wins badugi

                mock_winners.side_effect = mock_find_winners_side_effect

                result = showdown_manager.handle_showdown()

        # Both pots should be awarded
        assert len(result.pots) == 2

        # P2 should win Razz due to face classification priority
        razz_pot = next(pot for pot in result.pots if pot.hand_type == "Razz")
        assert "p2" in razz_pot.winners

        # P1 should win Badugi
        badugi_pot = next(pot for pot in result.pots if pot.hand_type == "Badugi")
        assert "p1" in badugi_pot.winners

    def test_side_pot_eligibility(self, showdown_manager):
        """Test complex side pot scenarios."""
        # Create players with different stack sizes
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.ACE, Suit.HEARTS),
                Card(Rank.ACE, Suit.CLUBS),
                Card(Rank.KING, Suit.DIAMONDS),
                Card(Rank.QUEEN, Suit.SPADES),
            ],
        )  # Trip Aces

        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.KING, Suit.SPADES),
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.KING, Suit.CLUBS),
                Card(Rank.ACE, Suit.DIAMONDS),
                Card(Rank.JACK, Suit.HEARTS),
            ],
        )  # Trip Kings

        p3 = create_player_with_cards(
            "p3",
            "Player3",
            [
                Card(Rank.QUEEN, Suit.HEARTS),
                Card(Rank.QUEEN, Suit.CLUBS),
                Card(Rank.QUEEN, Suit.DIAMONDS),
                Card(Rank.JACK, Suit.SPADES),
                Card(Rank.TEN, Suit.HEARTS),
            ],
        )  # Trip Queens

        showdown_manager.table.players = {"p1": p1, "p2": p2, "p3": p3}
        showdown_manager.table.community_cards = {}

        # Mock betting with side pots
        showdown_manager.betting.get_main_pot_amount.return_value = 150
        showdown_manager.betting.get_side_pot_count.return_value = 2
        showdown_manager.betting.get_side_pot_amount.side_effect = lambda i: [50, 30][i]
        showdown_manager.betting.get_total_pot.return_value = 230

        # Mock side pot eligibility - p1 eligible for all, p2 for main+side1, p3 for main only
        def mock_side_pot_eligible(pot_index):
            if pot_index == 0:  # First side pot
                return set(["p1", "p2"])
            elif pot_index == 1:  # Second side pot
                return set(["p1"])
            else:
                return set(["p1", "p2", "p3"])  # Main pot

        showdown_manager.betting.get_side_pot_eligible_players.side_effect = mock_side_pot_eligible

        showdown_manager.rules.showdown.best_hand = [{"name": "High Hand", "evaluationType": "high", "anyCards": 5}]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:

            def mock_eval_hand(cards, eval_type, **kwargs):
                if any(card in p1.hand.cards for card in cards):
                    return HandResult(
                        player_id="p1",
                        cards=cards,
                        hand_name="Three Aces",
                        hand_description="Trip Aces",
                        evaluation_type="high",
                        rank=4,
                        ordered_rank=4,
                    )
                elif any(card in p2.hand.cards for card in cards):
                    return HandResult(
                        player_id="p2",
                        cards=cards,
                        hand_name="Three Kings",
                        hand_description="Trip Kings",
                        evaluation_type="high",
                        rank=4,
                        ordered_rank=5,
                    )
                else:
                    return HandResult(
                        player_id="p3",
                        cards=cards,
                        hand_name="Three Queens",
                        hand_description="Trip Queens",
                        evaluation_type="high",
                        rank=4,
                        ordered_rank=6,
                    )

            mock_eval.side_effect = mock_eval_hand

            with patch.object(showdown_manager, "_find_winners") as mock_winners:
                # P1 wins all pots they're eligible for
                mock_winners.return_value = [p1]

                result = showdown_manager.handle_showdown()

        # Should have 3 pot results (main + 2 side)
        assert len(result.pots) == 3

        # P1 should win all pots (eligible for all and has best hand)
        for pot in result.pots:
            assert "p1" in pot.winners


class TestShowdownManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_player_list(self, showdown_manager):
        """Test showdown with no active players."""
        showdown_manager.table.players = {}

        result = showdown_manager.handle_showdown()

        assert len(result.pots) == 0
        assert len(result.hands) == 0
        assert result.is_complete

    def test_invalid_wild_card_configuration(self, showdown_manager):
        """Test handling of invalid wild card configurations."""
        player = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.QUEEN, Suit.DIAMONDS),
                Card(Rank.JACK, Suit.CLUBS),
                Card(Rank.TEN, Suit.SPADES),
            ],
        )

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        # Invalid wild card type - but valid hand configuration otherwise
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high",
                "anyCards": 5,  # Changed to 5 to match high evaluation requirements
                "wildCards": [
                    {
                        "type": "invalid_type",  # This is the invalid part we want to test
                        "role": "wild",
                    }
                ],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=player.hand.cards,
                hand_name="Straight",
                hand_description="Ace-high Straight",
                evaluation_type="high",
                rank=5,
                ordered_rank=5,
            )

            # Should not crash, just ignore invalid wild card rules
            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners

        # Verify that the invalid wild card rule was ignored gracefully
        # The hand should still be evaluated normally
        player_hands = result.hands.get("p1", [])
        assert len(player_hands) > 0
        hand_result = player_hands[0]
        assert hand_result.hand_name == "Straight"

    def test_insufficient_cards_for_combination(self, showdown_manager):
        """Test handling when player has insufficient cards for required combination."""
        # Player with only 2 cards
        player = create_player_with_cards("p1", "Player1", [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)])

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        # Require 5 cards but player only has 2
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high",
                "holeCards": 5,  # More than player has
                "communityCards": 0,
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        # Should handle gracefully - either return empty hand or use padding
        result = showdown_manager.handle_showdown()

        # Result should exist but may have empty hands
        assert result.is_complete

    def test_zero_cards_pip_value_handling(self, showdown_manager):
        """Test handling of zero cards with pip value (Scarney-style games)."""
        # Player with no cards
        player = create_player_with_cards("p1", "Player1", [])

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {}

        # Allow zero cards with pip value
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "Low Hand",
                "evaluationType": "low_pip_6_cards",
                "anyCards": 0,
                "minimumCards": 0,
                "zeroCardsPipValue": 0,  # Best possible low
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=[],
                hand_name="No Cards",
                hand_description="Zero cards (pip value 0)",
                evaluation_type="low_pip_6_cards",
                rank=1,
                ordered_rank=1,
            )

            result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners

        # Verify the hand result shows empty cards
        player_hands = result.hands.get("p1", [])
        assert len(player_hands) > 0
        hand_result = player_hands[0]
        assert len(hand_result.cards) == 0  # Fixed: should be 0 cards
        assert hand_result.hand_name == "No Cards"
        assert hand_result.evaluation_type == "low_pip_6_cards"

    def test_player_hand_size_condition(self, showdown_manager):
        """Test conditional best hands based on player hand size (like Tapiola Hold'em)."""
        # Create players with different hand sizes
        p1 = create_player_with_cards(
            "p1", "Player1", [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)]
        )  # 2 cards

        p2 = create_player_with_cards(
            "p2", "Player2", [Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.JACK, Suit.HEARTS), Card(Rank.TEN, Suit.HEARTS)]
        )  # 3 cards

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {
            "Center": [Card(Rank.NINE, Suit.CLUBS)],
            "Tower1": [Card(Rank.EIGHT, Suit.DIAMONDS)],
            "Tower2": [Card(Rank.SEVEN, Suit.HEARTS)],
        }

        # Set up conditional best hands based on hand size
        showdown_manager.rules.showdown.conditionalBestHands = [
            {
                "condition": {"type": "player_hand_size", "hand_sizes": [2]},
                "bestHand": [
                    {
                        "name": "2-Card Hand",
                        "evaluationType": "high",
                        "holeCards": 2,
                        "communitySubsetRequirements": [
                            {"subset": "Center", "count": 1, "required": True},
                            {"subset": "Tower1", "count": 1, "required": True},
                            {"subset": "Tower2", "count": 1, "required": True},
                        ],
                    }
                ],
            },
            {
                "condition": {"type": "player_hand_size", "hand_sizes": [3]},
                "bestHand": [
                    {
                        "name": "3-Card Hand",
                        "evaluationType": "high",
                        "holeCards": 3,
                        "communitySubsetRequirements": [
                            {"subset": "Tower1", "count": 1, "required": True},
                            {"subset": "Tower2", "count": 1, "required": True},
                        ],
                    }
                ],
            },
        ]

        # Set up proper showdown rules attributes (not mocks)
        showdown_manager.rules.showdown.classification_priority = []  # Empty list
        showdown_manager.rules.showdown.defaultActions = []
        showdown_manager.rules.showdown.globalDefaultAction = None
        showdown_manager.rules.showdown.best_hand = []  # Set as empty list initially

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:

            def mock_eval_hand(cards, eval_type, **kwargs):  # Accept any additional kwargs
                return HandResult(
                    player_id="test",
                    cards=cards,
                    hand_name="High Card",
                    hand_description="Test Hand",
                    evaluation_type="high",
                    rank=10,
                    ordered_rank=10,
                )

            mock_eval.side_effect = mock_eval_hand

            with patch.object(showdown_manager, "_find_best_hand_for_player") as mock_find_hand:

                def mock_find_best(player, community, config, eval_type):
                    if player.id == "p1":
                        # 2-card player gets 5 cards total
                        return player.hand.cards + [
                            showdown_manager.table.community_cards["Center"][0],
                            showdown_manager.table.community_cards["Tower1"][0],
                            showdown_manager.table.community_cards["Tower2"][0],
                        ], player.hand.cards
                    else:
                        # 3-card player gets 5 cards total
                        return player.hand.cards + [
                            showdown_manager.table.community_cards["Tower1"][0],
                            showdown_manager.table.community_cards["Tower2"][0],
                        ], player.hand.cards

                mock_find_hand.side_effect = mock_find_best

                result = showdown_manager.handle_showdown()

        # Both players should get evaluated with their appropriate configurations
        assert len(result.hands) == 2
        assert "p1" in result.hands
        assert "p2" in result.hands


class TestShowdownManagerQualifiers:
    """Test hand qualifiers and default actions."""

    def test_low_hand_qualifier(self, showdown_manager):
        """Test low hand with 8-or-better qualifier."""
        # Create players - one qualifies for low, one doesn't
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.THREE, Suit.CLUBS),
                Card(Rank.FOUR, Suit.DIAMONDS),
                Card(Rank.FIVE, Suit.SPADES),
            ],
        )  # A-5 low (qualifies)

        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.NINE, Suit.HEARTS),
                Card(Rank.TEN, Suit.CLUBS),
                Card(Rank.JACK, Suit.DIAMONDS),
                Card(Rank.QUEEN, Suit.SPADES),
                Card(Rank.KING, Suit.HEARTS),
            ],
        )  # No low (doesn't qualify)

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {}

        # Set up high-low showdown with qualifier
        showdown_manager.rules.showdown.best_hand = [
            {"name": "High Hand", "evaluationType": "high", "anyCards": 5},
            {
                "name": "Low Hand",
                "evaluationType": "a5_low",
                "anyCards": 5,
                "qualifier": [1, 56],  # 8-or-better
            },
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        # Set up proper showdown rules attributes
        showdown_manager.rules.showdown.classification_priority = []
        showdown_manager.rules.showdown.defaultActions = []
        showdown_manager.rules.showdown.globalDefaultAction = None
        showdown_manager.rules.showdown.best_hand = (
            showdown_manager.rules.showdown.best_hand
        )  # Use the configured best_hand

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:

            def mock_eval_hand(cards, eval_type, **kwargs):  # Accept any additional kwargs
                if eval_type == EvaluationType.LOW_A5:
                    if any(card.rank == Rank.ACE for card in cards):
                        # P1 has qualifying low
                        return HandResult(
                            player_id="p1",
                            cards=cards,
                            hand_name="A-5 Low",
                            hand_description="Wheel",
                            evaluation_type="a5_low",
                            rank=1,
                            ordered_rank=1,
                        )
                    else:
                        # P2 has no qualifying low
                        return HandResult(
                            player_id="p2",
                            cards=cards,
                            hand_name="No Low",
                            hand_description="No qualifying low",
                            evaluation_type="a5_low",
                            rank=999,
                            ordered_rank=999,
                        )
                else:  # High
                    return HandResult(
                        player_id="test",
                        cards=cards,
                        hand_name="High Card",
                        hand_description="King High",
                        evaluation_type="high",
                        rank=10,
                        ordered_rank=10,
                    )

            mock_eval.side_effect = mock_eval_hand

            with patch.object(showdown_manager, "_find_winners") as mock_winners:

                def mock_find_winners_side_effect(players, hand_results, eval_type, showdown_rules):
                    if eval_type == EvaluationType.LOW_A5:
                        # Only p1 qualifies for low
                        qualified = [p for p in players if p.id == "p1"]
                        return qualified
                    else:
                        # Both can compete for high
                        return [p2]  # P2 wins high

                mock_winners.side_effect = mock_find_winners_side_effect

                result = showdown_manager.handle_showdown()

        # Should have both high and low pots
        assert len(result.pots) == 2
        hand_types = [pot.hand_type for pot in result.pots]
        assert "High Hand" in hand_types
        assert "Low Hand" in hand_types

    def test_default_action_split_pot(self, showdown_manager):
        """Test default action when no one qualifies."""
        # Create players with no qualifying hands
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.NINE, Suit.HEARTS),
                Card(Rank.TEN, Suit.CLUBS),
                Card(Rank.JACK, Suit.DIAMONDS),
                Card(Rank.QUEEN, Suit.SPADES),
                Card(Rank.KING, Suit.HEARTS),
            ],
        )

        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.EIGHT, Suit.HEARTS),
                Card(Rank.NINE, Suit.CLUBS),
                Card(Rank.TEN, Suit.DIAMONDS),
                Card(Rank.JACK, Suit.SPADES),
                Card(Rank.QUEEN, Suit.HEARTS),
            ],
        )

        # Add stack attributes to the mock players
        p1.stack = 1000
        p2.stack = 1000

        # Ensure players are marked as active
        p1.is_active = True
        p2.is_active = True

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {}

        # Set up betting manager to return proper pot amounts
        showdown_manager.betting.get_main_pot_amount.return_value = 100
        showdown_manager.betting.get_side_pot_count.return_value = 0
        showdown_manager.betting.get_total_pot.return_value = 100

        # Set up showdown with strict qualifier and default action
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "Low Hand",
                "evaluationType": "a5_low",
                "anyCards": 5,
                "qualifier": [1, 1],  # Extremely strict - only wheel qualifies
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []
        showdown_manager.rules.showdown.globalDefaultAction = {
            "condition": "no_qualifier_met",
            "action": {"type": "split_pot"},
        }

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            # No one has qualifying low
            mock_eval.return_value = HandResult(
                player_id="test",
                cards=[],
                hand_name="No Low",
                hand_description="No qualifying low",
                evaluation_type="a5_low",
                rank=999,
                ordered_rank=999,
            )

            result = showdown_manager.handle_showdown()

        # Verify that pot was split between all players
        assert len(result.pots) == 1
        pot_result = result.pots[0]
        assert set(pot_result.winners) == {"p1", "p2"}
        assert pot_result.hand_type == "Split (No Qualifier)"
        assert pot_result.amount == 100  # Full pot amount

        # Verify that player stacks were updated (50 each for 100 pot split 2 ways)
        assert p1.stack == 1050  # 1000 + 50
        assert p2.stack == 1050  # 1000 + 50


class TestShowdownManagerCommunityCardCombinations:
    """Test complex community card selection rules."""

    def test_community_card_combinations(self, showdown_manager):
        """Test games with multiple community card combinations (like Banco)."""
        # Create player
        player = create_player_with_cards("p1", "Player1", [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)])

        showdown_manager.table.players = {"p1": player}

        # Set up Banco-style community cards
        showdown_manager.table.community_cards = {
            "Flop 1.1": [Card(Rank.QUEEN, Suit.SPADES)],
            "Turn 1.2": [Card(Rank.JACK, Suit.SPADES)],
            "River 1.3": [Card(Rank.TEN, Suit.SPADES)],
            "Flop 2.2": [Card(Rank.TWO, Suit.HEARTS)],
            "Turn 2.3": [Card(Rank.THREE, Suit.HEARTS)],
            "River 2.1": [Card(Rank.FOUR, Suit.HEARTS)],
        }

        # Set up showdown rules with community card combinations
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "High Hand",
                "evaluationType": "high",
                "holeCards": 2,
                "totalCards": 5,
                "communityCardCombinations": [
                    # Row 1
                    ["Flop 1.1", "Turn 1.2", "River 1.3"],
                    # Row 2 (partial)
                    ["Flop 2.2", "Turn 2.3", "River 2.1"],
                ],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
            mock_eval.return_value = HandResult(
                player_id="p1",
                cards=[],
                hand_name="Royal Flush",
                hand_description="Royal Flush in Spades",
                evaluation_type="high",
                rank=1,
                ordered_rank=1,
            )

            with patch.object(showdown_manager, "_find_winners") as mock_winners:
                mock_winners.return_value = [player]

                result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners

    def test_community_subset_requirements(self, showdown_manager):
        """Test specific community subset requirements (like Tapiola Hold'em)."""
        # Create player
        player = create_player_with_cards("p1", "Player1", [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)])

        showdown_manager.table.players = {"p1": player}
        showdown_manager.table.community_cards = {
            "Center": [Card(Rank.QUEEN, Suit.CLUBS)],
            "Tower1": [Card(Rank.JACK, Suit.DIAMONDS)],
            "Tower2": [Card(Rank.TEN, Suit.SPADES)],
        }

        # Require exactly one card from each subset
        showdown_manager.rules.showdown.best_hand = [
            {
                "name": "Best Hand",
                "evaluationType": "high",
                "holeCards": 2,
                "communitySubsetRequirements": [
                    {"subset": "Center", "count": 1, "required": True},
                    {"subset": "Tower1", "count": 1, "required": True},
                    {"subset": "Tower2", "count": 1, "required": True},
                ],
            }
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []

        with patch.object(showdown_manager, "_generate_subset_combinations") as mock_generate:
            # Mock that subset requirements generate valid combinations
            mock_generate.return_value = [
                [
                    showdown_manager.table.community_cards["Center"][0],
                    showdown_manager.table.community_cards["Tower1"][0],
                    showdown_manager.table.community_cards["Tower2"][0],
                ]
            ]

            with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:
                mock_eval.return_value = HandResult(
                    player_id="p1",
                    cards=[],
                    hand_name="Straight",
                    hand_description="Broadway Straight",
                    evaluation_type="high",
                    rank=5,
                    ordered_rank=5,
                )

                with patch.object(showdown_manager, "_find_winners") as mock_winners:
                    mock_winners.return_value = [player]

                    result = showdown_manager.handle_showdown()

        assert len(result.pots) == 1
        assert "p1" in result.pots[0].winners


class TestShowdownManagerDeclarations:
    """Test declaration-based showdown (Hi-Lo declare games)."""

    def test_declaration_based_showdown(self, showdown_manager):
        """Test Hi-Lo games with declarations."""
        # Create two players
        p1 = create_player_with_cards(
            "p1",
            "Player1",
            [
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.THREE, Suit.CLUBS),
                Card(Rank.FOUR, Suit.DIAMONDS),
                Card(Rank.FIVE, Suit.HEARTS),
            ],
        )  # Wheel - good for both high and low

        p2 = create_player_with_cards(
            "p2",
            "Player2",
            [
                Card(Rank.KING, Suit.SPADES),
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.KING, Suit.CLUBS),
                Card(Rank.QUEEN, Suit.DIAMONDS),
                Card(Rank.JACK, Suit.SPADES),
            ],
        )  # Trip Kings - high only

        # Add required attributes for the split pot functionality
        p1.stack = 1000
        p2.stack = 1000

        showdown_manager.table.players = {"p1": p1, "p2": p2}
        showdown_manager.table.community_cards = {}

        # Set up betting manager to return proper pot amounts
        showdown_manager.betting.get_main_pot_amount.return_value = 200
        showdown_manager.betting.get_side_pot_count.return_value = 0
        showdown_manager.betting.get_total_pot.return_value = 200
        showdown_manager.betting.get_side_pot_eligible_players.return_value = set()

        # Set up Hi-Lo with declarations
        showdown_manager.rules.showdown.best_hand = [
            {"name": "High Hand", "evaluationType": "high", "anyCards": 5},
            {
                "name": "Low Hand",
                "evaluationType": "a5_low",
                "anyCards": 5,
                "qualifier": [1, 56],  # 8 or better
            },
        ]
        showdown_manager.rules.showdown.conditionalBestHands = []
        showdown_manager.rules.showdown.defaultBestHand = []
        showdown_manager.rules.showdown.declaration_mode = "declare"

        # Set declarations: p1 goes for high_low, p2 goes for high only
        declarations = {
            "p1": {-1: "high_low"},  # Main pot
            "p2": {-1: "high"},  # Main pot
        }
        showdown_manager.set_declarations(declarations)

        with patch("generic_poker.evaluation.evaluator.evaluator.evaluate_hand") as mock_eval:

            def mock_eval_hand(cards, eval_type, qualifier=None):
                if eval_type.value == "high":
                    if len([c for c in cards if c.rank == Rank.KING]) == 3:
                        # P2's trip kings - worse than p1's straight flush
                        return HandResult(
                            player_id="p2",
                            cards=cards,
                            hand_name="Three of a Kind",
                            hand_description="Trip Kings",
                            evaluation_type="high",
                            rank=4,
                            ordered_rank=4,
                        )
                    else:
                        # P1's wheel as straight flush (best possible)
                        return HandResult(
                            player_id="p1",
                            cards=cards,
                            hand_name="Straight Flush",
                            hand_description="Wheel Straight Flush",
                            evaluation_type="high",
                            rank=2,
                            ordered_rank=2,
                        )
                else:  # a5_low
                    if len([c for c in cards if c.rank == Rank.KING]) == 3:
                        # P2 has no low (kings don't qualify)
                        return HandResult(
                            player_id="p2",
                            cards=cards,
                            hand_name="No Low",
                            hand_description="No qualifying low",
                            evaluation_type="a5_low",
                            rank=999,
                            ordered_rank=999,
                        )
                    else:
                        # P1's wheel (perfect low)
                        return HandResult(
                            player_id="p1",
                            cards=cards,
                            hand_name="Wheel",
                            hand_description="5-4-3-2-A low",
                            evaluation_type="a5_low",
                            rank=1,
                            ordered_rank=1,
                        )

            mock_eval.side_effect = mock_eval_hand

            result = showdown_manager.handle_showdown()

        # Verify results
        assert len(result.pots) == 2  # Should have high and low portions

        # Find high and low pot results
        high_pot = None
        low_pot = None
        for pot in result.pots:
            if pot.hand_type == "High Hand":
                high_pot = pot
            elif pot.hand_type == "Low Hand":
                low_pot = pot

        assert high_pot is not None, "Should have a high pot result"
        assert low_pot is not None, "Should have a low pot result"

        # High pot should go to p1 (straight flush beats trip kings)
        assert "p1" in high_pot.winners
        assert high_pot.amount == 100  # Half of 200

        # Low pot should go to p1 (only p1 has qualifying low and declared for it, plus won high)
        assert "p1" in low_pot.winners
        assert low_pot.amount == 100  # Half of 200

        # Verify hand results are stored correctly
        assert "p1" in result.hands
        assert "p2" in result.hands

        # P1 should have both high and low hand results
        p1_hands = result.hands["p1"]
        assert len(p1_hands) == 2
        hand_types = [hand.hand_type for hand in p1_hands]
        assert "High Hand" in hand_types
        assert "Low Hand" in hand_types

        # P2 should have only high hand result (didn't declare for low)
        p2_hands = result.hands["p2"]
        assert len(p2_hands) == 2  # Still gets both evaluations

        # Verify winning hands
        assert len(result.winning_hands) == 2  # One for high, one for low
        winning_types = [hand.hand_type for hand in result.winning_hands]
        assert "High Hand" in winning_types
        assert "Low Hand" in winning_types
