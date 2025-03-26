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

def create_predetermined_deck():
    """Create a deck with predetermined cards for testing."""
    # Create cards in the desired deal order (first card will be dealt first)
    # In this three-handed case, button is dealt first, then SB, then BB in order
    cards = [
        Card(Rank.ACE, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.SPADES), #SB
        Card(Rank.JACK, Suit.SPADES), #BB
        Card(Rank.KING, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.CLUBS), #SB
        Card(Rank.JACK, Suit.DIAMONDS), #BB
        Card(Rank.QUEEN, Suit.HEARTS), #FLOP
        Card(Rank.KING, Suit.DIAMONDS), #FLOP
        Card(Rank.TEN, Suit.SPADES), #FLOP
        Card(Rank.JACK, Suit.HEARTS), #TURN
        Card(Rank.QUEEN, Suit.SPADES), #RIVER
        Card(Rank.TEN, Suit.DIAMONDS), #
        Card(Rank.TEN, Suit.HEARTS), #
        Card(Rank.QUEEN, Suit.CLUBS), #
        Card(Rank.NINE, Suit.SPADES), #
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    rules = {
        "game": "Greek Hold 'em",
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
            "cardsRequired": "two hole cards, three community cards",
            "bestHand": [
                {
                    "evaluationType": "high",
                    "holeCards": 2,
                    "communityCards": 3
                }
            ]
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
    assert len(results.pots) == 1  # Just main pot
    assert len(results.hands) == 3  # All players stayed in
    
    # Check pot details
    main_pot = results.pots[0]
    assert main_pot.amount == expected_pot
    assert main_pot.pot_type == "main"
    assert not main_pot.split  # Only one winner
    
    # For Greek Hold'em - the SB should win with a Full House
    assert len(main_pot.winners) == 1
    assert 'SB' in main_pot.winners
    
    # Check hand descriptions
    winning_hand = results.hands['SB']
    assert "Full House" in winning_hand[0].hand_name
    assert "Full House, Kings over Queens" in winning_hand[0].hand_description
    
    # Check winning hands list
    assert len(results.winning_hands) == 1
    assert results.winning_hands[0].player_id == 'SB'

