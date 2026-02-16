"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck
from generic_poker.evaluation.hand_description import HandDescriber, EvaluationType
from tests.test_helpers import load_rules_from_file

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
        Card(Rank.ACE, Suit.HEARTS), #BTN
        Card(Rank.QUEEN, Suit.DIAMONDS), #SB
        Card(Rank.JACK, Suit.SPADES), #BB
        Card(Rank.KING, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.CLUBS), #SB
        Card(Rank.JACK, Suit.DIAMONDS), #BB
        Card(Rank.QUEEN, Suit.HEARTS), #FLOP
        Card(Rank.KING, Suit.DIAMONDS), #FLOP
        Card(Rank.TEN, Suit.SPADES), #FLOP
        Card(Rank.QUEEN, Suit.CLUBS), #TURN
        Card(Rank.QUEEN, Suit.SPADES), #RIVER
        Card(Rank.JACK, Suit.HEARTS), #
        Card(Rank.TEN, Suit.DIAMONDS), #
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.NINE, Suit.SPADES), #
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def create_predetermined_deck_split():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.HEARTS), #BTN
        Card(Rank.QUEEN, Suit.DIAMONDS), #SB
        Card(Rank.EIGHT, Suit.SPADES), #BB
        Card(Rank.KING, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.CLUBS), #SB
        Card(Rank.SIX, Suit.DIAMONDS), #BB
        Card(Rank.QUEEN, Suit.HEARTS), #FLOP
        Card(Rank.KING, Suit.DIAMONDS), #FLOP
        Card(Rank.FOUR, Suit.SPADES), #FLOP
        Card(Rank.TWO, Suit.CLUBS), #TURN
        Card(Rank.THREE, Suit.SPADES), #RIVER
        Card(Rank.FIVE, Suit.HEARTS), #
        Card(Rank.TEN, Suit.DIAMONDS), #
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.NINE, Suit.SPADES), #
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    game = Game(
        rules=load_rules_from_file('hold_em_8'),
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False
    )
  
    # Add players
    game.add_player("BTN", "Alice", 500)
    game.add_player("SB", "Bob", 500)
    game.add_player("BB", "Charlie", 500)
    
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
    

def test_game_results_showdown_high():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    assert game.table.players['SB'].stack == 495  # SB deducted
    assert game.table.players['BB'].stack == 490  # BB deducted
    assert game.table.players['BTN'].stack == 500 # has not acted yet 
    assert game.betting.get_main_pot_amount() == 15  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 1: Deal Hole Cards (2 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    
    # Verify hole cards
    assert str(game.table.players['BTN'].hand.cards[0]) == "Ah"  # Alice
    assert str(game.table.players['BTN'].hand.cards[1]) == "Kh"  # Alice
    assert str(game.table.players['SB'].hand.cards[0]) == "Qd"  # Bob
    assert str(game.table.players['SB'].hand.cards[1]) == "Kc"  # Bob
    assert str(game.table.players['BB'].hand.cards[0]) == "Js"  # Charlie
    assert str(game.table.players['BB'].hand.cards[1]) == "Jd"  # Charlie

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 15  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 2: Pre-Flop Bet
    game._next_step()  # Move to pre-flop bet
    assert game.current_step == 2
    assert game.state == GameState.BETTING    
    # check the current player - should be Button (BTN - Alice) for 3-handed games with blinds
    assert game.current_player.id == 'BTN'

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 15  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game    

    # Check valid actions for button (Alice)
    valid_actions = game.get_valid_actions("BTN")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 20, 20) in valid_actions  # raise another small bet (big blind)

    # Alice raises
    game.player_action('BTN', PlayerAction.RAISE, 20)

    # Check pot after Alice's action
    assert game.betting.get_main_pot_amount() == 35  # SB + BB + BTN raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 20, 20) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 30, 30) in valid_actions  # raise another small bet (big blind)

    # SB calls
    game.player_action('SB', PlayerAction.CALL, 20)

    # Check pot after Bob's action
    assert game.betting.get_main_pot_amount() == 50  # adds $15 to call the raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check valid actions for BB (Charlie)
    valid_actions = game.get_valid_actions("BB")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 20, 20) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 30, 30) in valid_actions  # raise another small bet (big blind)

    # BB calls
    game.player_action('BB', PlayerAction.CALL, 20)

    # Check pot after Charlie's action
    assert game.betting.get_main_pot_amount() == 60  # adds $10 to call the raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check player stacks - each player put in $20

    assert game.table.players['SB'].stack == 480
    assert game.table.players['BB'].stack == 480
    assert game.table.players['BTN'].stack == 480

    # Step 3: Deal Flop
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.DEALING 

    # Check community cards
    assert str(game.table.community_cards["default"][0]) == "Qh"  # Flop 1
    assert str(game.table.community_cards["default"][1]) == "Kd"  # Flop 2
    assert str(game.table.community_cards["default"][2]) == "Ts"  # Flop 3

    # Check pot after flop
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise

    # Step 4: Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 4
    assert game.state == GameState.BETTING
    assert game.current_player.id == "SB"  # SB acts first in post-flop betting rounds

    # Check valid actions for SB (Bob)
    # SB acts first in post-flop betting round
    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 10, 10) in valid_actions  # bet small bet

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Check pot after post-flop betting
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise

    # Step 5: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 5
    assert game.state == GameState.DEALING
    
    # Check community cards
    assert str(game.table.community_cards["default"][3]) == "Qc"  # Turn

    # Check pot after turn
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 6: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 6
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 20, 20) in valid_actions  # bet big bet

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Check pot after turn betting
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 7: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 7
    assert game.state == GameState.DEALING

    # Check community cards
    assert str(game.table.community_cards["default"][4]) == "Qs"  # River

    # Check pot after river
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 8: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 8
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 20, 20) in valid_actions  # bet big bet

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Check pot after river betting
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 9: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 9
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    expected_pot = 60  # SB + BB + BTN all put in $20   
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 1  # no low qualified - so only one pot
    assert len(results.hands) == 3  # All players have hands in the result
    
    # Get the pot
    high_pot = next((pot for pot in results.pots if pot.hand_type == "High Hand"), None)
    
    assert high_pot is not None
    
    # Check high pot details
    assert high_pot.amount == expected_pot  # Entire pot goes to high
    assert high_pot.pot_type == "main"
    assert len(high_pot.winners) == 1
    assert "SB" in high_pot.winners

 

def test_game_results_showdown_split():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    game.table.deck = create_predetermined_deck_split()

    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    assert game.table.players['SB'].stack == 495  # SB deducted
    assert game.table.players['BB'].stack == 490  # BB deducted
    assert game.table.players['BTN'].stack == 500 # has not acted yet 
    assert game.betting.get_main_pot_amount() == 15  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 1: Deal Hole Cards (2 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING    

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 15  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Step 2: Pre-Flop Bet
    game._next_step()  # Move to pre-flop bet
    assert game.current_step == 2
    assert game.state == GameState.BETTING    
    # check the current player - should be Button (BTN - Alice) for 3-handed games with blinds
    assert game.current_player.id == 'BTN'

    # pot unchanged
    assert game.betting.get_main_pot_amount() == 15  # SB + BB
    assert game.betting.get_ante_total() == 0  # no antes used in this game    

    # Check valid actions for button (Alice)
    valid_actions = game.get_valid_actions("BTN")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 10, 10) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 20, 20) in valid_actions  # raise another small bet (big blind)

    # Alice raises
    game.player_action('BTN', PlayerAction.RAISE, 20)

    # Check pot after Alice's action
    assert game.betting.get_main_pot_amount() == 35  # SB + BB + BTN raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 20, 20) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 30, 30) in valid_actions  # raise another small bet (big blind)

    # SB calls
    game.player_action('SB', PlayerAction.CALL, 20)

    # Check pot after Bob's action
    assert game.betting.get_main_pot_amount() == 50  # adds $15 to call the raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check valid actions for BB (Charlie)
    valid_actions = game.get_valid_actions("BB")
    assert len(valid_actions) == 3  # Bring-in or complete
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CALL, 20, 20) in valid_actions  # call the BB
    assert (PlayerAction.RAISE, 30, 30) in valid_actions  # raise another small bet (big blind)

    # BB calls
    game.player_action('BB', PlayerAction.CALL, 20)

    # Check pot after Charlie's action
    assert game.betting.get_main_pot_amount() == 60  # adds $10 to call the raise
    assert game.betting.get_ante_total() == 0  # no antes used in this game

    # Check player stacks - each player put in $20

    assert game.table.players['SB'].stack == 480
    assert game.table.players['BB'].stack == 480
    assert game.table.players['BTN'].stack == 480

    # Step 3: Deal Flop
    game._next_step()
    assert game.current_step == 3
    assert game.state == GameState.DEALING 

    # Check pot after flop
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise

    # Step 4: Post-Flop Bet
    game._next_step()  # Move to post-flop bet
    assert game.current_step == 4
    assert game.state == GameState.BETTING
    assert game.current_player.id == "SB"  # SB acts first in post-flop betting rounds

    # Check valid actions for SB (Bob)
    # SB acts first in post-flop betting round
    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 10, 10) in valid_actions  # bet small bet

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Check pot after post-flop betting
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise

    # Step 5: Deal Turn
    game._next_step()  # Deal turn
    assert game.current_step == 5
    assert game.state == GameState.DEALING
    
    # Check pot after turn
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 6: Turn Bet
    game._next_step()  # Move to turn bet
    assert game.current_step == 6
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 20, 20) in valid_actions  # bet big bet

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Check pot after turn betting
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 7: Deal River
    game._next_step()  # Deal river
    assert game.current_step == 7
    assert game.state == GameState.DEALING

    # Check pot after river
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 8: River Bet
    game._next_step()  # Move to river bet
    assert game.current_step == 8
    assert game.state == GameState.BETTING

    # Check valid actions for SB (Bob)
    valid_actions = game.get_valid_actions("SB")
    assert len(valid_actions) == 3  # Check valid actions
    assert (PlayerAction.FOLD, None, None) in valid_actions
    assert (PlayerAction.CHECK, None, None) in valid_actions  # check
    assert (PlayerAction.BET, 20, 20) in valid_actions  # bet big bet

    # SB checks
    game.player_action('SB', PlayerAction.CHECK)
    # BB checks
    game.player_action('BB', PlayerAction.CHECK)
    # BTN checks
    game.player_action('BTN', PlayerAction.CHECK)

    # Check pot after river betting
    assert game.betting.get_main_pot_amount() == 60  # SB + BB + BTN raise
    
    # Step 9: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 9
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    expected_pot = 60  # SB + BB + BTN all put in $20 
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 2  # high pot and low qualified 
    assert len(results.hands) == 3  # All players have hands in the result
    
    # High pot
    high_pot = next(pot for pot in results.pots if pot.hand_type == "High Hand")
    assert high_pot.amount == 30, f"Expected high pot of $30, got ${high_pot.amount}"
    assert high_pot.winners == ["SB"], f"Expected high pot winner SB, got {high_pot.winners}"
    assert not high_pot.split, "High pot should not be split"
    assert high_pot.pot_type == "main", "High pot should be main pot"

    # Low pot
    low_pot = next(pot for pot in results.pots if pot.hand_type == "Low Hand")
    assert low_pot.amount == 30, f"Expected low pot of $30, got ${low_pot.amount}"
    assert low_pot.winners == ["BB"], f"Expected low pot winner BB, got {low_pot.winners}"
    assert not low_pot.split, "Low pot should not be split"
    assert low_pot.pot_type == "main", "Low pot should be main pot"

    # Check hands for SB (assuming hands is a dict of lists)
    sb_hands = results.hands["SB"]
    assert len(sb_hands) == 2, "SB should have two hand evaluations (high and low)"

    # SB High hand
    sb_high = next(hand for hand in sb_hands if hand.hand_type == "High Hand")
    assert "Two Pair" in sb_high.hand_name, f"Expected 'Two Pair' in SB high hand name, got {sb_high.hand_name}"
    assert "Kings and Queens" in sb_high.hand_description, f"Expected 'Kings and Queens' in SB high hand description, got {sb_high.hand_description}"

    # Check hands for BB
    bb_hands = results.hands["BB"]
    assert len(bb_hands) == 2, "BB should have two hand evaluations (high and low)"
    
    # BB Low hand
    bb_low = next(hand for hand in bb_hands if hand.hand_type == "Low Hand")
    assert "Eight High" in bb_low.hand_description, f"Expected 'Eight High' in BB low hand description, got {bb_low.hand_description}"

    # Check winning hands list
    assert len(results.winning_hands) == 2, f"Expected 2 winning hands, got {len(results.winning_hands)}"
    
    # Verify winning hands
    winning_high = next(hand for hand in results.winning_hands if hand.hand_type == "High Hand")
    assert winning_high.player_id == "SB", f"Expected SB as high hand winner, got {winning_high.player_id}"
    assert "Two Pair" in winning_high.hand_name, f"Expected 'Two Pair' in winning high hand, got {winning_high.hand_name}"
    assert "Kings and Queens" in winning_high.hand_description, f"Expected 'Kings and Queens' in winning high hand description, got {winning_high.hand_description}"

    winning_low = next(hand for hand in results.winning_hands if hand.hand_type == "Low Hand")
    assert winning_low.player_id == "BB", f"Expected BB as low hand winner, got {winning_low.player_id}"
    assert "Eight High" in winning_low.hand_description, f"Expected 'Eight High' in winning low hand description, got {winning_low.hand_description}"