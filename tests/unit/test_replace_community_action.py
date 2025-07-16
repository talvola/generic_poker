"""Unit tests for the REPLACE_COMMUNITY action handler."""
import pytest
from unittest.mock import Mock, MagicMock, patch

from generic_poker.game.player_action_handler import PlayerActionHandler
from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.core.deck import Deck
from generic_poker.game.table import Table, Player
from generic_poker.game.action_result import ActionResult


@pytest.fixture
def mock_game():
    """Create a mock game for testing."""
    game = Mock()
    game.state = GameState.DRAWING
    game.current_replace_community_config = {
        "cardsToReplace": 2,
        "order": "clockwise",
        "startingFrom": "left_of_dealer"
    }
    
    # Mock rules and gameplay structure to avoid subscriptable error
    mock_step = Mock()
    mock_step.action_type = Mock()  # This will be checked but not used in DRAWING state
    game.rules = Mock()
    game.rules.gameplay = Mock()
    game.rules.gameplay.__getitem__ = Mock(return_value=mock_step)
    game.current_step = 0
    

    
    # Mock table and community cards
    game.table = Mock()
    game.table.community_cards = {
        "default": [
            Card(Rank.ACE, Suit.SPADES, Visibility.FACE_UP),
            Card(Rank.KING, Suit.HEARTS, Visibility.FACE_UP),
            Card(Rank.QUEEN, Suit.DIAMONDS, Visibility.FACE_UP),
            Card(Rank.JACK, Suit.CLUBS, Visibility.FACE_UP),
            Card(Rank.TEN, Suit.SPADES, Visibility.FACE_UP),
        ]
    }
    game.table.discard_pile = Mock()
    game.table.discard_pile.add_card = Mock()
    
    # Mock deck with replacement cards
    game.table.deck = Mock()
    game.table.deck.cards = [
        Card(Rank.NINE, Suit.HEARTS, Visibility.FACE_UP),
        Card(Rank.EIGHT, Suit.DIAMONDS, Visibility.FACE_UP),
    ]
    game.table.deck.deal_cards = Mock(return_value=[
        Card(Rank.NINE, Suit.HEARTS, Visibility.FACE_UP),
        Card(Rank.EIGHT, Suit.DIAMONDS, Visibility.FACE_UP),
    ])
    
    # Mock players
    game.table.players = {
        "player1": Mock(id="player1", is_active=True),
        "player2": Mock(id="player2", is_active=True),
        "player3": Mock(id="player3", is_active=True),
    }
    
    game.current_player = game.table.players["player1"]
    game.next_player = Mock(return_value=game.table.players["player2"])
    
    return game


@pytest.fixture
def action_handler(mock_game):
    """Create a PlayerActionHandler with mock game."""
    handler = PlayerActionHandler(mock_game)
    handler.players_completed_replacement = set()
    return handler


def test_setup_replace_community_round(action_handler, mock_game):
    """Test setting up a community replacement round."""
    config = {
        "cardsToReplace": 2,
        "order": "clockwise", 
        "startingFrom": "left_of_dealer"
    }
    
    action_handler.setup_replace_community_round(config)
    
    assert mock_game.current_replace_community_config == config
    assert mock_game.state == GameState.DRAWING
    assert hasattr(action_handler, 'players_completed_replacement')
    assert action_handler.players_completed_replacement == set()


def test_handle_replace_community_action_valid(action_handler, mock_game):
    """Test handling a valid community card replacement."""
    player = mock_game.table.players["player1"]
    
    # Cards to replace (from community)
    cards_to_replace = [
        mock_game.table.community_cards["default"][0],  # Ace of Spades
        mock_game.table.community_cards["default"][1],  # King of Hearts
    ]
    
    result = action_handler._handle_replace_community_action(player, cards_to_replace)
    
    assert result is True
    assert "player1" in action_handler.players_completed_replacement
    
    # Verify cards were removed from community
    for card in cards_to_replace:
        mock_game.table.discard_pile.add_card.assert_any_call(card)
    
    # Verify new cards were dealt
    mock_game.table.deck.deal_cards.assert_called_once_with(2)


def test_handle_replace_community_action_wrong_count(action_handler, mock_game):
    """Test handling replacement with wrong number of cards."""
    player = mock_game.table.players["player1"]
    
    # Wrong number of cards (should be 2, providing 1)
    cards_to_replace = [mock_game.table.community_cards["default"][0]]
    
    result = action_handler._handle_replace_community_action(player, cards_to_replace)
    
    assert result is False
    assert "player1" not in action_handler.players_completed_replacement


def test_handle_replace_community_action_invalid_card(action_handler, mock_game):
    """Test handling replacement with non-community card."""
    player = mock_game.table.players["player1"]
    
    # Invalid card (not in community)
    invalid_card = Card(Rank.TWO, Suit.CLUBS, Visibility.FACE_UP)
    cards_to_replace = [
        mock_game.table.community_cards["default"][0],
        invalid_card  # This card is not in community
    ]
    
    result = action_handler._handle_replace_community_action(player, cards_to_replace)
    
    assert result is False
    assert "player1" not in action_handler.players_completed_replacement


def test_check_replace_community_round_complete(action_handler, mock_game):
    """Test checking if replacement round is complete."""
    # Initially not complete
    assert action_handler._check_replace_community_round_complete() is False
    
    # Add players to completed set
    action_handler.players_completed_replacement.add("player1")
    action_handler.players_completed_replacement.add("player2")
    assert action_handler._check_replace_community_round_complete() is False
    
    # All players completed
    action_handler.players_completed_replacement.add("player3")
    assert action_handler._check_replace_community_round_complete() is True


@patch('generic_poker.game.player_action_handler.hasattr')
def test_get_valid_actions_replace_community(mock_hasattr, action_handler, mock_game):
    """Test getting valid actions for community replacement."""
    mock_game.current_player.id = "player1"
    
    # Mock hasattr to control which config attributes exist
    # This ensures we reach the current_replace_community_config branch
    def custom_hasattr(obj, name):
        if name == 'current_replace_community_config':
            return True
        elif name in ['current_discard_config', 'current_draw_config', 'current_separate_config', 
                      'current_expose_config', 'current_pass_config', 'current_declare_config']:
            return False
        else:
            # For other attributes, delegate to the real hasattr
            return hasattr.__wrapped__(obj, name) if hasattr(hasattr, '__wrapped__') else True
    
    mock_hasattr.side_effect = custom_hasattr
    
    valid_actions = action_handler.get_valid_actions("player1")
    
    # Should return REPLACE_COMMUNITY action with correct parameters
    assert len(valid_actions) == 1
    action, min_cards, max_cards = valid_actions[0]
    assert action == PlayerAction.REPLACE_COMMUNITY
    assert min_cards == 2
    assert max_cards == 2