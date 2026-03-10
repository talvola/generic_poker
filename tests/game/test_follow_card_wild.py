"""Tests for the follow_card dynamic wild card mechanic (Follow the Queen)."""

from generic_poker.config.loader import BettingStructure, GameRules
from generic_poker.core.card import Card, Rank, Suit, Visibility
from generic_poker.game.game import Game, GameState, PlayerAction

FOLLOW_QUEEN_JSON = """
{
  "game": "Follow the Queen",
  "category": "Stud",
  "players": {"min": 2, "max": 7},
  "deck": {"type": "standard", "cards": 52},
  "bettingStructures": ["Limit"],
  "forcedBets": {"style": "bring-in", "rule": "low card"},
  "gamePlay": [
    {"bet": {"type": "antes"}, "name": "Post Antes"},
    {
      "deal": {
        "location": "player",
        "cards": [
          {"number": 2, "state": "face down"},
          {"number": 1, "state": "face up"}
        ],
        "wildCards": [
          {"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}
        ]
      },
      "name": "Deal Hole Cards"
    },
    {"bet": {"type": "bring-in"}, "name": "Post Bring-In"},
    {"bet": {"type": "small"}, "name": "Third Street Bet"},
    {
      "deal": {
        "location": "player",
        "cards": [{"number": 1, "state": "face up"}],
        "wildCards": [
          {"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}
        ]
      },
      "name": "Deal Fourth Street"
    },
    {"bet": {"type": "small"}, "name": "Fourth Street Bet"},
    {
      "deal": {
        "location": "player",
        "cards": [{"number": 1, "state": "face up"}],
        "wildCards": [
          {"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}
        ]
      },
      "name": "Deal Fifth Street"
    },
    {"bet": {"type": "big"}, "name": "Fifth Street Bet"},
    {
      "deal": {
        "location": "player",
        "cards": [{"number": 1, "state": "face up"}],
        "wildCards": [
          {"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}
        ]
      },
      "name": "Deal Sixth Street"
    },
    {"bet": {"type": "big"}, "name": "Sixth Street Bet"},
    {
      "deal": {
        "location": "player",
        "cards": [{"number": 1, "state": "face down"}]
      },
      "name": "Deal Seventh Street"
    },
    {"bet": {"type": "big"}, "name": "Seventh Street Bet"},
    {"showdown": {"type": "final"}, "name": "Showdown"}
  ],
  "showdown": {
    "order": "clockwise",
    "startingFrom": "dealer",
    "cardsRequired": "best five of seven cards",
    "bestHand": [
      {
        "evaluationType": "high_wild_bug",
        "holeCards": 5,
        "communityCards": 0,
        "wildCards": [
          {"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}
        ]
      }
    ]
  }
}
"""


def create_follow_queen_game():
    """Create a Follow the Queen game with 2 players."""
    rules = GameRules.from_json(FOLLOW_QUEEN_JSON)
    game = Game(
        rules=rules,
        structure=BettingStructure.LIMIT,
        small_bet=10,
        big_bet=20,
        bring_in=5,
        ante=2,
        min_buyin=20,
        max_buyin=10000,
        auto_progress=False,
    )
    game.add_player("p0", "Alice", 500)
    game.add_player("p1", "Bob", 500)
    return game


class TestFollowCardBasicMechanics:
    """Test the follow_card wild card tracking during dealing."""

    def test_follow_trigger_pending_reset_on_new_hand(self):
        """Follow-card state should be reset at start of each hand."""
        game = create_follow_queen_game()
        game.follow_trigger_pending = True
        game.follow_card_wild_rank = Rank.SEVEN
        game.start_hand(shuffle_deck=True)

        assert game.follow_trigger_pending is False
        assert game.follow_card_wild_rank is None

    def test_trigger_card_sets_pending(self):
        """When a queen is dealt face-up, follow_trigger_pending should be set."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Simulate dealing a queen face-up
        queen = Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP)
        game._apply_wild_card_rules_to_card(queen, wild_rules, face_up=True)

        assert game.follow_trigger_pending is True
        assert game.follow_card_wild_rank is None

    def test_card_after_trigger_becomes_wild(self):
        """Card dealt face-up after a trigger should set the wild rank."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Deal queen face-up
        queen = Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP)
        game._apply_wild_card_rules_to_card(queen, wild_rules, face_up=True)

        # Deal a seven face-up after the queen
        seven = Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_UP)
        game._apply_wild_card_rules_to_card(seven, wild_rules, face_up=True)

        assert game.follow_trigger_pending is False
        assert game.follow_card_wild_rank == Rank.SEVEN
        assert seven.is_wild

    def test_face_down_card_does_not_trigger(self):
        """Face-down cards should not participate in the follow mechanic."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Deal queen face-down — should NOT trigger
        queen = Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_DOWN)
        game._apply_wild_card_rules_to_card(queen, wild_rules, face_up=False)

        assert game.follow_trigger_pending is False
        assert game.follow_card_wild_rank is None

    def test_face_down_after_trigger_does_not_set_wild(self):
        """Face-down card after trigger should not become the wild rank."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Deal queen face-up (trigger)
        queen = Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP)
        game._apply_wild_card_rules_to_card(queen, wild_rules, face_up=True)

        # Deal seven face-down — should NOT resolve the trigger
        seven = Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_DOWN)
        game._apply_wild_card_rules_to_card(seven, wild_rules, face_up=False)

        assert game.follow_trigger_pending is True  # Still pending
        assert game.follow_card_wild_rank is None

    def test_second_trigger_resets_wild(self):
        """Second trigger card should clear previous wild and reset pending."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Queen → 7 (7s are wild)
        queen1 = Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP)
        game._apply_wild_card_rules_to_card(queen1, wild_rules, face_up=True)
        seven = Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_UP)
        game._apply_wild_card_rules_to_card(seven, wild_rules, face_up=True)
        assert game.follow_card_wild_rank == Rank.SEVEN

        # Another queen — should clear 7s wild and reset
        queen2 = Card(Rank.QUEEN, Suit.SPADES, Visibility.FACE_UP)
        game._apply_wild_card_rules_to_card(queen2, wild_rules, face_up=True)
        assert game.follow_trigger_pending is True
        assert game.follow_card_wild_rank is None

    def test_second_trigger_then_new_card(self):
        """Queen → 7 → Queen → King should make Kings wild (not 7s)."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Queen → 7
        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(
            Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_UP), wild_rules, face_up=True
        )

        # Queen → King
        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.SPADES, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(Card(Rank.KING, Suit.CLUBS, Visibility.FACE_UP), wild_rules, face_up=True)

        assert game.follow_card_wild_rank == Rank.KING
        assert game.follow_trigger_pending is False

    def test_consecutive_triggers(self):
        """Queen → Queen → 7 should make 7s wild."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.SPADES, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(
            Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_UP), wild_rules, face_up=True
        )

        assert game.follow_card_wild_rank == Rank.SEVEN

    def test_last_face_up_is_trigger_no_wilds(self):
        """If the last face-up card is a trigger, no wilds from this rule."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Deal some cards, ending with a queen
        game._apply_wild_card_rules_to_card(Card(Rank.FIVE, Suit.HEARTS, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP), wild_rules, face_up=True)

        assert game.follow_trigger_pending is True
        assert game.follow_card_wild_rank is None

    def test_no_trigger_no_wilds(self):
        """If no trigger card is ever dealt, no wilds from this rule."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        game._apply_wild_card_rules_to_card(Card(Rank.FIVE, Suit.HEARTS, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(
            Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_UP), wild_rules, face_up=True
        )

        assert game.follow_trigger_pending is False
        assert game.follow_card_wild_rank is None


class TestFollowCardExistingCards:
    """Test that follow_card correctly updates wild status on existing cards."""

    def test_existing_cards_of_same_rank_become_wild(self):
        """When a rank becomes wild, existing player cards of that rank should be wild."""
        game = create_follow_queen_game()
        game.add_player("p2", "Charlie", 500)  # Need a player to hold cards
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Give p0 a seven in hand
        seven_hand = Card(Rank.SEVEN, Suit.CLUBS, Visibility.FACE_DOWN)
        game.table.players["p0"].hand.add_card(seven_hand)

        # Queen triggers, then seven follows → all 7s are wild
        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(
            Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_UP), wild_rules, face_up=True
        )

        # The existing seven in p0's hand should now be wild
        assert seven_hand.is_wild

    def test_wild_removed_when_new_trigger_appears(self):
        """When a new trigger appears, old wild cards should lose wild status."""
        game = create_follow_queen_game()
        wild_rules = [{"type": "follow_card", "trigger_rank": "Q", "role": "wild", "scope": "global", "match": "rank"}]

        # Give p0 a seven
        seven_hand = Card(Rank.SEVEN, Suit.CLUBS, Visibility.FACE_DOWN)
        game.table.players["p0"].hand.add_card(seven_hand)

        # Queen → 7 (7s wild)
        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.HEARTS, Visibility.FACE_UP), wild_rules, face_up=True)
        game._apply_wild_card_rules_to_card(
            Card(Rank.SEVEN, Suit.DIAMONDS, Visibility.FACE_UP), wild_rules, face_up=True
        )
        assert seven_hand.is_wild

        # Another queen → clears 7s
        game._apply_wild_card_rules_to_card(Card(Rank.QUEEN, Suit.SPADES, Visibility.FACE_UP), wild_rules, face_up=True)
        assert not seven_hand.is_wild


class TestFollowCardFullGame:
    """Integration test: play a Follow the Queen hand to completion."""

    def test_follow_queen_smoke(self):
        """Follow the Queen game can load, play, and complete."""
        rules = GameRules.from_json(FOLLOW_QUEEN_JSON)
        game = Game(
            rules=rules,
            structure=BettingStructure.LIMIT,
            small_bet=10,
            big_bet=20,
            bring_in=5,
            ante=2,
            min_buyin=20,
            max_buyin=10000,
            auto_progress=False,
        )
        game.add_player("p0", "Alice", 500)
        game.add_player("p1", "Bob", 500)

        game.start_hand(shuffle_deck=True)
        actions_taken = 0
        max_actions = 300

        while game.state != GameState.COMPLETE and actions_taken < max_actions:
            if game.state == GameState.BETTING:
                if game.current_player is None:
                    game._next_step()
                    actions_taken += 1
                    continue

                player_id = game.current_player.id
                valid = game.get_valid_actions(player_id)
                if not valid:
                    game._next_step()
                    actions_taken += 1
                    continue

                action_map = {a[0]: (a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else None) for a in valid}

                if PlayerAction.CHECK in action_map:
                    result = game.player_action(player_id, PlayerAction.CHECK)
                elif PlayerAction.CALL in action_map:
                    min_amt, _ = action_map[PlayerAction.CALL]
                    result = game.player_action(player_id, PlayerAction.CALL, min_amt)
                elif PlayerAction.FOLD in action_map:
                    result = game.player_action(player_id, PlayerAction.FOLD)
                elif PlayerAction.BET in action_map:
                    min_amt, _ = action_map[PlayerAction.BET]
                    result = game.player_action(player_id, PlayerAction.BET, min_amt)
                elif PlayerAction.COMPLETE in action_map:
                    min_amt, _ = action_map[PlayerAction.COMPLETE]
                    result = game.player_action(player_id, PlayerAction.COMPLETE, min_amt)
                else:
                    action, (min_amt, max_amt) = next(iter(action_map.items()))
                    result = game.player_action(player_id, action, min_amt or 0)

                if result and result.advance_step:
                    game._next_step()
            else:
                game._next_step()

            actions_taken += 1

        assert (
            game.state == GameState.COMPLETE
        ), f"Game stuck in {game.state} after {actions_taken} actions (step {game.current_step})"

        # Chip conservation
        total_chips = sum(p.stack for p in game.table.players.values())
        assert total_chips == 1000
