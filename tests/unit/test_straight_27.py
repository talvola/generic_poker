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
        Card(Rank.QUEEN, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.DIAMONDS), #SB
        Card(Rank.TEN, Suit.SPADES), #BB
        Card(Rank.JACK, Suit.HEARTS), #BTN
        Card(Rank.QUEEN, Suit.SPADES), #SB
        Card(Rank.TEN, Suit.DIAMONDS), #BB
        Card(Rank.TEN, Suit.HEARTS), #BTN
        Card(Rank.QUEEN, Suit.CLUBS), #SB
        Card(Rank.NINE, Suit.SPADES), #BB
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    rules = {
        "game": "Straight Poker 2-7",
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
                            "number": 5,
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
                "name": "Initial Bet"
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
                    "evaluationType": "27_low",
                    "anyCards": 5
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

def setup_test_game_with_mock_deck_nl():
    """Create a test game with three players and a predetermined deck.   No-limit."""
    rules = {
        "game": "Straight Poker 2-7",
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
                            "number": 5,
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
                "name": "Initial Bet"
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
                    "evaluationType": "27_low",
                    "anyCards": 5
                }
            ]
        }
    }
    
    game = Game(
        rules=GameRules.from_json(json.dumps(rules)),
        structure=BettingStructure.NO_LIMIT,
        small_blind=5,
        big_blind=10,
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
    
def test_next_step_deal():
    """Test basic sequence: Button calls, SB calls, BB checks."""
    game = setup_test_game_with_mock_deck()

    # verify player and initial stack before posting blinds
    assert game.table.players['BTN'].stack == 500
    assert game.table.players['SB'].stack == 500
    assert game.table.players['BB'].stack == 500    

    """Press Enter to start hand..."""
    # note that starting the hand also processes the first step (posting blinds)
    # so no call to process_current_step() is necessary.  
    game.start_hand()
    
    # Verify initial state
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets 

    # verify player and initial stack after posting blinds
    assert game.table.players['BTN'].stack == 500
    assert game.table.players['SB'].stack == 495
    assert game.table.players['BB'].stack == 490
    # test active status for each player 
    assert game.table.players['BTN'].is_active == True
    assert game.table.players['SB'].is_active == True
    assert game.table.players['BB'].is_active == True
    # make sure players have no cards before deal
    assert game.table.players['BTN'].hand.size == 0
    assert game.table.players['SB'].hand.size == 0
    assert game.table.players['BB'].hand.size == 0 

    # after posting blinds, move to the next step
    game._next_step()

    assert game.current_step == 1           # Should be in deal hole cards step
    assert game.state == GameState.DEALING  # Deal hold cards 

    # validate player's stacks are the same

    # verify player and initial stack after posting blinds
    assert game.table.players['BTN'].stack == 500
    assert game.table.players['SB'].stack == 495
    assert game.table.players['BB'].stack == 490
    # test active status for each player 
    assert game.table.players['BTN'].is_active == True
    assert game.table.players['SB'].is_active == True
    assert game.table.players['BB'].is_active == True

    # make sure players have each been dealt 5 cards
    assert game.table.players['BTN'].hand.size == 5
    assert game.table.players['SB'].hand.size == 5
    assert game.table.players['BB'].hand.size == 5   

    # verify player's cards

    # Check BTN's hand (Royal flush)
    btn_cards = game.table.players['BTN'].hand.get_cards()
    assert any(card.rank == Rank.ACE and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.JACK and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.HEARTS for card in btn_cards)
    # Check SB's hand (Kings full of Queens)
    sb_cards = game.table.players['SB'].hand.get_cards()
    assert any(card.rank == Rank.KING and card.suit == Suit.SPADES for card in sb_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.CLUBS for card in sb_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in sb_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.SPADES for card in sb_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.CLUBS for card in sb_cards)
    # Check BB's hand (Jacks and Tens)
    bb_cards = game.table.players['BB'].hand.get_cards()
    assert any(card.rank == Rank.JACK and card.suit == Suit.SPADES for card in bb_cards)
    assert any(card.rank == Rank.JACK and card.suit == Suit.DIAMONDS for card in bb_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.SPADES for card in bb_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.DIAMONDS for card in bb_cards)
    assert any(card.rank == Rank.NINE and card.suit == Suit.SPADES for card in bb_cards)

def test_next_step_showdown():
    """Test basic sequence: Button calls, SB calls, BB checks."""
    game = setup_test_game_with_mock_deck()

    # verify player and initial stack before posting blinds
    assert game.table.players['BTN'].stack == 500
    assert game.table.players['SB'].stack == 500
    assert game.table.players['BB'].stack == 500    

    """Press Enter to start hand..."""
    # note that starting the hand also processes the first step (posting blinds)
    # so no call to process_current_step() is necessary.  
    game.start_hand()

    # after posting blinds, move to the next step
    game._next_step()

    assert game.current_step == 1           # Should be in deal hole cards step
    assert game.state == GameState.DEALING  # Deal hold cards

    # make sure players have each been dealt 5 cards
    assert game.table.players['BTN'].hand.size == 5
    assert game.table.players['SB'].hand.size == 5
    assert game.table.players['BB'].hand.size == 5   

    # after dealing hole cards, move to the next step
    game._next_step()

    assert game.current_step == 2           # Should be in initial bet step
    assert game.state == GameState.BETTING  # Deal hold cards     

    # All players call or check
    game.player_action('BTN', PlayerAction.CALL, 10)    
    game.player_action('SB', PlayerAction.CALL, 10)    
    game.player_action('BB', PlayerAction.CHECK, 10)

    assert game.table.players['BTN'].stack == 490
    assert game.table.players['SB'].stack == 490
    assert game.table.players['BB'].stack == 490

    # after betting, move to showdown
    game._next_step()                   

    assert game.current_step == 3   
    assert game.state == GameState.COMPLETE

    print("\nShowdown Results:")
    # Create a hand describer for high card evaluation (standard poker)
    describer = HandDescriber(EvaluationType.HIGH)

    for player in game.table.get_position_order():
        if player.is_active:
            cards = player.hand.get_cards()
            card_str = ' '.join(str(c) for c in cards)
            print(f"{player.name}: {card_str}")

            # Get hand description
            try:
                hand_desc = describer.describe_hand(cards)
                hand_desc_detailed = describer.describe_hand_detailed(cards)
                if hand_desc == hand_desc_detailed:
                    print(f"  Hand: {hand_desc}")
                else:
                    print(f"  Hand: {hand_desc_detailed}")
            except Exception as e:
                print(f"  Hand: [Unable to describe: {e}]")

    assert game.table.players['BTN'].stack == 490
    assert game.table.players['SB'].stack == 490
    assert game.table.players['BB'].stack == 520

    