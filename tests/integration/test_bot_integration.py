"""Integration tests for bot support in game engine.

Layer 1 tests — drive game engine directly, no browser needed.
"""

from pathlib import Path

from generic_poker.config.loader import GameRules
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction
from online_poker.services.simple_bot import SimpleBot

CONFIG_DIR = Path(__file__).parent.parent.parent / "data" / "game_configs"


def _load_rules(variant: str) -> GameRules:
    """Load game rules for a variant."""
    config_path = CONFIG_DIR / f"{variant}.json"
    return GameRules.from_file(config_path)


def _create_game(
    variant: str,
    num_players: int = 2,
    small_blind: int = 1,
    big_blind: int = 2,
    structure: str = "No Limit",
    ante: int | None = None,
):
    """Create a game with the given variant and players."""
    from generic_poker.config.loader import BettingStructure

    struct = BettingStructure(structure)
    rules = _load_rules(variant)
    game = Game(
        rules,
        structure=struct,
        small_blind=small_blind,
        big_blind=big_blind,
        small_bet=big_blind,
        big_bet=big_blind * 2,
        bring_in=small_blind,
        ante=ante,
        auto_progress=False,
    )

    bot_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]
    for i in range(num_players):
        game.add_player(f"player_{i}", bot_names[i], 100)

    game.table.move_button()
    game.start_hand(shuffle_deck=True)

    # Advance through initial dealing
    while game.current_player is None and game.state != GameState.COMPLETE:
        game._next_step()
        if game.current_step >= len(game.rules.gameplay):
            break

    return game


def _advance_non_player_steps(game):
    """Advance through non-player steps (dealing, empty betting rounds)."""
    from generic_poker.config.loader import GameActionType

    while game.state != GameState.COMPLETE:
        if game.current_step >= len(game.rules.gameplay):
            break
        if game.state == GameState.DEALING:
            current_step = game.rules.gameplay[game.current_step]
            if current_step.action_type == GameActionType.CHOOSE:
                break
            game._next_step()
        elif game.state == GameState.BETTING and game.current_player is None:
            game._next_step()
        else:
            break


class TestBotHoldemHand:
    """Test bots playing a full Texas Hold'em hand."""

    def test_two_bots_complete_hand(self):
        """Two bots should be able to complete a full hand."""
        game = _create_game("hold_em")
        bots = {f"player_{i}": SimpleBot(f"player_{i}", name) for i, name in enumerate(["Alice", "Bob"])}

        max_actions = 50
        for _ in range(max_actions):
            if game.state == GameState.COMPLETE:
                break

            if not game.current_player:
                break

            pid = game.current_player.id
            bot = bots[pid]
            valid_actions = game.get_valid_actions(pid)

            if not valid_actions:
                break

            decision = bot.choose_action_full(valid_actions, game, pid)
            result = game.player_action(
                pid,
                decision.action,
                decision.amount or 0,
                cards=decision.cards,
                declaration_data=decision.declaration_data,
            )
            assert (
                result.success
            ), f"Action {decision.action} failed: {result.error if hasattr(result, 'error') else ''}"

            # Advance if needed
            if hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    _advance_non_player_steps(game)

        assert game.state == GameState.COMPLETE, f"Game did not complete, state={game.state}"

    def test_chip_conservation(self):
        """Total chips should be conserved after a hand."""
        game = _create_game("hold_em")
        # Include pot + stacks (blinds already posted by start_hand)
        pot = game.betting.get_main_pot_amount() if game.betting else 0
        total_before = sum(p.stack for p in game.table.players.values()) + pot

        bots = {f"player_{i}": SimpleBot(f"player_{i}", name) for i, name in enumerate(["Alice", "Bob"])}

        for _ in range(50):
            if game.state == GameState.COMPLETE:
                break
            if not game.current_player:
                break

            pid = game.current_player.id
            valid_actions = game.get_valid_actions(pid)
            if not valid_actions:
                break

            decision = bots[pid].choose_action_full(valid_actions, game, pid)
            result = game.player_action(
                pid,
                decision.action,
                decision.amount or 0,
                cards=decision.cards,
                declaration_data=decision.declaration_data,
            )

            if hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    _advance_non_player_steps(game)

        total_after = sum(p.stack for p in game.table.players.values())
        assert total_after == total_before, f"Chips not conserved: {total_before} -> {total_after}"

    def test_multi_bot_hand(self):
        """Four bots should complete a hand."""
        game = _create_game("hold_em", num_players=4)
        bots = {
            f"player_{i}": SimpleBot(f"player_{i}", name) for i, name in enumerate(["Alice", "Bob", "Charlie", "Diana"])
        }

        for _ in range(100):
            if game.state == GameState.COMPLETE:
                break
            if not game.current_player:
                break

            pid = game.current_player.id
            valid_actions = game.get_valid_actions(pid)
            if not valid_actions:
                break

            decision = bots[pid].choose_action_full(valid_actions, game, pid)
            result = game.player_action(
                pid,
                decision.action,
                decision.amount or 0,
                cards=decision.cards,
                declaration_data=decision.declaration_data,
            )
            assert result.success

            if hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    _advance_non_player_steps(game)

        assert game.state == GameState.COMPLETE


class TestBotDrawGame:
    """Test bots playing draw poker variants."""

    def test_five_card_draw(self):
        """Bots should handle draw actions in 5-card draw."""
        game = _create_game("5_card_draw")
        bots = {f"player_{i}": SimpleBot(f"player_{i}", name) for i, name in enumerate(["Alice", "Bob"])}

        for _ in range(80):
            if game.state == GameState.COMPLETE:
                break
            if not game.current_player:
                break

            pid = game.current_player.id
            valid_actions = game.get_valid_actions(pid)
            if not valid_actions:
                break

            decision = bots[pid].choose_action_full(valid_actions, game, pid)
            result = game.player_action(
                pid,
                decision.action,
                decision.amount or 0,
                cards=decision.cards,
                declaration_data=decision.declaration_data,
            )
            assert result.success, f"Action {decision.action} failed for {pid}: {getattr(result, 'error', '')}"

            if hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    _advance_non_player_steps(game)

        assert game.state == GameState.COMPLETE, f"5-card draw did not complete, state={game.state}"


class TestBotStudGame:
    """Test bots playing stud variants."""

    def test_seven_card_stud(self):
        """Bots should handle 7-card stud (bring-in, face-up cards)."""
        game = _create_game("7_card_stud", small_blind=5, big_blind=10, structure="Limit", ante=1)
        bots = {f"player_{i}": SimpleBot(f"player_{i}", name) for i, name in enumerate(["Alice", "Bob"])}

        for _ in range(100):
            if game.state == GameState.COMPLETE:
                break
            if not game.current_player:
                break

            pid = game.current_player.id
            valid_actions = game.get_valid_actions(pid)
            if not valid_actions:
                break

            decision = bots[pid].choose_action_full(valid_actions, game, pid)
            result = game.player_action(
                pid,
                decision.action,
                decision.amount or 0,
                cards=decision.cards,
                declaration_data=decision.declaration_data,
            )
            assert result.success, f"Stud action {decision.action} failed: {getattr(result, 'error', '')}"

            if hasattr(result, "advance_step") and result.advance_step:
                if game.state != GameState.COMPLETE:
                    game._next_step()
                    _advance_non_player_steps(game)

        assert game.state == GameState.COMPLETE


class TestBotNeverFoldsWhenCheckAvailable:
    """Regression test: bot should never fold when check is an option."""

    def test_no_fold_with_check(self):
        """Run 500 betting decisions — never fold when check available."""
        bot = SimpleBot("bot_test", "TestBot")
        valid_actions = [
            (PlayerAction.FOLD, None, None),
            (PlayerAction.CHECK, None, None),
            (PlayerAction.BET, 10, 100),
        ]

        for _ in range(500):
            decision = bot.choose_action_full(valid_actions)
            assert decision.action != PlayerAction.FOLD, "Bot folded when check was available"
