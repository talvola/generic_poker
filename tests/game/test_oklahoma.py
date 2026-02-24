"""Tests for Oklahoma (Omaha hi-lo with 3 boards, lowest river board removed)."""

import logging
import sys

import pytest

from generic_poker.core.card import Card, Rank, Suit
from generic_poker.core.deck import Deck
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game, GameState, PlayerAction
from tests.test_helpers import load_rules_from_file


class MockDeck(Deck):
    """A deck with predetermined card sequence for testing, followed by remaining cards."""

    def __init__(self, named_cards):
        super().__init__(include_jokers=False)
        self.cards.clear()
        for card in named_cards:
            self.cards.append(card)
        all_cards = [
            Card(rank, suit)
            for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
            for rank in [
                Rank.TWO,
                Rank.THREE,
                Rank.FOUR,
                Rank.FIVE,
                Rank.SIX,
                Rank.SEVEN,
                Rank.EIGHT,
                Rank.NINE,
                Rank.TEN,
                Rank.JACK,
                Rank.QUEEN,
                Rank.KING,
                Rank.ACE,
            ]
        ]
        used_cards = {(c.rank, c.suit) for c in named_cards}
        remaining_cards = [c for c in all_cards if (c.rank, c.suit) not in used_cards]
        for card in remaining_cards:
            self.cards.append(card)
        self.cards.reverse()


@pytest.fixture(autouse=True)
def setup_logging():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def create_oklahoma_deck_distinct_rivers():
    """Create a deck where Board 3 has the lowest river card and gets removed.

    Board layout (3 boards × 5 cards each = 15 community cards):
      Board 1: Flop(As Ks Qs) Turn(Js) River(Ts)  - river T (index 9 in BASE_RANKS)
      Board 2: Flop(Ah Kh Qh) Turn(Jh) River(9h)  - river 9 (index 10)
      Board 3: Flop(Ad Kd Qd) Turn(Jd) River(2d)  - river 2 (index 12) ← LOWEST, removed

    Player hole cards (4 each, Omaha-style):
      P1: Ac Tc 8c 7c
      P2: 5s 4s 3s 6h
    """
    named_cards = [
        # P1 hole (4)
        Card(Rank.ACE, Suit.CLUBS),
        Card(Rank.TEN, Suit.CLUBS),
        Card(Rank.EIGHT, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.CLUBS),
        # P2 hole (4)
        Card(Rank.FIVE, Suit.SPADES),
        Card(Rank.FOUR, Suit.SPADES),
        Card(Rank.THREE, Suit.SPADES),
        Card(Rank.SIX, Suit.HEARTS),
        # Flops: Board 1 (3), Board 2 (3), Board 3 (3) — dealt in config order
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.ACE, Suit.DIAMONDS),
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        # Turns: Board 1 (1), Board 2 (1), Board 3 (1)
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.JACK, Suit.DIAMONDS),
        # Rivers: Board 1 (1), Board 2 (1), Board 3 (1)
        Card(Rank.TEN, Suit.SPADES),  # Board 1 river: T
        Card(Rank.NINE, Suit.HEARTS),  # Board 2 river: 9
        Card(Rank.TWO, Suit.DIAMONDS),  # Board 3 river: 2 ← lowest
    ]
    return MockDeck(named_cards)


def create_oklahoma_deck_same_rivers():
    """Create a deck where all 3 boards have the same river rank → no board removed.

    Board layout:
      Board 1: Flop(As Ks Qs) Turn(Js) River(Ts)  - river T
      Board 2: Flop(Ah Kh Qh) Turn(Jh) River(Th)  - river T
      Board 3: Flop(Ad Kd Qd) Turn(Jd) River(Tc)  - river T
      All rivers are T → same rank → no removal

    Player hole cards:
      P1: Ac 9c 8c 7c
      P2: 5s 4s 3s 6h
    """
    named_cards = [
        # P1 hole (4)
        Card(Rank.ACE, Suit.CLUBS),
        Card(Rank.NINE, Suit.CLUBS),
        Card(Rank.EIGHT, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.CLUBS),
        # P2 hole (4)
        Card(Rank.FIVE, Suit.SPADES),
        Card(Rank.FOUR, Suit.SPADES),
        Card(Rank.THREE, Suit.SPADES),
        Card(Rank.SIX, Suit.HEARTS),
        # Flops
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.ACE, Suit.DIAMONDS),
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        # Turns
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.JACK, Suit.DIAMONDS),
        # Rivers — all Tens
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.TEN, Suit.HEARTS),
        Card(Rank.TEN, Suit.CLUBS),
    ]
    return MockDeck(named_cards)


def create_oklahoma_deck_two_tied_lowest():
    """Create a deck where 2 boards tie for lowest river → both removed.

    Board layout:
      Board 1: Flop(As Ks Qs) Turn(Js) River(Ts)  - river T
      Board 2: Flop(Ah Kh Qh) Turn(Jh) River(2h)  - river 2 ← lowest (tie)
      Board 3: Flop(Ad Kd Qd) Turn(Jd) River(2d)  - river 2 ← lowest (tie)
      Boards 2 and 3 both removed

    Player hole cards:
      P1: Ac 9c 8c 7c
      P2: 5s 4s 3s 6h
    """
    named_cards = [
        # P1 hole (4)
        Card(Rank.ACE, Suit.CLUBS),
        Card(Rank.NINE, Suit.CLUBS),
        Card(Rank.EIGHT, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.CLUBS),
        # P2 hole (4)
        Card(Rank.FIVE, Suit.SPADES),
        Card(Rank.FOUR, Suit.SPADES),
        Card(Rank.THREE, Suit.SPADES),
        Card(Rank.SIX, Suit.HEARTS),
        # Flops
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.ACE, Suit.DIAMONDS),
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        # Turns
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.JACK, Suit.DIAMONDS),
        # Rivers
        Card(Rank.TEN, Suit.SPADES),  # Board 1: T
        Card(Rank.TWO, Suit.HEARTS),  # Board 2: 2 ← tie lowest
        Card(Rank.TWO, Suit.DIAMONDS),  # Board 3: 2 ← tie lowest
    ]
    return MockDeck(named_cards)


def setup_game(deck_factory):
    """Setup a 2-player Oklahoma game with a specific deck."""
    rules = load_rules_from_file("oklahoma")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False,
    )
    game.add_player("BTN", "Player1", 500)
    game.add_player("SB", "Player2", 500)

    def patched_clear_hands():
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()

    game.table.clear_hands = patched_clear_hands
    game.table.deck = deck_factory()

    return game


def play_through_betting(game):
    """Play through a betting round (all players check/call, never fold/raise)."""
    while game.current_player:
        actions = game.get_valid_actions(game.current_player.id)
        # Pick check if available, else call — never fold or raise
        result = None
        for a in actions:
            if a[0] == PlayerAction.CHECK:
                result = game.player_action(game.current_player.id, PlayerAction.CHECK, 0)
                break
            elif a[0] == PlayerAction.CALL:
                result = game.player_action(game.current_player.id, PlayerAction.CALL, a[1])
                break
        if result and result.advance_step:
            game._next_step()
            break


def play_to_showdown(game):
    """Play a full Oklahoma hand to showdown with all checks/calls."""
    game.start_hand()
    max_steps = 50
    steps = 0

    while game.state not in (GameState.SHOWDOWN, GameState.COMPLETE) and steps < max_steps:
        if game.state == GameState.BETTING:
            if game.current_player is None:
                game._next_step()
            else:
                play_through_betting(game)
        else:
            game._next_step()
        steps += 1

    assert game.state in (
        GameState.SHOWDOWN,
        GameState.COMPLETE,
    ), f"Game stuck at state {game.state} after {steps} steps"
    return game


def test_oklahoma_remove_lowest_river():
    """Board with lowest river card is removed (distinct rivers)."""
    game = setup_game(create_oklahoma_deck_distinct_rivers)
    game = play_to_showdown(game)

    # Board 3 had river 2d (lowest), should be removed
    assert "Board 1" in game.table.community_cards, "Board 1 (river T) should survive"
    assert "Board 2" in game.table.community_cards, "Board 2 (river 9) should survive"
    assert "Board 3" not in game.table.community_cards, "Board 3 (river 2) should be removed"

    # Surviving boards still have 5 cards each
    assert len(game.table.community_cards["Board 1"]) == 5
    assert len(game.table.community_cards["Board 2"]) == 5


def test_oklahoma_same_rivers_no_removal():
    """When all river cards have the same rank, no boards are removed."""
    game = setup_game(create_oklahoma_deck_same_rivers)
    game = play_to_showdown(game)

    # All 3 boards should survive
    assert "Board 1" in game.table.community_cards
    assert "Board 2" in game.table.community_cards
    assert "Board 3" in game.table.community_cards
    assert len(game.table.community_cards["Board 1"]) == 5
    assert len(game.table.community_cards["Board 2"]) == 5
    assert len(game.table.community_cards["Board 3"]) == 5


def test_oklahoma_two_tied_lowest_both_removed():
    """When two boards tie for lowest river, both are removed."""
    game = setup_game(create_oklahoma_deck_two_tied_lowest)
    game = play_to_showdown(game)

    # Boards 2 and 3 both had river 2, should both be removed
    assert "Board 1" in game.table.community_cards, "Board 1 (river T) should survive"
    assert "Board 2" not in game.table.community_cards, "Board 2 (river 2) should be removed"
    assert "Board 3" not in game.table.community_cards, "Board 3 (river 2) should be removed"


def test_oklahoma_completes_with_results():
    """Full hand plays to showdown and produces valid results."""
    game = setup_game(create_oklahoma_deck_distinct_rivers)
    game = play_to_showdown(game)

    results = game.get_hand_results()
    assert results is not None
    assert len(results.pots) >= 1

    # Total chips should be conserved
    total_stacks = sum(p.stack for p in game.table.players.values())
    assert total_stacks == 1000  # Both started with 500


def test_oklahoma_surviving_board_cards():
    """Verify surviving boards have correct river cards after removal."""
    game = setup_game(create_oklahoma_deck_distinct_rivers)
    game = play_to_showdown(game)

    # Board 1 survived — river should be Ts
    board1 = game.table.community_cards["Board 1"]
    assert board1[-1].rank == Rank.TEN
    assert board1[-1].suit == Suit.SPADES

    # Board 2 survived — river should be 9h
    board2 = game.table.community_cards["Board 2"]
    assert board2[-1].rank == Rank.NINE
    assert board2[-1].suit == Suit.HEARTS

    # Board 3 removed
    assert "Board 3" not in game.table.community_cards


def test_oklahoma_same_rivers_completes():
    """When no boards are removed (same rivers), game still completes correctly."""
    game = setup_game(create_oklahoma_deck_same_rivers)
    game = play_to_showdown(game)

    results = game.get_hand_results()
    assert results is not None

    # All 3 boards survive — showdown evaluates across all boards
    assert "Board 1" in game.table.community_cards
    assert "Board 2" in game.table.community_cards
    assert "Board 3" in game.table.community_cards

    total_stacks = sum(p.stack for p in game.table.players.values())
    assert total_stacks == 1000
