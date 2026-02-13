"""Game orchestration system for managing multiple concurrent poker games."""

import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime, timedelta
from flask import current_app
from threading import Lock
import uuid

from ..models.table import PokerTable
from ..models.table_access import TableAccess
from ..services.table_manager import TableManager
from ..services.table_access_manager import TableAccessManager
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction
from generic_poker.config.loader import GameRules


logger = logging.getLogger(__name__)


class GameSession:
    """Represents an active poker game session for a specific table."""
    
    def __init__(self, table: PokerTable, game_rules: GameRules):
        """Initialize a game session.
        
        Args:
            table: The poker table this session is for
            game_rules: Game rules for the poker variant
        """
        self.session_id = str(uuid.uuid4())
        self.table = table
        self.game_rules = game_rules
        
        # Create the underlying Game instance
        self.game = self._create_game_instance()
        
        # Session state
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.is_active = True
        self.is_paused = False
        self.pause_reason = None
        
        # Player management
        self.connected_players: Set[str] = set()
        self.disconnected_players: Dict[str, datetime] = {}
        self.spectators: Set[str] = set()
        
        # Hand tracking
        self.hands_played = 0
        self.current_hand_id = None
        
        logger.info(f"Created game session {self.session_id} for table {table.id}")
    
    def _create_game_instance(self) -> Game:
        """Create the underlying Game instance from table configuration."""
        return self.table.create_game_instance(self.game_rules)
    
    def add_player(self, user_id: str, username: str, buy_in_amount: int) -> Tuple[bool, str]:
        """Add a player to the game session.
        
        Args:
            user_id: User ID of the player
            username: Username of the player
            buy_in_amount: Amount the player is buying in with
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Check if game is paused
            if self.is_paused:
                return False, f"Game is paused: {self.pause_reason}"
            
            # Check if player is already in game
            if user_id in self.connected_players:
                return False, "Player already in game"
            
            # Add player to the underlying Game
            self.game.add_player(user_id, username, buy_in_amount)
            
            # Track player in session
            self.connected_players.add(user_id)
            
            # Remove from disconnected if they were there
            if user_id in self.disconnected_players:
                del self.disconnected_players[user_id]
            
            self.update_activity()
            
            logger.info(f"Player {username} ({user_id}) joined game session {self.session_id}")
            return True, "Player added successfully"
            
        except Exception as e:
            logger.error(f"Failed to add player {user_id} to session {self.session_id}: {e}")
            return False, str(e)
    
    def remove_player(self, user_id: str, reason: str = "Left game") -> Tuple[bool, str]:
        """Remove a player from the game session.
        
        Args:
            user_id: User ID of the player to remove
            reason: Reason for removal
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            if user_id not in self.connected_players:
                return False, "Player not in game"
            
            # Remove from underlying Game
            self.game.remove_player(user_id)
            
            # Update session tracking
            self.connected_players.discard(user_id)
            self.disconnected_players.pop(user_id, None)
            
            self.update_activity()
            
            # Check if we need to pause the game
            self._check_pause_conditions()
            
            logger.info(f"Player {user_id} removed from session {self.session_id}: {reason}")
            return True, "Player removed successfully"
            
        except Exception as e:
            logger.error(f"Failed to remove player {user_id} from session {self.session_id}: {e}")
            return False, str(e)
    
    def handle_player_disconnect(self, user_id: str) -> None:
        """Handle a player disconnection.
        
        Args:
            user_id: User ID of the disconnected player
        """
        if user_id in self.connected_players:
            self.connected_players.discard(user_id)
            self.disconnected_players[user_id] = datetime.utcnow()
            
            logger.info(f"Player {user_id} disconnected from session {self.session_id}")
            
            # Check if we need to pause the game
            self._check_pause_conditions()
    
    def handle_player_reconnect(self, user_id: str) -> Tuple[bool, str]:
        """Handle a player reconnection.
        
        Args:
            user_id: User ID of the reconnecting player
            
        Returns:
            Tuple of (success, error_message)
        """
        if user_id in self.disconnected_players:
            # Check if they've been disconnected too long
            disconnect_time = self.disconnected_players[user_id]
            if datetime.utcnow() - disconnect_time > timedelta(minutes=10):
                # Too long disconnected, remove them
                self.remove_player(user_id, "Disconnected too long")
                return False, "Disconnected too long, removed from game"
            
            # Reconnect the player
            self.connected_players.add(user_id)
            del self.disconnected_players[user_id]
            
            # Check if we can unpause the game
            self._check_unpause_conditions()
            
            logger.info(f"Player {user_id} reconnected to session {self.session_id}")
            return True, "Reconnected successfully"
        
        return False, "Player was not disconnected"
    
    def add_spectator(self, user_id: str) -> Tuple[bool, str]:
        """Add a spectator to the game session.
        
        Args:
            user_id: User ID of the spectator
            
        Returns:
            Tuple of (success, error_message)
        """
        if user_id in self.connected_players:
            return False, "User is already a player"
        
        self.spectators.add(user_id)
        self.update_activity()
        
        logger.info(f"Spectator {user_id} joined session {self.session_id}")
        return True, "Spectator added successfully"
    
    def remove_spectator(self, user_id: str) -> None:
        """Remove a spectator from the game session.
        
        Args:
            user_id: User ID of the spectator to remove
        """
        self.spectators.discard(user_id)
        logger.info(f"Spectator {user_id} removed from session {self.session_id}")
    
    def process_player_action(self, user_id: str, action: PlayerAction, amount: int = 0) -> Tuple[bool, str, Any]:
        """Process a player action in the game.
        
        Args:
            user_id: User ID of the acting player
            action: The action being taken
            amount: Amount for betting actions
            
        Returns:
            Tuple of (success, error_message, action_result)
        """
        try:
            if not self.is_active or self.is_paused:
                return False, "Game is not active", None
            
            if user_id not in self.connected_players:
                return False, "Player not in game", None
            
            # Process action through the underlying Game
            result = self.game.player_action(user_id, action, amount)
            
            if result.success:
                self.update_activity()
                
                # Check if hand completed
                if self.game.state == GameState.COMPLETE:
                    self.hands_played += 1
                    self.current_hand_id = None
                    
                    # Update player chip stacks in database
                    self._update_player_stacks()
                
                logger.info(f"Player {user_id} action {action} processed in session {self.session_id}")
            
            message = getattr(result, 'message', '') or ''
            return result.success, message, result
            
        except Exception as e:
            logger.error(f"Failed to process action for player {user_id} in session {self.session_id}: {e}")
            return False, str(e), None
    
    def _update_player_stacks(self) -> None:
        """Update player chip stacks in the database after a hand."""
        try:
            for player in self.game.table.players.values():
                TableAccessManager.update_player_stack(player.id, self.table.id, player.stack)
        except Exception as e:
            logger.error(f"Failed to update player stacks for session {self.session_id}: {e}")
    
    def _check_pause_conditions(self) -> None:
        """Check if the game should be paused."""
        active_player_count = len(self.connected_players)
        
        if active_player_count < 2:
            self.is_paused = True
            self.pause_reason = "Insufficient players (need at least 2)"
            logger.info(f"Game session {self.session_id} paused: {self.pause_reason}")
    
    def _check_unpause_conditions(self) -> None:
        """Check if the game can be unpaused."""
        if self.is_paused and len(self.connected_players) >= 2:
            self.is_paused = False
            self.pause_reason = None
            logger.info(f"Game session {self.session_id} unpaused")
    
    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.utcnow()
        self.table.update_activity()
    
    def is_inactive(self, timeout_minutes: int = 30) -> bool:
        """Check if the session has been inactive for too long.
        
        Args:
            timeout_minutes: Minutes of inactivity before considering inactive
            
        Returns:
            True if inactive, False otherwise
        """
        return datetime.utcnow() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the game session.
        
        Returns:
            Dictionary with session information
        """
        return {
            'session_id': self.session_id,
            'table_id': self.table.id,
            'table_name': self.table.name,
            'variant': self.table.variant,
            'betting_structure': self.table.betting_structure,
            'stakes': self.table.get_stakes(),
            'max_players': self.table.max_players,
            'connected_players': len(self.connected_players),
            'disconnected_players': len(self.disconnected_players),
            'spectators': len(self.spectators),
            'is_active': self.is_active,
            'is_paused': self.is_paused,
            'pause_reason': self.pause_reason,
            'game_state': self.game.state.value if self.game else 'unknown',
            'hands_played': self.hands_played,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat()
        }
    
    def cleanup(self) -> None:
        """Clean up the game session."""
        self.is_active = False
        self.connected_players.clear()
        self.disconnected_players.clear()
        self.spectators.clear()
        
        logger.info(f"Game session {self.session_id} cleaned up")


class GameOrchestrator:
    """Orchestrates multiple concurrent poker game sessions."""
    
    def __init__(self):
        """Initialize the game orchestrator."""
        self.sessions: Dict[str, GameSession] = {}  # table_id -> GameSession
        self.session_lock = Lock()
        
        logger.info("Game orchestrator initialized")
    
    def create_session(self, table_id: str) -> Tuple[bool, str, Optional[GameSession]]:
        """Create a new game session for a table.
        
        Args:
            table_id: ID of the table to create session for
            
        Returns:
            Tuple of (success, error_message, session)
        """
        with self.session_lock:
            try:
                # Check if session already exists
                if table_id in self.sessions:
                    return False, "Session already exists for this table", None
                
                # Get table information
                table = TableManager.get_table_by_id(table_id)
                if not table:
                    return False, "Table not found", None
                
                # Get game rules
                game_rules = TableManager.get_variant_rules(table.variant)
                if not game_rules:
                    return False, f"Game rules not found for variant {table.variant}", None
                
                # Create the session
                session = GameSession(table, game_rules)
                self.sessions[table_id] = session
                
                logger.info(f"Created game session for table {table_id}")
                return True, "Session created successfully", session
                
            except Exception as e:
                logger.error(f"Failed to create session for table {table_id}: {e}")
                return False, str(e), None
    
    def get_session(self, table_id: str) -> Optional[GameSession]:
        """Get a game session by table ID.
        
        Args:
            table_id: ID of the table
            
        Returns:
            GameSession if found, None otherwise
        """
        return self.sessions.get(table_id)
    
    def remove_session(self, table_id: str) -> bool:
        """Remove a game session.
        
        Args:
            table_id: ID of the table
            
        Returns:
            True if session was removed, False if not found
        """
        with self.session_lock:
            session = self.sessions.pop(table_id, None)
            if session:
                session.cleanup()
                logger.info(f"Removed game session for table {table_id}")
                return True
            return False
    
    def get_all_sessions(self) -> List[GameSession]:
        """Get all active game sessions.
        
        Returns:
            List of all GameSession instances
        """
        return list(self.sessions.values())
    
    def get_session_count(self) -> int:
        """Get the number of active sessions.

        Returns:
            Number of active sessions
        """
        return len(self.sessions)

    def clear_session(self, table_id: str) -> bool:
        """Clear/reset a game session for a table.

        Alias for remove_session, used by test cleanup.

        Args:
            table_id: ID of the table

        Returns:
            True if session was cleared, False if not found
        """
        return self.remove_session(table_id)

    def get_active_session_count(self) -> int:
        """Get the number of active game sessions.

        Alias for get_session_count, used by test status endpoint.

        Returns:
            Number of active sessions
        """
        return self.get_session_count()
    
    def cleanup_inactive_sessions(self, timeout_minutes: int = 30) -> int:
        """Clean up inactive game sessions.
        
        Args:
            timeout_minutes: Minutes of inactivity before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        with self.session_lock:
            inactive_sessions = []
            
            for table_id, session in self.sessions.items():
                if session.is_inactive(timeout_minutes):
                    inactive_sessions.append(table_id)
            
            cleaned_count = 0
            for table_id in inactive_sessions:
                # Remove session directly without calling remove_session to avoid deadlock
                session = self.sessions.pop(table_id, None)
                if session:
                    session.cleanup()
                    cleaned_count += 1
                    logger.info(f"Removed game session for table {table_id}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive game sessions")
            
            return cleaned_count
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get statistics about the orchestrator.
        
        Returns:
            Dictionary with orchestrator statistics
        """
        active_sessions = 0
        paused_sessions = 0
        total_players = 0
        total_spectators = 0
        
        for session in self.sessions.values():
            if session.is_active:
                active_sessions += 1
                if session.is_paused:
                    paused_sessions += 1
                total_players += len(session.connected_players)
                total_spectators += len(session.spectators)
        
        return {
            'total_sessions': len(self.sessions),
            'active_sessions': active_sessions,
            'paused_sessions': paused_sessions,
            'total_players': total_players,
            'total_spectators': total_spectators,
            'average_players_per_session': total_players / max(active_sessions, 1)
        }


# Global orchestrator instance
game_orchestrator = GameOrchestrator()