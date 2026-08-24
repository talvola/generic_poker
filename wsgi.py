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

app, socketio = create_app()
