"""Simple bot player for demo purposes."""

import logging
import random

from generic_poker.game.game import PlayerAction

logger = logging.getLogger(__name__)


class SimpleBot:
    """A very basic bot that makes random valid actions."""

    def __init__(self, player_id: str, username: str):
        self.player_id = player_id
        self.username = username
        self.is_bot = True

    def choose_action(
        self, valid_actions: list[tuple], pot_amount: int = 0, stack: int = 0
    ) -> tuple[PlayerAction, int | None]:
        """Choose an action from the valid actions list.

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
                action_type, min_amount, max_amount = action_tuple

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

            action_type, min_amount, max_amount = chosen_action

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
            action_type, min_amount, max_amount = first_action
            return action_type, min_amount

    @staticmethod
    def is_bot_player(player_id: str) -> bool:
        """Check if a player ID represents a bot/demo player."""
        return player_id.startswith("demo_player_") or player_id.startswith("bot_")


class BotManager:
    """Manages bot players for tables."""

    def __init__(self):
        self.bots = {}

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


# Global bot manager instance
bot_manager = BotManager()
