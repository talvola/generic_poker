class MissingHandsClassifier:
    def __init__(self):
        self.ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        self.suits = ['s', 'h', 'd', 'c']
        # Map rank to index for Ace-low straights
        self.rank_to_value = {r: i for i, r in enumerate(self.ranks)}
        self.rank_to_value['A'] = 13  # For Ace-low straights
        self.hand_counts = {i: 0 for i in range(1, 21)}  # To count hands per rank

    def get_rank_counts(self, hand):
        """Count how many cards of each rank are in the hand."""
        rank_counts = {r: 0 for r in self.ranks}
        for card in hand:
            rank = card[0]
            rank_counts[rank] += 1
        return rank_counts

    def get_suit_counts(self, hand):
        """Count how many cards of each suit are in the hand."""
        suit_counts = {s: 0 for s in self.suits}
        for card in hand:
            suit = card[1]
            suit_counts[suit] += 1
        return suit_counts

    def is_straight(self, hand, length):
        """Check if the hand contains a straight of given length."""
        rank_values = sorted([self.rank_to_value[card[0]] for card in hand])
        # Check regular straights
        for i in range(len(rank_values) - length + 1):
            if all(rank_values[i + j] == rank_values[i] + j for j in range(length)):
                return True
        # Check Ace-low straight (A-2-3-... or 2-3-4-...)
        ace_low = [self.rank_to_value[card[0]] for card in hand]
        ace_low = sorted([v if v < 13 else 0 for v in ace_low])  # Treat A as 0 for Ace-low
        for i in range(len(ace_low) - length + 1):
            if all(ace_low[i + j] == ace_low[i] + j for j in range(length)):
                return True
        return False

    def is_flush(self, hand, length):
        """Check if the hand contains a flush of given length."""
        suit_counts = self.get_suit_counts(hand)
        return any(count >= length for count in suit_counts.values())

    def classify_hand(self, hand):
        """Classify the hand according to the 20 ranks."""
        rank_counts = self.get_rank_counts(hand)
        suit_counts = self.get_suit_counts(hand)
        rank_freq = sorted([count for count in rank_counts.values() if count > 0], reverse=True)
        max_suit = max(suit_counts.values())

        # Rank 1: Grand Straight Flush (7 cards, straight, flush)
        if max_suit == 7 and self.is_straight(hand, 7):
            return 1

        # Rank 2: Palace (1 Quad, 1 Trip)
        if rank_freq == [4, 3]:
            return 2

        # Rank 3: Long Straight Flush (6 cards straight flush + 1 kicker)
        if self.is_flush(hand, 6) and self.is_straight(hand, 6):
            return 3

        # Rank 4: Grand Flush (7 cards flush, not straight)
        if max_suit == 7 and not self.is_straight(hand, 7):
            return 4

        # Rank 5: Mansion (1 Quad, 1 Pair, 1 Kicker)
        if rank_freq == [4, 2, 1]:
            return 5

        # Rank 6: Straight Flush (5 cards straight flush + 2 kickers)
        if self.is_flush(hand, 5) and self.is_straight(hand, 5):
            return 6

        # Rank 7: Hotel (2 Trips, 1 Kicker)
        if rank_freq == [3, 3, 1]:
            return 7

        # Rank 8: Villa (1 Trip, 2 Pairs)
        if rank_freq == [3, 2, 2]:
            return 8

        # Rank 9: Grand Straight (7 cards straight, not flush)
        if self.is_straight(hand, 7) and max_suit < 7:
            return 9

        # Rank 10: Four of a Kind (1 Quad, 3 Kickers)
        if rank_freq == [4, 1, 1, 1]:
            return 10

        # Rank 11: Long Flush (6 cards flush + 1 kicker, not straight)
        if max_suit == 6 and not self.is_straight(hand, 6):
            return 11

        # Rank 12: Long Straight (6 cards straight + 1 kicker, not flush)
        if self.is_straight(hand, 6) and not self.is_flush(hand, 6):
            return 12

        # Rank 13: Three Pair (3 Pairs, 1 Kicker)
        if rank_freq == [2, 2, 2, 1]:
            return 13

        # Rank 14: Full House (1 Trip, 1 Pair, 2 Kickers)
        if rank_freq == [3, 2, 1, 1]:
            return 14

        # Rank 15: Flush (5 cards flush + 2 kickers, not straight)
        if max_suit == 5 and not self.is_straight(hand, 5):
            return 15

        # Rank 16: Straight (5 cards straight + 2 kickers, not flush)
        if self.is_straight(hand, 5) and not self.is_flush(hand, 5):
            return 16

        # Rank 17: Three of a Kind (1 Trip, 4 Kickers)
        if rank_freq == [3, 1, 1, 1, 1]:
            return 17

        # Rank 18: Two Pair (2 Pairs, 3 Kickers)
        if rank_freq == [2, 2, 1, 1, 1]:
            return 18

        # Rank 19: One Pair (1 Pair, 5 Kickers)
        if rank_freq == [2, 1, 1, 1, 1, 1]:
            return 19

        # Rank 20: High Card (7 distinct ranks, no straight, no flush)
        if rank_freq == [1, 1, 1, 1, 1, 1, 1] and not self.is_straight(hand, 5) and max_suit < 5:
            return 20

        raise ValueError(f"Hand {hand} does not match any rank!")

    def classify_missing_hands(self):
        """Read missing_hands.txt and classify each hand."""
        print("Classifying missing hands...")
        with open("missing_hands.txt", 'r') as f:
            for line in f:
                hand = line.strip().split(',')
                rank = self.classify_hand(hand)
                self.hand_counts[rank] += 1

        # Print results
        print("Missing hands by rank:")
        total_missing = 0
        for rank in range(1, 21):
            count = self.hand_counts[rank]
            if count > 0:
                print(f"Rank {rank}: {count} hands")
            total_missing += count
        print(f"Total missing hands: {total_missing}")

if __name__ == "__main__":
    classifier = MissingHandsClassifier()
    classifier.classify_missing_hands()
