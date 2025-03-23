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
        Card(Rank.QUEEN, Suit.DIAMONDS), #SB
        Card(Rank.JACK, Suit.SPADES), #BB
        Card(Rank.KING, Suit.HEARTS), #BTN
        Card(Rank.KING, Suit.CLUBS), #SB
        Card(Rank.JACK, Suit.DIAMONDS), #BB
        Card(Rank.QUEEN, Suit.HEARTS), #FLOP
        Card(Rank.KING, Suit.DIAMONDS), #FLOP
        Card(Rank.TEN, Suit.SPADES), #FLOP
        Card(Rank.QUEEN, Suit.CLUBS), #FLOP2
        Card(Rank.QUEEN, Suit.SPADES), #FLOP2
        Card(Rank.JACK, Suit.HEARTS), #FLOP2
        Card(Rank.TEN, Suit.DIAMONDS), #TURN1
        Card(Rank.TEN, Suit.HEARTS), #TURN2
        Card(Rank.NINE, Suit.SPADES), #RIVER1
        Card(Rank.TWO, Suit.SPADES), #RIVER2
     
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
        Card(Rank.TWO, Suit.CLUBS), #FLOP2
        Card(Rank.THREE, Suit.SPADES), #FLOP2
        Card(Rank.FIVE, Suit.HEARTS), #FLOP2
        Card(Rank.TEN, Suit.DIAMONDS), #TURN1
        Card(Rank.TEN, Suit.HEARTS), #TURN2
        Card(Rank.NINE, Suit.SPADES), #RIVER1
        Card(Rank.TWO, Suit.SPADES), #RIVER2
      
        # Rest of the deck in some order (won't be used in 5-card poker)
        # You can add more cards here if needed for other tests
    ]
    
    return MockDeck(cards)

def setup_test_game_with_mock_deck():
    """Create a test game with three players and a predetermined deck."""
    rules = {
        "game": "Double-Board Hold'em",
        "players": {
            "min": 2,
            "max": 6
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
                            "state": "face up",
                            "subset": "Board 1"
                        },
                        {
                            "number": 3,
                            "state": "face up",
                            "subset": "Board 2"
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
                            "state": "face up",
                            "subset": "Board 1"
                        },
                        {
                            "number": 1,
                            "state": "face up",
                            "subset": "Board 2"
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
                            "state": "face up",
                            "subset": "Board 1"
                        },
                        {
                            "number": 1,
                            "state": "face up",
                            "subset": "Board 2"
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
                    "name": "Board 1",
                    "evaluationType": "high",
                    "anyCards": 5,
                    "subset": "Board 1"
                },
                {
                    "name": "Board 2",
                    "evaluationType": "high",
                    "anyCards": 5,
                    "subset": "Board 2"
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
    assert str(game.table.community_cards["Board 1"][0]) == "Qh"  # Flop 1
    assert str(game.table.community_cards["Board 1"][1]) == "Kd"  # Flop 2
    assert str(game.table.community_cards["Board 1"][2]) == "Ts"  # Flop 3

    assert str(game.table.community_cards["Board 2"][0]) == "Qc"  # Flop 1
    assert str(game.table.community_cards["Board 2"][1]) == "Qs"  # Flop 2
    assert str(game.table.community_cards["Board 2"][2]) == "Jh"  # Flop 3

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
    assert str(game.table.community_cards["Board 1"][3]) == "Td"  # Turn
    assert str(game.table.community_cards["Board 2"][3]) == "Th"  # Turn

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
    assert str(game.table.community_cards["Board 1"][4]) == "9s"  # River
    assert str(game.table.community_cards["Board 2"][4]) == "2s"  # River
   
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
    assert len(results.pots) == 2  # two boards - two pots
    assert len(results.hands) == 3  # All players have hands in the result
    
    # Get the pots
    board_1_pot = next((pot for pot in results.pots if pot.hand_type == "Board 1"), None)
    board_2_pot = next((pot for pot in results.pots if pot.hand_type == "Board 2"), None)
    
    assert board_1_pot is not None
    assert board_2_pot is not None
    
    # Check board 1 pot details
    assert board_1_pot.amount == expected_pot // 2  # Half pot goes to high
    assert board_1_pot.pot_type == "main"
    assert len(board_1_pot.winners) == 1
    assert "BB" in board_1_pot.winners

    # Check board 2 pot details
    assert board_2_pot.amount == expected_pot // 2  # Half pot goes to high
    assert board_2_pot.pot_type == "main"
    assert len(board_2_pot.winners) == 1
    assert "BB" in board_2_pot.winners    

     # Verify winning hands
    winning_b1 = next(hand for hand in results.winning_hands if hand.hand_type == "Board 1")
    assert winning_b1.player_id == "BB", f"Expected BB as board 1 hand winner, got {winning_b1.player_id}"
    assert "Straight" in winning_b1.hand_name, f"Expected 'Straight' in winning high hand, got {winning_b1.hand_name}"
    assert "King-high" in winning_b1.hand_description, f"Expected 'King-high' in winning high hand description, got {winning_b1.hand_description}"

    winning_b2 = next(hand for hand in results.winning_hands if hand.hand_type == "Board 2")
    assert winning_b2.player_id == "BB", f"Expected BB as board 2 hand winner, got {winning_b2.player_id}"
    assert "Full House" in winning_b2.hand_name, f"Expected 'Full House' in winning high hand, got {winning_b2.hand_name}"
    assert "Jacks over Queens" in winning_b2.hand_description, f"Expected 'Jacks over Queens' in winning high hand description, got {winning_b2.hand_description}"

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
    assert len(results.pots) == 2  # two boards - two pots
    assert len(results.hands) == 3  # All players have hands in the result
    
    # Get the pots
    board_1_pot = next((pot for pot in results.pots if pot.hand_type == "Board 1"), None)
    board_2_pot = next((pot for pot in results.pots if pot.hand_type == "Board 2"), None)
    
    assert board_1_pot is not None
    assert board_2_pot is not None
    
    # Check board 1 pot details
    assert board_1_pot.amount == expected_pot // 2  # Half pot goes to high
    assert board_1_pot.pot_type == "main"
    assert len(board_1_pot.winners) == 1
    assert "SB" in board_1_pot.winners

    # Check board 2 pot details
    assert board_2_pot.amount == expected_pot // 2  # Half pot goes to high
    assert board_2_pot.pot_type == "main"
    assert len(board_2_pot.winners) == 1
    assert "BTN" in board_2_pot.winners    

     # Verify winning hands
    winning_b1 = next(hand for hand in results.winning_hands if hand.hand_type == "Board 1")
    assert winning_b1.player_id == "SB", f"Expected SB as board 1 hand winner, got {winning_b1.player_id}"
    assert "Two Pair" in winning_b1.hand_name, f"Expected 'Two Pair' in winning high hand, got {winning_b1.hand_name}"
    assert "Kings and Queens" in winning_b1.hand_description, f"Expected 'Kings and Queens' in winning high hand description, got {winning_b1.hand_description}"

    winning_b2 = next(hand for hand in results.winning_hands if hand.hand_type == "Board 2")
    assert winning_b2.player_id == "BTN", f"Expected BTN as board 2 hand winner, got {winning_b2.player_id}"
    assert "One Pair" in winning_b2.hand_name, f"Expected 'One Pair' in winning high hand, got {winning_b2.hand_name}"
    assert "Pair of Twos" in winning_b2.hand_description, f"Expected 'Pair of Twos' in winning high hand description, got {winning_b2.hand_description}"