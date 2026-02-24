"""Simple bot player for demo purposes."""

import logging
import random
from dataclasses import dataclass

from generic_poker.core.card import Visibility
from generic_poker.game.game import PlayerAction

logger = logging.getLogger(__name__)

BOT_NAMES = [
    "Alice Bot",
    "Bob Bot",
    "Charlie Bot",
    "Diana Bot",
    "Eve Bot",
    "Frank Bot",
    "Grace Bot",
    "Hank Bot",
    "Ivy Bot",
]


@dataclass
class BotDecision:
    """Represents a bot's chosen action with all necessary parameters."""

    action: PlayerAction
    amount: int | None = None
    cards: list | None = None
    declaration_data: list | None = None


class SimpleBot:
    """A very basic bot that makes random valid actions."""

    def __init__(self, player_id: str, username: str):
        self.player_id = player_id
        self.username = username
        self.is_bot = True

    def choose_action(
        self, valid_actions: list[tuple], pot_amount: int = 0, stack: int = 0
    ) -> tuple[PlayerAction, int | None]:
        """Choose an action from the valid actions list (betting actions only).

        Strategy:
        - Never fold when check is available (folding a free option is irrational)
        - Check/call most of the time, occasionally bet/raise
        - Fold facing a bet/raise ~20% of the time
        """
        if not valid_actions:
            logger.warning(f"Bot {self.username} has no valid actions")
            return PlayerAction.FOLD, None

        try:
            action_types = {a[0] for a in valid_actions}
            can_check = PlayerAction.CHECK in action_types

            action_weights = {}
            for action_tuple in valid_actions:
                action_type = action_tuple[0]
                min_amount = action_tuple[1] if len(action_tuple) > 1 else None
                max_amount = action_tuple[2] if len(action_tuple) > 2 else None

                if action_type == PlayerAction.FOLD:
                    # Never fold when check is available
                    action_weights[action_tuple] = 0 if can_check else 20
                elif action_type == PlayerAction.CHECK:
                    action_weights[action_tuple] = 70
                elif action_type == PlayerAction.CALL:
                    action_weights[action_tuple] = 60
                elif action_type in [PlayerAction.BET, PlayerAction.RAISE]:
                    action_weights[action_tuple] = 20
                else:
                    action_weights[action_tuple] = 5

            # Choose weighted random action
            actions = list(action_weights.keys())
            weights = list(action_weights.values())
            chosen_action = random.choices(actions, weights=weights)[0]

            action_type = chosen_action[0]
            min_amount = chosen_action[1] if len(chosen_action) > 1 else None
            max_amount = chosen_action[2] if len(chosen_action) > 2 else None

            # Determine amount for betting actions
            amount = None
            if action_type in [PlayerAction.BET, PlayerAction.RAISE, PlayerAction.CALL]:
                if min_amount is not None:
                    if max_amount is not None and max_amount > min_amount:
                        # Choose a random amount between min and max, favoring smaller amounts
                        range_size = max_amount - min_amount
                        # Use exponential distribution to favor smaller bets
                        random_factor = random.expovariate(2.0)  # Lambda = 2 for moderate bias
                        random_factor = min(random_factor, 1.0)  # Cap at 1.0
                        amount = min_amount + int(range_size * random_factor)
                    else:
                        amount = min_amount

            logger.info(f"Bot {self.username} chose action: {action_type.value} {amount if amount else ''}")
            return action_type, amount

        except Exception as e:
            logger.error(f"Bot {self.username} error choosing action: {e}")
            # Fallback to first valid action
            first_action = valid_actions[0]
            return first_action[0], first_action[1] if len(first_action) > 1 else None

    def choose_action_full(self, valid_actions: list[tuple], game=None, player_id: str | None = None) -> BotDecision:
        """Choose an action from the valid actions list, handling ALL action types.

        Args:
            valid_actions: List of action tuples from game.get_valid_actions()
            game: The Game object (for hand/card access)
            player_id: The player ID (defaults to self.player_id)

        Returns:
            BotDecision with action, amount, cards, and/or declaration_data
        """
        if not valid_actions:
            logger.warning(f"Bot {self.username} has no valid actions")
            return BotDecision(action=PlayerAction.FOLD)

        pid = player_id or self.player_id

        try:
            # Check what type of action we're dealing with
            first_action_type = valid_actions[0][0]

            # DRAW / DISCARD — select random cards to discard
            if first_action_type in (PlayerAction.DRAW, PlayerAction.DISCARD):
                return self._choose_draw_action(valid_actions[0], game, pid)

            # EXPOSE — expose minimum required face-down cards
            if first_action_type == PlayerAction.EXPOSE:
                return self._choose_expose_action(valid_actions[0], game, pid)

            # PASS — pass random cards
            if first_action_type == PlayerAction.PASS:
                return self._choose_pass_action(valid_actions[0], game, pid)

            # SEPARATE — shuffle cards into subsets
            if first_action_type == PlayerAction.SEPARATE:
                return self._choose_separate_action(valid_actions[0], game, pid)

            # DECLARE — always declare "high"
            if first_action_type == PlayerAction.DECLARE:
                return self._choose_declare_action(game)

            # CHOOSE — pick first option
            if first_action_type == PlayerAction.CHOOSE:
                return BotDecision(action=PlayerAction.CHOOSE, amount=0)

            # BRING_IN / COMPLETE — take minimum amount
            if first_action_type == PlayerAction.BRING_IN:
                min_amt = valid_actions[0][1] if len(valid_actions[0]) > 1 else 0
                return BotDecision(action=PlayerAction.BRING_IN, amount=min_amt)

            if first_action_type == PlayerAction.COMPLETE:
                min_amt = valid_actions[0][1] if len(valid_actions[0]) > 1 else 0
                return BotDecision(action=PlayerAction.COMPLETE, amount=min_amt)

            # Standard betting actions — use existing weighted logic
            action, amount = self.choose_action(valid_actions)
            return BotDecision(action=action, amount=amount)

        except Exception as e:
            logger.error(f"Bot {self.username} error in choose_action_full: {e}")
            # Fallback: try choose_action for betting, or return first action
            try:
                action, amount = self.choose_action(valid_actions)
                return BotDecision(action=action, amount=amount)
            except Exception:
                first = valid_actions[0]
                return BotDecision(action=first[0], amount=first[1] if len(first) > 1 else None)

    def _choose_draw_action(self, action_tuple: tuple, game, player_id: str) -> BotDecision:
        """Choose cards to discard for a draw/discard action."""
        action_type = action_tuple[0]
        min_cards = action_tuple[1] if len(action_tuple) > 1 else 0
        max_cards = action_tuple[2] if len(action_tuple) > 2 else 0
        min_cards = min_cards or 0
        max_cards = max_cards or 0

        # Get player's hand
        cards_to_discard = []
        if game and player_id in game.table.players:
            player = game.table.players[player_id]
            hand_cards = list(player.hand.get_cards()) if player.hand else []

            if hand_cards and max_cards > 0:
                # Discard a random number of cards between min and max
                num_discard = random.randint(min_cards, min(max_cards, len(hand_cards)))
                cards_to_discard = random.sample(hand_cards, num_discard)

        logger.info(f"Bot {self.username} {action_type.value}: discarding {len(cards_to_discard)} cards")
        return BotDecision(action=action_type, amount=0, cards=cards_to_discard)

    def _choose_expose_action(self, action_tuple: tuple, game, player_id: str) -> BotDecision:
        """Choose cards to expose — expose minimum required face-down cards."""
        min_cards = action_tuple[1] if len(action_tuple) > 1 else 1
        min_cards = min_cards or 1

        cards_to_expose = []
        if game and player_id in game.table.players:
            player = game.table.players[player_id]
            hand_cards = list(player.hand.get_cards()) if player.hand else []

            # Filter to face-down cards only
            face_down_cards = [c for c in hand_cards if c.visibility == Visibility.FACE_DOWN]

            if face_down_cards:
                num_expose = min(min_cards, len(face_down_cards))
                cards_to_expose = random.sample(face_down_cards, num_expose)

        logger.info(f"Bot {self.username} expose: exposing {len(cards_to_expose)} cards")
        return BotDecision(action=PlayerAction.EXPOSE, amount=0, cards=cards_to_expose)

    def _choose_pass_action(self, action_tuple: tuple, game, player_id: str) -> BotDecision:
        """Choose cards to pass — select exact count required."""
        num_cards = action_tuple[2] if len(action_tuple) > 2 else (action_tuple[1] if len(action_tuple) > 1 else 1)
        num_cards = num_cards or 1

        cards_to_pass = []
        if game and player_id in game.table.players:
            player = game.table.players[player_id]
            hand_cards = list(player.hand.get_cards()) if player.hand else []

            if hand_cards:
                actual_count = min(num_cards, len(hand_cards))
                cards_to_pass = random.sample(hand_cards, actual_count)

        logger.info(f"Bot {self.username} pass: passing {len(cards_to_pass)} cards")
        return BotDecision(action=PlayerAction.PASS, amount=0, cards=cards_to_pass)

    def _choose_separate_action(self, action_tuple: tuple, game, player_id: str) -> BotDecision:
        """Choose how to separate cards into subsets — shuffle and split."""
        cards_ordered = []
        if game and player_id in game.table.players:
            player = game.table.players[player_id]
            hand_cards = list(player.hand.get_cards()) if player.hand else []

            if hand_cards:
                # Shuffle the hand and return all cards in random order
                # The engine will split them by subset sizes from config
                cards_ordered = list(hand_cards)
                random.shuffle(cards_ordered)

        logger.info(f"Bot {self.username} separate: ordering {len(cards_ordered)} cards")
        return BotDecision(action=PlayerAction.SEPARATE, amount=0, cards=cards_ordered)

    def _choose_declare_action(self, game) -> BotDecision:
        """Choose declaration — always declare 'high'."""
        declaration = "high"
        # Check if game has declare config with available options
        if game and hasattr(game, "current_declare_config"):
            config = game.current_declare_config
            options = config.get("options", ["high"])
            if options:
                declaration = options[0]  # Pick first available (usually "high")

        declaration_data = [{"pot_index": -1, "declaration": declaration}]
        logger.info(f"Bot {self.username} declare: {declaration}")
        return BotDecision(action=PlayerAction.DECLARE, amount=0, declaration_data=declaration_data)

    @staticmethod
    def is_bot_player(player_id: str) -> bool:
        """Check if a player ID represents a bot/demo player."""
        return player_id.startswith("demo_player_") or player_id.startswith("bot_")


class BotManager:
    """Manages bot players for tables."""

    def __init__(self):
        self.bots: dict[str, SimpleBot] = {}

    def create_bot(self, player_id: str, username: str) -> SimpleBot:
        """Create a new bot player."""
        bot = SimpleBot(player_id, username)
        self.bots[player_id] = bot
        logger.info(f"Created bot player: {username} ({player_id})")
        return bot

    def get_bot(self, player_id: str) -> SimpleBot | None:
        """Get a bot by player ID."""
        return self.bots.get(player_id)

    def is_bot(self, player_id: str) -> bool:
        """Check if a player is a bot."""
        return SimpleBot.is_bot_player(player_id) or player_id in self.bots

    def remove_bot(self, player_id: str):
        """Remove a bot."""
        if player_id in self.bots:
            del self.bots[player_id]
            logger.info(f"Removed bot player: {player_id}")

    def remove_all_bots_for_table(self, table_id: str):
        """Remove all bots for a given table (identified by table_id prefix in bot ID)."""
        to_remove = [pid for pid in self.bots if pid.startswith(f"bot_{table_id[:8]}_")]
        for pid in to_remove:
            del self.bots[pid]
        if to_remove:
            logger.info(f"Removed {len(to_remove)} bots for table {table_id}")


# Global bot manager instance
bot_manager = BotManager()
