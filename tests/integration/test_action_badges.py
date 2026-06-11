"""Tests for the seat action badges (UX 2026-06-11).

Each player's action this betting round is recorded in GameSession and surfaced
as `last_action` for a color-coded seat badge, so it's obvious who checked,
called, bet, or raised before your turn — without opening the chat.
"""

from types import SimpleNamespace

from tests.test_helpers import load_rules_from_file

from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from generic_poker.game.game_state import PlayerAction
from online_poker.services.game_orchestrator import GameSession
from online_poker.services.game_state_manager import GameStateManager


def _game() -> Game:
    rules = load_rules_from_file("hold_em")
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=5,
        big_blind=10,
        min_buyin=100,
        max_buyin=5000,
        auto_progress=True,
    )
    game.add_player("p0", "Alice", 1000)
    game.add_player("p1", "Bob", 1000)
    game.start_hand(shuffle_deck=True)
    return game


def _session(game, last_actions=None):
    return SimpleNamespace(game=game, player_last_actions=last_actions or {})


def test_format_action_label():
    f = GameSession._format_action_label
    assert f(PlayerAction.FOLD, 0, False) == "Fold"
    assert f(PlayerAction.CHECK, 0, False) == "Check"
    assert f(PlayerAction.CALL, 10, False) == "Call $10"
    assert f(PlayerAction.BET, 20, False) == "Bet $20"
    assert f(PlayerAction.RAISE, 40, False) == "Raise $40"
    assert f(PlayerAction.RAISE, 200, True) == "All-in $200"
    assert f(PlayerAction.BRING_IN, 3, False) == "Bring-in $3"
    assert f(PlayerAction.DRAW, 0, False) == "Draw"


def test_get_last_action_shows_current_round_action():
    game = _game()
    rnd = game.betting.betting_round
    session = _session(game, {"p1": {"label": "Raise $40", "round": rnd}})
    assert GameStateManager._get_last_action(session, "p1") == "Raise $40"


def test_get_last_action_hidden_after_street_advances():
    game = _game()
    rnd = game.betting.betting_round
    # Record an action for an earlier round than the current one.
    session = _session(game, {"p1": {"label": "Raise $40", "round": rnd - 1}})
    assert GameStateManager._get_last_action(session, "p1") is None


def test_get_last_action_none_when_no_record():
    game = _game()
    session = _session(game, {})
    assert GameStateManager._get_last_action(session, "p1") is None


def test_get_last_action_folded_player_shows_fold():
    game = _game()
    game.table.players["p1"].is_active = False  # folded
    session = _session(game, {})  # even with no recorded action
    assert GameStateManager._get_last_action(session, "p1") == "Fold"


def test_record_and_reset_round_trip():
    """GameSession records the action label and reset clears it."""
    game = _game()
    session = _session(game)
    # Bind the real methods to our lightweight session.
    GameSession._record_player_action(session, "p0", PlayerAction.RAISE, 40, game.betting.betting_round)
    assert session.player_last_actions["p0"]["label"] == "Raise $40"
    GameSession.reset_action_tracking(session)
    assert session.player_last_actions == {}
