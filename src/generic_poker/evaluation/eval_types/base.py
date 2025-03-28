"""Base class for poker hand evaluators."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
import csv

from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.types import HandRanking
from generic_poker.evaluation.constants import (
    SUIT_ORDER, RANK_ORDERS, HAND_SIZES, RANK_ONLY_TYPES, PADDED_TYPES
)
from generic_poker.evaluation.cache import HandRankingsCache

class BaseEvaluator(ABC):
    """Base class for hand evaluators."""

    _rankings_cache = HandRankingsCache()

    def __init__(self, rankings_file: Path, eval_type: str):
        """
        Initialize evaluator.
        
        Args:
            rankings_file: Path to CSV file with hand rankings
            eval_type: Type of evaluation (used to determine rank-only status)
        """
        self.eval_type = eval_type
        self.required_size = HAND_SIZES[eval_type]
        self.rank_order = RANK_ORDERS[eval_type]
        self.rank_only = eval_type in RANK_ONLY_TYPES
        self.rankings = self._rankings_cache.get_rankings(eval_type, rankings_file)
        self.padding_required = eval_type in PADDED_TYPES
        self.hand_size = HAND_SIZES[eval_type]
        
    def _cards_to_string(self, cards: List[Card]) -> str:
        """
        Convert cards to string for ranking lookup.
        
        For rank-only formats (like '49', 'zero'): "AAAT8"
        For regular formats: "AsKsQsJsTs"
        """

        # should fix this - padding should create actual cards
        if self.rank_only:
            return ''.join(getattr(getattr(card, 'rank', None), 'value', 'X') for card in cards)
        else:
            return ''.join(f"{card.rank.value}{card.suit.value}" for card in cards)

    def _validate_hand_size(self, cards: List[Card]) -> None:
        """Ensure hand has correct number of cards."""
        if len(cards) != self.required_size and not self.padding_required:
            raise ValueError(
                f"{self.eval_type} evaluation requires exactly {self.required_size} cards"
            )
                
    def _sort_cards(self, cards: List[Card]) -> List[Card]:
        """
        Sort cards based on evaluation type's rank ordering.
        
        Args:
            cards: List of cards to sort
            
        Returns:
            Sorted list of cards according to evaluation type's rules
        """
        def get_rank_index(card: Card) -> int:
            """Get index in rank ordering list for sorting."""
            return self.rank_order.index(card.rank.value)
            
        return sorted(
            cards,
            key=lambda c: (
                get_rank_index(c),  # Primary sort by rank position
                SUIT_ORDER[c.suit]   # Secondary sort by suit
            )
        )
              
    @abstractmethod
    def evaluate(
        self,
        cards: List[Card],
        wild_cards: Optional[List[Card]] = None
    ) -> Optional[HandRanking]:
        """Evaluate a poker hand."""
        pass
               
