"""Unit tests for the Monte Carlo bot (Phase 1: betting decisions)."""

import time
from pathlib import Path
from random import Random

from generic_poker.config.loader import BettingStructure, GameRules
from generic_poker.core.card import Card
from generic_poker.core.deck import Deck
from generic_poker.evaluation.evaluator import EvaluationType
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction
from online_poker.services.mc_policy import decide
from online_poker.services.mc_rollout import (
    HandConfigSpec,
    RolloutSpec,
    UnsupportedForRollout,
    _best_hand_rank,
    estimate_equity,
    run_rollout,
)
from online_poker.services.monte_carlo_bot import MonteCarloBot
from online_poker.services.simple_bot import BotDecision, BotManager

CONFIG_DIR = Path(__file__).parent.parent.parent / "data" / "game_configs"

HOLDEM_CONFIG = HandConfigSpec(eval_type=EvaluationType.HIGH, any_cards=5)


def cards(*strs):
    return [Card.from_string(s) for s in strs]


def unseen_from(*card_lists):
    """Full standard deck minus all cards in the given lists."""
    used = {str(c) for lst in card_lists for c in lst}
    return [c for c in Deck().cards if str(c) not in used]


def holdem_spec(bot_cards, community=None, community_to_come=5, opponents=1):
    community = community or []
    opp_list = [(f"opp_{i}", [], 2) for i in range(opponents)]
    return RolloutSpec(
        bot_id="bot_1",
        bot_cards=bot_cards,
        opponents=opp_list,
        community=community,
        player_cards_to_come=0,
        community_cards_to_come=community_to_come,
        unseen=unseen_from(bot_cards, community),
        hand_configs=[HOLDEM_CONFIG],
    )


def far_deadline():
    return time.monotonic() + 60


class TestEquityEstimation:
    """Equity sanity checks against known preflop heads-up values."""

    def test_pocket_aces_preflop_heads_up(self):
        spec = holdem_spec(cards("As", "Ah"))
        equity, n = estimate_equity(spec, Random(42), far_deadline(), 400)
        assert n == 400
        assert 0.78 <= equity <= 0.92  # true value ~0.85

    def test_seven_deuce_preflop_heads_up(self):
        spec = holdem_spec(cards("7s", "2h"))
        equity, _ = estimate_equity(spec, Random(42), far_deadline(), 400)
        assert 0.27 <= equity <= 0.42  # true value ~0.35

    def test_nuts_on_river_is_certain_win(self):
        spec = holdem_spec(
            cards("As", "Ks"),
            community=cards("Qs", "Js", "Ts", "2h", "3d"),
            community_to_come=0,
        )
        equity, _ = estimate_equity(spec, Random(42), far_deadline(), 50)
        assert equity == 1.0

    def test_multiway_equity_lower_than_heads_up(self):
        hand = cards("As", "Ah")
        hu, _ = estimate_equity(holdem_spec(list(hand)), Random(42), far_deadline(), 300)
        multi, _ = estimate_equity(holdem_spec(list(hand), opponents=3), Random(42), far_deadline(), 300)
        assert multi < hu

    def test_deterministic_with_seed(self):
        spec = holdem_spec(cards("Kd", "Qd"))
        e1, _ = estimate_equity(spec, Random(7), far_deadline(), 200)
        e2, _ = estimate_equity(spec, Random(7), far_deadline(), 200)
        assert e1 == e2

    def test_deadline_stops_early_but_completes_at_least_one(self):
        spec = holdem_spec(cards("As", "Ah"))
        deadline = time.monotonic() - 1  # already past
        _, n = estimate_equity(spec, Random(42), deadline, 400)
        assert n == 1


class TestQualifierAndSplit:
    def test_low_qualifier_rejects_nine_high(self):
        cfg = HandConfigSpec(eval_type=EvaluationType.LOW_A5, any_cards=5, qualifier=[1, 56])
        assert _best_hand_rank(cards("9s", "7h", "5d", "3c", "2s"), [], cfg) is None

    def test_low_qualifier_accepts_wheel(self):
        cfg = HandConfigSpec(eval_type=EvaluationType.LOW_A5, any_cards=5, qualifier=[1, 56])
        assert _best_hand_rank(cards("As", "2h", "3d", "4c", "5s"), [], cfg) is not None

    def test_hilo_split_half_pot_each(self):
        """Stud8-style deterministic split: bot wins high, opponent wins qualifying low."""
        high = HandConfigSpec(eval_type=EvaluationType.HIGH, hole_cards=5, community_cards=0)
        low = HandConfigSpec(eval_type=EvaluationType.LOW_A5, hole_cards=5, community_cards=0, qualifier=[1, 56])
        bot_cards = cards("As", "Ah", "Ad", "Ks", "Kh", "9c", "Tc")  # aces full, no low
        opp_cards = cards("2s", "3h", "4d", "5c", "7s", "8h", "Jc")  # 7-low, no pair
        spec = RolloutSpec(
            bot_id="bot_1",
            bot_cards=bot_cards,
            opponents=[("opp", opp_cards, 0)],
            community=[],
            player_cards_to_come=0,
            community_cards_to_come=0,
            unseen=unseen_from(bot_cards, opp_cards),
            hand_configs=[high, low],
        )
        assert run_rollout(spec, Random(1)) == 0.5

    def test_hilo_no_qualifying_low_high_scoops(self):
        high = HandConfigSpec(eval_type=EvaluationType.HIGH, hole_cards=5, community_cards=0)
        low = HandConfigSpec(eval_type=EvaluationType.LOW_A5, hole_cards=5, community_cards=0, qualifier=[1, 56])
        bot_cards = cards("As", "Ah", "Ad", "Ks", "Kh", "Tc", "9c")
        opp_cards = cards("Qs", "Qh", "Jd", "Jc", "9s", "Th", "Kc")  # no low either
        spec = RolloutSpec(
            bot_id="bot_1",
            bot_cards=bot_cards,
            opponents=[("opp", opp_cards, 0)],
            community=[],
            player_cards_to_come=0,
            community_cards_to_come=0,
            unseen=unseen_from(bot_cards, opp_cards),
            hand_configs=[high, low],
        )
        assert run_rollout(spec, Random(1)) == 1.0

    def test_omaha_uses_exactly_two_hole_cards(self):
        """Board quads don't make an Omaha hand quads — only 3 board cards may be used."""
        cfg = HandConfigSpec(eval_type=EvaluationType.HIGH, hole_cards=2, community_cards=3)
        board = cards("9s", "9h", "9d", "9c", "2s")
        rank = _best_hand_rank(cards("As", "Kh", "5d", "4c"), board, cfg)
        assert rank is not None
        assert rank[0] > 2  # best is trip nines + two hole kickers, never quads (rank 2)


class TestPolicy:
    def test_never_folds_when_check_available(self):
        actions = [(PlayerAction.CHECK, None, None), (PlayerAction.FOLD, None, None)]
        for seed in range(20):
            decision = decide(0.05, actions, pot=100, call_cost=0, players_in_hand=2, rng=Random(seed))
            assert decision.action == PlayerAction.CHECK

    def test_folds_bad_pot_odds(self):
        actions = [
            (PlayerAction.FOLD, None, None),
            (PlayerAction.CALL, 100, 100),
            (PlayerAction.RAISE, 200, 500),
        ]
        # equity 10%, pot odds 50% — clear fold; aggression=0 disables bluffs
        decision = decide(0.10, actions, pot=100, call_cost=100, players_in_hand=2, rng=Random(1), aggression=0.0)
        assert decision.action == PlayerAction.FOLD

    def test_calls_or_raises_with_strong_equity(self):
        actions = [
            (PlayerAction.FOLD, None, None),
            (PlayerAction.CALL, 10, 10),
            (PlayerAction.RAISE, 20, 100),
        ]
        for seed in range(20):
            decision = decide(0.85, actions, pot=100, call_cost=10, players_in_hand=2, rng=Random(seed))
            assert decision.action in (PlayerAction.CALL, PlayerAction.RAISE)

    def test_bets_strong_hand_when_checked_to(self):
        actions = [(PlayerAction.CHECK, None, None), (PlayerAction.BET, 10, 100)]
        decision = decide(0.9, actions, pot=100, call_cost=0, players_in_hand=2, rng=Random(1))
        assert decision.action == PlayerAction.BET
        assert 10 <= decision.amount <= 100

    def test_bring_in_with_weak_hand(self):
        actions = [(PlayerAction.BRING_IN, 5, 5), (PlayerAction.COMPLETE, 10, 10)]
        decision = decide(0.2, actions, pot=10, call_cost=5, players_in_hand=4, rng=Random(1))
        assert decision.action == PlayerAction.BRING_IN
        assert decision.amount == 5

    def test_completes_bring_in_with_strong_hand(self):
        actions = [(PlayerAction.BRING_IN, 5, 5), (PlayerAction.COMPLETE, 10, 10)]
        decision = decide(0.9, actions, pot=10, call_cost=5, players_in_hand=4, rng=Random(1))
        assert decision.action == PlayerAction.COMPLETE


def _create_game(variant: str, num_players: int = 2, structure: str = "No Limit"):
    rules = GameRules.from_file(CONFIG_DIR / f"{variant}.json")
    game = Game(
        rules,
        structure=BettingStructure(structure),
        small_blind=1,
        big_blind=2,
        small_bet=2,
        big_bet=4,
        bring_in=1,
        ante=1 if variant in ("7_card_stud", "razz") else None,
        auto_progress=False,
    )
    names = ["Alice", "Bob", "Charlie", "Diana"]
    for i in range(num_players):
        game.add_player(f"player_{i}", names[i], 100)
    game.table.move_button()
    game.start_hand(shuffle_deck=True)
    while game.current_player is None and game.state != GameState.COMPLETE:
        game._next_step()
        if game.current_step >= len(game.rules.gameplay):
            break
    return game


class TestFromGame:
    def test_holdem_preflop_snapshot(self):
        game = _create_game("hold_em")
        bot_id = game.current_player.id
        spec = RolloutSpec.from_game(game, bot_id)
        assert len(spec.bot_cards) == 2
        assert len(spec.opponents) == 1
        assert spec.opponents[0][2] == 2  # opponent hole cards hidden
        assert spec.community_cards_to_come == 5
        assert spec.player_cards_to_come == 0
        assert len(spec.unseen) == 50

    def test_stud_snapshot_counts_cards_to_come(self):
        game = _create_game("7_card_stud", num_players=3, structure="Limit")
        bot_id = game.current_player.id
        spec = RolloutSpec.from_game(game, bot_id)
        assert len(spec.bot_cards) == 3  # third street
        assert spec.player_cards_to_come == 4  # 4th-7th street
        assert spec.community_cards_to_come == 0
        # Each opponent shows exactly one door card
        for _, visible, hidden in spec.opponents:
            assert len(visible) == 1
            assert hidden == 2

    def test_draw_game_pre_draw_unsupported(self):
        game = _create_game("5_card_draw")
        bot_id = game.current_player.id
        try:
            RolloutSpec.from_game(game, bot_id)
            raise AssertionError("expected UnsupportedForRollout")
        except UnsupportedForRollout:
            pass


class TestMonteCarloBot:
    def test_betting_decision_on_holdem(self):
        game = _create_game("hold_em")
        bot_id = game.current_player.id
        bot = MonteCarloBot(bot_id, "MC Bot", time_budget_ms=500, max_rollouts=100, seed=42)
        decision = bot.choose_action_full(game.get_valid_actions(bot_id), game, bot_id)
        assert isinstance(decision, BotDecision)
        valid_types = {a[0] for a in game.get_valid_actions(bot_id)}
        assert decision.action in valid_types

    def test_falls_back_on_draw_game(self):
        game = _create_game("5_card_draw")
        bot_id = game.current_player.id
        bot = MonteCarloBot(bot_id, "MC Bot", seed=42)
        decision = bot.choose_action_full(game.get_valid_actions(bot_id), game, bot_id)
        assert isinstance(decision, BotDecision)
        valid_types = {a[0] for a in game.get_valid_actions(bot_id)}
        assert decision.action in valid_types

    def test_decision_within_time_budget(self):
        game = _create_game("hold_em")
        bot_id = game.current_player.id
        bot = MonteCarloBot(bot_id, "MC Bot", time_budget_ms=1000, max_rollouts=10_000, seed=42)
        start = time.monotonic()
        bot.choose_action_full(game.get_valid_actions(bot_id), game, bot_id)
        assert time.monotonic() - start < 3.0

    def test_bot_manager_creates_mc_bot(self):
        manager = BotManager()
        bot = manager.create_bot("bot_test_1", "MC Bot", bot_type="mc")
        assert isinstance(bot, MonteCarloBot)
        assert manager.get_bot("bot_test_1") is bot
        manager.remove_bot("bot_test_1")

    def test_bot_manager_defaults_to_simple(self):
        manager = BotManager()
        bot = manager.create_bot("bot_test_2", "Simple Bot")
        assert not isinstance(bot, MonteCarloBot)
        manager.remove_bot("bot_test_2")
