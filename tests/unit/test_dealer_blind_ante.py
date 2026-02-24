"""Tests for poker betting flow."""

import json
import logging
import sys

import pytest

from generic_poker.config.loader import GameRules
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game, GameState, PlayerAction


@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for all tests."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Force reconfiguration of logging
    )


def create_nehe_game():
    """Create New England Hold'em game with dealer blind + ante."""
    rules = {
        "game": "New England Hold'em",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "bettingOrder": {"initial": "dealer", "subsequent": "last_actor"},
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Dealer Blind and Ante"},
            {"deal": {"location": "player", "cards": [{"number": 2, "state": "face down"}]}, "name": "Deal Hole Cards"},
            {"bet": {"type": "small"}, "name": "Pre-Flop Bet"},
            {"deal": {"location": "community", "cards": [{"number": 3, "state": "face up"}]}, "name": "Deal Flop"},
            {"bet": {"type": "small"}, "name": "Post-Flop Bet"},
            {"showdown": {"type": "final"}, "name": "Showdown"},
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "any combination of hole and community cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}],
        },
    }

    return Game(
        rules=GameRules.from_json(json.dumps(rules)),
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        small_blind=0,  # No small blind
        big_blind=10,  # Dealer blind amount
        ante=10,  # Dealer ante amount
        min_buyin=5,
        max_buyin=1000,
        auto_progress=False,
    )


def create_traditional_with_bb_ante_game():
    """Create traditional Hold'em with big blind ante."""
    rules = {
        "game": "Hold'em with Big Blind Ante",
        "players": {"min": 2, "max": 9},
        "deck": {"type": "standard", "cards": 52},
        "bettingStructures": ["Limit", "No Limit", "Pot Limit"],
        "bettingOrder": {"initial": "after_big_blind", "subsequent": "dealer"},
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds and Ante"},
            {"deal": {"location": "player", "cards": [{"number": 2, "state": "face down"}]}, "name": "Deal Hole Cards"},
            {"bet": {"type": "small"}, "name": "Pre-Flop Bet"},
            {"showdown": {"type": "final"}, "name": "Showdown"},
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "any combination of hole and community cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}],
        },
    }

    return Game(
        rules=GameRules.from_json(json.dumps(rules)),
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        small_blind=5,  # Traditional small blind
        big_blind=10,  # Traditional big blind
        ante=10,  # Big blind also posts ante
        min_buyin=10,
        max_buyin=1000,
        auto_progress=False,
    )


def test_nehe_dealer_blind_ante_basic():
    """Test New England Hold'em dealer posts blind and ante."""
    game = create_nehe_game()

    # Add players (p1=Button/Dealer, p2=SB position, p3=BB position, p4=UTG)
    game.add_player("p1", "Alice", 500)  # Will be dealer/button
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    game.add_player("p4", "Doug", 500)

    game.start_hand()

    # Verify initial state after forced bets
    assert game.current_step == 0
    assert game.state == GameState.BETTING

    # Check that dealer (p1) posted blind (ante is separate)
    dealer_bet = game.betting.current_bets.get("p1")
    assert dealer_bet is not None
    assert dealer_bet.amount == 10  # Just the blind portion
    assert dealer_bet.posted_blind == True

    # Check other players haven't posted anything
    for pid in ["p2", "p3", "p4"]:
        assert pid not in game.betting.current_bets

    # Check pot totals
    assert game.betting.get_ante_total() == 10  # Just the ante portion
    assert game.betting.get_main_pot_amount() == 20  # 10 blind + 10 ante
    assert game.betting.current_bet == 10  # Only the blind counts toward current bet

    # Move to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round

    # First to act should be player after dealer (p2)
    assert game.current_player.id == "p2"


def test_nehe_heads_up():
    """Test New England Hold'em in heads-up play."""
    game = create_nehe_game()

    # Add only 2 players
    game.add_player("p1", "Alice", 500)  # Will be dealer/button
    game.add_player("p2", "Bob", 500)

    game.start_hand()

    # Check that dealer posted blind and ante
    dealer_bet = game.betting.current_bets.get("p1")
    assert dealer_bet.amount == 10  # 10 blind

    # Check pot
    assert game.betting.get_ante_total() == 10  # Just the ante portion
    assert game.betting.get_main_pot_amount() == 20  # 10 blind + 10 ante
    assert game.betting.current_bet == 10

    # Move to betting
    game._next_step()  # Deal
    game._next_step()  # First betting round

    # In heads-up, non-dealer acts first
    assert game.current_player.id == "p2"


def test_traditional_bb_ante():
    """Test traditional Hold'em with big blind ante."""
    game = create_traditional_with_bb_ante_game()

    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)  # Will be small blind
    game.add_player("p3", "Charlie", 500)  # Will be big blind + ante
    game.add_player("p4", "Doug", 500)

    game.start_hand()

    # Check small blind
    sb_bet = game.betting.current_bets.get("p2")
    assert sb_bet is not None
    assert sb_bet.amount == 5  # Just small blind

    # Check big blind + ante
    bb_bet = game.betting.current_bets.get("p3")
    assert bb_bet is not None
    assert bb_bet.amount == 10  # 10 big blind

    # Check pot totals
    assert game.betting.get_main_pot_amount() == 25  # 5 SB + 10 BB + 10 ante
    assert game.betting.get_ante_total() == 10  # Just the ante
    assert game.betting.current_bet == 10  # Big blind sets the current bet

    # Move to betting
    game._next_step()  # Deal
    game._next_step()  # First betting round

    # First to act should be UTG (p4) - after big blind
    assert game.current_player.id == "p4"


def test_nehe_dealer_insufficient_stack():
    """Test when dealer doesn't have enough chips for both blind and ante."""
    game = create_nehe_game()

    game.add_player("p1", "Alice", 15)  # Only enough for blind + partial ante
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    game.add_player("p4", "Doug", 500)

    game.start_hand()

    # Dealer should post what they can
    dealer_bet = game.betting.current_bets.get("p1")
    assert dealer_bet is not None
    assert dealer_bet.amount == 10  # All their chips
    assert game.table.players["p1"].stack == 0  # Should be all-in

    # Check pot - should have all 15 chips
    assert game.betting.get_main_pot_amount() == 15
    assert game.betting.get_ante_total() == 5  # Just the partial ante from all-in


def test_bb_ante_insufficient_stack():
    """Test when big blind player can't cover blind + ante."""
    game = create_traditional_with_bb_ante_game()

    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 15)  # Only enough for blind + partial ante
    game.add_player("p4", "Doug", 500)

    game.start_hand()

    # Check small blind posted normally
    sb_bet = game.betting.current_bets.get("p2")
    assert sb_bet.amount == 5

    # Big blind posts what they can
    bb_bet = game.betting.current_bets.get("p3")
    assert bb_bet.amount == 10  # blind amount
    assert game.table.players["p3"].stack == 0  # Should be all-in

    # Check pot - should have all 15 chips
    assert game.betting.get_main_pot_amount() == 20  # sb of 5 + bb of 10 + ante of 5
    assert game.betting.get_ante_total() == 5  # Just the partial ante from all-in


def test_nehe_betting_progression():
    """Test full betting progression in New England Hold'em."""
    game = create_nehe_game()

    game.add_player("p1", "Alice", 500)  # Dealer
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    game.add_player("p4", "Doug", 500)

    game.start_hand()

    # Skip to first betting round
    game._next_step()  # Deal
    game._next_step()  # First betting round

    # Betting should start with p2 (after dealer)
    assert game.current_player.id == "p2"

    # Test calling sequence - players need to call 10 to match dealer's blind
    game.player_action("p2", PlayerAction.CALL, 10)
    assert game.current_player.id == "p3"

    game.player_action("p3", PlayerAction.CALL, 10)
    assert game.current_player.id == "p4"

    game.player_action("p4", PlayerAction.CALL, 10)
    assert game.current_player.id == "p1"  # Back to dealer

    valid_actions = game.get_valid_actions("p1")
    print(f"Valid actions for dealer: {valid_actions}")

    # Dealer can check (already has 10 in blind)
    result = game.player_action("p1", PlayerAction.CHECK, 0)
    assert result.advance_step  # Round should complete

    # Check final pot
    assert game.betting.get_main_pot_amount() == 50  # 4 * 10 + 10 ante


def test_nehe_raise_scenario():
    """Test raising in New England Hold'em."""
    game = create_nehe_game()

    game.add_player("p1", "Alice", 500)  # Dealer
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)
    game.add_player("p4", "Doug", 500)

    game.start_hand()
    game._next_step()  # Deal
    game._next_step()  # First betting round

    # p2 raises
    game.player_action("p2", PlayerAction.RAISE, 20)
    assert game.current_player.id == "p3"

    # Others call the raise
    game.player_action("p3", PlayerAction.CALL, 20)
    game.player_action("p4", PlayerAction.CALL, 20)

    valid_actions = game.get_valid_actions("p1")
    print(f"Valid actions for dealer: {valid_actions}")

    # Dealer needs to call the raise (additional 10 on top of blind)
    result = game.player_action("p1", PlayerAction.CALL, 20)
    assert result.advance_step

    # Check last actor tracking - p1 (dealer) was last to call
    assert game.betting.last_actor_id == "p1"

    # Move to next round
    game._next_step()  # Deal
    game._next_step()  # Next betting round

    # p2 should be first (after p1 who was last actor)
    assert game.current_player.id == "p2"


def test_ante_only_mode():
    """Test antes_only forced bet style: all players post antes, no blinds."""
    rules_json = {
        "game": "Ante Only Test",
        "players": {"min": 2, "max": 6},
        "deck": {"type": "standard", "cards": 52},
        "forcedBets": {"style": "antes_only"},
        "bettingStructures": ["Limit"],
        "gamePlay": [
            {"bet": {"type": "antes"}, "name": "Post Antes"},
            {
                "deal": {
                    "location": "player",
                    "cards": [{"number": 5, "state": "face down"}],
                },
                "name": "Deal Cards",
            },
            {"showdown": {"type": "final"}, "name": "Showdown"},
        ],
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [{"evaluationType": "high", "anyCards": 5}],
        },
    }

    game = Game(
        rules=GameRules.from_json(json.dumps(rules_json)),
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        ante=5,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False,
    )

    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    game.add_player("p3", "Charlie", 500)

    game.start_hand()

    # Stacks should be reduced by ante
    for p in game.table.players.values():
        assert p.stack == 495, f"{p.id} stack should be 495 after 5 ante"

    # Total pot should equal 3 * 5 = 15 (antes tracked in pot, not current_bets)
    assert game.betting.get_total_pot() == 15
    assert game.betting.get_ante_total() == 15

    # No current_player after forced bets (antes don't start a betting round)
    assert game.current_player is None

    # Advance through deal and showdown
    game._next_step()  # Deal cards
    assert game.state == GameState.DEALING

    game._next_step()  # Showdown
    assert game.state in (GameState.SHOWDOWN, GameState.COMPLETE)


def test_mixed_stack_sizes():
    """Test ante/blind posting with various stack sizes."""
    game = create_nehe_game()

    game.add_player("p1", "Alice", 25)  # Dealer - enough for blind+ante+some
    game.add_player("p2", "Bob", 8)  # Less than required bet
    game.add_player("p3", "Charlie", 500)
    game.add_player("p4", "Doug", 500)

    game.start_hand()
    game._next_step()  # Deal
    game._next_step()  # First betting round

    # p2 has only 8 chips, less than the 10 needed to call
    assert game.current_player.id == "p2"

    # p2 can only go all-in for 8
    valid_actions = game.action_handler.get_valid_actions("p2")
    call_actions = [a for a in valid_actions if a[0] == PlayerAction.CALL]
    assert len(call_actions) == 1
    assert call_actions[0][1] == 8  # Can only call for 8 (all-in)
