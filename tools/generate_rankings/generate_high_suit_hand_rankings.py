import itertools

def sort_key_a2(card):
    ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    suits = ['s', 'h', 'd', 'c']
    rank, suit = card[:-1], card[-1]
    return ranks.index(rank), suits.index(suit)

class PokerHandEvaluator:
    def generate_high_card_combos(self, num_cards):
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
        deck = [f"{rank}{suit}" for rank in ranks for suit in suits]
        card_combos = list(itertools.combinations(deck, num_cards))
        sorted_combos = [sorted(hand, key=sort_key_a2) for hand in card_combos]
        sorted_combos.sort(key=lambda hand: [sort_key_a2(card) for card in hand])
        return [list(hand) for hand in sorted_combos]

    def generate_three_card_high_suit_hands(self, suit='s'):
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
        all_hands = []

        # Generate all possible three-card combinations
        deck = [f"{rank}{suit}" for rank in ranks for suit in suits]
        three_card_combos = list(itertools.combinations(deck, 3))

        for combo in three_card_combos:
            hand = list(combo)
            hand.sort(key=sort_key_a2)  # Sort hand for consistency

            # Find the highest card of the specified suit in the hand
            suit_cards = [card for card in hand if card[-1] == suit]
            if suit_cards:
                # Get the rank of the highest card of the specified suit
                highest_suit_card = min(suit_cards, key=lambda x: ranks.index(x[:-1]))
                rank_idx = ranks.index(highest_suit_card[:-1]) + 1  # 1 for Ace, 2 for King, etc.
            else:
                # No cards of the specified suit
                rank_idx = len(ranks) + 1  # Rank 14 for no spades

            all_hands.append((hand, rank_idx, 1))  # OrderedRank is always 1

        # Sort all hands for consistent output
        all_hands.sort(key=lambda x: (x[1], [sort_key_a2(card) for card in x[0]]))
        return all_hands
    
    # generate one-card highest suit hands
    # They will look like this (for spades):
    # As, 1, 1
    # Ks, 2, 2
    # ... and so on - all non-spade cards will be rank 14

    # Generate one-card high suit hands
    def generate_one_card_high_suit_hands(self, suit='s'):
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
        all_hands = []

        # Generate all possible one-card combinations
        deck = [f"{rank}{suit}" for rank in ranks for suit in suits]
        one_card_combos = list(itertools.combinations(deck, 1))

        for combo in one_card_combos:
            hand = list(combo)
            hand.sort(key=sort_key_a2)  # Sort hand for consistency

            # Find the highest card of the specified suit in the hand
            suit_cards = [card for card in hand if card[-1] == suit]
            if suit_cards:
                # Get the rank of the highest card of the specified suit
                highest_suit_card = min(suit_cards, key=lambda x: ranks.index(x[:-1]))
                rank_idx = ranks.index(highest_suit_card[:-1]) + 1  # 1 for Ace, 2 for King, etc.
            else:
                # No cards of the specified suit
                rank_idx = len(ranks) + 1  # Rank 14 for no spades

            all_hands.append((hand, rank_idx, 1))  # OrderedRank is always 1

        # Sort all hands for consistent output
        all_hands.sort(key=lambda x: (x[1], [sort_key_a2(card) for card in x[0]]))
        return all_hands    

# Main script to generate files for each suit
hand_evaluator = PokerHandEvaluator()
suits = ['s', 'h', 'd', 'c']
suit_names = {'s': 'spade', 'h': 'heart', 'd': 'diamond', 'c': 'club'}

for suit in suits:
    # Generate all possible hands for the given suit
    all_hands = hand_evaluator.generate_three_card_high_suit_hands(suit=suit)

    # Validate that all three-card combinations are covered and check for duplicates
    card_combos = hand_evaluator.generate_high_card_combos(3)
    all_hands_set = {tuple(hand) for hand, _, _ in all_hands}
    not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]
    
    print(f"\nSuit: {suit_names[suit]}")
    print(f"There are {len(card_combos)} combinations of three cards.")
    print(f"Generated {len(all_hands)} hands.")
    if len(all_hands_set) != len(all_hands):
        print("Warning: Duplicate hands detected!")
    if not_in_all_hands:
        print(f"The following hands were not generated for high {suit_names[suit]} hands:")
        print(not_in_all_hands)
    else:
        print(f"All hands accounted for in high {suit_names[suit]} ranking.")

    # Write to CSV file
    output_file = f'all_card_hands_ranked_three_card_high_{suit_names[suit]}.csv'
    with open(output_file, 'w') as file:
        file.write('Hand,Rank,OrderedRank\n')
        for hand, rank, ordered_rank in all_hands:
            file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')

for suit in suits:
    # Generate all possible hands for the given suit
    all_hands = hand_evaluator.generate_one_card_high_suit_hands(suit=suit)

    # Validate that all one-card combinations are covered and check for duplicates
    card_combos = hand_evaluator.generate_high_card_combos(1)
    all_hands_set = {tuple(hand) for hand, _, _ in all_hands}
    not_in_all_hands = [hand for hand in card_combos if tuple(hand) not in all_hands_set]
    
    print(f"\nSuit: {suit_names[suit]}")
    print(f"There are {len(card_combos)} combinations of one cards.")
    print(f"Generated {len(all_hands)} hands.")
    if len(all_hands_set) != len(all_hands):
        print("Warning: Duplicate hands detected!")
    if not_in_all_hands:
        print(f"The following hands were not generated for high {suit_names[suit]} hands:")
        print(not_in_all_hands)
    else:
        print(f"All hands accounted for in high {suit_names[suit]} ranking.")

    # Write to CSV file
    output_file = f'all_card_hands_ranked_one_card_high_{suit_names[suit]}.csv'
    with open(output_file, 'w') as file:
        file.write('Hand,Rank,OrderedRank\n')
        for hand, rank, ordered_rank in all_hands:
            file.write(','.join(hand) + ',' + str(rank) + ',' + str(ordered_rank) + '\n')
