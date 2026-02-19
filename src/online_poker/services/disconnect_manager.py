"""Service for managing player disconnections and reconnections."""

import logging
from datetime import datetime, timedelta
from threading import RLock, Timer
from typing import Any

from generic_poker.game.game_state import PlayerAction

from ..services.game_state_manager import GameStateManager
from ..services.player_session_manager import PlayerSessionManager
from ..services.websocket_manager import GameEvent, get_websocket_manager
from . import game_orchestrator

logger = logging.getLogger(__name__)


class DisconnectedPlayer:
    """Represents a disconnected player with timeout handling."""

    def __init__(self, user_id: str, table_id: str, disconnect_time: datetime, timeout_minutes: int = 10):
        """Initialize disconnected player.

        Args:
            user_id: ID of the disconnected user
            table_id: ID of the table
            disconnect_time: When the player disconnected
            timeout_minutes: Minutes before auto-removal
        """
        self.user_id = user_id
        self.table_id = table_id
        self.disconnect_time = disconnect_time
        self.timeout_minutes = timeout_minutes
        self.auto_fold_timer: Timer | None = None
        self.removal_timer: Timer | None = None
        self.has_auto_folded = False
        self.is_current_player_on_disconnect = False

    def start_timers(self, disconnect_manager, auto_fold_seconds: int = 30):
        """Start auto-fold and removal timers.

        Args:
            disconnect_manager: Reference to the disconnect manager
            auto_fold_seconds: Seconds before auto-folding current player
        """
        removal_delay = self.timeout_minutes * 60  # Convert to seconds

        if self.is_current_player_on_disconnect:
            # Start auto-fold timer for current player
            self.auto_fold_timer = Timer(
                auto_fold_seconds, disconnect_manager._handle_auto_fold, args=[self.user_id, self.table_id]
            )
            self.auto_fold_timer.start()

            # Start removal timer
            self.removal_timer = Timer(
                removal_delay, disconnect_manager._handle_auto_removal, args=[self.user_id, self.table_id]
            )
            self.removal_timer.start()

            logger.info(
                f"Started timers for disconnected player {self.user_id}: "
                f"auto-fold in {auto_fold_seconds}s, removal in {removal_delay}s"
            )
        else:
            # For non-current players, auto-fold immediately and start removal timer
            disconnect_manager._handle_auto_fold(self.user_id, self.table_id)

            # Start removal timer
            self.removal_timer = Timer(
                removal_delay, disconnect_manager._handle_auto_removal, args=[self.user_id, self.table_id]
            )
            self.removal_timer.start()

            logger.info(
                f"Started timer for disconnected player {self.user_id}: "
                f"auto-fold immediate, removal in {removal_delay}s"
            )

    def cancel_timers(self):
        """Cancel all active timers."""
        if self.auto_fold_timer:
            self.auto_fold_timer.cancel()
            self.auto_fold_timer = None

        if self.removal_timer:
            self.removal_timer.cancel()
            self.removal_timer = None

        logger.debug(f"Cancelled timers for player {self.user_id}")

    def is_expired(self) -> bool:
        """Check if the disconnect timeout has expired.

        Returns:
            True if expired, False otherwise
        """
        timeout_delta = timedelta(minutes=self.timeout_minutes)
        return datetime.utcnow() - self.disconnect_time > timeout_delta

    def time_remaining(self) -> int:
        """Get seconds remaining before timeout.

        Returns:
            Seconds remaining, or 0 if expired
        """
        timeout_delta = timedelta(minutes=self.timeout_minutes)
        time_left = timeout_delta - (datetime.utcnow() - self.disconnect_time)
        return max(0, int(time_left.total_seconds()))


class DisconnectManager:
    """Manager for handling player disconnections and reconnections."""

    def __init__(self):
        """Initialize the disconnect manager."""
        self.disconnected_players: dict[str, DisconnectedPlayer] = {}  # user_id -> DisconnectedPlayer
        self.table_disconnects: dict[str, set[str]] = {}  # table_id -> set of user_ids
        self.lock = RLock()

        logger.info("Disconnect manager initialized")

    def handle_player_disconnect(
        self, user_id: str, table_id: str, is_current_player: bool = False
    ) -> tuple[bool, str]:
        """Handle a player disconnection.

        Args:
            user_id: ID of the disconnected user
            table_id: ID of the table
            is_current_player: Whether the player was current to act

        Returns:
            Tuple of (success, message)
        """
        try:
            with self.lock:
                # Check if player is already tracked as disconnected
                if user_id in self.disconnected_players:
                    existing = self.disconnected_players[user_id]
                    if existing.table_id == table_id:
                        logger.info(f"Player {user_id} already tracked as disconnected from table {table_id}")
                        return True, "Already handling disconnect"

                # Read timeout config from Flask with safe fallback
                try:
                    from flask import current_app

                    auto_fold_seconds = current_app.config.get("DISCONNECT_AUTO_FOLD_SECONDS", 30)
                    removal_minutes = current_app.config.get("DISCONNECT_REMOVAL_MINUTES", 10)
                except RuntimeError:
                    auto_fold_seconds = 30
                    removal_minutes = 10

                # Create disconnected player record
                disconnect_time = datetime.utcnow()
                disconnected_player = DisconnectedPlayer(
                    user_id, table_id, disconnect_time, timeout_minutes=removal_minutes
                )
                disconnected_player.is_current_player_on_disconnect = is_current_player

                # Store the disconnected player
                self.disconnected_players[user_id] = disconnected_player

                # Track by table
                if table_id not in self.table_disconnects:
                    self.table_disconnects[table_id] = set()
                self.table_disconnects[table_id].add(user_id)

                # Handle game session disconnect
                PlayerSessionManager.handle_player_disconnect(user_id, table_id)

                # Start timers for auto-fold and removal
                disconnected_player.start_timers(self, auto_fold_seconds=auto_fold_seconds)

                # Notify other players via WebSocket
                ws_manager = get_websocket_manager()
                if ws_manager:
                    disconnect_data = {
                        "user_id": user_id,
                        "table_id": table_id,
                        "disconnect_time": disconnect_time.isoformat(),
                        "timeout_minutes": disconnected_player.timeout_minutes,
                        "is_current_player": is_current_player,
                    }
                    ws_manager.broadcast_to_table(
                        table_id, GameEvent.PLAYER_DISCONNECTED, disconnect_data, exclude_user=user_id
                    )

                logger.info(f"Handled disconnect for player {user_id} from table {table_id}")
                return True, "Disconnect handled successfully"

        except Exception as e:
            logger.error(f"Failed to handle disconnect for player {user_id}: {e}")
            return False, f"Failed to handle disconnect: {str(e)}"

    def handle_player_reconnect(self, user_id: str, table_id: str) -> tuple[bool, str, dict[str, Any] | None]:
        """Handle a player reconnection.

        Args:
            user_id: ID of the reconnecting user
            table_id: ID of the table

        Returns:
            Tuple of (success, message, reconnect_info)
        """
        try:
            with self.lock:
                # Check if player is tracked as disconnected
                if user_id not in self.disconnected_players:
                    return False, "Player was not disconnected", None

                disconnected_player = self.disconnected_players[user_id]

                # Verify table matches
                if disconnected_player.table_id != table_id:
                    return False, "Table mismatch for reconnection", None

                # Check if timeout has expired
                if disconnected_player.is_expired():
                    # Clean up expired disconnect
                    self._cleanup_disconnected_player(user_id)
                    return False, "Disconnect timeout expired, player removed", None

                # Cancel timers
                disconnected_player.cancel_timers()

                # Handle game session reconnect
                success, message, session_info = PlayerSessionManager.handle_player_reconnect(user_id, table_id)

                if not success:
                    # Restart timers if reconnect failed
                    disconnected_player.start_timers(self)
                    return False, f"Game reconnect failed: {message}", None

                # Calculate disconnect duration
                disconnect_duration = datetime.utcnow() - disconnected_player.disconnect_time

                # Prepare reconnect info
                reconnect_info = {
                    "user_id": user_id,
                    "table_id": table_id,
                    "disconnect_duration": disconnect_duration.total_seconds(),
                    "had_auto_folded": disconnected_player.has_auto_folded,
                    "session_info": session_info,
                }

                # Clean up disconnect tracking
                self._cleanup_disconnected_player(user_id)

                # Notify other players via WebSocket
                ws_manager = get_websocket_manager()
                if ws_manager:
                    reconnect_data = {
                        "user_id": user_id,
                        "table_id": table_id,
                        "reconnect_time": datetime.utcnow().isoformat() + "Z",
                        "disconnect_duration": disconnect_duration.total_seconds(),
                    }
                    ws_manager.broadcast_to_table(table_id, GameEvent.PLAYER_RECONNECTED, reconnect_data)

                    # Send updated game state to reconnected player
                    game_state = GameStateManager.generate_game_state_view(table_id, user_id)
                    if game_state:
                        ws_manager.send_to_user(user_id, GameEvent.GAME_STATE_UPDATE, game_state.to_dict())

                logger.info(
                    f"Successfully reconnected player {user_id} to table {table_id} "
                    f"after {disconnect_duration.total_seconds():.1f}s"
                )

                return True, "Reconnected successfully", reconnect_info

        except Exception as e:
            logger.error(f"Failed to handle reconnect for player {user_id}: {e}")
            return False, f"Failed to handle reconnect: {str(e)}", None

    def _handle_auto_fold(self, user_id: str, table_id: str) -> None:
        """Handle auto-fold for a disconnected player.

        Args:
            user_id: ID of the player to auto-fold
            table_id: ID of the table
        """
        try:
            with self.lock:
                disconnected_player = self.disconnected_players.get(user_id)
                if not disconnected_player or disconnected_player.has_auto_folded:
                    return

                # Get game session
                session = game_orchestrator.game_orchestrator.get_session(table_id)
                if not session:
                    logger.warning(f"No game session found for auto-fold: table {table_id}")
                    return

                # Check if player is current to act
                current_player = GameStateManager._get_current_player(session)
                if current_player != user_id:
                    logger.debug(f"Player {user_id} not current to act, skipping auto-fold")
                    return

                # Process auto-fold action
                success, message, result = session.process_player_action(user_id, PlayerAction.FOLD, 0)

                if success:
                    disconnected_player.has_auto_folded = True

                    # Notify other players
                    ws_manager = get_websocket_manager()
                    if ws_manager:
                        auto_fold_data = {
                            "user_id": user_id,
                            "table_id": table_id,
                            "action": "fold",
                            "reason": "auto_fold_disconnect",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        ws_manager.broadcast_to_table(table_id, GameEvent.PLAYER_ACTION, auto_fold_data)

                        # Broadcast updated game state
                        ws_manager.broadcast_game_state_update(table_id)

                    logger.info(f"Auto-folded disconnected player {user_id} at table {table_id}")
                else:
                    logger.warning(f"Failed to auto-fold player {user_id}: {message}")

        except Exception as e:
            logger.error(f"Failed to handle auto-fold for player {user_id}: {e}")

    def _handle_auto_removal(self, user_id: str, table_id: str) -> None:
        """Handle auto-removal of a disconnected player.

        Args:
            user_id: ID of the player to remove
            table_id: ID of the table
        """
        try:
            with self.lock:
                disconnected_player = self.disconnected_players.get(user_id)
                if not disconnected_player:
                    return

                # Remove player from table and game
                success, message, cashout_info = PlayerSessionManager.leave_table_and_game(
                    user_id, table_id, "Disconnected too long"
                )

                if success:
                    # Notify other players
                    ws_manager = get_websocket_manager()
                    if ws_manager:
                        removal_data = {
                            "user_id": user_id,
                            "table_id": table_id,
                            "reason": "disconnect_timeout",
                            "cashout_info": cashout_info,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        ws_manager.broadcast_to_table(table_id, GameEvent.PLAYER_LEFT, removal_data)

                        # Broadcast updated game state
                        ws_manager.broadcast_game_state_update(table_id)

                    logger.info(f"Auto-removed disconnected player {user_id} from table {table_id}")
                else:
                    logger.warning(f"Failed to auto-remove player {user_id}: {message}")

                # Clean up disconnect tracking
                self._cleanup_disconnected_player(user_id)

        except Exception as e:
            logger.error(f"Failed to handle auto-removal for player {user_id}: {e}")

    def _cleanup_disconnected_player(self, user_id: str) -> None:
        """Clean up tracking for a disconnected player.

        Args:
            user_id: ID of the player to clean up
        """
        try:
            disconnected_player = self.disconnected_players.pop(user_id, None)
            if disconnected_player:
                # Cancel any active timers
                disconnected_player.cancel_timers()

                # Remove from table tracking
                table_id = disconnected_player.table_id
                if table_id in self.table_disconnects:
                    self.table_disconnects[table_id].discard(user_id)
                    if not self.table_disconnects[table_id]:
                        del self.table_disconnects[table_id]

                logger.debug(f"Cleaned up disconnect tracking for player {user_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup disconnected player {user_id}: {e}")

    def get_disconnected_player_info(self, user_id: str) -> dict[str, Any] | None:
        """Get information about a disconnected player.

        Args:
            user_id: ID of the user

        Returns:
            Disconnect information or None if not disconnected
        """
        try:
            disconnected_player = self.disconnected_players.get(user_id)
            if not disconnected_player:
                return None

            return {
                "user_id": user_id,
                "table_id": disconnected_player.table_id,
                "disconnect_time": disconnected_player.disconnect_time.isoformat(),
                "timeout_minutes": disconnected_player.timeout_minutes,
                "time_remaining": disconnected_player.time_remaining(),
                "has_auto_folded": disconnected_player.has_auto_folded,
                "is_expired": disconnected_player.is_expired(),
            }

        except Exception as e:
            logger.error(f"Failed to get disconnect info for player {user_id}: {e}")
            return None

    def get_table_disconnects(self, table_id: str) -> list[dict[str, Any]]:
        """Get all disconnected players for a table.

        Args:
            table_id: ID of the table

        Returns:
            List of disconnect information
        """
        try:
            disconnected_users = self.table_disconnects.get(table_id, set())
            disconnect_info = []

            for user_id in disconnected_users:
                info = self.get_disconnected_player_info(user_id)
                if info:
                    disconnect_info.append(info)

            return disconnect_info

        except Exception as e:
            logger.error(f"Failed to get table disconnects for {table_id}: {e}")
            return []

    def is_player_disconnected(self, user_id: str) -> bool:
        """Check if a player is currently disconnected.

        Args:
            user_id: ID of the user

        Returns:
            True if disconnected, False otherwise
        """
        return user_id in self.disconnected_players

    def cleanup_expired_disconnects(self) -> int:
        """Clean up expired disconnections.

        Returns:
            Number of expired disconnects cleaned up
        """
        try:
            with self.lock:
                expired_users = []

                for user_id, disconnected_player in self.disconnected_players.items():
                    if disconnected_player.is_expired():
                        expired_users.append(user_id)

                for user_id in expired_users:
                    disconnected_player = self.disconnected_players[user_id]
                    self._handle_auto_removal(user_id, disconnected_player.table_id)

                logger.info(f"Cleaned up {len(expired_users)} expired disconnects")
                return len(expired_users)

        except Exception as e:
            logger.error(f"Failed to cleanup expired disconnects: {e}")
            return 0

    def get_disconnect_stats(self) -> dict[str, Any]:
        """Get disconnect manager statistics.

        Returns:
            Dictionary with disconnect statistics
        """
        try:
            with self.lock:
                total_disconnects = len(self.disconnected_players)
                auto_folded_count = sum(1 for dp in self.disconnected_players.values() if dp.has_auto_folded)
                expired_count = sum(1 for dp in self.disconnected_players.values() if dp.is_expired())

                return {
                    "total_disconnected_players": total_disconnects,
                    "auto_folded_players": auto_folded_count,
                    "expired_disconnects": expired_count,
                    "active_table_disconnects": len(self.table_disconnects),
                    "average_disconnect_time": self._calculate_average_disconnect_time(),
                }

        except Exception as e:
            logger.error(f"Failed to get disconnect stats: {e}")
            return {}

    def _calculate_average_disconnect_time(self) -> float:
        """Calculate average disconnect time in seconds.

        Returns:
            Average disconnect time in seconds
        """
        if not self.disconnected_players:
            return 0.0

        total_time = 0.0
        current_time = datetime.utcnow()

        for disconnected_player in self.disconnected_players.values():
            disconnect_duration = current_time - disconnected_player.disconnect_time
            total_time += disconnect_duration.total_seconds()

        return total_time / len(self.disconnected_players)

    def force_reconnect_player(self, user_id: str, table_id: str) -> tuple[bool, str]:
        """Force reconnect a player (admin function).

        Args:
            user_id: ID of the user
            table_id: ID of the table

        Returns:
            Tuple of (success, message)
        """
        try:
            if user_id not in self.disconnected_players:
                return False, "Player is not disconnected"

            # Force reconnect by handling it normally
            success, message, reconnect_info = self.handle_player_reconnect(user_id, table_id)

            if success:
                logger.info(f"Force reconnected player {user_id} to table {table_id}")

            return success, message

        except Exception as e:
            logger.error(f"Failed to force reconnect player {user_id}: {e}")
            return False, f"Failed to force reconnect: {str(e)}"

    def force_remove_player(self, user_id: str) -> tuple[bool, str]:
        """Force remove a disconnected player (admin function).

        Args:
            user_id: ID of the user

        Returns:
            Tuple of (success, message)
        """
        try:
            disconnected_player = self.disconnected_players.get(user_id)
            if not disconnected_player:
                return False, "Player is not disconnected"

            # Force removal
            self._handle_auto_removal(user_id, disconnected_player.table_id)

            logger.info(f"Force removed disconnected player {user_id}")
            return True, "Player removed successfully"

        except Exception as e:
            logger.error(f"Failed to force remove player {user_id}: {e}")
            return False, f"Failed to force remove: {str(e)}"


# Global disconnect manager instance
disconnect_manager = DisconnectManager()
