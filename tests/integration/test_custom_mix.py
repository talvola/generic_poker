"""Custom (user-authored) mixed-game builder — Phase 9.3.

Covers the validation/normalization, config round-trip, per-table resolution
(inline JSON vs file fallback), and that an arbitrary user-composed rotation
plays each leg to completion under its own betting structure.
"""

import json

from generic_poker.config.loader import GameRules
from generic_poker.config.mixed_game_loader import MixedGameConfig
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState
from online_poker.models.table import PokerTable
from online_poker.services.table_manager import TableManager


class TestCustomMixValidation:
    """normalize_custom_mix: validation + normalization rules."""

    def test_valid_mix_normalizes(self):
        cfg, err = TableManager.normalize_custom_mix(
            "My Mix",
            [
                {"variant": "hold_em", "bettingStructure": "No Limit"},
                {"variant": "omaha_8", "bettingStructure": "Limit"},
                {"variant": "razz", "bettingStructure": "Limit"},
            ],
        )
        assert err is None
        assert cfg["name"] == TableManager.CUSTOM_MIX_VARIANT
        assert cfg["displayName"] == "My Mix"
        assert [leg["letter"] for leg in cfg["rotation"]] == ["H", "O", "R"]
        # Union of leg structures, order-preserving
        assert cfg["bettingStructures"] == ["No Limit", "Limit"]

    def test_letters_deduplicated(self):
        """Two variants starting with the same letter get distinct letters."""
        cfg, err = TableManager.normalize_custom_mix(
            "Dupes",
            [
                {"variant": "hold_em", "bettingStructure": "Limit"},
                {"variant": "razz", "bettingStructure": "Limit"},
                {"variant": "7_card_stud", "bettingStructure": "Limit"},
            ],
        )
        assert err is None
        letters = [leg["letter"] for leg in cfg["rotation"]]
        assert len(set(letters)) == len(letters)

    def test_explicit_letters_preserved(self):
        cfg, err = TableManager.normalize_custom_mix(
            "Lettered",
            [
                {"variant": "hold_em", "bettingStructure": "Limit", "letter": "X"},
                {"variant": "razz", "bettingStructure": "Limit", "letter": "Y"},
            ],
        )
        assert err is None
        assert [leg["letter"] for leg in cfg["rotation"]] == ["X", "Y"]

    def test_rejects_unknown_variant(self):
        _, err = TableManager.normalize_custom_mix(
            "X",
            [
                {"variant": "not_a_game", "bettingStructure": "Limit"},
                {"variant": "hold_em", "bettingStructure": "Limit"},
            ],
        )
        assert err and "Unknown variant" in err

    def test_rejects_unsupported_structure(self):
        # Razz is Limit-only; No Limit must be rejected.
        _, err = TableManager.normalize_custom_mix(
            "X",
            [
                {"variant": "razz", "bettingStructure": "No Limit"},
                {"variant": "hold_em", "bettingStructure": "Limit"},
            ],
        )
        assert err and "does not support" in err

    def test_rejects_too_few_games(self):
        _, err = TableManager.normalize_custom_mix("X", [{"variant": "hold_em", "bettingStructure": "Limit"}])
        assert err and "at least 2" in err

    def test_rejects_empty_name(self):
        _, err = TableManager.normalize_custom_mix(
            "  ",
            [
                {"variant": "hold_em", "bettingStructure": "Limit"},
                {"variant": "razz", "bettingStructure": "Limit"},
            ],
        )
        assert err and "name" in err.lower()

    def test_player_bounds_are_most_restrictive(self):
        # Stud games cap at 8; hold'em allows 9 -> mix max should be the lower bound.
        cfg, err = TableManager.normalize_custom_mix(
            "Bounds",
            [
                {"variant": "hold_em", "bettingStructure": "Limit"},
                {"variant": "7_card_stud", "bettingStructure": "Limit"},
            ],
        )
        assert err is None
        assert cfg["maxPlayers"] <= 8


class TestCustomMixConfigRoundTrip:
    """MixedGameConfig serialization parity for custom mixes."""

    def test_to_dict_from_dict_roundtrip(self):
        cfg, _ = TableManager.normalize_custom_mix(
            "RT",
            [
                {"variant": "hold_em", "bettingStructure": "No Limit"},
                {"variant": "razz", "bettingStructure": "Limit"},
            ],
        )
        mc = MixedGameConfig.from_dict(cfg)
        mc2 = MixedGameConfig.from_dict(mc.to_dict())
        assert mc2.display_name == mc.display_name
        assert [v.variant for v in mc2.rotation] == [v.variant for v in mc.rotation]
        assert [v.betting_structure for v in mc2.rotation] == [v.betting_structure for v in mc.rotation]
        assert [v.letter for v in mc2.rotation] == [v.letter for v in mc.rotation]


class TestCustomMixResolution:
    """get_table_mixed_config: inline JSON resolves; falls back to file lookup."""

    def _custom_table(self):
        cfg, _ = TableManager.normalize_custom_mix(
            "Inline Mix",
            [
                {"variant": "hold_em", "bettingStructure": "Limit"},
                {"variant": "omaha_8", "bettingStructure": "Limit"},
            ],
        )
        return PokerTable(
            name="Custom",
            variant=TableManager.CUSTOM_MIX_VARIANT,
            betting_structure="Limit",
            stakes={"small_bet": 10, "big_bet": 20},
            max_players=6,
            creator_id="c1",
            custom_mix_config=json.dumps(cfg),
            is_mixed_game=True,
        )

    def test_inline_custom_mix_resolves(self):
        table = self._custom_table()
        mc = TableManager.get_table_mixed_config(table)
        assert mc is not None
        assert mc.display_name == "Inline Mix"
        assert [v.variant for v in mc.rotation] == ["hold_em", "omaha_8"]

    def test_custom_mix_summary(self):
        table = self._custom_table()
        summary = table._custom_mix_summary()
        assert summary["display_name"] == "Inline Mix"
        assert summary["rotation_letters"] == ["H", "O"]
        assert len(summary["rotation"]) == 2

    def test_file_based_mix_still_resolves(self):
        """A normal (file-based) mix table with no inline JSON uses the file."""
        table = PokerTable(
            name="HORSE",
            variant="horse",
            betting_structure="Limit",
            stakes={"small_bet": 10, "big_bet": 20},
            max_players=6,
            creator_id="c1",
        )
        mc = TableManager.get_table_mixed_config(table)
        assert mc is not None
        assert mc.name == "horse"
        assert len(mc.rotation) == 5


class TestCustomMixPlays:
    """An arbitrary user rotation plays each leg to completion under its structure."""

    def _play(self, rules, structure):
        if structure == BettingStructure.LIMIT:
            game = Game(rules=rules, structure=structure, small_bet=2, big_bet=4, ante=0, auto_progress=True)
        else:
            game = Game(rules=rules, structure=structure, small_blind=1, big_blind=2, auto_progress=True)
        game.add_player("p1", "Alice", 200)
        game.add_player("p2", "Bob", 200)
        game.start_hand(shuffle_deck=True)
        actions = 0
        while game.state != GameState.COMPLETE and actions < 200:
            if game.current_player is None:
                break
            valid = game.get_valid_actions(game.current_player.id)
            if not valid:
                break
            action = valid[0][0]
            amount = valid[0][1] if len(valid[0]) > 1 else 0
            game.player_action(game.current_player.id, action, amount)
            actions += 1
        assert game.state == GameState.COMPLETE, f"{rules.game} ({structure}) did not complete"

    def test_custom_rotation_all_legs_play(self):
        cfg, err = TableManager.normalize_custom_mix(
            "Playable",
            [
                {"variant": "hold_em", "bettingStructure": "No Limit"},
                {"variant": "omaha_8", "bettingStructure": "Pot Limit"},
                {"variant": "razz", "bettingStructure": "Limit"},
            ],
        )
        assert err is None
        mc = MixedGameConfig.from_dict(cfg)
        structure_map = {
            "Limit": BettingStructure.LIMIT,
            "No Limit": BettingStructure.NO_LIMIT,
            "Pot Limit": BettingStructure.POT_LIMIT,
        }
        for leg in mc.rotation:
            rules = GameRules.from_file(f"data/game_configs/{leg.variant}.json")
            self._play(rules, structure_map[leg.betting_structure])
