"""Table management service for the online poker platform."""

import os
import json
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from flask import current_app

from ..database import db
from ..models.table import PokerTable
from ..models.table_config import TableConfig
from ..models.user import User
from ..services.user_manager import UserManager
from generic_poker.config.loader import GameRules, GameActionType
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game import Game


class TableValidationError(Exception):
    """Exception raised for table validation errors."""
    pass


class TableNotFoundError(Exception):
    """Exception raised when table is not found."""
    pass


class TableManager:
    """Service class for managing poker tables."""
    
    # Cache for loaded game rules to avoid repeated file I/O
    _rules_cache: Dict[str, GameRules] = {}
    
    # Actions not yet supported in the online platform — all actions now supported
    UNSUPPORTED_ACTIONS = set()

    @staticmethod
    def get_available_variants() -> List[Dict[str, Any]]:
        """Get list of all available poker variants.

        Filters out variants that use unsupported actions (expose, pass,
        declare, separate, choose).

        Returns:
            List of variant dictionaries with name, display_name, category,
            min_players, max_players, and supported betting structures
        """
        variants = []
        config_dir = Path("data/game_configs")

        if not config_dir.exists():
            return variants

        for config_file in config_dir.glob("*.json"):
            try:
                # Load game rules from cache or file
                variant_name = config_file.stem
                if variant_name not in TableManager._rules_cache:
                    rules = GameRules.from_file(config_file)
                    TableManager._rules_cache[variant_name] = rules
                else:
                    rules = TableManager._rules_cache[variant_name]

                # Skip variants with unsupported actions
                has_unsupported = False
                for step in rules.gameplay:
                    if step.action_type in TableManager.UNSUPPORTED_ACTIONS:
                        has_unsupported = True
                        break
                    # Also check sub-actions in grouped steps
                    if step.action_type == GameActionType.GROUPED and isinstance(step.action_config, list):
                        for sub_action in step.action_config:
                            for key in sub_action:
                                if key == 'name':
                                    continue
                                try:
                                    sub_type = GameActionType[key.upper()]
                                    if sub_type in TableManager.UNSUPPORTED_ACTIONS:
                                        has_unsupported = True
                                        break
                                except KeyError:
                                    pass
                            if has_unsupported:
                                break
                    if has_unsupported:
                        break
                if has_unsupported:
                    continue

                # Convert betting structures to string values
                supported_structures = [structure.value for structure in rules.betting_structures]

                display_name = rules.game
                category = rules.category or 'Other'

                variant_info = {
                    'name': variant_name,
                    'display_name': display_name,
                    'category': category,
                    'min_players': rules.min_players,
                    'max_players': rules.max_players,
                    'betting_structures': supported_structures,
                    'deck_type': rules.deck_type,
                }
                variants.append(variant_info)

            except Exception as e:
                # Log error but continue with other variants
                current_app.logger.warning(f"Failed to load variant {config_file.stem}: {e}")
                continue

        # Sort variants alphabetically by display name
        variants.sort(key=lambda x: x['display_name'])
        return variants
    
    @staticmethod
    def get_variant_rules(variant_name: str) -> Optional[GameRules]:
        """Get game rules for a specific variant.
        
        Args:
            variant_name: Name of the poker variant
            
        Returns:
            GameRules object or None if variant not found
        """
        if variant_name in TableManager._rules_cache:
            return TableManager._rules_cache[variant_name]
        
        config_file = Path(f"data/game_configs/{variant_name}.json")
        if not config_file.exists():
            return None
        
        try:
            rules = GameRules.from_file(config_file)
            TableManager._rules_cache[variant_name] = rules
            return rules
        except Exception as e:
            current_app.logger.error(f"Failed to load rules for variant {variant_name}: {e}")
            return None
    
    @staticmethod
    def validate_table_config(config: TableConfig) -> None:
        """Validate table configuration against variant rules.
        
        Args:
            config: Table configuration to validate
            
        Raises:
            TableValidationError: If configuration is invalid
        """
        # Get variant rules
        rules = TableManager.get_variant_rules(config.variant)
        if not rules:
            raise TableValidationError(f"Unknown poker variant: {config.variant}")
        
        # Validate player count against variant limits
        if config.max_players < rules.min_players:
            raise TableValidationError(
                f"Maximum players ({config.max_players}) is less than variant minimum ({rules.min_players})"
            )
        
        if config.max_players > rules.max_players:
            raise TableValidationError(
                f"Maximum players ({config.max_players}) exceeds variant maximum ({rules.max_players})"
            )
        
        # Validate betting structure is supported by variant
        if config.betting_structure not in rules.betting_structures:
            supported = [s.value for s in rules.betting_structures]
            raise TableValidationError(
                f"Betting structure {config.betting_structure.value} not supported by {config.variant}. "
                f"Supported structures: {supported}"
            )
    
    @staticmethod
    def create_table(creator_id: str, config: TableConfig) -> PokerTable:
        """Create a new poker table.
        
        Args:
            creator_id: ID of the user creating the table
            config: Table configuration
            
        Returns:
            Created PokerTable instance
            
        Raises:
            TableValidationError: If configuration is invalid
            ValueError: If creator not found or other validation errors
        """
        # Validate creator exists
        user_manager = UserManager()
        creator = user_manager.get_user_by_id(creator_id)
        if not creator:
            raise ValueError(f"Creator with ID {creator_id} not found")
        
        # Validate table configuration
        config.validate()
        TableManager.validate_table_config(config)
        
        # Create table instance
        table = PokerTable(
            name=config.name.strip(),
            variant=config.variant,
            betting_structure=config.betting_structure.value,
            stakes=config.stakes,
            max_players=config.max_players,
            creator_id=creator_id,
            is_private=config.is_private,
            allow_bots=config.allow_bots,
            password=config.password
        )
        
        # Save to database
        try:
            db.session.add(table)
            db.session.commit()
            current_app.logger.info(f"Created table {table.id} ({table.name}) by user {creator_id}")
            return table
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to create table: {e}")
            raise TableValidationError(f"Failed to create table: {e}")
    
    @staticmethod
    def get_public_tables() -> List[Dict[str, Any]]:
        """Get list of all public tables with basic information.
        
        Returns:
            List of public table information dictionaries
        """
        try:
            tables = db.session.query(PokerTable).filter(
                PokerTable.is_private == False
            ).order_by(PokerTable.created_at.desc()).all()
            
            return [table.to_dict() for table in tables]
        except Exception as e:
            current_app.logger.error(f"Failed to get public tables: {e}")
            return []
    
    @staticmethod
    def get_table_by_id(table_id: str) -> Optional[PokerTable]:
        """Get table by ID.
        
        Args:
            table_id: Table ID to search for
            
        Returns:
            PokerTable instance or None if not found
        """
        try:
            return db.session.query(PokerTable).filter(
                PokerTable.id == table_id
            ).first()
        except Exception as e:
            current_app.logger.error(f"Failed to get table {table_id}: {e}")
            return None
    
    @staticmethod
    def get_table_by_invite_code(invite_code: str) -> Optional[PokerTable]:
        """Get private table by invite code.
        
        Args:
            invite_code: Invite code to search for
            
        Returns:
            PokerTable instance or None if not found
        """
        try:
            return db.session.query(PokerTable).filter(
                PokerTable.invite_code == invite_code,
                PokerTable.is_private == True
            ).first()
        except Exception as e:
            current_app.logger.error(f"Failed to get table by invite code: {e}")
            return None
    
    @staticmethod
    def can_access_table(table: PokerTable, user_id: str, invite_code: Optional[str] = None, 
                        password: Optional[str] = None) -> Tuple[bool, str]:
        """Check if user can access a table.
        
        Args:
            table: Table to check access for
            user_id: ID of user requesting access
            invite_code: Invite code if joining private table
            password: Password if table is password protected
            
        Returns:
            Tuple of (can_access, error_message)
        """
        # Public tables are always accessible
        if not table.is_private:
            # Check password if table has one
            if table.password_hash and not table.check_password(password or ""):
                return False, "Incorrect table password"
            return True, ""
        
        # Private tables require invite code or creator access
        if table.creator_id == user_id:
            return True, ""  # Creator always has access
        
        if not invite_code:
            return False, "Invite code required for private table"
        
        if table.invite_code != invite_code:
            return False, "Invalid invite code"
        
        # Check password if table has one
        if table.password_hash and not table.check_password(password or ""):
            return False, "Incorrect table password"
        
        return True, ""
    
    @staticmethod
    def update_table_visibility(table_id: str, user_id: str, is_private: bool) -> Tuple[bool, str]:
        """Update table visibility (public/private).
        
        Args:
            table_id: ID of table to update
            user_id: ID of user requesting change
            is_private: New privacy setting
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"
            
            # Only creator can change visibility
            if table.creator_id != user_id:
                return False, "Only table creator can change visibility"
            
            # TODO: Check if hand is in progress (requires game state integration)
            # For now, allow changes anytime
            
            table.is_private = is_private
            
            # Generate invite code if making private
            if is_private and not table.invite_code:
                table.invite_code = table._generate_invite_code()
            
            # Clear invite code if making public
            if not is_private:
                table.invite_code = None
            
            db.session.commit()
            current_app.logger.info(f"Updated table {table_id} visibility to {'private' if is_private else 'public'}")
            return True, ""
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update table visibility: {e}")
            return False, "Failed to update table visibility"
    
    @staticmethod
    def regenerate_invite_code(table_id: str, user_id: str) -> Tuple[bool, str, Optional[str]]:
        """Regenerate invite code for a private table.
        
        Args:
            table_id: ID of table to update
            user_id: ID of user requesting change
            
        Returns:
            Tuple of (success, error_message, new_invite_code)
        """
        try:
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found", None
            
            # Only creator can regenerate invite code
            if table.creator_id != user_id:
                return False, "Only table creator can regenerate invite code", None
            
            if not table.is_private:
                return False, "Table must be private to have invite code", None
            
            # Generate new invite code
            table.invite_code = table._generate_invite_code()
            db.session.commit()
            
            current_app.logger.info(f"Regenerated invite code for table {table_id}")
            return True, "", table.invite_code
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to regenerate invite code: {e}")
            return False, "Failed to regenerate invite code", None
    
    @staticmethod
    def close_inactive_tables(timeout_minutes: int = 30) -> int:
        """Close tables that have been inactive for specified time.
        
        Args:
            timeout_minutes: Minutes of inactivity before closing table
            
        Returns:
            Number of tables closed
        """
        try:
            tables = db.session.query(PokerTable).all()
            closed_count = 0
            
            for table in tables:
                if table.is_inactive(timeout_minutes):
                    # Notify players before closing
                    TableManager._notify_table_closure(table, "inactivity")
                    
                    # Clean up associated access records
                    from ..services.table_access_manager import TableAccessManager
                    TableAccessManager._cleanup_table_access(table.id)
                    
                    # Remove table
                    db.session.delete(table)
                    closed_count += 1
                    current_app.logger.info(f"Closed inactive table {table.id} ({table.name})")
            
            if closed_count > 0:
                db.session.commit()
            
            return closed_count
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to close inactive tables: {e}")
            return 0
    
    @staticmethod
    def _notify_table_closure(table: PokerTable, reason: str) -> None:
        """Notify players about table closure.
        
        Args:
            table: Table being closed
            reason: Reason for closure
        """
        # TODO: Implement real-time notifications (WebSocket/Socket.IO)
        # For now, just log the notification
        current_app.logger.info(f"Table {table.name} closing due to {reason}")
    
    @staticmethod
    def can_modify_table_settings(table_id: str, user_id: str) -> Tuple[bool, str]:
        """Check if user can modify table settings.
        
        Args:
            table_id: ID of table to check
            user_id: ID of user requesting modification
            
        Returns:
            Tuple of (can_modify, error_message)
        """
        table = TableManager.get_table_by_id(table_id)
        if not table:
            return False, "Table not found"
        
        # Only table creator can modify settings
        if table.creator_id != user_id:
            return False, "Only table creator can modify settings"
        
        # Check if hand is in progress
        if TableManager._is_hand_in_progress(table):
            return False, "Cannot modify settings while hand is in progress"
        
        return True, ""
    
    @staticmethod
    def _is_hand_in_progress(table: PokerTable) -> bool:
        """Check if a hand is currently in progress at the table.
        
        Args:
            table: Table to check
            
        Returns:
            True if hand is in progress, False otherwise
        """
        # For now, we'll use a simple heuristic:
        # If there are 2+ active players and recent activity (within 5 minutes), assume hand in progress
        from datetime import datetime, timedelta
        
        active_players = sum(1 for access in table.access_records 
                           if access.is_active and not access.is_spectator)
        
        if active_players < 2:
            return False  # Need at least 2 players for a hand
        
        # Check for recent activity (within 5 minutes)
        recent_activity_threshold = datetime.utcnow() - timedelta(minutes=5)
        has_recent_activity = table.last_activity > recent_activity_threshold
        
        return has_recent_activity
    
    @staticmethod
    def update_table_settings(table_id: str, user_id: str, settings: Dict[str, Any]) -> Tuple[bool, str]:
        """Update table settings.
        
        Args:
            table_id: ID of table to update
            user_id: ID of user requesting update
            settings: Dictionary of settings to update
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Check permissions
            can_modify, error = TableManager.can_modify_table_settings(table_id, user_id)
            if not can_modify:
                return False, error
            
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"
            
            # Update allowed settings
            updated_fields = []
            
            if 'name' in settings:
                new_name = settings['name'].strip()
                if not new_name:
                    return False, "Table name cannot be empty"
                if len(new_name) > 100:
                    return False, "Table name cannot exceed 100 characters"
                table.name = new_name
                updated_fields.append('name')
            
            if 'is_private' in settings:
                old_private = table.is_private
                table.is_private = bool(settings['is_private'])
                
                # Generate invite code if making private
                if table.is_private and not table.invite_code:
                    table.invite_code = table._generate_invite_code()
                
                # Clear invite code if making public
                if not table.is_private:
                    table.invite_code = None
                
                updated_fields.append('visibility')
            
            if 'allow_bots' in settings:
                table.allow_bots = bool(settings['allow_bots'])
                updated_fields.append('allow_bots')
            
            # Update activity timestamp
            table.update_activity()
            
            db.session.commit()
            current_app.logger.info(f"Updated table {table_id} settings: {updated_fields}")
            
            return True, f"Updated: {', '.join(updated_fields)}"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update table settings: {e}")
            return False, "Failed to update table settings"
    
    @staticmethod
    def kick_player(table_id: str, creator_id: str, player_id: str, reason: str = "") -> Tuple[bool, str]:
        """Kick a player from the table.
        
        Args:
            table_id: ID of table
            creator_id: ID of table creator
            player_id: ID of player to kick
            reason: Optional reason for kicking
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"
            
            # Only table creator can kick players
            if table.creator_id != creator_id:
                return False, "Only table creator can kick players"
            
            # Cannot kick yourself
            if creator_id == player_id:
                return False, "Cannot kick yourself"
            
            # Check if hand is in progress
            if TableManager._is_hand_in_progress(table):
                return False, "Cannot kick players while hand is in progress"
            
            # Remove player from table
            from ..services.table_access_manager import TableAccessManager
            success, error = TableAccessManager.leave_table(player_id, table_id)
            
            if success:
                current_app.logger.info(f"Player {player_id} kicked from table {table_id} by {creator_id}. Reason: {reason}")
                return True, "Player kicked successfully"
            else:
                return False, error
                
        except Exception as e:
            current_app.logger.error(f"Failed to kick player: {e}")
            return False, "Failed to kick player"
    
    @staticmethod
    def transfer_host_privileges(table_id: str, current_creator_id: str, new_creator_id: str) -> Tuple[bool, str]:
        """Transfer host privileges to another player.
        
        Args:
            table_id: ID of table
            current_creator_id: ID of current table creator
            new_creator_id: ID of new table creator
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"
            
            # Only current creator can transfer privileges
            if table.creator_id != current_creator_id:
                return False, "Only current table creator can transfer privileges"
            
            # Cannot transfer to yourself
            if current_creator_id == new_creator_id:
                return False, "Cannot transfer privileges to yourself"
            
            # Check if new creator is at the table
            from ..models.table_access import TableAccess
            new_creator_access = db.session.query(TableAccess).filter(
                TableAccess.table_id == table_id,
                TableAccess.user_id == new_creator_id,
                TableAccess.is_active == True,
                TableAccess.is_spectator == False
            ).first()
            
            if not new_creator_access:
                return False, "New host must be an active player at the table"
            
            # Check if hand is in progress
            if TableManager._is_hand_in_progress(table):
                return False, "Cannot transfer host privileges while hand is in progress"
            
            # Transfer privileges
            old_creator_id = table.creator_id
            table.creator_id = new_creator_id
            table.update_activity()
            
            db.session.commit()
            
            current_app.logger.info(f"Host privileges transferred from {old_creator_id} to {new_creator_id} for table {table_id}")
            return True, "Host privileges transferred successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to transfer host privileges: {e}")
            return False, "Failed to transfer host privileges"
    
    @staticmethod
    def close_table(table_id: str, creator_id: str, reason: str = "Manual closure") -> Tuple[bool, str]:
        """Manually close a table.
        
        Args:
            table_id: ID of table to close
            creator_id: ID of table creator
            reason: Reason for closure
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            table = TableManager.get_table_by_id(table_id)
            if not table:
                return False, "Table not found"
            
            # Only table creator can close table
            if table.creator_id != creator_id:
                return False, "Only table creator can close the table"
            
            # Check if hand is in progress
            if TableManager._is_hand_in_progress(table):
                return False, "Cannot close table while hand is in progress"
            
            # Notify players
            TableManager._notify_table_closure(table, reason)
            
            # Clean up access records
            from ..services.table_access_manager import TableAccessManager
            TableAccessManager._cleanup_table_access(table_id)
            
            # Remove table
            db.session.delete(table)
            db.session.commit()
            
            current_app.logger.info(f"Table {table_id} closed by creator {creator_id}. Reason: {reason}")
            return True, "Table closed successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to close table: {e}")
            return False, "Failed to close table"
    
    @staticmethod
    def cleanup_expired_private_tables() -> int:
        """Clean up expired private tables and their access permissions.
        
        Returns:
            Number of tables cleaned up
        """
        try:
            # For now, we'll consider private tables expired if they've been inactive for 24 hours
            # This could be made configurable
            expired_count = TableManager.close_inactive_tables(timeout_minutes=24 * 60)
            
            current_app.logger.info(f"Cleaned up {expired_count} expired private tables")
            return expired_count
            
        except Exception as e:
            current_app.logger.error(f"Failed to cleanup expired private tables: {e}")
            return 0
    
    @staticmethod
    def get_suggested_stakes(betting_structure: BettingStructure) -> List[Dict[str, Any]]:
        """Get suggested stakes configurations for a betting structure.
        
        Args:
            betting_structure: Betting structure to get suggestions for
            
        Returns:
            List of suggested stakes configurations
        """
        if betting_structure in [BettingStructure.NO_LIMIT, BettingStructure.POT_LIMIT]:
            return [
                {'name': 'Micro Stakes', 'stakes': {'small_blind': 1, 'big_blind': 2}},
                {'name': 'Low Stakes', 'stakes': {'small_blind': 5, 'big_blind': 10}},
                {'name': 'Medium Stakes', 'stakes': {'small_blind': 25, 'big_blind': 50}},
                {'name': 'High Stakes', 'stakes': {'small_blind': 100, 'big_blind': 200}},
                {'name': 'Nosebleed', 'stakes': {'small_blind': 500, 'big_blind': 1000}}
            ]
        else:  # Limit
            return [
                {'name': 'Micro Limit', 'stakes': {'small_bet': 2, 'big_bet': 4, 'ante': 0}},
                {'name': 'Low Limit', 'stakes': {'small_bet': 10, 'big_bet': 20, 'ante': 0}},
                {'name': 'Medium Limit', 'stakes': {'small_bet': 50, 'big_bet': 100, 'ante': 0}},
                {'name': 'High Limit', 'stakes': {'small_bet': 200, 'big_bet': 400, 'ante': 0}}
            ]