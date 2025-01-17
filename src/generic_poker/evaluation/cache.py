"""Cache managers for poker evaluation data."""
import logging
from pathlib import Path
from typing import Dict
from generic_poker.evaluation.types import HandRanking

logger = logging.getLogger(__name__)

class HandRankingsCache:
    """Singleton cache manager for hand rankings data."""
    _instance = None
    _rankings: Dict[str, Dict[str, HandRanking]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HandRankingsCache, cls).__new__(cls)
        return cls._instance
    
    def get_rankings(self, eval_type: str, rankings_file: Path) -> Dict[str, HandRanking]:
        """Get rankings for evaluation type, loading from file if needed."""
        if eval_type not in self._rankings:
            logger.info(f"Loading rankings for {eval_type} from {rankings_file}")
            self._rankings[eval_type] = self._load_rankings(rankings_file)
        else:
            logger.debug(f"Using cached rankings for {eval_type}")
        return self._rankings[eval_type]
    
    def _load_rankings(self, rankings_file: Path) -> Dict[str, HandRanking]:
        """Load rankings from CSV file."""
        if not rankings_file.exists():
            raise ValueError(f"Rankings file not found: {rankings_file}")
            
        rankings = {}
        with open(rankings_file) as f:
            next(f)  # Skip header
            for line in f:
                parts = line.strip().rsplit(',', 2)
                if len(parts) != 3:
                    continue
                hand_str = parts[0].replace(',', '')
                try:
                    rank = int(parts[1])
                    ordered_rank = int(parts[2])
                except ValueError:
                    continue
                    
                rankings[hand_str] = HandRanking(
                    hand_str=hand_str,
                    rank=rank,
                    ordered_rank=ordered_rank
                )
        return rankings