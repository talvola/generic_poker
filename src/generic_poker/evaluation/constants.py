"""Constants for poker hand evaluation."""
from generic_poker.core.card import Suit

# Suit ordering used in many poker variants
# Particularly important for stud games where suit order determines bring-in
SUIT_ORDER = {
    Suit.SPADES: 0,
    Suit.HEARTS: 1,
    Suit.DIAMONDS: 2,
    Suit.CLUBS: 3,
    Suit.JOKER: 4  # Keep joker at end
}

# Standard rank ordering (A high)
BASE_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

# A-5 Low rank ordering (A is low, high cards left)
LOW_A5_RANKS = ['K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'A']
LOW_A6_RANKS = ['K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'A']

# Badugi 
BADUGI_RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K']

# Short decks
RANKS_36_CARD = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6']
RANKS_20_CARD = ['A', 'K', 'Q', 'J', 'T']

RANKS_27_JA = ['A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']
RANKS_27_JA_JOKER = ['R', 'A', 'K', 'Q', 'J', '7', '6', '5', '4', '3', '2']

# Special for 6-card low pip count games
BASE_RANKS_PADDED = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'X']

# Put Joker at the beginning
BASE_RANKS_JOKER = ['R', 'A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
LOW_A5_RANKS_JOKER = ['R', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'A']

# Map evaluation types to rank orderings
RANK_ORDERS = {
    # High hand games use base ordering
    'high': BASE_RANKS,
    'high_wild_bug': BASE_RANKS_JOKER,
    'soko_high': BASE_RANKS,
    'ne_seven_card_high': BASE_RANKS,
    'quick_quads': BASE_RANKS,
    # 2-7 Lowball can use same ranks
    '27_low': BASE_RANKS,
    '27_low_wild': BASE_RANKS_JOKER,
    # Pip games can also use the same ranks
    '49': BASE_RANKS,
    '6': BASE_RANKS,
    'zero': BASE_RANKS,
    '21': BASE_RANKS,
    '58': BASE_RANKS,
    'zero_6': BASE_RANKS,
    '21_6': BASE_RANKS,
    'football': BASE_RANKS,
    'six_card_football': BASE_RANKS,
    'seven_card_football': BASE_RANKS,
    # Hi-Dugi can use standard ranks
    'hidugi': BASE_RANKS,

    # 36-card deck
    '36card_ffh_high': RANKS_36_CARD,
    # 20-card deck
    '20card_high': RANKS_20_CARD,
    # 40-card deck 
    '27_ja_ffh_high': RANKS_27_JA,
    '27_ja_ffh_high_wild_bug': RANKS_27_JA_JOKER,
    
    # A-5 Lowball games always have Ace low
    'a5_low': LOW_A5_RANKS,
    'a5_low_high': LOW_A5_RANKS,
    'a5_low_wild': LOW_A5_RANKS_JOKER,
    'a6_low': LOW_A6_RANKS,

    # Badugi
    'badugi': BADUGI_RANKS,
    
    # 6-card low pip count
    'low_pip_6_cards': BASE_RANKS_PADDED,

    # stud bring-in hands, such as two_card_high, etc.
    'one_card_low': LOW_A5_RANKS,
    'two_card_a5_low': LOW_A5_RANKS,
    'three_card_a5_low': LOW_A5_RANKS,
    'four_card_a5_low': LOW_A5_RANKS,
    'one_card_low_al': LOW_A5_RANKS,
    'two_card_high_al': LOW_A5_RANKS,
    'three_card_high_al': LOW_A5_RANKS,
    'four_card_high_al': LOW_A5_RANKS,
    # special evaluation types for Razz High
    'two_card_a5_low_high': LOW_A5_RANKS,
    'three_card_a5_low_high': LOW_A5_RANKS,
    'four_card_a5_low_high': LOW_A5_RANKS,

    'one_card_high': BASE_RANKS,
    'two_card_high': BASE_RANKS,
    'three_card_high': BASE_RANKS,
    'four_card_high': BASE_RANKS,
    'one_card_high_ah': BASE_RANKS,
    'two_card_27_low': BASE_RANKS,
    'three_card_27_low': BASE_RANKS,
    'four_card_27_low': BASE_RANKS,

    # 40-card (no 8-T) card Stud evaluations
    'two_card_27_ja_ffh_high': RANKS_27_JA,
    'three_card_27_ja_ffh_high': RANKS_27_JA,
    'four_card_27_ja_ffh_high': RANKS_27_JA,
    'two_card_27_ja_ffh_high_wild_bug': RANKS_27_JA_JOKER,
    'three_card_27_ja_ffh_high_wild_bug': RANKS_27_JA_JOKER,
    'four_card_27_ja_ffh_high_wild_bug': RANKS_27_JA_JOKER,

    'one_card_high_ah_wild_bug': BASE_RANKS_JOKER,

    # wild hole card 
    'one_card_high_spade': BASE_RANKS,
    'one_card_high_heart': BASE_RANKS,
    'one_card_high_diamond': BASE_RANKS,
    'one_card_high_club': BASE_RANKS,
    'one_card_low_spade': BASE_RANKS,
    'one_card_low_heart': BASE_RANKS,
    'one_card_low_diamond': BASE_RANKS,
    'one_card_low_club': BASE_RANKS,    
    'three_card_high_spade': BASE_RANKS,
    'three_card_high_heart': BASE_RANKS,
    'three_card_high_diamond': BASE_RANKS,
    'three_card_high_club': BASE_RANKS
}

# Mapping of evaluation types to required hand sizes
HAND_SIZES = {
    'high': 5,
    'a5_low': 5,
    'a5_low_wild': 5,
    'a6_low': 5,
    '27_low': 5,
    '27_low_wild': 5,
    'a5_low_high': 5,
    '36card_ffh_high': 5,
    '20card_high': 5,
    '27_ja_ffh_high': 5,
    '27_ja_ffh_high_wild_bug': 5,
    'quick_quads': 5,
    '49': 5,
    '6': 5,
    'zero': 5,
    '21': 5,
    'football': 5,
    'six_card_football': 6,
    'seven_card_football': 7,
    'high_wild_bug': 5,
    'badugi': 4,
    'badugi_ah': 4,
    'hidugi': 4,
    'four_card_high': 4,
    'four_card_a5_low': 4,
    'four_card_high_al': 4,
    'four_card_27_low': 4,
    'four_card_a5_low_high': 4,
    'three_card_high': 3,
    'three_card_a5_low': 3,
    'three_card_high_al': 3,
    'three_card_27_low': 3,
    'three_card_a5_low_high': 3,
    'two_card_high': 2,
    'two_card_a5_low': 2,
    'two_card_high_al': 2,
    'two_card_27_low': 2,
    'two_card_a5_low_high': 2,
    'one_card_high': 1,
    'one_card_low': 1,
    'one_card_high_ah': 1,
    'one_card_low_al': 1,
    'two_card_27_ja_ffh_high': 2,
    'three_card_27_ja_ffh_high': 3,
    'four_card_27_ja_ffh_high': 4,
    'two_card_27_ja_ffh_high_wild_bug': 2,
    'three_card_27_ja_ffh_high_wild_bug': 3,
    'four_card_27_ja_ffh_high_wild_bug': 4,    
    'one_card_high_ah_wild_bug': 1,
    'low_pip_6_cards': 6,
    '58': 6,
    'zero_6': 6,
    '21_6': 6,
    'soko_high': 5,
    'ne_seven_card_high': 7,
    'three_card_high_spade': 3,
    'three_card_high_heart': 3,
    'three_card_high_diamond': 3,
    'three_card_high_club': 3,
    'one_card_high_spade': 1,
    'one_card_high_heart': 1,
    'one_card_high_diamond': 1,
    'one_card_high_club': 1,
    'one_card_low_spade': 1,
    'one_card_low_heart': 1,
    'one_card_low_diamond': 1,
    'one_card_low_club': 1 
}

# evaluation types which require padding to evaluate
PADDED_TYPES = {'low_pip_6_cards'}

# Alternative organization by size
EVAL_TYPES_BY_SIZE = {
    size: {eval_type for eval_type, req_size in HAND_SIZES.items() if req_size == size}
    for size in set(HAND_SIZES.values())
}

# Which evaluation types only use rank (no suits)
RANK_ONLY_TYPES = {'49', 'zero', '6', '21', 'low_pip_6_cards', '58', '21_6', 'zero_6', 'football', 'six_card_football', 'seven_card_football'}


