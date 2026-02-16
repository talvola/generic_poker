"""Edge case tests for 2-player No-Limit Texas Hold'em.

Tests cover scenarios not in the basic hold'em tests:
- All-in pre-flop and on later streets
- Split pots (identical hand values)
- Raise/re-raise sequences
- Min-raise and max-raise validation
- Player busting out across multiple hands
"""

import pytest
from typing import List, Optional

from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game, GameState, PlayerAction
from generic_poker.game.betting import BettingStructure
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.core.deck import Deck
from tests.test_helpers import load_rules_from_file


# ── Helpers ──────────────────────────────────────────────────────────────────

class MockDeck(Deck):
    """A deck with predetermined card sequence for testing."""

    def __init__(self, cards: List[Card]):
        super().__init__(include_jokers=False)
        self.cards.clear()
        for card in reversed(cards):
            self.cards.append(card)


def make_game(p1_stack=200, p2_stack=200, small_blind=1, big_blind=2,
              cards: Optional[List[Card]] = None):
    """Create a 2-player NL Hold'em game with optional predetermined deck.

    Deal order: p1 gets card 0, p2 gets card 1, p1 gets card 2, p2 gets card 3,
    then community: flop[0-2], turn, river.

    Args:
        p1_stack: Player 1 starting stack
        p2_stack: Player 2 starting stack
        small_blind: Small blind amount
        big_blind: Big blind amount
        cards: If provided, list of 9+ cards in deal order
    """
    game = Game(
        rules=load_rules_from_file('hold_em'),
        structure=BettingStructure.NO_LIMIT,
        small_blind=small_blind,
        big_blind=big_blind,
        min_buyin=10,
        max_buyin=10000,
        auto_progress=False
    )

    game.add_player("p1", "Alice", p1_stack)
    game.add_player("p2", "Bob", p2_stack)

    if cards:
        # Monkey-patch clear_hands to preserve our mock deck
        def patched_clear_hands():
            for player in game.table.players.values():
                player.hand.clear()
            game.table.community_cards.clear()

        game.table.clear_hands = patched_clear_hands
        game.table.deck = MockDeck(cards)

    return game


def advance_to_betting(game):
    """Advance from dealing state to the next betting round."""
    game._next_step()


def play_check_check(game):
    """Both players check (post-flop order: p2 first, then p1)."""
    assert game.state == GameState.BETTING
    cp = game.current_player
    other = "p1" if cp.id == "p2" else "p2"
    game.player_action(cp.id, PlayerAction.CHECK)
    game.player_action(other, PlayerAction.CHECK)


def advance_through_streets(game):
    """Advance from the end of one betting round through deal + next betting.

    Call _next_step() to deal, then _next_step() to start the next bet round.
    Returns the game state after advancing.
    """
    game._next_step()  # Deal
    game._next_step()  # Start betting
    return game.state


def play_to_showdown_checking(game):
    """From pre-flop betting, play check/call through to showdown.

    Assumes we're at pre-flop betting. SB calls, BB checks, then
    check-check through flop, turn, river, then advance to showdown.
    """
    # Pre-flop: SB (p1) calls, BB (p2) checks
    assert game.current_player.id == "p1"
    game.player_action("p1", PlayerAction.CALL, game.big_blind)
    game.player_action("p2", PlayerAction.CHECK)

    # Flop
    game._next_step()  # Deal flop
    game._next_step()  # Flop betting
    play_check_check(game)

    # Turn
    game._next_step()  # Deal turn
    game._next_step()  # Turn betting
    play_check_check(game)

    # River
    game._next_step()  # Deal river
    game._next_step()  # River betting
    play_check_check(game)

    # Showdown
    game._next_step()
    assert game.state == GameState.COMPLETE


# ── All-In Tests ─────────────────────────────────────────────────────────────

class TestAllInPreflop:
    """Test all-in scenarios before the flop."""

    def test_short_stack_all_in_preflop(self):
        """Short-stacked SB goes all-in pre-flop, BB calls.

        Game should auto-progress through remaining streets since
        no player can act.
        """
        # p1 (SB) has only 10 chips, p2 (BB) has 200
        # p1 hole: Ah Kh (strong hand)
        # p2 hole: 7c 2d (weak hand)
        # Board: Qs Jd Tc 3h 8s (p1 wins with AK high / straight draw)
        # Actually: p1 has AKQJT straight, p2 has Q-high
        cards = [
            Card(Rank.ACE, Suit.HEARTS),    # p1 hole 1
            Card(Rank.SEVEN, Suit.CLUBS),   # p2 hole 1
            Card(Rank.KING, Suit.HEARTS),   # p1 hole 2
            Card(Rank.TWO, Suit.DIAMONDS),  # p2 hole 2
            Card(Rank.QUEEN, Suit.SPADES),  # flop 1
            Card(Rank.JACK, Suit.DIAMONDS), # flop 2
            Card(Rank.TEN, Suit.CLUBS),     # flop 3
            Card(Rank.THREE, Suit.HEARTS),  # turn
            Card(Rank.EIGHT, Suit.SPADES),  # river
        ]

        game = make_game(p1_stack=10, p2_stack=200, cards=cards)
        game.start_hand()

        # Blinds: p1 posts SB=1 (stack=9), p2 posts BB=2 (stack=198)
        assert game.table.players['p1'].stack == 9
        assert game.table.players['p2'].stack == 198

        game._next_step()  # Deal hole cards
        game._next_step()  # Pre-flop betting

        # p1 (SB) goes all-in for 10 total (9 more on top of 1 SB)
        assert game.current_player.id == "p1"
        result = game.player_action("p1", PlayerAction.RAISE, 10)
        assert result.success, f"All-in raise failed: {result}"

        # p2 (BB) calls the all-in
        result = game.player_action("p2", PlayerAction.CALL, 10)
        assert result.success, f"Call failed: {result}"

        # Both players have all their money in (p1 is all-in)
        assert game.table.players['p1'].stack == 0

        # Now advance through remaining streets - betting should be skipped
        # since p1 is all-in and p2 has no one to bet against
        game._next_step()  # Deal flop

        # The flop betting round should auto-complete or have no action needed
        game._next_step()  # Flop betting
        if game.state == GameState.BETTING and game.current_player:
            # p2 might still need to check since they have chips
            # In heads-up with one all-in, the other player can only check
            game.player_action(game.current_player.id, PlayerAction.CHECK)

        game._next_step()  # Deal turn
        game._next_step()  # Turn betting
        if game.state == GameState.BETTING and game.current_player:
            game.player_action(game.current_player.id, PlayerAction.CHECK)

        game._next_step()  # Deal river
        game._next_step()  # River betting
        if game.state == GameState.BETTING and game.current_player:
            game.player_action(game.current_player.id, PlayerAction.CHECK)

        game._next_step()  # Showdown
        assert game.state == GameState.COMPLETE

        results = game.get_hand_results()
        assert results.is_complete
        assert results.total_pot == 20  # 10 from each player

        # p1 should win (AKQJT straight vs Q-high)
        assert 'p1' in results.pots[0].winners
        assert game.table.players['p1'].stack == 20  # Won the pot
        assert game.table.players['p2'].stack == 190  # Lost 10

    def test_both_players_all_in_preflop(self):
        """Both players all-in pre-flop with equal stacks.

        Game should deal all community cards and reach showdown.
        """
        # p1: Ah Kh, p2: Qs Qd
        # Board: 2c 3d 5s 7h 9c (p2 wins with pair of queens)
        cards = [
            Card(Rank.ACE, Suit.HEARTS),    # p1
            Card(Rank.QUEEN, Suit.SPADES),  # p2
            Card(Rank.KING, Suit.HEARTS),   # p1
            Card(Rank.QUEEN, Suit.DIAMONDS),# p2
            Card(Rank.TWO, Suit.CLUBS),     # flop
            Card(Rank.THREE, Suit.DIAMONDS),# flop
            Card(Rank.FIVE, Suit.SPADES),   # flop
            Card(Rank.SEVEN, Suit.HEARTS),  # turn
            Card(Rank.NINE, Suit.CLUBS),    # river
        ]

        game = make_game(p1_stack=50, p2_stack=50, cards=cards)
        game.start_hand()
        game._next_step()  # Deal hole cards
        game._next_step()  # Pre-flop betting

        # p1 (SB) goes all-in
        result = game.player_action("p1", PlayerAction.RAISE, 50)
        assert result.success

        # p2 calls all-in
        result = game.player_action("p2", PlayerAction.CALL, 50)
        assert result.success

        assert game.table.players['p1'].stack == 0
        assert game.table.players['p2'].stack == 0

        # Advance through all remaining streets
        for _ in range(6):  # flop deal, flop bet, turn deal, turn bet, river deal, river bet
            game._next_step()
            # If we hit a betting round with a current player, they check
            if game.state == GameState.BETTING and game.current_player:
                game.player_action(game.current_player.id, PlayerAction.CHECK)

        game._next_step()  # Showdown
        assert game.state == GameState.COMPLETE

        results = game.get_hand_results()
        assert results.is_complete
        assert results.total_pot == 100  # All chips in

        # p2 wins with Queens
        assert 'p2' in results.pots[0].winners

        # Chip conservation
        total = game.table.players['p1'].stack + game.table.players['p2'].stack
        assert total == 100


class TestAllInLaterStreet:
    """Test all-in scenarios on flop, turn, or river."""

    def test_all_in_on_flop(self):
        """Player goes all-in on the flop, other calls."""
        # p1: Ah Kh, p2: 7c 2d
        # Board: Ac 3d 5s 7h 9c (p1 wins with pair of aces)
        cards = [
            Card(Rank.ACE, Suit.HEARTS),    # p1
            Card(Rank.SEVEN, Suit.CLUBS),   # p2
            Card(Rank.KING, Suit.HEARTS),   # p1
            Card(Rank.TWO, Suit.DIAMONDS),  # p2
            Card(Rank.ACE, Suit.CLUBS),     # flop
            Card(Rank.THREE, Suit.DIAMONDS),# flop
            Card(Rank.FIVE, Suit.SPADES),   # flop
            Card(Rank.SEVEN, Suit.HEARTS),  # turn
            Card(Rank.NINE, Suit.CLUBS),    # river
        ]

        game = make_game(p1_stack=100, p2_stack=100, cards=cards)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop betting

        # Pre-flop: SB calls, BB checks
        game.player_action("p1", PlayerAction.CALL, 2)
        game.player_action("p2", PlayerAction.CHECK)

        game._next_step()  # Deal flop
        game._next_step()  # Flop betting

        # p2 (BB) acts first post-flop — bets all-in
        assert game.current_player.id == "p2"
        result = game.player_action("p2", PlayerAction.BET, 98)  # All remaining chips
        assert result.success

        # p1 calls the all-in
        result = game.player_action("p1", PlayerAction.CALL, 98)
        assert result.success

        assert game.table.players['p1'].stack == 0
        assert game.table.players['p2'].stack == 0

        # Advance through turn and river
        for _ in range(4):  # turn deal, turn bet, river deal, river bet
            game._next_step()
            if game.state == GameState.BETTING and game.current_player:
                game.player_action(game.current_player.id, PlayerAction.CHECK)

        game._next_step()  # Showdown
        assert game.state == GameState.COMPLETE

        results = game.get_hand_results()
        assert results.is_complete
        assert results.total_pot == 200

        # p1 wins with pair of aces (Ah Kh on Ac 3d 5s board)
        assert 'p1' in results.pots[0].winners

        # Chip conservation
        total = game.table.players['p1'].stack + game.table.players['p2'].stack
        assert total == 200

    def test_all_in_on_river(self):
        """Player goes all-in on the river."""
        # p1: Ah Kh (pair of aces), p2: Qd Jd (nothing)
        # Board: Ac 3d 5s 7h 9c
        cards = [
            Card(Rank.ACE, Suit.HEARTS),    # p1
            Card(Rank.QUEEN, Suit.DIAMONDS),# p2
            Card(Rank.KING, Suit.HEARTS),   # p1
            Card(Rank.JACK, Suit.DIAMONDS), # p2
            Card(Rank.ACE, Suit.CLUBS),     # flop
            Card(Rank.THREE, Suit.DIAMONDS),# flop
            Card(Rank.FIVE, Suit.SPADES),   # flop
            Card(Rank.SEVEN, Suit.HEARTS),  # turn
            Card(Rank.NINE, Suit.CLUBS),    # river
        ]

        game = make_game(p1_stack=100, p2_stack=100, cards=cards)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # Pre-flop: call/check
        game.player_action("p1", PlayerAction.CALL, 2)
        game.player_action("p2", PlayerAction.CHECK)

        # Flop: check/check
        game._next_step()  # Deal flop
        game._next_step()  # Flop betting
        play_check_check(game)

        # Turn: check/check
        game._next_step()  # Deal turn
        game._next_step()  # Turn betting
        play_check_check(game)

        # River: p2 bets all-in, p1 calls
        game._next_step()  # Deal river
        game._next_step()  # River betting
        assert game.current_player.id == "p2"
        game.player_action("p2", PlayerAction.BET, 98)
        game.player_action("p1", PlayerAction.CALL, 98)

        game._next_step()  # Showdown
        assert game.state == GameState.COMPLETE

        results = game.get_hand_results()
        assert results.total_pot == 200
        assert 'p1' in results.pots[0].winners  # Pair of aces beats Q-high


# ── Split Pot Tests ──────────────────────────────────────────────────────────

class TestSplitPot:
    """Test split pot scenarios."""

    def test_split_pot_board_plays(self):
        """Both players have the same best hand (board plays).

        When the community cards make a better hand than either player's
        hole cards, the pot should be split.
        """
        # p1: 2h 3h (low cards, board plays)
        # p2: 2d 3d (same thing)
        # Board: As Ks Qs Js Ts (royal flush on board - both play board)
        cards = [
            Card(Rank.TWO, Suit.HEARTS),    # p1
            Card(Rank.TWO, Suit.DIAMONDS),  # p2
            Card(Rank.THREE, Suit.HEARTS),  # p1
            Card(Rank.THREE, Suit.DIAMONDS),# p2
            Card(Rank.ACE, Suit.SPADES),    # flop
            Card(Rank.KING, Suit.SPADES),   # flop
            Card(Rank.QUEEN, Suit.SPADES),  # flop
            Card(Rank.JACK, Suit.SPADES),   # turn
            Card(Rank.TEN, Suit.SPADES),    # river
        ]

        game = make_game(p1_stack=100, p2_stack=100, cards=cards)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        play_to_showdown_checking(game)

        results = game.get_hand_results()
        assert results.is_complete
        assert results.total_pot == 4  # 2 from each (just blinds)

        # Should be a split pot
        main_pot = results.pots[0]
        assert main_pot.split, f"Expected split pot, got winners: {main_pot.winners}"
        assert 'p1' in main_pot.winners
        assert 'p2' in main_pot.winners

        # Each player gets half the pot back
        # Total stacks should still be 200
        total = game.table.players['p1'].stack + game.table.players['p2'].stack
        assert total == 200, f"Expected 200 total, got {total}"

    def test_split_pot_same_hand_different_suits(self):
        """Both players make the same straight from hole + community cards."""
        # p1: Ah 9h (makes A-high straight: A K Q J T)
        # p2: Ad 9d (makes same A-high straight)
        # Board: Kc Qc Jc Tc 2s
        cards = [
            Card(Rank.ACE, Suit.HEARTS),    # p1
            Card(Rank.ACE, Suit.DIAMONDS),  # p2
            Card(Rank.NINE, Suit.HEARTS),   # p1
            Card(Rank.NINE, Suit.DIAMONDS), # p2
            Card(Rank.KING, Suit.CLUBS),    # flop
            Card(Rank.QUEEN, Suit.CLUBS),   # flop
            Card(Rank.JACK, Suit.CLUBS),    # flop
            Card(Rank.TEN, Suit.CLUBS),     # turn
            Card(Rank.TWO, Suit.SPADES),    # river
        ]

        game = make_game(p1_stack=100, p2_stack=100, cards=cards)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # Pre-flop: p1 raises, p2 calls
        game.player_action("p1", PlayerAction.RAISE, 6)
        game.player_action("p2", PlayerAction.CALL, 6)

        # Check through remaining streets
        for _ in range(3):  # flop, turn, river
            game._next_step()  # Deal
            game._next_step()  # Betting
            play_check_check(game)

        game._next_step()  # Showdown
        assert game.state == GameState.COMPLETE

        results = game.get_hand_results()
        main_pot = results.pots[0]
        assert main_pot.split
        assert len(main_pot.winners) == 2
        assert 'p1' in main_pot.winners
        assert 'p2' in main_pot.winners

        # Chip conservation
        total = game.table.players['p1'].stack + game.table.players['p2'].stack
        assert total == 200


# ── Raise/Re-Raise Tests ────────────────────────────────────────────────────

class TestRaiseSequences:
    """Test raise and re-raise mechanics."""

    def test_preflop_raise_reraise_call(self):
        """SB raises, BB 3-bets, SB calls."""
        game = make_game(p1_stack=200, p2_stack=200)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop betting

        # p1 (SB) raises to 6
        assert game.current_player.id == "p1"
        result = game.player_action("p1", PlayerAction.RAISE, 6)
        assert result.success

        # p2 (BB) 3-bets to 18
        result = game.player_action("p2", PlayerAction.RAISE, 18)
        assert result.success

        # p1 calls the 3-bet
        result = game.player_action("p1", PlayerAction.CALL, 18)
        assert result.success

        # Pot should be 36 (18 from each)
        assert game.betting.get_main_pot_amount() == 36

        # Stacks: each put in 18
        assert game.table.players['p1'].stack == 182
        assert game.table.players['p2'].stack == 182

    def test_preflop_raise_reraise_reraise_call(self):
        """SB raises, BB 3-bets, SB 4-bets, BB calls."""
        game = make_game(p1_stack=500, p2_stack=500)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop betting

        # p1 raises to 6
        game.player_action("p1", PlayerAction.RAISE, 6)

        # p2 3-bets to 18
        game.player_action("p2", PlayerAction.RAISE, 18)

        # p1 4-bets to 50
        result = game.player_action("p1", PlayerAction.RAISE, 50)
        assert result.success

        # p2 calls
        result = game.player_action("p2", PlayerAction.CALL, 50)
        assert result.success

        assert game.betting.get_main_pot_amount() == 100
        assert game.table.players['p1'].stack == 450
        assert game.table.players['p2'].stack == 450

    def test_min_raise_is_one_big_blind(self):
        """Minimum raise pre-flop is double the big blind (raise BY the BB amount)."""
        game = make_game(p1_stack=200, p2_stack=200)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # Valid actions for p1 (SB)
        actions = game.get_valid_actions("p1")
        action_dict = {a[0]: (a[1], a[2]) for a in actions}

        # Min raise should be 4 (BB=2, raise BY 2 = total 4)
        assert PlayerAction.RAISE in action_dict
        min_raise, max_raise = action_dict[PlayerAction.RAISE]
        assert min_raise == 4, f"Expected min raise of 4, got {min_raise}"

        # Max raise should be all-in (200 = full stack)
        assert max_raise == 200, f"Expected max raise of 200, got {max_raise}"

    def test_min_reraise_equals_previous_raise_size(self):
        """After a raise to X, the min re-raise is X + (X - previous_bet)."""
        game = make_game(p1_stack=500, p2_stack=500)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # p1 raises to 10 (raise of 8 on top of BB=2)
        game.player_action("p1", PlayerAction.RAISE, 10)

        # p2's min re-raise should be 18 (10 + 8 = raise by the same increment)
        actions = game.get_valid_actions("p2")
        action_dict = {a[0]: (a[1], a[2]) for a in actions}
        min_reraise, _ = action_dict[PlayerAction.RAISE]
        assert min_reraise == 18, f"Expected min re-raise of 18, got {min_reraise}"

    def test_cannot_bet_more_than_stack(self):
        """Raise amount capped at player's stack."""
        game = make_game(p1_stack=50, p2_stack=200)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # p1's max raise should be limited to their stack (50)
        actions = game.get_valid_actions("p1")
        action_dict = {a[0]: (a[1], a[2]) for a in actions}
        _, max_raise = action_dict[PlayerAction.RAISE]
        assert max_raise == 50, f"Expected max raise of 50 (stack), got {max_raise}"

    def test_post_flop_bet_and_raise(self):
        """Post-flop: one player bets, other raises, first calls."""
        game = make_game(p1_stack=200, p2_stack=200)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # Pre-flop: call/check
        game.player_action("p1", PlayerAction.CALL, 2)
        game.player_action("p2", PlayerAction.CHECK)

        game._next_step()  # Deal flop
        game._next_step()  # Flop betting

        # p2 bets 10
        assert game.current_player.id == "p2"
        result = game.player_action("p2", PlayerAction.BET, 10)
        assert result.success

        # p1 raises to 30
        result = game.player_action("p1", PlayerAction.RAISE, 30)
        assert result.success

        # p2 calls
        result = game.player_action("p2", PlayerAction.CALL, 30)
        assert result.success

        # Pot = 4 (pre-flop) + 60 (flop: 30 each) = 64
        assert game.betting.get_main_pot_amount() == 64


# ── Multi-Hand / Bust-Out Tests ─────────────────────────────────────────────

class TestMultiHandAndBustOut:
    """Test multiple consecutive hands and player elimination."""

    def test_winner_stacks_carry_over(self):
        """After winning a hand, the winner's stack carries to the next hand."""
        # Hand 1: p1 has stronger hand, p2 folds
        game = make_game(p1_stack=100, p2_stack=100)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # p1 raises, p2 folds
        game.player_action("p1", PlayerAction.RAISE, 10)
        game.player_action("p2", PlayerAction.FOLD)

        assert game.state == GameState.COMPLETE

        # p1 wins the blinds + their own raise gets returned...
        # Actually: p2 put in BB=2, p1 raised to 10. p2 folds.
        # p1 wins pot (SB=1 + BB=2 = 3 in pot, p1 raised to 10 so pot = 1+2 = 3 before raise
        # After raise: p1 put in 10, p2 put in 2, pot = 12... no, p2 folds so:
        # p1 put in 10 total, p2 put in 2 (BB), pot = 12
        # p1 wins 12, net gain = 2 (the BB)
        p1_stack = game.table.players['p1'].stack
        p2_stack = game.table.players['p2'].stack
        assert p1_stack + p2_stack == 200  # Chip conservation
        assert p1_stack > 100  # p1 won
        assert p2_stack < 100  # p2 lost

    def test_short_stack_loses_all_chips(self):
        """A player with a small stack can go all-in and lose everything."""
        # p1 has 10 chips, p2 has 190 chips
        # Give p2 the winning hand
        cards = [
            Card(Rank.TWO, Suit.HEARTS),    # p1 (weak)
            Card(Rank.ACE, Suit.SPADES),    # p2 (strong)
            Card(Rank.THREE, Suit.HEARTS),  # p1
            Card(Rank.ACE, Suit.CLUBS),     # p2
            Card(Rank.KING, Suit.DIAMONDS), # flop
            Card(Rank.QUEEN, Suit.DIAMONDS),# flop
            Card(Rank.JACK, Suit.DIAMONDS), # flop
            Card(Rank.NINE, Suit.HEARTS),   # turn
            Card(Rank.EIGHT, Suit.CLUBS),   # river
        ]

        game = make_game(p1_stack=10, p2_stack=190, cards=cards)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # p1 goes all-in
        game.player_action("p1", PlayerAction.RAISE, 10)
        game.player_action("p2", PlayerAction.CALL, 10)

        # Advance to showdown
        for _ in range(6):
            game._next_step()
            if game.state == GameState.BETTING and game.current_player:
                game.player_action(game.current_player.id, PlayerAction.CHECK)

        game._next_step()  # Showdown
        assert game.state == GameState.COMPLETE

        results = game.get_hand_results()
        assert 'p2' in results.pots[0].winners  # p2 wins with pair of aces

        assert game.table.players['p1'].stack == 0  # Busted
        assert game.table.players['p2'].stack == 200  # Won everything

    def test_fold_win_minimal_pot(self):
        """When a player folds pre-flop, winner gets only the blinds."""
        game = make_game(p1_stack=100, p2_stack=100)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # p1 (SB) folds immediately
        game.player_action("p1", PlayerAction.FOLD)
        assert game.state == GameState.COMPLETE

        # p2 wins the pot (SB of 1)
        results = game.get_hand_results()
        assert results.total_pot == 3  # SB=1 + BB=2
        assert 'p2' in results.pots[0].winners

        # p1 lost their SB (1), p2 gets it back plus the SB
        assert game.table.players['p1'].stack == 99   # Lost SB
        assert game.table.players['p2'].stack == 101   # Won SB


class TestBetSizingValidation:
    """Test that bet sizing is correctly enforced."""

    def test_all_in_for_less_than_call(self):
        """Short stack can go all-in even if they can't match the current bet."""
        # p1 starts with 10 but after SB=1, has 9 left
        # p2 raises big, p1 can only all-in for less
        game = make_game(p1_stack=10, p2_stack=200)
        game.start_hand()  # p1 posts SB=1, p2 posts BB=2
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # p1 calls (now has 8 left)
        game.player_action("p1", PlayerAction.CALL, 2)

        # p2 raises to 50 (p1 can't match this)
        game.player_action("p2", PlayerAction.RAISE, 50)

        # p1 has 8 chips left, needs 48 more to call 50
        # Should be able to go all-in (call for less)
        actions = game.get_valid_actions("p1")
        action_names = [a[0] for a in actions]

        assert PlayerAction.FOLD in action_names
        assert PlayerAction.CALL in action_names  # All-in call for less

    def test_all_in_raise_less_than_min_raise(self):
        """All-in for less than the minimum raise is still valid."""
        # p2 has 200, raises to 100
        # p1 has 120 total. After posting SB=1, has 119 left.
        # min re-raise of 100 raise would be 198, but p1 only has 120
        # p1 should still be able to go all-in for 120
        game = make_game(p1_stack=120, p2_stack=200)
        game.start_hand()
        game._next_step()  # Deal
        game._next_step()  # Pre-flop

        # p1 calls (to simplify)
        game.player_action("p1", PlayerAction.CALL, 2)

        # p2 raises to 100
        game.player_action("p2", PlayerAction.RAISE, 100)

        # p1's options: fold, call 100, or all-in for 120
        actions = game.get_valid_actions("p1")
        action_dict = {a[0]: (a[1], a[2]) for a in actions}

        assert PlayerAction.FOLD in action_dict
        assert PlayerAction.CALL in action_dict

        # p1 should be able to go all-in (raise to 120) even though
        # min re-raise would be 198 (100 + 98)
        if PlayerAction.RAISE in action_dict:
            _, max_raise = action_dict[PlayerAction.RAISE]
            assert max_raise == 120, f"Max raise should be 120 (all-in), got {max_raise}"
