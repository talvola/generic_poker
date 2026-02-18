"""Constants for poker hand evaluation - now loaded from JSON configurations."""

import logging

from generic_poker.core.card import Suit

logger = logging.getLogger(__name__)

# Suit ordering used in many poker variants
# Particularly important for stud games where suit order determines bring-in
SUIT_ORDER = {
    Suit.SPADES: 0,
    Suit.HEARTS: 1,
    Suit.DIAMONDS: 2,
    Suit.CLUBS: 3,
    Suit.JOKER: 4,  # Keep joker at end
}

# Standard rank ordering (A high)
BASE_RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]

# A-5 Low rank ordering (A is low, high cards left)
LOW_A5_RANKS = ["K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2", "A"]
LOW_A6_RANKS = ["K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2", "A"]

# Badugi
BADUGI_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"]

# Short decks
RANKS_36_CARD = ["A", "K", "Q", "J", "T", "9", "8", "7", "6"]
RANKS_20_CARD = ["A", "K", "Q", "J", "T"]

RANKS_27_JA = ["A", "K", "Q", "J", "7", "6", "5", "4", "3", "2"]
RANKS_27_JA_JOKER = ["R", "A", "K", "Q", "J", "7", "6", "5", "4", "3", "2"]

# Special for 6-card low pip count games
BASE_RANKS_PADDED = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2", "X"]

# Put Joker at the beginning
BASE_RANKS_JOKER = ["R", "A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
LOW_A5_RANKS_JOKER = ["R", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2", "A"]

# Mapping from rank order names to actual rank lists
RANK_ORDER_MAP = {
    "BASE_RANKS": BASE_RANKS,
    "LOW_A5_RANKS": LOW_A5_RANKS,
    "LOW_A6_RANKS": LOW_A6_RANKS,
    "BADUGI_RANKS": BADUGI_RANKS,
    "RANKS_36_CARD": RANKS_36_CARD,
    "RANKS_20_CARD": RANKS_20_CARD,
    "RANKS_27_JA": RANKS_27_JA,
    "RANKS_27_JA_JOKER": RANKS_27_JA_JOKER,
    "BASE_RANKS_PADDED": BASE_RANKS_PADDED,
    "BASE_RANKS_JOKER": BASE_RANKS_JOKER,
    "LOW_A5_RANKS_JOKER": LOW_A5_RANKS_JOKER,
}

# These will be built dynamically from JSON configurations
_RANK_ORDERS: dict[str, list] = {}
_HAND_SIZES: dict[str, int] = {}
_PADDED_TYPES: set[str] = set()
_RANK_ONLY_TYPES: set[str] = set()
_EVAL_TYPES_BY_SIZE: dict[int, set[str]] = {}


def _build_constants_from_config():
    """Build the constants dictionaries from JSON configurations."""
    global _RANK_ORDERS, _HAND_SIZES, _PADDED_TYPES, _RANK_ONLY_TYPES, _EVAL_TYPES_BY_SIZE

    try:
        from generic_poker.evaluation.evaluation_config import evaluation_config_loader

        # Load all configurations
        evaluation_config_loader.load_all_configs()
        configs = evaluation_config_loader.get_all_configs()

        logger.info(f"Building constants from {len(configs)} evaluation configurations")

        # Build RANK_ORDERS dictionary
        for eval_type, config in configs.items():
            rank_order_name = config.rank_order
            if rank_order_name in RANK_ORDER_MAP:
                _RANK_ORDERS[eval_type] = RANK_ORDER_MAP[rank_order_name]
            else:
                logger.warning(f"Unknown rank order '{rank_order_name}' for {eval_type}, using BASE_RANKS")
                _RANK_ORDERS[eval_type] = BASE_RANKS

        # Build HAND_SIZES dictionary
        for eval_type, config in configs.items():
            _HAND_SIZES[eval_type] = config.hand_size

        # Build EVAL_TYPES_BY_SIZE
        for eval_type, hand_size in _HAND_SIZES.items():
            if hand_size not in _EVAL_TYPES_BY_SIZE:
                _EVAL_TYPES_BY_SIZE[hand_size] = set()
            _EVAL_TYPES_BY_SIZE[hand_size].add(eval_type)

        # Build PADDED_TYPES (types that require padding)
        for eval_type, config in configs.items():
            if "PADDED" in config.rank_order:
                _PADDED_TYPES.add(eval_type)

        # Build RANK_ONLY_TYPES (pip count games)
        pip_games = {
            "49",
            "58",
            "6",
            "zero",
            "zero_6",
            "21",
            "21_6",
            "low_pip_6_cards",
            "football",
            "six_card_football",
            "seven_card_football",
        }
        for eval_type in configs:
            if eval_type in pip_games:
                _RANK_ONLY_TYPES.add(eval_type)

        logger.info("Successfully built constants from JSON configurations")

    except Exception as e:
        logger.error(f"Failed to build constants from JSON configurations: {e}")
        logger.warning("Falling back to hardcoded constants")
        _build_fallback_constants()


def _build_fallback_constants():
    """Build fallback constants in case JSON loading fails."""
    global _RANK_ORDERS, _HAND_SIZES, _PADDED_TYPES, _RANK_ONLY_TYPES, _EVAL_TYPES_BY_SIZE

    # Fallback to original hardcoded mappings
    _RANK_ORDERS = {
        "high": BASE_RANKS,
        "high_wild_bug": BASE_RANKS_JOKER,
        "soko_high": BASE_RANKS,
        "ne_seven_card_high": BASE_RANKS,
        "quick_quads": BASE_RANKS,
        "27_low": BASE_RANKS,
        "27_low_wild": BASE_RANKS_JOKER,
        "49": BASE_RANKS,
        "6": BASE_RANKS,
        "zero": BASE_RANKS,
        "21": BASE_RANKS,
        "58": BASE_RANKS,
        "zero_6": BASE_RANKS,
        "21_6": BASE_RANKS,
        "football": BASE_RANKS,
        "six_card_football": BASE_RANKS,
        "seven_card_football": BASE_RANKS,
        "hidugi": BASE_RANKS,
        "36card_ffh_high": RANKS_36_CARD,
        "20card_high": RANKS_20_CARD,
        "27_ja_ffh_high": RANKS_27_JA,
        "27_ja_ffh_high_wild_bug": RANKS_27_JA_JOKER,
        "a5_low": LOW_A5_RANKS,
        "a5_low_high": LOW_A5_RANKS,
        "a5_low_wild": LOW_A5_RANKS_JOKER,
        "a6_low": LOW_A6_RANKS,
        "badugi": BADUGI_RANKS,
        "low_pip_6_cards": BASE_RANKS_PADDED,
        # Add more fallbacks as needed...
    }

    _HAND_SIZES = {
        "high": 5,
        "a5_low": 5,
        "a5_low_wild": 5,
        "a6_low": 5,
        "27_low": 5,
        "27_low_wild": 5,
        "a5_low_high": 5,
        "36card_ffh_high": 5,
        "20card_high": 5,
        "27_ja_ffh_high": 5,
        "27_ja_ffh_high_wild_bug": 5,
        "quick_quads": 5,
        "49": 5,
        "6": 5,
        "zero": 5,
        "21": 5,
        "football": 5,
        "six_card_football": 6,
        "seven_card_football": 7,
        "high_wild_bug": 5,
        "badugi": 4,
        "badugi_ah": 4,
        "hidugi": 4,
        # Add more fallbacks as needed...
    }

    _PADDED_TYPES = {"low_pip_6_cards"}
    _RANK_ONLY_TYPES = {
        "49",
        "zero",
        "6",
        "21",
        "low_pip_6_cards",
        "58",
        "21_6",
        "zero_6",
        "football",
        "six_card_football",
        "seven_card_football",
    }

    _EVAL_TYPES_BY_SIZE = {
        size: {eval_type for eval_type, req_size in _HAND_SIZES.items() if req_size == size}
        for size in set(_HAND_SIZES.values())
    }


# Build the constants when the module is imported
_build_constants_from_config()


# Expose the dynamically built constants
@property
def RANK_ORDERS() -> dict[str, list]:
    """Get the rank orders dictionary."""
    return _RANK_ORDERS


@property
def HAND_SIZES() -> dict[str, int]:
    """Get the hand sizes dictionary."""
    return _HAND_SIZES


@property
def PADDED_TYPES() -> set[str]:
    """Get the set of evaluation types that require padding."""
    return _PADDED_TYPES


@property
def RANK_ONLY_TYPES() -> set[str]:
    """Get the set of evaluation types that only use rank."""
    return _RANK_ONLY_TYPES


@property
def EVAL_TYPES_BY_SIZE() -> dict[int, set[str]]:
    """Get evaluation types organized by hand size."""
    return _EVAL_TYPES_BY_SIZE


# For backward compatibility, also expose as module-level attributes
# (This allows existing code to continue working)
def _update_module_globals():
    """Update module global variables for backward compatibility."""
    import sys

    module = sys.modules[__name__]
    module.RANK_ORDERS = _RANK_ORDERS
    module.HAND_SIZES = _HAND_SIZES
    module.PADDED_TYPES = _PADDED_TYPES
    module.RANK_ONLY_TYPES = _RANK_ONLY_TYPES
    module.EVAL_TYPES_BY_SIZE = _EVAL_TYPES_BY_SIZE


_update_module_globals()
