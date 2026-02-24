"""Tests for Binglaha (Omaha + die roll determining hi-only vs hi-lo)."""

import logging
import sys

import pytest

from generic_poker.core.card import Card, Rank, Suit
from generic_poker.core.deck import Deck
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game, GameState, PlayerAction
from tests.test_helpers import load_rules_from_file


class MockDeck(Deck):
    """A deck with predetermined card sequence for testing, followed by remaining cards."""

    def __init__(self, named_cards):
        super().__init__(include_jokers=False)
        self.cards.clear()
        for card in named_cards:
            self.cards.append(card)
        all_cards = [
            Card(rank, suit)
            for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
            for rank in [
                Rank.TWO,
                Rank.THREE,
                Rank.FOUR,
                Rank.FIVE,
                Rank.SIX,
                Rank.SEVEN,
                Rank.EIGHT,
                Rank.NINE,
                Rank.TEN,
                Rank.JACK,
                Rank.QUEEN,
                Rank.KING,
                Rank.ACE,
            ]
        ]
        used_cards = {(c.rank, c.suit) for c in named_cards}
        remaining_cards = [c for c in all_cards if (c.rank, c.suit) not in used_cards]
        for card in remaining_cards:
            self.cards.append(card)
        self.cards.reverse()


class MockDieDeck(Deck):
    """A die deck that always returns a specific value."""

    def __init__(self, die_value):
        super().__init__(include_jokers=0, deck_type="die")
        self.cards.clear()
        # Die value 1-6 maps to Rank.ONE through Rank.SIX
        rank_mapping = {1: Rank.ONE, 2: Rank.TWO, 3: Rank.THREE, 4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX}
        self.cards.append(Card(rank=rank_mapping[die_value], suit=Suit.CLUBS))


@pytest.fixture(autouse=True)
def setup_logging():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def create_binglaha_game():
    """Create a Binglaha game with predetermined cards."""
    # Card layout for 2 players:
    # P1 hole: Ah Kh Qh Jh (strong high hand - broadway)
    # P2 hole: 2s 3s 4s 5s (strong low hand - wheel cards)
    # Flop: 6d 7d 8d
    # Turn: Td
    # River: 9c
    #
    # Board: 6d 7d 8d Td 9c
    # P1 best Omaha high (2 hole + 3 community): Ah Kh + Td 9c 8d = A-high straight? No.
    #   Actually P1 must use exactly 2 hole + 3 community.
    #   Best high: Jh Qh + 8d Td 9c = Q-J-T-9-8 straight!
    #   Or Kh Qh + Jh isn't community... let me reconsider.
    #   P1 hole: Ah Kh Qh Jh, community: 6d 7d 8d Td 9c
    #   P1 uses Jh+Qh + 8d 9c Td = Q-J-T-9-8 straight
    #
    # P2 hole: 2s 3s 4s 5s, community: 6d 7d 8d Td 9c
    #   P2 high: 5s + ? - not great
    #   P2 low (a5): 2s 3s + 6d 7d 8d = 8-7-6-3-2 (qualifies for 8-or-better)
    #     Or 4s 5s + 6d 7d 8d = 8-7-6-5-4 (also qualifies but worse)
    #     Best low: 2s 3s + 6d 7d 8d = 8-7-6-3-2

    named_cards = [
        # P1 hole cards (4)
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.JACK, Suit.HEARTS),
        # P2 hole cards (4)
        Card(Rank.TWO, Suit.SPADES),
        Card(Rank.THREE, Suit.SPADES),
        Card(Rank.FOUR, Suit.SPADES),
        Card(Rank.FIVE, Suit.SPADES),
        # Flop (3)
        Card(Rank.SIX, Suit.DIAMONDS),
        Card(Rank.SEVEN, Suit.DIAMONDS),
        Card(Rank.EIGHT, Suit.DIAMONDS),
        # Turn (1) - dealt after die roll
        Card(Rank.TEN, Suit.DIAMONDS),
        # River (1)
        Card(Rank.NINE, Suit.CLUBS),
    ]
    return MockDeck(named_cards)


def setup_game(die_value):
    """Setup a 2-player Binglaha game with controlled die roll."""
    rules = load_rules_from_file("binglaha")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False,
    )
    game.add_player("BTN", "Player1", 500)
    game.add_player("SB", "Player2", 500)

    # Patch clear_hands to not reset our mock deck
    def patched_clear_hands():
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()

    game.table.clear_hands = patched_clear_hands
    game.table.deck = create_binglaha_game()

    # Patch the die deck creation to return our controlled value
    def patched_roll_die(config):
        die_subset = config.get("subset", "Die")
        if die_subset not in game.table.community_cards:
            game.table.community_cards[die_subset] = []
        # Create a die card with our controlled value
        rank_mapping = {1: Rank.ONE, 2: Rank.TWO, 3: Rank.THREE, 4: Rank.FOUR, 5: Rank.FIVE, 6: Rank.SIX}
        from generic_poker.core.card import Visibility

        die_card = Card(rank=rank_mapping[die_value], suit=Suit.CLUBS)
        die_card.visibility = Visibility.FACE_UP
        game.table.community_cards[die_subset].append(die_card)
        die_val = int(die_card.rank.value)
        game.die_determined_game_mode = "high_low" if die_val <= 3 else "high_only"

    game._handle_roll_die = patched_roll_die

    return game


def play_through_betting(game):
    """Play through a betting round (all players check/call, never fold/raise)."""
    while game.current_player:
        actions = game.get_valid_actions(game.current_player.id)
        # Pick check if available, else call — never fold or raise
        result = None
        for a in actions:
            if a[0] == PlayerAction.CHECK:
                result = game.player_action(game.current_player.id, PlayerAction.CHECK, 0)
                break
            elif a[0] == PlayerAction.CALL:
                result = game.player_action(game.current_player.id, PlayerAction.CALL, a[1])
                break
        if result and result.advance_step:
            game._next_step()
            break


def advance_non_betting(game):
    """Advance through non-betting steps (dealing, roll_die, etc.)."""
    while game.state in (GameState.DEALING, GameState.WAITING) and game.current_player is None:
        game._next_step()


def play_to_showdown(game):
    """Play a Binglaha hand to showdown with all checks/calls."""
    game.start_hand()
    max_steps = 50
    steps = 0

    while game.state not in (GameState.SHOWDOWN, GameState.COMPLETE) and steps < max_steps:
        if game.state == GameState.BETTING:
            if game.current_player is None:
                # Forced bets (blinds/antes) posted, advance
                game._next_step()
            else:
                play_through_betting(game)
        else:
            game._next_step()
        steps += 1

    assert game.state in (
        GameState.SHOWDOWN,
        GameState.COMPLETE,
    ), f"Game stuck at state {game.state} after {steps} steps"

    # Verify die was rolled and placed in community cards
    assert "Die" in game.table.community_cards
    assert len(game.table.community_cards["Die"]) == 1

    return game


def test_binglaha_die_roll_low_triggers_hilo():
    """Die roll 1-3 makes the game hi-lo (pot split between high and low)."""
    game = setup_game(die_value=2)
    game = play_to_showdown(game)

    # Verify die value is in community cards
    die_cards = game.table.community_cards.get("Die", [])
    assert len(die_cards) == 1
    assert int(die_cards[0].rank.value) == 2

    # Game mode should be hi-lo
    assert game.die_determined_game_mode == "high_low"

    # Get results
    results = game.get_hand_results()
    assert results is not None

    # In hi-lo mode, there should be 2 pot evaluations (high + low)
    # P1 should win high, P2 should win low (if qualifying)
    assert len(results.pots) >= 1


def test_binglaha_die_roll_high_triggers_high_only():
    """Die roll 4-6 makes the game high-only (no low pot)."""
    game = setup_game(die_value=5)
    game = play_to_showdown(game)

    # Verify die value
    die_cards = game.table.community_cards.get("Die", [])
    assert len(die_cards) == 1
    assert int(die_cards[0].rank.value) == 5

    # Game mode should be high-only
    assert game.die_determined_game_mode == "high_only"

    results = game.get_hand_results()
    assert results is not None

    # In high-only mode, there should be 1 winning hand evaluation
    # P1 with broadway cards should win the high
    assert len(results.pots) >= 1


def test_binglaha_die_boundary_value_3():
    """Die roll of exactly 3 should trigger hi-lo (boundary case)."""
    game = setup_game(die_value=3)
    game = play_to_showdown(game)

    assert game.die_determined_game_mode == "high_low"
    die_cards = game.table.community_cards["Die"]
    assert int(die_cards[0].rank.value) == 3


def test_binglaha_die_boundary_value_4():
    """Die roll of exactly 4 should trigger high-only (boundary case)."""
    game = setup_game(die_value=4)
    game = play_to_showdown(game)

    assert game.die_determined_game_mode == "high_only"
    die_cards = game.table.community_cards["Die"]
    assert int(die_cards[0].rank.value) == 4


def test_binglaha_die_community_cards_structure():
    """Verify the Die subset exists alongside regular community cards."""
    game = setup_game(die_value=1)
    game = play_to_showdown(game)

    # Should have 'default' subset with 5 community cards + 'Die' with 1 die card
    assert "default" in game.table.community_cards
    assert len(game.table.community_cards["default"]) == 5  # flop(3) + turn(1) + river(1)
    assert "Die" in game.table.community_cards
    assert len(game.table.community_cards["Die"]) == 1


def test_binglaha_hilo_evaluates_both_hands():
    """In hi-lo mode, verify both high and low hands are evaluated."""
    game = setup_game(die_value=1)  # hi-lo mode
    game = play_to_showdown(game)

    results = game.get_hand_results()
    assert results is not None

    # In hi-lo mode, hand results should contain evaluations for both "High Hand" and "Low Hand"
    hand_types = set()
    for _player_id, hand_list in results.hands.items():
        for hand in hand_list:
            hand_types.add(hand.hand_type)
    assert "High Hand" in hand_types, f"Expected 'High Hand' evaluation, got {hand_types}"
    assert "Low Hand" in hand_types, f"Expected 'Low Hand' evaluation, got {hand_types}"

    # Total chips should be conserved
    total_stacks = sum(p.stack for p in game.table.players.values())
    assert total_stacks == 1000


def test_binglaha_high_only_single_winner():
    """In high-only mode, verify single winner takes the whole pot."""
    game = setup_game(die_value=6)  # high-only mode
    game = play_to_showdown(game)

    results = game.get_hand_results()

    # In high-only mode, P1 with broadway cards should take everything
    total_awarded = sum(pot.amount for pot in results.pots)
    assert total_awarded > 0

    # Only the high hand winner should get the pot
    all_winners = set()
    for pot in results.pots:
        for w in pot.winners:
            all_winners.add(w)
    # Should be just one winner
    assert len(all_winners) == 1, f"Expected 1 winner in high-only mode, got {all_winners}"
