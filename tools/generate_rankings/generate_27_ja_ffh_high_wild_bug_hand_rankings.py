import csv
from collections import defaultdict
import itertools

def read_hands_from_file(filename):
    hands = []
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip the header
        for row in reader:
            hand = tuple(row[:5])
            rank = int(row[5]) + 1  # Increment rank by 1 to make space for five-of-a-kind
            ordered_rank = int(row[6])
            hands.append((hand, rank, ordered_rank))
    return hands

def normalize_hand(hand):
    wild_cards = sorted(card for card in hand if card.startswith('W'))
    bug_cards = sorted(card for card in hand if card.startswith('B'))
    non_wild_cards = [card for card in hand if not card.startswith('W') and not card.startswith('B')]
    return tuple(wild_cards + bug_cards + non_wild_cards)

from collections import defaultdict
import itertools

def generate_five_of_a_kind_hands():
    unique_hands = defaultdict(lambda: (float('inf'), float('inf')))
    suits = ['s', 'h', 'd', 'c']
    
    # Wild card five-of-a-kind hands
    ranks = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
    for i, rank in enumerate(ranks):
        # All possible cards of this rank
        rank_cards = [f'{rank}{suit}' for suit in suits]
        # 1 to 4 wild cards
        for num_wild in range(1, 5):
            wild_part = [f'W{j+1}' for j in range(num_wild)]
            # Number of regular cards needed
            reg_count = 5 - num_wild
            # All combinations of reg_count cards from rank_cards
            for reg_cards in itertools.combinations(rank_cards, reg_count):
                five_of_a_kind_hand = tuple(wild_part + list(reg_cards))
                unique_hands[normalize_hand(five_of_a_kind_hand)] = (1, i + 1)
        # 5 wild cards (special case)
        unique_hands[('W1', 'W2', 'W3', 'W4', 'W5')] = (1, 1)  # Always rank 1, ordered rank 1
    
    # Bug card five-of-a-kind hands (only Aces, per your rules)
    ranks = ['A']
    for i, rank in enumerate(ranks):
        rank_cards = [f'{rank}{suit}' for suit in suits]
        # 1 to 4 bug cards
        for num_bugs in range(1, 5):
            bug_part = [f'B{j+1}' for j in range(num_bugs)]
            reg_count = 5 - num_bugs
            for reg_cards in itertools.combinations(rank_cards, reg_count):
                five_of_a_kind_hand = tuple(bug_part + list(reg_cards))
                unique_hands[normalize_hand(five_of_a_kind_hand)] = (1, i + 1)
        # 5 bug cards (special case)
        unique_hands[('B1', 'B2', 'B3', 'B4', 'B5')] = (1, 1)
    
    return unique_hands

def generate_wild_card_hands(hands, unique_hands):
    for hand, rank, ordered_rank in hands:
        normalized_hand = normalize_hand(hand)
        if unique_hands[normalized_hand] > (rank, ordered_rank):
            unique_hands[normalized_hand] = (rank, ordered_rank)

        # Generate hands with 1 to 4 wild cards
        for num_wild_cards in range(1, 5):
            for positions in itertools.combinations(range(5), num_wild_cards):
                wild_card_hand = list(hand)
                for pos, wild_card_num in zip(positions, range(1, num_wild_cards + 1)):
                    wild_card_hand[pos] = f'W{wild_card_num}'
                normalized_wild_card_hand = normalize_hand(wild_card_hand)
                if unique_hands[normalized_wild_card_hand] > (rank, ordered_rank):
                    unique_hands[normalized_wild_card_hand] = (rank, ordered_rank)

        # Generate hands with 1 to 4 bugs
        # since we moved ranks down one, for high, the special hands are 
        # royal flush (2), straight flush (3), flush (6), and straight (7)
        # treat bug like a wild card for those hands

        if rank in [2, 3, 6, 7]:
            for num_wild_cards in range(1, 5):
                for positions in itertools.combinations(range(5), num_wild_cards):
                    wild_card_hand = list(hand)
                    for pos, wild_card_num in zip(positions, range(1, num_wild_cards + 1)):
                        wild_card_hand[pos] = f'B{wild_card_num}'
                    normalized_wild_card_hand = normalize_hand(wild_card_hand)
                    if unique_hands[normalized_wild_card_hand] > (rank, ordered_rank):
                        unique_hands[normalized_wild_card_hand] = (rank, ordered_rank)        
        else:
            # Only use bugs where an Ace was in the original hand
            ace_positions = [pos for pos, card in enumerate(hand) if card[0] == 'A']
            num_aces = len(ace_positions)
            for num_bug_cards in range(1, 5):
                if num_bug_cards > num_aces:
                    continue                
                for positions in itertools.combinations(ace_positions, num_bug_cards):
                    bug_card_hand = list(hand)
                    for pos, bug_num in zip(positions, range(1, num_bug_cards + 1)):
                        bug_card_hand[pos] = f'B{bug_num}'
                    normalized_bug_card_hand = normalize_hand(bug_card_hand)
                    if unique_hands[normalized_bug_card_hand] > (rank, ordered_rank):
                        unique_hands[normalized_bug_card_hand] = (rank, ordered_rank)                

    return unique_hands

def write_hands_to_file(filename, hands):
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Write the header
        writer.writerow(['Hand', 'Rank', 'OrderedRank'])
        # Write the hands        
        for hand, (rank, ordered_rank) in sorted(hands.items(), key=lambda item: (item[1][0], item[1][1])):
            writer.writerow(list(hand) + [rank, ordered_rank])

# Example usage
input_filename = 'all_card_hands_ranked_27_ja_ffh_high.csv'  # Input file name
output_filename = 'all_card_hands_ranked_27_ja_ffh_high_wild_bug.csv'  # Output file name

hands = read_hands_from_file(input_filename)
unique_hands = generate_five_of_a_kind_hands()
unique_hands = generate_wild_card_hands(hands, unique_hands)
write_hands_to_file(output_filename, unique_hands)
