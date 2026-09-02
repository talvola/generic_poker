"""WSGI entry point for production deployment (gunicorn + eventlet)."""

import eventlet

eventlet.monkey_patch()

# psycopg2 is a C extension with its own sockets, so eventlet.monkey_patch()
# does NOT make it cooperative — every query would block the single eventlet
# worker (and therefore every other player) for the whole round trip. Harmless
# when Postgres was ~1ms away on Render's internal network; not harmless over
# TLS to Neon. patch_psycopg() makes libpq yield to the hub instead.
from psycogreen.eventlet import patch_psycopg  # noqa: E402

patch_psycopg()

from app import create_app  # noqa: E402
from src.online_poker.config import get_config  # noqa: E402

# get_config() honors FLASK_ENV; without it the base Config ran in production
# (no Secure cookies, no production-only settings) — GitHub #7.
app, socketio = create_app(get_config())
