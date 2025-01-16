"""Base class for poker hand evaluators."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
import csv

from generic_poker.core.card import Card


@dataclass
class HandRanking:
    """
    Ranking data for a specific hand combination.
    
    Attributes:
        hand_str: String representation of hand
        rank: Primary rank (e.g., straight flush = 1)
        ordered_rank: Secondary ordering within rank
        description: Optional human-readable description
    """
    hand_str: str
    rank: int
    ordered_rank: Optional[int] = None
    description: Optional[str] = None


class BaseEvaluator(ABC):
    """Base class for hand evaluators."""
    
    RANK_ONLY_TYPES = {'49', 'zero', '6', '21', 'low_pip_6_cards', '58', '21_6', 'zero_6'}
    
    def __init__(self, rankings_file: Path, eval_type: str):
        """
        Initialize evaluator.
        
        Args:
            rankings_file: Path to CSV file with hand rankings
            eval_type: Type of evaluation (used to determine rank-only status)
        """
        self.rankings: Dict[str, HandRanking] = {}
        self.rank_only = eval_type in self.RANK_ONLY_TYPES
        self._load_rankings(rankings_file)
        
    def _cards_to_string(self, cards: List[Card]) -> str:
        """
        Convert cards to string for ranking lookup.
        
        For rank-only formats: "AAAT8"
        For regular formats: "AsKsQsJsTs"
        """
        if self.rank_only:
            return ''.join(card.rank.value for card in cards)
        else:
            return ''.join(f"{card.rank.value}{card.suit.value}" for card in cards)
            
    @abstractmethod
    def evaluate(
        self,
        cards: List[Card],
        wild_cards: Optional[List[Card]] = None
    ) -> Optional[HandRanking]:
        """Evaluate a poker hand."""
        pass
        
    @abstractmethod
    def _sort_cards(self, cards: List[Card]) -> List[Card]:
        """Sort cards in canonical order for this game type."""
        pass
        
    def _load_rankings(self, rankings_file: Path) -> None:
        """Load rankings from CSV file and store in optimized format."""
        if not rankings_file.exists():
            raise ValueError(f"Rankings file not found: {rankings_file}")
            
        with open(rankings_file) as f:
            # Skip header
            next(f)
            
            # Each line is hand_str,rank,ordered_rank
            for line in f:
                parts = line.strip().rsplit(',', 2)
                if len(parts) != 3:
                    continue
                    
                # Convert "As,Ks,Qs,Js,Ts" to "AsKsQsJsTs"
                # or "A,A,A,T,8" to "AAAT8" for rank-only
                hand_str = parts[0].replace(',', '')
                
                try:
                    rank = int(parts[1])
                    ordered_rank = int(parts[2])
                except ValueError:
                    continue
                    
                self.rankings[hand_str] = HandRanking(
                    hand_str=hand_str,
                    rank=rank,
                    ordered_rank=ordered_rank
                )