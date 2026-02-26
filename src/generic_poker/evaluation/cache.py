"""Cache managers for poker evaluation data."""

import logging
import sqlite3
from pathlib import Path

from generic_poker.evaluation.types import HandRanking

logger = logging.getLogger(__name__)


class SQLiteRankings:
    """Dict-like interface backed by SQLite for memory-efficient hand ranking lookups.

    Implements .get(key) to match the dict interface used by evaluators.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA cache_size=-8192")  # 8MB cache
        self._cursor = self._conn.cursor()

    def get(self, hand_str: str) -> HandRanking | None:
        """Look up a hand ranking by hand string."""
        self._cursor.execute(
            "SELECT rank, ordered_rank FROM hand_rankings WHERE hand_str = ?",
            (hand_str,),
        )
        result = self._cursor.fetchone()
        if result:
            return HandRanking(hand_str=hand_str, rank=result[0], ordered_rank=result[1])
        return None

    def items(self):
        """Iterate over all rankings (used by get_sample_hand)."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT hand_str, rank, ordered_rank FROM hand_rankings")
        for row in cursor:
            yield row[0], HandRanking(hand_str=row[0], rank=row[1], ordered_rank=row[2])

    def find_by_rank(self, rank: int, ordered_rank: int) -> str | None:
        """Find a hand string by rank and ordered_rank."""
        self._cursor.execute(
            "SELECT hand_str FROM hand_rankings WHERE rank = ? AND ordered_rank = ? LIMIT 1",
            (rank, ordered_rank),
        )
        result = self._cursor.fetchone()
        return result[0] if result else None

    def __contains__(self, key: str) -> bool:
        self._cursor.execute("SELECT 1 FROM hand_rankings WHERE hand_str = ? LIMIT 1", (key,))
        return self._cursor.fetchone() is not None

    def __del__(self):
        import contextlib

        with contextlib.suppress(Exception):
            self._conn.close()


class HandRankingsCache:
    """Singleton cache manager for hand rankings data.

    Uses SQLite databases for lookups instead of loading entire CSV files
    into memory. CSV files are automatically converted to SQLite on first access.
    """

    _instance = None
    _rankings: dict[str, SQLiteRankings] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_rankings(self, eval_type: str, rankings_file: Path) -> SQLiteRankings:
        """Get rankings for evaluation type, using SQLite for lookups."""
        if eval_type not in self._rankings:
            db_path = rankings_file.with_suffix(".db")
            if not db_path.exists():
                logger.info(f"Converting {rankings_file.name} to SQLite for {eval_type}")
                self._convert_csv_to_sqlite(rankings_file, db_path)
            logger.info(f"Opening SQLite rankings for {eval_type} from {db_path.name}")
            self._rankings[eval_type] = SQLiteRankings(db_path)
        else:
            logger.debug(f"Using cached SQLite rankings for {eval_type}")
        return self._rankings[eval_type]

    @staticmethod
    def _convert_csv_to_sqlite(csv_file: Path, db_path: Path) -> None:
        """Convert a CSV rankings file to SQLite database."""
        if not csv_file.exists():
            raise ValueError(f"Rankings file not found: {csv_file}")

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE hand_rankings ("
            "hand_str TEXT PRIMARY KEY, "
            "rank INTEGER NOT NULL, "
            "ordered_rank INTEGER NOT NULL)"
        )

        batch = []
        batch_size = 50000
        with open(csv_file) as f:
            next(f)  # Skip header
            for line in f:
                parts = line.strip().rsplit(",", 2)
                if len(parts) != 3:
                    continue
                hand_str = parts[0].replace(",", "")
                try:
                    rank = int(parts[1])
                    ordered_rank = int(parts[2])
                except ValueError:
                    continue
                batch.append((hand_str, rank, ordered_rank))
                if len(batch) >= batch_size:
                    conn.executemany(
                        "INSERT OR REPLACE INTO hand_rankings (hand_str, rank, ordered_rank) VALUES (?, ?, ?)",
                        batch,
                    )
                    batch.clear()

        if batch:
            conn.executemany(
                "INSERT OR REPLACE INTO hand_rankings (hand_str, rank, ordered_rank) VALUES (?, ?, ?)",
                batch,
            )

        conn.commit()
        logger.info(f"Created SQLite database: {db_path.name}")
        conn.close()
