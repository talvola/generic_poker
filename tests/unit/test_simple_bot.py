"""Tests for SimpleBot decision making."""

import pytest
from generic_poker.game.game import PlayerAction
from online_poker.services.simple_bot import SimpleBot


class TestSimpleBot:
    """Test bot action selection."""

    def setup_method(self):
        self.bot = SimpleBot("bot_1", "TestBot")

    def test_never_folds_when_check_available(self):
        """Bot should never fold when check is a free option."""
        valid_actions = [
            (PlayerAction.FOLD, None, None),
            (PlayerAction.CHECK, None, None),
            (PlayerAction.BET, 10, 100),
        ]
        # Run 200 times — should never fold
        for _ in range(200):
            action, _ = self.bot.choose_action(valid_actions)
            assert action != PlayerAction.FOLD, "Bot folded when check was available"

    def test_can_fold_when_facing_bet(self):
        """Bot should sometimes fold when facing a bet (no check available)."""
        valid_actions = [
            (PlayerAction.FOLD, None, None),
            (PlayerAction.CALL, 50, 50),
            (PlayerAction.RAISE, 100, 200),
        ]
        actions_chosen = set()
        for _ in range(200):
            action, _ = self.bot.choose_action(valid_actions)
            actions_chosen.add(action)
        assert PlayerAction.FOLD in actions_chosen, "Bot never folded facing a bet"

    def test_checks_and_bets_when_available(self):
        """Bot should use check and bet actions."""
        valid_actions = [
            (PlayerAction.FOLD, None, None),
            (PlayerAction.CHECK, None, None),
            (PlayerAction.BET, 10, 100),
        ]
        actions_chosen = set()
        for _ in range(200):
            action, _ = self.bot.choose_action(valid_actions)
            actions_chosen.add(action)
        assert PlayerAction.CHECK in actions_chosen
        assert PlayerAction.BET in actions_chosen

    def test_returns_amount_for_bet(self):
        """Bot should return a valid amount when betting."""
        valid_actions = [
            (PlayerAction.BET, 10, 100),
        ]
        action, amount = self.bot.choose_action(valid_actions)
        assert action == PlayerAction.BET
        assert 10 <= amount <= 100

    def test_no_valid_actions_returns_fold(self):
        """Bot should fold if no valid actions provided."""
        action, amount = self.bot.choose_action([])
        assert action == PlayerAction.FOLD
