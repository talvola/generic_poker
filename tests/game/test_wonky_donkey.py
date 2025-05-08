"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
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

def create_predetermined_deck_two_players_omaha():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.SPADES), #
        Card(Rank.KING, Suit.SPADES), #
        Card(Rank.QUEEN, Suit.SPADES), #
        Card(Rank.JACK, Suit.SPADES), #
        Card(Rank.TEN, Suit.SPADES), #
        Card(Rank.NINE, Suit.SPADES), #
        Card(Rank.EIGHT, Suit.SPADES), #
        Card(Rank.SEVEN, Suit.SPADES), #
        Card(Rank.SIX, Suit.SPADES), #
        Card(Rank.JACK, Suit.HEARTS), #
        Card(Rank.TEN, Suit.DIAMONDS), #
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.NINE, Suit.CLUBS), #        
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_two_players_omaha():
    """Create a test game with two players and a predetermined deck."""
    rules = load_rules_from_file('wonky_donkey')
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
        Card(Rank.TEN, Suit.SPADES), # f
        Card(Rank.NINE, Suit.HEARTS), # f
        Card(Rank.EIGHT, Suit.HEARTS), # f
        Card(Rank.SEVEN, Suit.HEARTS), # t 
        Card(Rank.SIX, Suit.SPADES), # r
        Card(Rank.JACK, Suit.HEARTS), # 
        Card(Rank.TEN, Suit.DIAMONDS), # 
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.NINE, Suit.CLUBS), #        
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_two_players_holdem():
    """Create a test game with two players and a predetermined deck."""
    rules = load_rules_from_file('wonky_donkey')
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
        Card(Rank.TEN, Suit.SPADES), # f
        Card(Rank.NINE, Suit.SPADES), # f
        Card(Rank.EIGHT, Suit.SPADES), # f
        Card(Rank.SEVEN, Suit.SPADES), # p1
        Card(Rank.SIX, Suit.SPADES), # p2
        Card(Rank.JACK, Suit.HEARTS), # p1
        Card(Rank.TWO, Suit.DIAMONDS), # p2
        Card(Rank.FOUR, Suit.HEARTS), # t
        Card(Rank.THREE, Suit.CLUBS), # r      
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck_two_players_omaha_hilo():
    """Create a test game with two players and a predetermined deck."""
    rules = load_rules_from_file('wonky_donkey')
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
    
def test_game_results_two_player_omaha():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck_two_players_omaha()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    assert game.table.players['p1'].stack == 499  # SB deducted
    assert game.table.players['p2'].stack == 498  # BB deducted
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 1: Deal Hole Cards (2 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['p1'].hand.cards[0]) == "As"  # Alice
    assert str(game.table.players['p1'].hand.cards[1]) == "Qs"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "Ks"  # Bob
    assert str(game.table.players['p2'].hand.cards[1]) == "Js"  # Bob

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 2: Pre-Flop Bet
    game._next_step()  # Move to pre-flop bet
    assert game.current_step == 2
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

    # Step 3: Deal Flop
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.DEALING 

    # Check community cards
    assert str(game.table.community_cards["Flop"][0]) == "Ts"  # Flop 1
    assert str(game.table.community_cards["Flop"][1]) == "9s"  # Flop 2
    assert str(game.table.community_cards["Flop"][2]) == "8s"  # Flop 3

    # Check pot after flop
    assert game.betting.get_main_pot_amount() == 400  

    # Step 4: Optional additional Deal to players
    # in this case, flop is all black cards, so we deal two additional cards to each player 

    game._next_step()
    assert game.current_step == 4
    assert game.state == GameState.DEALING 
       
    assert str(game.table.players['p1'].hand.cards[2]) == "7s"  # Alice
    assert str(game.table.players['p1'].hand.cards[3]) == "Jh"  # Alice
    assert str(game.table.players['p2'].hand.cards[2]) == "6s"  # Bob
    assert str(game.table.players['p2'].hand.cards[3]) == "Td"  # Bob

    # Step 5: Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 5
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

    # Step 6: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 6
    assert game.state == GameState.DEALING
    
    # Check community cards
    assert str(game.table.community_cards["Turn"][0]) == "Th"  # Turn

    # Check pot after turn
    assert game.betting.get_main_pot_amount() == 400  # 
    
    # Step 7: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 7
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
    
    # Step 8: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 8
    assert game.state == GameState.DEALING

    # Check community cards
    assert str(game.table.community_cards["River"][0]) == "9c"  # River

    # Check pot after river
    assert game.betting.get_main_pot_amount() == 400  #
    
    # Step 9: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 9
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
    
    # Step 9: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 10
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print('\nShowdown Results (Human):')
    print(results)
    print('\nShowdown Results (JSON):')
    print(results.to_json())

    # Check overall results
    expected_pot = 400  # SB + BB + BTN all put in $20
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
    assert 'p1' in main_pot.winners

    winning_hand = results.hands['p1']
    assert "Flush" in winning_hand[0].hand_name
    assert "Ace-high Flush" in winning_hand[0].hand_description

    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'p1'        

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

    # Step 1: Deal Hole Cards (2 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['p1'].hand.cards[0]) == "As"  # Alice
    assert str(game.table.players['p1'].hand.cards[1]) == "Qs"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "Ks"  # Bob
    assert str(game.table.players['p2'].hand.cards[1]) == "Js"  # Bob

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 2: Pre-Flop Bet
    game._next_step()  # Move to pre-flop bet
    assert game.current_step == 2
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

    # Step 3: Deal Flop
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.DEALING 

    # Check community cards
    assert str(game.table.community_cards["Flop"][0]) == "Ts"  # Flop 1
    assert str(game.table.community_cards["Flop"][1]) == "9h"  # Flop 2
    assert str(game.table.community_cards["Flop"][2]) == "8h"  # Flop 3 
    
    # Check pot after flop
    assert game.betting.get_main_pot_amount() == 400  

    # Step 4: Optional additional Deal to players
    # in this case, flop is all black cards, so we deal two additional cards to each player 

    game._next_step()
    assert game.current_step == 4
    assert game.state == GameState.DEALING 
       
    # Step 5: Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 5
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

    # Step 6: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 6
    assert game.state == GameState.DEALING

    # Check community cards
    assert str(game.table.community_cards["Turn"][0]) == "7h"  # Turn

    # Check pot after turn
    assert game.betting.get_main_pot_amount() == 400  # 
    
    # Step 7: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 7
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
    
    # Step 8: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 8
    assert game.state == GameState.DEALING

    # Check community cards
    assert str(game.table.community_cards["River"][0]) == "6s"  # River

    # Check pot after river
    assert game.betting.get_main_pot_amount() == 400  #
    
    # Step 9: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 9
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
    
    # Step 9: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 10
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print('\nShowdown Results (Human):')
    print(results)
    print('\nShowdown Results (JSON):')
    print(results.to_json())

    # Check overall results
    expected_pot = 400  # SB + BB + BTN all put in $20
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

    # Step 1: Deal Hole Cards (2 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['p1'].hand.cards[0]) == "As"  # Alice
    assert str(game.table.players['p1'].hand.cards[1]) == "Qs"  # Alice
    assert str(game.table.players['p2'].hand.cards[0]) == "5s"  # Bob
    assert str(game.table.players['p2'].hand.cards[1]) == "3s"  # Bob  
 
    # pot unchanged
    assert game.betting.get_main_pot_amount() == 3  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 2: Pre-Flop Bet
    game._next_step()  # Move to pre-flop bet
    assert game.current_step == 2
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

    # Step 3: Deal Flop
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.DEALING 

    # Check community cards
    assert str(game.table.community_cards["Flop"][0]) == "Ts"  # Flop 1
    assert str(game.table.community_cards["Flop"][1]) == "9s"  # Flop 2
    assert str(game.table.community_cards["Flop"][2]) == "8s"  # Flop 3
        
    # Check pot after flop
    assert game.betting.get_main_pot_amount() == 400  

    # Step 4: Optional additional Deal to players
    # in this case, flop is all black cards, so we deal two additional cards to each player 

    game._next_step()
    assert game.current_step == 4
    assert game.state == GameState.DEALING 
       
    assert str(game.table.players['p1'].hand.cards[2]) == "7s"  # Alice
    assert str(game.table.players['p1'].hand.cards[3]) == "Jh"  # Alice
    assert str(game.table.players['p2'].hand.cards[2]) == "6s"  # Bob
    assert str(game.table.players['p2'].hand.cards[3]) == "2d"  # Bob
    
    # Step 5: Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 5
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

    # Step 6: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 6
    assert game.state == GameState.DEALING
    
    # Check community cards
    assert str(game.table.community_cards["Turn"][0]) == "4h"  # Turn

    # Check pot after turn
    assert game.betting.get_main_pot_amount() == 400  # 
    
    # Step 7: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 7
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
    
    # Step 8: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 8
    assert game.state == GameState.DEALING

    # Check community cards
    assert str(game.table.community_cards["River"][0]) == "3c"  # River

    # Check pot after river
    assert game.betting.get_main_pot_amount() == 400  #
    
    # Step 9: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 9
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
    
    # Step 9: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 10
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print('\nShowdown Results (Human):')
    print(results)
    print('\nShowdown Results (JSON):')
    print(results.to_json())

    # Check overall results
    expected_pot = 400  # SB + BB + BTN all put in $20
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 2  # Just main pot
    assert len(results.hands) == 2  # All players stayed in

    # Check pot details
    main_pot = results.pots[0]
    assert main_pot.amount == expected_pot // 2
    assert main_pot.pot_type == "main"
    assert not main_pot.split  # Only one winner
    assert len(main_pot.winners) == 1
    assert 'p1' in main_pot.winners

    winning_hand = results.hands['p1']
    assert "Flush" in winning_hand[0].hand_name
    assert "Ace-high Flush" in winning_hand[0].hand_description

    # Check winning hands list
    assert len(results.winning_hands) == 2
    assert results.winning_hands[0].player_id == 'p1'           