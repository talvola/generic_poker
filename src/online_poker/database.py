"""Database configuration and connection management."""

import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy instance
db = SQLAlchemy()
migrate = Migrate()


def init_database(app: Flask) -> None:
    """Initialize database with Flask app."""
    # Database configuration
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Default to SQLite for development
        basedir = os.path.abspath(os.path.dirname(__file__))
        database_url = f"sqlite:///{os.path.join(basedir, '../../poker_platform.db')}"

    # Fix Render's postgres:// URL to postgresql:// for SQLAlchemy 2.0+
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions only if not already initialized
    if not hasattr(app, "extensions") or "sqlalchemy" not in app.extensions:
        db.init_app(app)
    if not hasattr(app, "extensions") or "migrate" not in app.extensions:
        migrate.init_app(app, db)


def create_tables() -> None:
    """Create all database tables."""
    db.create_all()


def drop_tables() -> None:
    """Drop all database tables."""
    db.drop_all()


def get_db_session():
    """Get database session."""
    return db.session
