"""Rebuy after busting and play-money bankroll reload (GitHub #10)."""

import os
from datetime import datetime, timedelta

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool

from online_poker.auth import init_login_manager
from online_poker.database import db
from online_poker.models.table import PokerTable
from online_poker.models.table_access import TableAccess
from online_poker.models.transaction import Transaction
from online_poker.models.user import User
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.lobby_routes import lobby_bp

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture
def app():
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["RATELIMIT_ENABLED"] = False
    app.config["DEFAULT_BANKROLL"] = 1000
    app.config["BANKROLL_RELOAD_THRESHOLD"] = 50
    app.config["BANKROLL_RELOAD_COOLDOWN_HOURS"] = 24
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    db.init_app(app)
    init_login_manager(app)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(lobby_bp, url_prefix="/")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(username, bankroll):
    user = User(username=username, email=f"{username}@test.com", password="password123", bankroll=bankroll)
    db.session.add(user)
    db.session.commit()
    return user


def _make_table(creator):
    table = PokerTable(
        name="Rebuy Test",
        variant="hold_em",
        betting_structure="no-limit",
        stakes={"small_blind": 1, "big_blind": 2},  # $40 - $400
        max_players=6,
        creator_id=creator.id,
    )
    db.session.add(table)
    db.session.commit()
    return table


def _seat(user, table, stack):
    access = TableAccess(user_id=user.id, table_id=table.id, buy_in_amount=80, seat_number=1)
    access.current_stack = stack
    db.session.add(access)
    db.session.commit()
    return access


def _login(client, username):
    resp = client.post("/auth/api/login", json={"username": username, "password": "password123"})
    assert resp.get_json()["success"]


class TestRebuy:
    def test_busted_player_can_rebuy_from_bankroll(self, client):
        user = _make_user("busted", 500)
        table = _make_table(user)
        _seat(user, table, 0)
        _login(client, "busted")

        resp = client.post(f"/api/tables/{table.id}/rebuy", json={"amount": 80})
        body = resp.get_json()
        assert resp.status_code == 200, body
        assert body["stack"] == 80
        assert body["bankroll"] == 420
        access = db.session.query(TableAccess).filter_by(user_id=user.id, table_id=table.id).first()
        assert access.current_stack == 80
        tx = db.session.query(Transaction).filter_by(user_id=user.id).all()
        assert len(tx) == 1 and tx[0].amount == -80 and tx[0].transaction_type == Transaction.TYPE_BUYIN

    def test_rebuy_respects_table_max_and_bankroll(self, client):
        user = _make_user("capped", 100)
        table = _make_table(user)
        _seat(user, table, 200)
        _login(client, "capped")

        too_big = client.post(f"/api/tables/{table.id}/rebuy", json={"amount": 250}).get_json()
        assert too_big["success"] is False and "maximum" in too_big["error"]
        ok = client.post(f"/api/tables/{table.id}/rebuy", json={"amount": 80}).get_json()
        assert ok["success"] is True and ok["stack"] == 280 and ok["bankroll"] == 20
        again = client.post(f"/api/tables/{table.id}/rebuy", json={"amount": 60}).get_json()
        assert again["success"] is False and "bankroll" in again["error"].lower()

    def test_rebuy_requires_a_seat(self, client):
        user = _make_user("standing", 500)
        table = _make_table(user)
        _login(client, "standing")
        resp = client.post(f"/api/tables/{table.id}/rebuy", json={"amount": 80})
        assert resp.status_code == 400
        assert "not seated" in resp.get_json()["error"]


class TestBankrollReload:
    def test_reload_tops_up_when_nearly_broke(self, client):
        _make_user("broke", 12)
        _login(client, "broke")
        status = client.get("/api/bankroll/reload-status").get_json()
        assert status["eligible"] is True
        resp = client.post("/api/bankroll/reload").get_json()
        assert resp["success"] is True
        assert resp["bankroll"] == 1000 and resp["amount"] == 988
        # Second reload inside the cooldown is refused
        again = client.post("/api/bankroll/reload")
        assert again.status_code == 400
        assert again.get_json()["next_eligible_at"]

    def test_reload_refused_above_threshold(self, client):
        _make_user("solvent", 200)
        _login(client, "solvent")
        assert client.get("/api/bankroll/reload-status").get_json()["eligible"] is False
        resp = client.post("/api/bankroll/reload")
        assert resp.status_code == 400
        assert "below" in resp.get_json()["error"]

    def test_reload_available_again_after_cooldown(self, client):
        user = _make_user("patient", 5)
        old = Transaction(user_id=user.id, amount=900, transaction_type=Transaction.TYPE_BONUS, description="old")
        old.created_at = datetime.utcnow() - timedelta(hours=25)
        db.session.add(old)
        db.session.commit()
        _login(client, "patient")
        assert client.get("/api/bankroll/reload-status").get_json()["eligible"] is True
