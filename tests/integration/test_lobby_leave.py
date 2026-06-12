"""Integration tests for the lobby HTTP leave endpoint (UX 2026-06-12).

Lets a seated player leave a table from the lobby (cash out + free the seat)
without opening it — useful when testing across many tables. With no socket
manager in the test app, the endpoint falls back to a plain DB cash-out, which
is what we assert here.
"""

import os

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool

from online_poker.auth import init_login_manager
from online_poker.database import db
from online_poker.models.table import PokerTable
from online_poker.models.table_access import TableAccess
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
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
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
def seated_user(app):
    user = User(username="seated", email="seated@test.com", password="password", bankroll=500)
    db.session.add(user)
    db.session.commit()
    table = PokerTable(
        name="Leave Test",
        variant="hold_em",
        betting_structure="no-limit",
        stakes={"small_blind": 5, "big_blind": 10},
        max_players=6,
        creator_id=user.id,
    )
    db.session.add(table)
    db.session.commit()
    access = TableAccess(user_id=user.id, table_id=table.id, buy_in_amount=200, seat_number=1)
    access.current_stack = 240  # won some chips
    db.session.add(access)
    db.session.commit()
    return user, table


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    return client.post("/auth/api/login", json={"username": "seated", "password": "password"})


def test_leave_cashes_out_and_frees_seat(client, seated_user):
    user, table = seated_user
    _login(client)
    resp = client.post(f"/api/tables/{table.id}/leave")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    access = db.session.query(TableAccess).filter_by(user_id=user.id, table_id=table.id).first()
    assert access.is_active is False
    refreshed = db.session.get(User, user.id)
    assert refreshed.bankroll == 500 + 240  # original + cashed-out stack


def test_leave_when_not_seated_is_rejected(client, seated_user):
    user, table = seated_user
    # Leave once, then try again — no active seat the second time.
    _login(client)
    client.post(f"/api/tables/{table.id}/leave")
    resp = client.post(f"/api/tables/{table.id}/leave")
    assert resp.status_code == 400
    assert "not seated" in resp.get_json()["error"].lower()


def test_leave_requires_auth(client, seated_user):
    _user, table = seated_user
    resp = client.post(f"/api/tables/{table.id}/leave")
    assert resp.status_code in (401, 302)
