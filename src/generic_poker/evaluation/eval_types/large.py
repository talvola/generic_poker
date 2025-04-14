import sqlite3
from typing import List, Optional, Union
from pathlib import Path
from generic_poker.core.card import Card
from generic_poker.evaluation.eval_types.base import BaseEvaluator
from generic_poker.evaluation.types import HandRanking

class LargeHandEvaluator(BaseEvaluator):
    """Evaluator for large hand sets using an SQLite database."""

    def __init__(self, db_file: Path, eval_type: str):
        """Initialize with a database file instead of a rankings file."""
        super().__init__(None, eval_type)  # No rankings file needed
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()

    def evaluate(self, cards: List[Card]) -> Optional[HandRanking]:
        """Evaluate a hand by querying the SQLite database."""
        self._validate_hand_size(cards)

        # Transform wild cards (if any) and sort
        transformed_cards = self._transform_wild_cards(cards)
        sorted_cards = self._sort_cards(transformed_cards)

        # Pad hand if required (though unlikely for NEHE)
        if self.padding_required:
            sorted_cards = self.pad_hand(sorted_cards, self.hand_size)

        # Convert to string for database query
        hand_str = self._cards_to_string(sorted_cards)

        # Query the database
        self.cursor.execute('SELECT rank, ordered_rank FROM hand_rankings WHERE hand_str = ?', (hand_str,))
        result = self.cursor.fetchone()

        if result:
            rank, ordered_rank = result
            return HandRanking(hand_str=hand_str, rank=rank, ordered_rank=ordered_rank)
        else:
            raise ValueError(f"Invalid hand: {hand_str}")

    def get_sample_hand(self, rank: int, ordered_rank: int) -> str:
        """Retrieve a sample hand from the database for the given rank and ordered_rank."""
        self.cursor.execute('SELECT hand_str FROM hand_rankings WHERE rank = ? AND ordered_rank = ? LIMIT 1', (rank, ordered_rank))
        result = self.cursor.fetchone()
        if result:
            return result[0]
        raise ValueError(f"No sample hand found for rank {rank} and ordered_rank {ordered_rank}")

    def pad_hand(self, player_hand: List[Union[Card, str]], pad_to: int) -> List[Union[Card, str]]:
        """Pad the hand to the required length with 'Xx' placeholders."""
        num_padding = pad_to - len(player_hand)
        return player_hand + ['Xx'] * num_padding

    def _transform_wild_cards(self, cards: List[Card]) -> List[Union[Card, str]]:
        """Transform wild cards into special strings (e.g., 'W1', 'B1')."""
        wild_count = 0
        transformed_cards = []
        for card in cards:
            if card.is_wild and card.wild_type != 'BUG':  # NEHE doesn’t use bugs, but included for generality
                wild_count += 1
                transformed_cards.append(f"W{wild_count}")
            else:
                transformed_cards.append(card)
        return transformed_cards

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        self.conn.close()