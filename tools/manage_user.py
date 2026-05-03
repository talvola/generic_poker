#!/usr/bin/env python
"""
Create or update a user account.

Usage:
    python tools/manage_user.py --username NAME --password PASS --bankroll AMOUNT
    python tools/manage_user.py --username NAME --bankroll AMOUNT   # update only
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from src.online_poker.database import db
from src.online_poker.models.user import User


def manage_user(username, password=None, bankroll=None, email=None):
    app, _ = create_app()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            if bankroll is not None:
                user.bankroll = bankroll
            if password is not None:
                user.set_password(password)
            db.session.commit()
            print(f"Updated {username}: bankroll=${user.bankroll}")
        else:
            if not password:
                print(f"Error: --password required when creating new user '{username}'")
                sys.exit(1)
            user = User(
                username=username,
                email=email or f"{username}@example.com",
                password=password,
                bankroll=bankroll or 1000,
            )
            db.session.add(user)
            db.session.commit()
            print(f"Created {username}: bankroll=${user.bankroll}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password")
    parser.add_argument("--bankroll", type=int)
    parser.add_argument("--email")
    args = parser.parse_args()
    manage_user(args.username, args.password, args.bankroll, args.email)
