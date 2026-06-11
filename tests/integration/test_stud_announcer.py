"""Tests for stud street chat announcements (BACKLOG 8.4).

Drives a real 7-Card Stud hand through every betting street and checks that the
announcement builder produces a correct, compact line naming each player's
visible up-cards and whose action it is. Non-stud games announce nothing.
"""

from tests.test_helpers import load_rules_from_file

from generic_poker.core.card import Visibility
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction
from online_poker.services.stud_announcer import (
    build_street_announcement,
    format_card,
    is_stud_game,
)


def _stud_game(num_players: int = 3) -> Game:
    rules = load_rules_from_file("7_card_stud")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        bring_in=3,
        ante=1,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=True,
    )
    for i in range(num_players):
        game.add_player(f"p{i}", f"Player{i}", 500)
    return game


def _holdem_game() -> Game:
    rules = load_rules_from_file("hold_em")
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=True,
    )
    game.add_player("p0", "Alice", 500)
    game.add_player("p1", "Bob", 500)
    return game


def _passive_action(game: Game) -> None:
    """Make the current player stay in as cheaply as possible (no folding)."""
    pid = game.current_player.id
    actions = {a[0]: a for a in game.get_valid_actions(pid)}
    for pref in (PlayerAction.CHECK, PlayerAction.CALL, PlayerAction.BRING_IN, PlayerAction.COMPLETE):
        if pref in actions:
            amount = actions[pref][1] or 0
            game.player_action(pid, pref, amount)
            return
    # Fallback: take the first non-fold action.
    for action, lo, _hi in game.get_valid_actions(pid):
        if action != PlayerAction.FOLD:
            game.player_action(pid, action, lo or 0)
            return
    game.player_action(pid, PlayerAction.FOLD, 0)


def test_format_card():
    assert format_card("Ah") == "A♥"
    assert format_card("Ks") == "K♠"
    assert format_card("Td") == "T♦"
    assert format_card("2c") == "2♣"


def test_holdem_is_not_stud():
    game = _holdem_game()
    assert is_stud_game(game) is False
    game.start_hand(shuffle_deck=True)
    assert build_street_announcement(game) is None


def test_stud_is_stud():
    assert is_stud_game(_stud_game()) is True


def test_third_street_announcement_content():
    game = _stud_game(3)
    game.start_hand(shuffle_deck=True)
    assert game.state == GameState.BETTING

    msg = build_street_announcement(game)
    assert msg is not None
    assert msg.startswith("3rd street")
    assert "action on" in msg
    assert game.current_player.name in msg

    # Every active player's actual single up-card must be present.
    for player in game.table.players.values():
        if not player.is_active:
            continue
        ups = [c for c in player.hand.cards if c.visibility == Visibility.FACE_UP]
        assert len(ups) == 1
        assert format_card(ups[0]) in msg


def test_street_labels_progress_through_hand():
    """Each betting street is labeled 3rd..7th in order, once each."""
    game = _stud_game(3)
    game.start_hand(shuffle_deck=True)

    seen_labels = []
    last_key = None
    guard = 0
    while game.state != GameState.COMPLETE and guard < 400:
        guard += 1
        if game.state == GameState.BETTING and game.current_player is not None:
            key = game.current_step
            msg = build_street_announcement(game)
            if msg and key != last_key:
                seen_labels.append(msg.split(" — ")[0])  # text before the em dash
                last_key = key
            _passive_action(game)
        else:
            # Non-betting interactive states shouldn't occur in stud; bail safely.
            break

    assert seen_labels == ["3rd street", "4th street", "5th street", "6th street", "7th street"]


def test_up_card_count_grows_each_street():
    """The board grows: 4th street shows 2 up-cards per player, etc."""
    game = _stud_game(2)
    game.start_hand(shuffle_deck=True)

    # 3rd street: 1 up card each.
    msg3 = build_street_announcement(game)
    assert msg3.startswith("3rd street")

    # Advance to 4th street.
    last_step = game.current_step
    guard = 0
    while game.current_step == last_step and game.state == GameState.BETTING and guard < 50:
        guard += 1
        _passive_action(game)

    if game.state == GameState.BETTING:
        msg4 = build_street_announcement(game)
        assert msg4.startswith("4th street")
        # Each active player should now show two up-cards (two tokens after the name).
        for player in game.table.players.values():
            if player.is_active:
                ups = [c for c in player.hand.cards if c.visibility == Visibility.FACE_UP]
                assert len(ups) == 2
