"""Dealer's Choice mixed game — Phase 9.4.

The rotation list is an *allowed menu*; the button player picks the next variant
each orbit (and before the very first hand) instead of cycling in fixed order.
Covers config flag plumbing + the GameSession choice state machine.
"""

import json

from tests.test_helpers import load_rules_from_file

from generic_poker.config.mixed_game_loader import MixedGameConfig
from online_poker.models.table import PokerTable
from online_poker.services.game_orchestrator import GameSession
from online_poker.services.table_manager import TableManager


def _dealers_choice_config():
    cfg, err = TableManager.normalize_custom_mix(
        "Friday Night",
        [
            {"variant": "hold_em", "bettingStructure": "No Limit"},
            {"variant": "omaha_8", "bettingStructure": "Limit"},
            {"variant": "razz", "bettingStructure": "Limit"},
        ],
        dealers_choice=True,
    )
    assert err is None
    return cfg


def _session_with_players(stacks=(200, 200)):
    cfg = _dealers_choice_config()
    table = PokerTable(
        name="DC",
        variant=TableManager.CUSTOM_MIX_VARIANT,
        betting_structure="Limit",
        stakes={"small_bet": 10, "big_bet": 20},
        max_players=6,
        creator_id="c1",
        custom_mix_config=json.dumps(cfg),
        is_mixed_game=True,
    )
    # First leg is NL hold'em; build the initial game for it like create_session does.
    session = GameSession(table, load_rules_from_file("hold_em"))
    session.mixed_game_config = MixedGameConfig.from_dict(cfg)
    session.game = table.create_game_instance_for_variant(load_rules_from_file("hold_em"), "No Limit")
    session.game.add_player("p1", "Alice", stacks[0])
    session.game.add_player("p2", "Bob", stacks[1])
    session.orbit_size = 2
    return session


class TestDealersChoiceConfig:
    def test_normalize_sets_flag(self):
        cfg = _dealers_choice_config()
        assert cfg["dealersChoice"] is True

    def test_config_roundtrip_preserves_flag(self):
        cfg = _dealers_choice_config()
        mc = MixedGameConfig.from_dict(cfg)
        assert mc.dealers_choice is True
        assert MixedGameConfig.from_dict(mc.to_dict()).dealers_choice is True

    def test_non_dealers_choice_defaults_false(self):
        cfg, _ = TableManager.normalize_custom_mix(
            "Plain",
            [
                {"variant": "hold_em", "bettingStructure": "Limit"},
                {"variant": "razz", "bettingStructure": "Limit"},
            ],
        )
        assert cfg["dealersChoice"] is False
        assert MixedGameConfig.from_dict(cfg).dealers_choice is False


class TestDealersChoiceStateMachine:
    def test_is_dealers_choice(self):
        session = _session_with_players()
        assert session.is_dealers_choice() is True

    def test_prompts_before_first_hand(self):
        session = _session_with_players()
        # No initial pick yet -> dealer must choose even though no orbit has elapsed.
        assert session.has_made_initial_choice is False
        assert session.needs_dealer_choice() is True

    def test_no_prompt_after_pick_until_orbit_completes(self):
        session = _session_with_players()
        session.apply_dealer_choice(2)  # Razz
        assert session.has_made_initial_choice is True
        assert session.current_variant_index == 2
        assert session.game_rules.game.lower().startswith("razz")
        assert session.needs_dealer_choice() is False  # mid-orbit
        # Play out the orbit (orbit_size == 2).
        session.hands_in_current_variant = 2
        assert session.should_rotate() is True
        assert session.needs_dealer_choice() is True  # new orbit -> pick again

    def test_apply_choice_preserves_stacks_and_button(self):
        session = _session_with_players(stacks=(250, 275))
        session.game.table.button_seat = session.game.table.players["p2"].position
        button_before = session.game.table.button_seat
        session.apply_dealer_choice(1)  # Omaha-8
        assert session.game.table.players["p1"].stack == 250
        assert session.game.table.players["p2"].stack == 275
        assert session.game.table.button_seat == button_before
        assert "omaha" in session.game_rules.game.lower()

    def test_apply_choice_rejects_out_of_range(self):
        session = _session_with_players()
        try:
            session.apply_dealer_choice(99)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass

    def test_menu_lists_all_variants(self):
        session = _session_with_players()
        menu = session.get_dealer_choice_menu()
        assert [m["index"] for m in menu] == [0, 1, 2]
        assert menu[0]["betting_structure"] == "No Limit"
        assert all("display_name" in m and "letter" in m for m in menu)

    def test_mixed_game_info_flags_dealers_choice(self):
        session = _session_with_players()
        session.apply_dealer_choice(0)
        info = session.get_mixed_game_info()
        assert info["dealers_choice"] is True


class TestDealerChoiceGate:
    """WebSocketManager._handle_dealer_choice_gate: bot auto-picks, human is prompted."""

    def _session_with(self, players):
        cfg = _dealers_choice_config()
        table = PokerTable(
            name="DC",
            variant=TableManager.CUSTOM_MIX_VARIANT,
            betting_structure="Limit",
            stakes={"small_bet": 10, "big_bet": 20},
            max_players=6,
            creator_id="c1",
            custom_mix_config=json.dumps(cfg),
            is_mixed_game=True,
        )
        session = GameSession(table, load_rules_from_file("hold_em"))
        session.mixed_game_config = MixedGameConfig.from_dict(cfg)
        session.game = table.create_game_instance_for_variant(load_rules_from_file("hold_em"), "No Limit")
        for pid, name in players:
            session.game.add_player(pid, name, 400)
        session.orbit_size = len(players)
        return session

    def _wsm(self):
        from unittest.mock import MagicMock

        from online_poker.services.websocket_manager import WebSocketManager

        wsm = WebSocketManager(MagicMock())
        wsm.broadcast_to_table = MagicMock()
        wsm.broadcast_game_action_chat = MagicMock()
        return wsm

    def test_bot_dealer_auto_picks(self):
        session = self._session_with([("bot_t_0", "Botty"), ("u-human", "Alice")])
        session.game.table.button_seat = session.game.table.get_player_seat_number("bot_t_0")
        wsm = self._wsm()
        waiting = wsm._handle_dealer_choice_gate("t1", session)
        assert waiting is False  # resolved inline; caller may start the hand
        assert session.has_made_initial_choice is True
        assert session.pending_dealer_choice is False
        events = [c.args[1] for c in wsm.broadcast_to_table.call_args_list]
        assert "variant_changed" in events

    def test_human_dealer_is_prompted_and_held(self):
        session = self._session_with([("bot_t_0", "Botty"), ("u-human", "Alice")])
        session.game.table.button_seat = session.game.table.get_player_seat_number("u-human")
        wsm = self._wsm()
        waiting = wsm._handle_dealer_choice_gate("t1", session)
        assert waiting is True  # hand held until the human picks
        assert session.pending_dealer_choice is True
        assert session.dealer_choice_player_id == "u-human"
        events = [c.args[1] for c in wsm.broadcast_to_table.call_args_list]
        assert "dealer_choice_required" in events
