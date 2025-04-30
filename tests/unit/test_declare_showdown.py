import pytest
from generic_poker.game.game import Game
from generic_poker.config.loader import BettingStructure
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.game_state import PlayerAction
from generic_poker.game.action_result import ActionResult

from tests.test_helpers import load_rules_from_file

import logging
import sys

@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for all tests."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )



# Helper function to create cards from shorthand (e.g., "KQJT9")
def parse_cards(card_str: str) -> list[Card]:
    rank_map = {
        'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN, 'J': Rank.JACK, 'T': Rank.TEN,
        '9': Rank.NINE, '8': Rank.EIGHT, '7': Rank.SEVEN, '6': Rank.SIX, '5': Rank.FIVE,
        '4': Rank.FOUR, '3': Rank.THREE, '2': Rank.TWO
    }
    suits = [Suit.SPADES, Suit.HEARTS, Suit.CLUBS, Suit.DIAMONDS]  # Cycle through suits
    cards = []
    for i, char in enumerate(card_str):
        if char in rank_map:
            cards.append(Card(rank_map[char], suits[i % 4]))
    return cards

# Helper function to set up game and run to showdown
def setup_game_to_showdown(players_cards: dict, declarations: dict):
    rules = load_rules_from_file('straight_7card_declare')
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        auto_progress=False
    )
    # Add players
    for pos, (name, cards) in players_cards.items():
        game.add_player(pos, name, 500)
    
    # Calculate expected pot size
    num_players = len(players_cards)
    pot_size = num_players * 10  # Each player contributes $10
    
    # Start hand and progress through steps
    game.start_hand()
    assert game.current_step == 0  # Post Blinds
    game._next_step()  # Deal cards
    assert game.current_step == 1
    
    # Set cards
    for pos, (name, cards) in players_cards.items():
        player = game.table.players[pos]
        player.hand.clear()
        player.hand.add_cards(cards)
    
    game._next_step()  # Initial Bet
    assert game.current_step == 2
    # Simulate betting (contribute to pot)
    for pos in players_cards:
        game.player_action(pos, PlayerAction.CALL, 10)
    
    game._next_step()  # Declare
    assert game.current_step == 3
    
    # Get player order (starts left of dealer, e.g., P2, P3, P1)
    active_players = game.table.get_active_players()
    player_order = [p.id for p in active_players]
    # Rotate to start with current_player (set by next_player(round_start=True))
    current_player_idx = player_order.index(game.current_player.id)
    player_order = player_order[current_player_idx:] + player_order[:current_player_idx]
    
    # Set declarations in turn order
    for player_id in player_order:
        if player_id in declarations:
            player = game.table.players[player_id]
            declaration_data = [{"pot_index": -1, "declaration": declarations[player_id]}]
            result = game.player_action(player.id, PlayerAction.DECLARE, declaration_data=declaration_data)
            assert result.success, f"Failed to set declaration for {player.name}: {result.error}"
    
    game._next_step()  # Showdown (processes showdown automatically)
    assert game.current_step == 4
    
    return game, pot_size

# Fixture for common game setup
@pytest.fixture
def game_setup():
    return lambda players_cards, declarations: setup_game_to_showdown(players_cards, declarations)

# Parametrized test for Conjelco test cases
@pytest.mark.parametrize("test_case,players_cards,declarations,expected", [
    # Test Case 1: A: high (KQJT9), B: low (8532A)
    (
        1,
        {
            "P1": ("Alice", parse_cards("KQJT9")),
            "P2": ("Bob", parse_cards("8532A"))
        },
        {"P1": "high", "P2": "low"},
        {
            "high_winners": ["P1"],
            "low_winners": ["P2"],
            "high_amount": 10,
            "low_amount": 10
        }
    ),
    # Test Case 2: A: high (KQJT9), B: low (7532A), C: high_low (76543)
    (
        2,
        {
            "P1": ("Alice", parse_cards("KQJT9")),  # Best high
            "P2": ("Bob", parse_cards("7532A")),    # Best low
            "P3": ("Charles", parse_cards("76543")) # Worse high and worse low
        },
        {"P1": "high", "P2": "low", "P3": "high_low"},
        {
            "high_winners": ["P1"],
            "low_winners": ["P2"],
            "high_amount": 15,
            "low_amount": 15
        }
    ),
    # Test Case 3: A: low (7532A), B: high_low (76543)
    (
        3,
        {
            "P1": ("Alice", parse_cards("7532A")),  # best low
            "P2": ("Bob", parse_cards("76543"))     # best high, but since declared both, can't win
        },
        {"P1": "low", "P2": "high_low"},
        {
            "high_winners": ["P1"],
            "low_winners": ["P1"],
            "high_amount": 10,
            "low_amount": 10
        }
    ),
    # Test Case 4: A: high (99954), B: high_low (76543), C low (8532A)
    (
        4,
        {
            "P1": ("Alice", parse_cards("99954")),
            "P2": ("Bob", parse_cards("76543")),
            "P3": ("Charles", parse_cards("8532A"))
        },
        {"P1": "high", "P2": "high_low", "P3": "low"},
        {
            "high_winners": ["P2"],
            "low_winners": ["P2"],
            "high_amount": 15,
            "low_amount": 15
        }
    ),
    # Test Case 5: A: high (QQQJJ), B: high_low (76543), C low (6542A)
    (
        5,
        {
            "P1": ("Alice", parse_cards("QQQJJ")),
            "P2": ("Bob", parse_cards("76543")),
            "P3": ("Charles", parse_cards("6542A"))
        },
        {"P1": "high", "P2": "high_low", "P3": "low"},
        {
            "high_winners": ["P1"],
            "low_winners": ["P3"],
            "high_amount": 15,
            "low_amount": 15
        }
    ),
    # Test Case 6: A: high (99954), B: high_low (76543), C low (6542A)
    (
        6,
        {
            "P1": ("Alice", parse_cards("99954")),   # Second-Best high
            "P2": ("Bob", parse_cards("76543")),     # Best High, but second-best Low 
            "P3": ("Charles", parse_cards("6542A"))  # best low - 6-high 
        },
        {"P1": "high", "P2": "high_low", "P3": "low"},
        {
            "high_winners": ["P1"],
            "low_winners": ["P3"],
            "high_amount": 15,
            "low_amount": 15
        }
    ),
    # Test Case 7: A: high (98765), B: high_low (987653A), C: low (76542)
    (
        7,
        {
            "P1": ("Alice", parse_cards("98765")),  # Tie for best high with 9 high straight
            "P2": ("Bob", parse_cards("987653A")),  # tie for best high with 9 high straight, best low with 7653
            "P3": ("Charles", parse_cards("76542")) # second-best low 7654
        },
        {"P1": "high", "P2": "high_low", "P3": "low"},
        {
            "high_winners": ["P1", "P2"],
            "low_winners": ["P2"],
            "high_amount": 15,
            "low_amount": 15
        }
    ),
    # Test Case 8: A: high_low (76543), B: high_low (76543 ), C: high (KKJJ9)
    (
        8,
        {
            "P1": ("Alice", parse_cards("76543")), # tied for best high 
            "P2": ("Bob", parse_cards("76543")),   # tied for best high
            "P3": ("Charles", parse_cards("KKJJ9")) # second-best high
        },
        {"P1": "high_low", "P2": "high_low", "P3": "high"},
        {
            "high_winners": ["P1", "P2"],
            "low_winners": ["P1", "P2"],
            "high_amount": 15,  # Split between P1 and P2
            "low_amount": 15  # Split between P1 and P2
        }
    ),
    # Test Case 9: A: high_low (76543), B: high (76543), C: high (KKJJ9)
    (
        9,
        {
            "P1": ("Alice", parse_cards("76543")), # tied for best high 
            "P2": ("Bob", parse_cards("76543")),   # tied for best high
            "P3": ("Charles", parse_cards("KKJJ9")) # second-best high
        },
        {"P1": "high_low", "P2": "high", "P3": "high"},
        {
            "high_winners": ["P1", "P2"],
            "low_winners": ["P1"],
            "high_amount": 15,  # Split between P1 and P2
            "low_amount": 15  # P1
        }
    ),
    # Test Case 10: A: high_low (76543), B: low (76543), C: high (KKJJ9)
    (
        10,
        {
            "P1": ("Alice", parse_cards("76543")), # best high , tied for best low
            "P2": ("Bob", parse_cards("76543")),   # best low , tied for best low
            "P3": ("Charles", parse_cards("KKJJ9")) # second-best high
        },
        {"P1": "high_low", "P2": "low", "P3": "high"},
        {
            "high_winners": ["P1"],
            "low_winners": ["P1", "P2"],
            "high_amount": 15,  # P1
            "low_amount": 15  # Split between P1 and P2
        }
    ),    
    # Test Case 11: A: high_low (76543), B: high_low (76543)
    (
        11,
        {
            "P1": ("Alice", parse_cards("76543")), # tied for best high , tied for best low
            "P2": ("Bob", parse_cards("76543"))   # tied for best low , tied for best low
        },
        {"P1": "high_low", "P2": "high_low"},
        {
            "high_winners": ["P1", "P2"],
            "low_winners": ["P1", "P2"],
            "high_amount": 10,  # Split between P1 and P2
            "low_amount": 10  # Split between P1 and P2
        }
    ),     
    # Test Case 12: A: high_low (76543), B: high_low (76543 + flush)
    # don't have a way to specify a flush - we'll use a four of a kind - we just want something bigger than a straight
    (
        12,
        {
            "P1": ("Alice", parse_cards("76543")), # tied for best low - lost high so can't win any part of the pot
            "P2": ("Bob", parse_cards("888876543"))   # best high , tied for best low
        },
        {"P1": "high_low", "P2": "high_low"},
        {
            "high_winners": ["P2"],
            "low_winners": ["P2"],
            "high_amount": 10,  # p2
            "low_amount": 10  # p2
        }
    ),    
    # Test Case 13: A: high_low (76543), B: high_low (76543 + flush), C: high (KKJJ9)
    # don't have a way to specify a flush - we'll use a four of a kind - we just want something bigger than a straight
    (
        13,
        {
            "P1": ("Alice", parse_cards("76543")), # tied for best low - lost high so can't win any part of the pot
            "P2": ("Bob", parse_cards("888876543")),   # best high , tied for best low
            "P3": ("Charles", parse_cards("KKJJ9")) # second-best high
        },
        {"P1": "high_low", "P2": "high_low", "P3": "high"},
        {
            "high_winners": ["P2"],
            "low_winners": ["P2"],
            "high_amount": 15,  # p2
            "low_amount": 15  # p2
        }
    ),      
    # Test Case 14: A: high_low (76543), B: high_low (8543A + flush)
    # don't have a way to specify a flush - we'll use a four of a kind - we just want something bigger than a straight
    # in this special case, we split the pot between the two high_low hands - even though neither have won/tied both the high and low
    (
        14,
        {
            "P1": ("Alice", parse_cards("76543")), # worst high, best low
            "P2": ("Bob", parse_cards("99998543A"))   # best high , worst low
        },
        {"P1": "high_low", "P2": "high_low"},
        {
            "high_winners": ["P1", "P2"],
            "low_winners": ["P1", "P2"],
            "high_amount": 10,  # p2
            "low_amount": 10  # p2
        }
    ),      
])
def test_conjelco_variation_2(test_case, players_cards, declarations, expected, game_setup):
    game, pot_size = game_setup(players_cards, declarations)
    
    # Verify showdown results
    result = game.last_hand_result
    assert result.is_complete
    
    # Log pot results for debugging
    logging.debug(f"Test case {test_case}: Pot results: {[(p.hand_type, p.winners, p.amount) for p in result.pots]}")
    
    # Find high and low pot results
    high_pot = next((p for p in result.pots if p.hand_type == "High Hand"), None)
    low_pot = next((p for p in result.pots if p.hand_type == "Low Hand"), None)
    
    # Check high winners
    if expected["high_winners"]:
        assert high_pot is not None, f"Test case {test_case}: Expected high pot, but none found"
        assert sorted(high_pot.winners) == sorted(expected["high_winners"]), \
            f"Test case {test_case}: Expected high winners {expected['high_winners']}, got {high_pot.winners}"
        assert high_pot.amount == expected["high_amount"], \
            f"Test case {test_case}: Expected high amount {expected['high_amount']}, got {high_pot.amount}"
    else:
        assert high_pot is None or high_pot.winners == [], \
            f"Test case {test_case}: Expected no high pot, but found {high_pot.winners}"
    
    # Check low winners
    if expected["low_winners"]:
        assert low_pot is not None, f"Test case {test_case}: Expected low pot, but none found"
        assert sorted(low_pot.winners) == sorted(expected["low_winners"]), \
            f"Test case {test_case}: Expected low winners {expected['low_winners']}, got {low_pot.winners}"
        assert low_pot.amount == expected["low_amount"], \
            f"Test case {test_case}: Expected low amount {expected['low_amount']}, got {low_pot.amount}"
    else:
        assert low_pot is None or low_pot.winners == [], \
            f"Test case {test_case}: Expected no low pot, but found {low_pot.winners}"
    
    # Verify total pot
    total_awarded = (high_pot.amount if high_pot and high_pot.winners else 0) + \
                    (low_pot.amount if low_pot and low_pot.winners else 0)
    assert total_awarded == pot_size, \
        f"Test case {test_case}: Total awarded pot {total_awarded} does not match expected {pot_size}"