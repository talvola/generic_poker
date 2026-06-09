#!/usr/bin/env python
"""
Seed the poker platform database with test data.

This script populates the database with sample users, tables, and games
for development and testing purposes.

Usage:
    python tools/seed_db.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
import string

from app import create_app
from src.online_poker.database import db
from src.online_poker.models.chat import ChatMessage, ChatModerationAction
from src.online_poker.models.game_history import GameHistory
from src.online_poker.models.game_session_state import GameSessionState
from src.online_poker.models.table import PokerTable
from src.online_poker.models.table_access import TableAccess
from src.online_poker.models.transaction import Transaction
from src.online_poker.models.user import User


def generate_invite_code(length=6):
    """Generate random invite code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def delete_table(table):
    """Delete a table and all associated records, cashing out any seated players."""
    for access in TableAccess.query.filter_by(table_id=table.id, is_active=True).all():
        if access.current_stack and access.current_stack > 0:
            user = User.query.filter_by(id=access.user_id).first()
            if user:
                user.bankroll += access.current_stack

    # Null out transaction references (keep audit trail), then delete dependents
    Transaction.query.filter_by(table_id=table.id).update({"table_id": None})
    ChatMessage.query.filter_by(table_id=table.id).delete()
    ChatModerationAction.query.filter_by(table_id=table.id).delete()
    GameHistory.query.filter_by(table_id=table.id).delete()
    GameSessionState.query.filter_by(table_id=table.id).delete()
    TableAccess.query.filter_by(table_id=table.id).delete()
    db.session.delete(table)


def seed_database():
    """Seed database with test data."""
    print("🎲 Seeding Poker Platform Database...")
    print()

    app, socketio = create_app()

    with app.app_context():
        # Check if database is already seeded
        existing_users = User.query.count()
        if existing_users > 0:
            print(f"⚠️  Database already has {existing_users} user(s).")
            response = input("Continue anyway? This will add more data. (y/n): ")
            if response.lower() != "y":
                print("Aborted.")
                return

        print("Creating test users...")
        users = []

        # Create test users with varying bankrolls
        test_users = [
            ("testuser", "test@example.com", "password", 800),
            ("alice", "alice@example.com", "password", 1000),
            ("bob", "bob@example.com", "password", 1500),
            ("charlie", "charlie@example.com", "password", 500),
            ("diana", "diana@example.com", "password", 2000),
        ]

        for username, email, password, bankroll in test_users:
            # Check if user already exists
            existing = User.query.filter_by(username=username).first()
            if existing:
                print(f"  - {username} (already exists, skipping)")
                users.append(existing)
                continue

            user = User(username=username, email=email, password=password, bankroll=bankroll)
            db.session.add(user)
            users.append(user)
            print(f"  - {username} (${bankroll})")

        db.session.commit()

        # Make testuser an admin
        testuser = User.query.filter_by(username="testuser").first()
        if testuser and not testuser.is_admin:
            testuser.is_admin = True
            db.session.commit()
            print("  - testuser promoted to admin")

        print(f"✓ Created/verified {len(users)} users")
        print()

        print("Creating test tables...")
        tables = []

        # Table configurations with proper stakes
        table_configs = [
            {
                "name": "Omaha",
                "variant": "omaha_8",  # Omaha Hi-Lo
                "betting_structure": "limit",
                "stakes": {"small_bet": 2, "big_bet": 4, "ante": 0},
                "max_players": 6,
                "is_private": False,
                "allow_bots": True,
                "creator": users[0],  # testuser
                "players": 2,  # Simulate 2 players joined
            },
            {
                "name": "Texas Hold'em - Micro Stakes",
                "variant": "hold_em",
                "betting_structure": "no-limit",
                "stakes": {"small_blind": 1, "big_blind": 2},
                "max_players": 9,
                "is_private": False,
                "allow_bots": False,
                "creator": users[1],  # alice
                "players": 0,
            },
            {
                "name": "7-Card Stud - High Stakes",
                "variant": "7_card_stud",
                "betting_structure": "limit",
                "stakes": {"small_bet": 10, "big_bet": 20, "ante": 1},
                "max_players": 8,
                "is_private": False,
                "allow_bots": True,
                "creator": users[2],  # bob
                "players": 0,
            },
            {
                "name": "Private Game",
                "variant": "hold_em",
                "betting_structure": "pot-limit",
                "stakes": {"small_blind": 5, "big_blind": 10},
                "max_players": 6,
                "is_private": True,
                "allow_bots": False,
                "creator": users[3],  # charlie
                "players": 0,
            },
        ]

        for config in table_configs:
            # Idempotency: skip if this seeded table already exists, and remove
            # duplicates accumulated from earlier deploys (keep the oldest)
            existing = (
                PokerTable.query.filter_by(name=config["name"], creator_id=config["creator"].id)
                .order_by(PokerTable.created_at)
                .all()
            )
            if existing:
                for duplicate in existing[1:]:
                    delete_table(duplicate)
                if len(existing) > 1:
                    db.session.commit()
                    print(f"  - {config['name']} (removed {len(existing) - 1} duplicate(s))")
                else:
                    print(f"  - {config['name']} (already exists, skipping)")
                tables.append(existing[0])
                continue

            table = PokerTable(
                name=config["name"],
                variant=config["variant"],
                betting_structure=config["betting_structure"],
                stakes=config["stakes"],  # Pass as dict, not JSON
                max_players=config["max_players"],
                creator_id=config["creator"].id,
                is_private=config["is_private"],
                allow_bots=config["allow_bots"],
                password=None,  # No password protection for now
            )
            db.session.add(table)
            tables.append(table)

            # Add player access records (after commit so table.id exists)
            db.session.commit()  # Commit table first to get ID

            for i in range(config["players"]):
                if i < len(users):
                    access = TableAccess(
                        table_id=table.id,
                        user_id=users[i].id,
                        is_spectator=False,
                        seat_number=i,  # Assign seats in order
                        buy_in_amount=200,
                    )
                    db.session.add(access)

            stakes_display = f"${config['stakes'].get('small_bet', config['stakes'].get('small_blind', 0))}/\
${config['stakes'].get('big_bet', config['stakes'].get('big_blind', 0))}"
            print(f"  - {config['name']} ({config['variant']}, {config['betting_structure']}, {stakes_display})")

        db.session.commit()
        print(f"✓ Created/verified {len(tables)} tables")
        print()

        print("✅ Database seeded successfully!")
        print()
        print("Test credentials:")
        print("  Username: testuser")
        print("  Password: password")
        print()
        print("Other users: alice, bob, charlie, diana (all with password: 'password')")
        print()
        if any(t.is_private for t in tables):
            print("Private table invite codes:")
            for table in tables:
                if table.is_private:
                    print(f"  - {table.name}: {table.invite_code}")
            print()
        print("You can now start the server with 'python app.py'")


if __name__ == "__main__":
    seed_database()
