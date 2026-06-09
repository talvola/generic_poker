"""Monte Carlo equity bot — variant-agnostic via the engine's hand evaluator.

Phase 1: Monte Carlo for betting decisions when the rest of the hand is
deal-only (Hold'em, Omaha, stud, and post-final-draw rounds of draw games).
Everything else — draw/discard/expose/pass/declare/choose actions, and betting
decisions in states the rollout engine can't model — falls back to SimpleBot.

Drop-in compatible with SimpleBot: same choose_action_full signature, same
BotDecision return type, same BotManager integration.
"""

import logging
import time
from random import Random

from generic_poker.game.game_state import PlayerAction

from .mc_policy import BETTING_ACTIONS, decide
from .mc_rollout import RolloutSpec, UnsupportedForRollout, estimate_equity
from .simple_bot import BotDecision, SimpleBot

logger = logging.getLogger(__name__)

# Absolute wall-clock cap per decision regardless of configured budget.
HARD_CAP_MS = 3000


class MonteCarloBot:
    """Bot that estimates equity by Monte Carlo rollouts and bets on pot odds."""

    def __init__(
        self,
        player_id: str,
        username: str,
        time_budget_ms: int = 1500,
        max_rollouts: int = 500,
        aggression: float = 1.0,
        seed: int | None = None,
    ):
        self.player_id = player_id
        self.username = username
        self.is_bot = True
        self.time_budget_ms = min(time_budget_ms, HARD_CAP_MS)
        self.max_rollouts = max_rollouts
        self.aggression = aggression
        self._rng = Random(seed)
        self._fallback = SimpleBot(player_id, username)

    def choose_action_full(self, valid_actions: list[tuple], game=None, player_id: str | None = None) -> BotDecision:
        """Choose an action; same contract as SimpleBot.choose_action_full."""
        if not valid_actions:
            logger.warning(f"MC bot {self.username} has no valid actions")
            return BotDecision(action=PlayerAction.FOLD)

        pid = player_id or self.player_id
        action_types = {a[0] for a in valid_actions}
        if game is None or not (action_types & BETTING_ACTIONS):
            return self._fallback.choose_action_full(valid_actions, game, player_id)

        try:
            spec = RolloutSpec.from_game(game, pid)
            deadline = time.monotonic() + self.time_budget_ms / 1000
            started = time.monotonic()
            equity, rollouts = estimate_equity(spec, self._rng, deadline, self.max_rollouts)
            elapsed_ms = (time.monotonic() - started) * 1000

            pot = game.betting.get_total_pot()
            call_cost = game.betting.get_additional_required(pid)
            players_in_hand = sum(1 for p in game.table.players.values() if p.is_active)

            decision = decide(equity, valid_actions, pot, call_cost, players_in_hand, self._rng, self.aggression)
            logger.info(
                f"MC bot {self.username}: equity={equity:.3f} ({rollouts} rollouts, {elapsed_ms:.0f}ms) "
                f"pot={pot} call={call_cost} -> {decision.action.value}"
                f"{' ' + str(decision.amount) if decision.amount else ''}"
            )
            return decision
        except UnsupportedForRollout as e:
            logger.debug(f"MC bot {self.username}: falling back to SimpleBot ({e})")
            return self._fallback.choose_action_full(valid_actions, game, player_id)
        except Exception:
            logger.warning(f"MC bot {self.username}: rollout failed, falling back to SimpleBot", exc_info=True)
            return self._fallback.choose_action_full(valid_actions, game, player_id)

    @staticmethod
    def is_bot_player(player_id: str) -> bool:
        """Check if a player ID represents a bot/demo player."""
        return SimpleBot.is_bot_player(player_id)
