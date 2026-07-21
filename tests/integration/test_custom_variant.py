"""Custom (user-authored) variants — Phase 9.5.

Covers the library API round-trip, table creation from a saved variant (inline
copy-on-create), rules resolution surviving library deletion, table-config
validation for the sentinel, and the per-table rules-card endpoint.
"""

import json
import uuid
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool

from generic_poker.game.betting import BettingStructure
from online_poker.auth import init_login_manager
from online_poker.database import db
from online_poker.models.custom_variant import CustomVariant
from online_poker.models.table_config import TableConfig
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.lobby_routes import lobby_bp
from online_poker.routes.table_routes import table_bp
from online_poker.services.table_manager import TableManager, TableValidationError
from online_poker.services.user_manager import UserManager

CONFIG_DIR = Path("data/game_configs")


def load_config(stem: str) -> dict:
    with open(CONFIG_DIR / f"{stem}.json") as f:
        return json.load(f)


def omaha7_config() -> dict:
    """A known-good custom config: Omaha 8 cloned to 7-or-better."""
    cfg = load_config("omaha_8")
    for bh in cfg["showdown"]["bestHand"]:
        if bh.get("evaluationType") == "a5_low":
            bh["qualifier"] = [1, 21]
    cfg["game"] = "Omaha 7-or-Better"
    return cfg


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    db.init_app(app)
    init_login_manager(app)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(lobby_bp)
    app.register_blueprint(table_bp, url_prefix="/table")

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
        TableManager._custom_variant_rules_cache.clear()


def make_user(suffix: str = ""):
    uid = str(uuid.uuid4())[:8]
    user = UserManager.create_user(f"author_{uid}{suffix}", f"author_{uid}{suffix}@test.com", "password123")
    UserManager.update_user_bankroll(user.id, 1000)
    return user


def login(client, user):
    resp = client.post("/auth/api/login", json={"username": user.username, "password": "password123"})
    assert resp.status_code == 200, resp.get_json()


class TestCustomVariantAPI:
    def test_save_list_upsert_delete_roundtrip(self, app):
        user = make_user()
        client = app.test_client()
        login(client, user)

        # Save
        resp = client.post(
            "/api/custom-variants",
            json={"display_name": "Omaha 7-or-Better", "base_variant": "omaha_8", "config": omaha7_config()},
        )
        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()
        assert data["success"]
        variant_id = data["variant"]["id"]
        assert data["variant"]["display_name"] == "Omaha 7-or-Better"
        assert "Limit" in data["variant"]["betting_structures"]

        # Upsert: same name overwrites, count stays 1
        resp = client.post(
            "/api/custom-variants",
            json={"display_name": "Omaha 7-or-Better", "base_variant": "omaha_8", "config": omaha7_config()},
        )
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["variant"]["id"] == variant_id
        assert db.session.query(CustomVariant).filter_by(user_id=user.id).count() == 1

        # List
        resp = client.get("/api/custom-variants")
        variants = resp.get_json()["variants"]
        assert len(variants) == 1
        assert variants[0]["config"]["game"] == "Omaha 7-or-Better"

        # Delete
        resp = client.delete(f"/api/custom-variants/{variant_id}")
        assert resp.get_json()["success"]
        assert db.session.query(CustomVariant).count() == 0

    def test_save_forces_config_game_to_display_name(self, app):
        user = make_user()
        client = app.test_client()
        login(client, user)
        cfg = omaha7_config()
        cfg["game"] = "Something Else"
        resp = client.post("/api/custom-variants", json={"display_name": "My Omaha", "config": cfg})
        assert resp.status_code == 200
        saved = db.session.query(CustomVariant).first()
        assert json.loads(saved.config)["game"] == "My Omaha"

    def test_invalid_config_rejected_with_structured_errors(self, app):
        user = make_user()
        client = app.test_client()
        login(client, user)
        cfg = omaha7_config()
        cfg["bogusKey"] = True
        resp = client.post("/api/custom-variants", json={"display_name": "Bad", "config": cfg})
        assert resp.status_code == 400
        data = resp.get_json()
        assert not data["success"]
        assert any(e["stage"] == "schema" for e in data["errors"])
        assert db.session.query(CustomVariant).count() == 0

    def test_validate_endpoint_shape(self, app):
        user = make_user()
        client = app.test_client()
        login(client, user)
        resp = client.post("/api/custom-variants/validate", json={"config": omaha7_config(), "smoke": False})
        data = resp.get_json()
        assert data["success"] and data["valid"]
        assert data["errors"] == []

        resp = client.post("/api/custom-variants/validate", json={"config": {"game": "x"}, "smoke": False})
        data = resp.get_json()
        assert data["success"] and not data["valid"]
        assert data["errors"]

    def test_non_owner_cannot_delete_or_use(self, app):
        owner, other = make_user("a"), make_user("b")
        client = app.test_client()
        login(client, owner)
        resp = client.post("/api/custom-variants", json={"display_name": "Mine", "config": omaha7_config()})
        assert resp.status_code == 200, resp.get_json()
        variant_id = resp.get_json()["variant"]["id"]

        other_client = app.test_client()
        login(other_client, other)
        assert other_client.delete(f"/api/custom-variants/{variant_id}").status_code == 404
        # Other user can't create a table from someone else's library entry
        resp = other_client.post(
            "/api/tables",
            json={
                "name": "Steal",
                "variant": "custom_variant",
                "custom_variant_id": variant_id,
                "betting_structure": "limit",
                "max_players": 6,
                "stakes": {"small_bet": 10, "big_bet": 20, "ante": 0},
            },
        )
        assert resp.status_code == 404

    def test_game_config_endpoint_for_clone_picker(self, app):
        user = make_user()
        client = app.test_client()
        login(client, user)
        resp = client.get("/table/game-configs/hold_em")
        data = resp.get_json()
        assert data["success"]
        assert data["config"]["game"] == "Hold'em"
        assert client.get("/table/game-configs/not_a_game").status_code == 404


class TestCustomVariantTable:
    def _create_table_from_library(self, app, client, user):
        resp = client.post(
            "/api/custom-variants", json={"display_name": "Omaha 7-or-Better", "config": omaha7_config()}
        )
        assert resp.status_code == 200, resp.get_json()
        variant_id = resp.get_json()["variant"]["id"]
        resp = client.post(
            "/api/tables",
            json={
                "name": "O7 Table",
                "variant": "custom_variant",
                "custom_variant_id": variant_id,
                "betting_structure": "limit",
                "max_players": 6,
                "stakes": {"small_bet": 10, "big_bet": 20, "ante": 0},
            },
        )
        assert resp.status_code == 200, resp.get_json()
        table_id = resp.get_json()["table_id"]
        return variant_id, TableManager.get_table_by_id(table_id)

    def test_table_created_with_inline_copy(self, app):
        user = make_user()
        client = app.test_client()
        login(client, user)
        _, table = self._create_table_from_library(app, client, user)
        assert table.variant == TableManager.CUSTOM_VARIANT_VARIANT
        assert table.custom_variant_config
        assert json.loads(table.custom_variant_config)["game"] == "Omaha 7-or-Better"
        assert table.to_dict()["custom_variant"]["display_name"] == "Omaha 7-or-Better"
        assert table.variant_display_name() == "Omaha 7-or-Better"
        assert not table.is_mixed_game

    def test_rules_resolve_after_library_deletion(self, app):
        """The key guarantee: deleting the library entry never affects the table."""
        user = make_user()
        client = app.test_client()
        login(client, user)
        variant_id, table = self._create_table_from_library(app, client, user)

        assert client.delete(f"/api/custom-variants/{variant_id}").get_json()["success"]

        rules = TableManager.get_table_variant_rules(table)
        assert rules is not None
        assert rules.game == "Omaha 7-or-Better"
        # And the rules actually PLAY: run the smoke harness over them.
        from online_poker.services.variant_authoring import _smoke_play

        assert _smoke_play(rules, smoke_hands=1, seed=7, warnings=[]) is None

    def test_official_stem_name_collision_is_harmless(self, app):
        """A custom variant literally named 'hold_em' resolves to its inline config."""
        user = make_user()
        client = app.test_client()
        login(client, user)
        cfg = omaha7_config()
        resp = client.post("/api/custom-variants", json={"display_name": "hold_em", "config": cfg})
        variant_id = resp.get_json()["variant"]["id"]
        resp = client.post(
            "/api/tables",
            json={
                "name": "Sneaky",
                "variant": "custom_variant",
                "custom_variant_id": variant_id,
                "betting_structure": "limit",
                "max_players": 6,
                "stakes": {"small_bet": 10, "big_bet": 20, "ante": 0},
            },
        )
        table = TableManager.get_table_by_id(resp.get_json()["table_id"])
        rules = TableManager.get_table_variant_rules(table)
        # Inline (Omaha-shaped) config, NOT the official hold_em file
        assert rules.game == "hold_em"
        assert any(
            bh.get("evaluationType") == "a5_low"
            for bh in json.loads(table.custom_variant_config)["showdown"]["bestHand"]
        )

    def test_rules_card_endpoint_uses_inline_config(self, app):
        user = make_user()
        client = app.test_client()
        login(client, user)
        _, table = self._create_table_from_library(app, client, user)
        resp = client.get(f"/table/{table.id}/rules-card")
        data = resp.get_json()
        assert data["success"]
        assert data["rules"]["game"] == "Omaha 7-or-Better"
        assert data["rules"]["betting_structures"]


class TestSentinelValidation:
    def _config(self, betting_structure, max_players, cfg=None):
        stakes = (
            {"small_bet": 10, "big_bet": 20}
            if betting_structure == BettingStructure.LIMIT
            else {"small_blind": 5, "big_blind": 10}
        )
        return TableConfig(
            name="T",
            variant=TableManager.CUSTOM_VARIANT_VARIANT,
            betting_structure=betting_structure,
            stakes=stakes,
            max_players=max_players,
            custom_variant_config=json.dumps(cfg or omaha7_config()),
        )

    def test_unsupported_structure_rejected(self, app):
        # omaha_8 config declares Limit/NL/PL? Use a config restricted to Limit.
        cfg = omaha7_config()
        cfg["bettingStructures"] = ["Limit"]
        with pytest.raises(TableValidationError, match="not supported"):
            TableManager.validate_table_config(self._config(BettingStructure.NO_LIMIT, 6, cfg))

    def test_player_bounds_enforced(self, app):
        cfg = omaha7_config()
        cfg["players"]["max"] = 4
        with pytest.raises(TableValidationError, match="exceeds variant maximum"):
            TableManager.validate_table_config(self._config(BettingStructure.LIMIT, 6, cfg))

    def test_valid_sentinel_config_passes(self, app):
        TableManager.validate_table_config(self._config(BettingStructure.LIMIT, 6))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
