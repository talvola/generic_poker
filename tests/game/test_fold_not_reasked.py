"""Regression: a folded player is never asked to act again (UX report 2026-06-11).

A tester reported folding and then being asked to act on a later street. The
engine itself never re-prompts a folded player; this locks that in across
several deterministic deals and multiple fold positions. (The reported symptom
was almost certainly UI/turn-timer pressure, not the engine.)
"""

import pytest

from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction
from tests.test_helpers import load_rules_from_file


def _game(seed: int, num_players: int = 3) -> Game:
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
    game.table.set_deck_seed(seed)
    for i in range(num_players):
        game.add_player(f"p{i}", f"P{i}", 1000)
    return game


@pytest.mark.parametrize("seed", [1, 2, 3, 7, 42])
def test_folded_player_never_asked_again(seed):
    game = _game(seed, num_players=3)
    game.start_hand(shuffle_deck=True)

    folded: set[str] = set()
    guard = 0
    while game.state != GameState.COMPLETE and guard < 200:
        guard += 1
        if game.state in (GameState.BETTING, GameState.DRAWING):
            if game.current_player is None:
                game._next_step()
                continue
            pid = game.current_player.id
            # The engine must never set a folded player as the one to act.
            assert pid not in folded, f"folded player {pid} was asked to act again (seed {seed})"
            valid = {a[0]: a for a in game.get_valid_actions(pid)}
            # First player to act folds; everyone else checks/calls to keep the hand going.
            if not folded and PlayerAction.FOLD in valid:
                game.player_action(pid, PlayerAction.FOLD, 0)
                folded.add(pid)
            elif PlayerAction.CHECK in valid:
                game.player_action(pid, PlayerAction.CHECK, 0)
            elif PlayerAction.CALL in valid:
                game.player_action(pid, PlayerAction.CALL, valid[PlayerAction.CALL][1])
            else:
                action, lo, _hi = game.get_valid_actions(pid)[0]
                game.player_action(pid, action, lo or 0)
        else:
            game._next_step()

    assert folded, "test should have folded a player"
    assert game.state == GameState.COMPLETE
