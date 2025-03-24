"""Main poker hand evaluation interface."""
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Type, Any, cast
from pathlib import Path

from generic_poker.core.card import Card
from generic_poker.evaluation.eval_types.base import BaseEvaluator, HandRanking


class EvaluationType(str, Enum):
    """Types of poker hand evaluation."""
    HIGH = 'high'                # Traditional high-hand poker
    HIGH_WILD = 'high_wild'      # High-hand with wild cards
    LOW_A5 = 'a5_low'           # A-5 lowball
    LOW_27 = '27_low'           # 2-7 lowball
    LOW_A5_HIGH = 'a5_low_high' # A-5 lowball, but highest unpaired hand
    BADUGI = 'badugi'           # Badugi
    BADUGI_AH = 'badugi_ah'     # Badugi with ace high
    HIDUGI = 'hidugi'           # Hi-Dugi
    HIGH_36CARD = '36card_ffh_high'  # 36-card deck high hands
    HIGH_20CARD = '20card_high'      # 20-card deck high hands
    GAME_49 = '49'              # Pip count games
    GAME_58 = '58'
    GAME_6 = '6'
    GAME_ZERO = 'zero'
    GAME_ZERO_6 = 'zero_6'
    GAME_21 = '21'
    GAME_21_6 = '21_6'
    LOW_PIP_6 = 'low_pip_6_cards'
    # special partial hands for stud games
    # but could be used for other games as well
    ONE_CARD_LOW = 'one_card_low'
    ONE_CARD_LOW_AL = 'one_card_low_al'
    ONE_CARD_HIGH = 'one_card_high'
    ONE_CARD_HIGH_AH = 'one_card_high_ah'
    # TWO_CARD_LOW = 'two_card_low'
    # TWO_CARD_LOW_AH = 'two_card_low_ah'
    # TWO_CARD_HIGH = 'two_card_high'
    # TWO_CARD_HIGH_AL = 'two_card_high_al'
    # TWO_CARD_HIGH_AL_RH = 'two_card_high_al_rh'
    # THREE_CARD_LOW = 'three_card_low'
    # THREE_CARD_LOW_AH = 'three_card_low_ah'
    # THREE_CARD_HIGH = 'three_card_high'
    # THREE_CARD_HIGH_AL = 'three_card_high_al'
    # THREE_CARD_HIGH_AL_RH = 'three_card_high_al_rh'
    # FOUR_CARD_LOW = 'four_card_low'
    # FOUR_CARD_LOW_AH = 'four_card_low_ah'
    # FOUR_CARD_HIGH = 'four_card_high'
    # FOUR_CARD_HIGH_AL = 'four_card_high_al'
    # FOUR_CARD_HIGH_AL_RH = 'four_card_high_al_rh'

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
            self._evaluators[eval_type] = evaluator_class(
                self._rankings_dir / f'all_card_hands_ranked_{eval_type}.csv',
                eval_type
            )
        return self._evaluators[eval_type]
        
    def evaluate_hand(
            self,
            cards: List[Card],
            eval_type: EvaluationType,
            wild_cards: Optional[List[Card]] = None,
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
            ranking = evaluator.evaluate(cards, wild_cards)
            
            # Convert HandRanking to HandResult
            result = HandResult.from_ranking(ranking) if ranking else HandResult(rank=0)
            
            # Check qualifier using HandResult
            if qualifier and not self._meets_qualifier(result, qualifier):
                return HandResult(rank=0)  # Return an invalid hand result

            return result
    
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
        from generic_poker.evaluation.eval_types.standard import StandardHandEvaluator
        
        # Map exceptions to specific evaluator classes; all others default to StandardHandEvaluator
        evaluator_map = {
            # Add exceptions here as needed, e.g.:
            # EvaluationType.HIGH_WILD: WildHandEvaluator,
            # EvaluationType.BADUGI: BadugiEvaluator,
        }
        
        # Return the mapped evaluator if it exists, otherwise default to StandardHandEvaluator
        return evaluator_map.get(eval_type, StandardHandEvaluator)
        
# Global instance
evaluator = HandEvaluator()