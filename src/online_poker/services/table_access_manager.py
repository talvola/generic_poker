"""Service for managing table access and player sessions."""

from typing import Optional, List, Dict, Any, Tuple
from flask import current_app

from ..database import db
from ..models.table import PokerTable
from ..models.table_access import TableAccess
from ..models.user import User
from ..services.table_manager import TableManager
from ..services.user_manager import UserManager


class TableAccessError(Exception):
    """Exception raised for table access errors."""
    pass


class TableAccessManager:
    """Service class for managing table access and player sessions."""
    
    @staticmethod
    def join_table(user_id: str, table_id: str, buy_in_amount: int,
                   invite_code: Optional[str] = None, password: Optional[str] = None,
                   as_spectator: bool = False) -> Tuple[bool, str, Optional[TableAccess]]:
        """Join a table as player or spectator.
        
        Args:
            user_id: ID of user joining
            table_id: ID of table to join
            buy_in_amount: Amount to buy in with (ignored for spectators)
            invite_code: Invite code for private tables
            password: Password for password-protected tables
            as_spectator: Whether to join as spectator
            
        Returns:
            Tuple of (success, error_message, access_record)
        """
        try:
            # Get table and user
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found", None
            
            user_manager = UserManager()
            user = user_manager.get_user_by_id(user_id)
            if not user:
                return False, "User not found", None
            
            # Check if user already has access to this table
            existing_access = db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id,
                TableAccess.user_id == user_id,
                TableAccess.is_active == True
            ).first()
            
            if existing_access:
                return False, "Already at this table", None
            
            # Check table access permissions
            can_access, access_error = TableManager.can_access_table(
                table, user_id, invite_code, password
            )
            if not can_access:
                return False, access_error, None
            
            # For spectators, just create access record
            if as_spectator:
                # Check if table allows spectators (public tables only for now)
                if table.is_private:
                    return False, "Private tables don't allow spectators", None
                
                access_record = TableAccess(
                    table_id=table_id,
                    user_id=user_id,
                    invite_code_used=invite_code,
                    is_spectator=True
                )
                
                db.session.add(access_record)
                db.session.commit()
                
                current_app.logger.info(f"User {user_id} joined table {table_id} as spectator")
                return True, "Joined as spectator", access_record
            
            # For players, check buy-in and table capacity
            if buy_in_amount < table.get_minimum_buyin():
                return False, f"Minimum buy-in is ${table.get_minimum_buyin()}", None
            
            if buy_in_amount > table.get_maximum_buyin():
                return False, f"Maximum buy-in is ${table.get_maximum_buyin()}", None
            
            # Check if user has sufficient bankroll
            if user.bankroll < buy_in_amount:
                return False, "Insufficient bankroll", None
            
            # Check table capacity
            active_players = db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id,
                TableAccess.is_active == True,
                TableAccess.is_spectator == False
            ).count()
            
            if active_players >= table.max_players:
                return False, "Table is full", None
            
            # Find available seat
            occupied_seats = set()
            for access in db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id,
                TableAccess.is_active == True,
                TableAccess.is_spectator == False,
                TableAccess.seat_number.isnot(None)
            ).all():
                occupied_seats.add(access.seat_number)
            
            seat_number = None
            for seat in range(1, table.max_players + 1):
                if seat not in occupied_seats:
                    seat_number = seat
                    break
            
            if seat_number is None:
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
                seat_number=seat_number,
                buy_in_amount=buy_in_amount
            )
            
            db.session.add(access_record)
            
            # Update table activity
            table.update_activity()
            
            db.session.commit()
            
            current_app.logger.info(f"User {user_id} joined table {table_id} with ${buy_in_amount} buy-in")
            return True, "Successfully joined table", access_record
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to join table: {e}")
            return False, "Failed to join table", None
    
    @staticmethod
    def leave_table(user_id: str, table_id: str) -> Tuple[bool, str]:
        """Leave a table and cash out chips.
        
        Args:
            user_id: ID of user leaving
            table_id: ID of table to leave
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get active access record
            access_record = db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id,
                TableAccess.user_id == user_id,
                TableAccess.is_active == True
            ).first()
            
            if not access_record:
                return False, "Not at this table"
            
            # Get user for bankroll update
            user_manager = UserManager()
            user = user_manager.get_user_by_id(user_id)
            if not user:
                return False, "User not found"
            
            # Cash out chips if player (not spectator)
            if not access_record.is_spectator and access_record.current_stack:
                user.update_bankroll(access_record.current_stack)
                current_app.logger.info(f"User {user_id} cashed out ${access_record.current_stack}")
            
            # Mark as inactive
            access_record.leave_table()
            
            # Update table activity
            table = TableManager.get_table_by_id(table_id)
            if table:
                table.update_activity()
            
            db.session.commit()
            
            current_app.logger.info(f"User {user_id} left table {table_id}")
            return True, "Successfully left table"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to leave table: {e}")
            return False, "Failed to leave table"
    
    @staticmethod
    def get_table_players(table_id: str) -> List[Dict[str, Any]]:
        """Get list of active players at a table.
        
        Args:
            table_id: ID of table to get players for
            
        Returns:
            List of player information dictionaries
        """
        try:
            access_records = db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id,
                TableAccess.is_active == True
            ).order_by(TableAccess.seat_number.asc()).all()
            
            players = []
            for access in access_records:
                user_manager = UserManager()
                user = user_manager.get_user_by_id(access.user_id)
                if user:
                    player_info = {
                        'user_id': access.user_id,
                        'username': user.username,
                        'seat_number': access.seat_number,
                        'is_spectator': access.is_spectator,
                        'buy_in_amount': access.buy_in_amount,
                        'current_stack': access.current_stack,
                        'joined_at': access.access_granted_at.isoformat(),
                        'last_activity': access.last_activity.isoformat()
                    }
                    players.append(player_info)
            
            return players
            
        except Exception as e:
            current_app.logger.error(f"Failed to get table players: {e}")
            return []
    
    @staticmethod
    def update_player_stack(user_id: str, table_id: str, new_stack: int) -> bool:
        """Update a player's chip stack.
        
        Args:
            user_id: ID of user to update
            table_id: ID of table
            new_stack: New chip stack amount
            
        Returns:
            True if successful, False otherwise
        """
        try:
            access_record = db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id,
                TableAccess.user_id == user_id,
                TableAccess.is_active == True,
                TableAccess.is_spectator == False
            ).first()
            
            if not access_record:
                return False
            
            access_record.update_stack(new_stack)
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update player stack: {e}")
            return False
    
    @staticmethod
    def _cleanup_table_access(table_id: str) -> int:
        """Clean up all access records for a specific table.
        
        Args:
            table_id: ID of table to clean up
            
        Returns:
            Number of access records cleaned up
        """
        try:
            # Get all access records for this table
            access_records = db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id
            ).all()
            
            cleaned_count = 0
            for record in access_records:
                # Cash out player if they have chips
                if not record.is_spectator and record.current_stack:
                    user_manager = UserManager()
                    user = user_manager.get_user_by_id(record.user_id)
                    if user:
                        user.update_bankroll(record.current_stack)
                        current_app.logger.info(f"Cashed out ${record.current_stack} for user {record.user_id}")
                
                # Delete the access record completely to avoid foreign key issues
                db.session.delete(record)
                cleaned_count += 1
            
            if cleaned_count > 0:
                db.session.flush()  # Flush to ensure access records are deleted before table
                current_app.logger.info(f"Cleaned up {cleaned_count} access records for table {table_id}")
            
            return cleaned_count
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to cleanup table access for {table_id}: {e}")
            return 0
    
    @staticmethod
    def cleanup_inactive_access(timeout_minutes: int = 30) -> int:
        """Clean up inactive table access records.
        
        Args:
            timeout_minutes: Minutes of inactivity before cleanup
            
        Returns:
            Number of records cleaned up
        """
        try:
            inactive_records = db.session.query(TableAccess).filter(
                TableAccess.is_active == True
            ).all()
            
            cleaned_count = 0
            for record in inactive_records:
                if record.is_inactive(timeout_minutes):
                    # Cash out player if they have chips
                    if not record.is_spectator and record.current_stack:
                        user_manager = UserManager()
                        user = user_manager.get_user_by_id(record.user_id)
                        if user:
                            user.update_bankroll(record.current_stack)
                    
                    record.leave_table()
                    cleaned_count += 1
                    current_app.logger.info(f"Cleaned up inactive access for user {record.user_id}")
            
            if cleaned_count > 0:
                db.session.commit()
            
            return cleaned_count
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to cleanup inactive access: {e}")
            return 0