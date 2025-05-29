"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck
from generic_poker.evaluation.hand_description import HandDescriber, EvaluationType
from tests.test_helpers import load_rules_from_file

import json 
import logging
import sys
from typing import List

# This is a complex game.   We want to at least test these scenarios:
# 1. Omaha - test for drawing, first to act in proper position (might need 2 and 3 player scenarios at least), and showdown
# 2. Holdem - test for discard, first to act in proper position (might need 2 and 3 player scenarios at least), and showdown
# 3. Stud games - test for expose/draw, overall rules, and proper use of bring-in in betting rounds.   And, showdown logic.
# might be a special case when someone folds in the bet/expose round in Stud

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

def create_predetermined_deck_two_players_omaha():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.HEARTS), #Alice FD HOLE
        Card(Rank.QUEEN, Suit.DIAMONDS), #Bob FD HOLE
        Card(Rank.JACK, Suit.SPADES), #Charlie FD HOLE
        Card(Rank.KING, Suit.HEARTS), #Alice FD HOLE2
        Card(Rank.KING, Suit.CLUBS), #Bob FD HOLE2
        Card(Rank.JACK, Suit.DIAMONDS), #Charlie FD HOLE2
        Card(Rank.QUEEN, Suit.HEARTS), #Alice DOOR CARD
        Card(Rank.KING, Suit.DIAMONDS), #Bob DOOR CARD
        Card(Rank.TWO, Suit.CLUBS), #Charlie DOOR CARD
        Card(Rank.TEN, Suit.SPADES), #Alice 4TH ST
        Card(Rank.QUEEN, Suit.CLUBS), #Bob 4TH ST
        Card(Rank.QUEEN, Suit.SPADES), #Charlie 4TH ST
        Card(Rank.JACK, Suit.HEARTS), #Alice 5TH ST
        Card(Rank.TEN, Suit.DIAMONDS), #Bob 5TH ST
        Card(Rank.TEN, Suit.HEARTS), #Charlie 5TH ST
        Card(Rank.NINE, Suit.SPADES), #Alice 6TH ST
        Card(Rank.SEVEN, Suit.SPADES), #Bob 6TH ST
        Card(Rank.SIX, Suit.SPADES), #Charlie 6TH ST
        Card(Rank.NINE, Suit.DIAMONDS), #Alice 7TH ST
        Card(Rank.SEVEN, Suit.HEARTS), #Bob 7TH ST
        Card(Rank.SIX, Suit.CLUBS), #Charlie 7TH ST    
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_two_players_razz():
    """Create a test game with two players and a predetermined deck."""
    rules = load_rules_from_file('paradise_road_pickem')
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=1,
        big_blind=2,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("p1", "Erik", 500)
    game.add_player("p2", "Foo", 500)
    
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
    game.table.deck = create_predetermined_deck_two_players_omaha()
    
    return game

def create_predetermined_deck_two_players_holdem():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.SPADES), # p1
        Card(Rank.KING, Suit.SPADES), # p2
        Card(Rank.QUEEN, Suit.SPADES), # p1
        Card(Rank.JACK, Suit.SPADES), # p2
        Card(Rank.TEN, Suit.SPADES), # p1 (will discard)
        Card(Rank.NINE, Suit.HEARTS), # p2 (will discard)
        Card(Rank.EIGHT, Suit.HEARTS), # f
        Card(Rank.SEVEN, Suit.HEARTS), # f
        Card(Rank.SIX, Suit.SPADES), # f
        Card(Rank.JACK, Suit.HEARTS), # t
        Card(Rank.TEN, Suit.DIAMONDS), # r
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.NINE, Suit.CLUBS), #        
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_two_players_holdem():
    """Create a test game with two players and a predetermined deck."""
    rules = load_rules_from_file('paradise_road_pickem')
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=1,
        big_blind=2,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("p1", "Erik", 500)
    game.add_player("p2", "Foo", 500)
    
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
    game.table.deck = create_predetermined_deck_two_players_holdem()
    
    return game

def create_predetermined_deck_two_players_omaha_hilo():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.SPADES), # p1
        Card(Rank.FIVE, Suit.SPADES), # p2 
        Card(Rank.QUEEN, Suit.SPADES), # p1
        Card(Rank.THREE, Suit.SPADES), # p2
        Card(Rank.TEN, Suit.SPADES), # p1
        Card(Rank.NINE, Suit.SPADES), # p2
        Card(Rank.EIGHT, Suit.SPADES), # p1
        Card(Rank.SEVEN, Suit.SPADES), # p2
        Card(Rank.SIX, Suit.SPADES), # f
        Card(Rank.JACK, Suit.HEARTS), # f
        Card(Rank.TWO, Suit.DIAMONDS), # f
        Card(Rank.FOUR, Suit.HEARTS), # t
        Card(Rank.THREE, Suit.CLUBS), # r      
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_two_players_omaha_hilo():
    """Create a test game with two players and a predetermined deck."""
    rules = load_rules_from_file('paradise_road_pickem')
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=1,
        big_blind=2,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("p1", "Erik", 500)
    game.add_player("p2", "Foo", 500)
    
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
    game.table.deck = create_predetermined_deck_two_players_omaha_hilo()
    
    return game

def create_predetermined_deck_two_players_razz():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.SPADES), # p1
        Card(Rank.FIVE, Suit.SPADES), # p2 
        Card(Rank.QUEEN, Suit.SPADES), # p3
        Card(Rank.THREE, Suit.SPADES), # p1
        Card(Rank.TEN, Suit.SPADES), # p2
        Card(Rank.NINE, Suit.SPADES), # p3
        Card(Rank.EIGHT, Suit.SPADES), # p1
        Card(Rank.SEVEN, Suit.SPADES), # p2
        Card(Rank.SIX, Suit.SPADES), # p3
        Card(Rank.JACK, Suit.HEARTS), # f
        Card(Rank.TWO, Suit.DIAMONDS), # f
        Card(Rank.FOUR, Suit.HEARTS), # t
        Card(Rank.THREE, Suit.CLUBS), # r      
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_two_players_razz():
    """Create a test game with two players and a predetermined deck."""
    rules = load_rules_from_file('paradise_road_pickem')
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=1,
        big_blind=2,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False        
    )
  
    # Add players
    game.add_player("utg", "Bar", 500)
    game.add_player("sb", "Erik", 500)
    game.add_player("bb", "Foo", 500)
    
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
    game.table.deck = create_predetermined_deck_two_players_razz()
    
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

# test out player choice of Razz

def test_game_results_two_player_razz_fold():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck_two_players_razz()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    assert game.table.players['sb'].stack == 499  # SB deducted
    assert game.table.players['bb'].stack == 498  # BB deducted
    assert game.table.players['utg'].stack == 500  # 
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game


    # Step 1: Deal Hole Cards (3 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['utg'].hand.cards[0]) == "As"  # sb
    assert str(game.table.players['utg'].hand.cards[1]) == "3s"  # sb
    assert str(game.table.players['utg'].hand.cards[2]) == "8s"  # sb
    assert str(game.table.players['sb'].hand.cards[0]) == "5s"  # bb
    assert str(game.table.players['sb'].hand.cards[1]) == "Ts"  # bb  
    assert str(game.table.players['sb'].hand.cards[2]) == "7s"  # bb     
    assert str(game.table.players['bb'].hand.cards[0]) == "Qs"  # utg
    assert str(game.table.players['bb'].hand.cards[1]) == "9s"  # utg  
    assert str(game.table.players['bb'].hand.cards[2]) == "6s"  # utg      
   
    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    
    # Step 2: Choose Game Type

    game._next_step()  
    assert game.current_step == 2
    assert game.state == GameState.DEALING   

    # check the current player - should be utg - after the big blind
    assert game.current_player.id == 'utg'    

    valid_actions = game.get_valid_actions("utg")
    # Format: (action, min_index, max_index, choices_list)
    assert valid_actions[0][0] == PlayerAction.CHOOSE
    assert valid_actions[0][3] == ["Hold'em", "Omaha 8", "Razz", "Seven Card Stud", "Seven Card Stud 8"]

    # Player selects Omaha 8 (index 1 in the possible values list)
    omaha_8_index = valid_actions[0][3].index("Razz")
    result = game.player_action("utg", PlayerAction.CHOOSE, amount=omaha_8_index)
    assert result.success
    assert result.advance_step
    assert game.game_choices["Game"] == "Razz"

    # skipping these 3 steps
    # Step 3: Deal Additional Card for Omaha 8
    # Step 4: Discard for Hold'em 
    # Step 5: Pre-Flop Bet for Hold'em or Omaha 

    # Step 6: Grouped Bet/Expose for Stud games
    game._next_step()
    assert game.current_step == 6
    assert game.state == GameState.BETTING
    assert game.action_handler.current_substep == 0    

    assert game.current_player.id == 'utg'
    valid_actions = game.get_valid_actions('utg')
    print(f"valid_actions = {valid_actions}")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    game.player_action('utg', PlayerAction.FOLD)    

def test_game_results_two_player_razz():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck_two_players_razz()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    assert game.table.players['sb'].stack == 499  # SB deducted
    assert game.table.players['bb'].stack == 498  # BB deducted
    assert game.table.players['utg'].stack == 500  # 
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game


    # Step 1: Deal Hole Cards (3 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['utg'].hand.cards[0]) == "As"  # sb
    assert str(game.table.players['utg'].hand.cards[1]) == "3s"  # sb
    assert str(game.table.players['utg'].hand.cards[2]) == "8s"  # sb
    assert str(game.table.players['sb'].hand.cards[0]) == "5s"  # bb
    assert str(game.table.players['sb'].hand.cards[1]) == "Ts"  # bb  
    assert str(game.table.players['sb'].hand.cards[2]) == "7s"  # bb     
    assert str(game.table.players['bb'].hand.cards[0]) == "Qs"  # utg
    assert str(game.table.players['bb'].hand.cards[1]) == "9s"  # utg  
    assert str(game.table.players['bb'].hand.cards[2]) == "6s"  # utg      
   
    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    
    # Step 2: Choose Game Type

    game._next_step()  
    assert game.current_step == 2
    assert game.state == GameState.DEALING   

    # check the current player - should be utg - after the big blind
    assert game.current_player.id == 'utg'    

    valid_actions = game.get_valid_actions("utg")
    # Format: (action, min_index, max_index, choices_list)
    assert valid_actions[0][0] == PlayerAction.CHOOSE
    assert valid_actions[0][3] == ["Hold'em", "Omaha 8", "Razz", "Seven Card Stud", "Seven Card Stud 8"]

    # Player selects Omaha 8 (index 1 in the possible values list)
    omaha_8_index = valid_actions[0][3].index("Razz")
    result = game.player_action("utg", PlayerAction.CHOOSE, amount=omaha_8_index)
    assert result.success
    assert result.advance_step
    assert game.game_choices["Game"] == "Razz"

    # skipping these 3 steps
    # Step 3: Deal Additional Card for Omaha 8
    # Step 4: Discard for Hold'em 
    # Step 5: Pre-Flop Bet for Hold'em or Omaha 

    # Step 6: Grouped Bet/Expose for Stud games
    game._next_step()
    assert game.current_step == 6
    assert game.state == GameState.BETTING
    assert game.action_handler.current_substep == 0    

    # this is wrong - should be UTG but game is outputting SB - i think it's going back to SB since game things we are in a regular round
    assert game.current_player.id == 'utg'
    valid_actions = game.get_valid_actions('utg')
    print(f"valid_actions = {valid_actions}")
    assert (PlayerAction.FOLD, None, None) in valid_actions
    game.player_action('utg', PlayerAction.FOLD)    

# test out player choice of Omaha 8 (aha Omaha Hi-Lo)

def test_game_results_two_player_omaha_hilo():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck_two_players_omaha_hilo()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    assert game.table.players['p1'].stack == 499  # SB deducted
    assert game.table.players['p2'].stack == 498  # BB deducted
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game


    # Step 1: Deal Hole Cards (3 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['p1'].hand.cards[0]) == "As"  # Alice
    assert str(game.table.players['p1'].hand.cards[1]) == "Qs"  # Alice
    assert str(game.table.players['p1'].hand.cards[2]) == "Ts"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "5s"  # Bob
    assert str(game.table.players['p2'].hand.cards[1]) == "3s"  # Bob  
    assert str(game.table.players['p2'].hand.cards[2]) == "9s"  # Bob     

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    
    # Step 2: Choose Game Type

    game._next_step()  
    assert game.current_step == 2
    assert game.state == GameState.DEALING   

    # check the current player - should be p1 - after the big blind
    assert game.current_player.id == 'p1'    

    valid_actions = game.get_valid_actions("p1")
    # Format: (action, min_index, max_index, choices_list)
    assert valid_actions[0][0] == PlayerAction.CHOOSE
    assert valid_actions[0][3] == ["Hold'em", "Omaha 8", "Razz", "Seven Card Stud", "Seven Card Stud 8"]

    # Player selects Omaha 8 (index 1 in the possible values list)
    omaha_8_index = valid_actions[0][3].index("Omaha 8")
    result = game.player_action("p1", PlayerAction.CHOOSE, amount=omaha_8_index)
    assert result.success
    assert result.advance_step
    assert game.game_choices["Game"] == "Omaha 8"

    # Step 3: Deal Additional Card (for Omaha 8)

    game._next_step()  # Deal hole cards
    assert game.current_step == 3
    assert game.state == GameState.DEALING    

    # Verify new hole cards

    assert str(game.table.players['p1'].hand.cards[3]) == "8s"  # Alice
    assert str(game.table.players['p2'].hand.cards[3]) == "7s"  # Bob    

    # should have Omaha hands now
    assert len(game.table.players["p1"].hand.cards) == 4
    assert len(game.table.players["p2"].hand.cards) == 4     

    # Step 4: Discard for Hold'em (should skip and go to Pre-Flop Bet)

    # Step 5: Pre-Flop Bet (for Hold'em or Omaha)
    game._next_step()
    assert game.current_step == 5
    assert game.state == GameState.BETTING


    # check the current player - should be p1 - after the big blind
    assert game.current_player.id == 'p1'

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game    

    # Check valid actions for p1
    valid_actions = game.get_valid_actions("p1")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 2, 2) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 4, 500) in valid_actions  # raise another small bet (big blind)

    # p1 raises
    results = game.player_action('p1', PlayerAction.RAISE, 200)
    print(f"p1 results = {results}")
    assert results.success
    assert not results.advance_step

    # Check pot after Alice's action
    assert game.betting.get_main_pot_amount() == 202  # $2 SB + $200 raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check valid actions for p2
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 200, 200) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 398, 500) in valid_actions  # minimum correct?  max is all-in

    # p2 calls
    assert game.current_player.id == 'p2'
    results = game.player_action('p2', PlayerAction.CALL, 200)
    print(f"p2 results = {results}")
    assert results.success
    assert results.advance_step

    # Check pot after action
    assert game.betting.get_main_pot_amount() == 400  # $200 from each
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check player stacks - each player put in $200

    assert game.table.players['p1'].stack == 300
    assert game.table.players['p2'].stack == 300

    # Step 6: Bet/Expose (for Stud games)
    # Step 7: Deal Flop
    game._next_step()
    assert game.current_step == 7
    assert game.state == GameState.DEALING 

    # Check community cards
    assert str(game.table.community_cards["default"][0]) == "6s"  # Flop 1
    assert str(game.table.community_cards["default"][1]) == "Jh"  # Flop 2
    assert str(game.table.community_cards["default"][2]) == "2d"  # Flop 3
                                      
    # Check pot after flop
    assert game.betting.get_main_pot_amount() == 400  


    # Step 8: Fourth Street (skipped for non-Stud games)
    # Step 9: Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 9
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p2"  # SB acts first in post-flop betting rounds

    # Check valid actions for SB (Bob)
    # SB acts first in post-flop betting round
    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 2, 300) in valid_actions  # bet small bet

    # SB checks
    results = game.player_action('p2', PlayerAction.CHECK)
    print(f"p2 results = {results}")

    # BB checks
    results = game.player_action('p1', PlayerAction.CHECK)
    print(f"p1 results = {results}")

    # Check pot after post-flop betting
    assert game.betting.get_main_pot_amount() == 400  # SB + BB + BTN raise




    # Step 10: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 10
    assert game.state == GameState.DEALING
    
    # Check community cards
    assert str(game.table.community_cards["default"][3]) == "4h"  # Turn

    # Check pot after turn
    assert game.betting.get_main_pot_amount() == 400  # 
    
    # Step 11: Deal Fifth Street (skipped for non-Stud games)

    # Step 12: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 12
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 2, 300) in valid_actions  # bet small bet

    # SB checks
    game.player_action('p2', PlayerAction.CHECK)
    print(f"p2 results = {results}")

    # BB checks
    game.player_action('p1', PlayerAction.CHECK)
    print(f"p1 results = {results}")

    # Check pot after turn betting
    assert game.betting.get_main_pot_amount() == 400  # SB + BB + BTN raise




    # Step 13: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 13
    assert game.state == GameState.DEALING

    # Check community cards
    assert str(game.table.community_cards["default"][4]) == "3c"  # River

    # Check pot after river
    assert game.betting.get_main_pot_amount() == 400  #
    
    # Step 14: Deal Sixth Street (skipped for non-Stud games)

    # Step 15: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 15
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 2, 300) in valid_actions  # bet small bet

    # SB checks
    game.player_action('p2', PlayerAction.CHECK)
    print(f"p2 results = {results}")

    # BB checks
    game.player_action('p1', PlayerAction.CHECK)
    print(f"p1 results = {results}")

    # Check pot after river betting
    assert game.betting.get_main_pot_amount() == 400  # SB + BB + BTN raise
    
    # Step 16: Deal Seventh Street (skipped for non-Stud games)
    # Step 17: Seventh Street Bet (Skipped for non-Stud games)

    # Step 18: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 18
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print('\nShowdown Results (Human):')
    print(results)
    print('\nShowdown Results (JSON):')
    print(results.to_json())

    # Check overall results
    expected_pot = 400  
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 2  # hi hand and lo hand
    assert len(results.hands) == 2  # All players stayed in

    # Check pot details
    main_pot = results.pots[0]
    assert main_pot.amount == expected_pot // 2
    assert main_pot.pot_type == "main"
    assert not main_pot.split  # Only one winner
    assert len(main_pot.winners) == 1
    assert 'p2' in main_pot.winners

    winning_hand = results.hands['p2']
    assert "Straight" in winning_hand[0].hand_name
    assert "Seven-high Straight" in winning_hand[0].hand_description
    
    assert "High Card" in winning_hand[1].hand_name
    assert "Six High" in winning_hand[1].hand_description

    # Check winning hands list
    assert len(results.winning_hands) == 2
    assert results.winning_hands[0].player_id == 'p2'


def test_game_results_two_player_holdem():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck_two_players_holdem()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    assert game.table.players['p1'].stack == 499  # SB deducted
    assert game.table.players['p2'].stack == 498  # BB deducted
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game


    # Step 1: Deal Hole Cards (3 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['p1'].hand.cards[0]) == "As"  # Alice
    assert str(game.table.players['p1'].hand.cards[1]) == "Qs"  # Alice
    assert str(game.table.players['p1'].hand.cards[2]) == "Ts"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "Ks"  # Bob
    assert str(game.table.players['p2'].hand.cards[1]) == "Js"  # Bob  
    assert str(game.table.players['p2'].hand.cards[2]) == "9h"  # Bob     

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game



    
    # Step 2: Choose Game Type

    game._next_step()  # Deal hole cards
    assert game.current_step == 2
    assert game.state == GameState.DEALING   

    # check the current player - should be p1 - after the big blind
    assert game.current_player.id == 'p1'    

    valid_actions = game.get_valid_actions("p1")
    # Format: (action, min_index, max_index, choices_list)
    assert valid_actions[0][0] == PlayerAction.CHOOSE
    assert valid_actions[0][3] == ["Hold'em", "Omaha 8", "Razz", "Seven Card Stud", "Seven Card Stud 8"]

    # Player selects Omaha 8 (index 1 in the possible values list)
    holdem_index = valid_actions[0][3].index("Hold'em")
    result = game.player_action("p1", PlayerAction.CHOOSE, amount=holdem_index)
    assert result.success
    assert result.advance_step
    assert game.game_choices["Game"] == "Hold'em"



    # Step 3: Deal Additional Card (for Omaha 8) - should skip
    # Step 4: Discard for Hold'em 
    game._next_step()
    assert game.current_step == 4  # Should skip step 3 and go to step 4 (Discard)
    assert game.state == GameState.DRAWING

    assert game.current_player.id == 'p2'
    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.DISCARD, 1, 1) in valid_actions

    # Player discards a card
    result = game.player_action('p2', PlayerAction.DISCARD, cards=[game.table.players['p2'].hand.cards[0]])
    assert result.success
    assert not result.advance_step

    # p1
    assert game.current_player.id == 'p1'
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.DISCARD, 1, 1) in valid_actions

    # Player discards a card
    result = game.player_action('p1', PlayerAction.DISCARD, cards=[game.table.players['p1'].hand.cards[0]])
    assert result.success
    assert result.advance_step



    # Step 5: Pre-Flop Bet
    game._next_step()
    assert game.current_step == 5
    assert game.state == GameState.BETTING


    # check the current player - should be p1 - after the big blind
    assert game.current_player.id == 'p1'

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game    

    # Check valid actions for p1
    valid_actions = game.get_valid_actions("p1")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 2, 2) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 4, 500) in valid_actions  # raise another small bet (big blind)

    # p1 raises
    results = game.player_action('p1', PlayerAction.RAISE, 200)
    print(f"p1 results = {results}")
    assert results.success

    # Check pot after Alice's action
    assert game.betting.get_main_pot_amount() == 202  # $2 SB + $200 raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check valid actions for p2
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 200, 200) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 398, 500) in valid_actions  # minimum correct?  max is all-in

    # p2 calls
    assert game.current_player.id == 'p2'
    results = game.player_action('p2', PlayerAction.CALL, 200)
    print(f"p2 results = {results}")
    assert results.success

    # Check pot after action
    assert game.betting.get_main_pot_amount() == 400  # $200 from each
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check player stacks - each player put in $200

    assert game.table.players['p1'].stack == 300
    assert game.table.players['p2'].stack == 300



    # Step 6: Bet and Expose Card if Stud game selected
    # Step 7: Deal Flop
    game._next_step()
    assert game.current_step == 7
    assert game.state == GameState.DEALING 

    # Check community cards
    assert str(game.table.community_cards["default"][0]) == "8h"  # Flop 1
    assert str(game.table.community_cards["default"][1]) == "7h"  # Flop 2
    assert str(game.table.community_cards["default"][2]) == "6s"  # Flop 3
                  
    # Check pot after flop
    assert game.betting.get_main_pot_amount() == 400  




    # Step 8: Fourth Street (skipped for non-Stud games)
    # Step 9: Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 9
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p2"  # SB acts first in post-flop betting rounds

    # Check valid actions for SB (Bob)
    # SB acts first in post-flop betting round
    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 2, 300) in valid_actions  # bet small bet

    # SB checks
    results = game.player_action('p2', PlayerAction.CHECK)
    print(f"p2 results = {results}")

    # BB checks
    results = game.player_action('p1', PlayerAction.CHECK)
    print(f"p1 results = {results}")

    # Check pot after post-flop betting
    assert game.betting.get_main_pot_amount() == 400  # SB + BB + BTN raise




    # Step 10: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 10
    assert game.state == GameState.DEALING
    
    # Check community cards
    assert str(game.table.community_cards["default"][3]) == "Jh"  # Turn

    # Check pot after turn
    assert game.betting.get_main_pot_amount() == 400  # 
    
    # Step 11: Deal Fifth Street (skipped for non-Stud games)

    # Step 12: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 12
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 2, 300) in valid_actions  # bet small bet

    # SB checks
    game.player_action('p2', PlayerAction.CHECK)
    print(f"p2 results = {results}")

    # BB checks
    game.player_action('p1', PlayerAction.CHECK)
    print(f"p1 results = {results}")

    # Check pot after turn betting
    assert game.betting.get_main_pot_amount() == 400  # SB + BB + BTN raise
    


    # Step 13: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 13
    assert game.state == GameState.DEALING

    # Check community cards
    assert str(game.table.community_cards["default"][4]) == "Td"  # River

    # Check pot after river
    assert game.betting.get_main_pot_amount() == 400  #
    
    # Step 14: Deal Sixth Street (skipped for non-Stud games)


    # Step 15: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 15
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("p2")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 2, 300) in valid_actions  # bet small bet

    # SB checks
    game.player_action('p2', PlayerAction.CHECK)
    print(f"p2 results = {results}")

    # BB checks
    game.player_action('p1', PlayerAction.CHECK)
    print(f"p1 results = {results}")

    # Check pot after river betting
    assert game.betting.get_main_pot_amount() == 400  # SB + BB + BTN raise
    
    # Step 16/17 - Seventh Street (skipped for non-Stud games)

    # Step 18: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 18
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print('\nShowdown Results (Human):')
    print(results)
    print('\nShowdown Results (JSON):')
    print(results.to_json())

    # Check overall results
    expected_pot = 400  
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 1  # Just main pot
    assert len(results.hands) == 2  # All players stayed in

    # Check pot details
    main_pot = results.pots[0]
    assert main_pot.amount == expected_pot 
    assert main_pot.pot_type == "main"
    assert not main_pot.split  # Only one winner
    assert len(main_pot.winners) == 1
    assert 'p2' in main_pot.winners

    winning_hand = results.hands['p2']
    assert "Straight" in winning_hand[0].hand_name
    assert "Jack-high Straight" in winning_hand[0].hand_description

    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'p2'          

def create_predetermined_deck_three_players_seven_card_stud():
    """Create a deck with predetermined cards for Seven Card Stud."""
    # Create cards in the desired deal order (first card will be dealt first)
    cards = [
        # Initial 3 cards per player before choice made
        Card(Rank.ACE, Suit.HEARTS),    # Player 1 down card 1
        Card(Rank.KING, Suit.DIAMONDS), # Player 2 down card 1
        Card(Rank.QUEEN, Suit.CLUBS),   # Player 3 down card 1
        Card(Rank.KING, Suit.HEARTS),   # Player 1 down card 2
        Card(Rank.KING, Suit.CLUBS),    # Player 2 down card 2
        Card(Rank.JACK, Suit.DIAMONDS), # Player 3 down card 2
        Card(Rank.QUEEN, Suit.HEARTS),  # Player 1 down card 3
        Card(Rank.TWO, Suit.DIAMONDS),  # Player 2 down card 3
        Card(Rank.QUEEN, Suit.SPADES),  # Player 3 down card 3
        
        # Additional cards for fourth street
        Card(Rank.TEN, Suit.SPADES),    # Player 1 fourth street (up)
        Card(Rank.ACE, Suit.CLUBS),     # Player 2 fourth street (up)
        Card(Rank.QUEEN, Suit.DIAMONDS),# Player 3 fourth street (up)
        
        # Additional cards for fifth street
        Card(Rank.JACK, Suit.HEARTS),   # Player 1 fifth street (up)
        Card(Rank.TEN, Suit.DIAMONDS),  # Player 2 fifth street (up)
        Card(Rank.TEN, Suit.HEARTS),    # Player 3 fifth street (up)
        
        # Additional cards for sixth street
        Card(Rank.NINE, Suit.SPADES),   # Player 1 sixth street (up)
        Card(Rank.NINE, Suit.HEARTS),   # Player 2 sixth street (up)
        Card(Rank.NINE, Suit.DIAMONDS), # Player 3 sixth street (up)
        
        # River cards (down)
        Card(Rank.TWO, Suit.HEARTS),    # Player 1 river (down)
        Card(Rank.TWO, Suit.SPADES),    # Player 2 river (down)
        Card(Rank.ACE, Suit.SPADES),    # Player 3 river (down)
        
        # Extra cards in case needed
        Card(Rank.THREE, Suit.HEARTS),
        Card(Rank.FOUR, Suit.DIAMONDS),
        Card(Rank.FIVE, Suit.SPADES),
    ]   
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_three_players_seven_card_stud():
    """Create a test game with three players and a predetermined deck for Seven Card Stud."""
    rules = load_rules_from_file('paradise_road_pickem')
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=1,
        big_blind=2,   
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
    game.table.deck = create_predetermined_deck_three_players_seven_card_stud()
    
    return game

def test_game_results_three_player_seven_card_stud():
    """Test a full Seven Card Stud game with three players."""
    game = setup_test_game_with_mock_deck_three_players_seven_card_stud()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0
    assert game.state == GameState.BETTING
    assert game.table.players['p1'].stack == 500  # No deduction 
    assert game.table.players['p2'].stack == 499  # SB deducted
    assert game.table.players['p3'].stack == 498  # BB deducted
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    
    # Step 1: Deal Hole Cards (3 down)
    game._next_step()
    assert game.current_step == 1
    assert game.state == GameState.DEALING
    
    # Verify hole cards - all face down before game choice
    # Player 1 - Alice
    assert str(game.table.players['p1'].hand.cards[0]) == "Ah"
    assert str(game.table.players['p1'].hand.cards[1]) == "Kh"
    assert str(game.table.players['p1'].hand.cards[2]) == "Qh"
    assert game.table.players['p1'].hand.cards[0].visibility == Visibility.FACE_DOWN
    assert game.table.players['p1'].hand.cards[1].visibility == Visibility.FACE_DOWN
    assert game.table.players['p1'].hand.cards[2].visibility == Visibility.FACE_DOWN
    
    # Player 2 - Bob
    assert str(game.table.players['p2'].hand.cards[0]) == "Kd"
    assert str(game.table.players['p2'].hand.cards[1]) == "Kc"
    assert str(game.table.players['p2'].hand.cards[2]) == "2d"
    assert game.table.players['p2'].hand.cards[0].visibility == Visibility.FACE_DOWN
    assert game.table.players['p2'].hand.cards[1].visibility == Visibility.FACE_DOWN
    assert game.table.players['p2'].hand.cards[2].visibility == Visibility.FACE_DOWN
    
    # Player 3 - Charlie
    assert str(game.table.players['p3'].hand.cards[0]) == "Qc"
    assert str(game.table.players['p3'].hand.cards[1]) == "Jd"
    assert str(game.table.players['p3'].hand.cards[2]) == "Qs"
    assert game.table.players['p3'].hand.cards[0].visibility == Visibility.FACE_DOWN
    assert game.table.players['p3'].hand.cards[1].visibility == Visibility.FACE_DOWN
    assert game.table.players['p3'].hand.cards[2].visibility == Visibility.FACE_DOWN
    
    # Step 2: Choose Game Type
    game._next_step()
    assert game.current_step == 2
    assert game.state == GameState.DEALING
    assert game.current_player.id == 'p1'
    
    # Player 1 (Alice) chooses Seven Card Stud
    valid_actions = game.get_valid_actions("p1")
    assert valid_actions[0][0] == PlayerAction.CHOOSE
    seven_card_stud_index = valid_actions[0][3].index("Seven Card Stud")
    result = game.player_action("p1", PlayerAction.CHOOSE, amount=seven_card_stud_index)
    assert result.success
    assert game.game_choices["Game"] == "Seven Card Stud"
    
    # Step 3-5: Skip steps for Omaha and Hold'em
    
    # Step 6: Grouped Bet/Expose for Stud games
    game._next_step()
    assert game.current_step == 6
    assert game.state == GameState.BETTING
    assert game.action_handler.current_substep == 0
    
    # First player (should be p1 - Alice) acting after the blinds (p2, p3)
    assert game.current_player.id == 'p1'
    
    # Alice bets and exposes a card
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 2, 2) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 4, 500) in valid_actions  # raise minimum
    
    # Alice bets (calls or raises)
    result = game.player_action('p1', PlayerAction.CALL, 2)
    assert result.success
    assert not result.advance_step  # Round shouldn't be over
    assert game.action_handler.current_substep == 1  # Moved to expose step
    
    # Alice needs to expose a card
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions
    
    # Alice exposes a card (selecting which hole card to expose)
    exposed_card = game.table.players['p1'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('p1', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success
    assert game.table.players['p1'].hand.cards[0].visibility == Visibility.FACE_UP
    
    # Bob's turn
    assert game.current_step == 6           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action
    assert game.current_player.id == 'p2'
    
    # check stacks
    assert game.table.players['p1'].stack == 498  # from call of BB
    assert game.table.players['p2'].stack == 499  # SB deducted
    assert game.table.players['p3'].stack == 498  # BB deducted

    # Bob bets
    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 2, 2) in valid_actions          # call the BB
    assert (PlayerAction.RAISE, 4, 500) in valid_actions        # SB can raise to stack of 500

    result = game.player_action('p2', PlayerAction.CALL, 2)
    assert result.success
    assert not result.advance_step
    assert game.action_handler.current_substep == 1  # Moved to expose step    
    
    # Bob exposes
    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['p2'].hand.cards[0]  # Choose the first hole card (Kd)
    result = game.player_action('p2', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success
    assert game.table.players['p2'].hand.cards[0].visibility == Visibility.FACE_UP
    
    # Charlie's turn
    assert game.current_player.id == 'p3'
    
    # Charlie bets
    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions   
    assert (PlayerAction.RAISE, 4, 500) in valid_actions    

    result = game.player_action('p3', PlayerAction.CALL, 2)
    assert result.success
    
    # Charlie exposes
    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions
    exposed_card = game.table.players['p3'].hand.cards[0]  # Choose the first hole card (Js)
    result = game.player_action('p3', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success
    assert game.table.players['p3'].hand.cards[0].visibility == Visibility.FACE_UP
    
    # Check pot after first betting round
    assert game.betting.get_main_pot_amount() == 6  # 3 players x $2 each
    
    # Step 7: Skip flop step for community card games
    
    # Step 8: Fourth Street deal and betting
    game._next_step()
    assert game.current_step == 8
    assert game.state == GameState.DEALING
       
    # Check that all players now have 4 cards
    assert len(game.table.players['p1'].hand.cards) == 4
    assert len(game.table.players['p2'].hand.cards) == 4
    assert len(game.table.players['p3'].hand.cards) == 4
    
    print("Player 1 hand:", game.table.players['p1'].hand)
    print("Player 2 hand:", game.table.players['p2'].hand)
    print("Player 3 hand:", game.table.players['p3'].hand)
    
    # Fourth street card should be face up
    assert str(game.table.players['p1'].hand.cards[3]) == "Ts"
    assert str(game.table.players['p2'].hand.cards[3]) == "Ac"
    assert str(game.table.players['p3'].hand.cards[3]) == "Qd"
    assert game.table.players['p1'].hand.cards[3].visibility == Visibility.FACE_UP
    assert game.table.players['p2'].hand.cards[3].visibility == Visibility.FACE_UP
    assert game.table.players['p3'].hand.cards[3].visibility == Visibility.FACE_UP
    
    # Betting on 4th street
    # High hand showing should start - Player 3 (Charlie) with Queen pair
    game._next_step()
    assert game.current_step == 9
    assert game.state == GameState.BETTING
    assert game.current_player.id == 'p3'  # Charlie has pair of Queens showing
    
    # Let's check the betting actions round by round
    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.CHECK, None, None) in valid_actions
    assert (PlayerAction.BET, 2, 498) in valid_actions
    
    # Charlie bets
    result = game.player_action('p3', PlayerAction.BET, 2)
    assert result.success
    
    # Alice calls
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 2, 2) in valid_actions
    result = game.player_action('p1', PlayerAction.CALL, 2)
    assert result.success
    
    # Bob calls
    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 2, 2) in valid_actions
    result = game.player_action('p2', PlayerAction.CALL, 2)
    assert result.success
    
    # Check pot after 4th street
    assert game.betting.get_main_pot_amount() == 12  # $6 from first round + $6 from 4th street   

    # Steo 10: Deal Turn is skipped for Stud games

    # Step 11: Fifth Street deal and betting
    game._next_step()
    assert game.current_step == 11
    assert game.state == GameState.DEALING
    
    # Check that all players now have 5 cards
    assert len(game.table.players['p1'].hand.cards) == 5
    assert len(game.table.players['p2'].hand.cards) == 5
    assert len(game.table.players['p3'].hand.cards) == 5
    
    # Fifth street cards should be face up
    assert str(game.table.players['p1'].hand.cards[4]) == "Jh"
    assert str(game.table.players['p2'].hand.cards[4]) == "Td"
    assert str(game.table.players['p3'].hand.cards[4]) == "Th"
    assert game.table.players['p1'].hand.cards[4].visibility == Visibility.FACE_UP
    assert game.table.players['p2'].hand.cards[4].visibility == Visibility.FACE_UP
    assert game.table.players['p3'].hand.cards[4].visibility == Visibility.FACE_UP
    
    # Step 12: Betting on 5th street
    # High hand showing still Charlie with pair of Queens
    game._next_step()
    assert game.current_step == 12
    assert game.state == GameState.BETTING
    assert game.current_player.id == 'p3'
    
    # Charlie bets 
    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.CHECK, None, None) in valid_actions
    assert (PlayerAction.BET, 2, 496) in valid_actions  # big bet
    
    result = game.player_action('p3', PlayerAction.BET, 4)
    assert result.success
    
    # Alice calls
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 4, 4) in valid_actions
    result = game.player_action('p1', PlayerAction.CALL, 4)
    assert result.success
    
    # Bob calls
    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 4, 4) in valid_actions
    result = game.player_action('p2', PlayerAction.CALL, 4)
    assert result.success
    
    # Check pot after 5th street
    assert game.betting.get_main_pot_amount() == 24  # $12 + $12 ($4 x 3 players)
    
    # Step 13: Deal River (skipped)
    # Step 14: Sixth Street deal
    game._next_step()
    assert game.state == GameState.DEALING
    assert game.current_step == 14
      
    # Check that all players now have 6 cards
    assert len(game.table.players['p1'].hand.cards) == 6
    assert len(game.table.players['p2'].hand.cards) == 6
    assert len(game.table.players['p3'].hand.cards) == 6
    
    # Sixth street cards should be face up
    assert str(game.table.players['p1'].hand.cards[5]) == "9s"
    assert str(game.table.players['p2'].hand.cards[5]) == "9h"
    assert str(game.table.players['p3'].hand.cards[5]) == "9d"
    assert game.table.players['p1'].hand.cards[5].visibility == Visibility.FACE_UP
    assert game.table.players['p2'].hand.cards[5].visibility == Visibility.FACE_UP
    assert game.table.players['p3'].hand.cards[5].visibility == Visibility.FACE_UP

    # Go to 6th street betting
    game._next_step()

    # Betting on 6th street - still Charlie with highest hand
    assert game.state == GameState.BETTING
    assert game.current_step == 15
    assert game.current_player.id == 'p3'
    
    # Charlie bets (big bet)
    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.CHECK, None, None) in valid_actions
    assert (PlayerAction.BET, 2, 492) in valid_actions
    
    result = game.player_action('p3', PlayerAction.BET, 4)
    assert result.success
    
    # Alice calls
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 4, 4) in valid_actions
    result = game.player_action('p1', PlayerAction.CALL, 4)
    assert result.success
    
    # Bob calls
    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 4, 4) in valid_actions
    result = game.player_action('p2', PlayerAction.CALL, 4)
    assert result.success
    
    # Check pot after 6th street
    assert game.betting.get_main_pot_amount() == 36  # $24 + $12 ($4 x 3 players)
    
    # Step 16: Seventh Street (river) deal and betting
    game._next_step()
    assert game.state == GameState.DEALING
    assert game.current_step == 16

    # Check that all players now have 7 cards
    assert len(game.table.players['p1'].hand.cards) == 7
    assert len(game.table.players['p2'].hand.cards) == 7
    assert len(game.table.players['p3'].hand.cards) == 7
    
    # River cards should be face down
    assert str(game.table.players['p1'].hand.cards[6]) == "2h"
    assert str(game.table.players['p2'].hand.cards[6]) == "2s"
    assert str(game.table.players['p3'].hand.cards[6]) == "As"
    assert game.table.players['p1'].hand.cards[6].visibility == Visibility.FACE_DOWN
    assert game.table.players['p2'].hand.cards[6].visibility == Visibility.FACE_DOWN
    assert game.table.players['p3'].hand.cards[6].visibility == Visibility.FACE_DOWN
    
    # Bet 7th street (river)
    game._next_step()

    # Betting on river - still Charlie with highest hand
    assert game.state == GameState.BETTING
    assert game.current_step == 17
    assert game.current_player.id == 'p3'
    
    # Charlie bets (big bet)
    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.CHECK, None, None) in valid_actions
    assert (PlayerAction.BET, 2, 488) in valid_actions
    
    result = game.player_action('p3', PlayerAction.BET, 4)
    assert result.success
    
    # Alice calls
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 4, 4) in valid_actions
    result = game.player_action('p1', PlayerAction.CALL, 4)
    assert result.success
    
    # Bob calls
    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 4, 4) in valid_actions
    result = game.player_action('p2', PlayerAction.CALL, 4)
    assert result.success
    
    # Check pot after river
    assert game.betting.get_main_pot_amount() == 48  # $36 + $12 ($4 x 3 players)
    
    # Move to showdown
    game._next_step()
    assert game.state == GameState.COMPLETE
    assert game.current_step == 18

    # Get results
    results = game.get_hand_results()
    
    print('\nShowdown Results (Human):')
    print(results)
    print('\nShowdown Results (JSON):')
    print(results.to_json())
    
    # Check overall results
    expected_pot = 48  
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 1  # Just main pot
    assert len(results.hands) == 3  # All players stayed in
    
    # Check pot details
    main_pot = results.pots[0]
    assert main_pot.amount == expected_pot 
    assert main_pot.pot_type == "main"
    assert not main_pot.split  # Only one winner
    assert len(main_pot.winners) == 1
    assert 'p1' in main_pot.winners  # Bob should win with trip Kings
    
    winning_hand = results.hands['p1']
    assert "Flush" in winning_hand[0].hand_name
    
    # Check final stacks
    assert game.table.players['p1'].stack == 532  # 500 - 16 (bets) + 48 (winnings)
    assert game.table.players['p2'].stack == 484  # 500 - 16 (bets)
    assert game.table.players['p3'].stack == 484  # 500 - 16 (bets)