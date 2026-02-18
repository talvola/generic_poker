"""WebSocket routes for real-time communication."""

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from ..services.websocket_manager import get_websocket_manager

websocket_bp = Blueprint("websocket", __name__, url_prefix="/api/websocket")


@websocket_bp.route("/stats", methods=["GET"])
@login_required
def get_connection_stats():
    """Get WebSocket connection statistics.

    Returns:
        JSON response with connection statistics
    """
    try:
        ws_manager = get_websocket_manager()
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket manager not initialized"}), 500

        stats = ws_manager.get_connection_stats()

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        current_app.logger.error(f"Failed to get connection stats: {e}")
        return jsonify({"success": False, "error": "Failed to get connection stats"}), 500


@websocket_bp.route("/tables/<table_id>/participants", methods=["GET"])
@login_required
def get_table_participants(table_id: str):
    """Get participants in a table WebSocket room.

    Args:
        table_id: ID of the table

    Returns:
        JSON response with participant list
    """
    try:
        ws_manager = get_websocket_manager()
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket manager not initialized"}), 500

        participants = ws_manager.get_table_participants(table_id)

        return jsonify({"success": True, "participants": participants, "count": len(participants)})

    except Exception as e:
        current_app.logger.error(f"Failed to get table participants: {e}")
        return jsonify({"success": False, "error": "Failed to get table participants"}), 500


@websocket_bp.route("/users/<user_id>/status", methods=["GET"])
@login_required
def get_user_connection_status(user_id: str):
    """Get connection status for a user.

    Args:
        user_id: ID of the user

    Returns:
        JSON response with connection status
    """
    try:
        ws_manager = get_websocket_manager()
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket manager not initialized"}), 500

        is_connected = ws_manager.is_user_connected(user_id)

        return jsonify({"success": True, "user_id": user_id, "connected": is_connected})

    except Exception as e:
        current_app.logger.error(f"Failed to get user connection status: {e}")
        return jsonify({"success": False, "error": "Failed to get connection status"}), 500


@websocket_bp.route("/notify", methods=["POST"])
@login_required
def send_notification():
    """Send a notification to a user.

    Expected JSON payload:
    {
        "user_id": "target_user_id",
        "message": "Notification message",
        "type": "info"
    }

    Returns:
        JSON response with send result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON payload required"}), 400

        user_id = data.get("user_id")
        message = data.get("message")
        notification_type = data.get("type", "info")

        if not user_id or not message:
            return jsonify({"success": False, "error": "user_id and message required"}), 400

        ws_manager = get_websocket_manager()
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket manager not initialized"}), 500

        success = ws_manager.send_notification(user_id, message, notification_type)

        return jsonify(
            {"success": success, "message": "Notification sent" if success else "Failed to send notification"}
        )

    except Exception as e:
        current_app.logger.error(f"Failed to send notification: {e}")
        return jsonify({"success": False, "error": "Failed to send notification"}), 500


@websocket_bp.route("/disconnects", methods=["GET"])
@login_required
def get_disconnect_stats():
    """Get disconnect manager statistics.

    Returns:
        JSON response with disconnect statistics
    """
    try:
        from ..services.disconnect_manager import disconnect_manager

        stats = disconnect_manager.get_disconnect_stats()

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        current_app.logger.error(f"Failed to get disconnect stats: {e}")
        return jsonify({"success": False, "error": "Failed to get disconnect stats"}), 500


@websocket_bp.route("/disconnects/users/<user_id>", methods=["GET"])
@login_required
def get_user_disconnect_info(user_id: str):
    """Get disconnect information for a specific user.

    Args:
        user_id: ID of the user

    Returns:
        JSON response with disconnect information
    """
    try:
        from ..services.disconnect_manager import disconnect_manager

        disconnect_info = disconnect_manager.get_disconnected_player_info(user_id)

        if disconnect_info:
            return jsonify({"success": True, "disconnect_info": disconnect_info})
        else:
            return jsonify({"success": False, "error": "User is not disconnected"}), 404

    except Exception as e:
        current_app.logger.error(f"Failed to get user disconnect info: {e}")
        return jsonify({"success": False, "error": "Failed to get disconnect info"}), 500


@websocket_bp.route("/disconnects/tables/<table_id>", methods=["GET"])
@login_required
def get_table_disconnects(table_id: str):
    """Get all disconnected players for a table.

    Args:
        table_id: ID of the table

    Returns:
        JSON response with table disconnect information
    """
    try:
        from ..services.disconnect_manager import disconnect_manager

        disconnects = disconnect_manager.get_table_disconnects(table_id)

        return jsonify({"success": True, "disconnects": disconnects, "count": len(disconnects)})

    except Exception as e:
        current_app.logger.error(f"Failed to get table disconnects: {e}")
        return jsonify({"success": False, "error": "Failed to get table disconnects"}), 500


@websocket_bp.route("/disconnects/users/<user_id>/reconnect", methods=["POST"])
@login_required
def force_reconnect_user(user_id: str):
    """Force reconnect a disconnected user (admin function).

    Args:
        user_id: ID of the user

    Expected JSON payload:
    {
        "table_id": "table_id"
    }

    Returns:
        JSON response with reconnect result
    """
    try:
        data = request.get_json()
        if not data or "table_id" not in data:
            return jsonify({"success": False, "error": "table_id required"}), 400

        table_id = data["table_id"]

        from ..services.disconnect_manager import disconnect_manager

        success, message = disconnect_manager.force_reconnect_player(user_id, table_id)

        return jsonify({"success": success, "message": message})

    except Exception as e:
        current_app.logger.error(f"Failed to force reconnect user: {e}")
        return jsonify({"success": False, "error": "Failed to force reconnect"}), 500


@websocket_bp.route("/disconnects/users/<user_id>/remove", methods=["POST"])
@login_required
def force_remove_user(user_id: str):
    """Force remove a disconnected user (admin function).

    Args:
        user_id: ID of the user

    Returns:
        JSON response with removal result
    """
    try:
        from ..services.disconnect_manager import disconnect_manager

        success, message = disconnect_manager.force_remove_player(user_id)

        return jsonify({"success": success, "message": message})

    except Exception as e:
        current_app.logger.error(f"Failed to force remove user: {e}")
        return jsonify({"success": False, "error": "Failed to force remove"}), 500


@websocket_bp.route("/disconnects/cleanup", methods=["POST"])
@login_required
def cleanup_expired_disconnects():
    """Clean up expired disconnections (admin function).

    Returns:
        JSON response with cleanup results
    """
    try:
        from ..services.disconnect_manager import disconnect_manager

        cleaned_count = disconnect_manager.cleanup_expired_disconnects()

        return jsonify(
            {
                "success": True,
                "cleaned_count": cleaned_count,
                "message": f"Cleaned up {cleaned_count} expired disconnects",
            }
        )

    except Exception as e:
        current_app.logger.error(f"Failed to cleanup expired disconnects: {e}")
        return jsonify({"success": False, "error": "Failed to cleanup expired disconnects"}), 500
