"""Hand ranking and evaluation functionality."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import csv
import logging

from generic_poker.core.card import Card

logger = logging.getLogger(__name__)


class EvaluationType(str, Enum):
    """Types of poker hand evaluation."""
    HIGH = 'high'
    HIGH_WILD = 'high_wild'
    LOW_A5 = 'a5_low'
    LOW_27 = '27_low'
    LOW_A5_HIGH = 'a5_low_high'
    BADUGI = 'badugi'
    BADUGI_AH = 'badugi_ah'
    HIDUGI = 'hidugi'
    HIGH_36CARD = '36card_ffh_high'
    HIGH_20CARD = '20card_high'
    GAME_49 = '49'
    GAME_58 = '58'
    GAME_6 = '6'
    GAME_ZERO = 'zero'
    GAME_ZERO_6 = 'zero_6'
    GAME_21 = '21'
    GAME_21_6 = '21_6'
    LOW_PIP_6 = 'low_pip_6_cards'


@dataclass
class HandRanking:
    """
    Represents the ranking of a specific poker hand.
    
    Attributes:
        hand_str: String representation of the hand
        rank: Primary rank of the hand
        ordered_rank: Secondary ordering within rank
    """
    hand_str: str
    rank: int
    ordered_rank: Optional[int]


class HandRankings:
    """
    Manages hand rankings for a specific evaluation type.
    
    Loads and caches rankings from CSV files.
    """
    
    def __init__(self, eval_type: EvaluationType):
        """
        Initialize rankings for evaluation type.
        
        Args:
            eval_type: Type of hand evaluation to use
        """
        self.eval_type = eval_type
        self.rankings: Dict[str, HandRanking] = {}
        self._load_rankings()
        
    def _load_rankings(self) -> None:
        """Load rankings from CSV file."""
        file_path = (
            Path(__file__).parents[3] / 
            'data' / 
            'hand_rankings' /
            f'all_card_hands_ranked_{self.eval_type}.csv'
        )
        
        if not file_path.exists():
            raise ValueError(
                f"Rankings file not found for {self.eval_type}: {file_path}"
            )
            
        try:
            with open(file_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Handle rankings with or without ordered rank
                    ordered_rank = (
                        int(row['OrderedRank'])
                        if 'OrderedRank' in row and row['OrderedRank']
                        else None
                    )
                    
                    self.rankings[row['Hand']] = HandRanking(
                        hand_str=row['Hand'],
                        rank=int(row['Rank']),
                        ordered_rank=ordered_rank
                    )
        except Exception as e:
            logger.error(f"Error loading rankings for {self.eval_type}: {e}")
            raise
            
    def get_ranking(self, hand_str: str) -> Optional[HandRanking]:
        """
        Get ranking for a hand.
        
        Args:
            hand_str: String representation of hand
            
        Returns:
            HandRanking if found, None if not
        """
        return self.rankings.get(hand_str)


class HandEvaluator:
    """
    Evaluates and compares poker hands.
    
    Caches rankings for different evaluation types.
    """
    
    def __init__(self):
        """Initialize evaluator."""
        self.rankings_cache: Dict[EvaluationType, HandRankings] = {}
        
    def get_rankings(self, eval_type: EvaluationType) -> HandRankings:
        """
        Get rankings for evaluation type, loading if needed.
        
        Args:
            eval_type: Type of hand evaluation
            
        Returns:
            HandRankings for that type
        """
        if eval_type not in self.rankings_cache:
            self.rankings_cache[eval_type] = HandRankings(eval_type)
        return self.rankings_cache[eval_type]
        
    def compare_hands(
        self,
        hand1: List[Card],
        hand2: List[Card],
        eval_type: EvaluationType
    ) -> int:
        """
        Compare two poker hands.
        
        Args:
            hand1: First hand to compare
            hand2: Second hand to compare
            eval_type: Type of evaluation to use
            
        Returns:
            1 if hand1 wins, -1 if hand2 wins, 0 if tie
            
        Raises:
            ValueError: If hands cannot be evaluated
        """
        # Get string representations
        hand1_str = self._cards_to_string(hand1)
        hand2_str = self._cards_to_string(hand2)
        
        # Get rankings
        rankings = self.get_rankings(eval_type)
        rank1 = rankings.get_ranking(hand1_str)
        rank2 = rankings.get_ranking(hand2_str)
        
        if not rank1 or not rank2:
            raise ValueError("Invalid hand(s) for evaluation type")
            
        # Compare primary ranks
        if rank1.rank != rank2.rank:
            # Note: Some evaluation types are low (lower is better)
            multiplier = -1 if eval_type.startswith('low') else 1
            return multiplier * (1 if rank1.rank < rank2.rank else -1)
            
        # If equal primary ranks, compare secondary if present
        if rank1.ordered_rank is not None and rank2.ordered_rank is not None:
            if rank1.ordered_rank != rank2.ordered_rank:
                multiplier = -1 if eval_type.startswith('low') else 1
                return multiplier * (
                    1 if rank1.ordered_rank < rank2.ordered_rank else -1
                )
                
        return 0  # Tie
        
    def _cards_to_string(self, cards: List[Card]) -> str:
        """
        Convert cards to string representation for lookup.
        
        Args:
            cards: List of cards to convert
            
        Returns:
            String representation of hand
        """
        # Sort by rank then suit
        sorted_cards = sorted(
            cards,
            key=lambda c: (c.rank.value, c.suit.value)
        )
        return ','.join(str(card) for card in sorted_cards)


# Global evaluator instance
evaluator = HandEvaluator()