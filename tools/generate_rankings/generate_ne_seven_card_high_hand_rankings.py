import itertools
import psutil
import gc
import os

class PokerHandEvaluator:
    def __init__(self):
        self.ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        self.suits = ['s', 'h', 'd', 'c']
        self.existing_hands = set()
        self.card_to_int = {r + s: i * 4 + j for i, r in enumerate(self.ranks) 
                           for j, s in enumerate(self.suits)}     
        self.buffer = []
        self.buffer_size = 50000  # Larger buffer to reduce I/O operations
        self.output_dir = "poker_hands"
        os.makedirs(self.output_dir, exist_ok=True) 

        # Define methods for generating each rank
        self.rank_methods = [
            self.generate_grand_straight_flushes,  # Rank 1
            self.generate_palaces,                 # Rank 2
            self.generate_long_straight_flushes,   # Rank 3
            self.generate_grand_flushes,           # Rank 4
            self.generate_mansions,                # Rank 5
            self.generate_straight_flushes,        # Rank 6
            self.generate_hotels,                  # Rank 7
            self.generate_villas,                  # Rank 8
            self.generate_grand_straights,         # Rank 9
            self.generate_four_of_a_kinds,         # Rank 10
            self.generate_long_flushes,            # Rank 11
            self.generate_long_straights,          # Rank 12
            self.generate_three_pairs,             # Rank 13
            self.generate_full_houses,             # Rank 14
            self.generate_flushes,                 # Rank 15
            self.generate_straights,               # Rank 16
            self.generate_three_of_a_kinds,        # Rank 17
            self.generate_two_pairs,               # Rank 18
            self.generate_one_pairs,               # Rank 19
            self.generate_high_cards               # Rank 20
        ]    

    
    def encode_hand(self, hand):
        """Encode a hand as a unique integer using bit operations."""
        # Sort cards for consistent encoding
        sorted_cards = sorted([self.card_to_int[card] for card in hand])
        # Use bit operations instead of exponentiation for efficiency
        result = 0
        for card in sorted_cards:
            result = (result << 6) | card  # Each card needs 6 bits (2^6 = 64 > 52)
        return result    
    
     
    

    def write_buffer(self, file_path):
        """Write buffer to file and clear it."""
        if not self.buffer:
            return 0
            
        count = len(self.buffer)
        with open(file_path, 'a') as f:
            for hand, rank, ordered_rank in self.buffer:
                hand_str = ','.join(hand)
                f.write(f"{hand_str},{rank},{ordered_rank}\n")
        
        self.buffer.clear()
        return count

    
    def generate_hands(self):
        """Generate all poker hands rank by rank."""
        total_hands = 0
        
        # Process each rank independently
        for rank, method in enumerate(self.rank_methods, 1):
            print(f"Processing rank {rank}...")
            
            # Clear memory from previous rank
            #self.existing_hands.clear()
            self.buffer.clear()
            gc.collect()
            
            # Process this rank
            rank_file = os.path.join(self.output_dir, f"rank_{rank}.csv")
            with open(rank_file, 'w') as f:
                f.write("Hand,Rank,OrderedRank\n")
            
            count = method(rank_file)
            total_hands += count
            
            # Force garbage collection
            #self.existing_hands.clear()
            self.buffer.clear()
            gc.collect()
            
            print(f"Rank {rank} complete: {count} hands")
            print(f"Memory usage: {psutil.Process().memory_info().rss / 1024 ** 2:.2f} MB")
            
        return total_hands    
    
    def generate_grand_straight_flushes(self, output_file):
        """Generate all 7-card Grand Straight Flushes (Rank 1)."""
        total_hands = 0
        ordered_rank = 1
        # Generate high-to-low sequences: A-K-Q-J-T-9-8 down to 8-7-6-5-4-3-2
        for i in range(len(self.ranks) - 6):
            for suit in self.suits:
                hand = [self.ranks[j] + suit for j in range(i, i + 7)]
                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                self.buffer.append((hand, 1, ordered_rank))
                encoded = self.encode_hand(hand)
                self.existing_hands.add(encoded)      
                total_hands += 1

            if len(self.buffer) >= self.buffer_size:
                self.write_buffer(output_file)

            ordered_rank += 1
        
        # Add Ace-low Grand Straight Flush: A-7-6-5-4-3-2
        a7_ranks = ['A', '7', '6', '5', '4', '3', '2']
        for suit in self.suits:
            hand = [a7_ranks[j] + suit for j in range(7)]
            hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
            self.buffer.append((hand, 1, ordered_rank))    
            encoded = self.encode_hand(hand)
            self.existing_hands.add(encoded)
            total_hands += 1

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands            

    def generate_palaces(self, output_file):
        """Generate all Palace hands (Rank 2): Four of one rank, three of another."""
        total_hands = 0
        ordered_rank = 1
        for four_rank in self.ranks:
            remaining_ranks = [r for r in self.ranks if r != four_rank]
            for three_rank in remaining_ranks:
                # All suit combinations for four-of-a-kind (4 choose 4 = 1, but all possible assignments)
                added_hand = False
                for four_suits in itertools.combinations(self.suits, 4):
                    four_cards = [four_rank + s for s in four_suits]
                    # All suit combinations for three-of-a-kind (4 choose 3 = 4)
                    for three_suits in itertools.combinations(self.suits, 3):
                        three_cards = [three_rank + s for s in three_suits]
                        hand = four_cards + three_cards
                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                        encoded = self.encode_hand(hand)
                        if encoded not in self.existing_hands:
                            self.buffer.append((hand, 2, ordered_rank))
                            self.existing_hands.add(encoded)
                            total_hands += 1
                            added_hand = True

                            if len(self.buffer) >= self.buffer_size:
                                self.write_buffer(output_file)

                if added_hand:
                    ordered_rank += 1

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                       

    def generate_long_straight_flushes(self, output_file):
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
        total_hands = 0

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
                        encoded = self.encode_hand(hand)
                        # Skip if already in a higher rank
                        if encoded not in self.existing_hands:
                            self.buffer.append((hand, 3, ordered_rank))
                            self.existing_hands.add(encoded)
                            total_hands += 1
                            added_hand = True
                            if len(self.buffer) >= self.buffer_size:
                                self.write_buffer(output_file)
                # Increment OrderedRank after all hands with this kicker rank are added
                if added_hand:
                    ordered_rank += 1

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands  

    def generate_grand_flushes(self, output_file):
        # List of ranks: A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']
        
        # Generate all 7-rank combinations
        rank_combinations = list(itertools.combinations(ranks, 7))
        
        # Sort by strength (highest ranks first)
        sorted_combinations = sorted(rank_combinations, key=lambda x: [ranks.index(r) for r in x])
        
        ordered_rank = 1
        total_hands = 0
        wrote_hand = False
        for rank_combo in sorted_combinations:
            for suit in suits:
                hand = [r + suit for r in rank_combo]
                # Sort hand consistently (by rank, then suit)
                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))               
                encoded = self.encode_hand(hand)
                # Assuming existing_hands tracks higher-ranked hands to exclude
                if encoded not in self.existing_hands:
                    self.buffer.append((hand, 4, ordered_rank))
                    self.existing_hands.add(encoded)
                    total_hands += 1
                    wrote_hand = True
                    if len(self.buffer) >= self.buffer_size:
                        self.write_buffer(output_file)
            if wrote_hand:
                ordered_rank += 1  # Increment only after all suits are processed    
                wrote_hand = False

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                  

    def generate_mansions(self, output_file):
        """Generate all Mansion hands (Rank 5): Four of one rank, two of another, and one kicker."""
        ordered_rank = 1
        total_hands = 0

        for four_rank in self.ranks:  # Iterate four-of-a-kind rank from A to 2
            remaining_ranks = [r for r in self.ranks if r != four_rank]  # Exclude four_rank
            for pair_rank in remaining_ranks:  # Pair rank from highest to lowest remaining
                kicker_ranks = [r for r in remaining_ranks if r != pair_rank]  # Exclude pair_rank
                for kicker_rank in kicker_ranks:  # Kicker from highest to lowest remaining
                    # Four-of-a-kind: all four suits (only one way)
                    four_cards = [four_rank + s for s in self.suits]
                    # Pair: choose 2 suits out of 4
                    added_hand = False
                    for pair_suits in itertools.combinations(self.suits, 2):
                        pair_cards = [pair_rank + s for s in pair_suits]
                        # Kicker: choose 1 suit out of 4
                        for kicker_suit in self.suits:
                            kicker_card = kicker_rank + kicker_suit
                            # Combine all cards into a hand
                            hand = four_cards + pair_cards + [kicker_card]
                            # Sort by rank then suit for consistency
                            hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                            encoded = self.encode_hand(hand)
                            # Add hand if not already in a stronger rank
                            if encoded not in self.existing_hands:
                                self.buffer.append((hand, 5, ordered_rank))
                                self.existing_hands.add(encoded)
                                total_hands += 1
                                added_hand = True 
                                if len(self.buffer) >= self.buffer_size:
                                    self.write_buffer(output_file)
                    # Increment ordered_rank after all suit combos for this rank combo
                    if added_hand:
                        ordered_rank += 1    

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                                      

    def generate_straight_flushes(self, output_file):
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
        total_hands = 0

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
                                    encoded = self.encode_hand(hand)
                                    # Skip if already in a higher rank
                                    if encoded not in self.existing_hands:
                                        self.buffer.append((hand, 6, ordered_rank))
                                        self.existing_hands.add(encoded)
                                        total_hands += 1
                                        added_hand = True
                                        if len(self.buffer) >= self.buffer_size:
                                            self.write_buffer(output_file)                                             
                    # Increment OrderedRank after all hands with this kicker pair are added
                    if added_hand:
                        ordered_rank += 1

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands   

    def generate_hotels(self, output_file):
        """Generate all Hotel hands (Rank 7): Two three-of-a-kinds and a kicker."""
        ordered_rank = 1
        total_hands = 0

        for i in range(len(self.ranks)):  # R1 from 'A' to '4'
            R1 = self.ranks[i]
            for j in range(i + 1, len(self.ranks)):  # R2 from next rank to '3'
                R2 = self.ranks[j]
                kicker_candidates = [r for r in self.ranks if r != R1 and r != R2]
                for K in kicker_candidates:  # K over remaining ranks, high to low
                    # Generate suit combinations
                    added_hand = False
                    for r1_suits in itertools.combinations(self.suits, 3):
                        r1_cards = [R1 + s for s in r1_suits]
                        for r2_suits in itertools.combinations(self.suits, 3):
                            r2_cards = [R2 + s for s in r2_suits]
                            for k_suit in self.suits:
                                k_card = K + k_suit
                                hand = r1_cards + r2_cards + [k_card]
                                # Sort by rank, then suit
                                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                encoded = self.encode_hand(hand)
                                if encoded not in self.existing_hands:
                                    self.buffer.append((hand, 7, ordered_rank))
                                    self.existing_hands.add(encoded)
                                    added_hand = True
                                    total_hands += 1
                                    if len(self.buffer) >= self.buffer_size:
                                        self.write_buffer(output_file)                                         
                    if added_hand:
                        ordered_rank += 1

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                         

    def generate_villas(self, output_file):
        """Generate all Villa hands (Rank 8): Three-of-a-kind and two pairs."""
        ordered_rank = 1
        total_hands = 0

        # R1 (three-of-a-kind) from 'A' to '4' (needs two ranks below for pairs)
        for i in range(len(self.ranks)):
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
                    added_hand = False
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
                                encoded = self.encode_hand(hand)
                                # Add if not already classified in a higher rank
                                if encoded not in self.existing_hands:
                                    self.buffer.append((hand, 8, ordered_rank))
                                    self.existing_hands.add(encoded)
                                    added_hand = True
                                    total_hands += 1
                                    if len(self.buffer) >= self.buffer_size:
                                        self.write_buffer(output_file)                                         
                    # Increment ordered_rank per unique (R1, P1, P2) combination
                    if added_hand:
                        ordered_rank += 1   

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                                            

    def generate_grand_straights(self, output_file):
        """Generate all 7-card Grand Straights (Rank 9) with mixed suits."""
        ordered_rank = 1
        total_hands = 0

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
                encoded = self.encode_hand(hand)
                added_hand = False
                if encoded not in self.existing_hands:
                    self.buffer.append((hand, 9, ordered_rank))
                    self.existing_hands.add(encoded)
                    added_hand = True
                    total_hands += 1
                    if len(self.buffer) >= self.buffer_size:
                        self.write_buffer(output_file)                         
                if added_hand:
                    ordered_rank += 1

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                         

    def generate_four_of_a_kinds(self, output_file):
        """Generate all Four of a Kind hands (Rank 10): Four cards of one rank and three distinct kickers."""
        ordered_rank = 1  # Tracks hand strength order
        total_hands = 0

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
                added_hand = False
                for kicker_suits in itertools.product(self.suits, repeat=3):
                    kicker_cards = [kicker_ranks[i] + kicker_suits[i] for i in range(3)]
                    # Combine into a 7-card hand
                    hand = four_cards + kicker_cards
                    # Sort for consistency (by rank, then suit)
                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                    encoded = self.encode_hand(hand)
                    # Step 6: Add hand if not already classified
                    if encoded not in self.existing_hands:
                        self.buffer.append((hand, 10, ordered_rank))
                        self.existing_hands.add(encoded)
                        added_hand = True
                        total_hands += 1
                        if len(self.buffer) >= self.buffer_size:
                            self.write_buffer(output_file)                             
                # Increment ordered_rank after all suit combos for this rank combo
                if added_hand:
                    ordered_rank += 1

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                     

    def generate_long_flushes(self, output_file):
        """Generate all Long Flush hands (Rank 11): 6-card flush with one kicker."""
        ordered_rank = 1
        total_hands = 0

        # For each suit as the flush suit
        for flush_suit in self.suits:
            # Generate all 6-card combinations of ranks for this suit
            flush_combinations = list(itertools.combinations(self.ranks, 6))
            # Sort by strength (highest ranks first)
            sorted_combinations = sorted(flush_combinations, key=lambda x: [self.ranks.index(r) for r in x])

            # Process each 6-card flush combination
            for flush_ranks in sorted_combinations:
                six_cards = [r + flush_suit for r in flush_ranks]
                # Process each kicker rank from high to low
                for kicker_rank in self.ranks:
                    added_hand = False
                    # Possible kickers: cards of kicker_rank not in six_cards
                    possible_kickers = [kicker_rank + s for s in self.suits if kicker_rank + s not in six_cards]
                    for kicker in possible_kickers:
                        hand = six_cards + [kicker]
                        # Sort consistently (by rank, then suit)
                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                        encoded = self.encode_hand(hand)
                        # Skip if already in a higher rank
                        if encoded not in self.existing_hands:
                            self.buffer.append((hand, 11, ordered_rank))
                            self.existing_hands.add(encoded)
                            added_hand = True
                            total_hands += 1
                            if len(self.buffer) >= self.buffer_size:
                                self.write_buffer(output_file)                                 
                    # Increment OrderedRank after all hands with this kicker rank are added
                    if added_hand:
                        ordered_rank += 1    

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                                         

    def generate_long_straights(self, output_file):
        """Generate all Long Straight hands (Rank 12): 6-card straight with one kicker."""
        ordered_rank = 1
        total_hands = 0

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

        # Process each sequence
        for sequence in straight_sequences:
            # Process each kicker rank from high to low
            for kicker_rank in self.ranks:
                added_hand = False
                # Generate all suit combinations for the 6-card straight
                for suit_assignment in itertools.product(self.suits, repeat=6):
                    six_cards = [sequence[i] + suit_assignment[i] for i in range(6)]
                    # Possible kickers: cards of kicker_rank not in six_cards
                    possible_kickers = [kicker_rank + s for s in self.suits if kicker_rank + s not in six_cards]
                    for kicker in possible_kickers:
                        hand = six_cards + [kicker]
                        # Sort consistently (by rank, then suit)
                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                        encoded = self.encode_hand(hand)
                        # Skip if already in a higher rank
                        if encoded not in self.existing_hands:
                            self.buffer.append((hand, 12, ordered_rank))
                            self.existing_hands.add(encoded)
                            added_hand = True
                            total_hands += 1
                            if len(self.buffer) >= self.buffer_size:
                                self.write_buffer(output_file)                                 
                # Increment OrderedRank after all hands with this kicker rank are added
                if added_hand:
                    ordered_rank += 1         

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                                     

    def generate_three_pairs(self, output_file):
        """Generate all Three Pair hands (Rank 13): Three pairs with a kicker."""
        ordered_rank = 1
        total_hands = 0

        # Choose 3 ranks for pairs from 13 available ranks
        for pair_ranks in itertools.combinations(self.ranks, 3):
            # Sort pairs in descending order for consistent strength (e.g., A, K, Q)
            pair_ranks = sorted(pair_ranks, key=lambda x: self.ranks.index(x))
            P1, P2, P3 = pair_ranks[0], pair_ranks[1], pair_ranks[2]  # P1 > P2 > P3
            # Kicker candidates exclude the three pair ranks
            kicker_ranks = [r for r in self.ranks if r not in pair_ranks]
            for kicker_rank in kicker_ranks:
                # Assign suits to each pair (2 suits out of 4)
                added_hand = False
                for p1_suits in itertools.combinations(self.suits, 2):
                    p1_cards = [P1 + s for s in p1_suits]
                    for p2_suits in itertools.combinations(self.suits, 2):
                        p2_cards = [P2 + s for s in p2_suits]
                        for p3_suits in itertools.combinations(self.suits, 2):
                            p3_cards = [P3 + s for s in p3_suits]
                            # Kicker: 1 suit out of 4
                            for kicker_suit in self.suits:
                                kicker_card = kicker_rank + kicker_suit
                                hand = p1_cards + p2_cards + p3_cards + [kicker_card]
                                # Sort consistently (by rank, then suit)
                                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                encoded = self.encode_hand(hand)
                                # Skip if already in a higher rank
                                if encoded not in self.existing_hands:
                                    self.buffer.append((hand, 13, ordered_rank))
                                    self.existing_hands.add(encoded)
                                    added_hand = True
                                    total_hands += 1
                                    if len(self.buffer) >= self.buffer_size:
                                        self.write_buffer(output_file)                                         
                # Increment ordered_rank after each (P1, P2, P3, kicker) combination
                if added_hand:
                    ordered_rank += 1     

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                          

    def generate_full_houses(self, output_file):
        """Generate all Full House hands (Rank 14): Three-of-a-kind, a pair, and two kickers."""
        ordered_rank = 1
        total_hands = 0

        for R1 in self.ranks:  # Three-of-a-kind rank
            remaining_ranks = [r for r in self.ranks if r != R1]
            for R2 in remaining_ranks:  # Pair rank
                kicker_candidates = [r for r in remaining_ranks if r != R2]
                # Choose 2 kickers, K1 > K2
                for kicker_pair in itertools.combinations(kicker_candidates, 2):
                    added_hand = False
                    K1, K2 = sorted(kicker_pair, key=lambda x: self.ranks.index(x))  # K1 > K2
                    # Assign suits
                    for r1_suits in itertools.combinations(self.suits, 3):  # 3 suits for R1
                        r1_cards = [R1 + s for s in r1_suits]
                        for r2_suits in itertools.combinations(self.suits, 2):  # 2 suits for R2
                            r2_cards = [R2 + s for s in r2_suits]
                            for k1_suit in self.suits:  # 1 suit for K1
                                k1_card = K1 + k1_suit
                                for k2_suit in self.suits:  # 1 suit for K2
                                    if k2_suit != k1_suit or K1 != K2:  # Ensure distinct cards
                                        k2_card = K2 + k2_suit
                                        hand = r1_cards + r2_cards + [k1_card, k2_card]
                                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                        encoded = self.encode_hand(hand)
                                        if encoded not in self.existing_hands:
                                            self.buffer.append((hand, 14, ordered_rank))
                                            self.existing_hands.add(encoded)
                                            added_hand = True
                                            total_hands += 1
                                            if len(self.buffer) >= self.buffer_size:
                                                self.write_buffer(output_file)                                                 
                    if added_hand:
                        ordered_rank += 1  # Increment after each (R1, R2, K1, K2)   

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                        

    def generate_flushes(self, output_file):
        """Generate all Flush hands (Rank 15): 5-card flush with two kickers."""
        ordered_rank = 1
        total_hands = 0

        # For each suit as the flush suit
        for flush_suit in self.suits:
            # Generate all 5-card combinations of ranks
            flush_combinations = list(itertools.combinations(self.ranks, 5))
            # Sort by strength (highest ranks first)
            sorted_combinations = sorted(flush_combinations, key=lambda x: [self.ranks.index(r) for r in x])

            # Process each 5-card flush combination
            for flush_ranks in sorted_combinations:
                five_cards = [r + flush_suit for r in flush_ranks]
                # Iterate over kicker ranks, K1 >= K2 in strength
                for i, kicker_rank1 in enumerate(self.ranks):
                    for kicker_rank2 in self.ranks[i:]:  # From K1 to '2'
                        added_hand = False
                        # Possible kickers: exclude cards in five_cards
                        possible_kicker1 = [kicker_rank1 + s for s in self.suits if kicker_rank1 + s not in five_cards]
                        possible_kicker2 = [kicker_rank2 + s for s in self.suits if kicker_rank2 + s not in five_cards]
                        for kicker1 in possible_kicker1:
                            for kicker2 in possible_kicker2:
                                if kicker1 != kicker2:  # Ensure distinct cards
                                    hand = five_cards + [kicker1, kicker2]
                                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                    encoded = self.encode_hand(hand)
                                    if encoded not in self.existing_hands:
                                        self.buffer.append((hand, 15, ordered_rank))
                                        self.existing_hands.add(encoded)
                                        added_hand = True
                                        total_hands += 1
                                        if len(self.buffer) >= self.buffer_size:
                                            self.write_buffer(output_file)                                                 
                        if added_hand:
                            ordered_rank += 1      

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                                       

    def generate_straights(self, output_file):
        """Generate all Straight hands (Rank 16): 5-card straight with two kickers."""
        ordered_rank = 1
        total_hands = 0
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

        # Process each sequence
        for sequence in straight_sequences:
            # Iterate over kicker ranks, K1 >= K2
            for i, kicker_rank1 in enumerate(self.ranks):
                for kicker_rank2 in self.ranks[i:]:
                    added_hand = False
                    # Generate all suit combinations for the 5-card straight
                    for suit_assignment in itertools.product(self.suits, repeat=5):
                        five_cards = [sequence[j] + suit_assignment[j] for j in range(5)]
                        # Possible kickers: exclude cards in five_cards
                        possible_kicker1 = [kicker_rank1 + s for s in self.suits if kicker_rank1 + s not in five_cards]
                        possible_kicker2 = [kicker_rank2 + s for s in self.suits if kicker_rank2 + s not in five_cards]
                        for kicker1 in possible_kicker1:
                            for kicker2 in possible_kicker2:
                                if kicker1 != kicker2:  # Ensure distinct cards
                                    hand = five_cards + [kicker1, kicker2]
                                    hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                    encoded = self.encode_hand(hand)
                                    if encoded not in self.existing_hands:
                                        self.buffer.append((hand, 16, ordered_rank))
                                        self.existing_hands.add(encoded)
                                        added_hand = True
                                        total_hands += 1
                                        if len(self.buffer) >= self.buffer_size:
                                            self.write_buffer(output_file)     
                    if added_hand:
                        ordered_rank += 1     

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                            

    def generate_three_of_a_kinds(self, output_file):
        """Generate all Three of a Kind hands (Rank 17): Three cards of one rank and four kickers."""
        ordered_rank = 1
        total_hands = 0

        for R1 in self.ranks:  # Three-of-a-kind rank
            remaining_ranks = [r for r in self.ranks if r != R1]
            # Choose 4 distinct kicker ranks
            for kicker_ranks in itertools.combinations(remaining_ranks, 4):
                # Sort kickers in descending order (e.g., K, Q, J, T)
                K1, K2, K3, K4 = sorted(kicker_ranks, key=lambda x: self.ranks.index(x))
                added_hand = False                                                                              
                # Assign suits to three-of-a-kind
                for r1_suits in itertools.combinations(self.suits, 3):
                    r1_cards = [R1 + s for s in r1_suits]
                    # Assign suits to kickers
                    for kicker_suits in itertools.product(self.suits, repeat=4):
                        kicker_cards = [K1 + kicker_suits[0], K2 + kicker_suits[1], 
                                    K3 + kicker_suits[2], K4 + kicker_suits[3]]
                        hand = r1_cards + kicker_cards
                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                        encoded = self.encode_hand(hand)
                        if encoded not in self.existing_hands:
                            self.buffer.append((hand, 17, ordered_rank))
                            self.existing_hands.add(encoded)
                            added_hand = True       
                            total_hands += 1
                            if len(self.buffer) >= self.buffer_size:
                                self.write_buffer(output_file)                                                     
                if added_hand:
                    ordered_rank += 1  # Increment after each (R1, K1, K2, K3, K4)   

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                         

    def generate_two_pairs(self, output_file):
        """Generate all Two Pair hands (Rank 18): Two pairs with three kickers.
        
        Memory-optimized version that processes combinations in batches.
        """
        total_hands = 0
        ordered_rank = 1
        
        # Process pair combinations in batches
        for pair_batch in self._batch_combinations(self.ranks, 2, 50):
            print(f"  Processing batch of {len(pair_batch)} pair combinations...")
            
            for pair_ranks in pair_batch:
                # Sort pairs: P1 > P2
                P1, P2 = sorted(pair_ranks, key=lambda x: self.ranks.index(x))
                
                # Get kicker candidates (exclude pair ranks)
                kicker_candidates = [r for r in self.ranks if r not in (P1, P2)]
                
                # Process kicker combinations in batches
                for kicker_batch in self._batch_combinations(kicker_candidates, 3, 100):
                    for kicker_ranks in kicker_batch:
                        # Sort kickers: K1 > K2 > K3
                        K1, K2, K3 = sorted(kicker_ranks, key=lambda x: self.ranks.index(x))
                        
                        added_hand = False
                        
                        # Process pair suit combinations with early filtering
                        for p1_suits in itertools.combinations(self.suits, 2):
                            p1_cards = [P1 + s for s in p1_suits]
                            
                            for p2_suits in itertools.combinations(self.suits, 2):
                                p2_cards = [P2 + s for s in p2_suits]
                                
                                # Process kicker suit combinations in batches
                                for k_suits in self._batch_product(self.suits, 3, 100):
                                    for kicker_suits in k_suits:
                                        kicker_cards = [
                                            K1 + kicker_suits[0], 
                                            K2 + kicker_suits[1], 
                                            K3 + kicker_suits[2]
                                        ]
                                        
                                        # Create the complete hand
                                        hand = p1_cards + p2_cards + kicker_cards
                                        hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                        
                                        # Encode and check if hand exists
                                        encoded = self.encode_hand(hand)
                                        if encoded not in self.existing_hands:
                                            self.buffer.append((hand, 18, ordered_rank))
                                            self.existing_hands.add(encoded)
                                            added_hand = True
                                            total_hands += 1
                                    
                                    # Flush buffer if it's full
                                    if len(self.buffer) >= self.buffer_size:
                                        self.write_buffer(output_file)
                                        # Force garbage collection
                                        gc.collect()
                        
                        # Increment ordered rank if any hands were added for this combination
                        if added_hand:
                            ordered_rank += 1
                            # Write any remaining hands for this ordered rank
                            if self.buffer:
                                self.write_buffer(output_file)
                    
                    # Clear batch memory
                    kicker_batch = None
                    gc.collect()
            
            # Clear batch memory
            pair_batch = None
            gc.collect()
            
            # Log memory usage periodically
            print(f"    Memory usage: {psutil.Process().memory_info().rss / 1024 ** 2:.2f} MB")
        
        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                         

    def generate_one_pairs(self, output_file):
        """Memory-optimized version of one pair generation."""
        total_hands = 0
        ordered_rank = 1
        
        for P1 in self.ranks:  # Pair rank
            print(f"  Generating One Pair hands for rank: {P1}")
            kicker_candidates = [r for r in self.ranks if r != P1]
            
            # Process each pair suit combination separately
            for p1_suits in itertools.combinations(self.suits, 2):
                p1_cards = [P1 + s for s in p1_suits]
                
                # Process kicker combinations in smaller batches
                for kicker_batch in self._batch_combinations(kicker_candidates, 5, 1000):
                    for kicker_ranks in kicker_batch:
                        K1, K2, K3, K4, K5 = sorted(kicker_ranks, key=lambda x: self.ranks.index(x))
                        
                        # Process kicker suits in smaller chunks
                        for k_suits in self._batch_product(self.suits, 5, 100):
                            for k1_suit, k2_suit, k3_suit, k4_suit, k5_suit in k_suits:
                                kicker_cards = [
                                    K1 + k1_suit, K2 + k2_suit, 
                                    K3 + k3_suit, K4 + k4_suit, K5 + k5_suit
                                ]
                                
                                hand = p1_cards + kicker_cards
                                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                                
                                encoded = self.encode_hand(hand)
                                if encoded not in self.existing_hands:
                                    self.buffer.append((hand, 19, ordered_rank))
                                    self.existing_hands.add(encoded)
                                    total_hands += 1
                            
                            # Write buffer if it's full
                            if len(self.buffer) >= self.buffer_size:
                                self.write_buffer(output_file)
                                # Force garbage collection
                                gc.collect()
                    
                    # Clear batch memory
                    kicker_batch = None
                    gc.collect()
                
                # Increment ordered rank
                if self.buffer:  # Only increment if hands were added
                    ordered_rank += 1
                    # Write any remaining hands
                    self.write_buffer(output_file)
            
            # Print memory usage after each pair rank
            print(f"    Memory usage: {psutil.Process().memory_info().rss / 1024 ** 2:.2f} MB")
            # Force garbage collection
            gc.collect()
        
        return total_hands                         

    def generate_high_cards(self, output_file):
        """Generate all High Card hands (Rank 20): Seven distinct ranks, no straights or flushes."""
        ordered_rank = 1
        total_hands = 0

        # Choose 7 distinct ranks
        for ranks in itertools.combinations(self.ranks, 7):
            # Sort ranks in descending order for strength
            sorted_ranks = sorted(ranks, key=lambda x: self.ranks.index(x))
            added_hand = False
            # Assign suits to all 7 cards
            for suit_assignment in itertools.product(self.suits, repeat=7):
                hand = [sorted_ranks[i] + suit_assignment[i] for i in range(7)]
                hand.sort(key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))
                encoded = self.encode_hand(hand)
                if encoded not in self.existing_hands:
                    self.buffer.append((hand, 20, ordered_rank))
                    # No need to add to self.existing_hands since this is the last rank
                    added_hand = True
                    total_hands += 1
                    if len(self.buffer) >= self.buffer_size:
                        self.write_buffer(output_file)                    
            if added_hand:
                ordered_rank += 1  # Increment only if a hand was added        

        # Write any remaining hands
        if self.buffer:
            self.write_buffer(output_file)
        
        return total_hands                   

    def _batch_combinations(self, items, r, batch_size=1000):
        """Process combinations in batches to avoid memory issues."""
        batch = []
        for combo in itertools.combinations(items, r):
            batch.append(combo)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        if batch:
            yield batch
    
    def _batch_product(self, items, repeat, batch_size=1000):
        """Process product in batches to avoid memory issues."""
        batch = []
        for combo in itertools.product(items, repeat=repeat):
            batch.append(combo)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        if batch:
            yield batch                                           
        
    def save_hands_to_file(self, filename, append=False):
        """Save hands to a CSV file, optionally appending."""
        mode = 'a' if append else 'w'
        with open(filename, mode) as f:
            if not append:  # Write header only on first call
                f.write('Hand,Rank,OrderedRank\n')
            for hand, rank, ordered_rank in self.all_hands:
                hand_str = ','.join(hand)
                f.write(f'{hand_str},{rank},{ordered_rank}\n')                

# Update main block
if __name__ == "__main__":
    evaluator = PokerHandEvaluator()
    total_hands = evaluator.generate_hands()
    print(f"Total hands generated: {total_hands}")
