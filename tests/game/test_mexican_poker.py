"""Tests for 7 card stud end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit, Visibility, WildType
from generic_poker.game.betting import BettingStructure, PlayerBet
from generic_poker.core.deck import Deck
from generic_poker.evaluation.hand_description import HandDescriber, EvaluationType

from tests.test_helpers import load_rules_from_file

import json 
import logging
import sys
from typing import List

class MockDeck(Deck):
    """A deck with predetermined card sequence for testing."""
    
    def __init__(self, cards: List[Card]):
        """
        Initialize a mock deck with specific cards.
        
        Args:
            cards: The cards to use, in reverse order of dealing 
                  (last card in list will be dealt first)
        """
        super().__init__(include_jokers=False)  # Initialize parent
        self.cards.clear()  # Clear the automatically generated cards
        
        # Add the provided cards in reverse order so the first card in the list
        # will be the last card dealt
        for card in reversed(cards):
            self.cards.append(card)

def create_predetermined_deck():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.JOKER, Suit.JOKER), #Alice FD HOLE
        Card(Rank.QUEEN, Suit.DIAMONDS), #Bob FD HOLE
        Card(Rank.JACK, Suit.SPADES), #Charlie FD HOLE
        Card(Rank.QUEEN, Suit.HEARTS), #Alice DOOR CARD
        Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
        Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD
        Card(Rank.FIVE, Suit.DIAMONDS), #Alice 3RD ST
        Card(Rank.SEVEN, Suit.HEARTS), #Bob 3RD ST
        Card(Rank.SIX, Suit.CLUBS), #Charlie 3RD ST
        Card(Rank.FOUR, Suit.SPADES), #Alice 4TH ST
        Card(Rank.QUEEN, Suit.CLUBS), #Bob 4TH ST
        Card(Rank.QUEEN, Suit.SPADES), #Charlie 4TH ST
        Card(Rank.JACK, Suit.HEARTS), #Alice 5TH ST
        Card(Rank.FOUR, Suit.DIAMONDS), #Bob 5TH ST
        Card(Rank.FOUR, Suit.HEARTS), #Charlie 5TH ST

        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def create_predetermined_deck_joker_exposed():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.QUEEN, Suit.HEARTS), #Alice FD HOLE
        Card(Rank.QUEEN, Suit.DIAMONDS), #Bob FD HOLE
        Card(Rank.JACK, Suit.SPADES), #Charlie FD HOLE
        Card(Rank.JOKER, Suit.JOKER), #Alice DOOR CARD
        Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
        Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD
        Card(Rank.FIVE, Suit.DIAMONDS), #Alice 3RD ST
        Card(Rank.SEVEN, Suit.HEARTS), #Bob 3RD ST
        Card(Rank.SIX, Suit.CLUBS), #Charlie 3RD ST
        Card(Rank.FOUR, Suit.SPADES), #Alice 4TH ST
        Card(Rank.QUEEN, Suit.CLUBS), #Bob 4TH ST
        Card(Rank.QUEEN, Suit.SPADES), #Charlie 4TH ST
        Card(Rank.JACK, Suit.HEARTS), #Alice 5TH ST
        Card(Rank.FOUR, Suit.DIAMONDS), #Bob 5TH ST
        Card(Rank.FOUR, Suit.HEARTS), #Charlie 5TH ST

        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    rules = load_rules_from_file('mexican_poker')

    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        bring_in=3,
        ante=1,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    
    # Monkey patch the Table.clear_hands method to preserve our mock deck
    original_clear_hands = game.table.clear_hands
    
    def patched_clear_hands():
        """Clear hands but keep our mock deck."""
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()
        # Note: We don't reset the deck here
    
    # Replace the method
    game.table.clear_hands = patched_clear_hands
    
    # Set our mock deck
    game.table.deck = create_predetermined_deck()
    
    return game

def setup_test_game_with_mock_deck_joker_exposed():
    """Create a test game with three players and a predetermined deck."""
    rules = load_rules_from_file('mexican_poker')

    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        bring_in=3,
        ante=1,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    
    # Monkey patch the Table.clear_hands method to preserve our mock deck
    original_clear_hands = game.table.clear_hands
    
    def patched_clear_hands():
        """Clear hands but keep our mock deck."""
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()
        # Note: We don't reset the deck here
    
    # Replace the method
    game.table.clear_hands = patched_clear_hands
    
    # Set our mock deck
    game.table.deck = create_predetermined_deck_joker_exposed()
    
    return game

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
    
def test_game_deal():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0           # Should be in post antes step
    assert game.state == GameState.BETTING  # Forced bets    
    game._next_step()  # Deal hole cards

    # check each player's face up card (door card)
    #Card(Rank.QUEEN, Suit.HEARTS), #Alice DOOR CARD
    #Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
    #Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD    
    print (game.table.players['p1'].hand.get_cards())

    # check face down cards
    assert str(game.table.players['p1'].hand.cards[0]) == "Rj"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "Qd"  # Bob
    assert str(game.table.players['p3'].hand.cards[0]) == "Js"  # Charlie    

    assert game.table.players['p1'].hand.get_cards(visible_only=True) == [Card(Rank.QUEEN, Suit.HEARTS)]
    assert game.table.players['p2'].hand.get_cards(visible_only=True) == [Card(Rank.KING, Suit.DIAMONDS)]
    assert game.table.players['p3'].hand.get_cards(visible_only=True) == [Card(Rank.TWO, Suit.CLUBS)]
    
    # validate wild card status of joker
    assert game.table.players['p1'].hand.cards[0].is_wild == True
    assert game.table.players['p1'].hand.cards[0].wild_type == WildType.NAMED

    # skip thru betting
    game._next_step()
    assert game.current_step == 2
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p2"  # Bob has Kd, highest card which is the rule for Mexican Poker
    result = game.player_action("p2", PlayerAction.BRING_IN, 3)
    assert result.success
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.BETTING
    result = game.player_action("p3", PlayerAction.CALL, 3)
    assert result.success
    result = game.player_action("p1", PlayerAction.CALL, 3)
    assert result.success
    result = game.player_action("p2", PlayerAction.CHECK, 0)
    assert result.success

    # The grouped actions should be:
    # P2 - Expose 0 cards, Deal 1 card face up (auto-executed after expose)
    # P3 - Expose 1 card, Deal 1 card face down (auto-executed after expose)
    # P1 - Expose 1 card, Deal 1 card face down (auto-executed after expose)

    game._next_step()
    assert game.current_step == 4
    assert game.action_handler.current_substep == 0  # expose is first part of group
    assert game.state == GameState.DRAWING  # really expose
    assert game.current_player.id == "p2"

    # check cards haven't changed
    assert str(game.table.players['p1'].hand.cards[0]) == "Rj"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "Qd"  # Bob
    assert str(game.table.players['p3'].hand.cards[0]) == "Js"  # Charlie

    assert game.table.players['p1'].hand.get_cards(visible_only=True) == [Card(Rank.QUEEN, Suit.HEARTS)]
    assert game.table.players['p2'].hand.get_cards(visible_only=True) == [Card(Rank.KING, Suit.DIAMONDS)]
    assert game.table.players['p3'].hand.get_cards(visible_only=True) == [Card(Rank.TWO, Suit.CLUBS)]

    valid_actions = game.get_valid_actions(game.current_player.id)
    assert len(valid_actions) == 1
    assert any(action[0] == PlayerAction.EXPOSE and action[1] == 0 and action[2] == 1 for action in valid_actions)

    # Bob (P2) exposes 0 cards — deal auto-executes: not all_exposed → face up card
    exposing_player = game.current_player.id
    cards_to_expose = None
    result = game.player_action(exposing_player, PlayerAction.EXPOSE, cards=cards_to_expose)
    assert result.success
    assert result.advance_step == False  # not time to go to next step yet

    # After expose, deal auto-executed — Bob now has 3 cards
    assert str(game.table.players[exposing_player].hand.cards[0]) == "Qd"  # Bob (p2)
    assert str(game.table.players[exposing_player].hand.cards[1]) == "Kd"  # Bob
    assert str(game.table.players[exposing_player].hand.cards[2]) == "5d"  # Bob (dealt face up)

    assert game.table.players[exposing_player].hand.get_cards(visible_only=True) == [Card(Rank.KING, Suit.DIAMONDS), Card(Rank.FIVE, Suit.DIAMONDS)]


    # Moving onto next player to act - Charlie (P3)
    # P3 - Expose 1 card, Deal 1 card face down

    assert game.current_step == 4
    assert game.action_handler.current_substep == 0  # back to expose for next player

    assert game.current_player.id == "p3"
    exposing_player = game.current_player.id
    cards_to_expose = game.table.players[exposing_player].hand.cards[:1]  # expose the first card

    valid_actions = game.get_valid_actions(game.current_player.id)
    assert len(valid_actions) == 1
    assert any(action[0] == PlayerAction.EXPOSE and action[1] == 0 and action[2] == 1 for action in valid_actions)

    assert str(game.table.players[exposing_player].hand.cards[0]) == "Js"  # Charlie (p3)
    assert str(game.table.players[exposing_player].hand.cards[1]) == "2c"  # Charlie

    # before expose, just the original 2c
    assert game.table.players[exposing_player].hand.get_cards(visible_only=True) == [Card(Rank.TWO, Suit.CLUBS)]

    result = game.player_action(exposing_player, PlayerAction.EXPOSE, cards=cards_to_expose)
    assert result.success
    assert result.advance_step == False  # not time to go to next step yet

    # After expose + auto-deal: exposed Js, original 2c face up, 7h dealt face down
    assert str(game.table.players[exposing_player].hand.cards[0]) == "Js"  # Charlie (p3)
    assert str(game.table.players[exposing_player].hand.cards[1]) == "2c"  # Charlie
    assert str(game.table.players[exposing_player].hand.cards[2]) == "7h"  # Charlie (dealt face down)

    assert game.table.players[exposing_player].hand.get_cards(visible_only=True) == [Card(Rank.JACK, Suit.SPADES), Card(Rank.TWO, Suit.CLUBS)]


    # Moving onto last player to act - Alice (P1)
    # P1 - Expose 1 card, Deal 1 card face down

    assert game.current_step == 4
    assert game.action_handler.current_substep == 0  # back to expose for next player

    assert game.current_player.id == "p1"
    exposing_player = game.current_player.id
    cards_to_expose = game.table.players[exposing_player].hand.cards[:1]  # expose the first card

    valid_actions = game.get_valid_actions(game.current_player.id)
    assert len(valid_actions) == 1
    assert any(action[0] == PlayerAction.EXPOSE and action[1] == 0 and action[2] == 1 for action in valid_actions)

    assert str(game.table.players[exposing_player].hand.cards[0]) == "Rj"  # Alice (p1)
    assert str(game.table.players[exposing_player].hand.cards[1]) == "Qh"  # Alice

    # before expose, just the original Qh
    assert game.table.players[exposing_player].hand.get_cards(visible_only=True) == [Card(Rank.QUEEN, Suit.HEARTS)]

    result = game.player_action(exposing_player, PlayerAction.EXPOSE, cards=cards_to_expose)
    assert result.success

    # After expose + auto-deal: exposed Rj, original Qh face up, 6c dealt face down
    assert str(game.table.players[exposing_player].hand.cards[0]) == "Rj"  # Alice (p1)
    assert str(game.table.players[exposing_player].hand.cards[1]) == "Qh"  # Alice
    assert str(game.table.players[exposing_player].hand.cards[2]) == "6c"  # Alice (dealt face down)

    assert game.table.players[exposing_player].hand.get_cards(visible_only=True) == [Card(Rank.JOKER, Suit.JOKER), Card(Rank.QUEEN, Suit.HEARTS)]

    # validate wild card status of joker
    assert game.table.players[exposing_player].hand.cards[0].is_wild == True
    assert game.table.players[exposing_player].hand.cards[0].wild_type == WildType.NAMED

    # All players exposed + dealt — advance to next step (betting)
    if result.advance_step:
        game._next_step()
    assert game.current_step == 5
    assert game.state == GameState.BETTING

def test_game_deal_joker_exposed():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck_joker_exposed()
    
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0           # Should be in post antes step
    assert game.state == GameState.BETTING  # Forced bets    
    game._next_step()  # Deal hole cards

    # check each player's face up card (door card)

        # Card(Rank.QUEEN, Suit.HEARTS), #Alice FD HOLE
        # Card(Rank.QUEEN, Suit.DIAMONDS), #Bob FD HOLE
        # Card(Rank.JACK, Suit.SPADES), #Charlie FD HOLE
        # Card(Rank.JOKER, Suit.JOKER), #Alice DOOR CARD
        # Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
        # Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD
        # Card(Rank.FIVE, Suit.DIAMONDS), #Alice 3RD ST
        # Card(Rank.SEVEN, Suit.HEARTS), #Bob 3RD ST
        # Card(Rank.SIX, Suit.CLUBS), #Charlie 3RD ST
        # Card(Rank.FOUR, Suit.SPADES), #Alice 4TH ST
        # Card(Rank.QUEEN, Suit.CLUBS), #Bob 4TH ST
        # Card(Rank.QUEEN, Suit.SPADES), #Charlie 4TH ST
        # Card(Rank.JACK, Suit.HEARTS), #Alice 5TH ST
        # Card(Rank.FOUR, Suit.DIAMONDS), #Bob 5TH ST
        # Card(Rank.FOUR, Suit.HEARTS), #Charlie 5TH ST
     
    print (game.table.players['p1'].hand.get_cards())

    # check face down cards
    assert str(game.table.players['p1'].hand.cards[0]) == "Qh"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "Qd"  # Bob
    assert str(game.table.players['p3'].hand.cards[0]) == "Js"  # Charlie    

    assert game.table.players['p1'].hand.get_cards(visible_only=True) == [Card(Rank.JOKER, Suit.JOKER)]
    assert game.table.players['p2'].hand.get_cards(visible_only=True) == [Card(Rank.KING, Suit.DIAMONDS)]
    assert game.table.players['p3'].hand.get_cards(visible_only=True) == [Card(Rank.TWO, Suit.CLUBS)]
    
    # validate wild card status of joker
    assert game.table.players['p1'].hand.cards[1].is_wild == True
    assert game.table.players['p1'].hand.cards[1].wild_type == WildType.BUG


def test_game_ante():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Play a full hand
    game.start_hand()
    assert game.current_step == 0           # Should be in post antes step
    assert game.state == GameState.BETTING  # Forced bets    

    # check each player's ante
    assert game.table.players['p1'].stack == 499
    assert game.table.players['p2'].stack == 499
    assert game.table.players['p3'].stack == 499

    # check the pot
    assert game.betting.get_main_pot_amount() == 3

