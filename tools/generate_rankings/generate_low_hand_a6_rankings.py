# for A-6 rankings - just do the same as high hand rankings, but reverse everything
# aces are only low

import itertools
from re import A
from collections import defaultdict

class PokerHandEvaluator:
    def __init__(self):
        self.ranks = ['K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'A']
        self.suits = ['s', 'h', 'd', 'c'] 
        self.hand_rankings = {}
        self.existing_hands = set()        
        self.card_to_int = {r + s: i * 4 + j for i, r in enumerate(self.ranks)
                           for j, s in enumerate(self.suits)}        
       

    def encode_hand(self, hand):
        """Encode a hand as a unique integer using bit operations."""
        # Sort cards for consistent encoding
        sorted_cards = sorted([self.card_to_int[card] for card in hand])
        # Use bit operations instead of exponentiation for efficiency
        result = 0
        for card in sorted_cards:
            result = (result << 6) | card  # Each card needs 6 bits (2^6 = 64 > 52)
        return result
    
    def reverse_all_ranks_and_ordered_ranks(self, all_hands):
        # Separate the hands by their ranks
        rank_groups = defaultdict(list)
        for hand in all_hands:
            rank = hand[1]
            rank_groups[rank].append(hand)
        
        # Maximum rank value
        max_rank = max(rank_groups.keys())

        # Create a new list to hold the adjusted hands
        adjusted_hands = []

        # Process each rank group
        for rank in sorted(rank_groups.keys()):
            hands = rank_groups[rank]
            
            # Reverse the rank value
            new_rank = max_rank + 1 - rank
            
            # Sort hands by their ordered rank
            hands.sort(key=lambda x: x[2])
            
            # Create a map of old ordered ranks to new ordered ranks
            ordered_rank_map = {}
            unique_ordered_ranks = sorted(set(hand[2] for hand in hands), reverse=True)
            for i, old_ordered_rank in enumerate(unique_ordered_ranks, start=1):
                ordered_rank_map[old_ordered_rank] = i
            
            # Adjust the hands with new ranks and ordered ranks
            for hand in hands:
                new_ordered_rank = ordered_rank_map[hand[2]]
                adjusted_hands.append((hand[0], new_rank, new_ordered_rank))
        
        # Sort the adjusted hands to maintain the overall order
        adjusted_hands.sort(key=lambda x: (x[1], x[2]))
        
        return adjusted_hands


    def generate_hands(self):


        all_hands = []
        straight_flushes = []
        lookup_hands = []

        # no need for royal flushes - Ace can't be high

        # Generate straight flushes - don't use Ace as high
        sf_ranks = ['K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'A']
        
        # restart ordered_rank each rank for now
        ordered_rank = 1
        for i in range(len(sf_ranks) - 4):
            for suit in self.suits:
                hand = [sf_ranks[j] + suit for j in range(i, i+5)]
                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                all_hands.append((hand, 2, ordered_rank))
                straight_flushes.append(hand)
                encoded = self.encode_hand(hand)
                self.existing_hands.add(encoded)
            ordered_rank += 1
        
        # Generate four of a kinds
        ordered_rank = 1  # back to 1 to start four of a kinds

        for rank in sf_ranks:
            added_hand = False
            for suit1, suit2, suit3, suit4 in itertools.combinations(self.suits, 4):
                hand = [rank + s for s in (suit1, suit2, suit3, suit4)]
                for kicker_rank in sf_ranks:
                    if kicker_rank != rank:
                        for suit_kicker in self.suits:
                            four_hand = hand + [kicker_rank + suit_kicker]                            
                            four_hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                            encoded = self.encode_hand(four_hand)
                            if encoded not in self.existing_hands:                            
                                self.existing_hands.add(encoded)                            
                                all_hands.append((four_hand, 3, ordered_rank))
                                added_hand = True
                    else:
                        added_hand = False
                    if added_hand:
                        ordered_rank += 1  

        # Generate full houses

        ordered_rank = 1  # back to 1 

        for rank1, rank2 in itertools.permutations(sf_ranks, 2):
            for suit1, suit2, suit3 in itertools.combinations(self.suits, 3):
                three_of_a_kind = [rank1 + s for s in (suit1, suit2, suit3)]
                for suit4, suit5 in itertools.combinations(self.suits, 2):
                    pair = [rank2 + s for s in (suit4, suit5)]
                    hand = three_of_a_kind + pair
                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                    encoded = self.encode_hand(hand)
                    if encoded not in self.existing_hands:                            
                        self.existing_hands.add(encoded)                     
                        all_hands.append((hand, 4, ordered_rank))
            ordered_rank += 1

        # Generate flushes
        ordered_rank = 1  # back to 1

        for combination in itertools.combinations(sf_ranks, 5):
            added_hand = False
            for suit in self.suits:
                # Check if it's a straight or royal flush, skip if true
                straight_flush_hand = [rank + suit for rank in combination]
                if any(hand == straight_flush_hand for hand in straight_flushes):
                    continue
                # Generate the flush hand
                hand = [rank + suit for rank in combination]
                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                encoded = self.encode_hand(hand)
                if encoded not in self.existing_hands:                            
                    self.existing_hands.add(encoded)                  
                    all_hands.append((hand, 5, ordered_rank))
                    lookup_hands.append(hand)
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
                    straight_hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                    encoded = self.encode_hand(straight_hand)
                    if encoded not in self.existing_hands:                            
                        self.existing_hands.add(encoded)                       
                        all_hands.append((straight_hand, 6, ordered_rank))
                        lookup_hands.append(hand)
                        added_hand = True
                if added_hand:
                    ordered_rank += 1                    
            return ordered_rank

        # Generate straights
        ordered_rank = 1  # back to 1
        ordered_rank = generate_straights(sf_ranks, self.suits, all_hands, ordered_rank)

        # Generate three of a kind
        ordered_rank = 1  # back to 1

        for rank in sf_ranks:
            for kicker_rank1 in sf_ranks:
                if kicker_rank1 == rank:
                    continue
                for kicker_rank2 in sf_ranks:
                    if kicker_rank2 == rank or self._rank_to_value(kicker_rank2) >= self._rank_to_value(kicker_rank1):
                        continue
                    added_hand = False
                    for suit_combinations in itertools.combinations(self.suits, 3):
                        for suit4, suit5 in itertools.product(self.suits, repeat=2):
                            hand = [rank + suit for suit in suit_combinations]
                            hand += [kicker_rank1 + suit4, kicker_rank2 + suit5]
                            hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                            encoded = self.encode_hand(hand)
                            if encoded not in self.existing_hands:                            
                                self.existing_hands.add(encoded)                                 
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
                                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                                encoded = self.encode_hand(hand)
                                if encoded not in self.existing_hands:                            
                                    self.existing_hands.add(encoded)                                          
                                    all_hands.append((hand, 8, ordered_rank))
                                    added_hand = True
                    if added_hand:
                        ordered_rank += 1
            return ordered_rank
    
        ordered_rank = 1  # back to 1

        ordered_rank = generate_two_pairs(sf_ranks, self.suits, all_hands, ordered_rank)

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
                                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                                    encoded = self.encode_hand(hand)
                                    if encoded not in self.existing_hands:                            
                                        self.existing_hands.add(encoded)                                      
                                        all_hands.append((hand, 9, ordered_rank))
                                        added_hand = True
                            if added_hand:
                                ordered_rank += 1
            return ordered_rank

        ordered_rank = 1  # back to 1

        ordered_rank = generate_one_pair(sf_ranks, self.suits, all_hands, ordered_rank)

        # Generate High Card hands

        def generate_high_card(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank1, rank2, rank3, rank4, rank5 in itertools.combinations(ranks, 5):
                added_hand = False           
                for suit_combinations in itertools.product(suits, repeat=5):
                    hand = [rank + suit for rank, suit in zip([rank1, rank2, rank3, rank4, rank5], suit_combinations)]
                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))  # Sort hand in desired order
                    encoded = self.encode_hand(hand)
                    if encoded not in self.existing_hands:                            
                        self.existing_hands.add(encoded)              
                        all_hands.append((hand, 10, ordered_rank))
                        added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank

        ordered_rank = 1  # back to 1
        ordered_rank = generate_high_card(sf_ranks, self.suits, all_hands, ordered_rank)

        #return all_hands
        # Example usage
        reversed_and_adjusted_hands = self.reverse_all_ranks_and_ordered_ranks(all_hands)
        #for hand in reversed_and_adjusted_hands[:10]:  # Displaying the first 10 hands as an example
        #    print(hand)

        return reversed_and_adjusted_hands

    def _rank_to_value(self, rank):
        rank_values = {'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13}
        return rank_values[rank]

# Create an instance of PokerHandEvaluator
hand_evaluator = PokerHandEvaluator()

# Generate all possible hands
all_hands = hand_evaluator.generate_hands()

# Open a file for writing
with open('all_card_hands_ranked_a6_low.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

print('File generated successfully.')
