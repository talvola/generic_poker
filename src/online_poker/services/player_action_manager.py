"""Service for managing player actions and betting interface."""

import logging
from datetime import datetime
from threading import Lock, Timer
from typing import Any

from generic_poker.game.betting import BettingStructure
from generic_poker.game.game_state import GameState, PlayerAction

from ..services.disconnect_manager import disconnect_manager
from ..services.game_orchestrator import GameSession, game_orchestrator
from ..services.websocket_manager import GameEvent, get_websocket_manager

logger = logging.getLogger(__name__)


class PlayerActionOption:
    """Represents a player action option with validation and display information."""

    def __init__(
        self,
        action_type: PlayerAction,
        min_amount: int | None = None,
        max_amount: int | None = None,
        default_amount: int | None = None,
        display_text: str = "",
        button_style: str = "default",
    ):
        """Initialize a player action option.

        Args:
            action_type: The type of action (fold, call, bet, etc.)
            min_amount: Minimum amount for betting actions
            max_amount: Maximum amount for betting actions
            default_amount: Default/suggested amount
            display_text: Text to display on the action button
            button_style: CSS style class for the button
        """
        self.action_type = action_type
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.default_amount = default_amount
        self.display_text = display_text
        self.button_style = button_style

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_type": self.action_type.value if self.action_type else None,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "default_amount": self.default_amount,
            "display_text": self.display_text,
            "button_style": self.button_style,
        }


class ActionValidation:
    """Result of action validation."""

    def __init__(self, is_valid: bool, error_message: str | None = None, suggested_amount: int | None = None):
        """Initialize action validation result.

        Args:
            is_valid: Whether the action is valid
            error_message: Error message if invalid
            suggested_amount: Suggested amount if the provided amount was invalid
        """
        self.is_valid = is_valid
        self.error_message = error_message
        self.suggested_amount = suggested_amount


class ActionTimeoutManager:
    """Manages action timeouts for players."""

    def __init__(self):
        """Initialize the timeout manager."""
        self.active_timers: dict[str, Timer] = {}  # user_id -> Timer
        self.timeout_callbacks: dict[str, callable] = {}  # user_id -> callback
        self.lock = Lock()

    def set_timeout(self, user_id: str, seconds: int, callback: callable) -> None:
        """Set a timeout for a player action.

        Args:
            user_id: ID of the player
            seconds: Timeout in seconds
            callback: Function to call when timeout expires
        """
        with self.lock:
            # Cancel existing timer if any
            self.cancel_timeout(user_id)

            # Create new timer
            timer = Timer(seconds, self._handle_timeout, args=[user_id])
            self.active_timers[user_id] = timer
            self.timeout_callbacks[user_id] = callback

            timer.start()
            logger.debug(f"Set {seconds}s timeout for player {user_id}")

    def cancel_timeout(self, user_id: str) -> None:
        """Cancel a player's timeout.

        Args:
            user_id: ID of the player
        """
        timer = self.active_timers.pop(user_id, None)
        if timer:
            timer.cancel()
            self.timeout_callbacks.pop(user_id, None)
            logger.debug(f"Cancelled timeout for player {user_id}")

    def get_remaining_time(self, user_id: str) -> int:
        """Get remaining time for a player's timeout.

        Args:
            user_id: ID of the player

        Returns:
            Remaining seconds, or 0 if no timeout active
        """
        # This is a simplified implementation - in practice, you'd need to track start times
        return 30 if user_id in self.active_timers else 0

    def _handle_timeout(self, user_id: str) -> None:
        """Handle timeout expiration for a player.

        Args:
            user_id: ID of the player whose timeout expired
        """
        with self.lock:
            callback = self.timeout_callbacks.pop(user_id, None)
            self.active_timers.pop(user_id, None)

            if callback:
                try:
                    callback(user_id)
                except Exception as e:
                    logger.error(f"Error in timeout callback for player {user_id}: {e}")


class PlayerActionManager:
    """Manages player actions, validation, and timeouts."""

    def __init__(self):
        """Initialize the player action manager."""
        self.timeout_manager = ActionTimeoutManager()
        self.action_history: dict[str, list[dict[str, Any]]] = {}  # table_id -> action history
        self.lock = Lock()

        logger.info("Player action manager initialized")

    def get_available_actions(self, table_id: str, user_id: str) -> list[PlayerActionOption]:
        """Get available actions for a player using the game engine.

        Args:
            table_id: ID of the table
            user_id: ID of the player

        Returns:
            List of available action options
        """
        try:
            # Get game session
            session = game_orchestrator.get_session(table_id)
            if not session or not session.game:
                logger.warning(f"No game session found for table {table_id}")
                return []

            # Check if it's the player's turn
            if not self._is_current_player(session, user_id):
                return []

            # Get valid actions from the game engine
            try:
                valid_actions = session.game.get_valid_actions(user_id)
            except Exception as e:
                logger.error(f"Failed to get valid actions from game engine: {e}")
                return []

            # Convert game engine actions to our action options
            action_options = []
            for action_tuple in valid_actions:
                action_type = action_tuple[0]
                min_amount = action_tuple[1] if len(action_tuple) > 1 else None
                max_amount = action_tuple[2] if len(action_tuple) > 2 else None

                # Create action option with proper display text and styling
                option = self._create_action_option(action_type, min_amount, max_amount, session)
                if option:
                    action_options.append(option)

            logger.debug(f"Found {len(action_options)} valid actions for player {user_id}")
            return action_options

        except Exception as e:
            logger.error(f"Failed to get available actions for player {user_id}: {e}")
            return []

    def _create_action_option(
        self, action_type: PlayerAction, min_amount: int | None, max_amount: int | None, session: GameSession
    ) -> PlayerActionOption | None:
        """Create an action option from game engine data.

        Args:
            action_type: The action type from the game engine
            min_amount: Minimum amount from game engine
            max_amount: Maximum amount from game engine
            session: Game session for context

        Returns:
            PlayerActionOption or None if invalid
        """
        try:
            # Determine display text and styling based on action type
            if action_type == PlayerAction.FOLD:
                return PlayerActionOption(action_type=action_type, display_text="Fold", button_style="danger")

            elif action_type == PlayerAction.CHECK:
                return PlayerActionOption(action_type=action_type, display_text="Check", button_style="secondary")

            elif action_type == PlayerAction.CALL:
                # Get the amount to call
                call_amount = min_amount or 0
                display_text = f"Call ${call_amount}" if call_amount > 0 else "Call"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=call_amount,
                    max_amount=call_amount,
                    default_amount=call_amount,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.BET:
                # Determine default bet amount based on betting structure
                default_amount = self._get_default_bet_amount(session, min_amount, max_amount)
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    default_amount=default_amount,
                    display_text="Bet",
                    button_style="success",
                )

            elif action_type == PlayerAction.RAISE:
                # Determine default raise amount
                default_amount = self._get_default_raise_amount(session, min_amount, max_amount)
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    default_amount=default_amount,
                    display_text="Raise",
                    button_style="warning",
                )

            elif action_type == PlayerAction.DRAW:
                max_cards = max_amount or 0
                min_cards = min_amount or 0
                if min_cards == 0:
                    display_text = f"Draw 0-{max_cards}"
                else:
                    display_text = f"Draw {min_cards}-{max_cards}"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=min_cards,
                    max_amount=max_cards,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.DISCARD:
                max_cards = max_amount or 0
                min_cards = min_amount or 0
                if min_cards == 0:
                    display_text = f"Discard 0-{max_cards}"
                else:
                    display_text = f"Discard {min_cards}-{max_cards}"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=min_cards,
                    max_amount=max_cards,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.PASS:
                num_cards = max_amount or 0
                display_text = f"Pass {num_cards} card{'s' if num_cards != 1 else ''}"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=num_cards,
                    max_amount=num_cards,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.EXPOSE:
                num_cards = max_amount or 0
                min_cards = min_amount or num_cards
                if min_cards != num_cards:
                    display_text = f"Expose {min_cards}-{num_cards}"
                else:
                    display_text = f"Expose {num_cards}"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=min_cards,
                    max_amount=num_cards,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.SEPARATE:
                total = max_amount or 0
                display_text = f"Separate {total} cards"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=total,
                    max_amount=total,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.DECLARE:
                display_text = "Declare"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=0,
                    max_amount=0,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.CHOOSE:
                display_text = "Choose"
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=min_amount or 0,
                    max_amount=max_amount or 0,
                    display_text=display_text,
                    button_style="primary",
                )

            elif action_type == PlayerAction.BRING_IN:
                bring_in_amount = min_amount or 0
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=bring_in_amount,
                    max_amount=bring_in_amount,
                    default_amount=bring_in_amount,
                    display_text=f"Bring In ${bring_in_amount}" if bring_in_amount > 0 else "Bring In",
                    button_style="primary",
                )

            elif action_type == PlayerAction.COMPLETE:
                complete_amount = min_amount or 0
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=complete_amount,
                    max_amount=complete_amount,
                    default_amount=complete_amount,
                    display_text=f"Complete ${complete_amount}" if complete_amount > 0 else "Complete",
                    button_style="warning",
                )

            else:
                # Handle other action types (for future expansion)
                return PlayerActionOption(
                    action_type=action_type,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    display_text=action_type.value.replace("_", " ").title(),
                    button_style="default",
                )

        except Exception as e:
            logger.error(f"Failed to create action option for {action_type}: {e}")
            return None

    def _get_default_bet_amount(
        self, session: GameSession, min_amount: int | None, max_amount: int | None
    ) -> int | None:
        """Get default bet amount based on betting structure.

        Args:
            session: Game session
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount

        Returns:
            Default bet amount
        """
        try:
            if not min_amount:
                return None

            # For limit games, use the fixed bet size
            if session.table.betting_structure == BettingStructure.LIMIT.value:
                return min_amount

            # For no-limit and pot-limit, suggest a reasonable default
            # This could be enhanced with more sophisticated logic
            pot_size = self._get_current_pot_size(session)

            # Suggest half-pot bet as default
            suggested = max(min_amount, pot_size // 2) if pot_size > 0 else min_amount

            # Ensure it's within bounds
            if max_amount:
                suggested = min(suggested, max_amount)

            return suggested

        except Exception as e:
            logger.error(f"Failed to get default bet amount: {e}")
            return min_amount

    def _get_default_raise_amount(
        self, session: GameSession, min_amount: int | None, max_amount: int | None
    ) -> int | None:
        """Get default raise amount based on betting structure.

        Args:
            session: Game session
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount

        Returns:
            Default raise amount
        """
        try:
            if not min_amount:
                return None

            # For limit games, use the fixed raise size
            if session.table.betting_structure == BettingStructure.LIMIT.value:
                return min_amount

            # For no-limit and pot-limit, suggest a reasonable default
            # This could be enhanced with more sophisticated logic
            pot_size = self._get_current_pot_size(session)

            # Suggest minimum raise + half pot as default
            suggested = min_amount + (pot_size // 2) if pot_size > 0 else min_amount

            # Ensure it's within bounds
            if max_amount:
                suggested = min(suggested, max_amount)

            return suggested

        except Exception as e:
            logger.error(f"Failed to get default raise amount: {e}")
            return min_amount

    def _get_current_pot_size(self, session: GameSession) -> int:
        """Get current pot size from the game session.

        Args:
            session: Game session

        Returns:
            Current pot size
        """
        try:
            if session.game and hasattr(session.game, "betting"):
                return session.game.betting.get_main_pot_amount()
            return 0
        except Exception as e:
            logger.error(f"Failed to get pot size: {e}")
            return 0

    def validate_action(
        self, table_id: str, user_id: str, action: PlayerAction, amount: int | None = None, cards: list | None = None
    ) -> ActionValidation:
        """Validate a player action before processing.

        Args:
            table_id: ID of the table
            user_id: ID of the player
            action: The action being attempted
            amount: Amount for betting actions
            cards: Cards for draw/discard actions

        Returns:
            ActionValidation result
        """
        try:
            # Get game session
            session = game_orchestrator.get_session(table_id)
            if not session or not session.game:
                return ActionValidation(False, "Game session not found")

            # Check if game is active
            if not session.is_active or session.is_paused:
                return ActionValidation(False, "Game is not active")

            # Check if player is in the game (check game engine, not WebSocket connection)
            # The player should be in the game's table.players dict
            if not session.game or user_id not in session.game.table.players:
                return ActionValidation(False, "Player not in game")

            # Check if it's the player's turn
            current_player_id = self._get_current_player(session)
            logger.info(f"Action validation: user_id={user_id}, current_player_id={current_player_id}")
            if not self._is_current_player(session, user_id):
                logger.warning(f"Turn check failed: user_id={user_id} != current_player={current_player_id}")
                return ActionValidation(False, "Not your turn to act")

            # Get valid actions from game engine
            valid_actions = session.game.get_valid_actions(user_id)

            # Check if the action is valid
            action_valid = False
            valid_min = None
            valid_max = None

            for valid_tuple in valid_actions:
                valid_action = valid_tuple[0]
                min_amt = valid_tuple[1] if len(valid_tuple) > 1 else None
                max_amt = valid_tuple[2] if len(valid_tuple) > 2 else None
                if valid_action == action:
                    action_valid = True
                    valid_min = min_amt
                    valid_max = max_amt
                    break

            if not action_valid:
                return ActionValidation(False, f"Action {action.value} is not valid")

            # Validate amount for betting actions
            if action in [PlayerAction.BET, PlayerAction.RAISE, PlayerAction.CALL]:
                if amount is None:
                    return ActionValidation(False, "Amount required for betting action")

                if valid_min is not None and amount < valid_min:
                    return ActionValidation(False, f"Amount too low (minimum: {valid_min})", valid_min)

                if valid_max is not None and amount > valid_max:
                    return ActionValidation(False, f"Amount too high (maximum: {valid_max})", valid_max)

            # Validate card count for draw/discard/pass/expose/separate actions
            if action in [
                PlayerAction.DRAW,
                PlayerAction.DISCARD,
                PlayerAction.PASS,
                PlayerAction.EXPOSE,
                PlayerAction.SEPARATE,
            ]:
                card_count = len(cards) if cards else 0
                min_cards = valid_min or 0
                max_cards = valid_max or 0
                if card_count < min_cards:
                    return ActionValidation(False, f"Must select at least {min_cards} cards")
                if max_cards > 0 and card_count > max_cards:
                    return ActionValidation(False, f"Cannot select more than {max_cards} cards")

            return ActionValidation(True)

        except Exception as e:
            logger.error(f"Failed to validate action for player {user_id}: {e}")
            return ActionValidation(False, f"Validation error: {str(e)}")

    def process_player_action(
        self,
        table_id: str,
        user_id: str,
        action: PlayerAction,
        amount: int | None = None,
        cards: list | None = None,
        declaration_data=None,
    ) -> tuple[bool, str, Any]:
        """Process a validated player action.

        Args:
            table_id: ID of the table
            user_id: ID of the player
            action: The action being taken
            amount: Amount for betting actions
            cards: Cards for draw/discard actions
            declaration_data: Declaration data for declare actions

        Returns:
            Tuple of (success, message, result)
        """
        try:
            # Validate the action first
            validation = self.validate_action(table_id, user_id, action, amount, cards=cards)
            if not validation.is_valid:
                return False, validation.error_message, None

            # Get game session
            session = game_orchestrator.get_session(table_id)
            if not session:
                return False, "Game session not found", None

            # Cancel any active timeout for this player
            self.timeout_manager.cancel_timeout(user_id)

            # Process the action through the game session
            success, message, result = session.process_player_action(
                user_id, action, amount or 0, cards=cards, declaration_data=declaration_data
            )

            if success:
                # Check if we need to advance to the next step (betting round complete)
                game = session.game
                if result and hasattr(result, "advance_step") and result.advance_step:
                    if game and game.state != GameState.COMPLETE:
                        logger.info("Betting round complete, advancing to next step")
                        game._next_step()
                        game_orchestrator.advance_through_non_player_steps(game)
                        logger.info(
                            f"Game advanced to step {game.current_step}, state {game.state}, current_player: {game.current_player.name if game.current_player else None}"
                        )

                # Record the action in history
                self._record_action(table_id, user_id, action, amount, datetime.utcnow())

                # Notify other players via WebSocket
                self._broadcast_player_action(table_id, user_id, action, amount, result, cards=cards)

                # Check if hand is complete (showdown finished)
                if session.game and session.game.state.name == "COMPLETE":
                    self._handle_hand_completion(table_id, session)
                else:
                    # Hand still in progress - check if new current player is pending leave
                    if session.pending_leaves:
                        self._auto_fold_pending_players(table_id, session)

                # Start timeout for next player if needed
                self._start_next_player_timeout(session)

                # Trigger bot actions if next player is a bot
                if session.game and session.game.state != GameState.COMPLETE:
                    from ..services.bot_action_service import BotActionService

                    BotActionService.trigger_bot_actions_if_needed(table_id)

                logger.info(f"Processed action {action.value} for player {user_id} at table {table_id}")

            return success, message, result

        except Exception as e:
            logger.error(f"Failed to process action for player {user_id}: {e}")
            return False, f"Processing error: {str(e)}", None

    def start_action_timer(self, table_id: str, user_id: str, timeout_seconds: int | None = None) -> None:
        """Start an action timer for a player.

        Args:
            table_id: ID of the table
            user_id: ID of the player
            timeout_seconds: Timeout in seconds (defaults to Flask config ACTION_TIMEOUT_SECONDS)
        """
        try:
            # Read timeout settings from Flask config with safe fallback
            try:
                from flask import current_app

                enabled = current_app.config.get("ACTION_TIMEOUT_ENABLED", False)
                if timeout_seconds is None:
                    timeout_seconds = current_app.config.get("ACTION_TIMEOUT_SECONDS", 30)
            except RuntimeError:
                # Outside Flask request context
                enabled = False
                if timeout_seconds is None:
                    timeout_seconds = 30

            # Skip if action timeout is disabled
            if not enabled:
                logger.debug(f"Action timeout disabled, skipping timer for player {user_id}")
                return

            def timeout_callback(timed_out_user_id: str):
                self._handle_action_timeout(table_id, timed_out_user_id)

            self.timeout_manager.set_timeout(user_id, timeout_seconds, timeout_callback)

            # Notify player of timeout via WebSocket
            ws_manager = get_websocket_manager()
            if ws_manager:
                timeout_data = {
                    "user_id": user_id,
                    "table_id": table_id,
                    "timeout_seconds": timeout_seconds,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                ws_manager.send_to_user(user_id, GameEvent.ACTION_TIMEOUT_STARTED, timeout_data)

            logger.debug(f"Started {timeout_seconds}s action timer for player {user_id}")

        except Exception as e:
            logger.error(f"Failed to start action timer for player {user_id}: {e}")

    def _handle_action_timeout(self, table_id: str, user_id: str) -> None:
        """Handle action timeout for a player.

        Args:
            table_id: ID of the table
            user_id: ID of the player who timed out
        """
        try:
            logger.info(f"Action timeout for player {user_id} at table {table_id}")

            # Check if player is disconnected - if so, let disconnect manager handle it
            if disconnect_manager.is_player_disconnected(user_id):
                logger.debug(f"Player {user_id} is disconnected, letting disconnect manager handle timeout")
                return

            # Auto-fold the player
            success, message, result = self.process_player_action(table_id, user_id, PlayerAction.FOLD)

            if success:
                # Notify all players of the auto-fold
                ws_manager = get_websocket_manager()
                if ws_manager:
                    timeout_data = {
                        "user_id": user_id,
                        "table_id": table_id,
                        "action": "fold",
                        "reason": "timeout",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                    ws_manager.broadcast_to_table(table_id, GameEvent.PLAYER_ACTION_TIMEOUT, timeout_data)

                logger.info(f"Auto-folded player {user_id} due to timeout")
            else:
                logger.error(f"Failed to auto-fold player {user_id}: {message}")

        except Exception as e:
            logger.error(f"Failed to handle action timeout for player {user_id}: {e}")

    def _start_next_player_timeout(self, session: GameSession) -> None:
        """Start timeout for the next player to act.

        Args:
            session: Game session
        """
        try:
            # Get current player
            current_player = self._get_current_player(session)
            if current_player and session.game.state in (GameState.BETTING, GameState.DRAWING):
                # Start timeout for the current player
                self.start_action_timer(session.table.id, current_player)

        except Exception as e:
            logger.error(f"Failed to start next player timeout: {e}")

    def _record_action(
        self, table_id: str, user_id: str, action: PlayerAction, amount: int | None, timestamp: datetime
    ) -> None:
        """Record a player action in the history.

        Args:
            table_id: ID of the table
            user_id: ID of the player
            action: The action taken
            amount: Amount for betting actions
            timestamp: When the action occurred
        """
        try:
            with self.lock:
                if table_id not in self.action_history:
                    self.action_history[table_id] = []

                action_record = {
                    "user_id": user_id,
                    "action": action.value,
                    "amount": amount,
                    "timestamp": timestamp.isoformat(),
                }

                self.action_history[table_id].append(action_record)

                # Keep only recent actions (last 100 per table)
                if len(self.action_history[table_id]) > 100:
                    self.action_history[table_id] = self.action_history[table_id][-100:]

        except Exception as e:
            logger.error(f"Failed to record action: {e}")

    def _broadcast_player_action(
        self,
        table_id: str,
        user_id: str,
        action: PlayerAction,
        amount: int | None,
        result: Any,
        cards: list | None = None,
    ) -> None:
        """Broadcast a player action to all table participants.

        Args:
            table_id: ID of the table
            user_id: ID of the player
            action: The action taken
            amount: Amount for betting actions
            result: Result from the game engine
            cards: Cards for draw/discard actions
        """
        try:
            ws_manager = get_websocket_manager()
            if not ws_manager:
                return

            action_data = {
                "user_id": user_id,
                "table_id": table_id,
                "action": action.value,
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "success": True,
            }

            # Add result data if available
            if result and hasattr(result, "to_dict"):
                action_data["result"] = result.to_dict()

            # Broadcast to all table participants
            ws_manager.broadcast_to_table(table_id, GameEvent.PLAYER_ACTION, action_data)

            # Also broadcast the action to chat/hand history
            from ..services.user_manager import UserManager

            user_manager = UserManager()
            user = user_manager.get_user_by_id(user_id)
            username = user.username if user else "Unknown"

            # Format action message for hand history
            action_name = action.value.lower()
            if action == PlayerAction.FOLD:
                action_msg = f"{username} folds"
            elif action == PlayerAction.CHECK:
                action_msg = f"{username} checks"
            elif action == PlayerAction.CALL:
                action_msg = f"{username} calls ${amount}" if amount else f"{username} calls"
            elif action == PlayerAction.BET:
                action_msg = f"{username} bets ${amount}"
            elif action == PlayerAction.RAISE:
                action_msg = f"{username} raises to ${amount}"
            elif action == PlayerAction.ALL_IN:
                action_msg = f"{username} is all-in for ${amount}"
            elif action == PlayerAction.DRAW:
                card_count = len(cards) if cards else 0
                if card_count == 0:
                    action_msg = f"{username} stands pat"
                elif card_count == 1:
                    action_msg = f"{username} draws 1 card"
                else:
                    action_msg = f"{username} draws {card_count} cards"
            elif action == PlayerAction.DISCARD:
                card_count = len(cards) if cards else 0
                action_msg = f"{username} discards {card_count} card{'s' if card_count != 1 else ''}"
            elif action == PlayerAction.PASS:
                card_count = len(cards) if cards else 0
                action_msg = f"{username} passes {card_count} card{'s' if card_count != 1 else ''}"
            elif action == PlayerAction.EXPOSE:
                card_count = len(cards) if cards else 0
                action_msg = f"{username} exposes {card_count} card{'s' if card_count != 1 else ''}"
            elif action == PlayerAction.SEPARATE:
                action_msg = f"{username} separates their cards"
            elif action == PlayerAction.DECLARE:
                action_msg = f"{username} declares"
            elif action == PlayerAction.CHOOSE:
                action_msg = f"{username} chooses"
            else:
                action_msg = f"{username} {action_name}"
                if amount:
                    action_msg += f" ${amount}"

            ws_manager.broadcast_game_action_chat(table_id, action_msg, "player_action")

            # Also broadcast updated game state
            ws_manager.broadcast_game_state_update(table_id)

        except Exception as e:
            logger.error(f"Failed to broadcast player action: {e}")

    def _is_current_player(self, session: GameSession, user_id: str) -> bool:
        """Check if a user is the current player to act.

        Args:
            session: Game session
            user_id: ID of the user

        Returns:
            True if user is current player, False otherwise
        """
        try:
            current_player = self._get_current_player(session)
            return current_player == user_id
        except Exception as e:
            logger.error(f"Failed to check current player: {e}")
            return False

    def _get_current_player(self, session: GameSession) -> str | None:
        """Get the current player to act from the game session.

        Args:
            session: Game session

        Returns:
            User ID of current player or None
        """
        try:
            if not session.game or not hasattr(session.game, "current_player"):
                return None

            current_player = session.game.current_player
            if current_player and hasattr(current_player, "id"):
                return current_player.id

            return None

        except Exception as e:
            logger.error(f"Failed to get current player: {e}")
            return None

    def get_action_history(self, table_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get action history for a table.

        Args:
            table_id: ID of the table
            limit: Maximum number of actions to return

        Returns:
            List of action records
        """
        try:
            with self.lock:
                history = self.action_history.get(table_id, [])
                return history[-limit:] if limit > 0 else history

        except Exception as e:
            logger.error(f"Failed to get action history for table {table_id}: {e}")
            return []

    def clear_action_history(self, table_id: str) -> None:
        """Clear action history for a table.

        Args:
            table_id: ID of the table
        """
        try:
            with self.lock:
                self.action_history.pop(table_id, None)
                logger.debug(f"Cleared action history for table {table_id}")

        except Exception as e:
            logger.error(f"Failed to clear action history for table {table_id}: {e}")

    def get_timeout_info(self, user_id: str) -> dict[str, Any]:
        """Get timeout information for a player.

        Args:
            user_id: ID of the player

        Returns:
            Dictionary with timeout information
        """
        try:
            remaining_time = self.timeout_manager.get_remaining_time(user_id)
            has_timeout = user_id in self.timeout_manager.active_timers

            return {"user_id": user_id, "has_active_timeout": has_timeout, "remaining_seconds": remaining_time}

        except Exception as e:
            logger.error(f"Failed to get timeout info for player {user_id}: {e}")
            return {"user_id": user_id, "has_active_timeout": False, "remaining_seconds": 0}

    def cancel_player_timeout(self, user_id: str) -> None:
        """Cancel a player's action timeout.

        Args:
            user_id: ID of the player
        """
        try:
            self.timeout_manager.cancel_timeout(user_id)
            logger.debug(f"Cancelled action timeout for player {user_id}")

        except Exception as e:
            logger.error(f"Failed to cancel timeout for player {user_id}: {e}")

    def _handle_hand_completion(self, table_id: str, session: GameSession) -> None:
        """Handle hand completion and broadcast showdown results.

        Args:
            table_id: ID of the table
            session: Game session that completed
        """
        try:
            logger.info(f"Hand completed for table {table_id}, processing showdown results")

            # Get hand results from the game engine
            hand_results = session.game.get_hand_results()

            if not hand_results:
                logger.warning(f"No hand results available for completed hand at table {table_id}")
                return

            # Convert to JSON format for frontend
            results_dict = {
                "is_complete": hand_results.is_complete,
                "total_pot": hand_results.total_pot,
                "pots": [],
                "hands": {},
                "winning_hands": [],
                "player_hole_cards": {},  # All players' hole cards for showdown display
            }

            # Get all players' hole cards for showdown display
            if session.game and hasattr(session.game, "table"):
                for player_id, player in session.game.table.players.items():
                    if hasattr(player, "hand") and hasattr(player.hand, "cards") and player.hand.cards:
                        results_dict["player_hole_cards"][player_id] = [str(card) for card in player.hand.cards]

            # Convert pots
            for pot in hand_results.pots:
                pot_dict = {
                    "amount": pot.amount,
                    "winners": pot.winners,
                    "split": pot.split,
                    "pot_type": pot.pot_type,
                    "hand_type": pot.hand_type,
                    "side_pot_index": pot.side_pot_index,
                    "eligible_players": list(pot.eligible_players) if pot.eligible_players else [],
                    "amount_per_player": pot.amount // len(pot.winners) if pot.winners else 0,
                }
                results_dict["pots"].append(pot_dict)

            # Convert hands
            for player_id, player_hands in hand_results.hands.items():
                results_dict["hands"][player_id] = []
                for hand in player_hands:
                    hand_dict = {
                        "player_id": hand.player_id,
                        "cards": [str(card) for card in hand.cards] if hand.cards else [],
                        "hand_name": hand.hand_name,
                        "hand_description": hand.hand_description,
                        "evaluation_type": hand.evaluation_type,
                        "hand_type": hand.hand_type,
                        "community_cards": [str(card) for card in hand.community_cards]
                        if hasattr(hand, "community_cards") and hand.community_cards
                        else [],
                        "used_hole_cards": [str(card) for card in hand.used_hole_cards] if hand.used_hole_cards else [],
                        "rank": hand.rank if hasattr(hand, "rank") else 0,
                        "ordered_rank": hand.ordered_rank if hasattr(hand, "ordered_rank") else 0,
                    }
                    results_dict["hands"][player_id].append(hand_dict)

            # Convert winning hands
            for winning_hand in hand_results.winning_hands:
                winning_dict = {
                    "player_id": winning_hand.player_id,
                    "cards": [str(card) for card in winning_hand.cards] if winning_hand.cards else [],
                    "hand_name": winning_hand.hand_name,
                    "hand_description": winning_hand.hand_description,
                    "evaluation_type": winning_hand.evaluation_type,
                    "hand_type": winning_hand.hand_type,
                    "community_cards": [str(card) for card in winning_hand.community_cards]
                    if hasattr(winning_hand, "community_cards") and winning_hand.community_cards
                    else [],
                    "used_hole_cards": [str(card) for card in winning_hand.used_hole_cards]
                    if winning_hand.used_hole_cards
                    else [],
                }
                results_dict["winning_hands"].append(winning_dict)

            # Broadcast hand completion to all table participants
            hand_number = getattr(session, "hands_played", 0) + 1
            websocket_manager = get_websocket_manager()
            if websocket_manager:
                websocket_manager.broadcast_hand_complete(table_id, results_dict, hand_number=hand_number)
                logger.info(f"Broadcasted hand completion results for table {table_id}")
            else:
                logger.warning("WebSocket manager not available for broadcasting hand completion")

            # Save hand to database
            self._save_hand_to_database(table_id, session, results_dict, hand_number)

            # Save session state for recovery after server restart
            self._save_session_state(table_id, session)

            # Process any pending leaves now that the hand is complete
            if session.pending_leaves:
                removed_players = session.process_pending_leaves()
                if removed_players:
                    from ..services.table_access_manager import TableAccessManager
                    from ..services.table_manager import TableManager

                    for removed_id in removed_players:
                        # Remove from DB
                        TableAccessManager.leave_table(removed_id, table_id)
                        logger.info(f"Removed pending-leave player {removed_id} from DB after hand completion")

                    # Broadcast updated state
                    if websocket_manager:
                        websocket_manager.broadcast_game_state_update(table_id)

                    # Update lobby
                    table = TableManager.get_table_by_id(table_id)
                    if table and websocket_manager:
                        websocket_manager.socketio.emit(
                            "table_updated", {"table": table.to_dict(), "action": "player_left"}
                        )

        except Exception as e:
            logger.error(f"Failed to handle hand completion for table {table_id}: {e}", exc_info=True)

    def _save_hand_to_database(self, table_id: str, session: GameSession, results_dict: dict, hand_number: int) -> None:
        """Save completed hand to the database for hand history.

        Args:
            table_id: ID of the table
            session: Game session that completed
            results_dict: Serialized hand results
            hand_number: Hand number
        """
        try:
            from ..database import db
            from ..models.game_history import GameHistory
            from ..services.user_manager import UserManager

            user_manager = UserManager()

            # Build players list with stacks
            players_data = []
            if session.game and hasattr(session.game, "table"):
                for player_id, player in session.game.table.players.items():
                    user = user_manager.get_user_by_id(player_id)
                    players_data.append(
                        {
                            "user_id": player_id,
                            "username": user.username if user else player.name,
                            "stack": player.stack,
                            "position": player.position.value if player.position else "NA",
                        }
                    )

            # Build actions from in-memory history
            actions_data = self.action_history.get(table_id, [])

            # Extract winner IDs from results
            winner_ids = []
            for pot in results_dict.get("pots", []):
                for winner_id in pot.get("winners", []):
                    if winner_id not in winner_ids:
                        winner_ids.append(winner_id)

            # Add winners to results for the model's get_winner_ids()
            results_with_winners = dict(results_dict)
            results_with_winners["winners"] = winner_ids

            # Get stakes from table
            stakes = {}
            if session.table:
                stakes = session.table.get_stakes() if hasattr(session.table, "get_stakes") else {}

            # Get variant and betting structure
            variant = session.table.variant if session.table else "unknown"
            betting_structure = session.table.betting_structure if session.table else "unknown"

            history = GameHistory(
                table_id=table_id,
                hand_number=hand_number,
                players=players_data,
                actions=actions_data,
                results=results_with_winners,
                variant=variant,
                betting_structure=betting_structure,
                stakes=stakes,
            )

            db.session.add(history)
            db.session.commit()
            logger.info(f"Saved hand #{hand_number} to database for table {table_id}")

        except Exception as e:
            logger.error(f"Failed to save hand to database for table {table_id}: {e}")
            try:
                from ..database import db

                db.session.rollback()
            except Exception as rollback_err:
                logger.error(f"Failed to rollback after hand save error: {rollback_err}")

    def _save_session_state(self, table_id: str, session: GameSession) -> None:
        """Save session state to database for recovery after server restart.

        Upserts a GameSessionState record with current dealer position and hands played.

        Args:
            table_id: ID of the table
            session: Game session that just completed a hand
        """
        try:
            from ..database import db
            from ..models.game_session_state import GameSessionState

            # Read current dealer seat from the game engine
            dealer_seat = 1
            if session.game and hasattr(session.game, "table"):
                dealer_seat = session.game.table.button_seat

            hands_played = getattr(session, "hands_played", 0)

            # Upsert: find existing record or create new one
            state = db.session.query(GameSessionState).filter_by(table_id=table_id).first()
            if state:
                state.dealer_seat = dealer_seat
                state.hands_played = hands_played
                state.is_active = True
                state.last_activity = datetime.utcnow()
                state.session_id = session.session_id
            else:
                state = GameSessionState(
                    table_id=table_id,
                    dealer_seat=dealer_seat,
                    hands_played=hands_played,
                    is_active=True,
                    session_id=session.session_id,
                )
                db.session.add(state)

            # Persist mixed game rotation state
            if session.mixed_game_config:
                state.current_variant_index = session.current_variant_index
                state.hands_in_current_variant = session.hands_in_current_variant
                state.orbit_size = session.orbit_size

            db.session.commit()
            logger.info(f"Saved session state for table {table_id}: dealer_seat={dealer_seat}, hands={hands_played}")

        except Exception as e:
            logger.error(f"Failed to save session state for table {table_id}: {e}")
            try:
                from ..database import db

                db.session.rollback()
            except Exception as rollback_err:
                logger.error(f"Failed to rollback after session state save error: {rollback_err}")

    def _auto_fold_pending_players(self, table_id: str, session: GameSession) -> None:
        """Auto-fold any pending-leave players who are now current to act.

        Loops in case multiple consecutive players are pending leave.

        Args:
            table_id: ID of the table
            session: GameSession instance
        """
        try:
            max_iterations = 10  # safety limit
            for _ in range(max_iterations):
                if not session.game or session.game.state == GameState.COMPLETE:
                    break

                folded, folded_id = session.auto_fold_pending_player()
                if not folded:
                    break

                logger.info(f"Auto-folded pending-leave player {folded_id} at table {table_id}")

                # Advance through non-player-input steps
                game = session.game
                if game.state != GameState.COMPLETE:
                    while game.state != GameState.COMPLETE:
                        if game.current_step >= len(game.rules.gameplay):
                            break
                        if (
                            game.state == GameState.DEALING
                            or game.state == GameState.BETTING
                            and game.current_player is None
                        ):
                            game._next_step()
                        else:
                            break

                # Broadcast action and state
                ws_manager = get_websocket_manager()
                if ws_manager:
                    ws_manager.broadcast_game_state_update(table_id)

                # Check if hand completed
                if session.game.state == GameState.COMPLETE:
                    self._handle_hand_completion(table_id, session)
                    break

        except Exception as e:
            logger.error(f"Failed to auto-fold pending players at table {table_id}: {e}")


# Global player action manager instance
player_action_manager = PlayerActionManager()
