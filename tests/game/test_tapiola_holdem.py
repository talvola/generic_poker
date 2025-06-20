"""Minimal end-to-end test for tapiola_hold_em."""
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
        for card in named_cards:
            self.cards.append(card)
        # Add remaining cards from a standard deck in deterministic order
        all_cards = [Card(rank, suit) for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]                     for rank in [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN,                                  Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]]
        used_cards = {(c.rank, c.suit) for c in named_cards}
        remaining_cards = [c for c in all_cards if (c.rank, c.suit) not in used_cards]
        for card in remaining_cards:
            self.cards.append(card)
        self.cards.reverse()

def create_predetermined_deck():
    """Create a deck with predetermined cards followed by the rest of a standard deck."""
    named_cards = [
        Card(Rank.ACE, Suit.HEARTS), Card(Rank.NINE, Suit.DIAMONDS), Card(Rank.JACK, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS), Card(Rank.KING, Suit.CLUBS), Card(Rank.JACK, Suit.DIAMONDS),
        Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.KING, Suit.DIAMONDS), Card(Rank.TEN, Suit.SPADES),
        Card(Rank.QUEEN, Suit.CLUBS), Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.TEN, Suit.DIAMONDS), Card(Rank.TEN, Suit.HEARTS), Card(Rank.NINE, Suit.SPADES),
        Card(Rank.TWO, Suit.SPADES), Card(Rank.TWO, Suit.DIAMONDS), Card(Rank.TWO, Suit.HEARTS),
        Card(Rank.SEVEN, Suit.DIAMONDS), Card(Rank.SIX, Suit.CLUBS), Card(Rank.THREE, Suit.SPADES),
    ]
    return MockDeck(named_cards)

def setup_test_game():
    """Setup a 3-player tapiola_hold_em game with a mock deck."""
    rules = load_rules_from_file('tapiola_holdem')
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

def test_tapiola_hold_em_minimal_flow():
    """Test minimal flow for tapiola_hold_em from start to showdown."""
    game = setup_test_game()
    game.start_hand()
    initial_hole_cards = {}
    for pid in ['BTN', 'SB', 'BB']:
        initial_hole_cards[pid] = 0
    # Step 0: Post Blinds
    assert game.current_step == 0
    assert game.state == GameState.BETTING
    assert game.table.players['SB'].stack == 495  # SB posted 5
    assert game.table.players['BB'].stack == 490  # BB posted 10
    assert game.table.players['BTN'].stack == 500  # BTN
    assert game.betting.get_main_pot_amount() == 15
    print('Stacks after blinds:', {pid: game.table.players[pid].stack for pid in ['BTN', 'SB', 'BB']})
    # Step 1: Deal Community Center Card
    game._next_step()  # deal_community_center_card
    assert game.current_step == 1
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['Center']) == 1  # Center subset
    print(f'\nStep 1 - Community Cards:')
    print(f'Center: {[str(c) for c in game.table.community_cards["Center"]]}')
    # Step 2: Deal Hole Cards
    game._next_step()  # deal_hole_cards
    assert game.current_step == 2
    assert game.state == GameState.DEALING
    for pid in ['BTN', 'SB', 'BB']:
        assert len(game.table.players[pid].hand.get_cards()) == 5 + initial_hole_cards[pid]
        initial_hole_cards[pid] += 5
    print(f'\nStep 2 - Player Hands:')
    for pid in ['BTN', 'SB', 'BB']:
        print(f'{pid}: {[str(c) for c in game.table.players[pid].hand.get_cards()]}')
    # Step 3: First Betting Round
    game._next_step()  # first_betting_round
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
    # Step 4: Deal First Tower Cards
    game._next_step()  # deal_first_tower_cards
    assert game.current_step == 4
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['Center']) == 1  # Center subset
    assert len(game.table.community_cards['Tower1']) == 1  # Tower1 subset
    assert len(game.table.community_cards['Tower2']) == 1  # Tower2 subset
    print(f'\nStep 4 - Community Cards:')
    print(f'Center: {[str(c) for c in game.table.community_cards["Center"]]}')
    print(f'Tower1: {[str(c) for c in game.table.community_cards["Tower1"]]}')
    print(f'Tower2: {[str(c) for c in game.table.community_cards["Tower2"]]}')
    # Step 5: First Discard Round
    game._next_step()  # first_discard_round
    assert game.current_step == 5
    assert game.state == GameState.DRAWING
    assert game.current_player.id == 'SB'  # Start with SB
    actions = game.get_valid_actions(game.current_player.id)
    assert any(a[0] == PlayerAction.DISCARD and a[1] == 1 for a in actions)
    for pid in ['SB', 'BB', 'BTN']:
        hand = game.table.players[pid].hand
        initial_count = len(hand.get_cards())
        cards_to_discard = hand.get_cards()[:1]
        game.player_action(pid, PlayerAction.DISCARD, cards=cards_to_discard)
        assert len(hand.get_cards()) == initial_count - 1  # Hand size reduced by discards
    print(f'\nStep 5 - Post-Discard Hands:')
    for pid in ['SB', 'BB', 'BTN']:
        print(f'{pid}: {[str(c) for c in game.table.players[pid].hand.get_cards()]}')
    # Step 6: Second Betting Round
    game._next_step()  # second_betting_round
    assert game.current_step == 6
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
    # Step 7: Deal Second Tower Cards
    game._next_step()  # deal_second_tower_cards
    assert game.current_step == 7
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['Center']) == 1  # Center subset
    assert len(game.table.community_cards['Tower1']) == 2  # Tower1 subset
    assert len(game.table.community_cards['Tower2']) == 2  # Tower2 subset
    print(f'\nStep 7 - Community Cards:')
    print(f'Center: {[str(c) for c in game.table.community_cards["Center"]]}')
    print(f'Tower1: {[str(c) for c in game.table.community_cards["Tower1"]]}')
    print(f'Tower2: {[str(c) for c in game.table.community_cards["Tower2"]]}')
    # Step 8: Second Discard Round
    game._next_step()  # second_discard_round
    assert game.current_step == 8
    assert game.state == GameState.DRAWING
    assert game.current_player.id == 'SB'  # Start with SB
    actions = game.get_valid_actions(game.current_player.id)
    assert any(a[0] == PlayerAction.DISCARD and a[1] == 1 for a in actions)
    for pid in ['SB', 'BB', 'BTN']:
        hand = game.table.players[pid].hand
        initial_count = len(hand.get_cards())
        cards_to_discard = hand.get_cards()[:1]
        game.player_action(pid, PlayerAction.DISCARD, cards=cards_to_discard)
        assert len(hand.get_cards()) == initial_count - 1  # Hand size reduced by discards
    print(f'\nStep 8 - Post-Discard Hands:')
    for pid in ['SB', 'BB', 'BTN']:
        print(f'{pid}: {[str(c) for c in game.table.players[pid].hand.get_cards()]}')
    # Step 9: Third Betting Round
    game._next_step()  # third_betting_round
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
    # Step 10: Deal Third Tower Cards
    game._next_step()  # deal_third_tower_cards
    assert game.current_step == 10
    assert game.state == GameState.DEALING
    assert len(game.table.community_cards['Center']) == 1  # Center subset
    assert len(game.table.community_cards['Tower1']) == 3  # Tower1 subset
    assert len(game.table.community_cards['Tower2']) == 3  # Tower2 subset
    print(f'\nStep 10 - Community Cards:')
    print(f'Center: {[str(c) for c in game.table.community_cards["Center"]]}')
    print(f'Tower1: {[str(c) for c in game.table.community_cards["Tower1"]]}')
    print(f'Tower2: {[str(c) for c in game.table.community_cards["Tower2"]]}')
    # Step 11: Third Optional Discard Round
    game._next_step()  # third_optional_discard_round
    assert game.current_step == 11
    assert game.state == GameState.DRAWING
    assert game.current_player.id == 'SB'  # Start with SB
    actions = game.get_valid_actions(game.current_player.id)
    assert any(a[0] == PlayerAction.DISCARD and a[1] >= 0 and a[2] == 1 for a in actions)
    for pid in ['SB', 'BB', 'BTN']:
        hand = game.table.players[pid].hand
        initial_count = len(hand.get_cards())
        # For optional discard, choose to discard 1 cards
        cards_to_discard = hand.get_cards()[:1] if 1 > 0 else []
        game.player_action(pid, PlayerAction.DISCARD, cards=cards_to_discard)
        assert len(hand.get_cards()) == initial_count - 1  # Hand size reduced by discards
    print(f'\nStep 11 - Post-Discard Hands:')
    for pid in ['SB', 'BB', 'BTN']:
        print(f'{pid}: {[str(c) for c in game.table.players[pid].hand.get_cards()]}')
    # Step 12: Final Bet
    game._next_step()  # final_bet
    assert game.current_step == 12
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
    # Step 13: Showdown
    game._next_step()  # showdown
    assert game.current_step == 13
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
    assert results.pots[0].amount == 30  # Best Hand pot
    assert main_pot.pot_type == 'main'  # Updated from run
    assert main_pot.split == False  # Updated from run
    assert len(main_pot.winners) == 1  # Updated from run
    assert sorted(main_pot.winners) == ['BB']  # Updated from run
    # TODO: Replace with expected winner, e.g., assert 'BTN' in main_pot.winners

    # Check winning hand
    winning_player = main_pot.winners[0]
    winning_hand = results.hands[winning_player]
    assert winning_hand[0].hand_name == 'Three of a Kind'  # Updated from run
    assert winning_hand[0].hand_description == 'Three Twos'  # Updated from run

    # Check winning hands list
    assert len(results.winning_hands) == 1  # Updated from run
    assert results.winning_hands[0].player_id == 'BB'  # Updated from run
    # TODO: Replace with expected winner, e.g., assert results.winning_hands[0].player_id == 'BTN'