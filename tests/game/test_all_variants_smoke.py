"""Parametrized smoke test for all 192 game variants.

Loads each game config, creates a game with minimum players,
and plays a hand to completion (everyone checks/calls/stands pat).
Catches crashes, infinite loops, and missing implementations.
"""

import pytest
from pathlib import Path
from typing import List

from generic_poker.config.loader import GameRules, BettingStructure
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Visibility

# ── Config Discovery ──────────────────────────────────────────────────────────

CONFIGS_DIR = Path(__file__).parents[2] / "data" / "game_configs"

# Games that use unimplemented actions — now empty, all 192 supported
UNSUPPORTED_GAMES = set()

# Games that have known engine bugs (evaluation errors, showdown crashes, etc.)
# These should be fixed eventually. Marked xfail so the test suite stays green.
# All 13 previously-buggy games fixed as of 2026-02-17.
KNOWN_ENGINE_BUGS = {
}


def get_all_config_files():
    """Return list of (basename, path) tuples for all game configs."""
    configs = []
    for f in sorted(CONFIGS_DIR.glob("*.json")):
        basename = f.stem
        configs.append(pytest.param(basename, f, id=basename))
    return configs


def get_supported_config_files():
    """Return configs excluding unsupported and known-buggy games."""
    all_configs = get_all_config_files()
    result = []
    for p in all_configs:
        name = p.values[0]
        if name in UNSUPPORTED_GAMES:
            continue
        if name in KNOWN_ENGINE_BUGS:
            result.append(pytest.param(
                *p.values, id=name,
                marks=pytest.mark.xfail(reason=KNOWN_ENGINE_BUGS[name], strict=False)
            ))
        else:
            result.append(p)
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_smoke_game(rules: GameRules) -> Game:
    """Create a game with minimum players and reasonable betting params."""
    structure = rules.betting_structures[0]

    kwargs = dict(
        rules=rules,
        structure=structure,
        min_buyin=20,
        max_buyin=10000,
        auto_progress=False,
    )

    if structure == BettingStructure.LIMIT:
        kwargs["small_bet"] = 10
        kwargs["big_bet"] = 20
    else:
        kwargs["small_blind"] = 5
        kwargs["big_blind"] = 10

    # Bring-in games need bring_in and ante params
    if rules.forced_bets.style == "bring-in":
        kwargs["bring_in"] = 5
        kwargs["ante"] = 2
        # Bring-in games using Limit also need small_bet/big_bet
        if structure == BettingStructure.LIMIT:
            kwargs["small_bet"] = 10
            kwargs["big_bet"] = 20

    game = Game(**kwargs)

    for i in range(rules.min_players):
        game.add_player(f"p{i}", f"Player{i}", 500)

    return game


def _take_action(game: Game, player_id: str, action: PlayerAction,
                  amount=None, cards=None):
    """Take an action and advance if the round completes."""
    kwargs = {}
    if amount is not None:
        kwargs['amount'] = amount
    if cards is not None:
        kwargs['cards'] = cards
    result = game.player_action(player_id, action, **kwargs)
    if result and result.advance_step:
        game._next_step()
    return result


def play_hand_passively(game: Game, max_actions: int = 500) -> int:
    """Play through a hand with all players checking/calling/standing pat.

    Args:
        game: Game instance with players added, hand not yet started.
        max_actions: Safety limit to prevent infinite loops.
    Returns:
        Number of actions/steps taken.
    """
    game.start_hand(shuffle_deck=True)
    actions_taken = 0

    while game.state != GameState.COMPLETE and actions_taken < max_actions:
        # Handle CHOOSE action in DEALING state (needs player input)
        if game.state == GameState.DEALING and game.current_player is not None:
            player_id = game.current_player.id
            valid = game.get_valid_actions(player_id)
            if valid:
                action_map = {a[0]: (a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else None) for a in valid}
                if PlayerAction.CHOOSE in action_map:
                    _take_action(game, player_id, PlayerAction.CHOOSE, amount=0)
                    actions_taken += 1
                    continue

        if game.state in (GameState.BETTING, GameState.DRAWING):
            if game.current_player is None:
                game._next_step()
                actions_taken += 1
                continue

            player_id = game.current_player.id
            valid = game.get_valid_actions(player_id)

            if not valid:
                game._next_step()
                actions_taken += 1
                continue

            action_map = {a[0]: (a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else None) for a in valid}

            if game.state == GameState.DRAWING:
                # Stand pat when possible, otherwise discard the minimum required
                if PlayerAction.DRAW in action_map:
                    min_draw, _ = action_map[PlayerAction.DRAW]
                    hand_cards = list(game.table.players[player_id].hand.cards)
                    discard = hand_cards[:min_draw] if min_draw else []
                    _take_action(game, player_id, PlayerAction.DRAW, amount=min_draw, cards=discard)
                elif PlayerAction.DISCARD in action_map:
                    min_disc, _ = action_map[PlayerAction.DISCARD]
                    hand_cards = list(game.table.players[player_id].hand.cards)
                    discard = hand_cards[:min_disc] if min_disc else []
                    _take_action(game, player_id, PlayerAction.DISCARD, amount=min_disc, cards=discard)
                elif PlayerAction.REPLACE_COMMUNITY in action_map:
                    num_replace, _ = action_map[PlayerAction.REPLACE_COMMUNITY]
                    # Pick community cards to replace
                    all_community = []
                    for subset_cards in game.table.community_cards.values():
                        all_community.extend(subset_cards)
                    to_replace = all_community[:num_replace]
                    _take_action(game, player_id, PlayerAction.REPLACE_COMMUNITY,
                                 amount=num_replace, cards=to_replace)
                elif PlayerAction.PASS in action_map:
                    num_pass, _ = action_map[PlayerAction.PASS]
                    hand_cards = list(game.table.players[player_id].hand.cards)
                    to_pass = hand_cards[:num_pass]
                    _take_action(game, player_id, PlayerAction.PASS, cards=to_pass)
                elif PlayerAction.EXPOSE in action_map:
                    min_expose, max_expose = action_map[PlayerAction.EXPOSE]
                    hand_cards = list(game.table.players[player_id].hand.cards)
                    # Select face-down cards to expose
                    face_down = [c for c in hand_cards if c.visibility == Visibility.FACE_DOWN]
                    to_expose = face_down[:max_expose]
                    # If min is 0 and no face-down cards, expose nothing
                    if len(to_expose) < min_expose:
                        to_expose = face_down[:min_expose] if face_down else []
                    _take_action(game, player_id, PlayerAction.EXPOSE, cards=to_expose)
                elif PlayerAction.SEPARATE in action_map:
                    total, _ = action_map[PlayerAction.SEPARATE]
                    hand_cards = list(game.table.players[player_id].hand.cards)
                    # Just assign cards in order to satisfy the total count
                    _take_action(game, player_id, PlayerAction.SEPARATE, cards=hand_cards[:total])
                elif PlayerAction.DECLARE in action_map:
                    # Always declare "high"
                    result = game.player_action(
                        player_id, PlayerAction.DECLARE,
                        declaration_data=[{"pot_index": -1, "declaration": "high"}]
                    )
                    if result and result.advance_step:
                        game._next_step()
                elif PlayerAction.CHOOSE in action_map:
                    # Always pick first option (index 0)
                    _take_action(game, player_id, PlayerAction.CHOOSE, amount=0)
                else:
                    action = next(iter(action_map))
                    _take_action(game, player_id, action, amount=0, cards=[])
            else:
                # Betting: prefer check > call > fold
                if PlayerAction.CHECK in action_map:
                    _take_action(game, player_id, PlayerAction.CHECK)
                elif PlayerAction.CALL in action_map:
                    min_amt, _ = action_map[PlayerAction.CALL]
                    _take_action(game, player_id, PlayerAction.CALL, amount=min_amt)
                elif PlayerAction.FOLD in action_map:
                    _take_action(game, player_id, PlayerAction.FOLD)
                elif PlayerAction.BET in action_map:
                    min_amt, _ = action_map[PlayerAction.BET]
                    _take_action(game, player_id, PlayerAction.BET, amount=min_amt)
                elif PlayerAction.COMPLETE in action_map:
                    min_amt, _ = action_map[PlayerAction.COMPLETE]
                    _take_action(game, player_id, PlayerAction.COMPLETE, amount=min_amt)
                else:
                    action, (min_amt, max_amt) = next(iter(action_map.items()))
                    _take_action(game, player_id, action, amount=min_amt or 0)

            actions_taken += 1

        else:
            # DEALING, WAITING, SHOWDOWN, or other — advance
            game._next_step()
            actions_taken += 1

    return actions_taken


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("basename,config_path", get_supported_config_files())
def test_variant_loads_and_plays(basename: str, config_path: Path):
    """Each supported game variant can load, start a hand, and complete it."""
    rules = GameRules.from_file(config_path)

    game = create_smoke_game(rules)
    actions = play_hand_passively(game)

    assert game.state == GameState.COMPLETE, (
        f"{basename}: game did not reach COMPLETE state "
        f"(stuck in {game.state} after {actions} actions, step {game.current_step})"
    )

    # Verify chip conservation
    total_chips = sum(p.stack for p in game.table.players.values())
    expected_chips = 500 * rules.min_players
    assert total_chips == expected_chips, (
        f"{basename}: chip conservation failed — "
        f"expected {expected_chips}, got {total_chips}"
    )


@pytest.mark.parametrize("basename,config_path", get_all_config_files())
def test_variant_config_loads(basename: str, config_path: Path):
    """Every game config can be parsed into GameRules without errors."""
    rules = GameRules.from_file(config_path)
    assert rules.game, f"{basename}: game name is empty"
    assert rules.min_players >= 2, f"{basename}: min_players < 2"
    assert rules.max_players >= rules.min_players
    assert len(rules.gameplay) > 0, f"{basename}: no gameplay steps"
    assert len(rules.betting_structures) > 0, f"{basename}: no betting structures"
