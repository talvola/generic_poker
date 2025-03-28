"""Standard poker evaluation based off generic file-based rankings"""
from typing import List, Optional
from generic_poker.core.card import Card
from generic_poker.evaluation.eval_types.base import BaseEvaluator, HandRanking

class StandardHandEvaluator(BaseEvaluator):
    """Evaluator for standard poker."""
    
    def pad_hand(self, player_hand, pad_to):
        # Calculate the number of padding entries needed
        num_padding = pad_to - len(player_hand)

        # Create a new hand with padding entries if needed
        # Create a pad card:
        pad_card = ('Xx', 'padding')  # This is a placeholder for padding, can be customized

        new_player_hand = player_hand + [('Xx', 'padding')] * num_padding

        return new_player_hand
        
    def evaluate(
        self,
        cards: List[Card],
        wild_cards: Optional[List[Card]] = None
    ) -> Optional[HandRanking]:
        """
        Evaluate a poker hand.
        
        Args:
            cards: Cards to evaluate
            wild_cards: Any wild cards in effect (not implemented yet)
            
        Returns:
            Hand ranking if valid hand, None if not
        """
        self._validate_hand_size(cards)
        
        # Sort cards in canonical order
        sorted_cards = self._sort_cards(cards)
    
        # Pad hand if needed
        if self.padding_required:
            sorted_cards = self.pad_hand(sorted_cards, self.hand_size)
        
        # Convert to string representation for lookup
        hand_str = self._cards_to_string(sorted_cards)
        
        # Look up ranking
        ranking = self.rankings.get(hand_str)
        if not ranking:
            raise ValueError(f"Invalid hand: {hand_str}")
            
        return ranking