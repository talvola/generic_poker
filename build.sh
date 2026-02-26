#!/usr/bin/env bash
# Render build script
set -o errexit

pip install -r requirements.txt
pip install -e .

# Initialize database tables (create_app already calls create_tables)
python -c "from app import create_app; create_app()"

# Run schema migrations for columns that create_all() won't add to existing tables
python -c "
from app import create_app
from src.online_poker.database import db
from sqlalchemy import text

app, _ = create_app()
with app.app_context():
    # Add is_admin column to users table if it doesn't exist
    try:
        db.session.execute(text('ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE'))
        db.session.commit()
        print('Added is_admin column to users table')
    except Exception as e:
        db.session.rollback()
        if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
            print('is_admin column already exists')
        else:
            print(f'Note: {e}')

    # Add is_mixed_game column to poker_tables if it doesn't exist
    try:
        db.session.execute(text('ALTER TABLE poker_tables ADD COLUMN is_mixed_game BOOLEAN NOT NULL DEFAULT FALSE'))
        db.session.commit()
        print('Added is_mixed_game column to poker_tables')
    except Exception as e:
        db.session.rollback()
        if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
            print('is_mixed_game column already exists')
        else:
            print(f'Note: {e}')

    # Add mixed game rotation columns to game_session_state if they don't exist
    for col in ['current_variant_index INTEGER', 'hands_in_current_variant INTEGER', 'orbit_size INTEGER']:
        col_name = col.split()[0]
        try:
            db.session.execute(text(f'ALTER TABLE game_session_state ADD COLUMN {col}'))
            db.session.commit()
            print(f'Added {col_name} column to game_session_state')
        except Exception as e:
            db.session.rollback()
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                print(f'{col_name} column already exists')
            else:
                print(f'Note: {e}')

    # Create disabled_variants table if it doesn't exist
    try:
        db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS disabled_variants (
                id VARCHAR(36) PRIMARY KEY,
                variant_name VARCHAR(100) UNIQUE NOT NULL,
                reason TEXT,
                disabled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                disabled_by VARCHAR(36) NOT NULL REFERENCES users(id)
            )
        '''))
        db.session.commit()
        print('Ensured disabled_variants table exists')
    except Exception as e:
        db.session.rollback()
        print(f'Note: {e}')
"

# Pre-convert hand ranking CSVs to SQLite for memory-efficient evaluation
python -c "
from pathlib import Path
from generic_poker.evaluation.cache import HandRankingsCache
cache = HandRankingsCache()
csv_dir = Path('data/hand_rankings')
for csv_file in sorted(csv_dir.glob('all_card_hands_ranked_*.csv')):
    db_path = csv_file.with_suffix('.db')
    if not db_path.exists():
        print(f'Converting {csv_file.name}...')
        cache._convert_csv_to_sqlite(csv_file, db_path)
    else:
        print(f'Already exists: {db_path.name}')
print('Hand ranking conversion complete')
"

# Seed database with test users (pipe 'y' to handle "already seeded" prompt)
echo "y" | python tools/seed_db.py
