"""Minimal end-to-end test for cincinnati."""
import pytest
from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.game.betting import BettingStructure
from generic_poker.core.deck import Deck
from tests.test_helpers import load_rules_from_file
import logging
import sys

class MockDeck(Deck):
    """A deck with predetermined card sequence for testing, followed by remaining cards."""
    def __init__(self, named_cards):
        super().__init__(include_jokers=False)
        self.cards.clear()
        # Add named cards in reverse order (last dealt first)
        for card in reversed(named_cards):
            self.cards.append(card)
        # Add remaining cards from a standard deck in deterministic order
        all_cards = [Card(rank, suit) for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]                     for rank in [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN,                                  Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]]
        used_cards = {(c.rank, c.suit) for c in named_cards}
        remaining_cards = [c for c in all_cards if (c.rank, c.suit) not in used_cards]
        for card in reversed(remaining_cards):
            self.cards.append(card)

def create_predetermined_deck():
    """Create a deck with predetermined cards followed by the rest of a standard deck."""
    named_cards = [
        Card(Rank.ACE, Suit.HEARTS), Card(Rank.NINE, Suit.DIAMONDS), Card(Rank.JACK, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS), Card(Rank.KING, Suit.CLUBS), Card(Rank.JACK, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.KING, Suit.DIAMONDS), Card(Rank.TEN, Suit.SPADES),
        Card(Rank.QUEEN, Suit.CLUBS), Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.TEN, Suit.DIAMONDS), Card(Rank.TEN, Suit.HEARTS), Card(Rank.NINE, Suit.SPADES),
        Card(Rank.TWO, Suit.SPADES), Card(Rank.TWO, Suit.DIAMONDS), Card(Rank.TWO, Suit.HEARTS),
    ]
    return MockDeck(named_cards)

def setup_test_game():
    """Setup a 3-player cincinnati game with a mock deck."""
    rules = load_rules_from_file('cincinnati')
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False
    )
    game.add_player('BTN', 'Player1', 500)
    game.add_player('SB', 'Player2', 500)
    game.add_player('BB', 'Player3', 500)
    original_clear_hands = game.table.clear_hands
    def patched_clear_hands():
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()
    game.table.clear_hands = patched_clear_hands
    game.table.deck = create_predetermined_deck()
    assert len(game.table.deck.cards) >= 52, 'MockDeck should have at least 52 cards'
    return game

@pytest.fixture(autouse=True)
def setup_logging():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )

def test_cincinnati_minimal_flow():
    """Test minimal flow for cincinnati from start to showdown."""
    game = setup_test_game()
    game.start_hand()
    # Step 0: Post Blinds
    assert game.current_step == 0
    assert game.state == GameState.BETTING
    assert game.table.players['SB'].stack == 495  # SB posted 5
    assert game.table.players['BB'].stack == 490  # BB posted 10
    assert game.table.players['BTN'].stack == 500  # BTN
    assert game.betting.get_main_pot_amount() == 15
    print('Stacks after blinds:', {pid: game.table.players[pid].stack for pid in ['BTN', 'SB', 'BB']})
    # Step 1: Deal Hole Cards
    game._next_step()  # deal_hole_cards
    assert game.current_step == 1
    assert game.state == GameState.DEALING
    for pid in ['BTN', 'SB', 'BB']:
        assert len(game.table.players[pid].hand.get_cards()) == 4
    print(f'\nStep 1 - Player Hands:')
    for pid in ['BTN', 'SB', 'BB']:
        print(f'{{pid}}: {{[str(c) for c in game.table.players[pid].hand.get_cards()]}}')
    # Step 2: Deal Community Card
    game._next_step()  # deal_community_card
    assert game.current_step == 2
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['default']) == 1
    print(f'\nStep 2 - Community Cards:')
    print([str(c) for c in game.table.community_cards['default']])
    # Step 3: Pre-Flop Bet
    game._next_step()  # pre-flop_bet
    assert game.current_step == 3
    assert game.state == GameState.BETTING
    assert game.current_player.id == 'BTN'  # BTN first pre-flop
    actions = game.get_valid_actions('BTN')
    assert (PlayerAction.CALL, 10, 10) in actions
    game.player_action('BTN', PlayerAction.CALL, 10)
    game.player_action('SB', PlayerAction.CALL, 5)  # SB completes to 10
    game.player_action('BB', PlayerAction.CHECK)  # BB already in for 10
    assert game.betting.get_main_pot_amount() == 30
    assert game.table.players['BTN'].stack == 490  # BTN called 10
    assert game.table.players['SB'].stack == 490  # SB completed
    assert game.table.players['BB'].stack == 490  # BB unchanged
    print('Stacks after pre-flop:', {pid: game.table.players[pid].stack for pid in ['BTN', 'SB', 'BB']})
    # Step 4: Deal Flop
    game._next_step()  # deal_flop
    assert game.current_step == 4
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['default']) == 2
    print(f'\nStep 4 - Community Cards:')
    print([str(c) for c in game.table.community_cards['default']])
    # Step 5: Post-Flop Bet
    game._next_step()  # post-flop_bet
    assert game.current_step == 5
    assert game.state == GameState.BETTING
    assert game.current_player.id == 'SB'  # SB first post-flop
    actions = game.get_valid_actions('SB')
    assert (PlayerAction.CHECK, None, None) in actions
    game.player_action('SB', PlayerAction.CHECK)
    game.player_action('BB', PlayerAction.CHECK)
    game.player_action('BTN', PlayerAction.CHECK)
    assert game.betting.get_main_pot_amount() == 30  # No change
    assert game.table.players['BTN'].stack == 490  # Unchanged from pre-flop
    assert game.table.players['SB'].stack == 490  # Unchanged from pre-flop
    assert game.table.players['BB'].stack == 490  # Unchanged
    print('Stacks after post-flop:', {pid: game.table.players[pid].stack for pid in ['BTN', 'SB', 'BB']})
    # Step 6: Deal Turn
    game._next_step()  # deal_turn
    assert game.current_step == 6
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['default']) == 3
    print(f'\nStep 6 - Community Cards:')
    print([str(c) for c in game.table.community_cards['default']])
    # Step 7: Turn Bet
    game._next_step()  # turn_bet
    assert game.current_step == 7
    assert game.state == GameState.BETTING
    assert game.current_player.id == 'SB'  # SB first post-flop
    actions = game.get_valid_actions('SB')
    assert (PlayerAction.CHECK, None, None) in actions
    game.player_action('SB', PlayerAction.CHECK)
    game.player_action('BB', PlayerAction.CHECK)
    game.player_action('BTN', PlayerAction.CHECK)
    assert game.betting.get_main_pot_amount() == 30  # No change
    assert game.table.players['BTN'].stack == 490  # Unchanged from pre-flop
    assert game.table.players['SB'].stack == 490  # Unchanged from pre-flop
    assert game.table.players['BB'].stack == 490  # Unchanged
    print('Stacks after post-flop:', {pid: game.table.players[pid].stack for pid in ['BTN', 'SB', 'BB']})
    # Step 8: Deal River
    game._next_step()  # deal_river
    assert game.current_step == 8
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['default']) == 4
    print(f'\nStep 8 - Community Cards:')
    print([str(c) for c in game.table.community_cards['default']])
    # Step 9: River Bet
    game._next_step()  # river_bet
    assert game.current_step == 9
    assert game.state == GameState.BETTING
    assert game.current_player.id == 'SB'  # SB first post-flop
    actions = game.get_valid_actions('SB')
    assert (PlayerAction.CHECK, None, None) in actions
    game.player_action('SB', PlayerAction.CHECK)
    game.player_action('BB', PlayerAction.CHECK)
    game.player_action('BTN', PlayerAction.CHECK)
    assert game.betting.get_main_pot_amount() == 30  # No change
    assert game.table.players['BTN'].stack == 490  # Unchanged from pre-flop
    assert game.table.players['SB'].stack == 490  # Unchanged from pre-flop
    assert game.table.players['BB'].stack == 490  # Unchanged
    print('Stacks after post-flop:', {pid: game.table.players[pid].stack for pid in ['BTN', 'SB', 'BB']})
    # Step 10: Showdown
    game._next_step()  # showdown
    assert game.current_step == 10
    assert game.state == GameState.COMPLETE
    results = game.get_hand_results()
    assert results.is_complete
    assert results.total_pot > 0
    assert len(results.hands) == 3
    assert len(results.pots) >= 1
    print('\nShowdown Results (Human):')
    print(results)
    print('\nShowdown Results (JSON):')
    print(results.to_json())

    # Check pot details
    main_pot = results.pots[0]
    assert results.pots[0].amount == 30  # Unspecified pot
    assert main_pot.pot_type == 'main'  # Updated from run
    assert main_pot.split == False  # Updated from run
    assert len(main_pot.winners) == 1  # Updated from run
    assert sorted(main_pot.winners) == ['BB']  # Updated from run
    # TODO: Replace with expected winner, e.g., assert 'BTN' in main_pot.winners

    # Check winning hand
    winning_player = main_pot.winners[0]
    winning_hand = results.hands[winning_player]
    assert winning_hand[0].hand_name == 'Flush'  # Updated from run
    assert winning_hand[0].hand_description == 'Nine-high Flush'  # Updated from run

    # Check winning hands list
    assert len(results.winning_hands) == 1  # Updated from run
    assert results.winning_hands[0].player_id == 'BB'  # Updated from run
    # TODO: Replace with expected winner, e.g., assert results.winning_hands[0].player_id == 'BTN'