"""Tests for simple straight poker game end-to-end."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck

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
        "game": "Straight Poker",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 5, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"bet": {"type": "small"}, "name": "Initial Bet"},
            {"showdown": {"type": "final"}, "name": "Showdown"}
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}]
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
        "game": "Straight Poker",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 5, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"bet": {"type": "small"}, "name": "Initial Bet"},
            {"showdown": {"type": "final"}, "name": "Showdown"}
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}]
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

@pytest.fixture
def test_hands():
    """Fixed test hands for different scenarios."""
    return {
        'BTN': [  # Royal flush
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.TEN, Suit.HEARTS),
        ],
        'SB': [  # Full house
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.DIAMONDS),
            Card(Rank.QUEEN, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
        ],
        'BB': [  # Two pair
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.TEN, Suit.SPADES),
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.SPADES),
        ]
    }

def setup_test_game(mock_hands=None):
    """Create a test game with three players and optional preset hands."""
    rules = {
        "game": "Straight Poker",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 5, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"bet": {"type": "small"}, "name": "Initial Bet"},
            {"showdown": {"type": "final"}, "name": "Showdown"}
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}]
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
    
    if mock_hands:
        # Replace the deal step to use our test hands
        def mock_deal(self, config):
            for pid, hand in mock_hands.items():
                self.table.players[pid].hand.clear()
                self.table.players[pid].hand.add_cards(hand)
        game._handle_deal = mock_deal.__get__(game)
    
    return game

def test_mock_deck_dealing():
    """Test that the mock deck deals cards as expected."""
    game = setup_test_game_with_mock_deck()
    
    # Start the game (posts blinds)
    game.start_hand()
    
    # Move to dealing step
    game._next_step()
    
    # Check that each player received the expected cards
    btn_cards = game.table.players['BTN'].hand.get_cards()
    sb_cards = game.table.players['SB'].hand.get_cards()
    bb_cards = game.table.players['BB'].hand.get_cards()
    
    # Print the cards for debugging
    logging.debug(f"BTN: {btn_cards}")
    logging.debug(f"SB: {sb_cards}")
    logging.debug(f"BB: {bb_cards}")

    # Check BTN's hand (Royal flush)
    assert any(card.rank == Rank.ACE and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.JACK and card.suit == Suit.HEARTS for card in btn_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.HEARTS for card in btn_cards)
    
    # Check SB's hand (Kings full of Queens)
    assert any(card.rank == Rank.KING and card.suit == Suit.SPADES for card in sb_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.CLUBS for card in sb_cards)
    assert any(card.rank == Rank.KING and card.suit == Suit.DIAMONDS for card in sb_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.SPADES for card in sb_cards)
    assert any(card.rank == Rank.QUEEN and card.suit == Suit.CLUBS for card in sb_cards)
    
    # Check BB's hand (Jacks and Tens)
    assert any(card.rank == Rank.JACK and card.suit == Suit.SPADES for card in bb_cards)
    assert any(card.rank == Rank.JACK and card.suit == Suit.DIAMONDS for card in bb_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.SPADES for card in bb_cards)
    assert any(card.rank == Rank.TEN and card.suit == Suit.DIAMONDS for card in bb_cards)
    assert any(card.rank == Rank.NINE and card.suit == Suit.SPADES for card in bb_cards)

def test_setup_new_game():
    """Test a full game with predetermined hands."""
    game = setup_test_game_with_mock_deck()

    # verify player and initial stack before posting blinds
    assert game.table.players['BTN'].stack == 500
    assert game.table.players['SB'].stack == 500
    assert game.table.players['BB'].stack == 500

def test_start_hand():
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

    # check the pot size
    assert game.betting.get_main_pot_amount() == 15
    
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

def test_next_step_initial_bet():
    """Test basic sequence: Button calls, SB calls, BB checks."""
    game = setup_test_game_with_mock_deck()

    """Press Enter to start hand..."""
    # note that starting the hand also processes the first step (posting blinds)
    # so no call to process_current_step() is necessary.  
    game.start_hand()

    # check the pot size
    assert game.betting.get_main_pot_amount() == 15

    # after posting blinds, move to the next step (dealing)
    game._next_step()

    assert game.current_step == 1           # Should be in deal hole cards step
    assert game.state == GameState.DEALING  # Deal hold cards 

    # after dealing, move to the next step (initial bet)
    game._next_step()

    assert game.current_step == 2           # Should be in initial bet step
    assert game.state == GameState.BETTING  

    # validate current player is the BTN
    assert game.current_player.id == 'BTN'

    # Get valid actions
    valid_actions = game.get_valid_actions(game.current_player.id)
    
    # Check that there are 3 valid actions
    assert len(valid_actions) == 3
    
    # Check each action individually - player can always fold
    assert any(action[0] == PlayerAction.FOLD and action[1] is None and action[2] is None for action in valid_actions)

    # The BTN can call the blind for $10
    assert any(action[0] == PlayerAction.CALL and action[1] == 10 and action[2] == 10 for action in valid_actions)

    # Find the raise action
    raise_action = next((action for action in valid_actions if action[0] == PlayerAction.RAISE), None)
    # This is a limit game, so the raise must be exactly $20 (calling $10, then raising $10 to make it $20)
    assert raise_action is not None
    assert raise_action[1] == 20  # Min raise amount
    assert raise_action[2] == 20  # Max raise amount

    # Test calling the blind
    result = game.player_action(game.current_player.id, PlayerAction.CALL, 10)
    # check result - success, and no state change since there are more players
    assert result.success == True
    assert result.state_changed == False 

    # check the player's stack - should be $490
    assert game.table.players['BTN'].stack == 490

    # check the pot size
    assert game.betting.get_main_pot_amount() == 15 + 10    

    # player_action already moved us to the next player, so we can check the current player
    assert game.current_player.id == 'SB'

    # Get valid actions
    valid_actions = game.get_valid_actions(game.current_player.id)

    # Check that there are 3 valid actions - SB can fold, call, or raise
    assert len(valid_actions) == 3

    # Check each action individually - player can always fold
    assert any(action[0] == PlayerAction.FOLD and action[1] is None and action[2] is None for action in valid_actions)

    # The SB can call for $5 more to make it $10.
    # Note that the SB already has $5 in the pot from the blind
    assert any(action[0] == PlayerAction.CALL and action[1] == 10 and action[2] == 10 for action in valid_actions)

    # Find the raise action
    raise_action = next((action for action in valid_actions if action[0] == PlayerAction.RAISE), None)
    # This is a limit game, so the raise must be exactly $10 (calling $5, then raising $5 to make it $10)
    assert raise_action is not None
    assert raise_action[1] == 20  # Min raise amount
    assert raise_action[2] == 20  # Max raise amount (player's stack)

    # Test calling the blind
    result = game.player_action(game.current_player.id, PlayerAction.CALL, 5)
    # check result - success, and no state change since there are more players
    assert result.success == True
    assert result.state_changed == False

    # check the player's stack - should be $490
    assert game.table.players['SB'].stack == 490

    # check the pot size
    assert game.betting.get_main_pot_amount() == 15 + 10 + 5       

def test_next_step_initial_bet_nl():
    """Test basic sequence: Button calls, SB calls, BB checks."""
    game = setup_test_game_with_mock_deck()

    """Press Enter to start hand..."""
    # note that starting the hand also processes the first step (posting blinds)
    # so no call to process_current_step() is necessary.  
    game.start_hand()

    # check the pot size
    assert game.betting.get_main_pot_amount() == 15

    # after posting blinds, move to the next step (dealing)
    game._next_step()

    assert game.current_step == 1           # Should be in deal hole cards step
    assert game.state == GameState.DEALING  # Deal hold cards 

    # after dealing, move to the next step (initial bet)
    game._next_step()

    assert game.current_step == 2           # Should be in initial bet step
    assert game.state == GameState.BETTING  

    # validate current player is the BTN
    assert game.current_player.id == 'BTN'

    # Get valid actions
    valid_actions = game.get_valid_actions(game.current_player.id)
    
    # Check that there are 3 valid actions
    assert len(valid_actions) == 3
    
    # Check each action individually - player can always fold
    assert any(action[0] == PlayerAction.FOLD and action[1] is None and action[2] is None for action in valid_actions)

    # The BTN can call the blind for $10
    assert any(action[0] == PlayerAction.CALL and action[1] == 10 and action[2] == 10 for action in valid_actions)

    # Find the raise action
    raise_action = next((action for action in valid_actions if action[0] == PlayerAction.RAISE), None)
    # This is a limit game, so the raise must be exactly $20 (calling $10, then raising $10 to make it $20)
    assert raise_action is not None
    assert raise_action[1] == 20  # Min raise amount
    assert raise_action[2] == 20  # Max raise amount

    # Test calling the blind
    result = game.player_action(game.current_player.id, PlayerAction.CALL, 10)
    # check result - success, and no state change since there are more players
    assert result.success == True
    assert result.state_changed == False 

    # check the player's stack - should be $490
    assert game.table.players['BTN'].stack == 490

    # check the pot size
    assert game.betting.get_main_pot_amount() == 15 + 10    

    # player_action already moved us to the next player, so we can check the current player
    assert game.current_player.id == 'SB'

    # Get valid actions
    valid_actions = game.get_valid_actions(game.current_player.id)

    # Check that there are 3 valid actions - SB can fold, call, or raise
    assert len(valid_actions) == 3

    # Check each action individually - player can always fold
    assert any(action[0] == PlayerAction.FOLD and action[1] is None and action[2] is None for action in valid_actions)

    # The SB can call for $5 more to make it $10.
    # Note that the SB already has $5 in the pot from the blind
    assert any(action[0] == PlayerAction.CALL and action[1] == 10 and action[2] == 10 for action in valid_actions)

    # Find the raise action
    raise_action = next((action for action in valid_actions if action[0] == PlayerAction.RAISE), None)
    # This is a limit game, so the raise must be exactly $10 (calling $5, then raising $5 to make it $10)
    assert raise_action is not None
    assert raise_action[1] == 20  # Min raise amount
    assert raise_action[2] == 20  # Max raise amount (player's stack)

    # Test calling the blind
    result = game.player_action(game.current_player.id, PlayerAction.CALL, 5)
    # check result - success, and no state change since there are more players
    assert result.success == True
    assert result.state_changed == False

    # check the player's stack - should be $490
    assert game.table.players['SB'].stack == 490

    # check the pot size
    assert game.betting.get_main_pot_amount() == 15 + 10 + 5        
    
def test_format_actions_for_display():
    """Test the formatting of actions for display."""
    game = setup_test_game_with_mock_deck()
    
    # Start the game and move to betting
    game.start_hand()
    game._next_step()  # Deal cards
    game._next_step()  # Move to initial bet
    
    # Test BTN's formatted actions
    formatted_actions = game.action_handler.format_actions_for_display('BTN')
    assert len(formatted_actions) == 3
    assert "Fold" in formatted_actions
    assert "Call $10 (+$10)" in formatted_actions
    assert "Raise to $20 (+$20)" in formatted_actions
    
    # BTN calls
    game.player_action('BTN', PlayerAction.CALL, 10)
    
    valid_actions = game.get_valid_actions('SB')
    call_action = next((a for a in valid_actions if a[0] == PlayerAction.CALL), None)
    print(f"Call action details: {call_action}")    
    
    # Test SB's formatted actions (SB has already put in $5 for the blind)
    formatted_actions = game.action_handler.format_actions_for_display('SB')
    assert len(formatted_actions) == 3
    assert "Fold" in formatted_actions
    assert "Call $10 (+$5)" in formatted_actions
    assert "Raise to $20 (+$15)" in formatted_actions
    
    # SB calls
    game.player_action('SB', PlayerAction.CALL, 10)
    
    # Test BB's formatted actions (BB has already put in $10 for the blind)
    formatted_actions = game.action_handler.format_actions_for_display('BB')
    assert len(formatted_actions) == 3
    assert "Fold" in formatted_actions
    assert "Check" in formatted_actions
    assert "Raise to $20 (+$10)" in formatted_actions

def test_format_actions_for_display_after_raise():
    """Test the formatting of actions after a raise has occurred."""
    game = setup_test_game_with_mock_deck()
    
    # Start the game and move to betting
    game.start_hand()
    game._next_step()  # Deal cards
    game._next_step()  # Move to initial bet
    
    # BTN raises to $20
    game.player_action('BTN', PlayerAction.RAISE, 20)

    # Test SB's formatted actions after a raise
    formatted_actions = game.action_handler.format_actions_for_display('SB')
    assert len(formatted_actions) == 3
    assert "Fold" in formatted_actions
    assert "Call $20 (+$15)" in formatted_actions
    assert "Raise to $30 (+$25)" in formatted_actions  # In limit, the next raise is +10
    
    # SB calls
    game.player_action('SB', PlayerAction.CALL, 20)
    
    # Test BB's formatted actions
    formatted_actions = game.action_handler.format_actions_for_display('BB')
    assert len(formatted_actions) == 3
    assert "Fold" in formatted_actions
    assert "Call $20 (+$10)" in formatted_actions
    assert "Raise to $30 (+$20)" in formatted_actions

def test_game_description():
    """Test the game description formatting."""
    # Test Limit game
    game = setup_test_game_with_mock_deck()  # This is a Limit game
    print("Game is ", game)

    description = game.get_game_description()
    assert description == "$10/$20 Limit Straight Poker"
    
    # Test String representation
    assert str(game) == "$10/$20 Limit Straight Poker"
    
    # Test table info
    info = game.get_table_info()
    assert info["game_description"] == "$10/$20 Limit Straight Poker"
    assert info["player_count"] == 3
    assert info["min_buyin"] == 100
    assert info["max_buyin"] == 1000
    assert info["active_players"] == 3  # All players should be active initially
    
    # Test No Limit game
    rules_json = json.dumps({
        "game": "Texas Hold'em",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {"location": "player", "cards": [{"number": 2, "state": "face down"}]}, "name": "Deal Cards"},
            {"bet": {"type": "small"}, "name": "Betting"},
            {"showdown": {"type": "final"}, "name": "Showdown"}
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}]
        }
    })
    
    nl_game = Game(
        rules=GameRules.from_json(rules_json),
        structure=BettingStructure.NO_LIMIT,
        small_blind=1,  # Small blind
        big_blind=2,    # Big blind
        min_buyin=40,
        max_buyin=200,
        auto_progress=False
    )
    
    nl_description = nl_game.get_game_description()
    assert nl_description == "$1/$2 No Limit Texas Hold'em"
    
    # Test Pot Limit game with non-standard blinds
    pl_game = Game(
        rules=GameRules.from_json(rules_json),
        structure=BettingStructure.POT_LIMIT,
        small_blind=2,   # Small blind
        big_blind=5,     # Big blind (non-standard)
        min_buyin=100,
        max_buyin=500,
        auto_progress=False
    )
    
    pl_description = pl_game.get_game_description()
    assert "Pot Limit Texas Hold'em" in pl_description
