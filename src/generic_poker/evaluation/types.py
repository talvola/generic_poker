# src/generic_poker/evaluation/types.py
"""Common types for poker evaluation."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class HandRanking:
    """Ranking data for a specific hand combination."""
    hand_str: str
    rank: int
    ordered_rank: Optional[int] = None
    description: Optional[str] = None