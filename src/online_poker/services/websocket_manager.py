"""WebSocket manager for real-time communication."""

import logging
import uuid
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from flask import current_app
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_login import current_user

from ..models.table_access import TableAccess
from ..services.player_session_manager import PlayerSessionManager
from ..services.game_state_manager import GameStateManager
from ..database import db


logger = logging.getLogger(__name__)


class GameEvent:
    """Event types for real-time communication."""
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    GAME_STATE_UPDATE = "game_state_update"
    PLAYER_ACTION = "player_action"
    HAND_COMPLETE = "hand_complete"
    CHAT_MESSAGE = "chat_message"
    PLAYER_DISCONNECTED = "player_disconnected"
    PLAYER_RECONNECTED = "player_reconnected"
    TABLE_UPDATE = "table_update"
    ERROR = "error"
    NOTIFICATION = "notification"
    READY_STATUS_UPDATE = "ready_status_update"
    HAND_STARTING = "hand_starting"


class WebSocketManager:
    """Manager for WebSocket connections and real-time communication."""
    
    def __init__(self, socketio: SocketIO):
        """Initialize the WebSocket manager.
        
        Args:
            socketio: Flask-SocketIO instance
        """
        self.socketio = socketio
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id
        self.session_users: Dict[str, str] = {}  # session_id -> user_id
        self.table_rooms: Dict[str, Set[str]] = {}  # table_id -> set of session_ids
        self.user_tables: Dict[str, str] = {}  # user_id -> table_id
        
        # Register event handlers
        self._register_handlers()
        
        logger.info("WebSocket manager initialized")
    
    def _register_handlers(self):
        """Register WebSocket event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """Handle client connection."""
            try:
                from flask import request

                session_id = request.sid

                # Allow unauthenticated connections for lobby browsing
                if current_user.is_authenticated:
                    user_id = current_user.id

                    # Store session mapping
                    self.user_sessions[user_id] = session_id
                    self.session_users[session_id] = user_id

                    logger.info(f"User {current_user.username} ({user_id}) connected with session {session_id}")

                    # Send connection confirmation
                    emit('connected', {
                        'user_id': user_id,
                        'username': current_user.username,
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    })
                else:
                    # Guest user (not authenticated)
                    logger.info(f"Guest user connected with session {session_id}")

                    emit('connected', {
                        'user_id': None,
                        'username': 'Guest',
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    })

                return True

            except Exception as e:
                logger.error(f"Connection error: {e}")
                disconnect()
                return False
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            try:
                from flask import request
                
                session_id = request.sid
                user_id = self.session_users.get(session_id)
                
                if user_id:
                    # Handle table disconnection
                    table_id = self.user_tables.get(user_id)
                    if table_id:
                        self.handle_table_disconnect(user_id, table_id)
                    
                    # Clean up session mappings
                    self.user_sessions.pop(user_id, None)
                    self.session_users.pop(session_id, None)
                    self.user_tables.pop(user_id, None)
                    
                    logger.info(f"User {user_id} disconnected")
                
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
        
        @self.socketio.on('connect_to_table_room')
        def handle_connect_to_table_room(data):
            """Handle connecting to a table's socket room (for players already seated)."""
            try:
                table_id = data.get('table_id')
                if not table_id:
                    emit('error', {'message': 'Table ID required'})
                    return
                
                user_id = current_user.id
                success = self.join_table_room(user_id, table_id)
                
                if success:
                    # Send current game state
                    game_state = GameStateManager.generate_game_state_view(
                        table_id, user_id
                    )
                    if game_state:
                        emit('game_state_update', game_state.to_dict())
                    
                    emit('table_joined', {
                        'table_id': table_id,
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    })
                else:
                    emit('error', {'message': 'Failed to join table room'})
                
            except Exception as e:
                logger.error(f"Join table error: {e}")
                emit('error', {'message': 'Failed to join table'})
        
        @self.socketio.on('leave_table')
        def handle_leave_table(data):
            """Handle leaving a table room."""
            try:
                table_id = data.get('table_id')
                if not table_id:
                    emit('error', {'message': 'Table ID required'})
                    return

                user_id = current_user.id

                # Leave the WebSocket room
                self.leave_table_room(user_id, table_id)

                # Actually remove player from the table in the database
                from ..services.table_access_manager import TableAccessManager
                from ..services.table_manager import TableManager
                success, message = TableAccessManager.leave_table(user_id, table_id)
                if not success:
                    logger.warning(f"Failed to leave table in database: {message}")
                else:
                    logger.info(f"User {user_id} left table {table_id}")

                    # Broadcast table update to all lobby users so they see updated player count
                    table = TableManager.get_table_by_id(table_id)
                    if table:
                        self.socketio.emit('table_updated', {
                            'table': table.to_dict(),
                            'action': 'player_left'
                        })

                emit('left_table', {
                    'table_id': table_id,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })

            except Exception as e:
                logger.error(f"Leave table error: {e}")
                emit('error', {'message': 'Failed to leave table'})
        
        @self.socketio.on('chat_message')
        def handle_chat_message(data):
            """Handle chat message."""
            try:
                table_id = data.get('table_id')
                message = data.get('message', '').strip()
                
                if not table_id or not message:
                    emit('error', {'message': 'Table ID and message required'})
                    return
                
                user_id = current_user.id
                
                # Check if user has access to this table
                player_info = PlayerSessionManager.get_player_info(user_id, table_id)
                if not player_info:
                    emit('error', {'message': 'No access to this table'})
                    return
                
                # Process message through chat service
                from ..services.chat_service import ChatService
                chat_service = ChatService()
                # Convert string IDs to UUID objects for ChatService
                table_uuid = uuid.UUID(table_id) if isinstance(table_id, str) else table_id
                user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
                chat_message = chat_service.send_message(
                    table_id=table_uuid,
                    user_id=user_uuid,
                    message=message
                )
                
                if not chat_message:
                    emit('error', {'message': 'Message blocked or user is muted'})
                    return
                
                # Broadcast chat message to table
                chat_data = chat_message.to_dict()
                chat_data['is_spectator'] = player_info['is_spectator']
                
                self.broadcast_to_table(table_id, GameEvent.CHAT_MESSAGE, chat_data)
                
                # Send confirmation to sender
                emit('message_sent', {
                    'message_id': str(chat_message.id),
                    'timestamp': chat_message.created_at.isoformat()
                })
                
            except Exception as e:
                logger.error(f"Chat message error: {e}")
                emit('error', {'message': 'Failed to send message'})
        
        @self.socketio.on('player_action')
        def handle_player_action(data):
            """Handle player action."""
            try:
                table_id = data.get('table_id')
                action = data.get('action')
                amount = data.get('amount', 0)
                
                if not table_id or not action:
                    emit('error', {'message': 'Table ID and action required'})
                    return
                
                user_id = current_user.id
                
                # Process action through game orchestrator
                from ..services.game_orchestrator import game_orchestrator
                session = game_orchestrator.get_session(table_id)
                if not session:
                    emit('error', {'message': 'Game session not found'})
                    return
                
                from generic_poker.game.game_state import PlayerAction
                try:
                    player_action = PlayerAction(action.upper())
                except ValueError:
                    emit('error', {'message': f'Invalid action: {action}'})
                    return
                
                success, message, result = session.process_player_action(
                    user_id, player_action, amount
                )

                if success:
                    # Check if we need to advance to the next step (betting round complete)
                    game = session.game
                    if result and hasattr(result, 'advance_step') and result.advance_step:
                        from generic_poker.game.game_state import GameState
                        if game and game.state != GameState.COMPLETE:
                            logger.info(f"Betting round complete, advancing to next step")

                            # Track community cards for phase change detection
                            prev_community_count = len(game.table.community_cards) if hasattr(game.table, 'community_cards') else 0

                            game._next_step()
                            # Continue advancing through dealing/non-player-input steps
                            # Check for DEALING state (doesn't require player input) OR no current player
                            while game.state != GameState.COMPLETE:
                                if game.current_step >= len(game.rules.gameplay):
                                    break

                                # Check for new community cards and emit phase change
                                curr_community_count = len(game.table.community_cards) if hasattr(game.table, 'community_cards') else 0
                                if curr_community_count > prev_community_count:
                                    community_cards = game.table.community_cards
                                    cards_str = ' '.join(str(c) for c in community_cards)
                                    if curr_community_count == 3:
                                        self.broadcast_game_action_chat(table_id, f"*** FLOP *** [{cards_str}]", 'deal')
                                    elif curr_community_count == 4:
                                        turn_card = community_cards[-1]
                                        self.broadcast_game_action_chat(table_id, f"*** TURN *** [{cards_str}]", 'deal')
                                    elif curr_community_count == 5:
                                        river_card = community_cards[-1]
                                        self.broadcast_game_action_chat(table_id, f"*** RIVER *** [{cards_str}]", 'deal')
                                    prev_community_count = curr_community_count

                                # DEALING state doesn't require player input - auto advance
                                if game.state == GameState.DEALING:
                                    game._next_step()
                                # BETTING state with no current player - round complete, advance
                                elif game.state == GameState.BETTING and game.current_player is None:
                                    game._next_step()
                                else:
                                    # Player input required
                                    break
                            logger.info(f"Game advanced to step {game.current_step}, state {game.state}, current_player: {game.current_player.name if game.current_player else None}")

                    # Broadcast action to all table participants
                    action_data = {
                        'user_id': user_id,
                        'username': current_user.username,
                        'action': action,
                        'amount': amount,
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    }

                    self.broadcast_to_table(table_id, GameEvent.PLAYER_ACTION, action_data)

                    # Broadcast game action to chat
                    action_lower = action.lower()
                    if action_lower == 'fold':
                        action_message = f"{current_user.username} folds"
                    elif action_lower == 'check':
                        action_message = f"{current_user.username} checks"
                    elif action_lower == 'call':
                        action_message = f"{current_user.username} calls ${amount}" if amount else f"{current_user.username} calls"
                    elif action_lower == 'bet':
                        action_message = f"{current_user.username} bets ${amount}"
                    elif action_lower == 'raise':
                        action_message = f"{current_user.username} raises to ${amount}"
                    elif action_lower == 'all_in' or action_lower == 'all-in':
                        action_message = f"{current_user.username} is all-in for ${amount}"
                    else:
                        action_message = f"{current_user.username}: {action} ${amount}" if amount else f"{current_user.username}: {action}"
                    self.broadcast_game_action_chat(table_id, action_message, 'player_action')

                    # Send updated game state to all participants
                    self.broadcast_game_state_update(table_id)

                    emit('action_result', {
                        'success': True,
                        'message': message
                    })
                else:
                    emit('error', {'message': message})
                
            except Exception as e:
                logger.error(f"Player action error: {e}")
                emit('error', {'message': 'Failed to process action'})
        
        @self.socketio.on('request_game_state')
        def handle_game_state_request(data):
            """Handle game state request."""
            try:
                table_id = data.get('table_id')
                if not table_id:
                    emit('error', {'message': 'Table ID required'})
                    return
                
                user_id = current_user.id
                
                # Check access
                player_info = PlayerSessionManager.get_player_info(user_id, table_id)
                is_spectator = player_info['is_spectator'] if player_info else True
                
                # Generate and send game state
                game_state = GameStateManager.generate_game_state_view(
                    table_id, user_id, is_spectator
                )
                
                if game_state:
                    emit('game_state_update', game_state.to_dict())
                # If no game state, silently skip - game may not have started yet
                
            except Exception as e:
                logger.error(f"Game state request error: {e}")
                emit('error', {'message': 'Failed to get game state'})
        
        @self.socketio.on('request_chat_history')
        def handle_chat_history_request(data):
            """Handle chat history request."""
            try:
                table_id = data.get('table_id')
                limit = data.get('limit', 50)
                
                if not table_id:
                    emit('error', {'message': 'Table ID required'})
                    return
                
                user_id = current_user.id
                
                # Check if user has access to this table
                player_info = PlayerSessionManager.get_player_info(user_id, table_id)
                if not player_info:
                    emit('error', {'message': 'No access to this table'})
                    return
                
                # Get chat history
                from ..services.chat_service import ChatService
                chat_service = ChatService()
                messages = chat_service.get_table_messages(table_id, limit)
                chat_history = [msg.to_dict() for msg in messages]
                
                emit('chat_history', {
                    'table_id': table_id,
                    'messages': chat_history
                })
                
            except Exception as e:
                logger.error(f"Chat history request error: {e}")
                emit('error', {'message': 'Failed to get chat history'})
        
        @self.socketio.on('moderate_user')
        def handle_moderate_user(data):
            """Handle user moderation request."""
            try:
                table_id = data.get('table_id')
                target_user_id = data.get('target_user_id')
                action_type = data.get('action_type')
                reason = data.get('reason', '')
                duration_minutes = data.get('duration_minutes')
                
                if not all([table_id, target_user_id, action_type]):
                    emit('error', {'message': 'Table ID, target user ID, and action type required'})
                    return
                
                user_id = current_user.id
                
                # Check if user is table creator or has moderation rights
                from ..models.table import PokerTable
                table = db.session.query(PokerTable).filter(
                    PokerTable.id == table_id
                ).first()
                
                if not table:
                    emit('error', {'message': 'Table not found'})
                    return
                
                if table.creator_id != user_id:
                    emit('error', {'message': 'Only table creator can moderate users'})
                    return
                
                # Apply moderation
                from ..services.chat_service import ChatService
                chat_service = ChatService()
                
                if action_type == 'mute':
                    mute_action = chat_service.mute_user(
                        table_id=table_id,
                        target_user_id=target_user_id,
                        moderator_user_id=user_id,
                        duration_minutes=duration_minutes,
                        reason=reason
                    )
                    success = True
                    message = f"User muted successfully"
                elif action_type == 'unmute':
                    unmute_action = chat_service.unmute_user(
                        table_id=table_id,
                        target_user_id=target_user_id,
                        moderator_user_id=user_id
                    )
                    success = unmute_action is not None
                    message = "User unmuted successfully" if success else "User was not muted"
                else:
                    success = False
                    message = f"Unsupported moderation action: {action_type}"
                
                if success:
                    emit('moderation_result', {
                        'success': True,
                        'message': message
                    })
                    
                    # Notify the moderated user
                    self.send_to_user(target_user_id, GameEvent.NOTIFICATION, {
                        'message': f'You have been {action_type}d in table {table.name}. Reason: {reason}',
                        'type': 'warning',
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    })
                    
                    # Broadcast moderation action to table (optional)
                    if action_type in ['ban', 'kick']:
                        self.broadcast_to_table(table_id, 'user_moderated', {
                            'target_user_id': target_user_id,
                            'action_type': action_type,
                            'reason': reason,
                            'timestamp': datetime.utcnow().isoformat() + 'Z'
                        })
                else:
                    emit('error', {'message': message})
                
            except Exception as e:
                logger.error(f"User moderation error: {e}")
                emit('error', {'message': 'Failed to moderate user'})
        
        @self.socketio.on('toggle_chat')
        def handle_toggle_chat(data):
            """Handle chat toggle request."""
            try:
                table_id = data.get('table_id')
                enabled = data.get('enabled', True)

                if not table_id:
                    emit('error', {'message': 'Table ID required'})
                    return

                user_id = current_user.id

                # Store user's chat preference (could be stored in session or database)
                # For now, just acknowledge the toggle
                emit('chat_toggled', {
                    'table_id': table_id,
                    'enabled': enabled,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })

            except Exception as e:
                logger.error(f"Chat toggle error: {e}")
                emit('error', {'message': 'Failed to toggle chat'})

        @self.socketio.on('set_ready')
        def handle_set_ready(data):
            """Handle player ready status change."""
            try:
                table_id = data.get('table_id')
                ready = data.get('ready', True)

                if not table_id:
                    emit('error', {'message': 'Table ID required'})
                    return

                user_id = current_user.id

                # Update ready status in database
                from ..services.table_access_manager import TableAccessManager
                success, message = TableAccessManager.set_player_ready(user_id, table_id, ready)

                if not success:
                    emit('error', {'message': message})
                    return

                # Get updated ready status for all players
                ready_status = TableAccessManager.get_ready_status(table_id)

                # Broadcast ready status to all table participants
                self.broadcast_to_table(table_id, GameEvent.READY_STATUS_UPDATE, {
                    'table_id': table_id,
                    'ready_status': ready_status,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })

                # If all players are ready, start the hand
                if ready_status['all_ready']:
                    self._start_hand_when_ready(table_id, ready_status)

            except Exception as e:
                logger.error(f"Set ready error: {e}")
                emit('error', {'message': 'Failed to update ready status'})

        @self.socketio.on('request_ready_status')
        def handle_request_ready_status(data):
            """Handle request for current ready status."""
            try:
                table_id = data.get('table_id')

                if not table_id:
                    emit('error', {'message': 'Table ID required'})
                    return

                from ..services.table_access_manager import TableAccessManager
                from ..services.game_orchestrator import game_orchestrator
                ready_status = TableAccessManager.get_ready_status(table_id)

                emit(GameEvent.READY_STATUS_UPDATE, {
                    'table_id': table_id,
                    'ready_status': ready_status,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })

                # If all players are ready but no game session exists (e.g., after server restart),
                # start the hand
                if ready_status['all_ready']:
                    session = game_orchestrator.get_session(table_id)
                    if not session or not session.game:
                        logger.info(f"All players ready at table {table_id} with no active game - starting hand")
                        self._start_hand_when_ready(table_id, ready_status)

            except Exception as e:
                logger.error(f"Request ready status error: {e}")
                emit('error', {'message': 'Failed to get ready status'})
    
    def join_table_room(self, user_id: str, table_id: str) -> bool:
        """Join a user to a table room.
        
        Args:
            user_id: ID of the user
            table_id: ID of the table
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_id = self.user_sessions.get(user_id)
            if not session_id:
                logger.warning(f"No session found for user {user_id}")
                return False
            
            # Join the room
            join_room(f"table_{table_id}", sid=session_id)
            
            # Track room membership
            if table_id not in self.table_rooms:
                self.table_rooms[table_id] = set()
            self.table_rooms[table_id].add(session_id)
            self.user_tables[user_id] = table_id
            
            logger.info(f"User {user_id} joined table room {table_id}")

            # Get username for the notification
            username = 'A player'
            try:
                from ..services.user_manager import UserManager
                user_manager = UserManager()
                user = user_manager.get_user_by_id(user_id)
                if user:
                    username = user.username
            except Exception as e:
                logger.warning(f"Could not get username for player_joined event: {e}")

            # Notify other participants
            self.broadcast_to_table(table_id, GameEvent.PLAYER_JOINED, {
                'user_id': user_id,
                'username': username,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, exclude_user=user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to join table room: {e}")
            return False
    
    def leave_table_room(self, user_id: str, table_id: str) -> bool:
        """Remove a user from a table room.
        
        Args:
            user_id: ID of the user
            table_id: ID of the table
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_id = self.user_sessions.get(user_id)
            if not session_id:
                return False
            
            # Leave the room
            leave_room(f"table_{table_id}", sid=session_id)
            
            # Update tracking
            if table_id in self.table_rooms:
                self.table_rooms[table_id].discard(session_id)
                if not self.table_rooms[table_id]:
                    del self.table_rooms[table_id]
            
            self.user_tables.pop(user_id, None)
            
            logger.info(f"User {user_id} left table room {table_id}")

            # Get username for the notification
            username = 'A player'
            try:
                from ..services.user_manager import UserManager
                user_manager = UserManager()
                user = user_manager.get_user_by_id(user_id)
                if user:
                    username = user.username
            except Exception as e:
                logger.warning(f"Could not get username for player_left event: {e}")

            # Notify other participants
            self.broadcast_to_table(table_id, GameEvent.PLAYER_LEFT, {
                'user_id': user_id,
                'username': username,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to leave table room: {e}")
            return False
    
    def broadcast_to_table(self, table_id: str, event: str, data: Dict[str, Any], 
                          exclude_user: Optional[str] = None) -> None:
        """Broadcast an event to all participants in a table.
        
        Args:
            table_id: ID of the table
            event: Event name
            data: Event data
            exclude_user: User ID to exclude from broadcast
        """
        try:
            room_name = f"table_{table_id}"
            
            if exclude_user:
                # Broadcast to all except excluded user
                exclude_session = self.user_sessions.get(exclude_user)
                if exclude_session:
                    # Get all sessions in room except excluded one
                    room_sessions = self.table_rooms.get(table_id, set())
                    target_sessions = room_sessions - {exclude_session}
                    
                    for session_id in target_sessions:
                        self.socketio.emit(event, data, room=session_id)
                else:
                    # Excluded user not found, broadcast to all
                    self.socketio.emit(event, data, room=room_name)
            else:
                # Broadcast to all in room
                self.socketio.emit(event, data, room=room_name)
            
            logger.debug(f"Broadcasted {event} to table {table_id}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast to table {table_id}: {e}")
    
    def send_to_user(self, user_id: str, event: str, data: Dict[str, Any]) -> bool:
        """Send an event to a specific user.
        
        Args:
            user_id: ID of the user
            event: Event name
            data: Event data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_id = self.user_sessions.get(user_id)
            if not session_id:
                logger.warning(f"No session found for user {user_id}")
                return False
            
            self.socketio.emit(event, data, room=session_id)
            logger.debug(f"Sent {event} to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to user {user_id}: {e}")
            return False
    
    def handle_table_disconnect(self, user_id: str, table_id: str) -> None:
        """Handle user disconnection from a table.
        
        Args:
            user_id: ID of the disconnected user
            table_id: ID of the table
        """
        try:
            # Check if user was current player
            from ..services.game_state_manager import GameStateManager
            from ..services.game_orchestrator import game_orchestrator
            
            is_current_player = False
            session = game_orchestrator.get_session(table_id)
            if session:
                current_player = GameStateManager._get_current_player(session)
                is_current_player = (current_player == user_id)
            
            # Handle disconnect through disconnect manager
            from ..services.disconnect_manager import disconnect_manager
            success, message = disconnect_manager.handle_player_disconnect(
                user_id, table_id, is_current_player
            )
            
            if success:
                logger.info(f"Handled disconnect for user {user_id} from table {table_id}")
            else:
                logger.warning(f"Failed to handle disconnect: {message}")
            
        except Exception as e:
            logger.error(f"Failed to handle table disconnect: {e}")
    
    def handle_table_reconnect(self, user_id: str, table_id: str) -> bool:
        """Handle user reconnection to a table.
        
        Args:
            user_id: ID of the reconnecting user
            table_id: ID of the table
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Handle reconnect through disconnect manager
            from ..services.disconnect_manager import disconnect_manager
            
            success, message, reconnect_info = disconnect_manager.handle_player_reconnect(
                user_id, table_id
            )
            
            if success:
                logger.info(f"Handled reconnect for user {user_id} to table {table_id}")
                return True
            else:
                logger.warning(f"Failed to reconnect user {user_id} to table {table_id}: {message}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to handle table reconnect: {e}")
            return False
    
    def broadcast_game_state_update(self, table_id: str) -> None:
        """Broadcast game state update to all table participants.
        
        Args:
            table_id: ID of the table
        """
        try:
            # Get all participants in the table room
            room_sessions = self.table_rooms.get(table_id, set())
            
            for session_id in room_sessions:
                user_id = self.session_users.get(session_id)
                if user_id:
                    # Get player info to determine if spectator
                    player_info = PlayerSessionManager.get_player_info(user_id, table_id)
                    is_spectator = player_info['is_spectator'] if player_info else True
                    
                    # Generate personalized game state
                    game_state = GameStateManager.generate_game_state_view(
                        table_id, user_id, is_spectator
                    )
                    
                    if game_state:
                        self.socketio.emit(
                            GameEvent.GAME_STATE_UPDATE, 
                            game_state.to_dict(), 
                            room=session_id
                        )
            
            logger.debug(f"Broadcasted game state update to table {table_id}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast game state update: {e}")

    def broadcast_hand_complete(self, table_id: str, hand_results: Dict[str, Any]) -> None:
        """Broadcast hand completion with showdown results to all table participants.
        
        Args:
            table_id: ID of the table
            hand_results: Hand results from the game engine
        """
        try:
            hand_complete_data = {
                'table_id': table_id,
                'hand_results': hand_results,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
            self.broadcast_to_table(table_id, GameEvent.HAND_COMPLETE, hand_complete_data)
            logger.info(f"Broadcasted hand completion to table {table_id}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast hand completion: {e}")
    
    def send_notification(self, user_id: str, message: str, notification_type: str = "info") -> bool:
        """Send a notification to a user.
        
        Args:
            user_id: ID of the user
            message: Notification message
            notification_type: Type of notification (info, warning, error, success)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            notification_data = {
                'message': message,
                'type': notification_type,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
            return self.send_to_user(user_id, GameEvent.NOTIFICATION, notification_data)
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def broadcast_game_action_chat(self, table_id: str, message: str, action_type: str = "player_action") -> None:
        """Broadcast a game action message to the table chat.

        Args:
            table_id: ID of the table
            message: The action message to display
            action_type: Type of action (forced_bet, player_action, deal, phase_change, showdown)
        """
        try:
            chat_data = {
                'type': 'game_action',
                'action_type': action_type,
                'message': message,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            self.broadcast_to_table(table_id, GameEvent.CHAT_MESSAGE, chat_data)
        except Exception as e:
            logger.error(f"Failed to broadcast game action chat: {e}")


    def get_connected_users(self) -> List[str]:
        """Get list of connected user IDs.
        
        Returns:
            List of connected user IDs
        """
        return list(self.user_sessions.keys())
    
    def get_table_participants(self, table_id: str) -> List[str]:
        """Get list of user IDs in a table room.
        
        Args:
            table_id: ID of the table
            
        Returns:
            List of user IDs in the table room
        """
        try:
            room_sessions = self.table_rooms.get(table_id, set())
            participants = []
            
            for session_id in room_sessions:
                user_id = self.session_users.get(session_id)
                if user_id:
                    participants.append(user_id)
            
            return participants
            
        except Exception as e:
            logger.error(f"Failed to get table participants: {e}")
            return []
    
    def is_user_connected(self, user_id: str) -> bool:
        """Check if a user is connected.
        
        Args:
            user_id: ID of the user
            
        Returns:
            True if connected, False otherwise
        """
        return user_id in self.user_sessions
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics.

        Returns:
            Dictionary with connection statistics
        """
        return {
            'connected_users': len(self.user_sessions),
            'active_tables': len(self.table_rooms),
            'total_room_participants': sum(len(sessions) for sessions in self.table_rooms.values())
        }

    def _start_hand_when_ready(self, table_id: str, ready_status: Dict[str, Any]) -> None:
        """Start a new hand when all players are ready.

        Args:
            table_id: ID of the table
            ready_status: Ready status info from TableAccessManager
        """
        try:
            from ..services.game_orchestrator import game_orchestrator
            from ..services.table_access_manager import TableAccessManager
            from ..services.user_manager import UserManager

            # Notify that hand is starting
            self.broadcast_to_table(table_id, GameEvent.HAND_STARTING, {
                'table_id': table_id,
                'message': 'All players ready - starting hand...',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })

            # Get or create game session
            session = game_orchestrator.get_session(table_id)
            if not session:
                # Create a new session - returns tuple (success, message, session)
                success, message, session = game_orchestrator.create_session(table_id)
                if not success or not session:
                    logger.error(f"Failed to create game session for table {table_id}: {message}")
                    self.broadcast_to_table(table_id, GameEvent.ERROR, {
                        'message': f'Failed to create game session: {message}'
                    })
                    return

            # Get user info for adding players
            user_manager = UserManager()

            # Ensure all ready players are in the game session
            for player in ready_status['players']:
                if player['is_ready']:
                    user = user_manager.get_user_by_id(player['user_id'])
                    username = user.username if user else 'Unknown'
                    # Get their stack from table access
                    access = TableAccessManager.get_user_access(player['user_id'], table_id)
                    buy_in = access.current_stack if access else 100
                    session.add_player(player['user_id'], username, buy_in)

            # Check if we can start a hand - use session.game directly
            game = session.game
            if game and len(game.table.players) >= 2:
                # Move the dealer button before starting new hand (rotates clockwise)
                game.table.move_button()
                logger.info(f"Moved dealer button to seat {game.table.button_seat}")

                # Start the hand
                game.start_hand()
                logger.info(f"Started new hand at table {table_id}")

                # Broadcast hand start and blinds to chat
                hand_number = session.hands_played + 1
                self.broadcast_game_action_chat(table_id, f"*** HAND #{hand_number} ***", 'phase_change')

                # Get blind information and broadcast to chat
                from generic_poker.game.table import Position
                for player in game.table.players.values():
                    if player.position and player.position.has_position(Position.SMALL_BLIND):
                        sb_amount = game.small_blind
                        self.broadcast_game_action_chat(table_id, f"{player.name} posts small blind ${sb_amount}", 'forced_bet')
                    elif player.position and player.position.has_position(Position.BIG_BLIND):
                        bb_amount = game.big_blind
                        self.broadcast_game_action_chat(table_id, f"{player.name} posts big blind ${bb_amount}", 'forced_bet')

                # Note: "*** HOLE CARDS ***" is announced by the frontend when it receives
                # the game state update with the player's cards (see announceHoleCards in table.js)

                # For online games with auto_progress=False, we need to manually
                # advance through dealing steps until player input is needed
                # Note: _next_step() already calls process_current_step() internally
                while game.current_player is None and game.state != game.state.COMPLETE:
                    game._next_step()
                    if game.current_step >= len(game.rules.gameplay):
                        break
                logger.info(f"Game advanced to current_player: {game.current_player.name if game.current_player else None}")

                # Reset ready status for next hand
                TableAccessManager.reset_all_ready(table_id)

                # Broadcast updated game state
                self.broadcast_game_state_update(table_id)

                # Broadcast that ready status has been reset
                new_ready_status = TableAccessManager.get_ready_status(table_id)
                self.broadcast_to_table(table_id, GameEvent.READY_STATUS_UPDATE, {
                    'table_id': table_id,
                    'ready_status': new_ready_status,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })
            else:
                player_count = len(game.table.players) if game else 0
                logger.warning(f"Cannot start hand at table {table_id} - only {player_count} players")
                self.broadcast_to_table(table_id, GameEvent.ERROR, {
                    'message': 'Cannot start hand - not enough players with chips'
                })

        except Exception as e:
            logger.error(f"Failed to start hand when ready: {e}", exc_info=True)
            self.broadcast_to_table(table_id, GameEvent.ERROR, {
                'message': 'Failed to start hand'
            })

    def broadcast_ready_status(self, table_id: str) -> None:
        """Broadcast current ready status to all table participants.

        Args:
            table_id: ID of the table
        """
        try:
            from ..services.table_access_manager import TableAccessManager
            ready_status = TableAccessManager.get_ready_status(table_id)

            self.broadcast_to_table(table_id, GameEvent.READY_STATUS_UPDATE, {
                'table_id': table_id,
                'ready_status': ready_status,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })

        except Exception as e:
            logger.error(f"Failed to broadcast ready status: {e}")


# Global WebSocket manager instance (will be initialized in app factory)
websocket_manager: Optional[WebSocketManager] = None


def init_websocket_manager(socketio: SocketIO) -> WebSocketManager:
    """Initialize the global WebSocket manager.
    
    Args:
        socketio: Flask-SocketIO instance
        
    Returns:
        WebSocketManager instance
    """
    global websocket_manager
    websocket_manager = WebSocketManager(socketio)
    return websocket_manager


def get_websocket_manager() -> Optional[WebSocketManager]:
    """Get the global WebSocket manager instance.
    
    Returns:
        WebSocketManager instance or None if not initialized
    """
    return websocket_manager