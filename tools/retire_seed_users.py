#!/usr/bin/env python
"""Retire the well-known seed accounts on a live database (GitHub #5).

build.sh used to run seed_db.py on every deploy, so production carried
testuser/alice/bob/charlie/diana with password "password" and testuser as
admin. This deactivates them, revokes admin, and rotates their passwords to
random values so the credentials printed in CLAUDE.md stop working.

Usage (from WSL, against Neon):
    export DATABASE_URL='<neon -pooler URL>'
    python tools/retire_seed_users.py            # dry run: shows what would change
    python tools/retire_seed_users.py --apply    # actually do it

Refuses to demote the last admin — promote your own account first with
tools/make_admin.py.
"""

import os
import secrets
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app  # noqa: E402
from src.online_poker.database import db  # noqa: E402
from src.online_poker.models.user import User  # noqa: E402

SEED_USERNAMES = ["testuser", "alice", "bob", "charlie", "diana"]


def main() -> int:
    apply = "--apply" in sys.argv
    app, _ = create_app()
    with app.app_context():
        seed_users = User.query.filter(User.username.in_(SEED_USERNAMES)).all()
        if not seed_users:
            print("No seed accounts found; nothing to do.")
            return 0

        other_admins = User.query.filter(User.is_admin == True, User.username.notin_(SEED_USERNAMES)).all()  # noqa: E712
        demoting_admin = any(u.is_admin for u in seed_users)
        if demoting_admin and not other_admins:
            print("Refusing: a seed account is the ONLY admin. Promote your own account first:")
            print("    python tools/make_admin.py <your-username>")
            return 1

        for u in seed_users:
            flags = []
            if u.is_active:
                flags.append("deactivate")
            if u.is_admin:
                flags.append("revoke admin")
            flags.append("rotate password")
            print(f"  - {u.username}: {', '.join(flags)}")
            if apply:
                u.is_active = False
                u.is_admin = False
                u.set_password(secrets.token_urlsafe(24))

        if apply:
            db.session.commit()
            print(f"Retired {len(seed_users)} seed account(s).")
        else:
            print("Dry run. Re-run with --apply to make these changes.")
        if other_admins:
            print("Remaining admins: " + ", ".join(a.username for a in other_admins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
