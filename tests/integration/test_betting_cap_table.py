"""Table-level betting-cap plumbing (BACKLOG 6.2.13).

Verifies that PokerTable's cap settings flow into the engine Game via
create_game_instance: the raise-cap override for Limit, and the per-hand money
cap (big blinds -> chips) for No-Limit/Pot-Limit.
"""

from tests.test_helpers import load_rules_from_file

from online_poker.models.table import PokerTable


def _table(structure: str, stakes: dict, **caps) -> PokerTable:
    return PokerTable(
        name="Cap Test",
        variant="hold_em",
        betting_structure=structure,
        stakes=stakes,
        max_players=6,
        creator_id="creator-1",
        **caps,
    )


def test_no_limit_money_cap_converted_to_chips():
    table = _table("no-limit", {"small_blind": 5, "big_blind": 10}, hand_cap_bb=30)
    game = table.create_game_instance(load_rules_from_file("hold_em"))
    assert game.betting.hand_cap == 300  # 30 big blinds * 10


def test_no_cap_by_default():
    table = _table("no-limit", {"small_blind": 5, "big_blind": 10})
    game = table.create_game_instance(load_rules_from_file("hold_em"))
    assert game.betting.hand_cap == 0


def test_limit_raise_cap_override():
    table = _table("limit", {"small_bet": 10, "big_bet": 20}, raise_cap_override=5)
    game = table.create_game_instance(load_rules_from_file("hold_em"))
    assert game.betting.max_raises == 5
    assert game.betting.raise_cap_enabled is True


def test_limit_unlimited_raises():
    table = _table("limit", {"small_bet": 10, "big_bet": 20}, raise_cap_override=0)
    game = table.create_game_instance(load_rules_from_file("hold_em"))
    assert game.betting.raise_cap_enabled is False


def test_limit_default_raise_cap():
    table = _table("limit", {"small_bet": 10, "big_bet": 20})
    game = table.create_game_instance(load_rules_from_file("hold_em"))
    assert game.betting.max_raises == 3  # hold'em has 3+ betting rounds
    assert game.betting.raise_cap_enabled is True


def test_money_cap_ignored_for_limit():
    """A money cap on a Limit table is a no-op (caps don't cross structures)."""
    table = _table("limit", {"small_bet": 10, "big_bet": 20}, hand_cap_bb=30)
    game = table.create_game_instance(load_rules_from_file("hold_em"))
    assert game.betting.hand_cap == 0


def test_raise_cap_ignored_for_no_limit():
    table = _table("no-limit", {"small_blind": 5, "big_blind": 10}, raise_cap_override=5)
    game = table.create_game_instance(load_rules_from_file("hold_em"))
    # Raise cap override does not apply to No-Limit; default rule stands.
    assert game.betting.max_raises == 3
