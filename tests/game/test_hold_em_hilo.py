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

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    game = Game(
        rules=load_rules_from_file('hold_em_hilo'),
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
    

def test_game_results():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Step 0: Post Blinds
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    assert game.state == GameState.BETTING
    # Step 1: Deal Hole Cards (2 down)
    game._next_step()  # Deal hole cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING
    # Step 2: Pre-Flop Bet
    game._next_step()  # Move to pre-flop bet
    assert game.current_step == 2
    assert game.state == GameState.BETTING

    # Calculate initial pot from blinds
    blinds_pot = 15  # 5 (SB) + 10 (BB)    
    
    # check the current player
    assert game.current_player.id == 'BTN'

    # BTN acts first and calls
    game.player_action('BTN', PlayerAction.CALL, 10)
    game.player_action('SB', PlayerAction.CALL, 10)
    game.player_action('BB', PlayerAction.CHECK)

    # Calculate final pot: blinds + additional calls
    expected_pot = blinds_pot + 10 + 5  # BTN adds 10, SB adds 5    
    
    # Run through flop, bet, turn, bet, river, bet
    game._next_step() # deal flop
    game._next_step() # betting round
    game.player_action('SB', PlayerAction.CHECK)
    game.player_action('BB', PlayerAction.CHECK)
    game.player_action('BTN', PlayerAction.CHECK)
    game._next_step() # deal turn
    game._next_step() # betting round
    game.player_action('SB', PlayerAction.CHECK)
    game.player_action('BB', PlayerAction.CHECK)
    game.player_action('BTN', PlayerAction.CHECK)
    game._next_step() # deal river
    game._next_step() # betting round
    game.player_action('SB', PlayerAction.CHECK)
    game.player_action('BB', PlayerAction.CHECK)
    game.player_action('BTN', PlayerAction.CHECK)

    # Step 9: Showdown
    game._next_step()  # Move to showdown
    assert game.current_step == 9
    assert game.state == GameState.COMPLETE

    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 2  # 2 pots - one for high, one for low
    assert len(results.hands) == 3  # All players have hands in the result
    
    # Get the high and low pots
    high_pot = next((pot for pot in results.pots if pot.hand_type == "High Hand"), None)
    low_pot = next((pot for pot in results.pots if pot.hand_type == "Low Hand"), None)
    
    assert high_pot is not None
    assert low_pot is not None
    
    # Check high pot details
    assert high_pot.amount == expected_pot / 2  # Split pot
    assert high_pot.pot_type == "main"
    assert len(high_pot.winners) == 1
    assert "SB" in high_pot.winners
    
    # Check low pot details
    assert low_pot.amount == expected_pot / 2
    assert low_pot.pot_type == "main"
    assert len(low_pot.winners) == 1
    assert "BB" in low_pot.winners
 
    # Verify winning hands
    winning_high = next(hand for hand in results.winning_hands if hand.hand_type == "High Hand")
    assert winning_high.player_id == "SB", f"Expected SB as high hand winner, got {winning_high.player_id}"
    assert "Four of a Kind" in winning_high.hand_name, f"Expected 'Four of a Kind' in winning high hand, got {winning_high.hand_name}"
    assert "Four Queens" in winning_high.hand_description, f"Expected 'Four Queens' in winning high hand description, got {winning_high.hand_description}"

    winning_low = next(hand for hand in results.winning_hands if hand.hand_type == "Low Hand")
    assert winning_low.player_id == "BB", f"Expected BB as low hand winner, got {winning_low.player_id}"
    assert "One Pair" in winning_low.hand_name, f"Expected 'One Pair' in winning low hand, got {winning_low.hand_name}"
    assert "Pair of Jacks" in winning_low.hand_description, f"Expected 'Pair of Jacks' in winning low hand description, got {winning_low.hand_description}"
