#!/usr/bin/env python
"""
Promote or revoke admin privileges for a user.

Usage:
    python tools/make_admin.py <username>           # Promote to admin
    python tools/make_admin.py <username> --revoke   # Revoke admin
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from src.online_poker.database import db
from src.online_poker.models.user import User


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/make_admin.py <username> [--revoke]")
        sys.exit(1)

    username = sys.argv[1]
    revoke = "--revoke" in sys.argv

    app, _ = create_app()

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found")
            sys.exit(1)

        if revoke:
            if not user.is_admin:
                print(f"User '{username}' is not an admin")
                return
            user.is_admin = False
            db.session.commit()
            print(f"Revoked admin privileges from '{username}'")
        else:
            if user.is_admin:
                print(f"User '{username}' is already an admin")
                return
            user.is_admin = True
            db.session.commit()
            print(f"Promoted '{username}' to admin")


if __name__ == "__main__":
    main()
