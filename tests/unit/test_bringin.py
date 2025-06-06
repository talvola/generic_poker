"""Tests for stud poker bring-in and first-to-act determination."""
import pytest
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.game.table import Player, PlayerPosition
from generic_poker.game.bringin import BringInDeterminator, CardRule

from dataclasses import dataclass
from typing import List, Dict, Any

import logging
import sys

@dataclass
class ShowdownConfig:
    order: str
    starting_from: str
    cards_required: str
    best_hand: List[Dict[str, Any]]
    default_action: Dict[str, Any]

@dataclass
class GameRules:
    forced_bets: Dict[str, Any]
    betting_order: Dict[str, Any]
    showdown: ShowdownConfig
    # Minimal fields; omit gameplay, bettingStructures, etc.

def minimal_stud_rules(rule: str = "low card", evaluation_type: str = "high", subsequent: str = "high_hand") -> GameRules:
    """
    Create a minimal GameRules object for Stud game tests.
    
    Args:
        rule: The bring-in rule (e.g., "low card", "high card", "high card ah")
        evaluation_type: The showdown evaluation type (e.g., "high", "a5_low", "27_low")
    
    Returns:
        A minimal GameRules object with forcedBets and showdown configured
    """
    showdown_config = ShowdownConfig(
        order="clockwise",
        starting_from="dealer",
        cards_required="best five out of seven cards",
        best_hand=[{"evaluationType": evaluation_type, "anyCards": 5}],
        default_action={}
    )
    return GameRules(
        forced_bets={"style": "bring-in", "rule": rule},
        betting_order=[{"initial": "bring_in", "subsequent": subsequent}],
        showdown=showdown_config
    )
    
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
        force=True
    )


@pytest.fixture
def players_with_door_cards():
    """Create a set of players with visible door cards.  2, K, A should cover all cases."""
    # Player 1 with a 2 of clubs showing
    player1 = Player(id="p1", name="Alice", stack=500)
    player1.hand.add_card(Card(Rank.TWO, Suit.CLUBS, Visibility.FACE_UP))  # Door card
    player1.hand.add_card(Card(Rank.ACE, Suit.HEARTS, Visibility.FACE_DOWN))
    player1.hand.add_card(Card(Rank.KING, Suit.DIAMONDS, Visibility.FACE_DOWN))
    
    # Player 2 with a King of spades showing
    player2 = Player(id="p2", name="Bob", stack=500)
    player2.hand.add_card(Card(Rank.KING, Suit.SPADES, Visibility.FACE_UP))  # Door card
    player2.hand.add_card(Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_DOWN))
    player2.hand.add_card(Card(Rank.JACK, Suit.CLUBS, Visibility.FACE_DOWN))
    
    # Player 3 with an Ace of diamonds showing
    player3 = Player(id="p3", name="Charlie", stack=500)
    player3.hand.add_card(Card(Rank.ACE, Suit.DIAMONDS, Visibility.FACE_UP))  # Door card
    player3.hand.add_card(Card(Rank.FOUR, Suit.SPADES, Visibility.FACE_DOWN))
    player3.hand.add_card(Card(Rank.FIVE, Suit.HEARTS, Visibility.FACE_DOWN))
    
    return [player1, player2, player3]

@pytest.fixture
def players_with_multiple_upcards():
    """Create a set of players with multiple visible cards."""
    # Player 1 with a pair of twos showing
    player1 = Player(id="p1", name="Alice", stack=500)
    player1.hand.add_card(Card(Rank.TWO, Suit.CLUBS, Visibility.FACE_UP))
    player1.hand.add_card(Card(Rank.TWO, Suit.HEARTS, Visibility.FACE_UP))
    player1.hand.add_card(Card(Rank.ACE, Suit.HEARTS, Visibility.FACE_DOWN))
    
    # Player 2 with A-2 showing
    player2 = Player(id="p2", name="Bob", stack=500)
    player2.hand.add_card(Card(Rank.ACE, Suit.SPADES, Visibility.FACE_UP))
    player2.hand.add_card(Card(Rank.TWO, Suit.DIAMONDS, Visibility.FACE_UP))
    player2.hand.add_card(Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_DOWN))
    
    # Player 3 with 8-7 showing
    player3 = Player(id="p3", name="Charlie", stack=500)
    player3.hand.add_card(Card(Rank.EIGHT, Suit.DIAMONDS, Visibility.FACE_UP))
    player3.hand.add_card(Card(Rank.SEVEN, Suit.CLUBS, Visibility.FACE_UP))
    player3.hand.add_card(Card(Rank.SEVEN, Suit.SPADES, Visibility.FACE_DOWN))

    # Player 4 with K-Q showing
    player4 = Player(id="p4", name="David", stack=500)
    player4.hand.add_card(Card(Rank.KING, Suit.HEARTS, Visibility.FACE_UP))
    player4.hand.add_card(Card(Rank.QUEEN, Suit.SPADES, Visibility.FACE_UP))    
    player4.hand.add_card(Card(Rank.JACK, Suit.DIAMONDS, Visibility.FACE_DOWN))
    
    return [player1, player2, player3, player4]

def test_first_round_low_card(players_with_door_cards):
    """Test first round bring-in with low card rule.   i.e., 7-Card Stud"""
    players = players_with_door_cards

    rules = minimal_stud_rules(rule="low card", evaluation_type="high")
    print(f"Rules: {rules}")


    # In first round with 'low card' rule, player with 2 of Clubs should go first
    first_player = BringInDeterminator.determine_first_to_act(
        players, 1, CardRule.LOW_CARD, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p1"  # Player with 2 of Clubs

def test_first_round_high_card(players_with_door_cards):
    """Test first round bring-in with high card rule.  i.e., Razz"""
    players = players_with_door_cards

    rules = minimal_stud_rules(rule="high card", evaluation_type="a5_low")
    
    # In first round with 'high card' rule, player with King of Spades should go first
    first_player = BringInDeterminator.determine_first_to_act(
        players, 1, CardRule.HIGH_CARD, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p2"  # Player with King of Spades

def test_first_round_low_card_ace_low(players_with_door_cards):
    """Test first round bring-in with low card (ace is low) rule.  No games currently used this"""
    players = players_with_door_cards

    rules = minimal_stud_rules(rule="low card al", evaluation_type="high")
    
    # In first round with 'low card al' rule, player with Ace of Diamonds should go first
    first_player = BringInDeterminator.determine_first_to_act(
        players, 1, CardRule.LOW_CARD_AL, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p3"  # Player with Ace of Diamonds

def test_first_round_low_card_ace_low_razz_high(players_with_door_cards):
    """Test first round bring-in with low card (ace is low) rule.  Razz High special rules"""
    players = players_with_door_cards

    rules = minimal_stud_rules(rule="low card al", evaluation_type="a5_low_high")
    
    # In first round with 'low card al' rule, player with Ace of Diamonds should go first
    first_player = BringInDeterminator.determine_first_to_act(
        players, 1, CardRule.LOW_CARD_AL, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p3"  # Player with Ace of Diamonds

def test_first_round_high_card_ace_high(players_with_door_cards):
    """Test first round bring-in with high card (ace is high) rule.  i.e., 2-7 Razz (unusual)"""
    players = players_with_door_cards
    
    rules = minimal_stud_rules(rule="high card", evaluation_type="27_low")

    # In first round with 'high card' rule, player with King of Spades should go first
    first_player = BringInDeterminator.determine_first_to_act(
        players, 1, CardRule.HIGH_CARD_AH, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p3"  # Player with Ace of Diamonds

def test_later_round_standard_stud(players_with_multiple_upcards):
    """Test later round first-to-act in standard 7-card stud."""
    players = players_with_multiple_upcards

    rules = minimal_stud_rules(rule="low card", evaluation_type="high")
    
    # In later rounds of standard stud, player with highest hand showing goes first
    # Player 1 has 2-2 showing, which is the highest
    first_player = BringInDeterminator.determine_first_to_act(
        players, 2, CardRule.LOW_CARD, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p1"  # Player with A-K showing

def test_later_round_razz(players_with_multiple_upcards):
    """Test later round first-to-act in Razz."""
    players = players_with_multiple_upcards

    rules = minimal_stud_rules(rule="high card", evaluation_type="a5_low")
    
    # In later rounds of Razz, player with lowest hand showing goes first
    # Player 2 has A-2 showing, which is the lowest
    first_player = BringInDeterminator.determine_first_to_act(
        players, 2, CardRule.HIGH_CARD, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p2"  # Player with A-2 showing

def test_later_round_razz_high(players_with_multiple_upcards):
    """Test later round first-to-act in Razz High."""
    players = players_with_multiple_upcards

    rules = minimal_stud_rules(rule="low card al", evaluation_type="a5_low_high")
    
    # In later rounds of Razz High, best unpaired hand showing goes first
    # Player 4 has K-Q showing, which is the lowest
    first_player = BringInDeterminator.determine_first_to_act(
        players, 2, CardRule.LOW_CARD_AL, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p4"  # Player with K-Q showing    

def test_later_round_27_razz(players_with_multiple_upcards):
    """Test later round first-to-act in Razz High."""
    players = players_with_multiple_upcards

    rules = minimal_stud_rules(rule="high card", evaluation_type="27_low")
    
    # In later rounds of Razz High, best unpaired hand showing goes first
    # Player 3 has 8-7 showing, which is the lowest
    first_player = BringInDeterminator.determine_first_to_act(
        players, 2, CardRule.HIGH_CARD_AH, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p3"  # Player with 8-7 showing    
    
def test_no_visible_cards():
    """Test handling of players with no visible cards."""
    rules = minimal_stud_rules(rule="low card", evaluation_type="high")
    player1 = Player(id="p1", name="Alice", stack=500)
    player1.hand.add_card(Card(Rank.TWO, Suit.CLUBS, Visibility.FACE_DOWN))
    player2 = Player(id="p2", name="Bob", stack=500)
    player2.hand.add_card(Card(Rank.TEN, Suit.SPADES, Visibility.FACE_DOWN))
    players = [player1, player2]

    first_player = BringInDeterminator.determine_first_to_act(players, 1, CardRule.LOW_CARD, rules)
    assert first_player is None, "Expected None when no visible cards are present"

def test_get_visible_cards():
    """Test extraction of visible cards from player's hand."""
    player = Player(id="p1", name="Alice", stack=500)
    player.hand.add_card(Card(Rank.TWO, Suit.CLUBS, Visibility.FACE_UP))
    player.hand.add_card(Card(Rank.ACE, Suit.HEARTS, Visibility.FACE_DOWN))
    player.hand.add_card(Card(Rank.KING, Suit.DIAMONDS, Visibility.FACE_UP))
    
    visible_cards = BringInDeterminator._get_visible_cards(player)
    
    assert len(visible_cards) == 2
    assert visible_cards[0].rank == Rank.TWO
    assert visible_cards[1].rank == Rank.KING

def test_first_round_low_card_al():
    rules = minimal_stud_rules(rule="low card al", evaluation_type="a5_low_high")

    """Test first round bring-in with low card Ace-low rule."""
    # Create players with visible door cards
    player1 = Player(id="p1", name="Alice", stack=500)
    player1.hand.add_card(Card(Rank.ACE, Suit.CLUBS, Visibility.FACE_UP))  # Ace is low
    
    player2 = Player(id="p2", name="Bob", stack=500)
    player2.hand.add_card(Card(Rank.KING, Suit.SPADES, Visibility.FACE_UP))  # King is high
    
    players = [player1, player2]
    
    # In first round with 'low card al' rule, player with Ace should go first (Ace is low)
    first_player = BringInDeterminator.determine_first_to_act(
        players, 1, CardRule.LOW_CARD_AL, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p1"  # Player with Ace of Clubs

def test_five_card_stud_third_round():
    """Test third round first-to-act in Five-Card Stud."""
    rules = minimal_stud_rules(rule="low card", evaluation_type="high")

    # Create players with three visible cards each
    player1 = Player(id="p1", name="Alice", stack=500)
    # Player 1 has three of a kind showing
    player1.hand.add_card(Card(Rank.EIGHT, Suit.CLUBS, Visibility.FACE_UP))
    player1.hand.add_card(Card(Rank.EIGHT, Suit.HEARTS, Visibility.FACE_UP))
    player1.hand.add_card(Card(Rank.EIGHT, Suit.DIAMONDS, Visibility.FACE_UP))
    player1.hand.add_card(Card(Rank.ACE, Suit.SPADES, Visibility.FACE_DOWN))
    
    player2 = Player(id="p2", name="Bob", stack=500)
    # Player 2 has a flush draw showing
    player2.hand.add_card(Card(Rank.ACE, Suit.SPADES, Visibility.FACE_UP))
    player2.hand.add_card(Card(Rank.KING, Suit.SPADES, Visibility.FACE_UP))
    player2.hand.add_card(Card(Rank.QUEEN, Suit.SPADES, Visibility.FACE_UP))
    player2.hand.add_card(Card(Rank.TWO, Suit.HEARTS, Visibility.FACE_DOWN))
    
    players = [player1, player2]
    
    # In standard stud, player with three of a kind should go first (better hand)
    first_player = BringInDeterminator.determine_first_to_act(
        players, 3, CardRule.LOW_CARD, rules
    )
    
    assert first_player is not None
    assert first_player.id == "p1"  # Player with three 8s

