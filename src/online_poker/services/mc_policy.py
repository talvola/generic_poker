"""Equity → betting action mapping for the Monte Carlo bot.

Amounts in valid-action tuples are TOTALS (the player's total bet after the
action), so they are used directly for BotDecision.amount. Pot-odds math uses
the incremental call cost passed in by the caller.
"""

import logging
from random import Random

from generic_poker.game.game_state import PlayerAction

from .simple_bot import BotDecision

logger = logging.getLogger(__name__)

BETTING_ACTIONS = {
    PlayerAction.FOLD,
    PlayerAction.CHECK,
    PlayerAction.CALL,
    PlayerAction.BET,
    PlayerAction.RAISE,
    PlayerAction.BRING_IN,
    PlayerAction.COMPLETE,
}

# Equity margin over pot odds below which we fold (slack for MC noise).
FOLD_MARGIN = -0.05
# Equity margin over pot odds above which we raise for value.
VALUE_MARGIN = 0.15
# Equity needed to bet when checking is free.
BET_THRESHOLD = 0.55
# Per-extra-opponent tightening: naive uniform-random opponent ranges
# overestimate multiway equity, so demand more as the field grows.
MULTIWAY_TIGHTEN = 0.03
# Baseline bluff frequency when folding is indicated (scaled by aggression).
BLUFF_FREQUENCY = 0.05


def decide(
    equity: float,
    valid_actions: list[tuple],
    pot: int,
    call_cost: int,
    players_in_hand: int,
    rng: Random,
    aggression: float = 1.0,
) -> BotDecision:
    """Map an equity estimate to a betting BotDecision."""
    options = {}
    for action_tuple in valid_actions:
        options.setdefault(action_tuple[0], action_tuple)

    tighten = MULTIWAY_TIGHTEN * max(0, players_in_hand - 2)

    # Stud third street: forced choice between bring-in and completing.
    if PlayerAction.BRING_IN in options:
        if PlayerAction.COMPLETE in options and equity > BET_THRESHOLD + tighten:
            return _sized_bet(options[PlayerAction.COMPLETE], equity, pot, rng, aggression)
        return BotDecision(action=PlayerAction.BRING_IN, amount=options[PlayerAction.BRING_IN][1])

    raise_option = (
        options.get(PlayerAction.RAISE) or options.get(PlayerAction.BET) or options.get(PlayerAction.COMPLETE)
    )

    if PlayerAction.CHECK in options:
        # Free option — never fold.
        if raise_option is not None and equity > BET_THRESHOLD + tighten:
            return _sized_bet(raise_option, equity, pot, rng, aggression)
        return BotDecision(action=PlayerAction.CHECK)

    pot_odds = call_cost / (pot + call_cost) if call_cost > 0 else 0.0
    margin = equity - pot_odds - tighten

    if margin < FOLD_MARGIN:
        if raise_option is not None and rng.random() < BLUFF_FREQUENCY * aggression:
            return _sized_bet(raise_option, equity, pot, rng, aggression)
        if PlayerAction.FOLD in options:
            return BotDecision(action=PlayerAction.FOLD)

    if margin > VALUE_MARGIN and raise_option is not None and rng.random() < min(1.0, 0.7 * aggression):
        return _sized_bet(raise_option, equity, pot, rng, aggression)

    if PlayerAction.CALL in options:
        return BotDecision(action=PlayerAction.CALL, amount=options[PlayerAction.CALL][1])
    if raise_option is not None:
        # All-in-or-fold spots: no call option but positive margin to continue.
        return _sized_bet(raise_option, equity, pot, rng, aggression)
    if PlayerAction.FOLD in options:
        return BotDecision(action=PlayerAction.FOLD)
    first = valid_actions[0]
    return BotDecision(action=first[0], amount=first[1] if len(first) > 1 else None)


def _sized_bet(action_tuple: tuple, equity: float, pot: int, rng: Random, aggression: float) -> BotDecision:
    """Pick a bet/raise amount within [min, max] scaled by equity strength.

    Limit games have min == max so this collapses to the fixed bet. For NL/PL,
    size toward (pot-sized + jitter) as equity grows; amounts are totals.
    """
    action = action_tuple[0]
    min_amount = action_tuple[1] if len(action_tuple) > 1 else None
    max_amount = action_tuple[2] if len(action_tuple) > 2 else None
    if min_amount is None:
        return BotDecision(action=action)
    if max_amount is None or max_amount <= min_amount:
        return BotDecision(action=action, amount=min_amount)

    # Strength 0 at the bet threshold, 1.0 at ~90%+ equity.
    strength = max(0.0, min(1.0, (equity - 0.5) / 0.4)) * min(1.5, aggression)
    jitter = rng.uniform(0.7, 1.1)
    # Target a fraction of pot on top of the minimum, capped by max.
    target = min_amount + int(pot * strength * jitter)
    amount = max(min_amount, min(max_amount, target))
    return BotDecision(action=action, amount=amount)
