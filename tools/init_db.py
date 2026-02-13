#!/usr/bin/env python
"""
Initialize the poker platform database.

This script creates all necessary database tables for the online poker platform.
Run this before seeding or starting the application for the first time.

Usage:
    python tools/init_db.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from src.online_poker.database import db

def init_database():
    """Initialize database tables."""
    print("🎲 Initializing Poker Platform Database...")
    print()

    # Create app
    app, socketio = create_app()

    with app.app_context():
        # Get database path
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"Database URI: {db_uri}")
        print()

        # Drop all existing tables (fresh start)
        print("Dropping existing tables...")
        db.drop_all()
        print("✓ Tables dropped")
        print()

        # Create all tables
        print("Creating tables...")
        db.create_all()
        print("✓ Tables created")
        print()

        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        print(f"Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")
        print()

        print("✅ Database initialized successfully!")
        print()
        print("Next steps:")
        print("  1. Run 'python tools/seed_db.py' to add test data")
        print("  2. Start the server with 'python app.py'")

if __name__ == '__main__':
    init_database()
