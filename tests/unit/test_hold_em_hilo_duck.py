"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck
from generic_poker.evaluation.hand_description import HandDescriber, EvaluationType

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

def create_predetermined_deck_no_high():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.EIGHT, Suit.HEARTS), #BTN
        Card(Rank.FIVE, Suit.HEARTS), #SB
        Card(Rank.FOUR, Suit.HEARTS), #BB
        Card(Rank.EIGHT, Suit.DIAMONDS), #BTN
        Card(Rank.FIVE, Suit.DIAMONDS), #SB
        Card(Rank.FOUR, Suit.DIAMONDS), #BB
        Card(Rank.KING, Suit.DIAMONDS), #FLOP
        Card(Rank.TEN, Suit.SPADES), #FLOP
        Card(Rank.QUEEN, Suit.CLUBS), #FLOP
        Card(Rank.ACE, Suit.DIAMONDS), #TURN
        Card(Rank.NINE, Suit.CLUBS), #RIVER
        Card(Rank.JACK, Suit.HEARTS), #
        Card(Rank.TEN, Suit.DIAMONDS), #
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.NINE, Suit.SPADES), #
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def create_predetermined_deck_high_qualifier():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.EIGHT, Suit.HEARTS), #BTN
        Card(Rank.FIVE, Suit.HEARTS), #SB
        Card(Rank.KING, Suit.HEARTS), #BB
        Card(Rank.NINE, Suit.HEARTS), #BTN
        Card(Rank.NINE, Suit.DIAMONDS), #SB
        Card(Rank.TWO, Suit.DIAMONDS), #BB
        Card(Rank.KING, Suit.DIAMONDS), #FLOP
        Card(Rank.JACK, Suit.SPADES), #FLOP
        Card(Rank.SIX, Suit.HEARTS), #FLOP
        Card(Rank.SEVEN, Suit.HEARTS), #TURN
        Card(Rank.THREE, Suit.HEARTS), #RIVER
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
    rules = {
        "game": "Hold'em Hi/Lo Duck Flush-Style",
        "players": {
            "min": 2,
            "max": 9
        },
        "deck": {
            "type": "standard",
            "cards": 52
        },
        "bettingStructures": [
            "Limit",
            "No Limit",
            "Pot Limit"
        ],
        "gamePlay": [
            {
                "bet": {
                    "type": "blinds"
                },
                "name": "Post Blinds"
            },
            {
                "deal": {
                    "location": "player",
                    "cards": [
                        {
                            "number": 2,
                            "state": "face down"
                        }
                    ]
                },
                "name": "Deal Hole Cards"
            },
            {
                "bet": {
                    "type": "small"
                },
                "name": "Pre-Flop Bet"
            },
            {
                "deal": {
                    "location": "community",
                    "cards": [
                        {
                            "number": 3,
                            "state": "face up"
                        }
                    ]
                },
                "name": "Deal Flop"
            },
            {
                "bet": {
                    "type": "small"
                },
                "name": "Post-Flop Bet"
            },
            {
                "deal": {
                    "location": "community",
                    "cards": [
                        {
                            "number": 1,
                            "state": "face up"
                        }
                    ]
                },
                "name": "Deal Turn"
            },
            {
                "bet": {
                    "type": "big"
                },
                "name": "Turn Bet"
            },
            {
                "deal": {
                    "location": "community",
                    "cards": [
                        {
                            "number": 1,
                            "state": "face up"
                        }
                    ]
                },
                "name": "Deal River"
            },
            {
                "bet": {
                    "type": "big"
                },
                "name": "River Bet"
            },
            {
                "showdown": {
                    "type": "final"
                },
                "name": "Showdown"
            }
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [
                {
                    "name": "High",
                    "evaluationType": "high",
                    "anyCards": 5,
                    "qualifier": [
                        5,
                        1277
                    ]
                }
            ],
            "defaultAction": {
                "condition": "no_qualifier_met",
                "action": "best_hand",
                "bestHand": [
                    {
                        "name": "2-7 Lowball",
                        "evaluationType": "27_low",
                        "anyCards": 5
                    }
                ]
            }
        }
}
    
    game = Game(
        rules=GameRules.from_json(json.dumps(rules)),
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
    

def test_game_results_no_high_qualifier():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Set our mock deck
    game.table.deck = create_predetermined_deck_no_high()    
    
    # Play a full hand
    game.start_hand()
    game._next_step()  # Deal hole cards
    game._next_step()  # Move to pre-flop bet

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
    game._next_step()  # Move to showdown

    # Check game state
    assert game.state == GameState.COMPLETE
    
    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 1  
    assert len(results.winning_hands) == 1  # one winner - BB
    
    low_pot = next((pot for pot in results.pots if pot.hand_type == "2-7 Lowball"), None)
    assert "BB" in low_pot.winners    
 

def test_game_results_high_qualifier():
    """Test that the game results API provides correct information."""
    game = setup_test_game_with_mock_deck()
    
    # Set our mock deck
    game.table.deck = create_predetermined_deck_high_qualifier()    
    
    # Play a full hand
    game.start_hand()
    game._next_step()  # Deal hole cards
    game._next_step()  # Move to pre-flop bet

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
    game._next_step()  # Move to showdown

    # Check game state
    assert game.state == GameState.COMPLETE
    
    # Get results
    results = game.get_hand_results()

    print("\nShowdown Results:")
    print(results)

    # Check overall results
    assert results.is_complete
    assert results.total_pot == expected_pot
    assert len(results.pots) == 1  # 1 pot split among all players
    assert len(results.winning_hands) == 1  # All players' high and low hands should be winning
    
    low_pot = next((pot for pot in results.pots if pot.hand_type == "Low"), None)
    high_pot = next((pot for pot in results.pots if pot.hand_type == "High"), None)
    assert "BTN" in high_pot.winners
    # no low pot
    assert low_pot is None


