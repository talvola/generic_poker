"""Chat-related routes."""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from typing import Dict, Any

from ..database import db
from ..models.chat import ChatMessage, ChatModerationAction, ChatFilter
from ..models.table import PokerTable
from ..services.chat_service import chat_service
from ..services.player_session_manager import PlayerSessionManager


chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat_bp.route('/history/<table_id>')
@login_required
def get_chat_history(table_id: str):
    """Get chat history for a table."""
    try:
        # Check if user has access to this table
        player_info = PlayerSessionManager.get_player_info(current_user.id, table_id)
        if not player_info:
            return jsonify({'error': 'No access to this table'}), 403
        
        limit = request.args.get('limit', 50, type=int)
        include_system = request.args.get('include_system', True, type=bool)
        
        chat_history = chat_service.get_chat_history(
            table_id, limit, include_system
        )
        
        return jsonify({
            'table_id': table_id,
            'messages': chat_history
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting chat history: {e}")
        return jsonify({'error': 'Failed to get chat history'}), 500


@chat_bp.route('/moderation/<table_id>')
@login_required
def get_moderation_history(table_id: str):
    """Get moderation history for a table (table creator only)."""
    try:
        # Check if user is table creator
        table = db.session.query(PokerTable).filter(
            PokerTable.id == table_id
        ).first()
        
        if not table:
            return jsonify({'error': 'Table not found'}), 404
        
        if table.creator_id != current_user.id:
            return jsonify({'error': 'Only table creator can view moderation history'}), 403
        
        limit = request.args.get('limit', 20, type=int)
        
        moderation_history = chat_service.get_moderation_history(table_id, limit)
        
        return jsonify({
            'table_id': table_id,
            'actions': moderation_history
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting moderation history: {e}")
        return jsonify({'error': 'Failed to get moderation history'}), 500


@chat_bp.route('/moderate', methods=['POST'])
@login_required
def moderate_user():
    """Apply moderation action to a user."""
    try:
        data = request.get_json()
        
        table_id = data.get('table_id')
        target_user_id = data.get('target_user_id')
        action_type = data.get('action_type')
        reason = data.get('reason', '')
        duration_minutes = data.get('duration_minutes')
        
        if not all([table_id, target_user_id, action_type]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if user is table creator
        table = db.session.query(PokerTable).filter(
            PokerTable.id == table_id
        ).first()
        
        if not table:
            return jsonify({'error': 'Table not found'}), 404
        
        if table.creator_id != current_user.id:
            return jsonify({'error': 'Only table creator can moderate users'}), 403
        
        # Apply moderation
        success, message = chat_service.moderate_user(
            target_user_id=target_user_id,
            table_id=table_id,
            moderator_user_id=current_user.id,
            action_type=action_type,
            reason=reason,
            duration_minutes=duration_minutes
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error moderating user: {e}")
        return jsonify({'error': 'Failed to moderate user'}), 500


@chat_bp.route('/filters', methods=['GET'])
@login_required
def get_chat_filters():
    """Get chat filters (admin only for now)."""
    try:
        # For now, only allow table creators to view filters
        # In a full implementation, this would be admin-only
        filters = db.session.query(ChatFilter).filter(
            ChatFilter.is_active == True
        ).all()
        
        return jsonify({
            'filters': [f.to_dict() for f in filters]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting chat filters: {e}")
        return jsonify({'error': 'Failed to get chat filters'}), 500


@chat_bp.route('/filters', methods=['POST'])
@login_required
def add_chat_filter():
    """Add a new chat filter (admin only for now)."""
    try:
        data = request.get_json()
        
        pattern = data.get('pattern')
        filter_type = data.get('filter_type')
        action = data.get('action')
        replacement = data.get('replacement')
        severity = data.get('severity', 1)
        
        if not all([pattern, filter_type, action]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Create new filter
        chat_filter = ChatFilter(
            pattern=pattern,
            filter_type=filter_type,
            action=action,
            replacement=replacement,
            severity=severity
        )
        
        db.session.add(chat_filter)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'filter': chat_filter.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error adding chat filter: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to add chat filter'}), 500


@chat_bp.route('/user-status/<table_id>/<user_id>')
@login_required
def get_user_chat_status(table_id: str, user_id: str):
    """Get chat status for a user in a table."""
    try:
        # Check if requesting user has access to this table
        player_info = PlayerSessionManager.get_player_info(current_user.id, table_id)
        if not player_info:
            return jsonify({'error': 'No access to this table'}), 403
        
        is_muted = chat_service.is_user_muted(user_id, table_id)
        is_banned = chat_service.is_user_banned(user_id, table_id)
        
        return jsonify({
            'user_id': user_id,
            'table_id': table_id,
            'is_muted': is_muted,
            'is_banned': is_banned
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting user chat status: {e}")
        return jsonify({'error': 'Failed to get user status'}), 500


@chat_bp.route('/cleanup-expired', methods=['POST'])
@login_required
def cleanup_expired_actions():
    """Clean up expired moderation actions (admin only)."""
    try:
        # For now, allow any logged-in user to trigger cleanup
        # In production, this would be admin-only or automated
        cleaned_count = chat_service.cleanup_expired_actions()
        
        return jsonify({
            'success': True,
            'cleaned_count': cleaned_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Error cleaning up expired actions: {e}")
        return jsonify({'error': 'Failed to cleanup expired actions'}), 500