"""Service for managing player joining and leaving mechanics."""

import logging
from datetime import datetime
from typing import Any

from ..database import db
from ..models.table_access import TableAccess
from ..services.game_orchestrator import game_orchestrator
from ..services.table_access_manager import TableAccessManager
from ..services.table_manager import TableManager
from ..services.user_manager import UserManager

logger = logging.getLogger(__name__)


class PlayerSessionError(Exception):
    """Exception raised for player session errors."""

    pass


class PlayerSessionManager:
    """Service for managing player joining and leaving mechanics."""

    @staticmethod
    def join_table_and_game(
        user_id: str,
        table_id: str,
        buy_in_amount: int,
        invite_code: str | None = None,
        password: str | None = None,
        as_spectator: bool = False,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """Join a table and its associated game session.

        Args:
            user_id: ID of user joining
            table_id: ID of table to join
            buy_in_amount: Amount to buy in with (ignored for spectators)
            invite_code: Invite code for private tables
            password: Password for password-protected tables
            as_spectator: Whether to join as spectator

        Returns:
            Tuple of (success, error_message, session_info)
        """
        try:
            # First, join the table through TableAccessManager
            success, message, access_record = TableAccessManager.join_table(
                user_id, table_id, buy_in_amount, invite_code, password, as_spectator
            )

            if not success:
                return False, message, None

            # Get or create game session
            session = game_orchestrator.get_session(table_id)
            if not session:
                # Create game session if it doesn't exist
                session_success, session_message, session = game_orchestrator.create_session(table_id)
                if not session_success:
                    # Rollback table join if game session creation fails
                    TableAccessManager.leave_table(user_id, table_id)
                    return False, f"Failed to create game session: {session_message}", None

            # Join the game session
            if as_spectator:
                success, message = session.add_spectator(user_id)
            else:
                # Get user info for game session
                user_manager = UserManager()
                user = user_manager.get_user_by_id(user_id)
                if not user:
                    TableAccessManager.leave_table(user_id, table_id)
                    return False, "User not found", None

                success, message = session.add_player(user_id, user.username, access_record.current_stack)

            if not success:
                # Rollback table join if game session join fails
                TableAccessManager.leave_table(user_id, table_id)
                return False, f"Failed to join game: {message}", None

            # Return session info
            session_info = {
                "session": session.get_session_info(),
                "access_record": access_record.to_dict() if access_record else None,
                "player_info": PlayerSessionManager.get_player_info(user_id, table_id),
            }

            logger.info(f"User {user_id} successfully joined table {table_id} and game session")
            return True, "Successfully joined table and game", session_info

        except Exception as e:
            logger.error(f"Failed to join table and game: {e}")
            # Attempt cleanup
            try:
                TableAccessManager.leave_table(user_id, table_id)
                session = game_orchestrator.get_session(table_id)
                if session:
                    if as_spectator:
                        session.remove_spectator(user_id)
                    else:
                        session.remove_player(user_id, "Join failed")
            except Exception:
                logger.debug("Cleanup after join failure also failed", exc_info=True)

            return False, "Failed to join table and game", None

    @staticmethod
    def leave_table_and_game(
        user_id: str, table_id: str, reason: str = "Player left"
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """Leave a table and its associated game session.

        Args:
            user_id: ID of user leaving
            table_id: ID of table to leave
            reason: Reason for leaving

        Returns:
            Tuple of (success, error_message, cashout_info)
        """
        try:
            # Get current access record to determine if spectator or player
            access_record = (
                db.session.query(TableAccess)
                .filter(TableAccess.table_id == table_id, TableAccess.user_id == user_id, TableAccess.is_active == True)
                .first()
            )

            if not access_record:
                return False, "Not at this table", None

            is_spectator = access_record.is_spectator
            initial_stack = access_record.current_stack

            # Leave game session first
            session = game_orchestrator.get_session(table_id)
            if session:
                if is_spectator:
                    session.remove_spectator(user_id)
                else:
                    success, message = session.remove_player(user_id, reason)
                    if not success:
                        logger.warning(f"Failed to remove player from game session: {message}")

            # Leave table (this handles chip cashout)
            success, message = TableAccessManager.leave_table(user_id, table_id)
            if not success:
                return False, message, None

            # Calculate cashout info
            cashout_info = None
            if not is_spectator and initial_stack:
                # Get final stack from session if available
                final_stack = initial_stack
                if session and user_id in session.connected_players:
                    # This shouldn't happen since we removed the player, but just in case
                    final_stack = initial_stack

                cashout_info = {
                    "initial_stack": initial_stack,
                    "final_stack": final_stack,
                    "profit_loss": final_stack - access_record.buy_in_amount if access_record.buy_in_amount else 0,
                    "session_duration": (datetime.utcnow() - access_record.access_granted_at).total_seconds(),
                }

            logger.info(f"User {user_id} successfully left table {table_id}")
            return True, "Successfully left table and game", cashout_info

        except Exception as e:
            logger.error(f"Failed to leave table and game: {e}")
            return False, "Failed to leave table and game", None

    @staticmethod
    def handle_player_disconnect(user_id: str, table_id: str) -> tuple[bool, str]:
        """Handle player disconnection from table and game.

        Args:
            user_id: ID of disconnected user
            table_id: ID of table

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Update table access activity
            access_record = (
                db.session.query(TableAccess)
                .filter(TableAccess.table_id == table_id, TableAccess.user_id == user_id, TableAccess.is_active == True)
                .first()
            )

            if access_record:
                access_record.update_activity()
                db.session.commit()

            # Handle game session disconnect
            session = game_orchestrator.get_session(table_id)
            if session:
                session.handle_player_disconnect(user_id)

            logger.info(f"Handled disconnect for user {user_id} at table {table_id}")
            return True, "Disconnect handled"

        except Exception as e:
            logger.error(f"Failed to handle disconnect: {e}")
            return False, "Failed to handle disconnect"

    @staticmethod
    def handle_player_reconnect(user_id: str, table_id: str) -> tuple[bool, str, dict[str, Any] | None]:
        """Handle player reconnection to table and game.

        Args:
            user_id: ID of reconnecting user
            table_id: ID of table

        Returns:
            Tuple of (success, error_message, session_info)
        """
        try:
            # Check if user has active access to table
            access_record = (
                db.session.query(TableAccess)
                .filter(TableAccess.table_id == table_id, TableAccess.user_id == user_id, TableAccess.is_active == True)
                .first()
            )

            if not access_record:
                return False, "No active access to this table", None

            # Update table access activity
            access_record.update_activity()
            db.session.commit()

            # Handle game session reconnect
            session = game_orchestrator.get_session(table_id)
            if not session:
                return False, "Game session not found", None

            success, message = session.handle_player_reconnect(user_id)
            if not success:
                return False, message, None

            # Return session info
            session_info = {
                "session": session.get_session_info(),
                "access_record": access_record.to_dict(),
                "player_info": PlayerSessionManager.get_player_info(user_id, table_id),
            }

            logger.info(f"User {user_id} successfully reconnected to table {table_id}")
            return True, "Successfully reconnected", session_info

        except Exception as e:
            logger.error(f"Failed to handle reconnect: {e}")
            return False, "Failed to handle reconnect", None

    @staticmethod
    def get_player_info(user_id: str, table_id: str) -> dict[str, Any] | None:
        """Get comprehensive player information for a table.

        Args:
            user_id: ID of user
            table_id: ID of table

        Returns:
            Player information dictionary or None if not found
        """
        try:
            # Get access record
            access_record = (
                db.session.query(TableAccess)
                .filter(TableAccess.table_id == table_id, TableAccess.user_id == user_id, TableAccess.is_active == True)
                .first()
            )

            if not access_record:
                return None

            # Get user info
            user_manager = UserManager()
            user = user_manager.get_user_by_id(user_id)
            if not user:
                return None

            # Get game session info
            session = game_orchestrator.get_session(table_id)
            game_status = None
            if session:
                if user_id in session.connected_players:
                    game_status = "connected"
                elif user_id in session.disconnected_players:
                    game_status = "disconnected"
                elif user_id in session.spectators:
                    game_status = "spectating"
                else:
                    game_status = "not_in_game"

            return {
                "user_id": user_id,
                "username": user.username,
                "seat_number": access_record.seat_number,
                "is_spectator": access_record.is_spectator,
                "buy_in_amount": access_record.buy_in_amount,
                "current_stack": access_record.current_stack,
                "joined_at": access_record.access_granted_at.isoformat(),
                "last_activity": access_record.last_activity.isoformat(),
                "game_status": game_status,
                "session_duration": (datetime.utcnow() - access_record.access_granted_at).total_seconds(),
            }

        except Exception as e:
            logger.error(f"Failed to get player info: {e}")
            return None

    @staticmethod
    def get_table_session_info(table_id: str) -> dict[str, Any] | None:
        """Get comprehensive information about a table and its game session.

        Args:
            table_id: ID of table

        Returns:
            Table session information dictionary or None if not found
        """
        try:
            # Get table info
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return None

            # Get players
            players = TableAccessManager.get_table_players(table_id)

            # Get game session info
            session = game_orchestrator.get_session(table_id)
            session_info = session.get_session_info() if session else None

            # Get spectators
            spectators = []
            for player in players:
                if player["is_spectator"]:
                    spectators.append(
                        {"user_id": player["user_id"], "username": player["username"], "joined_at": player["joined_at"]}
                    )

            # Get active players only
            active_players = [p for p in players if not p["is_spectator"]]

            return {
                "table": {
                    "id": table.id,
                    "name": table.name,
                    "variant": table.variant,
                    "betting_structure": table.betting_structure,
                    "stakes": table.get_stakes(),
                    "max_players": table.max_players,
                    "is_private": table.is_private,
                    "created_at": table.created_at.isoformat(),
                    "last_activity": table.last_activity.isoformat(),
                },
                "players": active_players,
                "spectators": spectators,
                "session": session_info,
                "stats": {
                    "total_players": len(active_players),
                    "total_spectators": len(spectators),
                    "seats_available": table.max_players - len(active_players),
                    "has_game_session": session is not None,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get table session info: {e}")
            return None

    @staticmethod
    def validate_buy_in(user_id: str, table_id: str, buy_in_amount: int) -> tuple[bool, str]:
        """Validate a buy-in amount for a user and table.

        Args:
            user_id: ID of user
            table_id: ID of table
            buy_in_amount: Proposed buy-in amount

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Get table
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"

            # Get user
            user_manager = UserManager()
            user = user_manager.get_user_by_id(user_id)
            if not user:
                return False, "User not found"

            # Check minimum buy-in
            min_buyin = table.get_minimum_buyin()
            if buy_in_amount < min_buyin:
                return False, f"Minimum buy-in is ${min_buyin}"

            # Check maximum buy-in
            max_buyin = table.get_maximum_buyin()
            if buy_in_amount > max_buyin:
                return False, f"Maximum buy-in is ${max_buyin}"

            # Check user bankroll
            if user.bankroll < buy_in_amount:
                return False, f"Insufficient bankroll. You have ${user.bankroll}, need ${buy_in_amount}"

            return True, "Buy-in amount is valid"

        except Exception as e:
            logger.error(f"Failed to validate buy-in: {e}")
            return False, "Failed to validate buy-in"

    @staticmethod
    def cleanup_inactive_sessions(timeout_minutes: int = 30) -> int:
        """Clean up inactive player sessions.

        Args:
            timeout_minutes: Minutes of inactivity before cleanup

        Returns:
            Number of sessions cleaned up
        """
        try:
            # Clean up table access records
            access_cleaned = TableAccessManager.cleanup_inactive_access(timeout_minutes)

            # Clean up game sessions
            session_cleaned = game_orchestrator.cleanup_inactive_sessions(timeout_minutes)

            total_cleaned = access_cleaned + session_cleaned
            if total_cleaned > 0:
                logger.info(
                    f"Cleaned up {total_cleaned} inactive sessions ({access_cleaned} access, {session_cleaned} game)"
                )

            return total_cleaned

        except Exception as e:
            logger.error(f"Failed to cleanup inactive sessions: {e}")
            return 0
