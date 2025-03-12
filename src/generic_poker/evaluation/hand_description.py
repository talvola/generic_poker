import csv
from typing import List, Optional, Dict, Set
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.evaluation.types import HandRanking
from generic_poker.evaluation.evaluator import EvaluationType, HandEvaluator, evaluator
from generic_poker.evaluation.constants import RANK_ORDERS, BASE_RANKS
from pathlib import Path

class HandDescriber:
    """Generates human-readable descriptions for poker hands."""

    HAND_DESCRIPTION_FILES: Dict[EvaluationType, str] = {
        EvaluationType.HIGH: 'all_card_hands_description_high.csv',
        EvaluationType.LOW_A5: 'all_card_hands_description_a5_low.csv',
        EvaluationType.LOW_A5_HIGH: 'all_card_hands_description_a5_low.csv',
        EvaluationType.LOW_27: 'all_card_hands_description_27_low.csv',
        EvaluationType.HIGH_36CARD: 'all_card_hands_description_36card_ffh_high.csv',
        # Badugi and variants
        EvaluationType.BADUGI: 'all_card_hands_description_badugi.csv',
        EvaluationType.BADUGI_AH: 'all_card_hands_description_badugi.csv',
        EvaluationType.HIDUGI: 'all_card_hands_description_hidugi.csv',
        # 21 (pseudo-blackjack) variants
        EvaluationType.GAME_21: 'all_card_hands_description_21.csv',
        EvaluationType.GAME_21_6: 'all_card_hands_description_21_6.csv',
    }

    def __init__(self, eval_type: EvaluationType):
        """Initialize with evaluation type."""
        self.eval_type = eval_type
        self.descriptions = self._load_hand_descriptions()
        self.evaluator = HandEvaluator()

        # Get the proper rank ordering for this evaluation type
        self.rank_order = RANK_ORDERS.get(eval_type.value, BASE_RANKS)        

    def _load_hand_descriptions(self) -> Dict[int, str]:
        """Load hand descriptions from CSV files."""
        descriptions = {}

        # Special case for pip-count games - just return the number
        if self.eval_type in [
            EvaluationType.GAME_49, EvaluationType.GAME_58,
            EvaluationType.GAME_6, EvaluationType.GAME_ZERO,
            EvaluationType.GAME_ZERO_6, EvaluationType.LOW_PIP_6
        ]:
            descriptions.update({i: str(i) for i in self._generate_hand_names()})
            return descriptions  # Skip file loading if generated

        # Try to load from file if available
        file_name = self.HAND_DESCRIPTION_FILES.get(self.eval_type)
        if file_name:
            file_path = Path(__file__).parents[3] / 'data' / 'hand_descriptions' / file_name
            try:
                if file_path.exists():
                    with open(file_path, mode='r') as file:
                        reader = csv.DictReader(file)
                        for row in reader:
                            descriptions[int(row['Rank'])] = row['HandDescription']
            except (FileNotFoundError, KeyError) as e:
                # Fall back to basic descriptions if file not found or invalid
                if self.eval_type == EvaluationType.HIGH:
                    descriptions = self.BASIC_DESCRIPTIONS.copy()
                else:
                    # For other types, just generate generic descriptions
                    descriptions = {i: f"Rank {i}" for i in range(1, 11)}
                
        return descriptions

    def _generate_hand_names(self) -> List[int]:
        """Generate list of pip-count hand values."""
        if self.eval_type == EvaluationType.GAME_49:
            return list(range(49, -1, -1))
        elif self.eval_type == EvaluationType.GAME_58:
            return list(range(58, -1, -1))
        elif self.eval_type == EvaluationType.GAME_6:
            return list(range(6, 51))
        elif self.eval_type == EvaluationType.GAME_ZERO:
            return list(range(0, 50))
        elif self.eval_type == EvaluationType.GAME_ZERO_6:
            return list(range(0, 59))
        elif self.eval_type == EvaluationType.LOW_PIP_6:
            return list(range(1, 60))
        else:
            return []

    def describe_hand(self, cards: List[Card]) -> str:
        """Get a basic description of the hand."""
        return self._describe_hand(cards, detailed=False)

    def describe_hand_detailed(self, cards: List[Card]) -> str:
        """Get a detailed description of the hand."""
        return self._describe_hand(cards, detailed=True)
    
    def _get_highest_rank(self, cards: List[Card]) -> Rank:
        """
        Get highest rank in hand based on current evaluation type's rank order.
        
        This uses the rank ordering from constants.py to determine which
        rank is considered highest for the current evaluation type.
        """
        rank_values = [card.rank.value for card in cards]
        
        # Find the indices of each rank in the rank order
        # (Lower index = higher rank in the ordering)
        rank_indices = {r: self.rank_order.index(r) for r in rank_values}   
        
        # Get the rank with the lowest index (highest rank)
        highest_rank_value = min(rank_values, key=lambda r: rank_indices[r])
        
        # Return the Rank enum for this value
        return next(r for r in Rank if r.value == highest_rank_value)

    def _get_sorted_ranks(self, cards: List[Card]) -> List[Rank]:
        """
        Sort ranks by their position in the rank ordering for this evaluation type.
        Returns highest ranks first.
        """
        ranks = [card.rank for card in cards]
        return sorted(ranks, key=lambda r: self.rank_order.index(r.value))

    def _describe_hand(self, cards: List[Card], detailed: bool) -> str:
        """Internal method to describe a hand."""

        # Evaluate the hand
        hand_result = self.evaluator.evaluate_hand(cards, self.eval_type)
        if not hand_result or hand_result.rank == 0:
            return "Invalid Hand"
            
        # Get basic description
        basic_desc = self.descriptions.get(hand_result.rank, f"Rank {hand_result.rank}")
        
        # For non-detailed, just return the basic description
        if not detailed:
            return basic_desc
                
        # For detailed descriptions, add more information based on hand type
        cards_used = hand_result.cards_used or cards
        
        # i don't like this - maybe use the basic_desc instead?
        if self.eval_type in EvaluationType.HIGH:
            if hand_result.rank == 10:  # High Card
                return self._describe_high_card(cards_used)            
            elif hand_result.rank == 9:  # Pair
                return self._describe_pair(cards_used)
            elif hand_result.rank == 8:  # Two Pair
                return self._describe_two_pair(cards_used)
            elif hand_result.rank == 7:  # Three of a Kind
                return self._describe_three_of_kind(cards_used)
            elif hand_result.rank == 6:  # Straight
                return self._describe_straight(cards_used)
            elif hand_result.rank == 5:  # Flush
                return self._describe_flush(cards_used)
            elif hand_result.rank == 4:  # Full House
                return self._describe_full_house(cards_used)
            elif hand_result.rank == 3:  # Four of a Kind
                return self._describe_four_of_kind(cards_used)
            elif hand_result.rank == 2:  # Straight Flush
                return self._describe_straight_flush(cards_used)

        elif self.eval_type in EvaluationType.LOW_A5:
            if hand_result.rank == 6:
                return self._describe_four_of_kind(cards_used)
            elif hand_result.rank == 5:
                return self._describe_full_house(cards_used)
            elif hand_result.rank == 4:
                return self._describe_three_of_kind(cards_used)
            elif hand_result.rank == 3:
                return self._describe_two_pair(cards_used)
            elif hand_result.rank == 2:
                return self._describe_pair(cards_used)
            elif hand_result.rank == 1:
                return self._describe_high_card(cards_used)
            
        elif self.eval_type in EvaluationType.LOW_27:
            if hand_result.rank == 1:  # High Card
                return self._describe_high_card(cards_used)            
            elif hand_result.rank == 2:  # Pair
                return self._describe_pair(cards_used)
            elif hand_result.rank == 3:  # Two Pair
                return self._describe_two_pair(cards_used)
            elif hand_result.rank == 4:  # Three of a Kind
                return self._describe_three_of_kind(cards_used)
            elif hand_result.rank == 5:  # Straight
                return self._describe_straight(cards_used)
            elif hand_result.rank == 6:  # Flush
                return self._describe_flush(cards_used)
            elif hand_result.rank == 7:  # Full House
                return self._describe_full_house(cards_used)
            elif hand_result.rank == 8:  # Four of a Kind
                return self._describe_four_of_kind(cards_used)
            elif hand_result.rank == 9:  # Straight Flush
                return self._describe_straight_flush(cards_used)
                
        # Default to basic description if no detailed version available
        return basic_desc
    
    def _describe_full_house(self, cards: List[Card]) -> str:
        """Generate detailed description for Full House."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
        # Find the rank with 3 cards (trips) and the rank with 2 cards (pair)
        trips_rank = None
        pair_rank = None
        for rank, count in rank_counts.items():
            if count == 3:
                trips_rank = rank
            elif count == 2:
                pair_rank = rank
                
        if trips_rank and pair_rank:
            return f"Full House, {trips_rank.plural_name} over {pair_rank.plural_name}"
        return "Full House"

    def _describe_four_of_kind(self, cards: List[Card]) -> str:
        """Generate detailed description for Four of a Kind."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
        for rank, count in rank_counts.items():
            if count == 4:
                return f"Four {rank.plural_name}"
        return "Four of a Kind"

    def _describe_three_of_kind(self, cards: List[Card]) -> str:
        """Generate detailed description for Three of a Kind."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
        for rank, count in rank_counts.items():
            if count == 3:
                return f"Three {rank.plural_name}"
        return "Three of a Kind"

    def _describe_two_pair(self, cards: List[Card]) -> str:
        """Generate detailed description for Two Pair."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
        pairs = []
        for rank, count in rank_counts.items():
            if count == 2:
                pairs.append(rank)
                
        if len(pairs) == 2:
            # Sort pairs by rank order (higher rank first)
            pairs.sort(key=lambda r: self.rank_order.index(r.value))
            return f"Two Pair, {pairs[0].plural_name} and {pairs[1].plural_name}"
        return "Two Pair"

    def _describe_pair(self, cards: List[Card]) -> str:
        """Generate detailed description for Pair."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
        for rank, count in rank_counts.items():
            if count == 2:
                return f"Pair of {rank.plural_name}"
        return "Pair"

    def _describe_high_card(self, cards: List[Card]) -> str:
        """Generate detailed description for High Card."""
        highest_rank = self._get_highest_rank(cards)
        return f"{highest_rank.full_name} High"

    def _describe_straight_flush(self, cards: List[Card]) -> str:
        """Generate detailed description for Straight Flush."""
        highest_rank = self._get_highest_rank(cards)
        return f"{highest_rank.full_name}-high Straight Flush"

    def _describe_flush(self, cards: List[Card]) -> str:
        """Generate detailed description for Flush."""
        highest_rank = self._get_highest_rank(cards)
        return f"{highest_rank.full_name}-high Flush"

    def _describe_straight(self, cards: List[Card]) -> str:
        """Generate detailed description for Straight."""
        highest_rank = self._get_highest_rank(cards)
        return f"{highest_rank.full_name}-high Straight"