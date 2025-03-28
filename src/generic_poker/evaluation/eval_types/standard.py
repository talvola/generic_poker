"""Standard poker evaluation based off generic file-based rankings"""
from typing import List, Optional, Union
from generic_poker.core.card import Card, WildType
from generic_poker.evaluation.eval_types.base import BaseEvaluator, HandRanking

import logging
logger = logging.getLogger(__name__)


class StandardHandEvaluator(BaseEvaluator):
    """Evaluator for standard poker."""
    
    def pad_hand(self, player_hand: List[Union[Card, str]], pad_to: int) -> List[Union[Card, str]]:
        """Pad the hand to the required length with 'Xx' placeholders."""
        num_padding = pad_to - len(player_hand)
        pad_card = 'X'  # Simplified to a string since it’s only used in string form
        return player_hand + [pad_card] * num_padding
        
    def _transform_wild_cards(self, cards: List[Card]) -> List[Union[Card, str]]:
        """
        Transform wild cards and bugs into special string representations (W1, W2, ..., B1, B2, ...).
        
        Args:
            cards: List of cards to transform
            
        Returns:
            List of transformed cards (either Card objects or strings like 'W1', 'B1')
        """
        wild_count = 0
        bug_count = 0
        transformed_cards = []

        for card in cards:
            if card.is_wild:
                if card.wild_type == WildType.BUG:
                    bug_count += 1
                    if bug_count > 5:
                        logger.warning(f"More than 5 bug cards in hand, truncating: {card}")
                        continue
                    transformed_cards.append(f"B{bug_count}")
                else:
                    wild_count += 1
                    if wild_count > 5:
                        logger.warning(f"More than 5 wild cards in hand, truncating: {card}")
                        continue
                    transformed_cards.append(f"W{wild_count}")
            else:
                transformed_cards.append(card)

        # Log a warning if both wild and bug cards are present (unsupported)
        if wild_count > 0 and bug_count > 0:
            logger.warning("Hand contains both wild and bug cards, which is not supported")

        return transformed_cards
            
    def evaluate(
        self,
        cards: List[Card]
    ) -> Optional[HandRanking]:
        """
        Evaluate a poker hand, transforming wild cards and bugs into W1, W2, ..., B1, B2, ...
        
        Args:
            cards: Cards to evaluate
            wild_cards: Any wild cards in effect (not implemented yet)
            
        Returns:
            Hand ranking if valid hand, None if not
        """
        self._validate_hand_size(cards)

        # Transform wild cards and bugs into W1, W2, ..., B1, B2, ...
        transformed_cards = self._transform_wild_cards(cards)        
       
        # Sort cards (including transformed wilds/bugs) in canonical order
        sorted_cards = self._sort_cards(transformed_cards)
    
        # Pad hand if needed
        if self.padding_required:
            sorted_cards = self.pad_hand(sorted_cards, self.hand_size)
        
        # Convert to string representation for lookup
        hand_str = self._cards_to_string(sorted_cards)
        
        # Log the transformed hand for debugging
        #  logger.debug(f"Evaluating hand: {hand_str}")

        # Look up ranking
        ranking = self.rankings.get(hand_str)
        if not ranking:
            raise ValueError(f"Invalid hand: {hand_str}")
            
        return ranking
    
    def get_sample_hand(self, rank, ordered_rank) -> str:
        """
        Get a sample hand for a specific rank and ordered rank.
        
        Args:
            rank: Primary rank to retrieve
            ordered_rank: Secondary ordering within the primary rank
            
        Returns:
            HandRanking: Sample hand for the specified rank and ordered rank
        """
        # Find a sample hand for the specified rank and ordered_rank
        ranking = None
        for hand_str, ranking in self.rankings.items():
            if ranking.rank == rank and ranking.ordered_rank == ordered_rank:
                break

        if not ranking:
            raise ValueError(f"No sample hand found for rank {rank} and ordered_rank {ordered_rank}")
        
        return hand_str    