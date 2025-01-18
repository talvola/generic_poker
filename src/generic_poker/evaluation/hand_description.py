import csv
from typing import List, Optional, Dict
from generic_poker.core.card import Card, Rank
from generic_poker.evaluation.types import HandRanking
from generic_poker.evaluation.evaluator import EvaluationType, HandEvaluator
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
        self.eval_type = eval_type
        self.descriptions = self._load_hand_descriptions()

    def _load_hand_descriptions(self) -> Dict[int, str]:
        descriptions = {}
        if self.eval_type in [
            EvaluationType.GAME_49, EvaluationType.GAME_58,
            EvaluationType.GAME_6, EvaluationType.GAME_ZERO,
            EvaluationType.GAME_ZERO_6, EvaluationType.LOW_PIP_6
        ]:
            descriptions.update({i: str(i) for i in self._generate_hand_names()})
            return descriptions  # Skip file loading if generated

        file_name = self.HAND_DESCRIPTION_FILES.get(self.eval_type)
        if file_name:
            file_path = Path('data/hand_descriptions') / file_name
            if file_path.exists():
                with open(file_path, mode='r') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        descriptions[int(row['Rank'])] = row['HandDescription']
            else:
                raise FileNotFoundError(f"Description file not found: {file_path}")
        else:
            raise ValueError(f"No description file mapped for evaluation type: {self.eval_type}")
        return descriptions

    def _generate_hand_names(self) -> List[int]:
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
        return self._describe_hand(cards, detailed=False)

    def describe_hand_detailed(self, cards: List[Card]) -> str:
        return self._describe_hand(cards, detailed=True)

    def _describe_hand(self, cards: List[Card], detailed: bool) -> str:
        evaluator = HandEvaluator()
        hand_result = evaluator.evaluate_hand(cards, self.eval_type)
        print('hand_result', hand_result)
        description = self.descriptions.get(hand_result.rank, "Unknown Hand")

        print('detailed: ', detailed, ' hand_result.rank: ', hand_result.rank, 'description: ', description, ' hand_result.cards_used: ', hand_result.cards_used)

        if detailed and description == 'Full House' and hand_result.cards_used:  # Full House
            ranks = [card.rank for card in hand_result.cards_used]
            triple_rank = max(set(ranks), key=ranks.count)
            pair_rank = min(set(ranks), key=ranks.count)
            description = f"Full House, {triple_rank.value}s over {pair_rank.value}s"

        return description
