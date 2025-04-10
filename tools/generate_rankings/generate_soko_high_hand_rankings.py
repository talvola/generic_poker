import itertools
from re import A

# This code generates all possible poker hands and ranks them according to Canadian Stud/Soko poker hand rankings.
# The additions to standard 'high hand' poker are a four straight and four flush between One Pair and Two Pair.

class PokerHandEvaluator:
    def __init__(self):
        self.hand_rankings = {}

    def generate_hands(self):
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        all_hands = []
        straight_flushes = []

        # Generate royal flushes
        suits = ['s', 'h', 'd', 'c']
        rank = 'A'
        ordered_rank = 1
        for suit in suits:
            hand = [(rank + suit), ('K' + suit), ('Q' + suit), ('J' + suit), ('T' + suit)]
            hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
            all_hands.append((hand, 1, ordered_rank))
            straight_flushes.append(hand)

        # Generate straight flushes - don't use Ace as high
        sf_ranks = ['K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        
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

        # Generate full houses

        ordered_rank = 1  # back to 1 

        for rank1, rank2 in itertools.permutations(ranks, 2):
            for suit1, suit2, suit3 in itertools.combinations(suits, 3):
                three_of_a_kind = [rank1 + s for s in (suit1, suit2, suit3)]
                for suit4, suit5 in itertools.combinations(suits, 2):
                    pair = [rank2 + s for s in (suit4, suit5)]
                    hand = three_of_a_kind + pair
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 4, ordered_rank))
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
                all_hands.append((hand, 5, ordered_rank))
                added_hand = True
            if added_hand:
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

        # Initialize existing_hands after Two Pair
        existing_hands = set()
        for hand, _, _ in all_hands:
            existing_hands.add(tuple(hand))

        # Generate all four-rank combinations
        # Each combination is sorted internally from high to low rank
        four_rank_combinations = [tuple(sorted(comb, key=lambda x: ranks.index(x))) for comb in itertools.combinations(ranks, 4)]

        # Sort the combinations by poker strength using rank indices
        sorted_four_rank_combinations = sorted(four_rank_combinations, key=lambda x: tuple(ranks.index(r) for r in x))


        # Generate all four-rank combinations, sorted by strength
        four_rank_combinations = [tuple(sorted(comb, key=lambda x: ranks.index(x))) for comb in itertools.combinations(ranks, 4)]
        sorted_four_rank_combinations = sorted(four_rank_combinations, key=lambda x: tuple(ranks.index(r) for r in x))

        # Generate four-card flushes with flush_rank
        four_card_flushes = []
        flush_rank = 0
        for four_ranks in sorted_four_rank_combinations:
            for flush_suit in suits:
                four_cards = [r + flush_suit for r in four_ranks]
                four_card_flushes.append((four_cards, flush_rank))
            flush_rank += 1

        # Group four-card flushes by flush_rank
        from itertools import groupby
        from operator import itemgetter

        ordered_rank = 1
        for flush_rank, group in groupby(four_card_flushes, key=itemgetter(1)):
            four_cards_list = [item[0] for item in group]  # List of four-card flushes with this flush_rank
            print(f"Processing flush_rank {flush_rank} with four-card sets: {[fc for fc in four_cards_list]}")
            
            # Iterate through kicker ranks from high to low
            for kicker_rank in ranks:
                added_hand = False
                # For each four-card flush in this flush_rank group
                for four_cards in four_cards_list:
                    flush_suit = four_cards[0][1]  # Extract suit from first card (e.g., 's' from 'As')
                    # Try all suits for the kicker
                    for kicker_suit in suits:
                        if kicker_suit == flush_suit:
                            continue  # Kicker must be a different suit
                        fifth_card = kicker_rank + kicker_suit
                        if fifth_card in four_cards:
                            continue  # Avoid duplicate cards
                        hand = four_cards + [fifth_card]
                        hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))
                        hand_tuple = tuple(hand)
                        if hand_tuple not in existing_hands:
                            all_hands.append((hand, 9, ordered_rank))
                            existing_hands.add(hand_tuple)
                            added_hand = True
                            print(f"Added hand {hand} with ordered_rank {ordered_rank}")
                # Increment ordered_rank only if we added at least one hand for this kicker rank
                if added_hand:
                    ordered_rank += 1
                    print(f"Incremented ordered_rank to {ordered_rank}")        

        # for four_ranks in sorted_four_rank_combinations:
        #     #print(f"Generating four flush with ranks: {four_ranks}")
        #     for flush_suit in suits:
        #         four_cards = [r + flush_suit for r in four_ranks]
        #         #print(f"   Generating four flush with suits: {four_cards}")
        #         # Generate kickers from highest to lowest rank
        #         for kicker_rank in ranks:
        #             for kicker_suit in suits:
        #                 if kicker_suit == flush_suit:
        #                     continue
        #                 fifth_card = kicker_rank + kicker_suit
        #                 if fifth_card in four_cards:
        #                     continue
        #                 #print(f"       Generating fifth card: {fifth_card}")
        #                 hand = four_cards + [fifth_card]
        #                 hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))
        #                 hand_tuple = tuple(hand)
        #                 if hand_tuple not in existing_hands:
        #                     all_hands.append((hand, 9, ordered_rank))
        #                     existing_hands.add(hand_tuple)
        #     #print(f"Incrementing ordered_rank")
        #     ordered_rank += 1


        # Define four-card straight sequences
        straight_sequences = [
            ['A', 'K', 'Q', 'J'],  # A-high
            ['K', 'Q', 'J', 'T'],
            ['Q', 'J', 'T', '9'],
            ['J', 'T', '9', '8'],
            ['T', '9', '8', '7'],
            ['9', '8', '7', '6'],
            ['8', '7', '6', '5'],
            ['7', '6', '5', '4'],
            ['6', '5', '4', '3'],
            ['5', '4', '3', '2'],
            ['4', '3', '2', 'A']   # 4-high, A low
        ]

        ordered_rank = 1
        for sequence in straight_sequences:
            # Step 1: Generate all four-card straights for this sequence
            four_card_straights = []
            for suit_comb in itertools.product(suits, repeat=4):
                four_cards = [sequence[i] + suit_comb[i] for i in range(4)]
                four_card_straights.append(four_cards)
            
            # Step 2: Iterate through kicker ranks from high to low
            for kicker_rank in ranks:
                added_hand = False
                # For each four-card straight in this sequence
                for four_cards in four_card_straights:
                    # Try all suits for the kicker
                    for kicker_suit in suits:
                        fifth_card = kicker_rank + kicker_suit
                        if fifth_card in four_cards:
                            continue  # Skip if the fifth card duplicates one in the four-card straight
                        hand = four_cards + [fifth_card]
                        hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))
                        hand_tuple = tuple(hand)
                        if hand_tuple not in existing_hands:
                            all_hands.append((hand, 10, ordered_rank))
                            existing_hands.add(hand_tuple)
                            added_hand = True
                # Step 3: Increment ordered_rank if we added any hands for this kicker
                if added_hand:
                    ordered_rank += 1

        # Generate One Pair (Rank 11, updated from 9)
        def generate_one_pair(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for pair_rank in ranks:
                remaining_ranks = ranks[:]
                remaining_ranks.remove(pair_rank)
                for kicker_rank1 in remaining_ranks:
                    for kicker_rank2 in remaining_ranks:
                        if self._rank_to_value(kicker_rank2) >= self._rank_to_value(kicker_rank1):
                            continue
                        for kicker_rank3 in remaining_ranks:
                            if self._rank_to_value(kicker_rank3) >= self._rank_to_value(kicker_rank1) or self._rank_to_value(kicker_rank3) >= self._rank_to_value(kicker_rank2):
                                continue
                            added_hand = False
                            for suit_combinations in itertools.combinations(suits, 2):
                                for suit1, suit2, suit3 in itertools.product(suits, repeat=3):
                                    hand = [pair_rank + suit for suit in suit_combinations]
                                    hand += [kicker_rank1 + suit1, kicker_rank2 + suit2, kicker_rank3 + suit3]
                                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))
                                    hand_tuple = tuple(hand)
                                    if hand_tuple not in existing_hands:
                                        all_hands.append((hand, 11, ordered_rank))
                                        existing_hands.add(hand_tuple)
                                        added_hand = True
                            if added_hand:
                                ordered_rank += 1
            return ordered_rank

        ordered_rank = 1
        ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank)

        # Generate High Card (Rank 12, updated from 10)
        def generate_high_card(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank_comb in itertools.combinations(ranks, 5):
                added_hand = False
                for suit_comb in itertools.product(suits, repeat=5):
                    hand = [r + s for r, s in zip(rank_comb, suit_comb)]
                    hand_tuple = tuple(hand)
                    if hand_tuple not in existing_hands:
                        hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))
                        all_hands.append((hand, 12, ordered_rank))
                        existing_hands.add(hand_tuple)
                        added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank

        ordered_rank = 1
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
with open('all_card_hands_ranked_soko_high.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

print('File generated successfully.')
