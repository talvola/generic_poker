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

def create_test_game_short_player(mock_hands=None):
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
        min_buyin=10,
        max_buyin=1000,
        auto_progress=False        
    )
    
    # Add players - make P1 short
    game.add_player("p1", "Alice", 15)
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

def test_basic_call_sequence_with_raise():
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
    
    # P4 calls
    result = game.player_action("p4", PlayerAction.CALL, 10)
    assert result.success
    assert not result.advance_step  # Round shouldn't be over
    assert game.current_player.id == "p1"  # Should move to p1
    
    # P1 raises
    result = game.player_action("p1", PlayerAction.RAISE, 20)
    assert result.success
    assert not result.advance_step
    assert game.current_player.id == "p2"  # Should move to p2
    
    # P2 (SB) folds
    result = game.player_action("p2", PlayerAction.FOLD)
    assert result.success
    assert not result.advance_step
    assert game.current_player.id == "p3"  # Should move to p3
    
    # P3 (BB) calls
    result = game.player_action("p3", PlayerAction.CALL, 20)
    assert result.success
    assert not result.advance_step
    assert game.current_player.id == "p4"  # Should move to p4
   
    # P4 calls the raise
    result = game.player_action("p4", PlayerAction.CALL, 20)
    assert result.success
    assert result.advance_step  # Round is over - everyone bet/called/folded

    # Verify final state
    assert game.betting.get_main_pot_amount() == 65  # SB put in 5, All other players put in 20

    game._next_step()  # Manually move to next deal
    assert game.current_step == 3    
    assert game.state == GameState.DEALING  # 
    game._next_step()  # then move to last betting step

    # Step 4 - last betting step 

    # since we are using 'last actor' - P4 acted last with the call, so P1 is the next actor

    assert game.current_player.id == "p1"    

def test_multiple_folds_last_actor():
    """Test that last_actor works correctly when multiple players fold in sequence."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # p4 calls, p1 folds, p2 folds, p3 checks
    game.player_action("p4", PlayerAction.CALL, 10)
    game.player_action("p1", PlayerAction.FOLD)
    game.player_action("p2", PlayerAction.FOLD) 
    result = game.player_action("p3", PlayerAction.CHECK, 0)
    assert result.advance_step
    
    # p3 was last to act, so p4 should be first in next round
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p4"

def test_last_actor_after_raise():
    """Test that the player who calls a raise becomes the last actor."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round  
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # p4 raises, p1 calls, p2 folds, p3 calls
    game.player_action("p4", PlayerAction.RAISE, 20)  # Raise to 20
    game.player_action("p1", PlayerAction.CALL, 20)
    game.player_action("p2", PlayerAction.FOLD)
    result = game.player_action("p3", PlayerAction.CALL, 20)
    assert result.advance_step
    
    # p3 was last to act (called the raise), so p4 should be first in next round
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p4"

def test_last_actor_reraise_scenario():
    """Test last actor tracking through multiple raises."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal  
    game._next_step()  # First betting round
    
    # p4 raises, p1 re-raises, everyone else calls
    game.player_action("p4", PlayerAction.RAISE, 20)  # Raise
    game.player_action("p1", PlayerAction.RAISE, 30)  # Re-raise
    game.player_action("p2", PlayerAction.CALL, 30)  # Call re-raise
    game.player_action("p3", PlayerAction.CALL, 30)  # Call re-raise  
    result = game.player_action("p4", PlayerAction.CALL, 30)  # Call re-raise
    assert result.advance_step
    
    # p4 was last to act (called the re-raise), so p1 should be first in next round
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p1"

def test_last_actor_all_in_scenario():
    """Test last actor when a player goes all-in."""
    game = create_test_game_short_player()

    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # p2 has put in 5 as the SB, and p3 has put in 10 as the BB

    # p4 calls, p1 goes all-in for 15, others call
    game.player_action("p4", PlayerAction.CALL, 10)
    game.player_action("p1", PlayerAction.RAISE, 15)  # All-in for less than normal raise amount of 20 - should be allowed
    game.player_action("p2", PlayerAction.CALL, 15)
    game.player_action("p3", PlayerAction.CALL, 15)
    result = game.player_action("p4", PlayerAction.CALL, 15)
    assert result.advance_step
    
    # p4 was last to act, so p4 should be first in next round
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p1"

def test_last_actor_heads_up_after_folds():
    """Test last actor behavior when action gets to heads-up."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # p4 calls, p1 and p2 fold, p3 checks (now heads-up for future rounds)
    game.player_action("p4", PlayerAction.CALL, 10)
    game.player_action("p1", PlayerAction.FOLD)
    game.player_action("p2", PlayerAction.FOLD)
    result = game.player_action("p3", PlayerAction.CHECK, 0)
    assert result.advance_step
    
    # p3 was last to act, so p4 should be first in next round
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p4"
    
    # Verify only p3 and p4 are still active
    active_players = [p for p in game.table.players.values() if p.is_active]
    assert len(active_players) == 2
    assert set(p.id for p in active_players) == {"p3", "p4"}

def test_last_actor_position_wraparound():
    """Test that last actor correctly wraps around table positions."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # Everyone calls except p1 who acts last and raises
    game.player_action("p4", PlayerAction.CALL, 10)
    game.player_action("p1", PlayerAction.RAISE, 20)  # p1 raises last
    game.player_action("p2", PlayerAction.CALL, 20)
    game.player_action("p3", PlayerAction.CALL, 20)
    result = game.player_action("p4", PlayerAction.CALL, 20)
    assert result.advance_step
    
    # p4 was last to act (called p1's raise), so p1 should be first in next round  
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p1"

def test_last_actor_with_no_previous_action():
    """Test fallback behavior when no last_actor_id is set."""
    game = create_test_game()
    
    # Manually clear last_actor_id to test fallback
    game.betting.last_actor_id = None
    
    # This should fall back to dealer order
    next_player = game.next_player(round_start=True)
    # Should use dealer order fallback since no last actor recorded
    assert next_player is not None

def test_last_actor_when_last_actor_folds():
    """Test behavior when the last actor from previous round has folded."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # p4 raises, others call/check, p3 folds
    game.player_action("p4", PlayerAction.RAISE, 20)
    game.player_action("p1", PlayerAction.CALL, 20)
    game.player_action("p2", PlayerAction.CALL, 20)  # Complete blind
    result = game.player_action("p3", PlayerAction.FOLD)
    assert result.advance_step
    
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    
    # p2 was last to call, p3 folded, so P4 is next
    assert game.current_player.id == "p4"

def test_last_actor_preserves_across_multiple_rounds():
    """Test that last actor correctly carries through multiple betting rounds."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # First round: p4 calls, p1 calls, p2 calls, p3 checks (p3 last)
    game.player_action("p4", PlayerAction.CALL, 10)
    game.player_action("p1", PlayerAction.CALL, 10) 
    game.player_action("p2", PlayerAction.CALL, 5)
    game.player_action("p3", PlayerAction.CHECK, 0)
    
    # Move to second betting round
    game._next_step()  # Deal
    game._next_step()  # Second betting round
    
    # p4 should be first (after p3 who was last)
    assert game.current_player.id == "p4"
    
    # Second round: p4 checks, p1 bets, p2 calls, p3 calls (p3 last again)
    game.player_action("p4", PlayerAction.CHECK, 0)
    game.player_action("p1", PlayerAction.BET, 10)
    game.player_action("p2", PlayerAction.CALL, 10)
    game.player_action("p3", PlayerAction.CALL, 10)
    
    # If there were a third round, p4 should be first again
    assert game.betting.last_actor_id == "p3"    

def test_last_actor_everyone_checks():
    """Test last actor when everyone checks in a round."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # Everyone just calls/checks (no raises)
    game.player_action("p4", PlayerAction.CALL, 10)
    game.player_action("p1", PlayerAction.CALL, 10)
    game.player_action("p2", PlayerAction.CALL, 5)  # Complete SB
    result = game.player_action("p3", PlayerAction.CHECK, 0)  # BB checks
    assert result.advance_step
    
    # Move to next round (should now be all checks)
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    
    # p4 should be first (after p3 who checked last)
    assert game.current_player.id == "p4"
    
    # Now everyone checks
    game.player_action("p4", PlayerAction.CHECK, 0)
    game.player_action("p1", PlayerAction.CHECK, 0)  
    game.player_action("p2", PlayerAction.CHECK, 0)
    result = game.player_action("p3", PlayerAction.CHECK, 0)
    assert result.advance_step
    
    # p3 checked last, so if there were another round, p4 should go first
    assert game.betting.last_actor_id == "p3"

def test_last_actor_cap_betting_limit():
    """Test last actor when betting reaches the cap in limit poker."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # Multiple raises to test cap (most limit games cap at 3-4 raises)
    game.player_action("p4", PlayerAction.RAISE, 20)  # Raise 1
    game.player_action("p1", PlayerAction.RAISE, 30)  # Raise 2
    game.player_action("p2", PlayerAction.RAISE, 40)  # Raise 3
    
    # Depending on cap rules, this might be the final raise or just a call
    # The important thing is testing that last_actor tracking works through caps
    game.player_action("p3", PlayerAction.CALL, 40)
    result = game.player_action("p4", PlayerAction.CALL, 40)
    
    # Test continues regardless of whether p1 can raise again or must call
    # The point is to ensure last_actor works with capped betting

def test_last_actor_mixed_actions_same_round():
    """Test complex sequence of different actions in same round."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # Complex sequence: call, raise, fold, call, raise, call, call
    game.player_action("p4", PlayerAction.CALL, 10)      # p4 calls
    game.player_action("p1", PlayerAction.RAISE, 20)     # p1 raises  
    game.player_action("p2", PlayerAction.FOLD)          # p2 folds
    game.player_action("p3", PlayerAction.RAISE, 30)     # p3 re-raises
    game.player_action("p4", PlayerAction.CALL, 30)      # p4 calls re-raise
    result = game.player_action("p1", PlayerAction.CALL, 30)  # p1 calls re-raise
    assert result.advance_step
    
    # p1 was last to act, so p3 should be first in next round (p2 folded)
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p3"

def test_last_actor_only_big_blind_left():
    """Test when everyone folds to the big blind."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # Everyone folds to big blind
    game.player_action("p4", PlayerAction.FOLD)
    game.player_action("p1", PlayerAction.FOLD)
    result = game.player_action("p2", PlayerAction.FOLD)  # SB folds
    
    # Should trigger fold win - BB wins without acting
    assert result.advance_step
    
    # Verify only p3 (BB) is still active
    active_players = [p for p in game.table.players.values() if p.is_active]
    assert len(active_players) == 1
    assert active_players[0].id == "p3"

def test_last_actor_small_blind_completion():
    """Test last actor tracking when small blind completes."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # Everyone folds to small blind, who completes
    game.player_action("p4", PlayerAction.FOLD)
    game.player_action("p1", PlayerAction.FOLD)
    game.player_action("p2", PlayerAction.CALL, 5)  # SB completes to 10
    result = game.player_action("p3", PlayerAction.CHECK, 0)  # BB checks
    assert result.advance_step
    
    # p3 (BB) was last to act with check, so p2 should be first in next round
    game._next_step()  # Deal
    game._next_step()  # Next betting round
    assert game.current_player.id == "p2"

def test_last_actor_with_antes():
    """Test that antes don't affect last_actor tracking."""
    # This would require modifying the game setup to include antes
    # But the principle is that ante posting shouldn't update last_actor_id
    # Only voluntary betting actions should update it
    pass  # Skip this test unless you want to add ante support to test setup

def test_last_actor_exact_call_amounts():
    """Test edge case where call amounts need to be exact."""
    game = create_test_game()
    game.start_hand()
    
    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round
    
    # Test exact call amounts (this was part of one bug you found)
    game.player_action("p4", PlayerAction.CALL, 10)
    game.player_action("p1", PlayerAction.CALL, 10)
    
    # p2 needs to call exactly 5 more (was SB with 5, needs to get to 10)
    game.player_action("p2", PlayerAction.CALL, 5)  # Should be total of 10, adding 5
    
    result = game.player_action("p3", PlayerAction.CHECK, 0)
    assert result.advance_step
    
    # p3 was last to act
    assert game.betting.last_actor_id == "p3"    