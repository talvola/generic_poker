import itertools
from re import A

ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
suits = ['s', 'h', 'd', 'c']

def sort_key_a2(card):
    ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    suits = ['s', 'h', 'd', 'c']

    rank, suit = card[:-1], card[-1]
    return ranks.index(rank), suits.index(suit)

def sort_key_ka(card):
    ranks = ['K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'A']
    suits = ['s', 'h', 'd', 'c']

    rank, suit = card[:-1], card[-1]
    return ranks.index(rank), suits.index(suit)

# Function to sort hands by rank and suit
def sort_hand(hand):
    return sorted(hand, key=lambda card: (ranks.index(card[0]), suits.index(card[1])))

# Function to sort the list of hands
def sort_hands_list(hands_list):       
    return sorted(hands_list, key=lambda hand: [ranks.index(card[0]) for card in hand])   

class PokerHandEvaluator:
   
    def generate_high_card_combos(self, num_cards):
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
    
        # Generate the deck
        deck = [f"{rank}{suit}" for rank in ranks for suit in suits]

        # Generate all 2-card combinations
        card_combos = list(itertools.combinations(deck, num_cards))

        # Convert each tuple to a list (optional)
        card_combos = [list(hand) for hand in card_combos]

        return card_combos   
 
    def create_tuples(self, all_hands, hands, rank):
        # Create tuples with ordered rank

        ordered_rank = 0
        previous_hand = None

        for hand in hands:
            hand_ranks = [card[:-1] for card in hand]  # Extract all but the last character of each card

            if hand_ranks != previous_hand:
                ordered_rank += 1
                previous_hand = hand_ranks 

            all_hands.append((hand, rank, ordered_rank))
        
        return all_hands
    
    # get the sum of the pips based on rules (aces and face card handling)
    def get_sum_pips(self, hand, aces, face_cards):
        sum_pips = 0
        for card in hand:
            rank = card[:-1]
            if rank == 'A':
                sum_pips += aces
            elif rank in ['K', 'Q', 'J']:
                sum_pips += face_cards
            elif rank == 'T':
                sum_pips += 10                
            else:
                sum_pips += int(rank)
        return sum_pips

    def generate_hands(self, ranks, suits, face_cards_value, ascending_rank=True, hand_size=5, pad=None):
        all_hands = []

        # Get all {hand_size}-card hands:

        five_card_combos = hand_evaluator.generate_high_card_combos(hand_size)

        # Initialize a list to store tuples of (sum_pips, hand)
        hands_by_sum_pips = []

        for hand in five_card_combos:
            sum_pips = self.get_sum_pips(hand, aces=1, face_cards=face_cards_value)
            hands_by_sum_pips.append((sum_pips, hand))

        # Sort hands_by_sum_pips by sum_pips in the specified order
        if ascending_rank:
            hands_by_sum_pips.sort(key=lambda x: x[0])
        else:
            hands_by_sum_pips.sort(reverse=True, key=lambda x: x[0])

        # if we are padding, then rank = pip count, otherwise we adjust to 1-based rank
        if pad is not None:
            first_count = 0
        else:
            if 1 <= hand_size <= 4:
                first_count = hand_size - 1
            elif hand_size == 5:
                first_count = 5
            elif hand_size == 6:
                first_count = 7

        # Create tuples of (hand, rank, ordered_rank)
        seen_hands = set()
        unique_hands = []

        max_rank = 49 if hand_size == 5 else 58

        for index, (sum_pips, hand) in enumerate(hands_by_sum_pips):
            if ascending_rank:
                if face_cards_value == 0:
                    rank = sum_pips + 1
                else:
                    rank = sum_pips - first_count  # Adjust rank to start from 1 for sum_pips = 6 for 5-card hand (AAAA2), 4 for 4-card hand (AAAA), etc.
            else:
                rank = max_rank - sum_pips + 1
            ordered_rank = 1

            canonical_hand = sorted([card[0] for card in hand], key=lambda rank: ranks.index(rank))  # Remove suits and sort

            if pad:
                canonical_hand = canonical_hand + ['X'] * pad

            hand_tuple = (tuple(canonical_hand), rank, ordered_rank)
            if hand_tuple not in seen_hands:
                seen_hands.add(hand_tuple)
                unique_hands.append(hand_tuple)

        return unique_hands
    
    def rank_hands(self, evaluated_hands):
        # Sort hands by total (descending) and number of cards (descending)
        evaluated_hands.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        ranked_hands = []
        current_rank = 0
        last_total = None
        last_cards = None
        
        for hand, total, cards in evaluated_hands:
            if total != last_total or cards != last_cards:
                last_total = total
                last_cards = cards
                current_rank += 1
                
            ranked_hands.append((hand, current_rank, 1))
        
        return ranked_hands
    
    # get the sum of the pips based on rules (aces and face card handling)
    def get_sum_pips_21(self, hand, aces, face_cards):
        sum_pips = 0
        for rank in hand:
            if rank == 'A':
                sum_pips += aces
            elif rank in ['K', 'Q', 'J']:
                sum_pips += face_cards
            elif rank == 'T':
                sum_pips += 10                
            else:
                sum_pips += int(rank)
        return sum_pips

    def find_best_subset(self, hand, aces, face_cards):
        best_sum = 0
        best_subset_size = 0
        card_values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': face_cards, 'Q': face_cards, 'K': face_cards, 'A': aces}

        for i in range(1, len(hand) + 1):
            for subset in itertools.combinations(hand, i):
                subset_sum = sum(card_values[card] for card in subset)
                subset_sum_size = len(subset)
                if subset_sum <= 21 and subset_sum > best_sum and subset_sum_size > best_subset_size:
                    best_sum = subset_sum
                    best_subset_size = subset_sum_size

        return best_sum, best_subset_size        
    
    def evaluate_all_combos(self, all_combos):
        hands_by_sum_pips = []

        for hand in all_combos:
            sum_pips = self.get_sum_pips_21(hand, aces=1, face_cards=0)

            if sum_pips <= 21:
                hands_by_sum_pips.append((hand, sum_pips, 5))
            else:
                best_sum, best_subset_size = self.find_best_subset(hand, aces=1, face_cards=0)
                hands_by_sum_pips.append((hand, best_sum, best_subset_size))

        return hands_by_sum_pips
        
    def generate_hands_21(self, ranks, hand_size=5):
        all_hands = []

        # Get all 5-card hands:

        card_combos = hand_evaluator.generate_high_card_combos(hand_size)
        
        previous_combo = None 

        all_combos = []
        seen_combos = set()

        for hand in card_combos:
            canonical_combo = sorted([card[0] for card in hand], key=lambda rank: ranks.index(rank))  # Remove suits and sort

            # Convert to tuple to make it hashable and check if already seen
            canonical_tuple = tuple(canonical_combo)

            if canonical_tuple not in seen_combos:
                seen_combos.add(canonical_tuple)
                all_combos.append(canonical_combo)

        evaluated_hands = hand_evaluator.evaluate_all_combos(all_combos)

        ranked_hands = self.rank_hands(evaluated_hands)

        # Create a lookup table for descriptions
        description_lookup = {}
        
        for ranked, evaluated in zip(ranked_hands, evaluated_hands):
            rank, ordered_rank = ranked[1], ranked[2]
            total, card_count = evaluated[1], evaluated[2]
            description = f"{card_count}-card {total}"
            if (rank, ordered_rank) not in description_lookup:
                description_lookup[(rank, ordered_rank)] = description

        return ranked_hands, evaluated_hands, description_lookup

# Create an instance of PokerHandEvaluator
hand_evaluator = PokerHandEvaluator()

# Dramaha variants
#
# 21 - closest to 21 without going over
# best hand is 5-card 21, then 4-card 21, 3-card 21, etc. then 5-card 20, 4-card 20, 3-card 20, etc.

all_hands, debug_hands, description_lookup = hand_evaluator.generate_hands_21(ranks)

# Open a file for writing
with open('all_card_hands_ranked_21.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')  

with open('all_card_hands_description_21.csv', 'w') as file:
    file.write('Rank,OrderedRank,HandDescription\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for key, description in description_lookup.items():
        file.write(str(key[0]) + ',' + str(key[1]) + ',' + description + '\n')  

""" """ # 6 cards

all_hands, debug_hands, description_lookup = hand_evaluator.generate_hands_21(ranks, hand_size=6)

# Open a file for writing
with open('all_card_hands_ranked_21_6.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')          

# # Open a file for writing
# with open('all_card_hands_ranked_21_debug.csv', 'w') as file:
#     file.write('Hand,Total,Cards\n')

#     # Iterate over all hands and write them to the file
#     ordered_ranks = {}
#     for hand, rank, ordered_rank in debug_hands:
#         file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')          

with open('all_card_hands_description_21_6.csv', 'w') as file:
    file.write('Rank,OrderedRank,HandDescription\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for key, description in description_lookup.items():
        file.write(str(key[0]) + ',' + str(key[1]) + ',' + description + '\n')  

# 49 - Draw hand with the most points (Aces = 1, face cards = 0, all others = their respective ranks)
#  best hand - TTTT9 (49 points)

all_hands = hand_evaluator.generate_hands(ranks, suits, face_cards_value=0, ascending_rank=False)

# Open a file for writing
with open('all_card_hands_ranked_49.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

# 58 - same thing with 6-cards

all_hands = hand_evaluator.generate_hands(ranks, suits, face_cards_value=0, ascending_rank=False, hand_size=6)

# Open a file for writing
with open('all_card_hands_ranked_58.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')


# 6 - Draw hand with the least points (Aces = 1, face cards = 10, all others = their respective ranks)
#  best hand - AAAA2 (6 points)

all_hands = hand_evaluator.generate_hands(ranks, suits, face_cards_value=10, ascending_rank=True)

# Open a file for writing
with open('all_card_hands_ranked_6.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')        

# variations with hands from 6 to 1 fewer cards (4 cards, etc.) - join them all in one file with padding (do this for others as well?)

all_hands_6 = hand_evaluator.generate_hands(ranks, suits, face_cards_value=10, ascending_rank=True, hand_size = 6, pad = 0)
all_hands_5 = hand_evaluator.generate_hands(ranks, suits, face_cards_value=10, ascending_rank=True, hand_size = 5, pad = 1)
all_hands_4 = hand_evaluator.generate_hands(ranks, suits, face_cards_value=10, ascending_rank=True, hand_size = 4, pad = 2)
all_hands_3 = hand_evaluator.generate_hands(ranks, suits, face_cards_value=10, ascending_rank=True, hand_size = 3, pad = 3)
all_hands_2 = hand_evaluator.generate_hands(ranks, suits, face_cards_value=10, ascending_rank=True, hand_size = 2, pad = 4)
all_hands_1 = hand_evaluator.generate_hands(ranks, suits, face_cards_value=10, ascending_rank=True, hand_size = 1, pad = 5)

# merge all of the above together 
all_hands = all_hands_6 + all_hands_5 + all_hands_4 + all_hands_3 + all_hands_2 + all_hands_1

# sort by rank, ordered_rank - ascending
all_hands = sorted(all_hands, key=lambda x: (x[1], x[2]))

# Open a file for writing
with open('all_card_hands_ranked_low_pip_6_cards.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # add in zero rank hand for all pads?
    file.write('X,X,X,X,X,X,0,1\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')   


# 0 - Draw hand with the least points (Aces = 1, face cards = 0, all others = their respective ranks)
#  best hand - AAAA2 (6 points)

all_hands = hand_evaluator.generate_hands(ranks, suits, face_cards_value=0, ascending_rank=True)

# Open a file for writing
with open('all_card_hands_ranked_zero.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')        

# 6 card version of the above

all_hands = hand_evaluator.generate_hands(ranks, suits, face_cards_value=0, ascending_rank=True, hand_size = 6)

# Open a file for writing
with open('all_card_hands_ranked_zero_6.csv', 'w') as file:
    file.write('Hand,Rank,OrderedRank\n')

    # Iterate over all hands and write them to the file
    ordered_ranks = {}
    for hand, rank, ordered_rank in all_hands:
        file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')        

print('Files generated successfully.')



