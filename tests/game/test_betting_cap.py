"""Tests for table-level betting caps (BACKLOG 6.2.13).

Two distinct conventions:

* Limit raise cap (per betting round): a bet + N raises, unlimited heads-up.
  Already enforced by default; here we test the per-table override
  (`max_raises_override`, `unlimited_raises`).
* Per-hand money cap ("cap game", mainly NL/PL): a player may contribute at most
  `hand_cap` chips across a whole hand; once reached they are all-in for the cap
  but keep their uncommitted chips. Enforced via `BettingManager.effective_stack`.
"""

import random

from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction
from tests.test_helpers import load_rules_from_file


def _nl_game(num_players=2, stack=1000, hand_cap=0):
    rules = load_rules_from_file("hold_em")
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=5,
        big_blind=10,
        min_buyin=100,
        max_buyin=5000,
        auto_progress=True,
        hand_cap=hand_cap,
    )
    for i in range(num_players):
        game.add_player(f"p{i}", f"Player{i}", stack)
    return game


def _limit_game(num_players=3, stack=1000, max_raises_override=None, unlimited_raises=False):
    rules = load_rules_from_file("hold_em")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=5000,
        auto_progress=True,
        max_raises_override=max_raises_override,
        unlimited_raises=unlimited_raises,
    )
    for i in range(num_players):
        game.add_player(f"p{i}", f"Player{i}", stack)
    return game


def _total_chips(game):
    return sum(p.stack for p in game.table.players.values()) + game.betting.get_total_pot()


def _run_out(game, max_actions=300):
    """Play to completion: passive check/call, advancing the board on all-ins."""
    actions = 0
    while game.state != GameState.COMPLETE and actions < max_actions:
        actions += 1
        if game.state in (GameState.BETTING, GameState.DRAWING):
            if game.current_player is None:
                game._next_step()  # everyone all-in: run out the board
                continue
            pid = game.current_player.id
            valid = {a[0]: a for a in game.get_valid_actions(pid)}
            for pref in (PlayerAction.CHECK, PlayerAction.CALL):
                if pref in valid:
                    res = game.player_action(pid, pref, valid[pref][1] or 0)
                    break
            else:
                action, lo, _hi = game.get_valid_actions(pid)[0]
                res = game.player_action(pid, action, lo or 0)
            if res and res.advance_step:
                game._next_step()
        else:
            game._next_step()


# --- Per-hand money cap ---


def test_effective_stack_math():
    game = _nl_game(hand_cap=100)
    game.betting.hand_contributed["p0"] = 30
    assert game.betting.effective_stack("p0", 1000) == 70  # cap - contributed
    assert game.betting.effective_stack("p0", 50) == 50  # real stack is smaller
    game.betting.hand_contributed["p0"] = 100
    assert game.betting.effective_stack("p0", 1000) == 0  # capped out


def test_no_cap_returns_real_stack():
    """With no cap, effective_stack is the real stack (regression safety)."""
    game = _nl_game(hand_cap=0)
    assert game.betting.effective_stack("p0", 1000) == 1000


def test_money_cap_clamps_max_raise():
    game = _nl_game(num_players=2, stack=1000, hand_cap=100)
    game.start_hand(shuffle_deck=True)
    pid = game.current_player.id
    raises = [a for a in game.get_valid_actions(pid) if a[0] == PlayerAction.RAISE]
    assert raises, "a raise should be available"
    # Max raise is the cap (100 total), not the 1000-chip stack.
    assert raises[0][2] == 100


def test_money_cap_all_in_retains_chips_and_conserves():
    game = _nl_game(num_players=2, stack=1000, hand_cap=100)
    before = _total_chips(game)
    game.start_hand(shuffle_deck=True)
    pid = game.current_player.id
    game.player_action(pid, PlayerAction.RAISE, 100)  # shove to the cap
    other = "p1" if pid == "p0" else "p0"
    game.player_action(other, PlayerAction.CALL, 100)
    _run_out(game)

    assert game.state == GameState.COMPLETE
    assert _total_chips(game) == before  # chip conservation
    # Neither player lost more than the cap; the loser kept stack - cap.
    for p in game.table.players.values():
        assert 1000 - p.stack <= 100


def test_money_cap_conservation_three_handed_with_short_stack():
    """A short real stack and a cap coexist; chips are conserved, cap respected."""
    game = _nl_game(num_players=3, stack=1000, hand_cap=120)
    # Make one player short so a genuine side pot can form below the cap.
    game.table.players["p2"].stack = 40
    before = _total_chips(game)
    game.start_hand(shuffle_deck=True)
    _run_out(game)
    assert game.state == GameState.COMPLETE
    assert _total_chips(game) == before
    for pid, p in game.table.players.items():
        start = 40 if pid == "p2" else 1000
        assert start - p.stack <= min(120, start)


# --- Limit raise cap configuration ---


def _raise_until_capped(game, max_attempts=12):
    """Preflop: keep raising with whoever is to act; return the number of raises made."""
    raises = 0
    for _ in range(max_attempts):
        if game.state != GameState.BETTING or game.current_player is None:
            break
        pid = game.current_player.id
        opts = {a[0]: a for a in game.get_valid_actions(pid)}
        if PlayerAction.RAISE in opts:
            game.player_action(pid, PlayerAction.RAISE, opts[PlayerAction.RAISE][1])
            raises += 1
        elif PlayerAction.CALL in opts:
            # No raise offered (capped) — verify and stop.
            break
    return raises


def test_default_limit_raise_cap_is_three():
    game = _limit_game(num_players=3)
    assert game.betting.max_raises == 3
    game.start_hand(shuffle_deck=True)
    _raise_until_capped(game)
    # After bet + 3 raises with 3 live players, raises are capped.
    assert game.betting.is_raise_capped()
    pid = game.current_player.id
    assert PlayerAction.RAISE not in {a[0] for a in game.get_valid_actions(pid)}


def test_limit_raise_cap_override():
    game = _limit_game(num_players=3, max_raises_override=5)
    assert game.betting.max_raises == 5
    game.start_hand(shuffle_deck=True)
    made = _raise_until_capped(game)
    # The cap now allows more raises than the default 3.
    assert made >= 4
    assert game.betting.is_raise_capped()


def test_unlimited_raises():
    game = _limit_game(num_players=3, unlimited_raises=True)
    assert game.betting.raise_cap_enabled is False
    game.start_hand(shuffle_deck=True)
    made = _raise_until_capped(game, max_attempts=10)
    # Never capped — stops only because chips/attempts run out, not a cap.
    assert game.betting.is_raise_capped() is False
    assert made >= 6


# --- Randomized chip-conservation stress for the money cap ---


def _drive_random_hand(game, rng, max_steps=400):
    """Play a started hand to completion with clean random actions.

    Uses only legal min-raise / all-in totals (not arbitrary in-range amounts),
    and never advances a hand that already reached COMPLETE (that footgun
    double-awards the pot — see CLAUDE.md).
    """
    steps = 0
    while game.state != GameState.COMPLETE and steps < max_steps:
        steps += 1
        if game.state in (GameState.BETTING, GameState.DRAWING):
            if game.current_player is None:
                game._next_step()
                continue
            pid = game.current_player.id
            action, lo, hi = rng.choice(game.get_valid_actions(pid))
            if action in (PlayerAction.FOLD, PlayerAction.CHECK):
                amount = 0
            elif hi is None:
                amount = lo or 0
            else:
                amount = hi if rng.random() < 0.5 else lo  # all-in or min-raise
            res = game.player_action(pid, action, amount)
            if res and res.advance_step and game.state != GameState.COMPLETE:
                game._next_step()
        else:
            game._next_step()


def test_money_cap_conserves_chips_under_random_play():
    """60 three-handed NL hands of aggressive random play conserve chips and respect the cap."""
    rng = random.Random(20260610)
    for hand in range(60):
        game = _nl_game(num_players=3, stack=1000, hand_cap=150)
        before = _total_chips(game)
        game.start_hand(shuffle_deck=True)
        _drive_random_hand(game, rng)
        assert game.state == GameState.COMPLETE, f"hand {hand} did not complete"
        assert _total_chips(game) == before, f"chip leak in hand {hand}"
        for p in game.table.players.values():
            assert 1000 - p.stack <= 150, f"player exceeded the cap in hand {hand}"
