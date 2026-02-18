#!/usr/bin/env bash
# Render build script
set -o errexit

pip install -r requirements.txt
pip install -e .

# Initialize database tables (create_app already calls create_tables)
python -c "from app import create_app; create_app()"

# Seed database with test users (pipe 'y' to handle "already seeded" prompt)
echo "y" | python tools/seed_db.py
