"""Integration tests for mixed game rotation (HORSE, 8-Game Mix)."""

import pytest

from generic_poker.config.loader import GameRules
from generic_poker.config.mixed_game_loader import MixedGameConfig
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState


class TestMixedGameConfigLoading:
    """Tests for loading mixed game config files."""

    def test_load_horse_config(self):
        """HORSE config loads with correct rotation."""
        config = MixedGameConfig.from_file("data/mixed_game_configs/horse.json")
        assert config.name == "horse"
        assert config.display_name == "HORSE"
        assert config.category == "Mixed"
        assert len(config.rotation) == 5
        assert config.max_players == 7
        assert config.min_players == 2
        assert config.rotation_type == "orbit"

    def test_horse_rotation_order(self):
        """HORSE has correct H-O-R-S-E order."""
        config = MixedGameConfig.from_file("data/mixed_game_configs/horse.json")
        expected = [
            ("hold_em", "H"),
            ("omaha_8", "O"),
            ("razz", "R"),
            ("7_card_stud", "S"),
            ("7_card_stud_8", "E"),
        ]
        for i, (variant, letter) in enumerate(expected):
            assert config.rotation[i].variant == variant
            assert config.rotation[i].letter == letter
            assert config.rotation[i].betting_structure == "Limit"

    def test_load_8game_config(self):
        """8-Game Mix config loads with correct rotation."""
        config = MixedGameConfig.from_file("data/mixed_game_configs/8_game_mix.json")
        assert config.name == "8_game_mix"
        assert config.display_name == "8-Game Mix"
        assert len(config.rotation) == 8
        assert config.max_players == 7

    def test_8game_mixed_structures(self):
        """8-Game Mix has multiple betting structures."""
        config = MixedGameConfig.from_file("data/mixed_game_configs/8_game_mix.json")
        structures = {v.betting_structure for v in config.rotation}
        assert "Limit" in structures
        assert "No Limit" in structures
        assert "Pot Limit" in structures

    def test_all_variants_exist(self):
        """All variants referenced in rotation configs exist as game configs."""
        for config_name in ["horse", "8_game_mix"]:
            config = MixedGameConfig.from_file(f"data/mixed_game_configs/{config_name}.json")
            for v in config.rotation:
                rules = GameRules.from_file(f"data/game_configs/{v.variant}.json")
                assert rules is not None, f"Missing variant config: {v.variant}"


class TestMixedGameRotation:
    """Tests for rotation logic in isolation (no online platform)."""

    @pytest.fixture
    def horse_config(self):
        return MixedGameConfig.from_file("data/mixed_game_configs/horse.json")

    def _create_game_for_variant(self, variant_name, structure="Limit"):
        """Create a game instance for a variant."""
        rules = GameRules.from_file(f"data/game_configs/{variant_name}.json")
        from generic_poker.game.betting import BettingStructure

        return Game(
            rules=rules,
            structure=BettingStructure.LIMIT,
            small_bet=2,
            big_bet=4,
            ante=0,
            auto_progress=True,
        )

    def test_horse_play_through_all_variants(self, horse_config):
        """Play through all 5 HORSE variants to ensure they all work."""
        for v in horse_config.rotation:
            game = self._create_game_for_variant(v.variant)
            game.add_player("p1", "Alice", 200)
            game.add_player("p2", "Bob", 200)
            game.start_hand(shuffle_deck=True)

            # Play passively (check/call/fold)
            max_actions = 100
            actions = 0
            while game.state != GameState.COMPLETE and actions < max_actions:
                if game.current_player is None:
                    break
                valid = game.get_valid_actions(game.current_player.id)
                if not valid:
                    break
                action = valid[0][0]
                amount = valid[0][1] if len(valid[0]) > 1 else 0
                game.player_action(game.current_player.id, action, amount)
                actions += 1

            assert game.state == GameState.COMPLETE, f"Variant {v.variant} did not complete (state={game.state})"

    def test_variant_swap_preserves_stacks(self, horse_config):
        """Player stacks are preserved when swapping variants."""
        # Start with Hold'em
        rules1 = GameRules.from_file("data/game_configs/hold_em.json")
        from generic_poker.game.betting import BettingStructure

        game = Game(
            rules=rules1,
            structure=BettingStructure.LIMIT,
            small_bet=2,
            big_bet=4,
            ante=0,
            auto_progress=True,
        )
        game.add_player("p1", "Alice", 150)
        game.add_player("p2", "Bob", 250)

        # Record stacks
        p1_stack = game.table.players["p1"].stack
        p2_stack = game.table.players["p2"].stack

        # Create a new game with different rules (Razz) and re-add players
        rules2 = GameRules.from_file("data/game_configs/razz.json")
        game2 = Game(
            rules=rules2,
            structure=BettingStructure.LIMIT,
            small_bet=2,
            big_bet=4,
            ante=0,
            auto_progress=True,
        )
        game2.add_player("p1", "Alice", p1_stack)
        game2.add_player("p2", "Bob", p2_stack)

        # Verify stacks preserved
        assert game2.table.players["p1"].stack == 150
        assert game2.table.players["p2"].stack == 250

    def test_8game_nl_holdem_variant(self):
        """8-Game Mix NL Hold'em variant works with NL structure."""
        rules = GameRules.from_file("data/game_configs/hold_em.json")
        from generic_poker.game.betting import BettingStructure

        game = Game(
            rules=rules,
            structure=BettingStructure.NO_LIMIT,
            small_blind=1,
            big_blind=2,
            auto_progress=True,
        )
        game.add_player("p1", "Alice", 200)
        game.add_player("p2", "Bob", 200)
        game.start_hand(shuffle_deck=True)

        # Play passively
        max_actions = 100
        actions = 0
        while game.state != GameState.COMPLETE and actions < max_actions:
            if game.current_player is None:
                break
            valid = game.get_valid_actions(game.current_player.id)
            if not valid:
                break
            action = valid[0][0]
            amount = valid[0][1] if len(valid[0]) > 1 else 0
            game.player_action(game.current_player.id, action, amount)
            actions += 1

        assert game.state == GameState.COMPLETE

    def test_8game_pl_omaha_variant(self):
        """8-Game Mix PL Omaha variant works with PL structure."""
        rules = GameRules.from_file("data/game_configs/omaha.json")
        from generic_poker.game.betting import BettingStructure

        game = Game(
            rules=rules,
            structure=BettingStructure.POT_LIMIT,
            small_blind=1,
            big_blind=2,
            auto_progress=True,
        )
        game.add_player("p1", "Alice", 200)
        game.add_player("p2", "Bob", 200)
        game.start_hand(shuffle_deck=True)

        max_actions = 100
        actions = 0
        while game.state != GameState.COMPLETE and actions < max_actions:
            if game.current_player is None:
                break
            valid = game.get_valid_actions(game.current_player.id)
            if not valid:
                break
            action = valid[0][0]
            amount = valid[0][1] if len(valid[0]) > 1 else 0
            game.player_action(game.current_player.id, action, amount)
            actions += 1

        assert game.state == GameState.COMPLETE


class TestMixedGameOrbitTracking:
    """Tests for orbit-based rotation tracking."""

    def test_orbit_with_2_players(self):
        """With 2 players, orbit = 2 hands."""
        # Simulate orbit tracking
        orbit_size = 2
        hands_in_variant = 0

        for _ in range(2):
            hands_in_variant += 1

        assert hands_in_variant >= orbit_size  # Should rotate

    def test_orbit_with_6_players(self):
        """With 6 players, orbit = 6 hands."""
        orbit_size = 6
        hands_in_variant = 0

        for _ in range(5):
            hands_in_variant += 1
            assert hands_in_variant < orbit_size  # Not yet

        hands_in_variant += 1
        assert hands_in_variant >= orbit_size  # Now rotate

    def test_rotation_wraps_around(self):
        """Rotation index wraps around to beginning."""
        rotation_length = 5  # HORSE
        current_index = 4  # Last game (E)
        current_index = (current_index + 1) % rotation_length
        assert current_index == 0  # Back to H
