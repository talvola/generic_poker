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
from generic_poker.core.card import Card

# ── Config Discovery ──────────────────────────────────────────────────────────

CONFIGS_DIR = Path(__file__).parents[2] / "data" / "game_configs"

# Games that use unimplemented actions (expose, pass, declare, separate, choose)
# These are expected to fail until those features are implemented.
UNSUPPORTED_GAMES = {
    "3_hand_hold_em", "3_hand_hold_em_8",
    "5_card_shodugi", "6_card_shodugi",
    "7_card_flip", "7_card_flip_8",
    "7_card_stud_hilo_declare",
    "cowpie", "crazy_sohe",
    "double_hold_em",
    "italian_poker",
    "kentrel",
    "lazy_sohe",
    "mexican_poker",
    "paradise_road_pickem",
    "pass_the_pineapple",
    "sheshe",
    "showmaha", "showmaha_8",
    "sohe", "sohe_311",
    "straight_7card_declare", "straight_9card_declare", "straight_declare",
    "studaha",
    "tahoe_pitch_roll",
}

# Games that have known engine bugs (evaluation errors, showdown crashes, etc.)
# These should be fixed eventually. Marked xfail so the test suite stays green.
KNOWN_ENGINE_BUGS = {
    # Showdown TypeError: int + list in showdown_manager.py:1645
    "2_or_5_omaha_8": "showdown int+list TypeError",
    "2_or_5_omaha_8_with_draw": "showdown int+list TypeError",
    # ValueError: evaluation requires exactly N cards
    "canadian_stud": "soko_high evaluation requires exactly 5 cards",
    "london_lowball": "a6_low evaluation requires exactly 5 cards",
    "razzaho": "a5_low evaluation requires exactly 5 cards",
    "razzbadeucey": "badugi_ah evaluation requires exactly 4 cards",
    "super_razzbadeucey": "badugi_ah evaluation requires exactly 4 cards",
    # AttributeError: NoneType has no attribute 'cards' in showdown_manager.py:1472
    "omaha_321_hi_hi": "showdown NoneType.cards AttributeError",
    # Drawing phase stuck — DRAW action returns no valid actions
    "one_mans_trash": "drawing phase stuck (complex draw logic)",
    # Chip conservation failures (non-deterministic, depends on dealt cards)
    "stampler": "chip conservation failure (ante handling bug)",
    "stumpler": "chip conservation failure (ante handling bug)",
    "5_card_stampler": "chip conservation failure (ante handling bug)",
    "6_card_stampler": "chip conservation failure (ante handling bug)",
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

            action_map = {a[0]: (a[1], a[2]) for a in valid}

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
