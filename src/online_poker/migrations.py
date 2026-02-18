"""Database migration utilities."""

from flask import Flask
from flask_migrate import init, migrate, upgrade

from .database import db, init_database
from .models import ChatFilter, ChatMessage, ChatModerationAction, GameHistory, PokerTable, Transaction, User


def init_migrations(app: Flask) -> None:
    """Initialize migration repository."""
    with app.app_context():
        try:
            init()
            print("Migration repository initialized.")
        except Exception as e:
            print(f"Migration repository already exists or error: {e}")


def create_migration(app: Flask, message: str = "Auto migration") -> None:
    """Create a new migration."""
    with app.app_context():
        try:
            migrate(message=message)
            print(f"Migration created: {message}")
        except Exception as e:
            print(f"Error creating migration: {e}")


def upgrade_database(app: Flask) -> None:
    """Upgrade database to latest migration."""
    with app.app_context():
        try:
            upgrade()
            print("Database upgraded successfully.")
        except Exception as e:
            print(f"Error upgrading database: {e}")


def setup_database(app: Flask, create_sample_data: bool = False) -> None:
    """Set up database with initial schema and optional sample data."""
    init_database(app)

    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created.")

        if create_sample_data:
            create_sample_data_if_needed()


def create_sample_data_if_needed() -> None:
    """Create sample data for development if database is empty."""
    # Check if we already have users
    if User.query.first() is not None:
        print("Sample data already exists.")
        return

    print("Creating sample data...")

    # Create sample users
    sample_users = [
        User("alice", "alice@example.com", "password123", 2000),
        User("bob", "bob@example.com", "password123", 1500),
        User("charlie", "charlie@example.com", "password123", 3000),
    ]

    for user in sample_users:
        db.session.add(user)

    db.session.commit()

    # Create sample table
    alice = User.query.filter_by(username="alice").first()
    if alice:
        sample_table = PokerTable(
            name="Alice's Texas Hold'em",
            variant="texas_holdem",
            betting_structure="No-Limit",
            stakes={"small_blind": 1, "big_blind": 2},
            max_players=6,
            creator_id=alice.id,
            is_private=False,
            allow_bots=True,
        )
        db.session.add(sample_table)
        db.session.commit()

    print("Sample data created successfully.")


def reset_database(app: Flask) -> None:
    """Reset database by dropping and recreating all tables."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database reset completed.")


def get_database_info(app: Flask) -> dict:
    """Get information about the current database."""
    with app.app_context():
        from sqlalchemy import inspect

        inspector = inspect(db.engine)

        info = {
            "database_url": app.config.get("SQLALCHEMY_DATABASE_URI"),
            "tables": inspector.get_table_names(),
            "user_count": User.query.count(),
            "table_count": PokerTable.query.count(),
            "transaction_count": Transaction.query.count(),
            "game_history_count": GameHistory.query.count(),
            "chat_message_count": ChatMessage.query.count(),
            "chat_moderation_count": ChatModerationAction.query.count(),
            "chat_filter_count": ChatFilter.query.count(),
        }
        return info
