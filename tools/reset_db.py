#!/usr/bin/env python
"""
Reset the poker platform database to a clean state.

This script drops all tables, recreates them, and seeds with fresh test data.
Use this during development to quickly reset to a known good state.

Usage:
    python tools/reset_db.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from init_db import init_database
from seed_db import seed_database

def reset_database():
    """Reset database to clean seeded state."""
    print("=" * 60)
    print("🔄 RESETTING POKER PLATFORM DATABASE")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Drop all existing tables and data")
    print("  2. Create fresh table schema")
    print("  3. Seed with test data")
    print()

    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return

    print()
    print("-" * 60)
    print("Step 1: Initializing database")
    print("-" * 60)
    print()
    init_database()

    print()
    print("-" * 60)
    print("Step 2: Seeding database")
    print("-" * 60)
    print()
    seed_database()

    print()
    print("=" * 60)
    print("✅ DATABASE RESET COMPLETE!")
    print("=" * 60)
    print()
    print("Your database is now in a clean state with test data.")
    print("Start the server with: python app.py")

if __name__ == '__main__':
    reset_database()
