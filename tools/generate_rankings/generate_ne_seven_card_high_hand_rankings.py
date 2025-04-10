import itertools

class PokerHandEvaluator:
    def __init__(self):
        self.ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        self.suits = ['s', 'h', 'd', 'c']
        self.all_hands = []
        self.existing_hands = set()

    def generate_hands(self):
        """Generate all 7-card hands for Grand Straight Flush and Palace."""
        # Reset all_hands
        self.all_hands = []
        self.existing_hands = set()

        # Generate Grand Straight Flushes (Rank 1)
        self.generate_grand_straight_flushes()

        # Generate Palaces (Rank 2)
        self.generate_palaces()    

        # Generate Palaces (Rank 3)
        self.generate_long_straight_flushes()

        # Generate Grand Flushes (Rank 4)
        self.generate_grand_flushes()        

        # Generate Mansions (Rank 5)
        self.generate_mansions()       

        # Generate Straight Flushes (Rank 6)
        self.generate_straight_flushes()     

        # Generate Hotels (Rank 7)
        self.generate_hotels()                     

        # Generate Villas (Rank 8)
        self.generate_villas()     

        # Generate Grand Straights (Rank 9)
        self.generate_grand_straights()     

        # Generate Four of a Kinds (Rank 10)
        self.generate_four_of_a_kinds()          

        return self.all_hands
    
    def generate_grand_straight_flushes(self):
        """Generate all 7-card Grand Straight Flushes (Rank 1)."""
        ordered_rank = 1
        # Generate high-to-low sequences: A-K-Q-J-T-9-8 down to 8-7-6-5-4-3-2
        for i in range(len(self.ranks) - 6):
            for suit in self.suits:
                hand = [self.ranks[j] + suit for j in range(i, i + 7)]
                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                self.all_hands.append((hand, 1, ordered_rank))
                self.existing_hands.add(tuple(hand))
            ordered_rank += 1
        
        # Add Ace-low Grand Straight Flush: A-7-6-5-4-3-2
        a7_ranks = ['A', '7', '6', '5', '4', '3', '2']
        for suit in self.suits:
            hand = [a7_ranks[j] + suit for j in range(7)]
            hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
            self.all_hands.append((hand, 1, ordered_rank))    
            self.existing_hands.add(tuple(hand))

    def generate_palaces(self):
        """Generate all Palace hands (Rank 2): Four of one rank, three of another."""
        ordered_rank = 1
        for four_rank in self.ranks:
            remaining_ranks = [r for r in self.ranks if r != four_rank]
            for three_rank in remaining_ranks:
                # All suit combinations for four-of-a-kind (4 choose 4 = 1, but all possible assignments)
                for four_suits in itertools.combinations(self.suits, 4):
                    four_cards = [four_rank + s for s in four_suits]
                    # All suit combinations for three-of-a-kind (4 choose 3 = 4)
                    for three_suits in itertools.combinations(self.suits, 3):
                        three_cards = [three_rank + s for s in three_suits]
                        hand = four_cards + three_cards
                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                        self.all_hands.append((hand, 2, ordered_rank))
                        self.existing_hands.add(tuple(hand))
                ordered_rank += 1

    def generate_long_straight_flushes(self):
        # Define the 6-card straight sequences
        straight_sequences = [
            ['A', 'K', 'Q', 'J', 'T', '9'],
            ['K', 'Q', 'J', 'T', '9', '8'],
            ['Q', 'J', 'T', '9', '8', '7'],
            ['J', 'T', '9', '8', '7', '6'],
            ['T', '9', '8', '7', '6', '5'],
            ['9', '8', '7', '6', '5', '4'],
            ['8', '7', '6', '5', '4', '3'],
            ['7', '6', '5', '4', '3', '2'],
            ['A', '2', '3', '4', '5', '6']  # Ace-low
        ]

        ordered_rank = 1

        # Process each sequence
        for sequence in straight_sequences:
            # Process each kicker rank from high to low
            for kicker_rank in self.ranks:
                added_hand = False
                # Try each suit for the straight flush
                for sf_suit in self.suits:
                    six_cards = [r + sf_suit for r in sequence]
                    # Possible kickers: cards of kicker_rank not in six_cards
                    possible_kickers = [kicker_rank + s for s in self.suits if kicker_rank + s not in six_cards]
                    for kicker in possible_kickers:
                        hand = six_cards + [kicker]
                        # Sort hand consistently (by rank, then suit)
                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                        hand_tuple = tuple(hand)
                        # Skip if already in a higher rank
                        if hand_tuple not in self.existing_hands:
                            self.all_hands.append((hand, 3, ordered_rank))
                            self.existing_hands.add(hand_tuple)
                            added_hand = True
                # Increment OrderedRank after all hands with this kicker rank are added
                if added_hand:
                    ordered_rank += 1
        return ordered_rank    

    def generate_grand_flushes(self):
        # List of ranks: A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
        
        # Generate all 7-rank combinations
        rank_combinations = list(itertools.combinations(ranks, 7))
        
        # Sort by strength (highest ranks first)
        sorted_combinations = sorted(rank_combinations, key=lambda x: [ranks.index(r) for r in x])
        
        ordered_rank = 1
        wrote_hand = False
        for rank_combo in sorted_combinations:
            for suit in suits:
                hand = [r + suit for r in rank_combo]
                hand_tuple = tuple(hand)
                # Assuming existing_hands tracks higher-ranked hands to exclude
                if hand_tuple not in self.existing_hands:
                    self.all_hands.append((hand, 4, ordered_rank))
                    self.existing_hands.add(hand_tuple)
                    wrote_hand = True
            if wrote_hand:
                ordered_rank += 1  # Increment only after all suits are processed    
                wrote_hand = False

    def generate_mansions(self):
        """Generate all Mansion hands (Rank 5): Four of one rank, two of another, and one kicker."""
        ordered_rank = 1
        for four_rank in self.ranks:  # Iterate four-of-a-kind rank from A to 2
            remaining_ranks = [r for r in self.ranks if r != four_rank]  # Exclude four_rank
            for pair_rank in remaining_ranks:  # Pair rank from highest to lowest remaining
                kicker_ranks = [r for r in remaining_ranks if r != pair_rank]  # Exclude pair_rank
                for kicker_rank in kicker_ranks:  # Kicker from highest to lowest remaining
                    # Four-of-a-kind: all four suits (only one way)
                    four_cards = [four_rank + s for s in self.suits]
                    # Pair: choose 2 suits out of 4
                    for pair_suits in itertools.combinations(self.suits, 2):
                        pair_cards = [pair_rank + s for s in pair_suits]
                        # Kicker: choose 1 suit out of 4
                        for kicker_suit in self.suits:
                            kicker_card = kicker_rank + kicker_suit
                            # Combine all cards into a hand
                            hand = four_cards + pair_cards + [kicker_card]
                            # Sort by rank then suit for consistency
                            hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                            hand_tuple = tuple(hand)
                            # Add hand if not already in a stronger rank
                            if hand_tuple not in self.existing_hands:
                                self.all_hands.append((hand, 5, ordered_rank))
                                self.existing_hands.add(hand_tuple)
                    # Increment ordered_rank after all suit combos for this rank combo
                    ordered_rank += 1                

    def generate_straight_flushes(self):
        # Define the 5-card straight sequences
        straight_sequences = [
            ['A', 'K', 'Q', 'J', 'T'],
            ['K', 'Q', 'J', 'T', '9'],
            ['Q', 'J', 'T', '9', '8'],
            ['J', 'T', '9', '8', '7'],
            ['T', '9', '8', '7', '6'],
            ['9', '8', '7', '6', '5'],
            ['8', '7', '6', '5', '4'],
            ['7', '6', '5', '4', '3'],
            ['6', '5', '4', '3', '2'],
            ['5', '4', '3', '2', 'A']  # Ace-low
        ]

        ordered_rank = 1

        # Process each sequence from strongest to weakest
        for sequence in straight_sequences:
            # Iterate over kicker ranks, ensuring kicker_rank1 >= kicker_rank2 in strength
            for i, kicker_rank1 in enumerate(self.ranks):
                for kicker_rank2 in self.ranks[i:]:  # From kicker_rank1 to '2'
                    added_hand = False
                    # Try each suit for the straight flush
                    for sf_suit in self.suits:
                        # Create the 5-card straight flush
                        five_cards = [r + sf_suit for r in sequence]
                        # Possible kickers: cards of each rank not in five_cards
                        possible_kicker1 = [kicker_rank1 + s for s in self.suits if kicker_rank1 + s not in five_cards]
                        possible_kicker2 = [kicker_rank2 + s for s in self.suits if kicker_rank2 + s not in five_cards]
                        # Generate all combinations of kicker1 and kicker2
                        for kicker1 in possible_kicker1:
                            for kicker2 in possible_kicker2:
                                if kicker1 != kicker2:  # Ensure distinct cards
                                    hand = five_cards + [kicker1, kicker2]
                                    # Sort hand consistently (by rank, then suit)
                                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                    hand_tuple = tuple(hand)
                                    # Skip if already in a higher rank
                                    if hand_tuple not in self.existing_hands:
                                        self.all_hands.append((hand, 6, ordered_rank))
                                        self.existing_hands.add(hand_tuple)
                                        added_hand = True
                    # Increment OrderedRank after all hands with this kicker pair are added
                    if added_hand:
                        ordered_rank += 1
        return ordered_rank

    def generate_hotels(self):
        """Generate all Hotel hands (Rank 7): Two three-of-a-kinds and a kicker."""
        ordered_rank = 1
        for i in range(len(self.ranks) - 2):  # R1 from 'A' to '4'
            R1 = self.ranks[i]
            for j in range(i + 1, len(self.ranks) - 1):  # R2 from next rank to '3'
                R2 = self.ranks[j]
                kicker_candidates = [r for r in self.ranks if r != R1 and r != R2]
                for K in kicker_candidates:  # K over remaining ranks, high to low
                    # Generate suit combinations
                    for r1_suits in itertools.combinations(self.suits, 3):
                        r1_cards = [R1 + s for s in r1_suits]
                        for r2_suits in itertools.combinations(self.suits, 3):
                            r2_cards = [R2 + s for s in r2_suits]
                            for k_suit in self.suits:
                                k_card = K + k_suit
                                hand = r1_cards + r2_cards + [k_card]
                                # Sort by rank, then suit
                                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                hand_tuple = tuple(hand)
                                if hand_tuple not in self.existing_hands:
                                    self.all_hands.append((hand, 7, ordered_rank))
                                    self.existing_hands.add(hand_tuple)
                    ordered_rank += 1

    def generate_villas(self):
        """Generate all Villa hands (Rank 8): Three-of-a-kind and two pairs."""
        ordered_rank = 1
        # R1 (three-of-a-kind) from 'A' to '4' (needs two ranks below for pairs)
        for i in range(len(self.ranks) - 2):
            R1 = self.ranks[i]
            # Exclude R1 from pair ranks
            remaining_ranks = [r for r in self.ranks if r != R1]
            # P1 and P2 from remaining ranks, ensuring P1 > P2
            for j in range(len(remaining_ranks) - 1):
                P1 = remaining_ranks[j]
                for k in range(j + 1, len(remaining_ranks)):
                    P2 = remaining_ranks[k]
                    # Generate suit combinations
                    # Three-of-a-kind: 3 suits out of 4
                    for r1_suits in itertools.combinations(self.suits, 3):
                        r1_cards = [R1 + s for s in r1_suits]
                        # First pair: 2 suits out of 4
                        for p1_suits in itertools.combinations(self.suits, 2):
                            p1_cards = [P1 + s for s in p1_suits]
                            # Second pair: 2 suits out of 4
                            for p2_suits in itertools.combinations(self.suits, 2):
                                p2_cards = [P2 + s for s in p2_suits]
                                # Combine into a 7-card hand
                                hand = r1_cards + p1_cards + p2_cards
                                # Sort by rank (index in self.ranks), then suit
                                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                hand_tuple = tuple(hand)
                                # Add if not already classified in a higher rank
                                if hand_tuple not in self.existing_hands:
                                    self.all_hands.append((hand, 8, ordered_rank))
                                    self.existing_hands.add(hand_tuple)
                    # Increment ordered_rank per unique (R1, P1, P2) combination
                    ordered_rank += 1                    

    def generate_grand_straights(self):
        """Generate all 7-card Grand Straights (Rank 9) with mixed suits."""
        ordered_rank = 1
        straight_sequences = [
            ['A', 'K', 'Q', 'J', 'T', '9', '8'],  # A-high
            ['K', 'Q', 'J', 'T', '9', '8', '7'],
            ['Q', 'J', 'T', '9', '8', '7', '6'],
            ['J', 'T', '9', '8', '7', '6', '5'],
            ['T', '9', '8', '7', '6', '5', '4'],
            ['9', '8', '7', '6', '5', '4', '3'],
            ['8', '7', '6', '5', '4', '3', '2'],
            ['7', '6', '5', '4', '3', '2', 'A']   # Ace-low
        ]
        
        for sequence in straight_sequences:
            for suit_assignment in itertools.product(self.suits, repeat=7):
                hand = [sequence[j] + suit_assignment[j] for j in range(7)]
                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                hand_tuple = tuple(hand)
                if hand_tuple not in self.existing_hands:
                    self.all_hands.append((hand, 9, ordered_rank))
                    self.existing_hands.add(hand_tuple)
            ordered_rank += 1

    def generate_four_of_a_kinds(self):
        """Generate all Four of a Kind hands (Rank 10): Four cards of one rank and three distinct kickers."""
        ordered_rank = 1  # Tracks hand strength order

        # Step 1: Iterate over each possible four-of-a-kind rank
        for four_rank in self.ranks:  # 'A' to '2'
            # Step 2: Get remaining ranks for kickers
            remaining_ranks = [r for r in self.ranks if r != four_rank]
            # Step 3: Choose three distinct kicker ranks
            for kicker_ranks in itertools.combinations(remaining_ranks, 3):
                # Sort kickers in descending order (e.g., K, Q, J)
                kicker_ranks = sorted(kicker_ranks, key=lambda x: self.ranks.index(x))
                # Step 4: Generate four-of-a-kind cards with all suits
                four_cards = [four_rank + s for s in self.suits]
                # Step 5: Assign suits to kickers
                for kicker_suits in itertools.product(self.suits, repeat=3):
                    kicker_cards = [kicker_ranks[i] + kicker_suits[i] for i in range(3)]
                    # Combine into a 7-card hand
                    hand = four_cards + kicker_cards
                    # Sort for consistency (by rank, then suit)
                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                    hand_tuple = tuple(hand)
                    # Step 6: Add hand if not already classified
                    if hand_tuple not in self.existing_hands:
                        self.all_hands.append((hand, 10, ordered_rank))
                        self.existing_hands.add(hand_tuple)
                # Increment ordered_rank after all suit combos for this rank combo
                ordered_rank += 1
        
    def save_hands_to_file(self, filename):
        """Save all hands to a CSV file."""
        with open(filename, 'w') as f:
            f.write('Hand,Rank,OrderedRank\n')
            for hand, rank, ordered_rank in self.all_hands:
                hand_str = ','.join(hand)
                f.write(f'{hand_str},{rank},{ordered_rank}\n')

# Usage
if __name__ == "__main__":
    evaluator = PokerHandEvaluator()
    hands = evaluator.generate_hands()
    evaluator.save_hands_to_file('nehe_hands_rank1_10.csv')
    print(f"Generated {len(hands)} hands for Ranks 1 thru 10.")
