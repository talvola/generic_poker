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
