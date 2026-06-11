"""Tests for the debug seeded / stacked deck feature (BACKLOG T009).

The engine supports two reproducibility aids for testing specific scenarios:

* a seeded RNG (``Table(deck_seed=...)``) for reproducible-but-random shuffles
  across hands, and
* a stacked deck (``table.set_stacked_deck(cards)``) that forces an exact deal
  order so a scenario (e.g. an open pair on 4th street) can be reproduced on
  demand. This is the engine equivalent of the ``MockDeck`` test pattern, but
  it survives the deck rebuild that happens in ``Table.clear_hands``.
"""

from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from tests.test_helpers import load_rules_from_file


def _holdem_game() -> Game:
    rules = load_rules_from_file("hold_em")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=True,
    )
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    return game


def _seeded_holdem_game(seed: int) -> Game:
    rules = load_rules_from_file("hold_em")
    # Reproduce Game's table construction but inject a seed.
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=True,
    )
    game.table.deck_seed = seed
    import random

    game.table._deck_rng = random.Random(seed)
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    return game


def _hole_cards(game: Game) -> dict[str, list[str]]:
    return {pid: [str(c) for c in p.hand.cards] for pid, p in game.table.players.items()}


def test_seeded_deck_is_reproducible():
    """Two games with the same seed deal identical hands."""
    g1 = _seeded_holdem_game(42)
    g1.start_hand(shuffle_deck=True)
    g2 = _seeded_holdem_game(42)
    g2.start_hand(shuffle_deck=True)
    assert _hole_cards(g1) == _hole_cards(g2)


def test_seeded_deck_varies_across_hands():
    """A seeded deck still deals different cards on successive hands."""
    g = _seeded_holdem_game(7)
    g.start_hand(shuffle_deck=True)
    first = _hole_cards(g)
    g.start_hand(shuffle_deck=True)
    second = _hole_cards(g)
    assert first != second


def test_different_seeds_differ():
    g1 = _seeded_holdem_game(1)
    g1.start_hand(shuffle_deck=True)
    g2 = _seeded_holdem_game(2)
    g2.start_hand(shuffle_deck=True)
    assert _hole_cards(g1) != _hole_cards(g2)


def test_stacked_deck_forces_deal_order():
    """A stacked deck deals the specified cards first, in order.

    Hold'em deals one card to each player in seat order, then a second to
    each, so the first four stacked cards become the two hole cards for the
    two players.
    """
    game = _holdem_game()
    stack = [
        Card(Rank.ACE, Suit.SPADES),  # p1 card 1
        Card(Rank.KING, Suit.SPADES),  # p2 card 1
        Card(Rank.ACE, Suit.HEARTS),  # p1 card 2
        Card(Rank.KING, Suit.HEARTS),  # p2 card 2
    ]
    game.table.set_stacked_deck(stack)
    game.start_hand(shuffle_deck=True)  # shuffle requested but must be ignored

    hands = _hole_cards(game)
    assert hands["p1"] == ["As", "Ah"]
    assert hands["p2"] == ["Ks", "Kh"]


def test_stacked_deck_not_shuffled_away():
    """start_hand(shuffle_deck=True) must not shuffle a stacked deck."""
    game = _holdem_game()
    game.table.set_stacked_deck([Card(Rank.TWO, Suit.CLUBS), Card(Rank.SEVEN, Suit.DIAMONDS)])
    game.start_hand(shuffle_deck=True)
    assert game.table.players["p1"].hand.cards[0] == Card(Rank.TWO, Suit.CLUBS)


def test_stacked_deck_one_shot_reverts():
    """A one-shot stack applies to the next hand only, then reverts to random."""
    game = _holdem_game()
    game.table.set_stacked_deck([Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)])
    game.start_hand(shuffle_deck=True)
    assert game.table.deck_is_stacked is True
    first = _hole_cards(game)
    assert first["p1"][0] == "As"

    game.start_hand(shuffle_deck=True)
    assert game.table.deck_is_stacked is False
    # No guarantee the random hand differs, but the stack must be consumed.
    assert game.table.stacked_deck is None


def test_stacked_deck_repeat_persists():
    """A repeating stack re-applies every hand until cleared."""
    game = _holdem_game()
    game.table.set_stacked_deck([Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)], repeat=True)
    game.start_hand(shuffle_deck=True)
    assert _hole_cards(game)["p1"][0] == "As"
    game.start_hand(shuffle_deck=True)
    assert _hole_cards(game)["p1"][0] == "As"

    game.table.clear_stacked_deck()
    game.start_hand(shuffle_deck=True)
    assert game.table.deck_is_stacked is False
