"""Tests for poker betting flow."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.game.betting import BettingStructure

import json 

import logging
import sys

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

def create_test_game(mock_hands=None):
    """Create a test game with three players and optional preset hands."""
    rules = {
        "game": "Straight Poker with Grouped Expose",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 5, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"groupedActions": [
                {
                    "bet": {
                        "type": "small"
                    }
                },
                {
                    "expose": {
                        "cards": [
                            {
                                "number": 1,
                                "state": "face down",
                                "oncePerStep": "true",
                                "immediate": "true"
                            }
                        ]
                    }
                }
            ],
            "name": "Bet and Expose Card"
            },            
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

def test_basic_call_sequence_grouped_limit():
    """Test basic sequence: Button calls, SB calls, BB checks."""
    game = create_test_game()
    game.start_hand()

    # check table positions

    assert game.table.button_pos == 0

    active_players = game.table.get_active_players()
    assert active_players[0] == game.table.players["BTN"]
    assert active_players[1] == game.table.players["SB"]
    assert active_players[2] == game.table.players["BB"]
    
    # Verify initial state
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets 

    assert game.betting.current_bet == 10  # Big blind amount
    assert game.betting.get_main_pot_amount() == 15  # SB(5) + BB(10)
    game._next_step()  # Manually move to dealing hole cards



    assert game.current_step == 1           # Should be in dealing step
    assert game.state == GameState.DEALING  # ?
    game._next_step()  # just continue to betting/expose step




    # Step 2 is the grouped bet/expose step

    # BTN is first player

    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action
    assert game.state == GameState.BETTING  # Now player betting occurs    

    # Verify first action is to Button (Alice)
    assert game.current_player.id == "BTN"
    valid_actions = game.get_valid_actions('BTN')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # BTN can fold
    assert (PlayerAction.CALL, 10, 10) in valid_actions         # BTN can call BB of 10
    assert (PlayerAction.RAISE, 20, 20) in valid_actions        # BTN can raise to 20
    # Button calls
    result = game.player_action("BTN", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step  # Round shouldn't be over
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('BTN')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['BTN'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('BTN', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success

    # SB is second player
    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action

    assert game.current_player.id == "SB"  # Should move to SB
    valid_actions = game.get_valid_actions('SB')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # SB can fold
    assert (PlayerAction.CALL, 10, 10) in valid_actions         # SB can call BB of 10
    assert (PlayerAction.RAISE, 20, 20) in valid_actions        # SB can raise to 20

    # Small blind calls
    result = game.player_action("SB", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('SB')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['SB'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('SB', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success


    # BB is third player - still in grouped action
    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action

    assert game.current_player.id == "BB"  # Should move to BB
    valid_actions = game.get_valid_actions('BB')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # BB can fold
    assert (PlayerAction.CHECK, None, None) in valid_actions                # BB can check
    assert (PlayerAction.RAISE, 20, 20) in valid_actions        # SB can raise to 20

    # Big blind checks
    result = game.player_action("BB", PlayerAction.CHECK, 0)
    assert result.success
    assert not result.advance_step
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('BB')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['BB'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('BB', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success
    assert result.advance_step  # Round should end
    
    # Verify final state
    assert game.betting.get_main_pot_amount() == 30  # All players put in 10

    game._next_step()  # continue to showdown
    assert game.current_step == 3    

def create_test_game_nolimit(mock_hands=None):
    """Create a test game with three players and optional preset hands."""
    rules = {
        "game": "Straight Poker with Grouped Expose",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 5, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"groupedActions": [
                {
                    "bet": {
                        "type": "small"
                    }
                },
                {
                    "expose": {
                        "cards": [
                            {
                                "number": 1,
                                "state": "face down",
                                "oncePerStep": "true",
                                "immediate": "true"
                            }
                        ]
                    }
                }
            ],
            "name": "Bet and Expose Card"
            },            
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
    
    if mock_hands:
        # Replace the deal step to use our test hands
        def mock_deal(self, config):
            for pid, hand in mock_hands.items():
                self.table.players[pid].hand.clear()
                self.table.players[pid].hand.add_cards(hand)
        game._handle_deal = mock_deal.__get__(game)
    
    return game

def test_basic_call_sequence_grouped_nolimit():
    """Test basic sequence: Button calls, SB calls, BB checks."""
    game = create_test_game_nolimit()
    game.start_hand()

    # check table positions

    assert game.table.button_pos == 0

    active_players = game.table.get_active_players()
    assert active_players[0] == game.table.players["BTN"]
    assert active_players[1] == game.table.players["SB"]
    assert active_players[2] == game.table.players["BB"]

    # verify table 
    assert game.table.players['BTN'].stack == 500

    # Verify initial state
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets 


    assert game.betting.current_bet == 10  # Big blind amount
    assert game.betting.get_main_pot_amount() == 15  # SB(5) + BB(10)
    game._next_step()  # Manually move to dealing hole cards



    assert game.current_step == 1           # Should be in dealing step
    assert game.state == GameState.DEALING  # ?
    game._next_step()  # just continue to betting/expose step




    # Step 2 is the grouped bet/expose step

    # BTN is first player

    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action
    assert game.state == GameState.BETTING  # Now player betting occurs    

    # Verify first action is to Button (Alice)
    assert game.current_player.id == "BTN"
    valid_actions = game.get_valid_actions('BTN')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # BTN can fold
    assert (PlayerAction.CALL, 10, 10) in valid_actions         # BTN can call BB of 10
    assert (PlayerAction.RAISE, 20, 500) in valid_actions        # BTN can raise stack of 500

    # Button calls
    result = game.player_action("BTN", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step  # Round shouldn't be over
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('BTN')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['BTN'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('BTN', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success

    # SB is second player
    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action

    assert game.current_player.id == "SB"  # Should move to SB
    valid_actions = game.get_valid_actions('SB')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # SB can fold
    assert (PlayerAction.CALL, 10, 10) in valid_actions         # SB can call BB of 10
    assert (PlayerAction.RAISE, 20, 500) in valid_actions        # SB can raise to stack of 500

    # Small blind calls
    result = game.player_action("SB", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('SB')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['SB'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('SB', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success


    # BB is third player - still in grouped action
    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action

    assert game.current_player.id == "BB"  # Should move to BB
    valid_actions = game.get_valid_actions('BB')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # BB can fold
    assert (PlayerAction.CHECK, None, None) in valid_actions                # BB can check
    assert (PlayerAction.RAISE, 20, 500) in valid_actions        # SB can raise to stack of 500

    # Big blind checks
    result = game.player_action("BB", PlayerAction.CHECK, 0)
    assert result.success
    assert not result.advance_step
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('BB')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['BB'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('BB', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success
    assert result.advance_step  # Round should end
    
    # Verify final state
    assert game.betting.get_main_pot_amount() == 30  # All players put in 10

    game._next_step()  # continue to showdown
    assert game.current_step == 3    

# testing on whether insertion order or alphabetic order is used

def create_test_game_nolimit_p1_p2_p3(mock_hands=None):
    """Create a test game with three players and optional preset hands."""
    rules = {
        "game": "Straight Poker with Grouped Expose",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 5, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"groupedActions": [
                {
                    "bet": {
                        "type": "small"
                    }
                },
                {
                    "expose": {
                        "cards": [
                            {
                                "number": 1,
                                "state": "face down",
                                "oncePerStep": "true",
                                "immediate": "true"
                            }
                        ]
                    }
                }
            ],
            "name": "Bet and Expose Card"
            },            
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
    
    if mock_hands:
        # Replace the deal step to use our test hands
        def mock_deal(self, config):
            for pid, hand in mock_hands.items():
                self.table.players[pid].hand.clear()
                self.table.players[pid].hand.add_cards(hand)
        game._handle_deal = mock_deal.__get__(game)
    
    return game

def test_basic_call_sequence_grouped_nolimit_p1_p2_p3():
    """Test basic sequence: Button calls, SB calls, BB checks."""
    game = create_test_game_nolimit_p1_p2_p3()
    game.start_hand()

    # check table positions

    assert game.table.button_pos == 0

    active_players = game.table.get_active_players()
    assert active_players[0] == game.table.players["p1"]
    assert active_players[1] == game.table.players["p2"]
    assert active_players[2] == game.table.players["p3"]

    # verify table 
    assert game.table.players['p1'].stack == 500

    # Verify initial state
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets 


    assert game.betting.current_bet == 2  # Big blind amount
    assert game.betting.get_main_pot_amount() == 3  # SB(5) + BB(10)
    game._next_step()  # Manually move to dealing hole cards



    assert game.current_step == 1           # Should be in dealing step
    assert game.state == GameState.DEALING  # ?
    game._next_step()  # just continue to betting/expose step

    # Step 2 is the grouped bet/expose step

    # p1 is first player

    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action
    assert game.state == GameState.BETTING  # Now player betting occurs    

    # Verify first action is to Button (Alice)
    assert game.current_player.id == "p1"
    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # BTN can fold
    assert (PlayerAction.CALL, 2, 2) in valid_actions         # BTN can call BB of 2
    assert (PlayerAction.RAISE, 4, 500) in valid_actions        # BTN can raise stack of 500

    # Button calls
    result = game.player_action("p1", PlayerAction.CALL, 2)
    assert result.success
    assert not result.advance_step  # Round shouldn't be over
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('p1')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['p1'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('p1', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success
    assert game.table.players['p1'].hand.cards[0].visibility == Visibility.FACE_UP

    # p2 is second player
    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action
    assert game.current_player.id == "p2"  # Should move to SB

    # check stacks
    assert game.table.players['p1'].stack == 498  # from call of BB
    assert game.table.players['p2'].stack == 499  # SB deducted
    assert game.table.players['p3'].stack == 498  # BB deducted

    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # SB can fold
    assert (PlayerAction.CALL, 2, 2) in valid_actions         # SB can call BB of 2
    assert (PlayerAction.RAISE, 4, 500) in valid_actions        # SB can raise to stack of 500

    # Small blind calls
    result = game.player_action("p2", PlayerAction.CALL, 2)
    assert result.success
    assert not result.advance_step
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('p2')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['p2'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('p2', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success    
    assert game.table.players['p2'].hand.cards[0].visibility == Visibility.FACE_UP

    # p3 is third player - still in grouped action
    assert game.current_step == 2           # Should be in Grouped step
    assert game.action_handler.current_substep == 0  # first part of grouped action
    assert game.current_player.id == "p3"  # Should move to SB

    assert game.current_player.id == "p3"  # Should move to BB
    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.FOLD, None, None) in valid_actions     # BB can fold
    assert (PlayerAction.CHECK, None, None) in valid_actions    # BB can check
    assert (PlayerAction.RAISE, 4, 500) in valid_actions        # BB can raise to stack of 500

    # Big blind checks
    result = game.player_action("p3", PlayerAction.CHECK, 0)
    assert result.success
    assert not result.advance_step
    assert game.action_handler.current_substep == 1  # Moved to expose step

    valid_actions = game.get_valid_actions('p3')
    assert (PlayerAction.EXPOSE, 1, 1) in valid_actions

    exposed_card = game.table.players['p3'].hand.cards[0]  # Choose the first hole card (Ah)
    result = game.player_action('p3', PlayerAction.EXPOSE, cards=[exposed_card])
    assert result.success
    assert game.table.players['p3'].hand.cards[0].visibility == Visibility.FACE_UP

    assert result.advance_step  # Round should end
    
    # Verify final state
    assert game.betting.get_main_pot_amount() == 6  # All players put in 2

    game._next_step()  # continue to showdown
    assert game.current_step == 3    

# def test_basic_fold_sequence():
#     """Test basic sequence: Button folds, SB calls, BB checks in pre-flop betting."""
#     game = create_test_game()
#     game.start_hand()
#     assert game.current_step == 0  # Post Blinds
#     assert game.state == GameState.BETTING  # Fine for forced bets

#     game._next_step()  # Move to Deal Hole Cards (Step 1)
#     assert game.current_step == 1
#     assert game.state == GameState.DEALING

#     game._next_step()  # Move to Initial Bet (Step 2)
#     assert game.current_step == 2
#     assert game.state == GameState.BETTING
#     assert game.current_player.id == "BTN"  # Pre-flop starts with BTN in 3-player

#     # Button folds
#     result = game.player_action("BTN", PlayerAction.FOLD, 0)
#     assert result.success
#     assert not result.advance_step
#     assert game.current_player.id == "SB"

#     # Small blind calls (needs $5 more to match BB’s $10)
#     result = game.player_action("SB", PlayerAction.CALL, 10)  # Adjust amount
#     assert result.success
#     assert not result.advance_step
#     assert game.current_player.id == "BB"

#     # Big blind checks
#     result = game.player_action("BB", PlayerAction.CHECK, 0)
#     assert result.success
#     assert result.advance_step  # Betting round ends
#     assert game.betting.get_main_pot_amount() == 20  # SB: 5+5=10, BB: 10

#     game._next_step()  # Move to Showdown (Step 3)
#     assert game.current_step == 3
#     assert game.state == GameState.COMPLETE  # Hand is complete

# def test_hand_with_showdown(test_hands):
#     """Test complete hand with showdown - BTN should win with royal flush."""
#     game = create_test_game(mock_hands=test_hands)
    
#     # Capture initial stacks before blinds are posted
#     initial_stacks = {pid: player.stack for pid, player in game.table.players.items()}
    
#     game.start_hand()
    
#     # Verify blinds posted
#     assert game.betting.get_main_pot_amount() == 15  # SB(5) + BB(10)
#     assert game.table.players["SB"].stack == initial_stacks["SB"] - 5
#     assert game.table.players["BB"].stack == initial_stacks["BB"] - 10
    
#     assert game.current_step == 0  # Post Blinds
#     assert game.state == GameState.BETTING

#     game._next_step()  # Move to Deal Hole Cards (Step 1)
#     assert game.current_step == 1
#     game._next_step()  # Move to Initial Bet (Step 2)
#     assert game.current_step == 2

#     # BTN calls
#     result = game.player_action("BTN", PlayerAction.CALL, 10)
#     assert result.success
    
#     # SB completes
#     result = game.player_action("SB", PlayerAction.CALL, 10)
#     assert result.success
    
#     # BB checks
#     result = game.player_action("BB", PlayerAction.CHECK, 0)
#     assert result.success
#     assert result.advance_step  # Should move to showdown
    
#     game._next_step()  # Move to Showdown (Step 3)
#     assert game.current_step == 3

#     # Verify final state
#     assert game.state == GameState.COMPLETE
    
#     # BTN should win with royal flush
#     winner_stack = game.table.players["BTN"].stack
#     expected_win = 30  # Everyone put in 10
#     assert winner_stack == initial_stacks["BTN"] - 10 + expected_win
    
#     # Others should have lost their bets
#     assert game.table.players["SB"].stack == initial_stacks["SB"] - 10
#     assert game.table.players["BB"].stack == initial_stacks["BB"] - 10


# def test_split_pot_scenario():
#     """Test when two players tie for best hand."""
#     # Create identical full houses for BTN and SB
#     tied_hands = {
#         'BTN': [
#             Card(Rank.KING, Suit.SPADES),
#             Card(Rank.KING, Suit.HEARTS),
#             Card(Rank.KING, Suit.DIAMONDS),
#             Card(Rank.QUEEN, Suit.SPADES),
#             Card(Rank.QUEEN, Suit.HEARTS),
#         ],
#         'SB': [
#             Card(Rank.KING, Suit.CLUBS),
#             Card(Rank.KING, Suit.DIAMONDS),
#             Card(Rank.KING, Suit.HEARTS),
#             Card(Rank.QUEEN, Suit.DIAMONDS),
#             Card(Rank.QUEEN, Suit.CLUBS),
#         ],
#         'BB': [  # Lower hand
#             Card(Rank.JACK, Suit.SPADES),
#             Card(Rank.JACK, Suit.HEARTS),
#             Card(Rank.TEN, Suit.SPADES),
#             Card(Rank.TEN, Suit.HEARTS),
#             Card(Rank.NINE, Suit.SPADES),
#         ]
#     }
    
#     game = create_test_game(mock_hands=tied_hands)
    
#     # Capture initial stacks before blinds
#     initial_stacks = {pid: player.stack for pid, player in game.table.players.items()}
    
#     game.start_hand()
    
#     assert game.current_step == 0  # Post Blinds
#     game._next_step()  # Move to Deal Hole Cards (Step 1)
#     assert game.current_step == 1
#     game._next_step()  # Move to Initial Bet (Step 2)
#     assert game.current_step == 2    

#     # Play out the hand
#     result = game.player_action("BTN", PlayerAction.CALL, 10)
#     assert result.success
    
#     result = game.player_action("SB", PlayerAction.CALL, 10)
#     assert result.success
    
#     result = game.player_action("BB", PlayerAction.CHECK, 0)
#     assert result.success
#     assert result.advance_step
    
#     game._next_step()  # Move to Showdown (Step 3)
#     assert game.current_step == 3

#     # Verify split pot
#     pot_size = 30  # 10 each
#     expected_win = pot_size // 2  # Split between BTN and SB
    
#     assert game.table.players["BTN"].stack == initial_stacks["BTN"] - 10 + expected_win
#     assert game.table.players["SB"].stack == initial_stacks["SB"] - 10 + expected_win
#     assert game.table.players["BB"].stack == initial_stacks["BB"] - 10  # Lost their bet

# def test_all_fold_to_one():
#     """Test when all players fold to one player - no showdown needed."""
#     game = create_test_game()
    
#     # Get initial stacks before blinds
#     initial_stacks = {pid: player.stack for pid, player in game.table.players.items()}
    
#     game.start_hand()
#     assert game.current_step == 0  # Post Blinds
#     assert game.state == GameState.BETTING  # For forced bets

#     game._next_step()  # Move to Deal Hole Cards (Step 1)
#     assert game.current_step == 1
#     assert game.state == GameState.DEALING

#     game._next_step()  # Move to Initial Bet (Step 2)
#     assert game.current_step == 2
#     assert game.state == GameState.BETTING
#     assert game.current_player.id == "BTN"  # Pre-flop starts with BTN

#     # BTN folds
#     result = game.player_action("BTN", PlayerAction.FOLD, 0)
#     assert result.success
#     assert not result.advance_step
#     assert game.current_player.id == "SB"

#     # SB folds
#     result = game.player_action("SB", PlayerAction.FOLD, 0)
#     assert result.success
#     assert result.advance_step  # Hand ends when all but one fold
    
#     # BB wins the pot without showdown
#     assert game.state == GameState.COMPLETE
#     pot_size = 15  # Just the blinds (SB: 5, BB: 10)
#     assert game.table.players["BB"].stack == initial_stacks["BB"] - 10 + pot_size
#     assert game.table.players["BTN"].stack == initial_stacks["BTN"]  # No additional contribution
#     assert game.table.players["SB"].stack == initial_stacks["SB"] - 5  # Lost small blind

# def test_raise_and_calls(test_hands):
#     """Test raising scenario where everyone calls."""
#     game = create_test_game(test_hands)
    
#     # Get initial stacks before blinds
#     initial_stacks = {pid: player.stack for pid, player in game.table.players.items()}
#     print(initial_stacks)
    
#     game.start_hand()

#     assert game.current_step == 0  # Post Blinds
    
#     assert game.betting.get_main_pot_amount() == 15  # SB(5) + BB(10)
#     assert game.table.players["BTN"].stack == initial_stacks["BTN"]
#     assert game.table.players["SB"].stack == initial_stacks["SB"] - 5
#     assert game.table.players["BB"].stack == initial_stacks["BB"] - 10
#     assert game.betting.get_main_pot_amount() == 15  # SB + BB

#     game._next_step()  # Move to Deal Hole Cards (Step 1)
#     assert game.current_step == 1
#     game._next_step()  # Move to Initial Bet (Step 2)
#     assert game.current_step == 2     
    
#     print(game.table.players["BTN"].stack)
#     print(game.state)    
#     print(game.get_valid_actions("BTN"))

#     # Get stacks after blinds
#     post_blinds_stacks = {pid: player.stack for pid, player in game.table.players.items()}
#     print(post_blinds_stacks)

#     # BTN raises to 20
#     result = game.player_action("BTN", PlayerAction.RAISE, 20)
#     assert result.success
#     assert not result.advance_step
#     assert game.betting.current_bet == 20
#     assert game.table.players["BTN"].stack == initial_stacks["BTN"] - 20
#     assert game.betting.get_main_pot_amount() == 15 + 20 # SB + BB + BTN raise
    
#     # SB calls 20
#     result = game.player_action("SB", PlayerAction.CALL, 20)
#     assert result.success
#     assert not result.advance_step
    
#     # BB calls additional 10
#     result = game.player_action("BB", PlayerAction.CALL, 20)
#     assert result.success
#     assert result.advance_step  # Round should complete
        
#     # Verify pot and stacks after the raise round
#     assert game.betting.get_main_pot_amount() == 60  # Everyone put in 20
    
#     game._next_step()  # Move to Showdown (Step 3)
#     assert game.current_step == 3

#     # BTN should win with royal flush
#     assert game.state == GameState.COMPLETE
#     winner_stack = game.table.players["BTN"].stack
#     expected_win = 60  # Everyone put in 20
#     assert winner_stack == initial_stacks["BTN"] - 20 + expected_win
    
#     # Others should have lost their bets
#     assert game.table.players["SB"].stack == initial_stacks["SB"] - 20
#     assert game.table.players["BB"].stack == initial_stacks["BB"] - 20
