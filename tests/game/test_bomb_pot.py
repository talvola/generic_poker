"""Tests for the bomb pot forced-bet style (BACKLOG 6.2.10).

A bomb pot: everyone antes, there is NO preflop betting round, and the deal goes
straight to the flop. Post-flop play proceeds like a normal flop game (betting
starts left of the button). These tests verify the ante collection, the
skipped preflop street, the post-flop action order, and chip conservation —
including the double-board split variant.
"""

from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction
from tests.test_helpers import load_rules_from_file

ANTE = 5
START_STACK = 500


def _bomb_game(config: str, num_players: int = 3) -> Game:
    rules = load_rules_from_file(config)
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        ante=ANTE,
        min_buyin=100,
        max_buyin=1000,
        auto_progress=True,
    )
    for i in range(num_players):
        game.add_player(f"p{i}", f"Player{i}", START_STACK)
    return game


def _total_chips(game: Game) -> int:
    stacks = sum(p.stack for p in game.table.players.values())
    return stacks + game.betting.get_total_pot()


def _play_passively(game: Game, max_actions: int = 300) -> None:
    actions = 0
    while game.state != GameState.COMPLETE and actions < max_actions:
        actions += 1
        if game.state == GameState.BETTING and game.current_player is not None:
            pid = game.current_player.id
            valid = {a[0]: a for a in game.get_valid_actions(pid)}
            for pref in (PlayerAction.CHECK, PlayerAction.CALL):
                if pref in valid:
                    game.player_action(pid, pref, valid[pref][1] or 0)
                    break
            else:
                action, lo, _hi = game.get_valid_actions(pid)[0]
                game.player_action(pid, action, lo or 0)
        else:
            break


def test_bomb_style_loaded():
    game = _bomb_game("bomb_pot_holdem")
    assert game.rules.forced_bets.style == "bomb"
    # Bomb pots are flop games: betting order is dealer-based, not stud high-hand.
    assert game.rules.betting_order.subsequent == "dealer"


def test_everyone_antes():
    game = _bomb_game("bomb_pot_holdem", num_players=3)
    game.start_hand(shuffle_deck=True)
    for p in game.table.players.values():
        assert p.stack == START_STACK - ANTE
    assert game.betting.get_main_pot_amount() == 3 * ANTE


def test_no_preflop_betting_flop_already_dealt():
    """The first betting decision is post-flop — the flop is already on board."""
    game = _bomb_game("bomb_pot_holdem", num_players=3)
    game.start_hand(shuffle_deck=True)

    assert game.state == GameState.BETTING
    assert game.current_player is not None
    # First voluntary betting round is the post-flop bet, not a preflop bet.
    assert game.rules.gameplay[game.current_step].name == "Post-Flop Bet"
    # Three community cards (the flop) are already dealt before any betting.
    assert len(game.table.community_cards["default"]) == 3


def test_post_flop_action_starts_left_of_button():
    game = _bomb_game("bomb_pot_holdem", num_players=3)
    game.start_hand(shuffle_deck=True)
    order = game.table.get_position_order(include_inactive=False)
    # order[0] is the button; post-flop action begins with the next player.
    assert game.current_player.id == order[1].id


def test_chip_conservation_single_board():
    game = _bomb_game("bomb_pot_holdem", num_players=3)
    before = _total_chips(game)
    game.start_hand(shuffle_deck=True)
    _play_passively(game)
    assert game.state == GameState.COMPLETE
    assert _total_chips(game) == before


def test_double_board_bomb_pot_completes_and_conserves_chips():
    game = _bomb_game("double_board_bomb_pot", num_players=3)
    before = _total_chips(game)
    game.start_hand(shuffle_deck=True)

    # Two boards exist and no preflop betting precedes the flop.
    assert game.rules.gameplay[game.current_step].name == "Post-Flop Bet"
    assert len(game.table.community_cards["Board 1"]) == 3
    assert len(game.table.community_cards["Board 2"]) == 3

    _play_passively(game)
    assert game.state == GameState.COMPLETE
    assert _total_chips(game) == before
