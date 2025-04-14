import sqlite3
import csv
from pathlib import Path

def create_database(db_file: Path, rank_files: list[Path]):
    """Create an SQLite database from multiple rank CSV files."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Create the hand_rankings table if it doesn’t exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hand_rankings (
            hand_str TEXT PRIMARY KEY,
            rank INTEGER,
            ordered_rank INTEGER
        )
    ''')
    
    # Process each rank file
    for rank_file in rank_files:
        with open(rank_file, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip the header row
            for row in reader:
                if len(row) != 9:
                    print(f"Skipping invalid row in {rank_file}: {row}")
                    continue
                # Extract the hand string (first 7 fields)
                hand_str = ''.join(field.strip() for field in row[:7])
                try:
                    # Extract rank and ordered_rank (last two fields)
                    rank = int(row[7])
                    ordered_rank = int(row[8])
                except ValueError as e:
                    print(f"Error in {rank_file}: {e} - Row: {row}")
                    continue
                # Insert into the database, ignoring duplicates
                cursor.execute('INSERT OR IGNORE INTO hand_rankings VALUES (?, ?, ?)', 
                               (hand_str, rank, ordered_rank))
    
    conn.commit()
    conn.close()

# Usage
db_file = Path('data/hand_rankings/hand_rankings.db')
rank_files = [Path(f'tools/generate_rankings/poker_hands/rank_{i}.csv') for i in range(1, 21)]
create_database(db_file, rank_files)

