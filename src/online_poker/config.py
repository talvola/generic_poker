"""Configuration settings for the online poker platform."""

import os
from typing import Optional


def _fix_database_url(url: str) -> str:
    """Fix Render's postgres:// URL to postgresql:// for SQLAlchemy 2.0+."""
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    """Base configuration class."""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database settings
    SQLALCHEMY_DATABASE_URI = _fix_database_url(
        os.environ.get('DATABASE_URL') or 'sqlite:///poker_platform.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # SocketIO settings
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    
    # Game settings
    DEFAULT_BANKROLL = int(os.environ.get('DEFAULT_BANKROLL', '1000'))
    TABLE_INACTIVE_TIMEOUT = int(os.environ.get('TABLE_INACTIVE_TIMEOUT', '30'))  # minutes
    PLAYER_DISCONNECT_TIMEOUT = int(os.environ.get('PLAYER_DISCONNECT_TIMEOUT', '60'))  # seconds
    
    # Security settings
    BCRYPT_LOG_ROUNDS = int(os.environ.get('BCRYPT_LOG_ROUNDS', '12'))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', '5'))
    
    # Performance settings
    MAX_CONCURRENT_TABLES = int(os.environ.get('MAX_CONCURRENT_TABLES', '100'))
    MAX_PLAYERS_PER_TABLE = int(os.environ.get('MAX_PLAYERS_PER_TABLE', '9'))
    MAX_SPECTATORS_PER_TABLE = int(os.environ.get('MAX_SPECTATORS_PER_TABLE', '20'))


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    TESTING = False
    
    # Use SQLite for development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///poker_dev.db'
    
    # Less strict security for development
    SESSION_COOKIE_SECURE = False
    BCRYPT_LOG_ROUNDS = 4  # Faster for development


class TestingConfig(Config):
    """Testing configuration."""
    
    TESTING = True
    DEBUG = True
    
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Faster password hashing for tests
    BCRYPT_LOG_ROUNDS = 4


class ProductionConfig(Config):
    """Production configuration."""
    
    DEBUG = False
    TESTING = False
    
    # Use PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = _fix_database_url(
        os.environ.get('DATABASE_URL') or 'postgresql://user:password@localhost/poker_platform'
    )
    
    # Strict security settings
    SESSION_COOKIE_SECURE = True
    BCRYPT_LOG_ROUNDS = 12
    
    # Production-specific settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> Config:
    """Get configuration class based on environment."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config.get(config_name, config['default'])