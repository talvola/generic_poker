"""Tests for poker betting flow."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
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
        "game": "Straight Poker - Last Actor Test",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "bettingOrder": {"initial": "after_big_blind","subsequent": "last_actor"},       
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 4, "state": "face down"}]
            }, "name": "Deal Hole Cards"},
            {"bet": {"type": "small"}, "name": "Initial Bet"},
            {"deal": {
                "location": "player",
                "cards": [{"number": 1, "state": "face down"}]
            }, "name": "Deal Hole Cards"},     
            {"bet": {"type": "small"}, "name": "Second Bet"},
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
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    game.add_player("p4", "Doug", 500)
    
    if mock_hands:
        # Replace the deal step to use our test hands
        def mock_deal(self, config):
            for pid, hand in mock_hands.items():
                self.table.players[pid].hand.clear()
                self.table.players[pid].hand.add_cards(hand)
        game._handle_deal = mock_deal.__get__(game)
    
    return game

def test_basic_call_sequence():
    """Test basic sequence: p1 calls, p2 calls, p3 checks, p4 checks."""
    game = create_test_game()
    game.start_hand()
    
    # Verify initial state
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets 

    assert game.betting.current_bet == 10  # Big blind amount
    assert game.betting.get_main_pot_amount() == 15  # SB(5) + BB(10)
    game._next_step()  # Manually move to dealing hole cards
    
    assert game.current_step == 1           # Should be in dealing step
    assert game.state == GameState.DEALING  # 
    game._next_step()  # Manually move to dealing hole cards

    assert game.current_step == 2           # Should be in Iniital Bet step
    assert game.state == GameState.BETTING  # Now player betting occurs    

    # Verify first action is to Button (Alice)
    assert game.current_player.id == "p4"
    
    # 
    result = game.player_action("p4", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step  # Round shouldn't be over
    assert game.current_player.id == "p1"  # Should move to p1
    
    # Small blind calls
    result = game.player_action("p1", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step
    assert game.current_player.id == "p2"  # Should move to p2
    
    # Big blind checks
    result = game.player_action("p2", PlayerAction.CALL, 3)
    assert result.success
    assert not result.advance_step
    assert game.current_player.id == "p3"  # Should move to p4
    
    # Big blind checks
    result = game.player_action("p3", PlayerAction.CHECK, 0)
    assert result.success
    assert result.advance_step  # Round should end
   
    # Verify final state
    assert game.betting.get_main_pot_amount() == 40  # All players put in 10

    game._next_step()  # Manually move to next deal
    assert game.current_step == 3    
    assert game.state == GameState.DEALING  # 
    game._next_step()  # then move to last betting step

    # Step 4 - last betting step 

    # since we are using 'last actor' - P3 acted last previously, so we are at P4 now.

    assert game.current_player.id == "p4"


def test_basic_call_sequence_with_fold():
    """Test basic sequence: p1 calls, p2 calls, p3 checks, p4 checks."""
    game = create_test_game()
    game.start_hand()
    
    # Verify initial state
    assert game.current_step == 0           # Should be in post blinds step
    assert game.state == GameState.BETTING  # Forced bets 

    assert game.betting.current_bet == 10  # Big blind amount
    assert game.betting.get_main_pot_amount() == 15  # SB(5) + BB(10)
    game._next_step()  # Manually move to dealing hole cards
    
    assert game.current_step == 1           # Should be in dealing step
    assert game.state == GameState.DEALING  # 
    game._next_step()  # Manually move to dealing hole cards

    assert game.current_step == 2           # Should be in Iniital Bet step
    assert game.state == GameState.BETTING  # Now player betting occurs    

    # Verify first action is to Button (Alice)
    assert game.current_player.id == "p4"
    
    # 
    result = game.player_action("p4", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step  # Round shouldn't be over
    assert game.current_player.id == "p1"  # Should move to p1
    
    # Small blind calls
    result = game.player_action("p1", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step
    assert game.current_player.id == "p2"  # Should move to p2
    
    # Small blind folds
    result = game.player_action("p2", PlayerAction.FOLD)
    assert result.success
    assert not result.advance_step
    assert game.current_player.id == "p3"  # Should move to p4
    
    # Big blind checks
    result = game.player_action("p3", PlayerAction.CHECK, 0)
    assert result.success
    assert result.advance_step  # Round should end
   
    # Verify final state
    assert game.betting.get_main_pot_amount() == 35  # SB put in 5, All other players put in 10

    game._next_step()  # Manually move to next deal
    assert game.current_step == 3    
    assert game.state == GameState.DEALING  # 
    game._next_step()  # then move to last betting step

    # Step 4 - last betting step 

    # since we are using 'last actor' - P3 acted last previously, so we are at P4 now.

    assert game.current_player.id == "p4"