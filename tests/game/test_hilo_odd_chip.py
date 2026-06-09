"""Regression test: odd chip in hi-lo split pots goes to the high hand.

The odd-chip rule matched low evaluation types with startswith("low"), but the
real type names are "a5_low"/"27_low"/etc., so traditional hi-lo games (Omaha 8,
Stud 8) silently dropped the odd chip — the pot split as floor(pot/2) twice and
one chip vanished from play.
"""

from generic_poker.core.card import Card, Rank, Suit
from generic_poker.core.deck import Deck
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game, GameState, PlayerAction
from tests.test_helpers import load_rules_from_file

LOW_RANKS = [Rank.ACE, Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN, Rank.EIGHT]


class AllLowDeck(Deck):
    """A deck whose top cards are all 8-or-lower, so every hand has a qualifying low.

    With every dealt card low, the hi-lo split happens regardless of the engine's
    deal order — no per-player card mapping needed.
    """

    def __init__(self):
        super().__init__(include_jokers=False)
        low_cards = [Card(rank, suit) for suit in Suit if suit != Suit.JOKER for rank in LOW_RANKS]
        other_cards = [c for c in self.cards if c.rank not in LOW_RANKS]
        self.cards.clear()
        # Deck deals from the end of the list — put low cards on top
        self.cards.extend(other_cards)
        self.cards.extend(low_cards)


def test_omaha8_odd_pot_split_conserves_chips_and_high_gets_odd_chip():
    rules = load_rules_from_file("omaha_8")
    game = Game(
        rules=rules,
        structure=BettingStructure.NO_LIMIT,
        small_blind=1,
        big_blind=2,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=False,
    )
    for i in range(3):
        game.add_player(f"p{i}", f"Player{i}", 500)

    # clear_hands() rebuilds the deck, so patch it to preserve the stacked deck
    def patched_clear_hands():
        for player in game.table.players.values():
            player.hand.clear()
        game.table.community_cards.clear()

    game.table.clear_hands = patched_clear_hands
    game.table.deck = AllLowDeck()
    game.start_hand()
    while game.current_player is None and game.state != GameState.COMPLETE:
        game._next_step()

    # Build an odd pot: BTN calls 2, SB folds (1 dead), BB checks → pot = 5
    result = game.player_action(game.current_player.id, PlayerAction.CALL, 2)
    assert result.success
    result = game.player_action(game.current_player.id, PlayerAction.FOLD, 0)
    assert result.success
    result = game.player_action(game.current_player.id, PlayerAction.CHECK, 0)
    assert result.success and result.advance_step
    assert game.betting.get_total_pot() == 5

    # Check down to showdown
    steps = 0
    game._next_step()
    while game.state != GameState.COMPLETE and steps < 50:
        if game.state == GameState.BETTING and game.current_player is not None:
            result = game.player_action(game.current_player.id, PlayerAction.CHECK, 0)
            assert result.success
            if result.advance_step:
                game._next_step()
        else:
            game._next_step()
        steps += 1
    assert game.state == GameState.COMPLETE

    # Chip conservation: the odd chip must not vanish
    assert sum(p.stack for p in game.table.players.values()) == 1500

    # The 5-chip pot splits 3 (high, gets odd chip) / 2 (low)
    results = game.get_hand_results()
    amounts = {pot.hand_type: pot.amount for pot in results.pots}
    assert amounts.get("High Hand") == 3
    assert amounts.get("Low Hand") == 2
