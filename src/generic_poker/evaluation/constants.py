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

# Badugi 
BADUGI_RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K']

# Short decks
RANKS_36_CARD = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6']
RANKS_20_CARD = ['A', 'K', 'Q', 'J', 'T']

# Special for 6-card low pip count games
BASE_RANKS_PADDED = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2', 'X']

# Map evaluation types to rank orderings
RANK_ORDERS = {
    # High hand games use base ordering
    'high': BASE_RANKS,
    'high_wild': BASE_RANKS,
    # 2-7 Lowball can use same ranks
    '27_low': BASE_RANKS,
    # Pip games can also use the same ranks
    '49': BASE_RANKS,
    '6': BASE_RANKS,
    'zero': BASE_RANKS,
    '21': BASE_RANKS,
    '58': BASE_RANKS,
    'zero_6': BASE_RANKS,
    '21_6': BASE_RANKS,
    # Hi-Dugi can use standard ranks
    'hidugi': BASE_RANKS,

    # 36-card deck
    '36card_ffh_high': RANKS_36_CARD,
    # 20-card deck
    '20card_high': RANKS_20_CARD,
    
    # A-5 Lowball games always have Ace low
    'a5_low': LOW_A5_RANKS,
    'a5_low_high': LOW_A5_RANKS,

    # Badugi
    'badugi': BADUGI_RANKS,
    
    # 6-card low pip count
    'low_pip_6_cards': BASE_RANKS_PADDED

    # leaving out the stud bring-in hands for now, such as two_card_high, etc.
}

# Mapping of evaluation types to required hand sizes
HAND_SIZES = {
    'high': 5,
    'a5_low': 5,
    '27_low': 5,
    'a5_low_high': 5,
    '36card_ffh_high': 5,
    '20card_high': 5,
    '49': 5,
    '6': 5,
    'zero': 5,
    '21': 5,
    'high_wild': 5,
    'badugi': 4,
    'badugi_ah': 4,
    'hidugi': 4,
    'four_card_high': 4,
    'four_card_low': 4,
    'four_card_high_al': 4,
    'four_card_low_ah': 4,
    'four_card_high_al_rh': 4,
    'three_card_high': 3,
    'three_card_low': 3,
    'three_card_high_al': 3,
    'three_card_low_ah': 3,
    'three_card_high_al_rh': 3,
    'two_card_high': 2,
    'two_card_low': 2,
    'two_card_high_al': 2,
    'two_card_low_ah': 2,
    'two_card_high_al_rh': 2,
    'one_card_high': 1,
    'one_card_low': 1,
    'one_card_high_ah': 1,
    'one_card_low_al': 1,
    'low_pip_6_cards': 6,
    '58': 6,
    'zero_6': 6,
    '21_6': 6
}

# Alternative organization by size
EVAL_TYPES_BY_SIZE = {
    size: {eval_type for eval_type, req_size in HAND_SIZES.items() if req_size == size}
    for size in set(HAND_SIZES.values())
}

# Which evaluation types only use rank (no suits)
RANK_ONLY_TYPES = {'49', 'zero', '6', '21', 'low_pip_6_cards', '58', '21_6', 'zero_6'}
