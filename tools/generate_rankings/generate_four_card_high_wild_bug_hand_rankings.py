import csv
from collections import defaultdict
import itertools

hand_length = 4

def read_hands_from_file(filename):
    hands = []
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip the header
        for row in reader:
            hand = tuple(row[:hand_length])
            rank = int(row[hand_length]) 
            ordered_rank = int(row[hand_length + 1])
            hands.append((hand, rank, ordered_rank))
    return hands

def normalize_hand(hand):
    wild_cards = sorted(card for card in hand if card.startswith('W'))
    bug_cards = sorted(card for card in hand if card.startswith('B'))
    non_wild_cards = [card for card in hand if not card.startswith('W') and not card.startswith('B')]
    return tuple(wild_cards + bug_cards + non_wild_cards)

from collections import defaultdict
import itertools

def generate_wild_card_hands(hands, unique_hands):
    for hand, rank, ordered_rank in hands:
        normalized_hand = normalize_hand(hand)
        if unique_hands[normalized_hand] > (rank, ordered_rank):
            unique_hands[normalized_hand] = (rank, ordered_rank)

        # Generate hands with 1 to hand_length wild cards
        for num_wild_cards in range(1, hand_length):
            for positions in itertools.combinations(range(hand_length), num_wild_cards):
                wild_card_hand = list(hand)
                for pos, wild_card_num in zip(positions, range(1, num_wild_cards + 1)):
                    wild_card_hand[pos] = f'W{wild_card_num}'
                normalized_wild_card_hand = normalize_hand(wild_card_hand)
                if unique_hands[normalized_wild_card_hand] > (rank, ordered_rank):
                    unique_hands[normalized_wild_card_hand] = (rank, ordered_rank)

        # Only use bugs where an Ace was in the original hand
        ace_positions = [pos for pos, card in enumerate(hand) if card[0] == 'A']
        num_aces = len(ace_positions)
        for num_bug_cards in range(1, hand_length):
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
input_filename = 'all_card_hands_ranked_four_card_high.csv'  # Input file name
output_filename = 'all_card_hands_ranked_four_card_high_wild_bug.csv'  # Output file name

hands = read_hands_from_file(input_filename)
unique_hands = defaultdict(lambda: (float('inf'), float('inf')))
unique_hands = generate_wild_card_hands(hands, unique_hands)
write_hands_to_file(output_filename, unique_hands)
