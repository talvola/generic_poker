"""A-5 Low hand evaluation."""
from typing import List, Optional
from generic_poker.core.card import Card
from generic_poker.evaluation.eval_types.base import BaseEvaluator, HandRanking

class A5LowEvaluator(BaseEvaluator):
    """Evaluator for A-5 Lowball poker."""
    
    def evaluate(
        self,
        cards: List[Card],
        wild_cards: Optional[List[Card]] = None
    ) -> Optional[HandRanking]:
        """
        Evaluate an A-5 Low poker hand.
        
        In A-5 Low:
        - A-2-3-4-5 is the best possible hand (wheel)
        - Straights and flushes don't count
        - Pairs and other made hands are bad
        
        Args:
            cards: Cards to evaluate
            wild_cards: Any wild cards in effect (not implemented yet)
        """
        self._validate_hand_size(cards)
        
        # Sort cards in canonical order for ranking lookup
        sorted_cards = self._sort_cards(cards)
        
        # Convert to string representation for lookup
        hand_str = self._cards_to_string(sorted_cards)
        
        # Look up ranking
        ranking = self.rankings.get(hand_str)
        if not ranking:
            raise ValueError(f"Invalid hand: {hand_str}")
            
        return ranking