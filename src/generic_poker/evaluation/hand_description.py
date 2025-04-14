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
        # Wild card hands
        EvaluationType.HIGH_WILD: 'all_card_hands_description_high_wild_bug.csv',
        # Less than 5 cards
        EvaluationType.TWO_CARD_HIGH: 'all_card_hands_description_two_card_high.csv',       
        # Special hands
        EvaluationType.NE_SEVEN_CARD_HIGH: 'all_card_hands_description_ne_seven_card_high.csv',
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
            
        elif self.eval_type in EvaluationType.HIGH_WILD:
            # for wild hands, let's use this approach:
            # we know the rank and ordered_rank of the hand
            # we will look up an entry from the HIGH evaluation 
            # for the equivalent rank (the rank - 1) to get a sample
            # hand, and then use that description.    
            #
            # Five of a kind will still be handled normally.
            if hand_result.rank == 1:  # Five of a Kind
                return self._describe_five_of_kind(cards_used)         
                
            high_cards = evaluator.get_sample_hand(EvaluationType.HIGH, hand_result.rank - 1, hand_result.ordered_rank)
            
            if hand_result.rank == 11:  # High Card
                return self._describe_high_card(high_cards)            
            elif hand_result.rank == 10:  # Pair
                return self._describe_pair(high_cards)
            elif hand_result.rank == 9:  # Two Pair
                return self._describe_two_pair(high_cards)
            elif hand_result.rank == 8:  # Three of a Kind
                return self._describe_three_of_kind(high_cards)
            elif hand_result.rank == 7:  # Straight
                return self._describe_straight(high_cards)
            elif hand_result.rank == 6:  # Flush
                return self._describe_flush(high_cards)
            elif hand_result.rank == 5:  # Full House
                return self._describe_full_house(high_cards)
            elif hand_result.rank == 4:  # Four of a Kind
                return self._describe_four_of_kind(high_cards)
            elif hand_result.rank == 3:  # Straight Flush
                return self._describe_straight_flush(high_cards)            
            elif hand_result.rank == 1:  # Five of a Kind
                return self._describe_five_of_kind(high_cards)            

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
            
        elif self.eval_type in EvaluationType.TWO_CARD_HIGH:
            if hand_result.rank == 2:  # High Card
                return self._describe_high_card(cards_used)            
            elif hand_result.rank == 1:  # Pair            
                return self._describe_pair(cards_used)
            
        # Handle NE_SEVEN_CARD_HIGH (7-card hands)
        elif self.eval_type == EvaluationType.NE_SEVEN_CARD_HIGH:
            if hand_result.rank == 1:  # Grand Straight Flush
                return self._describe_straight_flush(cards_used, prefix='Grand', min_length = 7)
            elif hand_result.rank == 2:  # Palace
                return self._describe_palace(cards_used)
            elif hand_result.rank == 3:  # Long Straight Flush
                return self._describe_straight_flush(cards_used, prefix='Long', min_length = 6)  # Treat as a straight flush
            elif hand_result.rank == 4:  # Grand Flush
                return self._describe_flush(cards_used, prefix='Grand', min_length = 7)
            elif hand_result.rank == 5:  # Mansion
                return self._describe_mansion(cards_used)
            elif hand_result.rank == 6:  # Straight Flush
                return self._describe_straight_flush(cards_used, min_length = 5)  # Treat as a straight flush
            elif hand_result.rank == 7:  # Hotel
                return self._describe_hotel(cards_used)
            elif hand_result.rank == 8:  # Villa
                return self._describe_villa(cards_used)
            elif hand_result.rank == 9:  # Grand Straight
                return self._describe_straight(cards_used, prefix='Grand', min_length = 7)
            elif hand_result.rank == 10:  # Four of a Kind
                return self._describe_four_of_kind(cards_used)
            elif hand_result.rank == 11:  # Long Flush
                return self._describe_flush(cards_used, prefix='Long', min_length = 6)
            elif hand_result.rank == 12:  # Long Straight
                return self._describe_straight(cards_used, prefix='Long', min_length = 6)
            elif hand_result.rank == 13:  # Three Pair
                return self._describe_three_pair(cards_used)
            elif hand_result.rank == 14:  # Full House
                return self._describe_full_house(cards_used)
            elif hand_result.rank == 15:  # Flush
                return self._describe_flush(cards_used)
            elif hand_result.rank == 16:  # Straight
                return self._describe_straight(cards_used)
            elif hand_result.rank == 17:  # Three of a Kind
                return self._describe_three_of_kind(cards_used)
            elif hand_result.rank == 18:  # Two Pair
                return self._describe_two_pair(cards_used)
            elif hand_result.rank == 19:  # One Pair
                return self._describe_pair(cards_used)
            elif hand_result.rank == 20:  # High Card
                return self._describe_high_card(cards_used)            
                
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

    def _describe_straight_flush(self, cards: List[Card], prefix: Optional[str] = None, min_length: int = 5) -> str:
        """
        Generate detailed description for Straight Flush.
        
        Args:
            cards: List of cards to describe.
            prefix: Optional prefix (e.g., 'Grand', 'Long') to include in the description.
            min_length: Minimum length of the straight flush to find (e.g., 5, 6, or 7).
        
        Returns:
            Detailed description of the straight flush.
        """
        # Find the straight flush
        straight_flush_cards = self._find_straight_flush(cards, min_length=min_length)
        if not straight_flush_cards:
            return "Invalid Straight Flush"
        
        # Get the highest rank of the straight flush
        highest_rank = self._get_highest_rank(straight_flush_cards)
        
        if prefix:
            return f"{highest_rank.full_name}-high {prefix} Straight Flush"
        return f"{highest_rank.full_name}-high Straight Flush"

    def _describe_flush(self, cards: List[Card], prefix: Optional[str] = None, min_length: int = 5) -> str:
        """
        Generate detailed description for Flush.
        
        Args:
            cards: List of cards to describe.
            prefix: Optional prefix (e.g., 'Grand', 'Long') to include in the description.
            min_length: Minimum length of the flush to find (e.g., 5, 6, or 7).
        
        Returns:
            Detailed description of the flush.
        """
        # Find the flush
        flush_cards = self._find_flush(cards, min_length=min_length)
        if not flush_cards:
            return "Invalid Flush"
        
        # Get the highest rank of the flush
        highest_rank = self._get_highest_rank(flush_cards)
        
        if prefix:
            return f"{highest_rank.full_name}-high {prefix} Flush"
        return f"{highest_rank.full_name}-high Flush"

    def _describe_straight(self, cards: List[Card], prefix: Optional[str] = None, min_length: int = 5) -> str:
        """
        Generate detailed description for Straight.
        
        Args:
            cards: List of cards to describe.
            prefix: Optional prefix (e.g., 'Grand', 'Long') to include in the description.
            min_length: Minimum length of the straight to find (e.g., 5, 6, or 7).
        
        Returns:
            Detailed description of the straight.
        """
        # Find the straight
        straight_cards = self._find_straight(cards, min_length=min_length)
        if not straight_cards:
            return "Invalid Straight"
        
        # Get the highest rank of the straight
        highest_rank = self._get_highest_rank(straight_cards)
        
        if prefix:
            return f"{highest_rank.full_name}-high {prefix} Straight"
        return f"{highest_rank.full_name}-high Straight"
    
    def _describe_five_of_kind(self, cards: List[Card]) -> str:
        """Generate detailed description for five of a Kind."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
        for rank, count in rank_counts.items():
            if count == 4:
                return f"Five {rank.plural_name}"
        return "Five of a Kind"    
    
    def _describe_palace(self, cards: List[Card]) -> str:
        """Generate detailed description for Palace (four of a kind + three of a kind)."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        four_rank = None
        three_rank = None
        for rank, count in rank_counts.items():
            if count == 4:
                four_rank = rank
            elif count == 3:
                three_rank = rank
        
        if four_rank and three_rank:
            return f"Palace, {four_rank.plural_name} over {three_rank.plural_name}"
        return "Palace"

    def _describe_mansion(self, cards: List[Card]) -> str:
        """Generate detailed description for Mansion (four of a kind + pair)."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        four_rank = None
        pair_rank = None
        for rank, count in rank_counts.items():
            if count == 4:
                four_rank = rank
            elif count == 2:
                pair_rank = rank
        
        if four_rank and pair_rank:
            return f"Mansion, {four_rank.plural_name} over {pair_rank.plural_name}"
        return "Mansion"

    def _describe_villa(self, cards: List[Card]) -> str:
        """Generate detailed description for Hotel (full house + pair)."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        three_rank = None
        pair_ranks = []
        for rank, count in rank_counts.items():
            if count == 3:
                three_rank = rank
            elif count == 2:
                pair_ranks.append(rank)
        
        if three_rank and len(pair_ranks) >= 2:
            # Take the higher pair for the full house, lower pair as the extra
            pair_ranks.sort(key=lambda r: self.rank_order.index(r.value))
            return f"Villa, {three_rank.plural_name} over {pair_ranks[0].plural_name} with {pair_ranks[1].plural_name}"
        return "Villa"
    
    def _describe_hotel(self, cards: List[Card]) -> str:
        """Generate detailed description for Hotel (2 three-of-a-kind)."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        three_ranks = []
        for rank, count in rank_counts.items():
            if count == 3:
                three_ranks.append(rank)
        
        if three_ranks and len(three_ranks) >= 2:
            # Take the higher pair for the full house, lower pair as the extra
            three_ranks.sort(key=lambda r: self.rank_order.index(r.value))
            return f"Hotel, {three_ranks[0].plural_name} and {three_ranks[1].plural_name}"
        
        return "Hotel"    

    def _describe_three_pair(self, cards: List[Card]) -> str:
        """Generate detailed description for Three Pair."""
        ranks = [card.rank for card in cards]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        pairs = [rank for rank, count in rank_counts.items() if count == 2]
        pairs.sort(key=lambda r: self.rank_order.index(r.value))  # Highest to lowest
        
        if len(pairs) >= 3:
            return f"Three Pair, {pairs[0].plural_name}, {pairs[1].plural_name}, and {pairs[2].plural_name}"
        return "Three Pair"    
    
    def _find_straight_flush(self, cards: List[Card], min_length: int = 5) -> List[Card]:
        """
        Find the longest straight flush in the hand.
        
        Args:
            cards: List of cards to analyze.
            min_length: Minimum length of the straight flush to find (e.g., 5 for a regular straight flush, 6 for a long straight flush).
        
        Returns:
            List of cards forming the straight flush, sorted highest to lowest.
            Returns empty list if no straight flush of at least min_length is found.
        """
        # Group cards by suit
        suit_groups = {}
        for card in cards:
            suit = card.suit
            if suit not in suit_groups:
                suit_groups[suit] = []
            suit_groups[suit].append(card)
        
        # Check each suit for a straight flush
        best_straight_flush = []
        for suit, suit_cards in suit_groups.items():
            if len(suit_cards) < min_length:
                continue
            
            # Sort cards by rank (highest to lowest)
            sorted_cards = sorted(suit_cards, key=lambda c: self.rank_order.index(c.rank.value))
            
            # Look for consecutive sequences
            current_sequence = [sorted_cards[0]]
            for i in range(1, len(sorted_cards)):
                prev_rank_idx = self.rank_order.index(current_sequence[-1].rank.value)
                curr_rank_idx = self.rank_order.index(sorted_cards[i].rank.value)
                if curr_rank_idx == prev_rank_idx + 1:  # Consecutive ranks
                    current_sequence.append(sorted_cards[i])
                else:
                    # Check if current sequence is long enough
                    if len(current_sequence) >= min_length and len(current_sequence) > len(best_straight_flush):
                        best_straight_flush = current_sequence
                    # Start a new sequence
                    current_sequence = [sorted_cards[i]]
            
            # Check the last sequence
            if len(current_sequence) >= min_length and len(current_sequence) > len(best_straight_flush):
                best_straight_flush = current_sequence
        
        # Handle Ace-low straights (e.g., A-2-3-4-5 or A-2-3-4-5-6)
        for suit, suit_cards in suit_groups.items():
            if len(suit_cards) < min_length:
                continue
            sorted_cards = sorted(suit_cards, key=lambda c: self.rank_order.index(c.rank.value))
            ace_low_cards = []
            ace = None
            for card in sorted_cards:
                if card.rank.value == 'A':
                    ace = card
                else:
                    ace_low_cards.append(card)
            if ace and len(ace_low_cards) >= min_length - 1:
                # Check for A-2-3-4-5...
                current_sequence = [ace]
                for i in range(len(self.rank_order) - 1, -1, -1):  # Start from lowest rank (2)
                    rank = self.rank_order[i]
                    if len(current_sequence) == min_length:
                        break
                    for card in ace_low_cards:
                        if card.rank.value == rank:
                            current_sequence.append(card)
                            break
                if len(current_sequence) == min_length and len(current_sequence) > len(best_straight_flush):
                    # Sort Ace-low sequence correctly (e.g., 5-4-3-2-A)
                    current_sequence.sort(key=lambda c: self.rank_order.index(c.rank.value))
                    current_sequence.insert(0, current_sequence.pop())  # Move Ace to end
                    best_straight_flush = current_sequence
        
        return best_straight_flush    
    
    def _find_straight(self, cards: List[Card], min_length: int = 5) -> List[Card]:
        """
        Find the longest straight in the hand.
        
        Args:
            cards: List of cards to analyze.
            min_length: Minimum length of the straight to find (e.g., 5, 6, or 7).
        
        Returns:
            List of cards forming the straight, sorted highest to lowest.
            Returns empty list if no straight of at least min_length is found.
        """
        # Remove duplicates by keeping the highest suit for each rank
        rank_to_card = {}
        for card in cards:
            rank = card.rank
            if rank not in rank_to_card or SUIT_ORDER[card.suit] < SUIT_ORDER[rank_to_card[rank].suit]:
                rank_to_card[rank] = card
        
        # Sort cards by rank (highest to lowest)
        unique_cards = list(rank_to_card.values())
        sorted_cards = sorted(unique_cards, key=lambda c: self.rank_order.index(c.rank.value))
        
        # Look for consecutive sequences
        best_straight = []
        current_sequence = [sorted_cards[0]]
        for i in range(1, len(sorted_cards)):
            prev_rank_idx = self.rank_order.index(current_sequence[-1].rank.value)
            curr_rank_idx = self.rank_order.index(sorted_cards[i].rank.value)
            if curr_rank_idx == prev_rank_idx + 1:  # Consecutive ranks
                current_sequence.append(sorted_cards[i])
            else:
                # Check if current sequence is long enough
                if len(current_sequence) >= min_length and len(current_sequence) > len(best_straight):
                    best_straight = current_sequence
                # Start a new sequence
                current_sequence = [sorted_cards[i]]
        
        # Check the last sequence
        if len(current_sequence) >= min_length and len(current_sequence) > len(best_straight):
            best_straight = current_sequence
        
        # Handle Ace-low straights (e.g., A-2-3-4-5 or A-2-3-4-5-6)
        ace_low_cards = []
        ace = None
        for card in sorted_cards:
            if card.rank.value == 'A':
                ace = card
            else:
                ace_low_cards.append(card)
        if ace and len(ace_low_cards) >= min_length - 1:
            # Check for A-2-3-4-5...
            current_sequence = [ace]
            for i in range(len(self.rank_order) - 1, -1, -1):  # Start from lowest rank (2)
                rank = self.rank_order[i]
                if len(current_sequence) == min_length:
                    break
                for card in ace_low_cards:
                    if card.rank.value == rank:
                        current_sequence.append(card)
                        break
            if len(current_sequence) == min_length and len(current_sequence) > len(best_straight):
                # Sort Ace-low sequence correctly (e.g., 5-4-3-2-A)
                current_sequence.sort(key=lambda c: self.rank_order.index(c.rank.value))
                current_sequence.insert(0, current_sequence.pop())  # Move Ace to end
                best_straight = current_sequence
        
        return best_straight    
    
    def _find_flush(self, cards: List[Card], min_length: int = 5) -> List[Card]:
        """
        Find the longest flush in the hand.
        
        Args:
            cards: List of cards to analyze.
            min_length: Minimum length of the flush to find (e.g., 5, 6, or 7).
        
        Returns:
            List of cards forming the flush, sorted highest to lowest.
            Returns empty list if no flush of at least min_length is found.
        """
        # Group cards by suit
        suit_groups = {}
        for card in cards:
            suit = card.suit
            if suit not in suit_groups:
                suit_groups[suit] = []
            suit_groups[suit].append(card)
        
        # Find the suit with the most cards
        best_flush = []
        for suit, suit_cards in suit_groups.items():
            if len(suit_cards) >= min_length:
                # Sort cards by rank (highest to lowest)
                sorted_cards = sorted(suit_cards, key=lambda c: self.rank_order.index(c.rank.value))
                # Take the top min_length cards (or all for Grand Flush)
                flush_cards = sorted_cards[:min_length] if len(sorted_cards) > min_length else sorted_cards
                if len(flush_cards) > len(best_flush):
                    best_flush = flush_cards
        
        return best_flush    