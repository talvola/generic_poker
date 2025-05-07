"""Main poker hand evaluation interface."""
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Type, Any, Tuple, cast
from pathlib import Path
import logging
import csv

from generic_poker.core.card import Card
from generic_poker.core.hand import PlayerHand
from generic_poker.evaluation.eval_types.base import BaseEvaluator, HandRanking
from generic_poker.evaluation.eval_types.large import LargeHandEvaluator
from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator

class EvaluationType(str, Enum):
    """Types of poker hand evaluation."""
    HIGH = 'high'                # Traditional high-hand poker
    HIGH_WILD = 'high_wild_bug'  # High-hand with wild cards
    LOW_A5 = 'a5_low'           # A-5 lowball
    LOW_A5_WILD = 'a5_low_wild'           # A-5 lowball
    LOW_A6 = 'a6_low'           # A-6 lowball
    LOW_27 = '27_low'           # 2-7 lowball
    LOW_27_WILD = '27_low_wild'           # 2-7 lowball
    LOW_A5_HIGH = 'a5_low_high' # A-5 lowball, but highest unpaired hand
    BADUGI = 'badugi'           # Badugi
    BADUGI_AH = 'badugi_ah'     # Badugi with ace high
    HIDUGI = 'hidugi'           # Hi-Dugi
    HIGH_36CARD = '36card_ffh_high'  # 36-card deck high hands
    HIGH_20CARD = '20card_high'      # 20-card deck high hands
    HIGH_27_JA = '27_ja_ffh_high'  # 40-card deck (no 8-T) high hands
    HIGH_27_JA_WILD = '27_ja_ffh_high_wild_bug'  # 40-card deck (no 8-T) high hands with wild and/or bug cards
    QUICK_QUADS = 'quick_quads'                # Quick quads high-hand poker
    GAME_49 = '49'              # Pip count games
    GAME_58 = '58'
    GAME_6 = '6'
    GAME_ZERO = 'zero'
    GAME_ZERO_6 = 'zero_6'
    GAME_21 = '21'
    GAME_21_6 = '21_6'
    LOW_PIP_6 = 'low_pip_6_cards'
    FOOTBALL = 'football' 
    SIX_CARD_FOOTBALL = 'six_card_football' 
    SEVEN_CARD_FOOTBALL = 'seven_card_football' 
    # special partial hands for stud games
    # but could be used for other games as well
    ONE_CARD_LOW = 'one_card_low'
    ONE_CARD_LOW_AL = 'one_card_low_al'
    ONE_CARD_HIGH = 'one_card_high'
    ONE_CARD_HIGH_AH = 'one_card_high_ah'
    ONE_CARD_HIGH_AH_WILD = 'one_card_high_ah_wild_bug'
    # 2-4 card Stud evaluations
    TWO_CARD_LOW = 'two_card_a5_low'
    TWO_CARD_LOW_AH = 'two_card_27_low'
    TWO_CARD_HIGH = 'two_card_high'
    TWO_CARD_HIGH_AL = 'two_card_high_al'  # Unimplemented
    TWO_CARD_HIGH_AL_RH = 'two_card_a5_low_high'
    THREE_CARD_LOW = 'three_card_a5_low'
    THREE_CARD_LOW_AH = 'three_card_27_low'
    THREE_CARD_HIGH = 'three_card_high'
    THREE_CARD_HIGH_AL = 'three_card_high_al'  # Unimplemented
    THREE_CARD_HIGH_AL_RH = 'three_card_a5_low_high'
    FOUR_CARD_LOW = 'four_card_a5_low'
    FOUR_CARD_LOW_AH = 'four_card_27_low'
    FOUR_CARD_HIGH = 'four_card_high'
    FOUR_CARD_HIGH_AL = 'four_card_high_al'  # Unimplemented
    FOUR_CARD_HIGH_AL_RH = 'four_card_a5_low_high'
    # 40-card (no 8-T) card Stud evaluations
    TWO_CARD_HIGH_27_JA = 'two_card_27_ja_ffh_high'
    THREE_CARD_HIGH_27_JA = 'three_card_27_ja_ffh_high'
    FOUR_CARD_HIGH_27_JA = 'four_card_27_ja_ffh_high'
    TWO_CARD_HIGH_27_JA_WILD = 'two_card_27_ja_ffh_high_wild_bug'
    THREE_CARD_HIGH_27_JA_WILD = 'three_card_27_ja_ffh_high_wild_bug'
    FOUR_CARD_HIGH_27_JA_WILD = 'four_card_27_ja_ffh_high_wild_bug'  
    # alternate high hands
    SOKO_HIGH = 'soko_high'
    NE_SEVEN_CARD_HIGH = 'ne_seven_card_high'
    # for high suit in hand
    ONE_CARD_HIGH_SPADE = 'one_card_high_spade'
    ONE_CARD_HIGH_HEART = 'one_card_high_heart'
    ONE_CARD_HIGH_DIAMOND = 'one_card_high_diamond'
    ONE_CARD_HIGH_CLUB = 'one_card_high_club'  
    ONE_CARD_LOW_SPADE = 'one_card_low_spade'
    ONE_CARD_LOW_HEART = 'one_card_low_heart'
    ONE_CARD_LOW_DIAMOND = 'one_card_low_diamond'
    ONE_CARD_LOW_CLUB = 'one_card_low_club'          
    THREE_CARD_HIGH_SPADE = 'three_card_high_spade'
    THREE_CARD_HIGH_HEART = 'three_card_high_heart'
    THREE_CARD_HIGH_DIAMOND = 'three_card_high_diamond'
    THREE_CARD_HIGH_CLUB = 'three_card_high_club'



@dataclass
class HandResult:
    """
    Result of hand evaluation.
    
    Attributes:
        rank: Primary rank of hand (e.g., straight flush = 1, four of kind = 2)
        ordered_rank: Secondary ordering within rank (e.g., ace-high straight = 1)
        description: Human-readable description of hand
        cards_used: Cards that make up the hand
        sources: Where each card came from (hole, community, etc.)
    """
    rank: int
    ordered_rank: Optional[int] = None
    description: Optional[str] = None
    cards_used: Optional[List[Card]] = None
    sources: Optional[List[str]] = None
    classifications: Dict[str, str] = field(default_factory=dict)  # New field for classifications

    @classmethod
    def from_ranking(cls, ranking: HandRanking) -> 'HandResult':
        """Convert HandRanking to HandResult."""
        return cls(
            rank=ranking.rank,
            ordered_rank=ranking.ordered_rank,
            description=ranking.description
        )

class HandEvaluator:
    """
    Main interface for poker hand evaluation.
    
    Loads and caches appropriate evaluators for different game types.
    Handles comparing hands and determining winners.
    """
    
    def __init__(self):
        """Initialize evaluator."""
        self._evaluators: Dict[EvaluationType, BaseEvaluator] = {}
        self._rankings_dir = Path(__file__).parents[3] / 'data' / 'hand_rankings'
        
    def get_evaluator(self, eval_type: EvaluationType) -> BaseEvaluator:
        """
        Get evaluator for a specific game type.
        
        Args:
            eval_type: Type of evaluation needed
            
        Returns:
            Appropriate evaluator instance
            
        Raises:
            ValueError: If evaluation type not supported
        """
        if eval_type not in self._evaluators:
            evaluator_class = self._get_evaluator_class(eval_type)
            if eval_type == EvaluationType.NE_SEVEN_CARD_HIGH:
                db_file = self._rankings_dir / 'hand_rankings.db'
                self._evaluators[eval_type] = evaluator_class(db_file, eval_type.value)
            else:
                rankings_file = self._rankings_dir / f'all_card_hands_ranked_{eval_type.value}.csv'
                self._evaluators[eval_type] = evaluator_class(rankings_file, eval_type.value)
        return self._evaluators[eval_type]
        
    def evaluate_hand(
            self,
            cards: List[Card],
            eval_type: EvaluationType,
            qualifier: Optional[List[int]] = None
        ) -> HandResult:
            """
            Evaluate a poker hand.
            
            Args:
                cards: Cards to evaluate
                eval_type: Type of evaluation to use
                wild_cards: Any wild cards in effect
                qualifier: Minimum hand requirement [rank, ordered_rank]
                
            Returns:
                HandResult with evaluation details
            """
            evaluator = self.get_evaluator(eval_type)
            ranking = evaluator.evaluate(cards)
            
            # Convert HandRanking to HandResult
            result = HandResult.from_ranking(ranking) if ranking else HandResult(rank=0)
            
            # Check qualifier using HandResult
            if qualifier and not self._meets_qualifier(result, qualifier):
                return HandResult(rank=0)  # Return an invalid hand result

            return result
    
    def get_sample_hand(
            self,
            eval_type: EvaluationType,
            rank: int,
            ordered_rank: int
    ) -> List[Card]:
            """
            Get a sample hand for a specific evaluation type and rank.
            
            Args:
                eval_type: Type of evaluation to use
                rank: Primary rank to retrieve
                ordered_rank: Secondary ordering within the primary rank
            Returns:
                HandResult: Sample hand for the specified rank and ordered rank
            """
            evaluator = self.get_evaluator(eval_type)
            hand_str = evaluator.get_sample_hand(rank, ordered_rank)

            # turn the hand_str into a list of cards

            hand = PlayerHand.from_string(hand_str)
            return hand
    
    def sort_cards(self, cards: List[Card], eval_type: Optional[EvaluationType] = None) -> List[Card]:
        """
        Sort cards according to evaluation type rules.
        
        Args:
            cards: Cards to sort
            eval_type: Evaluation type to use for sorting (defaults to current type)
            
        Returns:
            Sorted copy of the cards
        """
        type_str = eval_type.value if eval_type else self.current_type
        
        if type_str in self._evaluators:
            return self._evaluators[type_str]._sort_cards(cards.copy())
        
        # Fallback to basic sorting if evaluator not found
        return sorted(cards.copy(), key=lambda c: (c.rank.value, c.suit.value))    
        
    def compare_hands(
            self,
            hand1: List[Card],
            hand2: List[Card],
            eval_type: EvaluationType,
            qualifier: Optional[List[int]] = None
        ) -> int:
            """
            Compare two poker hands.
            
            Args:
                hand1: First hand to compare
                hand2: Second hand to compare
                eval_type: Type of evaluation to use
                qualifier: Minimum hand requirement
                
            Returns:
                1 if hand1 wins, -1 if hand2 wins, 0 if tie
                
            Note:
                Rankings are always ordered with best hands first (rank=1),
                regardless of whether it's a high or low game. This ordering
                is encoded in the ranking files themselves.
            """
            result1 = self.evaluate_hand(hand1, eval_type, qualifier=qualifier)
            result2 = self.evaluate_hand(hand2, eval_type, qualifier=qualifier)
            
            if not result1 and not result2:
                return 0  # Neither hand qualifies
            if not result1:
                return -1  # Only hand2 qualifies
            if not result2:
                return 1  # Only hand1 qualifies
            
            # Lower rank = better hand (for both high and low games)
            if result1.rank != result2.rank:
                return 1 if result1.rank < result2.rank else -1
                
            # If primary ranks equal, compare secondary ordering
            if result1.ordered_rank is not None and result2.ordered_rank is not None:
                if result1.ordered_rank != result2.ordered_rank:
                    return 1 if result1.ordered_rank < result2.ordered_rank else -1
                    
            return 0  # Completely tied
        
    def compare_hands_with_offset(
        self,
        hand1: List[Card],
        hand2: List[Card],
        eval_type1: EvaluationType,
        eval_type2: EvaluationType,
        qualifier1: Optional[List[int]] = None,
        qualifier2: Optional[List[int]] = None
    ) -> int:
        """
        Compare two hands using a comparison table for different evaluation types.

        Args:
            hand1: First hand (e.g., 5-card hand)
            hand2: Second hand (e.g., 2-card hand)
            eval_type1: Evaluation type for hand1 (e.g., 'high')
            eval_type2: Evaluation type for hand2 (e.g., 'two_card_high')
            qualifier1: Qualifier for hand1 (e.g., [rank, ordered_rank])
            qualifier2: Qualifier for hand2

        Returns:
            1 if hand1 is better, -1 if hand2 is better, 0 if tie
        """
        logger = logging.getLogger(__name__)

        # Evaluate both hands
        result1 = self.evaluate_hand(hand1, eval_type1, qualifier=qualifier1)
        result2 = self.evaluate_hand(hand2, eval_type2, qualifier=qualifier2)

        # Handle qualification cases
        if not result1 and not result2:
            return 0  # Neither hand qualifies
        if not result1:
            return -1  # Only hand2 qualifies
        if not result2:
            return 1  # Only hand1 qualifies

        # Determine smaller and larger hands based on evaluation types
        # For simplicity, assume eval_type2 is smaller (e.g., 'two_card_high') and eval_type1 is larger (e.g., 'high')
        # This can be enhanced with logic to dynamically determine hand sizes if needed
        smaller_eval_type = eval_type2
        larger_eval_type = eval_type1
        smaller_result = result2
        larger_result = result1

        # Get the comparison table file path
        comparison_file = self._get_comparison_file(smaller_eval_type, larger_eval_type)

        if comparison_file.exists():
            # Load the comparison table
            comparison_table = self._load_comparison_table(comparison_file)

            # Map the smaller hand's rank to the larger hand's system
            equivalent_rank = self._get_equivalent_rank(
                comparison_table,
                smaller_result.rank,
                smaller_result.ordered_rank
            )

            if equivalent_rank is not None:
                # Unpack the tuple into mapped_rank and mapped_ordered_rank
                mapped_rank, mapped_ordered_rank = equivalent_rank   

                # Compare primary ranks (lower is better)
                if larger_result.rank < mapped_rank:
                    return 1  # 5-card hand (larger_result) is better
                elif larger_result.rank > mapped_rank:
                    return -1  # 2-card hand (mapped to equivalent_rank) is better
                else:
                    # Ranks are equal, compare ordered ranks
                    # Use float('inf') if ordered_rank is None, assuming None is worst
                    larger_ordered_rank = larger_result.ordered_rank if larger_result.ordered_rank is not None else float('inf')
                    if larger_ordered_rank < mapped_ordered_rank:
                        return 1  # 5-card hand is better
                    elif larger_ordered_rank > mapped_ordered_rank:
                        return -1  # 2-card hand is better
                    else:
                        return 0  # Hands are equal
            else:
                logger.warning(
                    f"No equivalent rank found for {smaller_eval_type.value} "
                    f"rank {smaller_result.rank}, ordered_rank {smaller_result.ordered_rank}"
                )
                return -1  # Default to smaller hand being better if no mapping
        else:
            logger.warning(f"Comparison table not found: {comparison_file}")
            return 1  # Fallback: assume larger hand is better
        
    def _get_comparison_file(self, smaller_eval_type: EvaluationType, larger_eval_type: EvaluationType) -> Path:
        """
        Construct the path to the comparison table file.

        Args:
            smaller_eval_type: Evaluation type of the smaller hand
            larger_eval_type: Evaluation type of the larger hand

        Returns:
            Path object pointing to the comparison CSV file
        """
        comparison_dir = Path(__file__).parents[3] / 'data' / 'hand_comparisons'
        file_name = f"{smaller_eval_type.value}_{larger_eval_type.value}_comparison.csv"
        return comparison_dir / file_name

    def _load_comparison_table(self, file_path: Path) -> List[Dict[str, str]]:
        """
        Load the comparison table from a CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            List of dictionaries containing the table rows
        """
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            return list(reader)        
        
    def _get_equivalent_rank(
        self,
        table: List[Dict[str, str]],
        rank: int,
        ordered_rank: Optional[int]
    ) -> Optional[Tuple[int, float]]:
        """
        Map the smaller hand's rank and ordered rank to the larger hand's system.

        Args:
            table: Loaded comparison table
            rank: Primary rank of the smaller hand
            ordered_rank: Secondary ordered rank of the smaller hand

        Returns:
            Tuple of (equivalent rank, equivalent ordered rank) in the larger hand's system,
            or None if not found
        """
        # Handle case where ordered_rank is None
        ordered_rank = ordered_rank if ordered_rank is not None else 0
        
        for row in table:
            if (int(row['two_card_rank']) == rank and
                int(row['two_card_ordered_rank']) == ordered_rank):
                mapped_rank = int(row['five_card_rank'])
                mapped_ordered_rank = float(row['five_card_ordered_rank'])
                return (mapped_rank, mapped_ordered_rank)
        return None 
            
    def _meets_qualifier(self, result: Optional[HandResult], qualifier: List[int]) -> bool:
        """Check if hand meets qualifier requirements."""
        if not result:
            return False

        rank, ordered_rank = qualifier
        if result.rank > rank:
            return False
        if result.rank == rank and ordered_rank is not None:
            if result.ordered_rank is None or result.ordered_rank > ordered_rank:
                return False
        return True
        
    def _get_evaluator_class(self, eval_type: EvaluationType) -> Type[BaseEvaluator]:
        """Get appropriate evaluator class for eval type."""
        if eval_type == EvaluationType.NE_SEVEN_CARD_HIGH:
            return LargeHandEvaluator
        return StandardHandEvaluator
        
# Global instance
evaluator = HandEvaluator()