"""Configuration settings for the online poker platform."""

import os


def _fix_database_url(url: str) -> str:
    """Fix Render's postgres:// URL to postgresql:// for SQLAlchemy 2.0+."""
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _engine_options(url: str) -> dict:
    """SQLAlchemy engine options tuned for Neon (serverless Postgres, PgBouncer pooler).

    SQLite gets none of it — pool sizing and libpq connect args are Postgres-only.
    """
    if not url.startswith("postgresql"):
        return {}
    return {
        # A Neon compute that scaled to zero drops idle connections; pre_ping
        # discards the dead ones instead of raising on the next query.
        "pool_pre_ping": True,
        "pool_recycle": 300,
        # Keep the pool small — the pooled endpoint multiplexes for us.
        "pool_size": 5,
        "max_overflow": 5,
        "connect_args": {
            # Wake-from-idle is ~500ms; 10s leaves room for a slow cold start.
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    }


class Config:
    """Base configuration class."""

    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # Database settings
    SQLALCHEMY_DATABASE_URI = _fix_database_url(os.environ.get("DATABASE_URL") or "sqlite:///poker_platform.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)

    # Session settings
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # SocketIO settings
    SOCKETIO_ASYNC_MODE = "threading"
    # Comma-separated origins allowed to open a socket, or "*". Production
    # narrows this to the site's own origin (cookie-authenticated sockets from
    # any origin would be CSRF).
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    # Verbose socket.io / engine.io frame logging (very noisy)
    SOCKETIO_LOGGING = os.environ.get("SOCKETIO_LOGGING", "false").lower() == "true"

    # Game settings
    DEFAULT_BANKROLL = int(os.environ.get("DEFAULT_BANKROLL", "1000"))
    TABLE_INACTIVE_TIMEOUT = int(os.environ.get("TABLE_INACTIVE_TIMEOUT", "30"))  # minutes

    # Bot settings — "mc" (Monte Carlo equity) or "simple" (random weighted)
    BOT_TYPE = os.environ.get("BOT_TYPE", "mc")

    # Debug: allow the /api/debug stacked/seeded deck endpoints (T009). Off by
    # default; enable per-environment (dev/testing) or via env var to reproduce
    # specific deal scenarios during tester sessions. Always gated behind admin.
    DEBUG_ALLOW_STACKED_DECK = os.environ.get("DEBUG_ALLOW_STACKED_DECK", "false").lower() == "true"

    # Test-only /api/test routes (E2E state reset). Unauthenticated by design, so
    # they are OFF unless a dev/testing config or env var turns them on (GitHub #4).
    ENABLE_TEST_ROUTES = os.environ.get("ENABLE_TEST_ROUTES", "false").lower() == "true"

    # Timeout settings
    ACTION_TIMEOUT_ENABLED = os.environ.get("ACTION_TIMEOUT_ENABLED", "false").lower() == "true"
    ACTION_TIMEOUT_SECONDS = int(os.environ.get("ACTION_TIMEOUT_SECONDS", "30"))
    DISCONNECT_AUTO_FOLD_SECONDS = int(os.environ.get("DISCONNECT_AUTO_FOLD_SECONDS", "30"))
    DISCONNECT_REMOVAL_MINUTES = int(os.environ.get("DISCONNECT_REMOVAL_MINUTES", "10"))

    # Auth session settings
    SESSION_TIMEOUT_HOURS = int(os.environ.get("SESSION_TIMEOUT_HOURS", "24"))
    REMEMBER_ME_DAYS = int(os.environ.get("REMEMBER_ME_DAYS", "30"))
    RESET_TOKEN_EXPIRY_HOURS = int(os.environ.get("RESET_TOKEN_EXPIRY_HOURS", "1"))

    # Hand history settings
    HAND_HISTORY_DEFAULT_LIMIT = int(os.environ.get("HAND_HISTORY_DEFAULT_LIMIT", "20"))
    HAND_HISTORY_MAX_LIMIT = int(os.environ.get("HAND_HISTORY_MAX_LIMIT", "100"))

    # Security settings
    BCRYPT_LOG_ROUNDS = int(os.environ.get("BCRYPT_LOG_ROUNDS", "12"))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))

    # Rate limiting settings
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "60/minute")
    RATELIMIT_AUTH_LOGIN = os.environ.get("RATELIMIT_AUTH_LOGIN", "5/minute")
    RATELIMIT_AUTH_REGISTER = os.environ.get("RATELIMIT_AUTH_REGISTER", "3/hour")
    RATELIMIT_AUTH_RESET = os.environ.get("RATELIMIT_AUTH_RESET", "3/hour")
    RATELIMIT_TABLE_CREATE = os.environ.get("RATELIMIT_TABLE_CREATE", "10/hour")

    # Session recovery settings
    STALE_SESSION_CLEANUP_HOURS = int(os.environ.get("STALE_SESSION_CLEANUP_HOURS", "2"))

    # Performance settings
    MAX_CONCURRENT_TABLES = int(os.environ.get("MAX_CONCURRENT_TABLES", "100"))
    MAX_PLAYERS_PER_TABLE = int(os.environ.get("MAX_PLAYERS_PER_TABLE", "9"))
    MAX_SPECTATORS_PER_TABLE = int(os.environ.get("MAX_SPECTATORS_PER_TABLE", "20"))


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False

    # Less strict security for development
    SESSION_COOKIE_SECURE = False
    BCRYPT_LOG_ROUNDS = 4  # Faster for development

    # Disable action timeouts by default for easier debugging
    # Override with ACTION_TIMEOUT_ENABLED=true env var if needed
    ACTION_TIMEOUT_ENABLED = os.environ.get("ACTION_TIMEOUT_ENABLED", "false").lower() == "true"

    # Disable rate limiting for development
    RATELIMIT_ENABLED = False

    # Allow the debug stacked-deck endpoints in development by default
    DEBUG_ALLOW_STACKED_DECK = os.environ.get("DEBUG_ALLOW_STACKED_DECK", "true").lower() == "true"

    # E2E tests run against `python app.py` (this config) and need /api/test
    ENABLE_TEST_ROUTES = os.environ.get("ENABLE_TEST_ROUTES", "true").lower() == "true"

    SOCKETIO_LOGGING = os.environ.get("SOCKETIO_LOGGING", "true").lower() == "true"


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    DEBUG = True

    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

    # Faster password hashing for tests
    BCRYPT_LOG_ROUNDS = 4

    # Disable action timeout in tests
    ACTION_TIMEOUT_ENABLED = False

    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False

    # Allow the debug stacked-deck endpoints in tests
    DEBUG_ALLOW_STACKED_DECK = True
    ENABLE_TEST_ROUTES = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False

    # Use PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = _fix_database_url(
        os.environ.get("DATABASE_URL") or "postgresql://user:password@localhost/poker_platform"
    )

    # Strict security settings
    SESSION_COOKIE_SECURE = True
    BCRYPT_LOG_ROUNDS = 12
    # No dev fallback: create_app refuses to start without a real SECRET_KEY
    SECRET_KEY = os.environ.get("SECRET_KEY")
    # Only the site itself may open cookie-authenticated sockets
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "https://generic-poker.onrender.com")
    SOCKETIO_LOGGING = False

    # Production-specific settings
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)


# Configuration mapping
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(config_name: str | None = None) -> Config:
    """Get configuration class based on environment."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    return config.get(config_name, config["default"])
