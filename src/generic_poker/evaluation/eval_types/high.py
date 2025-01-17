"""Standard high-hand poker evaluation."""
from typing import List, Optional
from generic_poker.core.card import Card
from generic_poker.evaluation.eval_types.base import BaseEvaluator, HandRanking

class HighHandEvaluator(BaseEvaluator):
    """Evaluator for standard high-hand poker."""
    
    def evaluate(
        self,
        cards: List[Card],
        wild_cards: Optional[List[Card]] = None
    ) -> Optional[HandRanking]:
        """
        Evaluate a high poker hand.
        
        Args:
            cards: Cards to evaluate
            wild_cards: Any wild cards in effect (not implemented yet)
            
        Returns:
            Hand ranking if valid hand, None if not
        """
        self._validate_hand_size(cards)
        
        # Sort cards in canonical order
        sorted_cards = self._sort_cards(cards)
        
        # Convert to string representation for lookup
        hand_str = self._cards_to_string(sorted_cards)
        
        # Look up ranking
        ranking = self.rankings.get(hand_str)
        if not ranking:
            raise ValueError(f"Invalid hand: {hand_str}")
            
        return ranking