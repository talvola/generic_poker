"""Standard high-hand poker evaluation."""
from typing import List, Optional
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.eval_types.base import BaseEvaluator, HandRanking
from pathlib import Path

class HighHandEvaluator(BaseEvaluator):
    """Evaluator for standard high-hand poker."""
    
    def __init__(self, rankings_file: Path):
        """Initialize high hand evaluator."""
        super().__init__(rankings_file, 'high')

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
        if len(cards) != 5:
            raise ValueError("High hand evaluation requires exactly 5 cards")
            
        # Sort cards in canonical order
        sorted_cards = self._sort_cards(cards)
        
        # Convert to string representation for lookup
        hand_str = self._cards_to_string(sorted_cards)
        
        # Look up ranking
        ranking = self.rankings.get(hand_str)
        if not ranking:
            raise ValueError(f"Invalid hand: {hand_str}")
            
        return ranking
        
    def _sort_cards(self, cards: List[Card]) -> List[Card]:
            """
            Sort cards for high hand evaluation.
            
            Sort descending by rank (A-2), then by suit in bridge order (s,h,d,c)
            """
            from generic_poker.evaluation.constants import SUIT_ORDER
            
            return sorted(
                cards,
                key=lambda c: (
                    # Get index in Rank enum, excluding JOKER
                    # Negative to sort descending by rank
                    -list(Rank).index(c.rank) if c.rank != Rank.JOKER else 1,
                    # Use suit ordering
                    SUIT_ORDER[c.suit]
                )
            )
               
    def _validate_hand_size(self, cards: List[Card]) -> None:
        """Ensure hand has correct number of cards."""
        if len(cards) != 5:
            raise ValueError(
                f"High hand evaluation requires 5 cards, got {len(cards)}"
            )
            
    def _handle_wild_cards(
        self,
        cards: List[Card],
        wild_cards: List[Card]
    ) -> List[Card]:
        """
        Handle wild card substitution.
        
        Not implemented yet - will handle converting wild cards to
        their best possible value for the hand.
        """
        raise NotImplementedError("Wild card support not implemented")