"""Stud betting rules per Robert's Rules of Poker v11 (Section 8 + Betting & Raising 4-5).

Covers:
- 8.3: the bring-in player may open for the forced amount or a full bet
- 8.6: completing the bring-in to a full bet is NOT a raise, and is available
  to every player facing the uncompleted bring-in (not just the first)
- 8.7: an open pair on fourth street gives players the small-or-big bet option
  (config-gated via forcedBets.openPairDoubleBet; razz/stud8 do not use it)
- B&R 4: limit cap of a bet and three raises with 3+ live players
- B&R 5: unlimited raising heads-up
"""

from generic_poker.config.loader import BettingStructure
from generic_poker.core.card import Card, Rank, Suit
from generic_poker.core.deck import Deck
from generic_poker.game.game import Game, GameState, PlayerAction
from tests.test_helpers import load_rules_from_file


class MockDeck(Deck):
    """A deck with predetermined card sequence (first card listed is dealt first)."""

    def __init__(self, cards):
        super().__init__(include_jokers=False)
        self.cards.clear()
        for card in reversed(cards):
            self.cards.append(card)


def act(game, pid, action, amount=0):
    result = game.player_action(pid, action, amount)
    assert result.success, f"{pid} {action.value} {amount} failed: {result.error}"
    if result.advance_step and game.state != GameState.COMPLETE:
        game._next_step()
    # Advance through dealing/non-action steps to the next decision point
    while game.state != GameState.COMPLETE and game.current_step < len(game.rules.gameplay):
        if game.state == GameState.DEALING or game.state == GameState.BETTING and game.current_player is None:
            game._next_step()
        else:
            break
    return result


def make_stud_game(num_players=3, deck=None, variant="7_card_stud"):
    rules = load_rules_from_file(variant)
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        bring_in=3,
        ante=1,
        min_buyin=100,
        max_buyin=2000,
        auto_progress=False,
    )
    for i in range(1, num_players + 1):
        game.add_player(f"p{i}", f"Player{i}", 500)
    if deck is not None:

        def patched_clear_hands():
            for player in game.table.players.values():
                player.hand.clear()
            game.table.community_cards.clear()

        game.table.clear_hands = patched_clear_hands
        game.table.deck = deck
    game.start_hand()
    while game.current_player is None and game.state != GameState.COMPLETE:
        game._next_step()
    return game


def open_pair_deck():
    """p3 (2c door) brings in; p1 pairs their queen door card on 4th street."""
    return MockDeck(
        [
            Card(Rank.ACE, Suit.HEARTS),  # p1 hole 1
            Card(Rank.SEVEN, Suit.DIAMONDS),  # p2 hole 1
            Card(Rank.JACK, Suit.SPADES),  # p3 hole 1
            Card(Rank.KING, Suit.HEARTS),  # p1 hole 2
            Card(Rank.EIGHT, Suit.CLUBS),  # p2 hole 2
            Card(Rank.JACK, Suit.DIAMONDS),  # p3 hole 2
            Card(Rank.QUEEN, Suit.HEARTS),  # p1 door
            Card(Rank.KING, Suit.DIAMONDS),  # p2 door
            Card(Rank.TWO, Suit.CLUBS),  # p3 door (bring-in)
            Card(Rank.QUEEN, Suit.SPADES),  # p1 4th st — open pair of queens
            Card(Rank.NINE, Suit.CLUBS),  # p2 4th st
            Card(Rank.TEN, Suit.SPADES),  # p3 4th st
            Card(Rank.JACK, Suit.HEARTS),  # p1 5th st
            Card(Rank.TEN, Suit.DIAMONDS),  # p2 5th st
            Card(Rank.TEN, Suit.HEARTS),  # p3 5th st
            Card(Rank.NINE, Suit.SPADES),  # p1 6th st
            Card(Rank.SEVEN, Suit.SPADES),  # p2 6th st
            Card(Rank.SIX, Suit.SPADES),  # p3 6th st
            Card(Rank.NINE, Suit.DIAMONDS),  # p1 7th st
            Card(Rank.SEVEN, Suit.HEARTS),  # p2 7th st
            Card(Rank.SIX, Suit.CLUBS),  # p3 7th st
        ]
    )


def test_every_player_facing_bring_in_may_complete():
    """Rule 8.6: completion is available to ALL players facing the uncompleted
    bring-in — historically only the first-to-act got it; others were offered
    an illegal raise to bring-in + small bet."""
    game = make_stud_game(num_players=4)

    bring_in_player = game.current_player.id
    actions = game.get_valid_actions(bring_in_player)
    assert (PlayerAction.BRING_IN, 3, 3) in actions
    assert (PlayerAction.COMPLETE, 10, 10) in actions  # Rule 8.3: may open full
    act(game, bring_in_player, PlayerAction.BRING_IN, 3)

    # First player calls the bring-in
    first = game.current_player.id
    actions = game.get_valid_actions(first)
    assert (PlayerAction.COMPLETE, 10, 10) in actions
    assert not any(a[0] == PlayerAction.RAISE for a in actions), "no raise vs uncompleted bring-in"
    act(game, first, PlayerAction.CALL, 3)

    # Second player STILL gets the completion option (this was the bug)
    second = game.current_player.id
    actions = game.get_valid_actions(second)
    assert (PlayerAction.CALL, 3, 3) in actions
    assert (PlayerAction.COMPLETE, 10, 10) in actions
    assert not any(a[0] == PlayerAction.RAISE for a in actions)
    act(game, second, PlayerAction.COMPLETE, 10)

    # After completion, normal small-bet raises apply
    third = game.current_player.id
    actions = game.get_valid_actions(third)
    assert (PlayerAction.CALL, 10, 10) in actions
    assert (PlayerAction.RAISE, 20, 20) in actions


def test_completion_does_not_count_toward_raise_cap():
    """Rule 8.6 + B&R 4: bring-in, completion, then exactly three raises."""
    game = make_stud_game(num_players=5)

    act(game, game.current_player.id, PlayerAction.BRING_IN, 3)
    act(game, game.current_player.id, PlayerAction.COMPLETE, 10)
    assert game.betting.raise_count == 0  # completion is the bet, not a raise

    act(game, game.current_player.id, PlayerAction.RAISE, 20)
    act(game, game.current_player.id, PlayerAction.RAISE, 30)
    act(game, game.current_player.id, PlayerAction.RAISE, 40)
    assert game.betting.raise_count == 3
    assert game.betting.is_raise_capped()

    # Betting is capped: call or fold only
    actions = game.get_valid_actions(game.current_player.id)
    types = {a[0] for a in actions}
    assert PlayerAction.RAISE not in types
    assert PlayerAction.CALL in types and PlayerAction.FOLD in types


def test_heads_up_raising_is_uncapped():
    """B&R 5: unlimited raising heads-up."""
    game = make_stud_game(num_players=2)

    act(game, game.current_player.id, PlayerAction.BRING_IN, 3)
    act(game, game.current_player.id, PlayerAction.COMPLETE, 10)

    # Trade raises well past the 3-raise cap
    expected = 20
    for _ in range(6):
        actions = game.get_valid_actions(game.current_player.id)
        raises = [a for a in actions if a[0] == PlayerAction.RAISE]
        assert raises, f"raise should still be available heads-up (count={game.betting.raise_count})"
        assert raises[0][1] == expected
        act(game, game.current_player.id, PlayerAction.RAISE, expected)
        expected += 10
    assert game.betting.raise_count > 3
    assert not game.betting.is_raise_capped()


def test_open_pair_on_fourth_street_allows_big_bet():
    """Rule 8.7: with an open pair showing on 4th street, the opener may bet
    the small or big limit; once a big-size wager is made, raises are big."""
    game = make_stud_game(num_players=3, deck=open_pair_deck())

    # Third street: p3 (2c) brings in, others call, p3 checks-completes nothing
    act(game, "p3", PlayerAction.BRING_IN, 3)
    act(game, "p1", PlayerAction.CALL, 3)
    act(game, "p2", PlayerAction.CALL, 3)
    act(game, "p3", PlayerAction.CHECK)

    # Fourth street: p1 shows Qh Qs — open pair, and acts first as high hand
    assert game.state == GameState.BETTING
    assert game.current_player.id == "p1"
    actions = game.get_valid_actions("p1")
    assert (PlayerAction.BET, 10, 10) in actions
    assert (PlayerAction.BET, 20, 20) in actions  # the double-bet option

    # p1 bets the big limit; subsequent raises are in big increments
    act(game, "p1", PlayerAction.BET, 20)
    actions = game.get_valid_actions("p2")
    raises = [a for a in actions if a[0] == PlayerAction.RAISE]
    assert raises == [(PlayerAction.RAISE, 40, 40)]


def test_no_open_pair_keeps_single_small_bet():
    """Without an open pair, 4th street offers only the small bet."""
    game = make_stud_game(num_players=3)

    act(game, game.current_player.id, PlayerAction.BRING_IN, 3)
    act(game, game.current_player.id, PlayerAction.CALL, 3)
    act(game, game.current_player.id, PlayerAction.CALL, 3)
    # Bring-in player closes the round
    last = game.current_player.id
    actions = game.get_valid_actions(last)
    if any(a[0] == PlayerAction.CHECK for a in actions):
        act(game, last, PlayerAction.CHECK)
    else:
        act(game, last, PlayerAction.CALL, 3)

    assert game.state == GameState.BETTING
    opener = game.current_player.id
    actions = game.get_valid_actions(opener)
    bets = [a for a in actions if a[0] == PlayerAction.BET]
    has_open_pair = game.betting.open_pair_double_now()
    if not has_open_pair:  # random deal — only assert when no pair showing
        assert bets == [(PlayerAction.BET, 10, 10)]


def test_razz_has_no_open_pair_double_bet():
    """Robert's Section 9: an open pair does not affect the limit in razz."""
    rules = load_rules_from_file("razz")
    assert not getattr(rules.forced_bets, "openPairDoubleBet", False)


def test_stud8_has_no_open_pair_double_bet():
    """Robert's Section 10 rule 6: open pair does not affect the limit in stud hi-lo."""
    rules = load_rules_from_file("7_card_stud_8")
    assert not getattr(rules.forced_bets, "openPairDoubleBet", False)


def test_holdem_limit_preflop_cap():
    """B&R 4: limit hold'em preflop — blind is the bet, then three raises cap it."""
    rules = load_rules_from_file("hold_em")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=2,
        big_bet=4,
        min_buyin=40,
        max_buyin=400,
        auto_progress=False,
    )
    for i in range(1, 4):
        game.add_player(f"p{i}", f"Player{i}", 200)
    game.start_hand()
    while game.current_player is None and game.state != GameState.COMPLETE:
        game._next_step()

    # Preflop at $2: raise to 4, 6, 8 — then capped
    for total in (4, 6, 8):
        pid = game.current_player.id
        actions = game.get_valid_actions(pid)
        assert (PlayerAction.RAISE, total, total) in actions
        act(game, pid, PlayerAction.RAISE, total)

    assert game.betting.is_raise_capped()
    types = {a[0] for a in game.get_valid_actions(game.current_player.id)}
    assert PlayerAction.RAISE not in types
