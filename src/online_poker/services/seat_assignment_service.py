"""Service for managing seat assignments and table joining with enhanced seat selection."""

from typing import Any

from flask import current_app

from ..database import db
from ..models.table_access import TableAccess
from ..services.table_manager import TableManager
from ..services.user_manager import UserManager


class SeatAssignmentError(Exception):
    """Exception raised for seat assignment errors."""

    pass


class SeatAssignmentService:
    """Service class for managing seat assignments and table joining."""

    @staticmethod
    def get_available_seats(table_id: str) -> list[dict[str, Any]]:
        """Get list of available and occupied seats at a table.

        Args:
            table_id: ID of table to check

        Returns:
            List of seat information dictionaries
        """
        try:
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return []

            # Get all active players at the table
            active_players = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == table_id, TableAccess.is_active == True, TableAccess.is_spectator == False
                )
                .all()
            )

            # Create seat map
            occupied_seats = {}
            for access in active_players:
                if access.seat_number:
                    user_manager = UserManager()
                    user = user_manager.get_user_by_id(access.user_id)
                    occupied_seats[access.seat_number] = {
                        "user_id": access.user_id,
                        "username": user.username if user else "Unknown",
                        "stack": access.current_stack,
                        "joined_at": access.access_granted_at.isoformat(),
                    }

            # Build complete seat list
            seats = []
            for seat_num in range(1, table.max_players + 1):
                if seat_num in occupied_seats:
                    seat_info = {"seat_number": seat_num, "is_available": False, "player": occupied_seats[seat_num]}
                else:
                    seat_info = {"seat_number": seat_num, "is_available": True, "player": None}
                seats.append(seat_info)

            return seats

        except Exception as e:
            current_app.logger.error(f"Failed to get available seats: {e}")
            return []

    @staticmethod
    def join_table_with_seat_choice(
        user_id: str,
        table_id: str,
        buy_in_amount: int,
        seat_number: int | None = None,
        invite_code: str | None = None,
        password: str | None = None,
    ) -> tuple[bool, str, TableAccess | None]:
        """Join a table with optional seat selection.

        Args:
            user_id: ID of user joining
            table_id: ID of table to join
            buy_in_amount: Amount to buy in with
            seat_number: Preferred seat number (None for automatic assignment)
            invite_code: Invite code for private tables
            password: Password for password-protected tables

        Returns:
            Tuple of (success, error_message, access_record)
        """
        try:
            # Get table and validate
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found", None

            user_manager = UserManager()
            user = user_manager.get_user_by_id(user_id)
            if not user:
                return False, "User not found", None

            # Check if user already has access to this table
            existing_access = (
                db.session.query(TableAccess)
                .filter(TableAccess.table_id == table_id, TableAccess.user_id == user_id, TableAccess.is_active == True)
                .first()
            )

            if existing_access:
                return False, "Already at this table", None

            # Check table access permissions
            can_access, access_error = TableManager.can_access_table(table, user_id, invite_code, password)
            if not can_access:
                return False, access_error, None

            # Validate buy-in amount
            if buy_in_amount < table.get_minimum_buyin():
                return False, f"Minimum buy-in is ${table.get_minimum_buyin()}", None

            if buy_in_amount > table.get_maximum_buyin():
                return False, f"Maximum buy-in is ${table.get_maximum_buyin()}", None

            # Check if user has sufficient bankroll
            if user.bankroll < buy_in_amount:
                return False, "Insufficient bankroll", None

            # Check table capacity
            active_players = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == table_id, TableAccess.is_active == True, TableAccess.is_spectator == False
                )
                .count()
            )

            if active_players >= table.max_players:
                return False, "Table is full", None

            # Handle seat assignment
            assigned_seat = None
            if seat_number is not None:
                # User requested specific seat
                if seat_number < 1 or seat_number > table.max_players:
                    return False, f"Invalid seat number. Must be between 1 and {table.max_players}", None

                # Check if seat is available
                seat_taken = (
                    db.session.query(TableAccess)
                    .filter(
                        TableAccess.table_id == table_id,
                        TableAccess.is_active == True,
                        TableAccess.is_spectator == False,
                        TableAccess.seat_number == seat_number,
                    )
                    .first()
                )

                if seat_taken:
                    return False, f"Seat {seat_number} is already taken", None

                assigned_seat = seat_number
            else:
                # Automatic seat assignment - find first available seat
                occupied_seats = set()
                for access in (
                    db.session.query(TableAccess)
                    .filter(
                        TableAccess.table_id == table_id,
                        TableAccess.is_active == True,
                        TableAccess.is_spectator == False,
                        TableAccess.seat_number.isnot(None),
                    )
                    .all()
                ):
                    occupied_seats.add(access.seat_number)

                for seat in range(1, table.max_players + 1):
                    if seat not in occupied_seats:
                        assigned_seat = seat
                        break

                if assigned_seat is None:
                    return False, "No available seats", None

            # Deduct buy-in from user bankroll
            if not user.update_bankroll(-buy_in_amount):
                return False, "Failed to deduct buy-in", None

            # Create access record
            access_record = TableAccess(
                table_id=table_id,
                user_id=user_id,
                invite_code_used=invite_code,
                is_spectator=False,
                seat_number=assigned_seat,
                buy_in_amount=buy_in_amount,
            )

            db.session.add(access_record)

            # Update table activity
            table.update_activity()

            db.session.commit()

            current_app.logger.info(
                f"User {user_id} joined table {table_id} in seat {assigned_seat} with ${buy_in_amount} buy-in"
            )
            return True, f"Successfully joined table in seat {assigned_seat}", access_record

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to join table with seat choice: {e}")
            return False, "Failed to join table", None

    @staticmethod
    def join_as_spectator(
        user_id: str, table_id: str, invite_code: str | None = None, password: str | None = None
    ) -> tuple[bool, str, TableAccess | None]:
        """Join a table as spectator.

        Args:
            user_id: ID of user joining
            table_id: ID of table to join
            invite_code: Invite code for private tables
            password: Password for password-protected tables

        Returns:
            Tuple of (success, error_message, access_record)
        """
        try:
            # Get table and validate
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found", None

            user_manager = UserManager()
            user = user_manager.get_user_by_id(user_id)
            if not user:
                return False, "User not found", None

            # Check if user already has access to this table
            existing_access = (
                db.session.query(TableAccess)
                .filter(TableAccess.table_id == table_id, TableAccess.user_id == user_id, TableAccess.is_active == True)
                .first()
            )

            if existing_access:
                return False, "Already at this table", None

            # Check table access permissions
            can_access, access_error = TableManager.can_access_table(table, user_id, invite_code, password)
            if not can_access:
                return False, access_error, None

            # For now, only allow spectators on public tables
            # This could be made configurable per table
            if table.is_private:
                return False, "Private tables don't allow spectators", None

            # Create spectator access record
            access_record = TableAccess(
                table_id=table_id,
                user_id=user_id,
                invite_code_used=invite_code,
                is_spectator=True,
                seat_number=None,
                buy_in_amount=None,
            )

            db.session.add(access_record)

            # Update table activity
            table.update_activity()

            db.session.commit()

            current_app.logger.info(f"User {user_id} joined table {table_id} as spectator")
            return True, "Successfully joined as spectator", access_record

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to join as spectator: {e}")
            return False, "Failed to join as spectator", None

    @staticmethod
    def change_seat(user_id: str, table_id: str, new_seat_number: int) -> tuple[bool, str]:
        """Change a player's seat at the table.

        Args:
            user_id: ID of user changing seats
            table_id: ID of table
            new_seat_number: New seat number to move to

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get current access record
            access_record = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == table_id,
                    TableAccess.user_id == user_id,
                    TableAccess.is_active == True,
                    TableAccess.is_spectator == False,
                )
                .first()
            )

            if not access_record:
                return False, "Not seated at this table"

            # Get table for validation
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"

            # Validate new seat number
            if new_seat_number < 1 or new_seat_number > table.max_players:
                return False, f"Invalid seat number. Must be between 1 and {table.max_players}"

            # Check if already in that seat
            if access_record.seat_number == new_seat_number:
                return False, "Already in that seat"

            # Check if new seat is available
            seat_taken = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == table_id,
                    TableAccess.is_active == True,
                    TableAccess.is_spectator == False,
                    TableAccess.seat_number == new_seat_number,
                )
                .first()
            )

            if seat_taken:
                return False, f"Seat {new_seat_number} is already taken"

            # TODO: Check if hand is in progress and prevent seat changes during hands
            # For now, allow seat changes anytime

            old_seat = access_record.seat_number
            access_record.seat_number = new_seat_number
            access_record.update_activity()

            # Update table activity
            table.update_activity()

            db.session.commit()

            current_app.logger.info(
                f"User {user_id} moved from seat {old_seat} to seat {new_seat_number} at table {table_id}"
            )
            return True, f"Successfully moved to seat {new_seat_number}"

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to change seat: {e}")
            return False, "Failed to change seat"

    @staticmethod
    def get_table_seating_info(table_id: str) -> dict[str, Any]:
        """Get comprehensive seating information for a table.

        Args:
            table_id: ID of table to get info for

        Returns:
            Dictionary with seating information
        """
        try:
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return {}

            seats = SeatAssignmentService.get_available_seats(table_id)

            # Count players and spectators
            active_players = sum(1 for seat in seats if not seat["is_available"])

            spectators = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == table_id, TableAccess.is_active == True, TableAccess.is_spectator == True
                )
                .count()
            )

            return {
                "table_id": table_id,
                "table_name": table.name,
                "max_players": table.max_players,
                "current_players": active_players,
                "spectators": spectators,
                "is_full": active_players >= table.max_players,
                "seats": seats,
                "minimum_buyin": table.get_minimum_buyin(),
                "maximum_buyin": table.get_maximum_buyin(),
                "allows_spectators": not table.is_private,  # For now, only public tables allow spectators
            }

        except Exception as e:
            current_app.logger.error(f"Failed to get table seating info: {e}")
            return {}

    @staticmethod
    def notify_players_of_join(
        table_id: str, new_player_id: str, seat_number: int | None = None, is_spectator: bool = False
    ) -> None:
        """Notify existing players about a new player joining.

        Args:
            table_id: ID of table
            new_player_id: ID of player who joined
            seat_number: Seat number if player (None for spectators)
            is_spectator: Whether the new user is a spectator
        """
        try:
            # Get new player info
            user_manager = UserManager()
            new_user = user_manager.get_user_by_id(new_player_id)
            if not new_user:
                return

            # Get all other active users at the table
            db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id, TableAccess.is_active == True, TableAccess.user_id != new_player_id
            ).all()

            # Prepare notification message
            if is_spectator:
                message = f"{new_user.username} joined as spectator"
            else:
                message = f"{new_user.username} joined the table in seat {seat_number}"

            # TODO: Send real-time notifications via WebSocket
            # For now, just log the notification
            current_app.logger.info(f"Table {table_id}: {message}")

            # This would be implemented with WebSocket/Socket.IO:
            # from ..services.websocket_manager import WebSocketManager
            # websocket_manager = WebSocketManager()
            # websocket_manager.broadcast_to_table(table_id, 'player_joined', {
            #     'user_id': new_player_id,
            #     'username': new_user.username,
            #     'seat_number': seat_number,
            #     'is_spectator': is_spectator,
            #     'message': message
            # })

        except Exception as e:
            current_app.logger.error(f"Failed to notify players of join: {e}")

    @staticmethod
    def get_seat_assignment_mode(table_id: str) -> str:
        """Get the seat assignment mode for a table.

        Args:
            table_id: ID of table to check

        Returns:
            'player_choice' or 'automatic' - for now always returns 'player_choice'
        """
        # For now, we'll always allow player choice
        # This could be made configurable per table in the future
        return "player_choice"

    @staticmethod
    def validate_join_during_hand(table_id: str) -> tuple[bool, str]:
        """Check if a player can join during an active hand.

        Args:
            table_id: ID of table to check

        Returns:
            Tuple of (can_join, message)
        """
        try:
            # TODO: Integrate with game state to check if hand is in progress
            # For now, we'll use a simple heuristic based on recent activity and player count

            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"

            # Check if there are enough players for a hand
            active_players = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == table_id, TableAccess.is_active == True, TableAccess.is_spectator == False
                )
                .count()
            )

            # Get minimum players for this variant
            rules = TableManager.get_variant_rules(table.variant)
            if not rules:
                return True, "Can join - variant rules not found"

            if active_players < rules.min_players:
                return True, "Can join - not enough players for a hand"

            # Check for recent activity (within 5 minutes suggests hand in progress)
            from datetime import datetime, timedelta

            recent_activity_threshold = datetime.utcnow() - timedelta(minutes=5)

            if table.last_activity > recent_activity_threshold:
                return True, "Can join but will wait for next hand"

            return True, "Can join"

        except Exception as e:
            current_app.logger.error(f"Failed to validate join during hand: {e}")
            return True, "Can join (validation failed)"
