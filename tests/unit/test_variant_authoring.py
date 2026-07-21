"""Unit tests for the custom-variant validation pipeline (Phase 9.5)."""

import json
from pathlib import Path

import pytest

from online_poker.services.simple_bot import SimpleBot
from online_poker.services.table_manager import TableManager
from online_poker.services.variant_authoring import (
    MAX_CONFIG_BYTES,
    validate_custom_variant,
)

CONFIG_DIR = Path("data/game_configs")


def load_config(stem: str) -> dict:
    with open(CONFIG_DIR / f"{stem}.json") as f:
        return json.load(f)


def stages(errors) -> list[str]:
    return [e.stage for e in errors]


class TestPrechecks:
    def test_non_dict_rejected(self):
        ok, errors, _ = validate_custom_variant(["not", "a", "dict"], run_smoke=False)
        assert not ok
        assert stages(errors) == ["precheck"]

    def test_missing_game_name_rejected(self):
        cfg = load_config("hold_em")
        cfg["game"] = "   "
        ok, errors, _ = validate_custom_variant(cfg, run_smoke=False)
        assert not ok
        assert stages(errors) == ["precheck"]
        assert errors[0].json_path == "game"

    def test_oversize_config_rejected(self):
        cfg = load_config("hold_em")
        cfg["references"] = ["x" * MAX_CONFIG_BYTES]
        ok, errors, _ = validate_custom_variant(cfg, run_smoke=False)
        assert not ok
        assert stages(errors) == ["precheck"]
        assert "too large" in errors[0].message


class TestSchemaStage:
    def test_unknown_top_level_key_rejected(self):
        cfg = load_config("hold_em")
        cfg["bogusKey"] = True
        ok, errors, _ = validate_custom_variant(cfg, run_smoke=False)
        assert not ok
        assert "schema" in stages(errors)
        assert any("bogusKey" in e.message for e in errors)

    def test_bad_enum_value_reports_json_path(self):
        cfg = load_config("hold_em")
        cfg["deck"]["type"] = "tarot"
        ok, errors, _ = validate_custom_variant(cfg, run_smoke=False)
        assert not ok
        assert all(e.stage == "schema" for e in errors)
        assert any(e.json_path and "deck" in e.json_path for e in errors)


class TestEngineStage:
    def test_deck_size_mismatch_rejected(self):
        cfg = load_config("hold_em")
        cfg["deck"]["cards"] = 36  # standard deck must be 52; schema allows the enum value
        ok, errors, _ = validate_custom_variant(cfg, run_smoke=False)
        assert not ok
        # Caught by schema (const pairing) or engine depending on schema strictness —
        # either way it must not pass.
        assert set(stages(errors)) <= {"schema", "engine"}


class TestPlatformStage:
    def test_unsupported_action_rejected(self, monkeypatch):
        from generic_poker.config.loader import GameActionType

        cfg = load_config("hold_em")
        monkeypatch.setattr(TableManager, "UNSUPPORTED_ACTIONS", {GameActionType.DEAL})
        ok, errors, _ = validate_custom_variant(cfg, run_smoke=False)
        assert not ok
        assert stages(errors) == ["platform"]
        assert "deal" in errors[0].message.lower()

    def test_gate_shared_with_lobby_filter(self, monkeypatch):
        """get_available_variants must use the same helper the pipeline uses."""
        from generic_poker.config.loader import GameActionType

        rules = TableManager.get_variant_rules("hold_em")
        assert TableManager.find_unsupported_action(rules) is None
        monkeypatch.setattr(TableManager, "UNSUPPORTED_ACTIONS", {GameActionType.DEAL})
        assert TableManager.find_unsupported_action(rules) == GameActionType.DEAL


class TestSmokeStage:
    def test_valid_clone_passes_smoke(self):
        cfg = load_config("omaha_8")
        for bh in cfg["showdown"]["bestHand"]:
            if bh.get("evaluationType") == "a5_low":
                bh["qualifier"] = [1, 21]  # 7-or-better
        cfg["game"] = "Omaha 7-or-Better (Custom)"
        ok, errors, warnings = validate_custom_variant(cfg)
        assert ok, [e.to_dict() for e in errors]
        assert errors == []

    def test_deterministic_under_fixed_seed(self):
        cfg = load_config("hold_em")
        cfg["game"] = "Hold'em Clone"
        r1 = validate_custom_variant(cfg, seed=99)
        r2 = validate_custom_variant(cfg, seed=99)
        assert r1[0] == r2[0] is True

    def test_bot_crash_becomes_smoke_error(self, monkeypatch):
        cfg = load_config("hold_em")

        def boom(self, *a, **kw):
            raise RuntimeError("bot exploded")

        monkeypatch.setattr(SimpleBot, "choose_action_full", boom)
        ok, errors, _ = validate_custom_variant(cfg)
        assert not ok
        assert stages(errors) == ["smoke"]
        assert "bot exploded" in errors[0].message


class TestWarnings:
    def test_missing_category_warns_but_passes(self):
        cfg = load_config("hold_em")
        cfg.pop("category", None)
        ok, errors, warnings = validate_custom_variant(cfg, run_smoke=False)
        assert ok
        assert any("category" in w for w in warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
