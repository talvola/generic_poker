"""Validation pipeline for user-authored custom variants (Phase 9.5).

Pure functions over a candidate game-config dict — no DB, no websockets, no
Flask context. Four stages, fail-fast between them:

  0. precheck — shape, size, name
  1. schema   — jsonschema against data/schemas/game.json
  2. engine   — GameRules.from_json (loader + gameplay-sequence validation)
  3. platform — online-platform unsupported-action gate
  4. smoke    — play seeded hands in-memory with SimpleBots per betting structure

A config that passes all stages is safe to store and to build a live table from.
"""

import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path

from generic_poker.config.loader import GameActionType, GameRules
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState

logger = logging.getLogger(__name__)

MAX_CONFIG_BYTES = 64 * 1024
MAX_NAME_LEN = 60  # mirrors CustomVariant.display_name column width
MAX_ACTIONS_PER_HAND = 500
# Generous: first validation of an exotic eval type may pay a one-time
# ranking-table load; a genuinely stuck hand still trips MAX_ACTIONS_PER_HAND.
SMOKE_TIME_BUDGET_S = 15.0
SMOKE_START_STACK = 200

_SCHEMA_PATH = Path("data/schemas/game.json")
_schema_validator = None


@dataclass
class ValidationIssue:
    stage: str  # "precheck" | "schema" | "engine" | "platform" | "smoke"
    message: str
    json_path: str | None = None

    def to_dict(self) -> dict:
        return {"stage": self.stage, "message": self.message, "json_path": self.json_path}


def _get_schema_validator():
    """Lazily build (and cache) the Draft-07 validator for the game schema."""
    global _schema_validator
    if _schema_validator is None:
        from jsonschema import Draft7Validator

        with open(_SCHEMA_PATH) as f:
            _schema_validator = Draft7Validator(json.load(f))
    return _schema_validator


def validate_custom_variant(
    config: dict, *, run_smoke: bool = True, smoke_hands: int = 2, seed: int = 4242
) -> tuple[bool, list[ValidationIssue], list[str]]:
    """Run the full authoring pipeline over a candidate config.

    Returns (ok, errors, warnings). ``errors`` is empty iff ``ok``.
    ``run_smoke=False`` skips stage 4 (used for keystroke-time editor feedback).
    """
    warnings: list[str] = []

    # Stage 0 — prechecks
    if not isinstance(config, dict):
        return False, [ValidationIssue("precheck", "Config must be a JSON object")], warnings
    try:
        size = len(json.dumps(config))
    except (TypeError, ValueError) as e:
        return False, [ValidationIssue("precheck", f"Config is not JSON-serializable: {e}")], warnings
    if size > MAX_CONFIG_BYTES:
        return (
            False,
            [ValidationIssue("precheck", f"Config too large ({size} bytes, max {MAX_CONFIG_BYTES})")],
            warnings,
        )
    name = config.get("game")
    if not isinstance(name, str) or not name.strip():
        return False, [ValidationIssue("precheck", "Config needs a non-empty 'game' name", "game")], warnings
    if len(name.strip()) > MAX_NAME_LEN:
        return (
            False,
            [ValidationIssue("precheck", f"'game' name too long (max {MAX_NAME_LEN} chars)", "game")],
            warnings,
        )

    # Stage 1 — JSON schema
    schema_errors = []
    for err in _get_schema_validator().iter_errors(config):
        path = "/".join(str(p) for p in err.absolute_path) or None
        schema_errors.append(ValidationIssue("schema", err.message, path))
        if len(schema_errors) >= 20:
            schema_errors.append(ValidationIssue("schema", "(further schema errors truncated)"))
            break
    if schema_errors:
        return False, schema_errors, warnings

    # Stage 2 — engine load + internal validation
    try:
        rules = GameRules.from_json(json.dumps(config))
    except Exception as e:
        return False, [ValidationIssue("engine", str(e))], warnings

    # Stage 3 — online-platform gate
    from .table_manager import TableManager

    unsupported = TableManager.find_unsupported_action(rules)
    if unsupported is not None:
        return (
            False,
            [ValidationIssue("platform", f"Action '{unsupported.name.lower()}' is not supported for online play yet")],
            warnings,
        )

    if not config.get("category"):
        warnings.append("No 'category' set — the variant will list under 'Other'")

    # Stage 4 — smoke-play
    if run_smoke:
        smoke_issue = _smoke_play(rules, smoke_hands=smoke_hands, seed=seed, warnings=warnings)
        if smoke_issue:
            return False, [smoke_issue], warnings

    return True, [], warnings


def _smoke_play(rules: GameRules, *, smoke_hands: int, seed: int, warnings: list[str]) -> ValidationIssue | None:
    """Play seeded in-memory hands with SimpleBots for every declared structure.

    Loop modeled on tools/bot_arena.py. Returns a ValidationIssue on the first
    failure, None if every hand completes. NOTE: never call game._next_step()
    once state is COMPLETE (double-awards the pot).
    """
    from .simple_bot import SimpleBot

    num_players = min(rules.max_players, max(3, rules.min_players))
    if num_players < rules.min_players:
        num_players = rules.min_players
    deadline = time.monotonic() + SMOKE_TIME_BUDGET_S

    # The deck is seeded below, but SimpleBot decisions use the global RNG —
    # seed it too (and restore afterwards) so validation is fully deterministic.
    rng_state = random.getstate()
    random.seed(seed)
    try:
        return _smoke_play_seeded(rules, SimpleBot, num_players, smoke_hands, seed, deadline)
    finally:
        random.setstate(rng_state)


def _smoke_play_seeded(
    rules: GameRules, SimpleBot, num_players: int, smoke_hands: int, seed: int, deadline: float
) -> ValidationIssue | None:
    for structure in rules.betting_structures:
        try:
            game = Game(
                rules,
                structure=structure,
                small_blind=1,
                big_blind=2,
                small_bet=2,
                big_bet=4,
                bring_in=1,
                ante=1,
                auto_progress=False,
            )
            bots = {}
            for i in range(num_players):
                pid = f"smoke_bot_{i}"
                bots[pid] = SimpleBot(pid, f"Smoke-{i}")
                game.add_player(pid, f"Smoke-{i}", SMOKE_START_STACK)
        except Exception as e:
            return ValidationIssue("smoke", f"[{structure.value}] failed to set up game: {e}")

        for hand_num in range(1, smoke_hands + 1):
            for player in game.table.players.values():
                player.stack = SMOKE_START_STACK
            game.table.set_deck_seed(seed + hand_num)
            try:
                ok = _play_one_hand(game, bots, deadline)
            except Exception as e:
                logger.debug("Smoke-play exception", exc_info=True)
                return ValidationIssue("smoke", f"[{structure.value}] hand {hand_num} crashed: {e}")
            if ok is not True:
                return ValidationIssue("smoke", f"[{structure.value}] hand {hand_num} {ok}")
            game.table.move_button()

    return None


def _play_one_hand(game: Game, bots: dict, deadline: float):
    """Play one hand to completion. Returns True, or a failure-description string."""
    game.start_hand(shuffle_deck=True)
    _advance_non_player_steps(game)

    for _ in range(MAX_ACTIONS_PER_HAND):
        if time.monotonic() > deadline:
            return "exceeded the validation time budget"
        if game.state == GameState.COMPLETE:
            return True
        player = game.current_player
        if player is None:
            _advance_non_player_steps(game)
            if game.current_player is None and game.state != GameState.COMPLETE:
                return "stalled (no current player and hand not complete)"
            continue

        bot = bots[player.id]
        valid_actions = game.get_valid_actions(player.id)
        if not valid_actions:
            return f"stalled (no valid actions for {player.id})"
        decision = bot.choose_action_full(valid_actions, game, player.id)
        result = game.player_action(
            player.id,
            decision.action,
            decision.amount or 0,
            cards=decision.cards,
            declaration_data=decision.declaration_data,
        )
        if not result.success:
            return f"bot action rejected: {result.error}"
        if result.advance_step and game.state != GameState.COMPLETE:
            game._next_step()
            _advance_non_player_steps(game)
    if game.state == GameState.COMPLETE:
        return True
    return f"did not complete within {MAX_ACTIONS_PER_HAND} actions"


def _advance_non_player_steps(game: Game) -> None:
    while game.state != GameState.COMPLETE:
        if game.current_step >= len(game.rules.gameplay):
            break
        if game.state == GameState.DEALING:
            step = game.rules.gameplay[game.current_step]
            if step.action_type == GameActionType.CHOOSE and game.current_player is not None:
                break
            game._next_step()
        elif game.state == GameState.BETTING and game.current_player is None:
            game._next_step()
        else:
            break


__all__ = ["ValidationIssue", "validate_custom_variant"]
