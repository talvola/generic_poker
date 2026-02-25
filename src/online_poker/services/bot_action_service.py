"""Service for managing bot actions in online games."""

import logging
from threading import Lock

from flask import current_app

from generic_poker.game.game_state import GameState

logger = logging.getLogger(__name__)

# Per-table lock to prevent concurrent bot processing
_table_locks: dict[str, Lock] = {}
_table_locks_lock = Lock()


def _get_table_lock(table_id: str) -> Lock:
    """Get or create a lock for a specific table."""
    with _table_locks_lock:
        if table_id not in _table_locks:
            _table_locks[table_id] = Lock()
        return _table_locks[table_id]


class BotActionService:
    """Checks if the current player is a bot and processes actions in a loop."""

    @staticmethod
    def trigger_bot_actions_if_needed(table_id: str) -> None:
        """Check if the current player is a bot and start background processing.

        Safe to call after any state change — returns immediately if current
        player is not a bot or no game is active.

        Args:
            table_id: ID of the table to check
        """
        try:
            from ..services.game_orchestrator import game_orchestrator
            from ..services.simple_bot import bot_manager

            session = game_orchestrator.get_session(table_id)
            if not session or not session.game:
                return

            game = session.game
            if game.state == GameState.COMPLETE:
                return

            # Check if current player is a bot
            if not game.current_player:
                return

            current_id = game.current_player.id
            if not bot_manager.is_bot(current_id):
                return

            # Current player is a bot — start background task
            from ..services.websocket_manager import get_websocket_manager

            ws_manager = get_websocket_manager()
            if ws_manager and ws_manager.socketio:
                # Capture Flask app for background task (which runs outside request context)
                app = current_app._get_current_object()
                ws_manager.socketio.start_background_task(BotActionService._bot_action_loop, table_id, app)
                logger.info(f"Started bot action loop for table {table_id}")

        except Exception as e:
            logger.error(f"Error in trigger_bot_actions_if_needed for table {table_id}: {e}")

    @staticmethod
    def _bot_action_loop(table_id: str, app=None) -> None:
        """Background loop that processes bot actions until a human player is next.

        Args:
            table_id: ID of the table
            app: Flask app instance for establishing application context
        """
        table_lock = _get_table_lock(table_id)

        # Non-blocking acquire — if another loop is already running, skip
        if not table_lock.acquire(blocking=False):
            logger.debug(f"Bot loop already running for table {table_id}, skipping")
            return

        try:
            # Run inside app context so DB queries work (e.g., GameStateManager)
            if app:
                with app.app_context():
                    BotActionService._run_bot_loop(table_id)
            else:
                BotActionService._run_bot_loop(table_id)
        except Exception as e:
            logger.error(f"Bot action loop error for table {table_id}: {e}", exc_info=True)
        finally:
            table_lock.release()

    @staticmethod
    def _run_bot_loop(table_id: str) -> None:
        """Inner bot action loop (runs inside app context).

        Args:
            table_id: ID of the table
        """
        from ..services.game_orchestrator import GameOrchestrator, game_orchestrator
        from ..services.simple_bot import bot_manager
        from ..services.websocket_manager import get_websocket_manager

        ws_manager = get_websocket_manager()

        max_iterations = 50  # Safety limit
        for _iteration in range(max_iterations):
            # Sleep before acting (so humans can see previous state)
            if ws_manager and ws_manager.socketio:
                ws_manager.socketio.sleep(1.5)

            # Re-read session state each iteration
            session = game_orchestrator.get_session(table_id)
            if not session or not session.game:
                logger.debug(f"Bot loop: no session for table {table_id}, stopping")
                break

            game = session.game
            if game.state == GameState.COMPLETE:
                logger.debug(f"Bot loop: game complete for table {table_id}, stopping")
                break

            # Check game is in a state that needs player input
            if game.state not in (GameState.BETTING, GameState.DRAWING, GameState.DEALING):
                break

            # Check current player is a bot
            if not game.current_player:
                break

            current_id = game.current_player.id
            if not bot_manager.is_bot(current_id):
                logger.debug(f"Bot loop: current player {current_id} is human, stopping")
                break

            bot = bot_manager.get_bot(current_id)
            if not bot:
                logger.warning(f"Bot loop: bot {current_id} not found in manager")
                break

            # Get valid actions and choose
            try:
                valid_actions = game.get_valid_actions(current_id)
                if not valid_actions:
                    logger.warning(f"Bot loop: no valid actions for bot {current_id}")
                    break

                decision = bot.choose_action_full(valid_actions, game, current_id)
                logger.info(
                    f"Bot {bot.username} chose {decision.action.value}"
                    f" (amount={decision.amount}, cards={len(decision.cards) if decision.cards else 0})"
                )

                # Process the action through the session
                success, message, result = session.process_player_action(
                    current_id,
                    decision.action,
                    decision.amount or 0,
                    cards=decision.cards,
                    declaration_data=decision.declaration_data,
                )

                if not success:
                    logger.error(f"Bot action failed for {bot.username}: {message}")
                    break

                # Check if we need to advance (betting round complete)
                if result and hasattr(result, "advance_step") and result.advance_step:
                    if game.state != GameState.COMPLETE:
                        game._next_step()
                        GameOrchestrator.advance_through_non_player_steps(game)

                # Broadcast the action
                if ws_manager:
                    action_msg = BotActionService._format_action_message(bot.username, decision)
                    ws_manager.broadcast_game_action_chat(table_id, action_msg, "player_action")
                    ws_manager.broadcast_game_state_update(table_id)

                # Check if hand is complete
                if game.state == GameState.COMPLETE:
                    try:
                        hand_results = game.get_hand_results()
                        if hand_results:
                            from ..services.player_action_manager import player_action_manager

                            player_action_manager._handle_hand_completion(table_id, session)
                    except Exception as hc_err:
                        logger.error(f"Bot loop: hand completion error: {hc_err}")
                    break

            except Exception as action_err:
                logger.error(f"Bot loop action error for {current_id}: {action_err}", exc_info=True)
                break

        else:
            logger.warning(f"Bot loop hit max iterations for table {table_id}")

    @staticmethod
    def _format_action_message(username: str, decision) -> str:
        """Format a bot action for chat display."""
        action = decision.action
        amount = decision.amount

        if action.value == "fold":
            return f"{username} folds"
        elif action.value == "check":
            return f"{username} checks"
        elif action.value == "call":
            return f"{username} calls ${amount}" if amount else f"{username} calls"
        elif action.value == "bet":
            return f"{username} bets ${amount}"
        elif action.value == "raise":
            return f"{username} raises to ${amount}"
        elif action.value == "all_in":
            return f"{username} is all-in for ${amount}"
        elif action.value == "draw":
            card_count = len(decision.cards) if decision.cards else 0
            if card_count == 0:
                return f"{username} stands pat"
            return f"{username} draws {card_count} card{'s' if card_count != 1 else ''}"
        elif action.value == "discard":
            card_count = len(decision.cards) if decision.cards else 0
            return f"{username} discards {card_count} card{'s' if card_count != 1 else ''}"
        elif action.value == "pass":
            card_count = len(decision.cards) if decision.cards else 0
            return f"{username} passes {card_count} card{'s' if card_count != 1 else ''}"
        elif action.value == "expose":
            card_count = len(decision.cards) if decision.cards else 0
            return f"{username} exposes {card_count} card{'s' if card_count != 1 else ''}"
        elif action.value == "separate":
            return f"{username} separates their cards"
        elif action.value == "declare":
            return f"{username} declares"
        elif action.value == "choose":
            return f"{username} chooses"
        elif action.value == "bring_in":
            return f"{username} brings in for ${amount}"
        elif action.value == "complete":
            return f"{username} completes to ${amount}"
        else:
            return f"{username}: {action.value}" + (f" ${amount}" if amount else "")
