"""Routes for game orchestration and session management."""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from typing import Dict, Any

from ..services.game_orchestrator import game_orchestrator, GameSession
from ..services.table_access_manager import TableAccessManager
from ..models.table_access import TableAccess
from ..database import db
from generic_poker.game.game_state import PlayerAction


game_bp = Blueprint('game', __name__, url_prefix='/api/games')


@game_bp.route('/sessions', methods=['GET'])
@login_required
def get_all_sessions():
    """Get information about all active game sessions.
    
    Returns:
        JSON response with session list
    """
    try:
        sessions = game_orchestrator.get_all_sessions()
        session_info = [session.get_session_info() for session in sessions]
        
        return jsonify({
            'success': True,
            'sessions': session_info,
            'count': len(session_info)
        })
    except Exception as e:
        current_app.logger.error(f"Failed to get sessions: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get sessions'
        }), 500


@game_bp.route('/sessions/<table_id>', methods=['POST'])
@login_required
def create_session(table_id: str):
    """Create a new game session for a table.
    
    Args:
        table_id: ID of the table to create session for
        
    Returns:
        JSON response with session creation result
    """
    try:
        success, message, session = game_orchestrator.create_session(table_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'session': session.get_session_info()
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Failed to create session: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to create session'
        }), 500


@game_bp.route('/sessions/<table_id>', methods=['GET'])
@login_required
def get_session(table_id: str):
    """Get information about a specific game session.
    
    Args:
        table_id: ID of the table
        
    Returns:
        JSON response with session information
    """
    try:
        session = game_orchestrator.get_session(table_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
        
        return jsonify({
            'success': True,
            'session': session.get_session_info()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get session: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get session'
        }), 500


@game_bp.route('/sessions/<table_id>', methods=['DELETE'])
@login_required
def remove_session(table_id: str):
    """Remove a game session.
    
    Args:
        table_id: ID of the table
        
    Returns:
        JSON response with removal result
    """
    try:
        success = game_orchestrator.remove_session(table_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Session removed successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to remove session: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to remove session'
        }), 500


@game_bp.route('/sessions/<table_id>/join', methods=['POST'])
@login_required
def join_table_and_game(table_id: str):
    """Join a table and its game session.
    
    Args:
        table_id: ID of the table
        
    Expected JSON payload:
    {
        "buy_in_amount": 1000,
        "as_spectator": false,
        "invite_code": "optional_invite_code",
        "password": "optional_password"
    }
    
    Returns:
        JSON response with join result
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        data = request.get_json() or {}
        buy_in_amount = data.get('buy_in_amount', 0)
        as_spectator = data.get('as_spectator', False)
        invite_code = data.get('invite_code')
        password = data.get('password')
        
        # Validate buy-in if not spectator
        if not as_spectator:
            is_valid, validation_message = PlayerSessionManager.validate_buy_in(
                current_user.id, table_id, buy_in_amount
            )
            if not is_valid:
                return jsonify({
                    'success': False,
                    'error': validation_message
                }), 400
        
        # Join table and game
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            current_user.id, table_id, buy_in_amount, invite_code, password, as_spectator
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'data': session_info
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to join table and game: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to join table and game'
        }), 500


@game_bp.route('/sessions/<table_id>/leave', methods=['POST'])
@login_required
def leave_table_and_game(table_id: str):
    """Leave a table and its game session.
    
    Args:
        table_id: ID of the table
        
    Expected JSON payload:
    {
        "reason": "optional_reason"
    }
    
    Returns:
        JSON response with leave result
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Player left')
        
        # Leave table and game
        success, message, cashout_info = PlayerSessionManager.leave_table_and_game(
            current_user.id, table_id, reason
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        response_data = {
            'success': True,
            'message': message
        }
        
        if cashout_info:
            response_data['cashout'] = cashout_info
        
        return jsonify(response_data)
        
    except Exception as e:
        current_app.logger.error(f"Failed to leave table and game: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to leave table and game'
        }), 500


@game_bp.route('/sessions/<table_id>/action', methods=['POST'])
@login_required
def process_player_action(table_id: str):
    """Process a player action in the game.
    
    Args:
        table_id: ID of the table
        
    Expected JSON payload:
    {
        "action": "CALL",
        "amount": 100
    }
    
    Returns:
        JSON response with action result
    """
    try:
        data = request.get_json()
        if not data or 'action' not in data:
            return jsonify({
                'success': False,
                'error': 'Action required'
            }), 400
        
        session = game_orchestrator.get_session(table_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'Game session not found'
            }), 404
        
        # Parse action
        try:
            action = PlayerAction(data['action'])
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid action: {data["action"]}'
            }), 400
        
        amount = data.get('amount', 0)
        
        # Process the action
        success, message, result = session.process_player_action(
            current_user.id, action, amount
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        response_data = {
            'success': True,
            'message': message,
            'session': session.get_session_info()
        }
        
        # Include action result details if available
        if result:
            response_data['action_result'] = {
                'success': result.success,
                'message': result.message,
                'game_state': session.game.state.value
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        current_app.logger.error(f"Failed to process player action: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to process action'
        }), 500


@game_bp.route('/sessions/<table_id>/disconnect', methods=['POST'])
@login_required
def handle_disconnect(table_id: str):
    """Handle player disconnection.
    
    Args:
        table_id: ID of the table
        
    Returns:
        JSON response with disconnect handling result
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        success, message = PlayerSessionManager.handle_player_disconnect(
            current_user.id, table_id
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to handle disconnect: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to handle disconnect'
        }), 500


@game_bp.route('/sessions/<table_id>/reconnect', methods=['POST'])
@login_required
def handle_reconnect(table_id: str):
    """Handle player reconnection.
    
    Args:
        table_id: ID of the table
        
    Returns:
        JSON response with reconnect handling result
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        success, message, session_info = PlayerSessionManager.handle_player_reconnect(
            current_user.id, table_id
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'data': session_info
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to handle reconnect: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to handle reconnect'
        }), 500


@game_bp.route('/stats', methods=['GET'])
@login_required
def get_orchestrator_stats():
    """Get orchestrator statistics.
    
    Returns:
        JSON response with orchestrator stats
    """
    try:
        stats = game_orchestrator.get_orchestrator_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get orchestrator stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get stats'
        }), 500


@game_bp.route('/sessions/<table_id>/info', methods=['GET'])
@login_required
def get_table_session_info(table_id: str):
    """Get comprehensive information about a table and its game session.
    
    Args:
        table_id: ID of the table
        
    Returns:
        JSON response with table session information
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        session_info = PlayerSessionManager.get_table_session_info(table_id)
        
        if not session_info:
            return jsonify({
                'success': False,
                'error': 'Table not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': session_info
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get table session info: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get table session info'
        }), 500


@game_bp.route('/sessions/<table_id>/players/<user_id>', methods=['GET'])
@login_required
def get_player_info(table_id: str, user_id: str):
    """Get information about a specific player at a table.
    
    Args:
        table_id: ID of the table
        user_id: ID of the user
        
    Returns:
        JSON response with player information
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        # Only allow users to get their own info or if they're at the same table
        if user_id != current_user.id:
            # Check if current user is at the same table
            current_player_info = PlayerSessionManager.get_player_info(current_user.id, table_id)
            if not current_player_info:
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
        
        player_info = PlayerSessionManager.get_player_info(user_id, table_id)
        
        if not player_info:
            return jsonify({
                'success': False,
                'error': 'Player not found at this table'
            }), 404
        
        return jsonify({
            'success': True,
            'data': player_info
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get player info: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get player info'
        }), 500


@game_bp.route('/sessions/<table_id>/validate-buyin', methods=['POST'])
@login_required
def validate_buy_in(table_id: str):
    """Validate a buy-in amount for the current user.
    
    Args:
        table_id: ID of the table
        
    Expected JSON payload:
    {
        "buy_in_amount": 1000
    }
    
    Returns:
        JSON response with validation result
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        data = request.get_json()
        if not data or 'buy_in_amount' not in data:
            return jsonify({
                'success': False,
                'error': 'Buy-in amount required'
            }), 400
        
        buy_in_amount = data['buy_in_amount']
        
        is_valid, message = PlayerSessionManager.validate_buy_in(
            current_user.id, table_id, buy_in_amount
        )
        
        return jsonify({
            'success': is_valid,
            'message': message,
            'valid': is_valid
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to validate buy-in: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to validate buy-in'
        }), 500


@game_bp.route('/sessions/<table_id>/state', methods=['GET'])
@login_required
def get_game_state(table_id: str):
    """Get the current game state for a player/spectator.
    
    Args:
        table_id: ID of the table
        
    Returns:
        JSON response with game state view
    """
    try:
        from ..services.game_state_manager import GameStateManager
        from ..services.player_session_manager import PlayerSessionManager
        
        # Check if user has access to this table
        player_info = PlayerSessionManager.get_player_info(current_user.id, table_id)
        is_spectator = player_info['is_spectator'] if player_info else True
        
        # Generate game state view
        game_state = GameStateManager.generate_game_state_view(
            table_id, current_user.id, is_spectator
        )
        
        if not game_state:
            return jsonify({
                'success': False,
                'error': 'Game state not available'
            }), 404
        
        return jsonify({
            'success': True,
            'game_state': game_state.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get game state: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get game state'
        }), 500


@game_bp.route('/sessions/<table_id>/state/updates', methods=['GET'])
@login_required
def get_state_updates(table_id: str):
    """Get game state updates since a specific timestamp.
    
    Args:
        table_id: ID of the table
        
    Query parameters:
        since: ISO timestamp to get updates since
        
    Returns:
        JSON response with state updates
    """
    try:
        from ..services.game_state_manager import GameStateManager
        from datetime import datetime
        
        # Get timestamp parameter
        since_param = request.args.get('since')
        since_timestamp = None
        if since_param:
            try:
                since_timestamp = datetime.fromisoformat(since_param.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid timestamp format'
                }), 400
        
        # For now, just return the current game state
        # In a full implementation, this would track and return actual updates
        game_state = GameStateManager.generate_game_state_view(
            table_id, current_user.id
        )
        
        if not game_state:
            return jsonify({
                'success': False,
                'error': 'Game state not available'
            }), 404
        
        # Return as an update
        update = GameStateManager.create_game_state_update(
            table_id, "full_state", game_state.to_dict()
        )
        
        return jsonify({
            'success': True,
            'updates': [update.to_dict()],
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get state updates: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get state updates'
        }), 500


@game_bp.route('/sessions/<table_id>/hand-result', methods=['GET'])
@login_required
def get_hand_result(table_id: str):
    """Get the result of the last completed hand.
    
    Args:
        table_id: ID of the table
        
    Returns:
        JSON response with hand result
    """
    try:
        from ..services.game_state_manager import GameStateManager
        
        # Get game session
        session = game_orchestrator.get_session(table_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'Game session not found'
            }), 404
        
        # Process hand completion (this would typically be called when a hand ends)
        hand_result = GameStateManager.process_hand_completion(session)
        
        if not hand_result:
            return jsonify({
                'success': False,
                'error': 'No hand result available'
            }), 404
        
        return jsonify({
            'success': True,
            'hand_result': hand_result.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get hand result: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get hand result'
        }), 500


@game_bp.route('/cleanup', methods=['POST'])
@login_required
def cleanup_inactive_sessions():
    """Clean up inactive game sessions (admin function).
    
    Returns:
        JSON response with cleanup results
    """
    try:
        from ..services.player_session_manager import PlayerSessionManager
        
        timeout_minutes = request.json.get('timeout_minutes', 30) if request.json else 30
        cleaned_count = PlayerSessionManager.cleanup_inactive_sessions(timeout_minutes)
        
        return jsonify({
            'success': True,
            'cleaned_sessions': cleaned_count,
            'message': f'Cleaned up {cleaned_count} inactive sessions'
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to cleanup sessions: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to cleanup sessions'
        }), 500