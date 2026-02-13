import itertools
import gc

class AllHandsGenerator:
    def __init__(self):
        self.ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        self.suits = ['s', 'h', 'd', 'c']
        self.cards = [r + s for r in self.ranks for s in self.suits]  # All 52 cards
        self.buffer = []
        self.buffer_size = 50000  # Buffer to reduce I/O operations
        self.output_file = "all_7_card_hands.txt"

    def sort_hand(self, hand):
        """Sort hand by rank (A to 2) and suit (s, h, d, c) within same rank."""
        return sorted(hand, key=lambda x: (self.ranks.index(x[0]), self.suits.index(x[1])))

    def write_buffer(self):
        """Write sorted buffer to file and clear it."""
        if not self.buffer:
            return
        # Sort the buffer to ensure lexicographical order
        self.buffer.sort()
        with open(self.output_file, 'a') as f:
            for hand in self.buffer:
                f.write(f"{','.join(hand)}\n")
        self.buffer.clear()
        gc.collect()

    def generate_all_hands(self):
        print("Generating all 7-card hands...")
        all_hands = []
        total_hands = 0
        for hand in itertools.combinations(self.cards, 7):
            sorted_hand = self.sort_hand(hand)
            all_hands.append(sorted_hand)
            total_hands += 1
            if len(all_hands) % 50000 == 0:
                print(f"Processed {total_hands} hands...")

        print("Sorting all hands...")
        all_hands.sort()

        print("Writing to file...")
        with open(self.output_file, 'w') as f:
            for hand in all_hands:
                f.write(f"{','.join(hand)}\n")

        print(f"Total hands generated: {total_hands}")
        return total_hands

if __name__ == "__main__":
    generator = AllHandsGenerator()
    total_hands = generator.generate_all_hands()
