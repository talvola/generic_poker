"""Tests for SimpleBot decision making."""

from unittest.mock import MagicMock

from generic_poker.core.card import Card, Visibility
from generic_poker.game.game import PlayerAction
from online_poker.services.simple_bot import BotDecision, SimpleBot


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

    def test_handles_variable_length_tuples(self):
        """Bot should handle 4-tuple (CHOOSE) and 2-tuple action formats."""
        # 4-tuple for CHOOSE
        valid_actions = [
            (PlayerAction.CHOOSE, 0, 2, ["option_a", "option_b", "option_c"]),
        ]
        decision = self.bot.choose_action_full(valid_actions)
        assert decision.action == PlayerAction.CHOOSE
        assert decision.amount == 0

        # 2-tuple
        valid_actions = [
            (PlayerAction.CHECK, None),
        ]
        action, amount = self.bot.choose_action(valid_actions)
        assert action == PlayerAction.CHECK


class TestSimpleBotChooseActionFull:
    """Test choose_action_full() for all action types."""

    def setup_method(self):
        self.bot = SimpleBot("bot_1", "TestBot")

    def _make_mock_game(self, hand_cards=None):
        """Create a mock game with player hand."""
        game = MagicMock()
        player = MagicMock()
        hand = MagicMock()
        if hand_cards is not None:
            hand.get_cards.return_value = hand_cards
        else:
            hand.get_cards.return_value = []
        player.hand = hand
        game.table.players = {"bot_1": player}
        return game

    def test_draw_selects_valid_card_count(self):
        """Draw action should select between min and max cards from hand."""
        cards = [
            Card.from_string("Ah"),
            Card.from_string("Kh"),
            Card.from_string("Qh"),
            Card.from_string("Jh"),
            Card.from_string("Th"),
        ]
        game = self._make_mock_game(cards)
        valid_actions = [(PlayerAction.DRAW, 0, 3)]

        for _ in range(50):
            decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
            assert decision.action == PlayerAction.DRAW
            assert decision.cards is not None
            assert 0 <= len(decision.cards) <= 3
            # All returned cards should be from the hand
            for card in decision.cards:
                assert card in cards

    def test_draw_empty_hand(self):
        """Draw with empty hand should return no cards."""
        game = self._make_mock_game([])
        valid_actions = [(PlayerAction.DRAW, 0, 3)]

        decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
        assert decision.action == PlayerAction.DRAW
        assert decision.cards == []

    def test_discard_works_like_draw(self):
        """Discard action should work the same as draw."""
        cards = [Card.from_string("Ah"), Card.from_string("Kh")]
        game = self._make_mock_game(cards)
        valid_actions = [(PlayerAction.DISCARD, 1, 2)]

        decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
        assert decision.action == PlayerAction.DISCARD
        assert decision.cards is not None
        assert 1 <= len(decision.cards) <= 2

    def test_expose_only_selects_face_down_cards(self):
        """Expose should only select face-down cards."""
        face_down = Card.from_string("Ah")
        face_down.visibility = Visibility.FACE_DOWN
        face_up = Card.from_string("Kh")
        face_up.visibility = Visibility.FACE_UP

        game = self._make_mock_game([face_down, face_up])
        valid_actions = [(PlayerAction.EXPOSE, 1, 1)]

        for _ in range(20):
            decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
            assert decision.action == PlayerAction.EXPOSE
            assert decision.cards is not None
            assert len(decision.cards) == 1
            assert decision.cards[0].visibility == Visibility.FACE_DOWN

    def test_expose_with_no_face_down(self):
        """Expose with no face-down cards returns empty list."""
        face_up = Card.from_string("Ah")
        face_up.visibility = Visibility.FACE_UP

        game = self._make_mock_game([face_up])
        valid_actions = [(PlayerAction.EXPOSE, 1, 1)]

        decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
        assert decision.action == PlayerAction.EXPOSE
        assert decision.cards == []

    def test_pass_selects_exact_count(self):
        """Pass should select exactly the required number of cards."""
        cards = [Card.from_string("Ah"), Card.from_string("Kh"), Card.from_string("Qh")]
        game = self._make_mock_game(cards)
        valid_actions = [(PlayerAction.PASS, 2, 2)]

        decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
        assert decision.action == PlayerAction.PASS
        assert decision.cards is not None
        assert len(decision.cards) == 2

    def test_separate_returns_all_cards(self):
        """Separate should return all cards in some order."""
        cards = [
            Card.from_string("Ah"),
            Card.from_string("Kh"),
            Card.from_string("Qh"),
            Card.from_string("Jh"),
        ]
        game = self._make_mock_game(cards)
        valid_actions = [(PlayerAction.SEPARATE, 4, 4)]

        decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
        assert decision.action == PlayerAction.SEPARATE
        assert decision.cards is not None
        assert len(decision.cards) == 4
        # Cards are unhashable, compare string representations
        assert sorted(str(c) for c in decision.cards) == sorted(str(c) for c in cards)

    def test_declare_returns_valid_declaration(self):
        """Declare should return valid declaration_data."""
        game = MagicMock()
        game.current_declare_config = {"options": ["high", "low", "both"], "per_pot": False}
        valid_actions = [(PlayerAction.DECLARE, None, None)]

        decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
        assert decision.action == PlayerAction.DECLARE
        assert decision.declaration_data is not None
        assert len(decision.declaration_data) == 1
        assert decision.declaration_data[0]["pot_index"] == -1
        assert decision.declaration_data[0]["declaration"] in ["high", "low", "both"]

    def test_declare_without_config(self):
        """Declare without config defaults to 'high'."""
        game = MagicMock(spec=[])  # No attributes
        valid_actions = [(PlayerAction.DECLARE, None, None)]

        decision = self.bot.choose_action_full(valid_actions, game, "bot_1")
        assert decision.action == PlayerAction.DECLARE
        assert decision.declaration_data[0]["declaration"] == "high"

    def test_choose_returns_first_option(self):
        """Choose should return amount=0 (first option)."""
        valid_actions = [(PlayerAction.CHOOSE, 0, 2, ["opt_a", "opt_b", "opt_c"])]

        decision = self.bot.choose_action_full(valid_actions)
        assert decision.action == PlayerAction.CHOOSE
        assert decision.amount == 0

    def test_bring_in_returns_minimum(self):
        """Bring-in should return the minimum amount."""
        valid_actions = [(PlayerAction.BRING_IN, 5, 5)]

        decision = self.bot.choose_action_full(valid_actions)
        assert decision.action == PlayerAction.BRING_IN
        assert decision.amount == 5

    def test_complete_returns_minimum(self):
        """Complete should return the minimum amount."""
        valid_actions = [(PlayerAction.COMPLETE, 10, 10)]

        decision = self.bot.choose_action_full(valid_actions)
        assert decision.action == PlayerAction.COMPLETE
        assert decision.amount == 10

    def test_betting_actions_use_weighted_random(self):
        """Standard betting actions should use the weighted random strategy."""
        valid_actions = [
            (PlayerAction.FOLD, None, None),
            (PlayerAction.CHECK, None, None),
            (PlayerAction.BET, 10, 100),
        ]

        decisions = set()
        for _ in range(200):
            decision = self.bot.choose_action_full(valid_actions)
            decisions.add(decision.action)

        assert PlayerAction.CHECK in decisions
        assert PlayerAction.BET in decisions
        assert PlayerAction.FOLD not in decisions  # Never fold when check available

    def test_no_valid_actions(self):
        """Empty valid_actions should return FOLD."""
        decision = self.bot.choose_action_full([])
        assert decision.action == PlayerAction.FOLD

    def test_no_game_object_draw(self):
        """Draw without game object should return empty card list."""
        valid_actions = [(PlayerAction.DRAW, 0, 3)]

        decision = self.bot.choose_action_full(valid_actions, game=None, player_id="bot_1")
        assert decision.action == PlayerAction.DRAW
        assert decision.cards == []


class TestBotDecision:
    """Test BotDecision dataclass."""

    def test_defaults(self):
        d = BotDecision(action=PlayerAction.FOLD)
        assert d.action == PlayerAction.FOLD
        assert d.amount is None
        assert d.cards is None
        assert d.declaration_data is None

    def test_with_all_fields(self):
        cards = [Card.from_string("Ah")]
        d = BotDecision(
            action=PlayerAction.DRAW,
            amount=0,
            cards=cards,
            declaration_data=[{"pot_index": -1, "declaration": "high"}],
        )
        assert d.action == PlayerAction.DRAW
        assert d.cards == cards


class TestIsBot:
    """Test bot identification."""

    def test_bot_prefix(self):
        assert SimpleBot.is_bot_player("bot_abc123_0") is True

    def test_demo_prefix(self):
        assert SimpleBot.is_bot_player("demo_player_1") is True

    def test_human_id(self):
        assert SimpleBot.is_bot_player("550e8400-e29b-41d4-a716-446655440000") is False
