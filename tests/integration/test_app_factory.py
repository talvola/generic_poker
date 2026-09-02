"""App-factory wiring that must hold in production (GitHub #4, #7)."""

import importlib
import os
import sys

import pytest
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # repo root, for app.py

from app import create_app  # noqa: E402
from src.online_poker.config import TestingConfig  # noqa: E402
from src.online_poker.services.game_orchestrator import game_orchestrator  # noqa: E402


class _MemoryTesting(TestingConfig):
    # Shared in-memory SQLite so create_app's create_all and requests see one DB
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}


class _TestRoutesOff(_MemoryTesting):
    ENABLE_TEST_ROUTES = False


@pytest.fixture
def make_app():
    apps = []

    def _make(config_class):
        app, _socketio = create_app(config_class)
        apps.append(app)
        return app

    yield _make
    for app in apps:
        with app.app_context():
            app.extensions["sqlalchemy"].drop_all()
    game_orchestrator.sessions.clear()


def test_test_routes_absent_unless_enabled(make_app):
    app = make_app(_TestRoutesOff)
    client = app.test_client()
    assert client.get("/api/test/status").status_code == 404
    assert client.post("/api/test/cleanup").status_code == 404


def test_test_routes_present_when_enabled(make_app):
    app = make_app(_MemoryTesting)
    client = app.test_client()
    assert client.get("/api/test/status").status_code == 200


def test_base_config_keeps_test_routes_off(monkeypatch):
    monkeypatch.delenv("ENABLE_TEST_ROUTES", raising=False)
    import src.online_poker.config as cfg

    importlib.reload(cfg)
    assert cfg.Config.ENABLE_TEST_ROUTES is False
    assert cfg.ProductionConfig.ENABLE_TEST_ROUTES is False
    assert cfg.DevelopmentConfig.ENABLE_TEST_ROUTES is True


class _NoSecretKey(_MemoryTesting):
    SECRET_KEY = None


def test_refuses_to_start_without_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(_NoSecretKey)


def test_cross_site_writes_are_rejected(make_app):
    app = make_app(_MemoryTesting)
    client = app.test_client()
    body = {"username": "nobody", "password": "nothing123"}
    assert client.post("/auth/api/login", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/auth/api/login", json=body, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    # Same-origin and header-less requests reach the handler (401: bad credentials, not 403)
    assert client.post("/auth/api/login", json=body, headers={"Origin": "http://localhost"}).status_code != 403
    assert client.post("/auth/api/login", json=body).status_code != 403
    # Reads are never blocked
    assert client.get("/auth/check-auth", headers={"Origin": "https://evil.example"}).status_code != 403


def test_socketio_cors_comes_from_config(make_app):
    class _Cors(_MemoryTesting):
        SOCKETIO_CORS_ALLOWED_ORIGINS = "https://a.example, https://b.example"

    app = make_app(_Cors)
    sio = app.extensions["socketio"]
    assert sio.server.eio.cors_allowed_origins == ["https://a.example", "https://b.example"]
