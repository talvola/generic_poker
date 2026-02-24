"""Main Flask application for the Online Poker Platform."""

import contextlib
import logging
import os

from flask import Flask, jsonify, redirect, url_for
from flask_socketio import SocketIO
from src.online_poker.auth import init_login_manager
from src.online_poker.config import Config, get_config

# Import our modules
from src.online_poker.database import create_tables, db, init_database
from src.online_poker.extensions import limiter
from src.online_poker.routes.admin_routes import admin_bp
from src.online_poker.routes.auth_routes import auth_bp
from src.online_poker.routes.game_routes import game_bp
from src.online_poker.routes.lobby_routes import lobby_bp, register_lobby_socket_events
from src.online_poker.routes.table_routes import table_bp
from src.online_poker.routes.test_routes import test_bp
from src.online_poker.services.websocket_manager import init_websocket_manager


def _cleanup_stale_sessions(app):
    """Clean up stale game sessions on startup.

    Finds GameSessionState records that are still marked active but whose
    last_activity is older than the configured threshold. For each:
    - Cashes out players (adds current_stack back to bankroll)
    - Marks TableAccess as inactive
    - Marks GameSessionState as inactive
    """
    from datetime import datetime, timedelta

    from src.online_poker.database import db
    from src.online_poker.models.game_session_state import GameSessionState
    from src.online_poker.models.table_access import TableAccess
    from src.online_poker.models.user import User

    threshold_hours = app.config.get("STALE_SESSION_CLEANUP_HOURS", 2)
    cutoff = datetime.utcnow() - timedelta(hours=threshold_hours)

    try:
        stale_sessions = (
            db.session.query(GameSessionState)
            .filter(
                GameSessionState.is_active == True,
                GameSessionState.last_activity < cutoff,
            )
            .all()
        )

        if not stale_sessions:
            return

        cleaned = 0
        for state in stale_sessions:
            # Cash out all active players at this table
            active_accesses = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == state.table_id,
                    TableAccess.is_active == True,
                    TableAccess.is_spectator == False,
                )
                .all()
            )

            for access in active_accesses:
                if access.current_stack and access.current_stack > 0:
                    user = db.session.query(User).filter_by(id=access.user_id).first()
                    if user:
                        user.bankroll += access.current_stack
                access.is_active = False
                access.is_ready = False

            state.is_active = False
            cleaned += 1

        db.session.commit()
        if cleaned > 0:
            print(f"Cleaned up {cleaned} stale game session(s) (inactive > {threshold_hours}h)")

    except Exception as e:
        print(f"Warning: Failed to clean up stale sessions: {e}")
        try:
            db.session.rollback()
        except Exception as rollback_err:
            print(f"Warning: Failed to rollback: {rollback_err}")


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)

    # Initialize SocketIO (use default async_mode for better compatibility)
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode=None,  # Let SocketIO choose the best async mode
        logger=True,
        engineio_logger=True,
        ping_timeout=60,
        ping_interval=25,
    )

    # Initialize authentication
    init_login_manager(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(lobby_bp, url_prefix="/")
    app.register_blueprint(table_bp, url_prefix="/table")
    app.register_blueprint(game_bp, url_prefix="/game")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(test_bp)  # Test-only routes for E2E testing

    # Initialize WebSocket manager
    init_websocket_manager(socketio)

    # Register template filters
    @app.template_filter("format_variant")
    def format_variant(variant):
        """Format poker variant name for display."""
        variants = {
            "hold_em": "Texas Hold'em",
            "omaha": "Omaha",
            "omaha_8": "Omaha Hi-Lo",
            "7_card_stud": "7-Card Stud",
            "7_card_stud_8": "7-Card Stud Hi-Lo",
            "razz": "Razz",
            "mexican_poker": "Mexican Poker",
            "horse": "HORSE",
            "8_game_mix": "8-Game Mix",
        }
        return variants.get(variant, variant.replace("_", " ").title())

    @app.template_filter("format_structure")
    def format_structure(structure):
        """Format betting structure for display."""
        return structure.replace("-", " ").replace("_", " ").title()

    # Register WebSocket events
    register_lobby_socket_events(socketio)

    # Initialize database
    init_database(app)

    # Create database tables
    with app.app_context():
        create_tables()
        _cleanup_stale_sessions(app)

    # Error handler for rate limiting
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({"success": False, "message": "Too many requests. Please try again later."}), 429

    # Root route
    @app.route("/")
    def index():
        """Redirect to lobby."""
        return redirect(url_for("lobby.index"))

    return app, socketio


def setup_logging():
    """Set up logging for the application."""
    handlers = [logging.StreamHandler()]
    # Only add file handler in development (Render filesystem is ephemeral)
    if os.environ.get("FLASK_ENV") != "production":
        with contextlib.suppress(OSError):
            handlers.append(logging.FileHandler("poker_platform.log"))
    logging.basicConfig(
        level=logging.INFO if os.environ.get("FLASK_ENV") == "production" else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


if __name__ == "__main__":
    setup_logging()

    config_class = get_config()
    app, socketio = create_app(config_class)

    print("🎲 Starting Online Poker Platform...")
    print("📍 Access the lobby at: http://localhost:5000")
    print("🔧 Debug mode: ON")

    socketio.run(
        app,
        debug=True,
        use_reloader=False,  # Disable reloader to fix WebSocket issues
        host="0.0.0.0",
        port=5000,
        allow_unsafe_werkzeug=True,
    )
