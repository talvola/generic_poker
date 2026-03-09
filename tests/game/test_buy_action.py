"""Tests for the BUY action (Buy Your Card mechanic)."""

import json

import pytest

from generic_poker.config.loader import GameRules
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction


def create_minimal_buy_game(num_players=2, buy_cost=10, optional=True, stack=500):
    """Create a minimal game with just deal + buy + showdown for unit testing."""
    import json

    from generic_poker.config.loader import GameRules

    config_json = {
        "game": "Test Buy Game",
        "players": {"min": 2, "max": 6},
        "deck": {"type": "standard", "cards": 52},
        "forcedBets": {"style": "blinds"},
        "bettingStructures": ["Limit"],
        "bettingOrder": {"initial": "after_big_blind", "subsequent": "after_big_blind"},
        "showdown": {
            "order": "clockwise",
            "startingFrom": "dealer",
            "cardsRequired": "all cards",
            "bestHand": [{"evaluationType": "high", "holeCards": 5, "communityCards": 0}],
        },
        "gamePlay": [
            {"bet": {"type": "blinds"}, "name": "Post Blinds"},
            {
                "deal": {
                    "location": "player",
                    "cards": [{"number": 5, "state": "face down"}],
                },
                "name": "Deal Cards",
            },
            {
                "buy": {
                    "cards": [
                        {
                            "number": 1,
                            "state": "face down",
                            "cost": {"type": "fixed", "amount": buy_cost},
                            "optional": optional,
                        }
                    ]
                },
                "name": "Buy a Card",
            },
            {"bet": {"type": "small"}, "name": "Bet"},
            {"showdown": {"type": "standard"}, "name": "Showdown"},
        ],
    }

    rules = GameRules.from_json(json.dumps(config_json))
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
    )

    for i in range(num_players):
        game.add_player(f"player_{i}", f"Player {i}", stack)

    return game


class TestBuyAction:
    """Test the buy action mechanic."""

    def test_buy_round_starts(self):
        """Test that a buy round sets up correctly."""
        game = create_minimal_buy_game()
        game.start_hand(shuffle_deck=True)

        # Advance through blinds and deal
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                # Auto-check/call through betting
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        assert game.state == GameState.DRAWING
        assert hasattr(game, "current_buy_config")
        assert game.current_player is not None

    def test_buy_valid_actions_optional(self):
        """Test valid actions for optional buy."""
        game = create_minimal_buy_game(buy_cost=10, optional=True, stack=500)
        game.start_hand(shuffle_deck=True)

        # Get to buy round
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        player_id = game.current_player.id
        actions = game.get_valid_actions(player_id)

        # Should have BUY with min=0 (stand pat) and max=10 (buy cost)
        assert len(actions) == 1
        assert actions[0][0] == PlayerAction.BUY
        assert actions[0][1] == 0  # min = stand pat
        assert actions[0][2] == 10  # max = buy cost

    def test_buy_stand_pat(self):
        """Test standing pat (declining to buy)."""
        game = create_minimal_buy_game(buy_cost=10, optional=True, stack=500)
        game.start_hand(shuffle_deck=True)

        # Get to buy round
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        player_id = game.current_player.id
        player = game.table.players[player_id]
        initial_stack = player.stack
        initial_cards = len(player.hand.get_cards())

        result = game.player_action(player_id, PlayerAction.BUY, 0)
        assert result.success

        # Stack unchanged, cards unchanged
        assert player.stack == initial_stack
        assert len(player.hand.get_cards()) == initial_cards

    def test_buy_card_costs_chips(self):
        """Test that buying a card deducts chips and adds to pot."""
        game = create_minimal_buy_game(buy_cost=10, optional=True, stack=500)
        game.start_hand(shuffle_deck=True)

        # Get to buy round
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        player_id = game.current_player.id
        player = game.table.players[player_id]
        initial_stack = player.stack
        initial_cards = len(player.hand.get_cards())
        pot_before = game.betting.pot.total

        result = game.player_action(player_id, PlayerAction.BUY, 10)
        assert result.success

        # Stack decreased by cost
        assert player.stack == initial_stack - 10
        # Got one more card
        assert len(player.hand.get_cards()) == initial_cards + 1
        # Pot increased
        assert game.betting.pot.total == pot_before + 10

    def test_buy_round_completes(self):
        """Test that buy round completes after all players act."""
        game = create_minimal_buy_game(buy_cost=10, optional=True, stack=500)
        game.start_hand(shuffle_deck=True)

        # Get to buy round
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        # Both players act
        p1 = game.current_player.id
        result1 = game.player_action(p1, PlayerAction.BUY, 10)  # Player 1 buys
        assert result1.success

        p2 = game.current_player.id
        assert p2 != p1
        result2 = game.player_action(p2, PlayerAction.BUY, 0)  # Player 2 stands pat
        assert result2.success
        assert result2.advance_step  # Round complete

    def test_buy_cant_afford(self):
        """Test that player who can't afford buy can only stand pat."""
        game = create_minimal_buy_game(buy_cost=1000, optional=True, stack=500)
        game.start_hand(shuffle_deck=True)

        # Get to buy round
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        player_id = game.current_player.id
        actions = game.get_valid_actions(player_id)

        # Can only stand pat (min=0, max=0)
        assert len(actions) == 1
        assert actions[0][0] == PlayerAction.BUY
        assert actions[0][1] == 0
        assert actions[0][2] == 0

    def test_buy_mandatory_cant_afford_must_fold(self):
        """Test that mandatory buy with insufficient chips forces fold."""
        game = create_minimal_buy_game(buy_cost=1000, optional=False, stack=500)
        game.start_hand(shuffle_deck=True)

        # Get to buy round
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        player_id = game.current_player.id
        actions = game.get_valid_actions(player_id)

        # Must fold - can't afford mandatory buy
        assert len(actions) == 1
        assert actions[0][0] == PlayerAction.FOLD

    def test_buy_match_pot_cost(self):
        """Test buy with match_pot cost type."""
        config_json = {
            "game": "Test Match Pot Buy",
            "players": {"min": 2, "max": 6},
            "deck": {"type": "standard", "cards": 52},
            "forcedBets": {"style": "blinds"},
            "bettingStructures": ["Limit"],
            "bettingOrder": {"initial": "after_big_blind", "subsequent": "after_big_blind"},
            "showdown": {
                "order": "clockwise",
                "startingFrom": "dealer",
                "cardsRequired": "all cards",
                "bestHand": [{"evaluationType": "high", "holeCards": 5, "communityCards": 0}],
            },
            "gamePlay": [
                {"bet": {"type": "blinds"}, "name": "Post Blinds"},
                {
                    "deal": {
                        "location": "player",
                        "cards": [{"number": 5, "state": "face down"}],
                    },
                    "name": "Deal Cards",
                },
                {
                    "buy": {
                        "cards": [
                            {
                                "number": 1,
                                "state": "face down",
                                "cost": {"type": "match_pot"},
                                "optional": True,
                            }
                        ]
                    },
                    "name": "Buy (Match Pot)",
                },
                {"showdown": {"type": "standard"}, "name": "Showdown"},
            ],
        }

        rules = GameRules.from_json(json.dumps(config_json))
        game = Game(
            rules=rules,
            structure=BettingStructure.LIMIT,
            small_bet=10,
            big_bet=20,
        )

        game.add_player("p1", "Player 1", 500)
        game.add_player("p2", "Player 2", 500)
        game.start_hand(shuffle_deck=True)

        # Get to buy round (after blinds)
        while game.state != GameState.DRAWING or not hasattr(game, "current_buy_config"):
            if game.state == GameState.COMPLETE:
                pytest.fail("Game completed before reaching buy round")
            if game.state == GameState.BETTING:
                actions = game.get_valid_actions(game.current_player.id)
                check = next((a for a in actions if a[0] == PlayerAction.CHECK), None)
                call = next((a for a in actions if a[0] == PlayerAction.CALL), None)
                if check:
                    game.player_action(game.current_player.id, PlayerAction.CHECK)
                elif call:
                    game.player_action(game.current_player.id, PlayerAction.CALL, call[1])
                else:
                    game.player_action(game.current_player.id, PlayerAction.FOLD)
            else:
                game._next_step()

        # Cost should be current pot (blinds = 10 + 20 = 30 for limit with SB calling)
        player_id = game.current_player.id
        actions = game.get_valid_actions(player_id)
        pot_total = game.betting.pot.total

        assert actions[0][0] == PlayerAction.BUY
        assert actions[0][2] == pot_total  # Max amount = pot

    def test_buy_full_hand_to_showdown(self):
        """Test a full hand with buy action reaches showdown."""
        game = create_minimal_buy_game(buy_cost=10, optional=True, stack=500)
        game.start_hand(shuffle_deck=True)

        max_actions = 100
        action_count = 0

        while game.state != GameState.COMPLETE and game.state != GameState.SHOWDOWN:
            if action_count > max_actions:
                pytest.fail("Too many actions - possible infinite loop")
            action_count += 1

            if game.current_player is None:
                if game.state not in (GameState.COMPLETE, GameState.SHOWDOWN):
                    game._next_step()
                continue

            player_id = game.current_player.id
            actions = game.get_valid_actions(player_id)

            if not actions:
                game._next_step()
                continue

            action = actions[0]
            action_type = action[0]

            if action_type == PlayerAction.BUY:
                # Stand pat for simplicity
                game.player_action(player_id, PlayerAction.BUY, 0)
            elif action_type == PlayerAction.CHECK:
                game.player_action(player_id, PlayerAction.CHECK)
            elif action_type == PlayerAction.CALL:
                game.player_action(player_id, PlayerAction.CALL, action[1])
            elif action_type == PlayerAction.FOLD:
                game.player_action(player_id, PlayerAction.FOLD)
            elif action_type == PlayerAction.BET:
                game.player_action(player_id, PlayerAction.CHECK)
            elif action_type == PlayerAction.BRING_IN:
                game.player_action(player_id, PlayerAction.BRING_IN, action[1])
            else:
                game.player_action(player_id, action_type, action[1] or 0)

        assert game.state in (GameState.SHOWDOWN, GameState.COMPLETE)


class TestBuyChipConservation:
    """Test that chips are conserved through buy actions."""

    def test_chips_conserved_when_buying(self):
        """Total chips in play should be constant."""
        game = create_minimal_buy_game(buy_cost=10, optional=True, stack=500)
        total_chips = sum(p.stack for p in game.table.players.values())

        game.start_hand(shuffle_deck=True)

        max_actions = 100
        action_count = 0

        while game.state != GameState.COMPLETE and game.state != GameState.SHOWDOWN:
            if action_count > max_actions:
                break
            action_count += 1

            if game.current_player is None:
                if game.state not in (GameState.COMPLETE, GameState.SHOWDOWN):
                    game._next_step()
                continue

            player_id = game.current_player.id
            actions = game.get_valid_actions(player_id)

            if not actions:
                game._next_step()
                continue

            action = actions[0]
            action_type = action[0]

            if action_type == PlayerAction.BUY:
                # Buy the card
                max_amt = action[2] if len(action) > 2 else 0
                game.player_action(player_id, PlayerAction.BUY, max_amt)
            elif action_type == PlayerAction.CHECK:
                game.player_action(player_id, PlayerAction.CHECK)
            elif action_type == PlayerAction.CALL:
                game.player_action(player_id, PlayerAction.CALL, action[1])
            elif action_type == PlayerAction.FOLD:
                game.player_action(player_id, PlayerAction.FOLD)
            else:
                game.player_action(player_id, action_type, action[1] or 0)

        # Verify chip conservation
        stacks = sum(p.stack for p in game.table.players.values())
        pot = game.betting.pot.total
        assert stacks + pot == total_chips, f"Chips not conserved: stacks={stacks}, pot={pot}, expected={total_chips}"
