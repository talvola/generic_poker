"""Base class for poker hand evaluators."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Union
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
        
    def _cards_to_string(self, cards: List[Union[Card, str]]) -> str:
        """
        Convert cards to string for ranking lookup.
        
        For rank-only formats (like '49', 'zero'): "AAAT8"
        For regular formats: "AsKsQsJsTs"
        Handles wild cards (W1, W2, ...) and bugs (B1, B2, ...)
        """
        if self.rank_only:
            return ''.join(
                card if isinstance(card, str) else getattr(getattr(card, 'rank', None), 'value', 'X')
                for card in cards
            )
        else:
            return ''.join(
                card if isinstance(card, str) else f"{card.rank.value}{card.suit.value}"
                for card in cards
            )

    def _validate_hand_size(self, cards: List[Card]) -> None:
        """Ensure hand has correct number of cards."""
        if len(cards) != self.required_size and not self.padding_required:
            raise ValueError(
                f"{self.eval_type} evaluation requires exactly {self.required_size} cards"
            )
                
    def _sort_cards(self, cards: List[Union[Card, str]]) -> List[Union[Card, str]]:
        """
        Sort cards based on evaluation type's rank ordering.
        Wild cards (W1, W2, ...) and bugs (B1, B2, ...) sort to the beginning.
        
        Args:
            cards: List of cards or transformed strings to sort
            
        Returns:
            Sorted list according to evaluation type's rules
        """
        def get_sort_key(item: Union[Card, str]) -> tuple:
            """Get sorting key for a card or transformed string."""
            if isinstance(item, str):
                # Wild cards (W1-W5) and bugs (B1-B5) sort to the beginning
                if item.startswith('W'):
                    return (-2, int(item[1]), 'z')  # Wilds sort first
                elif item.startswith('B'):
                    return (-1, int(item[1]), 'z')  # Bugs sort after wilds but before regular cards
                elif item == 'Xx':
                    return (len(self.rank_order) + 1, 0, 'z')  # Padding last
                else:
                    raise ValueError(f"Invalid transformed card: {item}")
            else:
                # Regular card sorting
                rank_index = self.rank_order.index(item.rank.value)
                suit_index = SUIT_ORDER[item.suit]
                return (rank_index, 0, suit_index)

        return sorted(cards, key=get_sort_key)
              
    def get_sample_hand(
        self,
        rank: int,
        ordered_rank: int
    ) -> HandRanking:
        pass

    @abstractmethod
    def evaluate(
        self,
        cards: List[Card],
        wild_cards: Optional[List[Card]] = None
    ) -> Optional[HandRanking]:
        """Evaluate a poker hand."""
        pass
               
