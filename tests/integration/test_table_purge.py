"""Empty-table purge (GitHub #11)."""

from datetime import datetime, timedelta

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool

from online_poker.database import db
from online_poker.models.table import PokerTable
from online_poker.models.table_access import TableAccess
from online_poker.models.user import User
from online_poker.services.table_manager import TableManager


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _user(name, admin=False):
    u = User(username=name, email=f"{name}@t.com", password="password123", bankroll=1000)
    u.is_admin = admin
    db.session.add(u)
    db.session.commit()
    return u


def _table(creator, name, idle_minutes):
    t = PokerTable(
        name=name,
        variant="hold_em",
        betting_structure="no-limit",
        stakes={"small_blind": 1, "big_blind": 2},
        max_players=6,
        creator_id=creator.id,
    )
    db.session.add(t)
    db.session.commit()
    t.last_activity = datetime.utcnow() - timedelta(minutes=idle_minutes)
    db.session.commit()
    return t


def test_purge_keeps_busy_recent_and_admin_tables(app):
    player = _user("player")
    admin = _user("admin", admin=True)
    old_empty = _table(player, "old empty", 90)
    _table(player, "fresh empty", 5)
    old_seated = _table(player, "old seated", 90)
    db.session.add(TableAccess(user_id=player.id, table_id=old_seated.id, buy_in_amount=80, seat_number=1))
    _table(admin, "house table", 90)
    old_spectated = _table(player, "old spectated", 90)
    db.session.add(TableAccess(user_id=player.id, table_id=old_spectated.id, is_spectator=True))
    db.session.commit()

    purged = TableManager.purge_empty_tables(idle_minutes=30)

    assert purged == 2
    remaining = {t.name for t in db.session.query(PokerTable).all()}
    assert remaining == {"fresh empty", "old seated", "house table"}
    assert db.session.query(TableAccess).filter_by(table_id=old_spectated.id).count() == 0
    assert db.session.query(PokerTable).get(old_empty.id) is None
