import itertools
from re import A

class PokerHandEvaluator:
    def __init__(self):
        self.hand_rankings = {}

    def generate_hands(self):
        ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        all_hands = []
        straight_flushes = []

        # No royal flushes - but still use 2 as ordered rank to be consistent with regular high hands

        # Generate straight flushes 
        sf_ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        
        # restart ordered_rank each rank for now
        ordered_rank = 1
        for i in range(len(sf_ranks) - 4):
            for suit in suits:
                hand = [sf_ranks[j] + suit for j in range(i, i+5)]
                hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                all_hands.append((hand, 2, ordered_rank))
                straight_flushes.append(hand)
            ordered_rank += 1
        
        # add in A-5 straight flush
        a5_ranks = ['A', '5', '4', '3', '2']
        for suit in suits:
            hand = [a5_ranks[j] + suit for j in range(0, 5)]
            hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
            all_hands.append((hand, 2, ordered_rank))
            straight_flushes.append(hand)        

        # Generate four of a kinds
        ordered_rank = 1  # back to 1 to start four of a kinds

        for rank in ranks:
            added_hand = False
            for suit1, suit2, suit3, suit4 in itertools.combinations(suits, 4):
                hand = [rank + s for s in (suit1, suit2, suit3, suit4)]
                for kicker_rank in ranks:
                    if kicker_rank != rank:
                        for suit_kicker in suits:
                            four_hand = hand + [kicker_rank + suit_kicker]                            
                            four_hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                            all_hands.append((four_hand, 3, ordered_rank))
                            added_hand = True
                    else:
                        added_hand = False
                    if added_hand:
                        ordered_rank += 1  

        # Generate flushes
        ordered_rank = 1  # back to 1

        for combination in itertools.combinations(ranks, 5):
            added_hand = False
            for suit in suits:
                # Check if it's a straight or royal flush, skip if true
                straight_flush_hand = [rank + suit for rank in combination]
                if any(hand == straight_flush_hand for hand in straight_flushes):
                    continue
                # Generate the flush hand
                hand = [rank + suit for rank in combination]
                hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                all_hands.append((hand, 4, ordered_rank))
                added_hand = True
            if added_hand:
                ordered_rank += 1

        # Generate full houses

        ordered_rank = 1  # back to 1 

        for rank1, rank2 in itertools.permutations(ranks, 2):
            for suit1, suit2, suit3 in itertools.combinations(suits, 3):
                three_of_a_kind = [rank1 + s for s in (suit1, suit2, suit3)]
                for suit4, suit5 in itertools.combinations(suits, 2):
                    pair = [rank2 + s for s in (suit4, suit5)]
                    hand = three_of_a_kind + pair
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 5, ordered_rank))
            ordered_rank += 1

        def generate_straights(s_ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for i in range(len(s_ranks) - 4):
                straight = s_ranks[i:i+5]
                for suits_combination in itertools.product(suits, repeat=5):
                    straight_hand = [rank + suit for rank, suit in zip(straight, suits_combination)]
                    if any(hand == straight_hand for hand in straight_flushes):
                        continue
                    straight_hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((straight_hand, 6, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1                    
            return ordered_rank

        # Generate straights
        ordered_rank = 1  # back to 1
        ordered_rank = generate_straights(ranks, suits, all_hands, ordered_rank)

        # Add A-5 straight
        straight = ['A', '5', '4', '3', '2']
        generate_straights(straight, suits, all_hands, ordered_rank)

        # Generate three of a kind
        ordered_rank = 1  # back to 1

        for rank in ranks:
            for kicker_rank1 in ranks:
                if kicker_rank1 == rank:
                    continue
                for kicker_rank2 in ranks:
                    if kicker_rank2 == rank or self._rank_to_value(kicker_rank2) >= self._rank_to_value(kicker_rank1):
                        continue
                    added_hand = False
                    for suit_combinations in itertools.combinations(suits, 3):
                        for suit4, suit5 in itertools.product(suits, repeat=2):
                            hand = [rank + suit for suit in suit_combinations]
                            hand += [kicker_rank1 + suit4, kicker_rank2 + suit5]
                            hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                            all_hands.append((hand, 7, ordered_rank))
                            added_hand = True
                    if added_hand:
                        ordered_rank += 1



        # Generate two pairs

        def generate_two_pairs(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank1, rank2 in itertools.combinations(ranks, 2):
                for kicker_rank in ranks:
                    if kicker_rank == rank1 or kicker_rank == rank2:
                        continue 
                    for suit1, suit2 in itertools.combinations(suits, 2):
                        for suit3, suit4 in itertools.combinations(suits, 2):
                            for suit5 in suits:
                                hand = [rank1 + suit1, rank1 + suit2, rank2 + suit3, rank2 + suit4, kicker_rank + suit5]
                                hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                                all_hands.append((hand, 8, ordered_rank))
                                added_hand = True
                    if added_hand:
                        ordered_rank += 1
            return ordered_rank
    
        ordered_rank = 1  # back to 1

        ordered_rank = generate_two_pairs(ranks, suits, all_hands, ordered_rank)

        # Generate one pair

        def generate_one_pair(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for pair_rank in ranks:
                remaining_ranks = ranks[:]
                remaining_ranks.remove(pair_rank)
                for kicker_rank1 in remaining_ranks:
                    added_hand = False
                    for kicker_rank2 in remaining_ranks:
                        added_hand = False
                        if self._rank_to_value(kicker_rank2) >= self._rank_to_value(kicker_rank1):
                            continue
                        for kicker_rank3 in remaining_ranks:
                            added_hand = False
                            if self._rank_to_value(kicker_rank3) >= self._rank_to_value(kicker_rank1) or self._rank_to_value(kicker_rank3) >= self._rank_to_value(kicker_rank2):
                                continue
                            for suit_combinations in itertools.combinations(suits, 2):
                                for suit1, suit2, suit3 in itertools.product(suits, repeat=3):
                                    hand = [pair_rank + suit for suit in suit_combinations]
                                    hand += [kicker_rank1 + suit1, kicker_rank2 + suit2, kicker_rank3 + suit3]
                                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                                    all_hands.append((hand, 9, ordered_rank))
                                    added_hand = True
                            if added_hand:
                                ordered_rank += 1
            return ordered_rank

        ordered_rank = 1  # back to 1

        ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank)

        # Generate High Card hands

        existing_hands = set()
        for hand_tuple in all_hands:
            existing_hands.add(tuple(hand_tuple[0]))

        def generate_high_card(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank1, rank2, rank3, rank4, rank5 in itertools.combinations(ranks, 5):
                added_hand = False           
                for suit_combinations in itertools.product(suits, repeat=5):
                    hand = [rank + suit for rank, suit in zip([rank1, rank2, rank3, rank4, rank5], suit_combinations)]
                    hand_key = tuple(hand)
                    if hand_key in existing_hands:
                        continue
                    existing_hands.add(hand_key)
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 10, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank

        ordered_rank = 1  # back to 1
        ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank)

        return all_hands

    def _rank_to_value(self, rank):
        rank_values = {'2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8, 'T': 9, 'J': 10, 'Q': 11, 'K': 12, 'A': 13}
        return rank_values[rank]

# Create an instance of PokerHandEvaluator
hand_evaluator = PokerHandEvaluator()

# Generate all possible hands
all_hands = hand_evaluator.generate_hands()

# Open a file for writing
with open('all_card_hands_ranked_27_ja_ffh_high.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

print('File generated successfully.')
