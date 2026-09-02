#!/usr/bin/env bash
# Render build script
set -o errexit

pip install -r requirements.txt
pip install -e .

# Initialize database tables (create_app already calls create_tables)
python -c "from app import create_app; create_app()"

# Run schema migrations for columns/tables that create_all() won't add
python tools/migrate_schema.py

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

# No seeding here: the production DB (Neon) persists across deploys, and the
# seed script creates well-known test accounts (one of them admin). Seed a
# fresh dev DB with `python tools/reset_db.py`; manage real accounts by
# running tools/manage_user.py against Neon from a shell (see CLAUDE.md).
