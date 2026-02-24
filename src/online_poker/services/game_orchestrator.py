"""Game orchestration system for managing multiple concurrent poker games."""

import logging
import uuid
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from generic_poker.config.loader import GameActionType, GameRules
from generic_poker.config.mixed_game_loader import MixedGameConfig
from generic_poker.game.game import Game
from generic_poker.game.game_state import GameState, PlayerAction

from ..models.table import PokerTable
from ..services.table_access_manager import TableAccessManager
from ..services.table_manager import TableManager

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
        self.connected_players: set[str] = set()
        self.disconnected_players: dict[str, datetime] = {}
        self.spectators: set[str] = set()
        self.pending_leaves: set[str] = set()  # Players who clicked Leave mid-hand

        # Hand tracking
        self.hands_played = 0
        self.current_hand_id = None

        # Mixed game rotation state
        self.mixed_game_config: MixedGameConfig | None = None
        self.current_variant_index: int = 0
        self.hands_in_current_variant: int = 0
        self.orbit_size: int = 0  # Number of hands per orbit (= player count at rotation start)

        logger.info(f"Created game session {self.session_id} for table {table.id}")

    def _create_game_instance(self) -> Game:
        """Create the underlying Game instance from table configuration."""
        return self.table.create_game_instance(self.game_rules)

    def add_player(
        self, user_id: str, username: str, buy_in_amount: int, seat_number: int | None = None
    ) -> tuple[bool, str]:
        """Add a player to the game session.

        Args:
            user_id: User ID of the player
            username: Username of the player
            buy_in_amount: Amount the player is buying in with
            seat_number: Preferred seat number (from DB), or None for auto-assign

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
            self.game.add_player(user_id, username, buy_in_amount, preferred_seat=seat_number)

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

    def remove_player(self, user_id: str, reason: str = "Left game") -> tuple[bool, str]:
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
            self.pending_leaves.discard(user_id)

            self.update_activity()

            # Check if we need to pause the game
            self._check_pause_conditions()

            # Deactivate session if no players remain
            if not self.connected_players:
                self.is_active = False
                logger.info(f"Session {self.session_id} deactivated (no players remaining)")

            logger.info(f"Player {user_id} removed from session {self.session_id}: {reason}")
            return True, "Player removed successfully"

        except Exception as e:
            logger.error(f"Failed to remove player {user_id} from session {self.session_id}: {e}")
            return False, str(e)

    def mark_player_leaving(self, user_id: str) -> tuple[bool, str]:
        """Mark a player as leaving and fold them immediately.

        This is an intentional leave (not a disconnect), so no grace period.

        If a hand is active:
        - If it's the player's turn, fold via normal game action
        - If not their turn, directly mark as inactive (out-of-turn fold)
        - Either way, if only 1 active player remains, the hand completes

        If no hand is active, remove immediately.

        Args:
            user_id: User ID of the player leaving

        Returns:
            Tuple of (hand_completed, message)
        """
        try:
            if user_id not in self.connected_players:
                return False, "Player not in game"

            # Check if a hand is in progress
            hand_active = self.game and self.game.state in (
                GameState.BETTING,
                GameState.DEALING,
                GameState.SHOWDOWN,
                GameState.DRAWING,
            )

            if not hand_active:
                # No hand active, remove immediately
                self.remove_player(user_id, "Player left table")
                return False, "Removed immediately (no active hand)"

            # Hand is active - add to pending leaves
            self.pending_leaves.add(user_id)

            # Check if the player is even in the hand (may have already folded)
            player = self.game.table.players.get(user_id)
            if not player or not player.is_active:
                logger.info(f"Player {user_id} already folded/inactive, marked for post-hand removal")
                return False, "Marked for removal after hand"

            # If this player is the current player, fold via normal game action
            if (
                self.game.current_player
                and self.game.current_player.id == user_id
                and self.game.state == GameState.BETTING
            ):
                success, message, result = self.process_player_action(user_id, PlayerAction.FOLD, 0)
                if success:
                    logger.info(f"Auto-folded leaving player {user_id} (was current player)")
                    return self.game.state == GameState.COMPLETE, "Folded and marked for removal"
                else:
                    logger.warning(f"Failed to auto-fold leaving player {user_id}: {message}")

            # Not current player (or fold failed): directly mark as inactive
            # This is safe for intentional leaves — no grace period needed
            if player.is_active:
                player.is_active = False
                # Mark bet as acted so betting round logic isn't stuck
                from generic_poker.game.betting import PlayerBet

                bet = self.game.betting.current_bets.get(user_id, PlayerBet())
                bet.has_acted = True
                self.game.betting.current_bets[user_id] = bet

                logger.info(f"Directly folded leaving player {user_id} (not current player)")

                # Check if only 1 active player remains → hand should complete
                active_players = [p for p in self.game.table.players.values() if p.is_active]
                if len(active_players) == 1:
                    self.game._handle_fold_win()
                    logger.info("Hand completed after leaving player fold (last player standing)")
                    return True, "Folded (out of turn) and hand completed"

            return False, "Folded and marked for post-hand removal"

        except Exception as e:
            logger.error(f"Failed to mark player {user_id} as leaving: {e}")
            return False, str(e)

    def auto_fold_pending_player(self) -> tuple[bool, str | None]:
        """Check if the current player is pending leave and auto-fold them.

        Should be called after any game state change that sets a new current player.

        Returns:
            Tuple of (player_was_folded, folded_user_id)
        """
        try:
            if not self.game or not self.game.current_player:
                return False, None

            current_id = self.game.current_player.id
            if current_id not in self.pending_leaves:
                return False, None

            if self.game.state != GameState.BETTING:
                return False, None

            # Auto-fold the pending player
            success, message, result = self.process_player_action(current_id, PlayerAction.FOLD, 0)

            if success:
                logger.info(f"Auto-folded pending-leave player {current_id}")
                return True, current_id
            else:
                logger.warning(f"Failed to auto-fold pending-leave player {current_id}: {message}")
                return False, None

        except Exception as e:
            logger.error(f"Failed to auto-fold pending player: {e}")
            return False, None

    def process_pending_leaves(self) -> list[str]:
        """Process all pending leaves after a hand completes.

        Removes players from the game engine who clicked Leave during the hand.

        Returns:
            List of removed user IDs
        """
        if not self.pending_leaves:
            return []

        removed = []
        for user_id in list(self.pending_leaves):
            try:
                if user_id in self.connected_players:
                    self.remove_player(user_id, "Left during hand")
                    removed.append(user_id)
                    logger.info(f"Removed pending-leave player {user_id} after hand completion")
            except Exception as e:
                logger.error(f"Failed to remove pending-leave player {user_id}: {e}")

        self.pending_leaves.clear()
        return removed

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

    def handle_player_reconnect(self, user_id: str) -> tuple[bool, str]:
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

    def add_spectator(self, user_id: str) -> tuple[bool, str]:
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

    def process_player_action(
        self, user_id: str, action: PlayerAction, amount: int = 0, cards=None, declaration_data=None
    ) -> tuple[bool, str, Any]:
        """Process a player action in the game.

        Args:
            user_id: User ID of the acting player
            action: The action being taken
            amount: Amount for betting actions
            cards: Cards for draw/discard actions
            declaration_data: Declaration data for declare actions

        Returns:
            Tuple of (success, error_message, action_result)
        """
        try:
            if not self.is_active or self.is_paused:
                return False, "Game is not active", None

            if user_id not in self.connected_players:
                return False, "Player not in game", None

            # Process action through the underlying Game
            result = self.game.player_action(user_id, action, amount, cards=cards, declaration_data=declaration_data)

            if result.success:
                self.update_activity()

                # Check if hand completed
                if self.game.state == GameState.COMPLETE:
                    self.hands_played += 1
                    self.current_hand_id = None
                    self.increment_variant_hand_count()

                    # Update player chip stacks in database
                    self._update_player_stacks()

                logger.info(f"Player {user_id} action {action} processed in session {self.session_id}")

            message = getattr(result, "message", "") or ""
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

    def get_session_info(self) -> dict[str, Any]:
        """Get information about the game session.

        Returns:
            Dictionary with session information
        """
        return {
            "session_id": self.session_id,
            "table_id": self.table.id,
            "table_name": self.table.name,
            "variant": self.table.variant,
            "betting_structure": self.table.betting_structure,
            "stakes": self.table.get_stakes(),
            "max_players": self.table.max_players,
            "connected_players": len(self.connected_players),
            "disconnected_players": len(self.disconnected_players),
            "spectators": len(self.spectators),
            "is_active": self.is_active,
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason,
            "game_state": self.game.state.value if self.game else "unknown",
            "hands_played": self.hands_played,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }

    # --- Mixed game rotation ---

    def should_rotate(self) -> bool:
        """Check if it's time to rotate to the next variant in a mixed game.

        Returns True when the current variant has completed a full orbit
        (one hand per player at the table when the variant started).
        """
        if not self.mixed_game_config:
            return False
        if self.orbit_size <= 0:
            return False
        return self.hands_in_current_variant >= self.orbit_size

    def rotate_variant(self) -> str:
        """Advance to the next variant in the rotation.

        Preserves player stacks, seats, and dealer button position.

        Returns:
            Display name of the new variant.
        """
        if not self.mixed_game_config:
            return ""

        # Advance index (wrap around)
        self.current_variant_index = (self.current_variant_index + 1) % len(self.mixed_game_config.rotation)
        self.hands_in_current_variant = 0
        # Recalculate orbit size based on current player count
        self.orbit_size = len(self.game.table.players)

        self._swap_game_for_variant()

        new_rules = self.game_rules
        logger.info(f"Session {self.session_id} rotated to variant {self.current_variant_index}: {new_rules.game}")
        return new_rules.game

    def _swap_game_for_variant(self) -> None:
        """Create a new Game instance for the current variant in the rotation.

        Preserves players (IDs, names, stacks, seats) and dealer button position.
        """
        mixed_variant = self.mixed_game_config.rotation[self.current_variant_index]

        # Load new rules
        new_rules = TableManager.get_variant_rules(mixed_variant.variant)
        if not new_rules:
            logger.error(f"Cannot load rules for variant {mixed_variant.variant}")
            return

        # Save current state
        player_data = {}
        for pid, player in self.game.table.players.items():
            player_data[pid] = {
                "name": player.name,
                "stack": player.stack,
                "seat": player.position,
            }
        button_seat = self.game.table.button_seat

        # Update rules and create new game
        self.game_rules = new_rules
        self.game = self.table.create_game_instance_for_variant(new_rules, mixed_variant.betting_structure)

        # Restore players
        for pid, data in player_data.items():
            self.game.add_player(pid, data["name"], data["stack"], preferred_seat=data["seat"])

        # Restore dealer button
        self.game.table.button_seat = button_seat

    def increment_variant_hand_count(self) -> None:
        """Increment the hand counter for the current variant in a mixed game."""
        if self.mixed_game_config:
            self.hands_in_current_variant += 1

    def get_mixed_game_info(self) -> dict[str, Any] | None:
        """Get rotation info for the frontend.

        Returns:
            Dict with rotation state, or None if not a mixed game.
        """
        if not self.mixed_game_config:
            return None

        rotation_display = []
        for v in self.mixed_game_config.rotation:
            rules = TableManager.get_variant_rules(v.variant)
            rotation_display.append(rules.game if rules else v.variant)

        return {
            "name": self.mixed_game_config.display_name,
            "current_variant": self.game_rules.game,
            "current_variant_index": self.current_variant_index,
            "rotation_variants": rotation_display,
            "rotation_letters": [v.letter for v in self.mixed_game_config.rotation],
            "hands_until_rotation": max(0, self.orbit_size - self.hands_in_current_variant),
            "orbit_size": self.orbit_size,
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
        self.sessions: dict[str, GameSession] = {}  # table_id -> GameSession
        self.session_lock = Lock()

        logger.info("Game orchestrator initialized")

    def create_session(self, table_id: str) -> tuple[bool, str, GameSession | None]:
        """Create a new game session for a table.

        Handles both single-variant tables and mixed game tables (HORSE, 8-Game Mix).

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

                # Check if this is a mixed game
                mixed_config = TableManager.get_mixed_game_config(table.variant)
                if mixed_config:
                    # Load the first variant in the rotation
                    first_variant = mixed_config.rotation[0]
                    game_rules = TableManager.get_variant_rules(first_variant.variant)
                    if not game_rules:
                        return (
                            False,
                            f"Game rules not found for variant {first_variant.variant}",
                            None,
                        )

                    session = GameSession(table, game_rules)
                    session.mixed_game_config = mixed_config
                    session.current_variant_index = 0
                    session.hands_in_current_variant = 0
                    # orbit_size set when first hand starts (need player count)
                else:
                    # Standard single-variant table
                    game_rules = TableManager.get_variant_rules(table.variant)
                    if not game_rules:
                        return (
                            False,
                            f"Game rules not found for variant {table.variant}",
                            None,
                        )
                    session = GameSession(table, game_rules)

                self.sessions[table_id] = session

                logger.info(f"Created game session for table {table_id}")
                return True, "Session created successfully", session

            except Exception as e:
                logger.error(f"Failed to create session for table {table_id}: {e}")
                return False, str(e), None

    def get_session(self, table_id: str) -> GameSession | None:
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
                self._deactivate_session_state(table_id)
                logger.info(f"Removed game session for table {table_id}")
                return True
            return False

    def get_all_sessions(self) -> list[GameSession]:
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
                    self._deactivate_session_state(table_id)
                    cleaned_count += 1
                    logger.info(f"Removed game session for table {table_id}")

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive game sessions")

            return cleaned_count

    def _deactivate_session_state(self, table_id: str) -> None:
        """Mark the persisted session state as inactive in the database.

        Args:
            table_id: ID of the table
        """
        try:
            from ..database import db
            from ..models.game_session_state import GameSessionState

            state = db.session.query(GameSessionState).filter_by(table_id=table_id).first()
            if state:
                state.is_active = False
                db.session.commit()
                logger.info(f"Deactivated session state for table {table_id}")
        except Exception as e:
            logger.error(f"Failed to deactivate session state for table {table_id}: {e}")
            try:
                from ..database import db

                db.session.rollback()
            except Exception as rollback_err:
                logger.error(f"Failed to rollback after session state deactivation error: {rollback_err}")

    @staticmethod
    def advance_through_non_player_steps(game) -> None:
        """Advance past dealing/empty-betting states until player input is needed.

        Used after processing a player action with advance_step=True, or after
        starting a hand. Skips DEALING steps (unless CHOOSE) and BETTING steps
        with no current player.

        Args:
            game: The Game instance to advance
        """
        while game.state != GameState.COMPLETE:
            if game.current_step >= len(game.rules.gameplay):
                break
            # DEALING state — auto-advance unless it's a CHOOSE step
            if game.state == GameState.DEALING:
                current_step = game.rules.gameplay[game.current_step]
                if current_step.action_type == GameActionType.CHOOSE:
                    break  # Wait for player choice
                game._next_step()
            # BETTING state with no current player — round complete, advance
            elif game.state == GameState.BETTING and game.current_player is None:
                game._next_step()
            else:
                # Player input required (BETTING/DRAWING with current_player set)
                break

    def get_orchestrator_stats(self) -> dict[str, Any]:
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
            "total_sessions": len(self.sessions),
            "active_sessions": active_sessions,
            "paused_sessions": paused_sessions,
            "total_players": total_players,
            "total_spectators": total_spectators,
            "average_players_per_session": total_players / max(active_sessions, 1),
        }


# Global orchestrator instance
game_orchestrator = GameOrchestrator()
