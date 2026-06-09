"""Monte Carlo rollout engine (Phase 1): snapshot a mid-hand game, simulate completions.

Phase 1 supports betting decisions in games whose remaining steps are only
deals and bets — Hold'em, Omaha, stud games, and the post-final-draw betting
rounds of draw games. Anything outside that (pending draws, wild cards,
multi-board layouts, declarations, exotic showdown configs) raises
UnsupportedForRollout and the bot falls back to SimpleBot.

Equity is the bot's expected pot-share fraction: each showdown bestHand config
is worth 1/N of the pot, configs with no qualifying hands redistribute their
share to configs that have winners (mirrors the engine's redistribution rule).
This handles ties, hi-lo splits, and dramaha-style splits uniformly.
"""

import itertools
import logging
import time
from dataclasses import dataclass, field
from random import Random

from generic_poker.config.loader import GameActionType
from generic_poker.core.card import Card, Visibility
from generic_poker.core.deck import Deck
from generic_poker.evaluation.evaluator import EvaluationType, HandEvaluator

logger = logging.getLogger(__name__)

_evaluator = HandEvaluator()

# The full bestHand vocabulary used by the Phase 1 target variants (WSOP mix).
PHASE1_BESTHAND_KEYS = {"name", "evaluationType", "anyCards", "holeCards", "communityCards", "qualifier"}

# Steps a rollout can simulate without a decision policy.
SIMULATABLE_STEPS = {GameActionType.BET, GameActionType.DEAL, GameActionType.SHOWDOWN}


class UnsupportedForRollout(Exception):
    """Game rules or state are outside Phase 1 rollout support."""


@dataclass
class HandConfigSpec:
    """One showdown bestHand entry, reduced to the Phase 1 vocabulary."""

    eval_type: EvaluationType
    any_cards: int | None = None
    hole_cards: int | None = None
    community_cards: int = 0
    qualifier: list[int] | None = None


@dataclass
class RolloutSpec:
    """Flat snapshot of everything a rollout needs. All Card lists are copies."""

    bot_id: str
    bot_cards: list[Card]
    # (player_id, cards known to the bot, count of cards hidden from the bot)
    opponents: list[tuple[str, list[Card], int]]
    community: list[Card]
    player_cards_to_come: int  # per still-in player, bot included
    community_cards_to_come: int
    unseen: list[Card]
    hand_configs: list[HandConfigSpec] = field(default_factory=list)

    @classmethod
    def from_game(cls, game, bot_id: str) -> "RolloutSpec":
        """Build a snapshot from a live Game, or raise UnsupportedForRollout."""
        showdown = game.rules.showdown
        if showdown.declaration_mode not in (None, "cards_speak"):
            raise UnsupportedForRollout("declaration mode")
        if showdown.conditionalBestHands:
            raise UnsupportedForRollout("conditional best hands")
        if not showdown.best_hand:
            raise UnsupportedForRollout("no bestHand configs")

        hand_configs = [_parse_hand_config(cfg) for cfg in showdown.best_hand]

        if any(
            getattr(game, attr, None)
            for attr in ("dynamic_wild_rank", "follow_card_wild_rank", "follow_trigger_pending")
        ) or getattr(game, "player_wild_ranks", None):
            raise UnsupportedForRollout("wild card state active")

        player_to_come, community_to_come = _count_remaining_deals(game)

        bot_player = game.table.players.get(bot_id)
        if bot_player is None:
            raise UnsupportedForRollout("bot not seated")
        bot_cards = [_copy_card(c) for c in bot_player.hand.get_cards()]

        community_subsets = {name: cards for name, cards in game.table.community_cards.items() if cards}
        if set(community_subsets) - {"default"}:
            raise UnsupportedForRollout("multi-board community cards")
        community = [_copy_card(c) for c in community_subsets.get("default", [])]

        seen_keys = {str(c) for c in bot_cards} | {str(c) for c in community}
        if any(c.is_wild for c in bot_cards) or any(c.is_wild for c in community):
            raise UnsupportedForRollout("wild cards in play")

        opponents = []
        for pid, player in game.table.players.items():
            if pid == bot_id or not player.is_active:
                continue
            visible = []
            hidden = 0
            for card in player.hand.get_cards():
                if card.visibility == Visibility.FACE_UP:
                    if card.is_wild:
                        raise UnsupportedForRollout("wild cards in play")
                    visible.append(_copy_card(card))
                    seen_keys.add(str(card))
                else:
                    hidden += 1
            opponents.append((pid, visible, hidden))
        if not opponents:
            raise UnsupportedForRollout("no active opponents")

        # Dead cards: exclude the whole discard pile from the unseen pool. For
        # unknown cards this is equity-neutral (symmetry); for the bot's own
        # past discards it is required for correctness.
        for card in game.table.discard_pile.get_cards():
            seen_keys.add(str(card))

        full_deck = Deck(deck_type=game.table.deck_type).cards
        unseen = [c for c in full_deck if str(c) not in seen_keys]

        needed = sum(h for _, _, h in opponents) + (len(opponents) + 1) * player_to_come + community_to_come
        if len(unseen) < needed:
            raise UnsupportedForRollout("not enough unseen cards to simulate")

        return cls(
            bot_id=bot_id,
            bot_cards=bot_cards,
            opponents=opponents,
            community=community,
            player_cards_to_come=player_to_come,
            community_cards_to_come=community_to_come,
            unseen=unseen,
            hand_configs=hand_configs,
        )


def _copy_card(card: Card) -> Card:
    return Card(card.rank, card.suit, card.visibility)


def _parse_hand_config(cfg: dict) -> HandConfigSpec:
    if set(cfg) - PHASE1_BESTHAND_KEYS:
        raise UnsupportedForRollout(f"bestHand fields beyond Phase 1: {set(cfg) - PHASE1_BESTHAND_KEYS}")
    try:
        eval_type = EvaluationType(cfg["evaluationType"])
    except (KeyError, ValueError) as e:
        raise UnsupportedForRollout(f"evaluation type: {cfg.get('evaluationType')}") from e

    any_cards = cfg.get("anyCards")
    hole_cards = cfg.get("holeCards")
    community_cards = cfg.get("communityCards", 0)
    if any_cards is not None:
        if not isinstance(any_cards, int):
            raise UnsupportedForRollout("non-integer anyCards")
    else:
        if not isinstance(hole_cards, int) or not isinstance(community_cards, int):
            raise UnsupportedForRollout("non-integer holeCards/communityCards")
    return HandConfigSpec(
        eval_type=eval_type,
        any_cards=any_cards,
        hole_cards=hole_cards,
        community_cards=community_cards,
        qualifier=cfg.get("qualifier"),
    )


def _count_remaining_deals(game) -> tuple[int, int]:
    """Count cards still to be dealt per player and to the community.

    Raises UnsupportedForRollout if any remaining pre-showdown step needs a
    decision policy (draw/discard/expose/...) or uses features we can't model.
    """
    player_to_come = 0
    community_to_come = 0
    for step in game.rules.gameplay[game.current_step + 1 :]:
        if step.action_type not in SIMULATABLE_STEPS:
            raise UnsupportedForRollout(f"remaining step: {step.action_type.name}")
        if step.action_type != GameActionType.DEAL:
            continue
        config = step.action_config
        if not isinstance(config, dict) or "conditional_state" in config:
            raise UnsupportedForRollout("conditional deal step")
        location = config.get("location")
        for card_spec in config.get("cards", []):
            number = card_spec.get("number", 0)
            if not isinstance(number, int):
                raise UnsupportedForRollout("non-integer deal count")
            if location == "player":
                player_to_come += number
            elif location == "community":
                if card_spec.get("subset", "default") != "default":
                    raise UnsupportedForRollout("multi-board community deal")
                community_to_come += number
            else:
                raise UnsupportedForRollout(f"deal location: {location}")
    return player_to_come, community_to_come


def run_rollout(spec: RolloutSpec, rng: Random) -> float:
    """Run one rollout; return the bot's pot-share fraction (0.0 - 1.0)."""
    needed = (
        sum(h for _, _, h in spec.opponents)
        + (len(spec.opponents) + 1) * spec.player_cards_to_come
        + spec.community_cards_to_come
    )
    drawn = rng.sample(spec.unseen, needed) if needed else []
    pos = 0

    hands: dict[str, list[Card]] = {}
    for pid, visible, hidden in spec.opponents:
        hands[pid] = visible + drawn[pos : pos + hidden + spec.player_cards_to_come]
        pos += hidden + spec.player_cards_to_come
    hands[spec.bot_id] = spec.bot_cards + drawn[pos : pos + spec.player_cards_to_come]
    pos += spec.player_cards_to_come
    community = spec.community + drawn[pos:]

    config_bests: list[dict[str, tuple[int, int]]] = []
    for cfg in spec.hand_configs:
        bests = {}
        for pid, cards in hands.items():
            rank = _best_hand_rank(cards, community, cfg)
            if rank is not None:
                bests[pid] = rank
        config_bests.append(bests)

    # Each config is worth an equal pot share; configs nobody qualifies for
    # redistribute their share to the configs that do have winners.
    winnable = [bests for bests in config_bests if bests]
    if not winnable:
        return 0.0
    share_per_config = 1.0 / len(winnable)
    bot_share = 0.0
    for bests in winnable:
        best_rank = min(bests.values())
        winners = [pid for pid, rank in bests.items() if rank == best_rank]
        if spec.bot_id in winners:
            bot_share += share_per_config / len(winners)
    return bot_share


def _best_hand_rank(hole: list[Card], community: list[Card], cfg: HandConfigSpec) -> tuple[int, int] | None:
    """Best (rank, ordered_rank) for one player under one config; None if no qualifying hand.

    Lower tuples are better (rank 1 = best for both high and low games).
    """
    best: tuple[int, int] | None = None
    if cfg.any_cards is not None:
        pool = hole + community
        if len(pool) < cfg.any_cards:
            return None
        for combo in itertools.combinations(pool, cfg.any_cards):
            rank = _rank_of(combo, cfg.eval_type)
            if rank is not None and (best is None or rank < best):
                best = rank
    else:
        if len(hole) < cfg.hole_cards or len(community) < cfg.community_cards:
            return None
        for hole_combo in itertools.combinations(hole, cfg.hole_cards):
            for community_combo in itertools.combinations(community, cfg.community_cards):
                rank = _rank_of(hole_combo + community_combo, cfg.eval_type)
                if rank is not None and (best is None or rank < best):
                    best = rank

    # Qualifier check on the best hand only — if the best doesn't qualify,
    # nothing does. evaluate_hand's own qualifier handling returns rank=0
    # which would incorrectly beat rank 1 in tuple comparison, so check here.
    if best is not None and cfg.qualifier:
        q_rank, q_ordered = cfg.qualifier[0], cfg.qualifier[1] if len(cfg.qualifier) > 1 else None
        if best[0] > q_rank or (best[0] == q_rank and q_ordered is not None and best[1] > q_ordered):
            return None
    return best


def _rank_of(cards, eval_type: EvaluationType) -> tuple[int, int] | None:
    result = _evaluator.evaluate_hand(list(cards), eval_type)
    if result is None or result.rank == 0:
        return None
    return (result.rank, result.ordered_rank if result.ordered_rank is not None else 0)


def estimate_equity(spec: RolloutSpec, rng: Random, deadline: float, max_rollouts: int) -> tuple[float, int]:
    """Average pot-share over rollouts until max_rollouts or deadline. Always runs at least one."""
    total = 0.0
    completed = 0
    while completed < max_rollouts:
        if completed > 0 and time.monotonic() > deadline:
            break
        total += run_rollout(spec, rng)
        completed += 1
    return total / completed, completed
