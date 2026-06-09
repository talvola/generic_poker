#!/usr/bin/env python
"""Offline bot arena: pit bot types against each other over many hands.

Drives the core engine directly (no web server, no DB). Stacks reset every
hand so results are a clean sum of per-hand chip deltas.

Usage:
    python tools/bot_arena.py                                  # MC vs Simple, 200 hands of hold'em
    python tools/bot_arena.py --variant omaha_8 --hands 500
    python tools/bot_arena.py --bots mc,simple,simple --structure Limit
    python tools/bot_arena.py --variant 7_card_stud --structure Limit --seed 42
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging

from generic_poker.config.loader import BettingStructure, GameActionType, GameRules
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState
from online_poker.services.monte_carlo_bot import MonteCarloBot
from online_poker.services.simple_bot import SimpleBot

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "game_configs")
START_STACK = 200
MAX_ACTIONS_PER_HAND = 500


def make_bot(bot_type: str, player_id: str, name: str, seed: int | None, time_budget_ms: int):
    if bot_type == "mc":
        return MonteCarloBot(player_id, name, time_budget_ms=time_budget_ms, seed=seed)
    return SimpleBot(player_id, name)


def advance_non_player_steps(game):
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


def play_hand(game, bots) -> bool:
    """Play one hand to completion. Returns False if the hand stalled."""
    game.start_hand(shuffle_deck=True)
    advance_non_player_steps(game)

    for _ in range(MAX_ACTIONS_PER_HAND):
        if game.state == GameState.COMPLETE:
            return True
        player = game.current_player
        if player is None:
            advance_non_player_steps(game)
            if game.current_player is None and game.state != GameState.COMPLETE:
                return False
            continue

        bot = bots[player.id]
        valid_actions = game.get_valid_actions(player.id)
        if not valid_actions:
            return False
        decision = bot.choose_action_full(valid_actions, game, player.id)
        result = game.player_action(
            player.id,
            decision.action,
            decision.amount or 0,
            cards=decision.cards,
            declaration_data=decision.declaration_data,
        )
        if not result.success:
            print(f"  ! action rejected for {bot.username}: {result.error}")
            return False
        if result.advance_step and game.state != GameState.COMPLETE:
            game._next_step()
            advance_non_player_steps(game)
    return game.state == GameState.COMPLETE


def main():
    parser = argparse.ArgumentParser(description="Pit bot types against each other offline.")
    parser.add_argument("--variant", default="hold_em", help="Game config name (default: hold_em)")
    parser.add_argument("--hands", type=int, default=200, help="Number of hands (default: 200)")
    parser.add_argument("--bots", default="mc,simple", help="Comma-separated bot types to seat, e.g. mc,simple,simple")
    parser.add_argument("--structure", default="No Limit", help='Betting structure: "No Limit", "Pot Limit", "Limit"')
    parser.add_argument("--seed", type=int, default=None, help="Seed for MC bots (reproducibility)")
    parser.add_argument("--budget-ms", type=int, default=300, help="MC time budget per decision (default: 300)")
    parser.add_argument("--verbose", action="store_true", help="Enable engine/bot logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.CRITICAL)

    bot_types = [b.strip() for b in args.bots.split(",") if b.strip()]
    if len(bot_types) < 2:
        parser.error("need at least 2 bots")

    rules = GameRules.from_file(os.path.join(CONFIG_DIR, f"{args.variant}.json"))
    game = Game(
        rules,
        structure=BettingStructure(args.structure),
        small_blind=1,
        big_blind=2,
        small_bet=2,
        big_bet=4,
        bring_in=1,
        ante=1,
        auto_progress=False,
    )

    bots = {}
    profits = {}
    for i, bot_type in enumerate(bot_types):
        pid = f"bot_{i}"
        name = f"{bot_type.upper()}-{i}"
        bots[pid] = make_bot(bot_type, pid, name, args.seed, args.budget_ms)
        profits[pid] = 0
        game.add_player(pid, name, START_STACK)

    print(f"Arena: {args.variant} ({args.structure}), {args.hands} hands, bots: {', '.join(bot_types)}")
    started = time.monotonic()
    completed = stalled = 0

    for hand_num in range(1, args.hands + 1):
        for player in game.table.players.values():
            player.stack = START_STACK
        game.table.move_button()
        if play_hand(game, bots):
            completed += 1
            for pid, player in game.table.players.items():
                profits[pid] += player.stack - START_STACK
        else:
            stalled += 1
        if hand_num % 50 == 0:
            print(f"  {hand_num} hands... " + "  ".join(f"{bots[p].username}: {profits[p]:+d}" for p in profits))

    elapsed = time.monotonic() - started
    print(
        f"\nDone: {completed} hands completed, {stalled} stalled, {elapsed:.1f}s "
        f"({elapsed / max(1, completed) * 1000:.0f}ms/hand)"
    )
    print(f"{'Bot':<12} {'Profit':>8} {'BB/100':>8}")
    for pid in profits:
        bb100 = profits[pid] / 2 / max(1, completed) * 100  # big blind = 2
        print(f"{bots[pid].username:<12} {profits[pid]:>+8d} {bb100:>+8.1f}")


if __name__ == "__main__":
    main()
