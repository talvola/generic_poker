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
    non_wild_cards = [card for card in hand if not card.startswith('W')]
    return tuple(wild_cards + non_wild_cards)

def generate_five_of_a_kind_hands():
    unique_hands = defaultdict(lambda: (float('inf'), float('inf')))  # Store (rank, ordered_rank) with default high values

    # Add five-of-a-kind hands
    ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    for i, rank in enumerate(ranks):
        # 1 wild card
        five_of_a_kind_hand = ('W1', f'{rank}s', f'{rank}h', f'{rank}d', f'{rank}c')
        unique_hands[normalize_hand(five_of_a_kind_hand)] = (1, i + 1)
        # 2 wild cards
        five_of_a_kind_hand = ('W1', 'W2', f'{rank}s', f'{rank}h', f'{rank}d')
        unique_hands[normalize_hand(five_of_a_kind_hand)] = (1, i + 1)
        # 3 wild cards
        five_of_a_kind_hand = ('W1', 'W2', 'W3', f'{rank}s', f'{rank}h')
        unique_hands[normalize_hand(five_of_a_kind_hand)] = (1, i + 1)
        # 4 wild cards
        five_of_a_kind_hand = ('W1', 'W2', 'W3', 'W4', f'{rank}s')
        unique_hands[normalize_hand(five_of_a_kind_hand)] = (1, i + 1)
        # 5 wild cards (special case)
        unique_hands[('W1', 'W2', 'W3', 'W4', 'W5')] = (1, 1)
    
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
input_filename = 'all_card_hands_ranked_high.csv'  # Input file name
output_filename = 'all_card_hands_ranked_high_wild.csv'  # Output file name

hands = read_hands_from_file(input_filename)
unique_hands = generate_five_of_a_kind_hands()
unique_hands = generate_wild_card_hands(hands, unique_hands)
write_hands_to_file(output_filename, unique_hands)
