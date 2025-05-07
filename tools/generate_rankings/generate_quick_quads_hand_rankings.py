import itertools
from re import A

class PokerHandEvaluator:
    def __init__(self):
        self.hand_rankings = {}

    def load_hand_rankings(self, file_path):
        with open(file_path, 'r') as file:
            for line in file:
                rank, hand_name = line.strip().split(',')
                self.hand_rankings[hand_name] = int(rank)

    def generate_quick_quads(self, rank, ordered_rank, all_hands, four_of_a_kinds):
        quad_ranks = ['A', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        # Helper function to get the card value considering Aces can be 1
        def get_card_value(rank):
            if rank == 'A':
                return 1  # Ace can be 1 for Quick Quads
            return self._rank_to_value(rank) + 1        

        # Track kicker combinations to avoid duplicating ordered_rank
        kicker_combinations = set()
        current_kicker_combo = None
        ordered_rank += 1
        added_hand = False

        rank_value = self._rank_to_value(rank) + 1
           
        # Find pairs of cards that sum to the rank value
        for kicker_rank1 in quad_ranks:
            # Get the proper value (Ace can be 1)
            kicker_value1 = get_card_value(kicker_rank1)
            
            # Skip if kicker value is too large
            if kicker_value1 >= rank_value:
                continue
            
            # Find the complementary card value needed
            needed_value = rank_value - kicker_value1
            
            # Find ranks with this value
            for complementary_rank in quad_ranks:
                comp_value = get_card_value(complementary_rank)

                if comp_value == needed_value:
                    # Create a key to track this kicker combination (order doesn't matter)
                    combo_key = tuple(sorted([kicker_rank1, complementary_rank]))
                    added_hand = False
                    
                    # Only update ordered_rank when the kicker combination changes
                    if combo_key != current_kicker_combo:
                        current_kicker_combo = combo_key
                        kicker_combinations.add(combo_key)

                    # Generate all possible suit combinations for the two kickers
                    for suit_kicker1 in suits:
                        kicker1 = kicker_rank1 + suit_kicker1
                        
                        # Skip if kicker is already in the three of a kind
                        #if kicker1 in three_of_a_kind:
                        #    continue
                            
                        for suit_kicker2 in suits:
                            kicker2 = complementary_rank + suit_kicker2
                            
                            # Skip if kickers are the same card
                            if kicker1 == kicker2:
                                continue
                            
                            # Skip if second kicker is in the three of a kind
                            #if kicker2 in three_of_a_kind:
                            #    continue

                            # Generate all three of a kind combinations for this rank
                            for suit_combo in itertools.combinations(suits, 3):
                                three_of_a_kind = [rank + suit for suit in suit_combo]

                                # Create and sort the full hand
                                quad_hand = three_of_a_kind + [kicker1, kicker2]
                                quad_hand.sort(key=lambda x: (quad_ranks.index(x[0]), suits.index(x[1])))

                                # Check if this hand is already in four_of_a_kinds
                                if any(quad_hand == existing_hand for existing_hand in four_of_a_kinds):
                                    continue                                
                                                                
                                # Debug the values to ensure they sum correctly
                                print(f"Card values: {kicker_rank1}={kicker_value1}, {complementary_rank}={comp_value}, Sum={kicker_value1+comp_value}, Target={rank_value}")
                                
                                # Add to the lists
                                all_hands.append((quad_hand, 3, ordered_rank))
                                four_of_a_kinds.append(quad_hand)
                                added_hand = True

                                print(f"Quick Quad: {','.join(quad_hand)},3,{ordered_rank}")

                    if added_hand:
                        ordered_rank += 1                                
        
        return ordered_rank

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
        ordered_rank = 0  # back to 1 to start four of a kinds
        four_of_a_kinds = []

        # Only process ranks 2 through 10
        valid_quick_quads_ranks = []
        for r in ranks:
            rank_value = self._rank_to_value(r)
            if 1 <= rank_value <= 9:
                valid_quick_quads_ranks.append(r)

        print("Generating natural four of a kinds...")

        # Track the last kicker rank for rank changes
        last_kicker_rank = None

        for rank in ranks:
            for suit1, suit2, suit3, suit4 in itertools.combinations(suits, 4):
                hand = [rank + s for s in (suit1, suit2, suit3, suit4)]
                
                # Sort kicker ranks in descending order (A to 2)
                for kicker_rank in ranks:
                    if kicker_rank != rank:
                        # Update ordered_rank only when kicker rank changes
                        if kicker_rank != last_kicker_rank:
                            ordered_rank += 1
                            last_kicker_rank = kicker_rank
                        
                        for suit_kicker in suits:
                            four_hand = hand + [kicker_rank + suit_kicker]                            
                            four_hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                            all_hands.append((four_hand, 3, ordered_rank))
                            four_of_a_kinds.append(four_hand)
                            print(f"Natural four: {','.join(four_hand)},3,{ordered_rank}")

            # Generate Quick Quads
            if rank in valid_quick_quads_ranks:
                print(f"Processing Quick Quads for rank {rank} (value {rank_value})")
                ordered_rank = self.generate_quick_quads(rank, ordered_rank, all_hands, four_of_a_kinds) - 1 # avoid double increment
   
        # Generate full houses

        ordered_rank = 1  # back to 1 

        for rank1, rank2 in itertools.permutations(ranks, 2):
            for suit1, suit2, suit3 in itertools.combinations(suits, 3):
                three_of_a_kind = [rank1 + s for s in (suit1, suit2, suit3)]
                for suit4, suit5 in itertools.combinations(suits, 2):
                    pair = [rank2 + s for s in (suit4, suit5)]
                    hand = three_of_a_kind + pair
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    if any(hand == four_of_a_kind for four_of_a_kind in four_of_a_kinds):
                        continue                         
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
                            if any(hand == four_of_a_kind for four_of_a_kind in four_of_a_kinds):
                                continue                            
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
with open('all_card_hands_ranked_quick_quads.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

print('File generated successfully.')
