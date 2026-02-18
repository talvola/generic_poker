# src/generic_poker/evaluation/types.py
"""Common types for poker evaluation."""

from dataclasses import dataclass


@dataclass
class HandRanking:
    """Ranking data for a specific hand combination."""

    hand_str: str
    rank: int
    ordered_rank: int | None = None
    description: str | None = None
