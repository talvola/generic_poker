import itertools
from re import A

def sort_key_a2(card):
    ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
    suits = ['s', 'h', 'd', 'c']

    rank, suit = card[:-1], card[-1]
    return ranks.index(rank), suits.index(suit)

def sort_key_ka(card):
    ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
    suits = ['s', 'h', 'd', 'c']

    rank, suit = card[:-1], card[-1]
    return ranks.index(rank), suits.index(suit)

class PokerHandEvaluator:
   
    def generate_high_card_combos(self, num_cards):
        ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
    
        # Generate the deck
        deck = [f"{rank}{suit}" for rank in ranks for suit in suits]

        # Generate all 2-card combinations
        card_combos = list(itertools.combinations(deck, num_cards))

        # Sort each hand and then the list of hands
        sorted_combos = [sorted(hand, key=sort_key_a2) for hand in card_combos]
        sorted_combos.sort(key=lambda hand: [sort_key_a2(card) for card in hand])

        # Convert each tuple to a list (optional)
        sorted_combos = [list(hand) for hand in sorted_combos]

        return sorted_combos 
    
    def generate_low_card_combos(self, num_cards):
        ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        suits = ['s', 'h', 'd', 'c']
    
        # Generate the deck
        deck = [f"{rank}{suit}" for rank in ranks for suit in suits]

        # Generate all 2-card combinations
        card_combos = list(itertools.combinations(deck, num_cards))

        # Sort each hand and then the list of hands
        sorted_combos = [sorted(hand, key=sort_key_ka) for hand in card_combos]
        sorted_combos.sort(key=lambda hand: [sort_key_ka(card) for card in hand])

        # Convert each tuple to a list (optional)
        sorted_combos = [list(hand) for hand in sorted_combos]

        return sorted_combos             
        
    def generate_low_one_card_hands(self):
        ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        all_hands = []
        ordered_rank = 1

        for rank in reversed(ranks):
            for suit in reversed(suits):
                hand = [rank + suit]
                all_hands.append((hand, 1, ordered_rank))
                ordered_rank += 1

        return all_hands

    def generate_low_al_one_card_hands(self):
        ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        suits = ['s', 'h', 'd', 'c']

        all_hands = []
        ordered_rank = 1

        for rank in reversed(ranks):
            for suit in reversed(suits):
                hand = [rank + suit]
                all_hands.append((hand, 1, ordered_rank))
                ordered_rank += 1

        return all_hands    
    
    def generate_high_ah_one_card_hands(self):
        ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        all_hands = []
        ordered_rank = 1

        for rank in ranks:
            for suit in suits:
                hand = [rank + suit]
                all_hands.append((hand, 1, ordered_rank))
                ordered_rank += 1

        return all_hands

    def generate_high_one_card_hands(self):
        ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        suits = ['s', 'h', 'd', 'c']

        all_hands = []
        ordered_rank = 1

        for rank in ranks:
            for suit in suits:
                hand = [rank + suit]
                all_hands.append((hand, 1, ordered_rank))
                ordered_rank += 1

        return all_hands    
    
    def generate_high_two_card_hands(self, ace_low = False, razz_high = False):
        if ace_low:
            ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        else:
            ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        def generate_one_pair(ranks, suits, all_hands, ordered_rank, hand_rank):
            added_hand = False
            for pair_rank in ranks:
                for suit_combinations in itertools.combinations(suits, 2):
                    hand = [pair_rank + suit for suit in suit_combinations]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, hand_rank, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank

        def generate_high_card(ranks, suits, all_hands, ordered_rank, hand_rank):
            added_hand = False
            for rank_combinations in itertools.combinations(ranks, 2):
                for suit_combinations in itertools.product(suits, repeat=2):
                    hand = [rank + suit for rank, suit in zip(rank_combinations, suit_combinations)]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, hand_rank, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank


        all_hands = []

        # this is a little odd - but razz high puts high hand first even though rest of logic is closer to high

        if razz_high:
            ordered_rank = 1  
            ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank, 1)     
        
            ordered_rank = 1  
            ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank, 2)     
        else:
            ordered_rank = 1  
            ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank, 1)

            ordered_rank = 1  
            ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank, 2)

        return all_hands      
    
    def generate_low_two_card_hands(self, ace_high = False):
        if ace_high:
            ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        else:
            ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        suits = ['s', 'h', 'd', 'c']

        def generate_high_card(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank_combinations in reversed(list(enumerate(itertools.combinations(ranks, 2)))):
                for suit_combinations in itertools.product(suits, repeat=2):
                    hand = [rank + suit for rank, suit in zip(rank_combinations[1], suit_combinations)]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 1, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank        

        all_hands = []
        ordered_rank = 1  

        ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank)

        def generate_one_pair(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for pair_rank in reversed(ranks):
                for suit_combinations in itertools.combinations(suits, 2):
                    hand = [pair_rank + suit for suit in suit_combinations]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 2, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank

        ordered_rank = 1  

        ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank)

        return all_hands         
    
    def generate_low_three_card_hands(self, ace_high = False):
        if ace_high:
            ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        else:
            ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        suits = ['s', 'h', 'd', 'c']

        def generate_high_card(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank_combinations in reversed(list(enumerate(itertools.combinations(ranks, 3)))):
                for suit_combinations in itertools.product(suits, repeat=3):
                    hand = [rank + suit for rank, suit in zip(rank_combinations[1], suit_combinations)]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 1, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank     

        all_hands = []
        ordered_rank = 1  

        ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank)        

        def generate_one_pair(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for pair_rank in reversed(ranks):
                for suit_combinations in itertools.combinations(suits, 2):
                    for kicker_rank in (rank for rank in reversed(ranks) if rank != pair_rank):
                        for suit_kicker in suits:                    
                            hand = [pair_rank + suit for suit in suit_combinations]
                            hand.append(kicker_rank + suit_kicker)
                            hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                            all_hands.append((hand, 2, ordered_rank))
                            added_hand = True
                        if added_hand:
                            ordered_rank += 1
            return ordered_rank

        ordered_rank = 1  

        ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank)
   
        def generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank):
            for rank in reversed(ranks):
                for suit_combinations in itertools.combinations(suits, 3):
                    hand = [rank + suit for suit in suit_combinations]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 3, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1

        ordered_rank = 1  

        ordered_rank = generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank)

        return all_hands       
    
    def generate_low_four_card_hands(self, ace_high = False):
        if ace_high:
            ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        else:
            ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        suits = ['s', 'h', 'd', 'c']

        def generate_high_card(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank_combinations in reversed(list(enumerate(itertools.combinations(ranks, 4)))):
                for suit_combinations in itertools.product(suits, repeat=4):
                    hand = [rank + suit for rank, suit in zip(rank_combinations[1], suit_combinations)]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 1, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank     

        all_hands = []
        ordered_rank = 1  

        ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank)        

        def generate_one_pair(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for pair_rank in reversed(ranks):
                for suit_combinations in itertools.combinations(suits, 2):
                    for kicker_rank in (rank for rank in reversed(ranks) if rank != pair_rank):
                        for kicker2_rank in (rank for rank in reversed(ranks) if rank not in [pair_rank, kicker_rank]):
                            for suit_kicker in suits:  
                                for suit_kicker2 in suits:                    
                                    hand = [pair_rank + suit for suit in suit_combinations]
                                    hand += [kicker_rank + suit_kicker, kicker2_rank + suit_kicker2]
                                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                                    all_hands.append((hand, 2, ordered_rank))
                                    added_hand = True
                        if added_hand:
                            ordered_rank += 1
            return ordered_rank
      
        ordered_rank = 1  

        ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank)

        def generate_two_pairs(ranks, suits, all_hands, ordered_rank):
            added_hand = False
            for rank1, rank2 in itertools.combinations(reversed(ranks), 2):
                for suit1, suit2 in itertools.combinations(suits, 2):
                    for suit3, suit4 in itertools.combinations(suits, 2):
                        hand = [rank1 + suit1, rank1 + suit2, rank2 + suit3, rank2 + suit4]
                        hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                        all_hands.append((hand, 3, ordered_rank))
                        added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank
        
        ordered_rank = 1  

        ordered_rank = generate_two_pairs(ranks, suits, all_hands, ordered_rank)

        def generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank):
            for three_rank in reversed(ranks):
                for suit_combinations in itertools.combinations(suits, 3):
                    for kicker_rank in (rank for rank in reversed(ranks) if rank != three_rank):
                        for suit_kicker in suits:                    
                            hand = [three_rank + suit for suit in suit_combinations]
                            hand.append(kicker_rank + suit_kicker)
                            hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                            all_hands.append((hand, 4, ordered_rank))
                            added_hand = True
                    if added_hand:
                        ordered_rank += 1

        ordered_rank = 1  

        ordered_rank = generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank)

        def generate_four_of_a_kind(ranks, suits, all_hands, ordered_rank):
            for rank in reversed(ranks):
                for suit_combinations in itertools.combinations(suits, 4):
                    hand = [rank + suit for suit in suit_combinations]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, 5, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1

        ordered_rank = 1  

        ordered_rank = generate_four_of_a_kind(ranks, suits, all_hands, ordered_rank)        

        return all_hands      
        
           
    def generate_high_three_card_hands(self, ace_low = False, razz_high = False):
        if ace_low:
            ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        else:
            ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
   
        def generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank, hand_rank):
            for rank in ranks:
                for suit_combinations in itertools.combinations(suits, 3):
                    hand = [rank + suit for suit in suit_combinations]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, hand_rank, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1



        def generate_one_pair(ranks, suits, all_hands, ordered_rank, hand_rank):
            added_hand = False
            for pair_rank in ranks:
                for suit_combinations in itertools.combinations(suits, 2):
                    for kicker_rank in (rank for rank in ranks if rank != pair_rank):
                        for suit_kicker in suits:                    
                            hand = [pair_rank + suit for suit in suit_combinations]
                            hand.append(kicker_rank + suit_kicker)
                            hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                            all_hands.append((hand, hand_rank, ordered_rank))
                            added_hand = True
                        if added_hand:
                            ordered_rank += 1
            return ordered_rank

        def generate_high_card(ranks, suits, all_hands, ordered_rank, hand_rank):
            added_hand = False
            for rank1, rank2, rank3 in itertools.combinations(ranks, 3):
                added_hand = False           
                for suit_combinations in itertools.product(suits, repeat=3):
                    hand = [rank + suit for rank, suit in zip([rank1, rank2, rank3], suit_combinations)]
                    hand_key = tuple(hand)
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, hand_rank, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank

        all_hands = []

        if razz_high:
            ordered_rank = 1  
            ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank, 1)    
            ordered_rank = 1  
            ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank, 2)                     
            ordered_rank = 1  
            ordered_rank = generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank, 3)        
        else:
            ordered_rank = 1  
            ordered_rank = generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank, 1)
            ordered_rank = 1  
            ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank, 2)
            ordered_rank = 1  
            ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank, 3)

        return all_hands   
            
    def generate_high_four_card_hands(self, ace_low = False, razz_high = False):
        if ace_low:
            ranks = ['K', 'Q', 'J', '7', '6', '5', '4', '3', '2', 'A']
        else:
            ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        def generate_four_of_a_kind(ranks, suits, all_hands, ordered_rank, hand_rank):
            for rank in ranks:
                for suit_combinations in itertools.combinations(suits, 4):
                    hand = [rank + suit for suit in suit_combinations]
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, hand_rank, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1

        def generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank, hand_rank):
            for three_rank in ranks:
                for suit_combinations in itertools.combinations(suits, 3):
                    for kicker_rank in (rank for rank in ranks if rank != three_rank):
                        for suit_kicker in suits:                       
                            hand = [three_rank + suit for suit in suit_combinations]
                            hand.append(kicker_rank + suit_kicker)
                            hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                            all_hands.append((hand, hand_rank, ordered_rank))
                            added_hand = True
                        if added_hand:
                            ordered_rank += 1

        def generate_two_pairs(ranks, suits, all_hands, ordered_rank, hand_rank):
            added_hand = False
            for rank1, rank2 in itertools.combinations(ranks, 2):
                for suit1, suit2 in itertools.combinations(suits, 2):
                    for suit3, suit4 in itertools.combinations(suits, 2):
                        hand = [rank1 + suit1, rank1 + suit2, rank2 + suit3, rank2 + suit4]
                        hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                        all_hands.append((hand, hand_rank, ordered_rank))
                        added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank   

        def generate_one_pair(ranks, suits, all_hands, ordered_rank, hand_rank):
            added_hand = False
            for pair_rank in ranks:
                for suit_combinations in itertools.combinations(suits, 2):
                    for kicker_rank in (rank for rank in ranks if rank != pair_rank):
                        for kicker2_rank in (rank for rank in ranks if rank not in [pair_rank, kicker_rank]):
                            for suit_kicker in suits:                    
                                for suit_kicker2 in suits:                    
                                    hand = [pair_rank + suit for suit in suit_combinations]
                                    hand += [kicker_rank + suit_kicker, kicker2_rank + suit_kicker2]
                                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                                    all_hands.append((hand, hand_rank, ordered_rank))
                                    added_hand = True
                            if added_hand:
                                ordered_rank += 1
            return ordered_rank

        def generate_high_card(ranks, suits, all_hands, ordered_rank, hand_rank):
            added_hand = False
            for rank1, rank2, rank3, rank4 in itertools.combinations(ranks, 4):
                added_hand = False           
                for suit_combinations in itertools.product(suits, repeat=4):
                    hand = [rank + suit for rank, suit in zip([rank1, rank2, rank3, rank4], suit_combinations)]
                    hand_key = tuple(hand)
                    hand.sort(key=lambda x: (ranks.index(x[0]), suits.index(x[1])))  # Sort hand in desired order
                    all_hands.append((hand, hand_rank, ordered_rank))
                    added_hand = True
                if added_hand:
                    ordered_rank += 1
            return ordered_rank


        
        all_hands = []

        if razz_high:
            ordered_rank = 1  
            ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank, 1)     
            ordered_rank = 1  
            ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank, 2)       
            ordered_rank = 1  
            ordered_rank = generate_two_pairs(ranks, suits, all_hands, ordered_rank, 3)      
            ordered_rank = 1  
            ordered_rank = generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank, 4)         
            ordered_rank = 1  
            ordered_rank = generate_four_of_a_kind(ranks, suits, all_hands, ordered_rank, 5)
        else:
            ordered_rank = 1  
            ordered_rank = generate_four_of_a_kind(ranks, suits, all_hands, ordered_rank, 1)
            ordered_rank = 1  
            ordered_rank = generate_three_of_a_kind(ranks, suits, all_hands, ordered_rank, 2)
            ordered_rank = 1  
            ordered_rank = generate_two_pairs(ranks, suits, all_hands, ordered_rank, 3)   
            ordered_rank = 1  
            ordered_rank = generate_one_pair(ranks, suits, all_hands, ordered_rank, 4)
            ordered_rank = 1  
            ordered_rank = generate_high_card(ranks, suits, all_hands, ordered_rank, 5)

        return all_hands   
            

# Create an instance of PokerHandEvaluator
hand_evaluator = PokerHandEvaluator()



# A-5 Low one card hands

# Generate all possible hands
all_hands = hand_evaluator.generate_low_one_card_hands()

card_combos = hand_evaluator.generate_low_card_combos(1)
print(f"There are {len(card_combos)} combinations of one card.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for one card low hands (Ace high):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_one_card_27_ja_ffh_low.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

# A-5 Low (Ace is low) one card hands

# Generate all possible hands
all_hands = hand_evaluator.generate_low_al_one_card_hands()

card_combos = hand_evaluator.generate_high_card_combos(1)
print(f"There are {len(card_combos)} combinations of one card.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for one card low hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_one_card_27_ja_ffh_low_al.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

# 2-7 Low one card hands

# Generate all possible hands
all_hands = hand_evaluator.generate_high_ah_one_card_hands()

card_combos = hand_evaluator.generate_low_card_combos(1)
print(f"There are {len(card_combos)} combinations of one card.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for one card high hands (Ace high):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_one_card_27_ja_ffh_high_ah.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

# Generate all possible hands
all_hands = hand_evaluator.generate_high_one_card_hands()

card_combos = hand_evaluator.generate_high_card_combos(1)
print(f"There are {len(card_combos)} combinations of one card.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for one card high hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_one_card_27_ja_ffh_high.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')





# Generate all possible hands
all_hands = hand_evaluator.generate_high_two_card_hands()

card_combos = hand_evaluator.generate_high_card_combos(2)
print(f"There are {len(card_combos)} combinations of two cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for two card high hands (Ace high):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_two_card_27_ja_ffh_high.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')          

# Generate all possible hands
all_hands = hand_evaluator.generate_high_two_card_hands(ace_low = True)

card_combos = hand_evaluator.generate_low_card_combos(2)
print(f"There are {len(card_combos)} combinations of two cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for two card high hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_two_card_27_ja_ffh_high_al.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')     

# Generate all possible hands
all_hands = hand_evaluator.generate_high_two_card_hands(ace_low = True, razz_high = True)

card_combos = hand_evaluator.generate_low_card_combos(2)
print(f"There are {len(card_combos)} combinations of two cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for two card high hands (Ace low - Razz High ranks):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_two_card_27_ja_ffh_high_al_rh.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')     

# Generate all possible hands
all_hands = hand_evaluator.generate_low_two_card_hands()

card_combos = hand_evaluator.generate_low_card_combos(2)
print(f"There are {len(card_combos)} combinations of two cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for two card low hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_two_card_27_ja_ffh_low.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')        

# Generate all possible hands
all_hands = hand_evaluator.generate_low_two_card_hands(ace_high = True)

card_combos = hand_evaluator.generate_high_card_combos(2)
print(f"There are {len(card_combos)} combinations of two cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for two card low (Ace high) hands:")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_two_card_27_ja_ffh_low_ah.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')    

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')    




# Generate all possible hands
all_hands = hand_evaluator.generate_high_three_card_hands()

card_combos = hand_evaluator.generate_high_card_combos(3)
print(f"There are {len(card_combos)} combinations of three cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for three card high hands (Ace high):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_three_card_27_ja_ffh_high.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')    


# Generate all possible hands
all_hands = hand_evaluator.generate_high_three_card_hands(ace_low = True)

card_combos = hand_evaluator.generate_low_card_combos(3)
print(f"There are {len(card_combos)} combinations of three cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for three card high hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_three_card_27_ja_ffh_high_al.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')    

# Generate all possible hands
all_hands = hand_evaluator.generate_high_three_card_hands(ace_low = True, razz_high=True)

card_combos = hand_evaluator.generate_low_card_combos(3)
print(f"There are {len(card_combos)} combinations of three cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for three card high hands (Ace low - Razz High ranks):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_three_card_27_ja_ffh_high_al_rh.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')    


# Generate all possible hands
all_hands = hand_evaluator.generate_low_three_card_hands()

card_combos = hand_evaluator.generate_low_card_combos(3)
print(f"There are {len(card_combos)} combinations of three cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for three card low hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_three_card_27_ja_ffh_low.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')   

# Generate all possible hands
all_hands = hand_evaluator.generate_low_three_card_hands(ace_high = True)

card_combos = hand_evaluator.generate_high_card_combos(3)
print(f"There are {len(card_combos)} combinations of three cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for three card low (Ace high) hands:")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_three_card_27_ja_ffh_low_ah.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')
   
    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')           




# Generate all possible hands
all_hands = hand_evaluator.generate_high_four_card_hands()

card_combos = hand_evaluator.generate_high_card_combos(4)
print(f"There are {len(card_combos)} combinations of four cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for four card high hands (Ace high):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_four_card_27_ja_ffh_high.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')        


# Generate all possible hands
all_hands = hand_evaluator.generate_high_four_card_hands(ace_low = True)

card_combos = hand_evaluator.generate_low_card_combos(4)
print(f"There are {len(card_combos)} combinations of four cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for four card high hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_four_card_27_ja_ffh_high_al.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')    

# Generate all possible hands
all_hands = hand_evaluator.generate_high_four_card_hands(ace_low = True, razz_high=True)

card_combos = hand_evaluator.generate_low_card_combos(4)
print(f"There are {len(card_combos)} combinations of four cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for four card high hands (Ace low - Razz High ranks):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_four_card_27_ja_ffh_high_al_rh.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')    



# Generate all possible hands
all_hands = hand_evaluator.generate_low_four_card_hands()

card_combos = hand_evaluator.generate_low_card_combos(4)
print(f"There are {len(card_combos)} combinations of four cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for four card low hands (Ace low):")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_four_card_27_ja_ffh_low.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')    

# Generate all possible hands
all_hands = hand_evaluator.generate_low_four_card_hands(ace_high = True)

card_combos = hand_evaluator.generate_high_card_combos(4)
print(f"There are {len(card_combos)} combinations of four cards.")

# Create a set of the hands from all_hands
all_hands_set = {tuple(hand) for hand, _, _ in all_hands}

# Filter card_combos to find hands not in all_hands
not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]

print("The following hands were not generated in all_hands for four card low (Ace high) hands:")
print(not_in_all_hands)

# Open a file for writing
with open('all_card_hands_ranked_four_card_27_ja_ffh_low_ah.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')              

print('File generated successfully.')


