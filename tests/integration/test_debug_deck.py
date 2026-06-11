"""Integration tests for the debug stacked/seeded deck API (BACKLOG T009).

Covers the admin-gated ``/api/debug`` endpoints that let a tester force a
specific deal order (or seed the shuffle) so scenarios can be reproduced on
demand. Verifies auth gating, the feature flag, and that a stacked deck
actually changes the dealt hand.
"""

import os
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool
from tests.test_helpers import load_rules_from_file

from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from online_poker.auth import init_login_manager
from online_poker.database import db
from online_poker.models.user import User
from online_poker.routes.admin_routes import admin_bp
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.debug_routes import debug_bp
from online_poker.services.game_orchestrator import game_orchestrator

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TABLE_ID = "debug-test-table"


def _make_game() -> Game:
    rules = load_rules_from_file("hold_em")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=True,
    )
    game.add_player("p1", "Alice", 500)
    game.add_player("p2", "Bob", 500)
    return game


@pytest.fixture
def app():
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["DEBUG_ALLOW_STACKED_DECK"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    db.init_app(app)
    init_login_manager(app)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(debug_bp)

    with app.app_context():
        db.create_all()
        # Inject a live game session for the orchestrator the routes use.
        game_orchestrator.sessions[TABLE_ID] = SimpleNamespace(game=_make_game())
        yield app
        game_orchestrator.sessions.pop(TABLE_ID, None)
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin_user(app):
    user = User(username="admin", email="admin@test.com", password="password", bankroll=1000)
    user.is_admin = True
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def regular_user(app):
    user = User(username="regular", email="regular@test.com", password="password", bankroll=500)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username):
    return client.post("/auth/api/login", json={"username": username, "password": "password"})


def _session_table():
    return game_orchestrator.sessions[TABLE_ID].game.table


def test_requires_admin(client, regular_user):
    login(client, "regular")
    resp = client.post(f"/api/debug/tables/{TABLE_ID}/stacked-deck", json={"cards": ["As", "Ks"]})
    assert resp.status_code == 403


def test_disabled_returns_404(client, admin_user):
    """With the feature flag off, the endpoint is invisible (404)."""
    login(client, "admin")
    client.application.config["DEBUG_ALLOW_STACKED_DECK"] = False
    resp = client.post(f"/api/debug/tables/{TABLE_ID}/stacked-deck", json={"cards": ["As", "Ks"]})
    assert resp.status_code == 404


def test_set_stacked_deck(client, admin_user):
    login(client, "admin")
    resp = client.post(
        f"/api/debug/tables/{TABLE_ID}/stacked-deck",
        json={"cards": ["As", "Ks", "Ah", "Kh"]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    table = _session_table()
    assert [str(c) for c in table.stacked_deck] == ["As", "Ks", "Ah", "Kh"]

    # The stack must actually drive the deal.
    table_game = game_orchestrator.sessions[TABLE_ID].game
    table_game.start_hand(shuffle_deck=True)
    assert [str(c) for c in table_game.table.players["p1"].hand.cards] == ["As", "Ah"]
    assert [str(c) for c in table_game.table.players["p2"].hand.cards] == ["Ks", "Kh"]


def test_invalid_card_rejected(client, admin_user):
    login(client, "admin")
    resp = client.post(f"/api/debug/tables/{TABLE_ID}/stacked-deck", json={"cards": ["Zz"]})
    assert resp.status_code == 400


def test_empty_cards_rejected(client, admin_user):
    login(client, "admin")
    resp = client.post(f"/api/debug/tables/{TABLE_ID}/stacked-deck", json={"cards": []})
    assert resp.status_code == 400


def test_clear_stacked_deck(client, admin_user):
    login(client, "admin")
    client.post(f"/api/debug/tables/{TABLE_ID}/stacked-deck", json={"cards": ["As", "Ks"]})
    resp = client.delete(f"/api/debug/tables/{TABLE_ID}/stacked-deck")
    assert resp.status_code == 200
    assert _session_table().stacked_deck is None


def test_set_and_clear_seed(client, admin_user):
    login(client, "admin")
    resp = client.post(f"/api/debug/tables/{TABLE_ID}/seed", json={"seed": 42})
    assert resp.status_code == 200
    assert _session_table().deck_seed == 42

    resp = client.post(f"/api/debug/tables/{TABLE_ID}/seed", json={"seed": None})
    assert resp.status_code == 200
    assert _session_table().deck_seed is None


def test_deck_status(client, admin_user):
    login(client, "admin")
    client.post(f"/api/debug/tables/{TABLE_ID}/stacked-deck", json={"cards": ["As", "Ks"], "repeat": True})
    resp = client.get(f"/api/debug/tables/{TABLE_ID}/deck-status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["pending_stack"] == ["As", "Ks"]
    assert data["stacked_deck_repeat"] is True


def test_unknown_table_returns_404(client, admin_user):
    login(client, "admin")
    resp = client.post("/api/debug/tables/nonexistent/stacked-deck", json={"cards": ["As"]})
    assert resp.status_code == 404
