"""Routes for table management."""

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from generic_poker.game.betting import BettingStructure

from ..database import db
from ..models.table_access import TableAccess
from ..models.table_config import TableConfig
from ..services.table_access_manager import TableAccessManager
from ..services.table_manager import TableManager, TableValidationError

table_bp = Blueprint("table", __name__, url_prefix="/api/tables")


@table_bp.route("/variants", methods=["GET"])
@login_required
def get_variants():
    """Get all available poker variants.

    Returns:
        JSON response with list of available variants
    """
    try:
        variants = TableManager.get_available_variants()
        return jsonify({"success": True, "variants": variants, "count": len(variants)})
    except Exception as e:
        current_app.logger.error(f"Failed to get variants: {e}")
        return jsonify({"success": False, "error": "Failed to load poker variants"}), 500


@table_bp.route("/betting-structures", methods=["GET"])
@login_required
def get_betting_structures():
    """Get all supported betting structures.

    Returns:
        JSON response with list of betting structures
    """
    structures = [
        {"value": BettingStructure.LIMIT.value, "name": "Limit", "description": "Fixed betting limits"},
        {
            "value": BettingStructure.NO_LIMIT.value,
            "name": "No-Limit",
            "description": "Players can bet any amount up to their stack",
        },
        {
            "value": BettingStructure.POT_LIMIT.value,
            "name": "Pot-Limit",
            "description": "Players can bet up to the size of the pot",
        },
    ]

    return jsonify({"success": True, "betting_structures": structures})


@table_bp.route("/suggested-stakes/<betting_structure>", methods=["GET"])
@login_required
def get_suggested_stakes(betting_structure: str):
    """Get suggested stakes for a betting structure.

    Args:
        betting_structure: Betting structure to get suggestions for

    Returns:
        JSON response with suggested stakes
    """
    try:
        # Convert string to enum
        structure_enum = BettingStructure(betting_structure)
        suggestions = TableManager.get_suggested_stakes(structure_enum)

        return jsonify({"success": True, "suggestions": suggestions})
    except ValueError:
        return jsonify({"success": False, "error": f"Invalid betting structure: {betting_structure}"}), 400
    except Exception as e:
        current_app.logger.error(f"Failed to get suggested stakes: {e}")
        return jsonify({"success": False, "error": "Failed to get suggested stakes"}), 500


@table_bp.route("/", methods=["POST"])
@login_required
def create_table():
    """Create a new poker table.

    Expected JSON payload:
    {
        "name": "Table name",
        "variant": "hold_em",
        "betting_structure": "No-Limit",
        "stakes": {"small_blind": 1, "big_blind": 2},
        "max_players": 6,
        "is_private": false,
        "password": "optional",
        "allow_bots": false
    }

    Returns:
        JSON response with created table information
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Validate required fields
        required_fields = ["name", "variant", "betting_structure", "stakes", "max_players"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"success": False, "error": f"Missing required fields: {missing_fields}"}), 400

        # Convert betting structure string to enum
        try:
            betting_structure = BettingStructure(data["betting_structure"])
        except ValueError:
            return jsonify({"success": False, "error": f"Invalid betting structure: {data['betting_structure']}"}), 400

        # Create table configuration
        config = TableConfig(
            name=data["name"],
            variant=data["variant"],
            betting_structure=betting_structure,
            stakes=data["stakes"],
            max_players=data["max_players"],
            is_private=data.get("is_private", False),
            password=data.get("password"),
            allow_bots=data.get("allow_bots", False),
        )

        # Create table
        table = TableManager.create_table(current_user.id, config)

        return jsonify(
            {"success": True, "table": table.to_dict(), "message": f'Table "{table.name}" created successfully'}
        ), 201

    except TableValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Failed to create table: {e}")
        return jsonify({"success": False, "error": "Failed to create table"}), 500


@table_bp.route("/", methods=["GET"])
@login_required
def get_tables():
    """Get list of public tables.

    Returns:
        JSON response with list of public tables
    """
    try:
        tables = TableManager.get_public_tables()
        return jsonify({"success": True, "tables": tables, "count": len(tables)})
    except Exception as e:
        current_app.logger.error(f"Failed to get tables: {e}")
        return jsonify({"success": False, "error": "Failed to load tables"}), 500


@table_bp.route("/<table_id>", methods=["GET"])
@login_required
def get_table(table_id: str):
    """Get specific table information.

    Args:
        table_id: ID of table to retrieve

    Returns:
        JSON response with table information
    """
    try:
        table = TableManager.get_table_by_id(table_id)
        if not table:
            return jsonify({"success": False, "error": "Table not found"}), 404

        # Check if user can view private table
        if table.is_private and table.creator_id != current_user.id:
            return jsonify({"success": False, "error": "Access denied to private table"}), 403

        return jsonify({"success": True, "table": table.to_dict()})
    except Exception as e:
        current_app.logger.error(f"Failed to get table {table_id}: {e}")
        return jsonify({"success": False, "error": "Failed to load table"}), 500


@table_bp.route("/invite/<invite_code>", methods=["GET"])
@login_required
def get_table_by_invite(invite_code: str):
    """Get table information by invite code.

    Args:
        invite_code: Invite code for private table

    Returns:
        JSON response with table information
    """
    try:
        table = TableManager.get_table_by_invite_code(invite_code)
        if not table:
            return jsonify({"success": False, "error": "Invalid invite code"}), 404

        return jsonify({"success": True, "table": table.to_dict()})
    except Exception as e:
        current_app.logger.error(f"Failed to get table by invite {invite_code}: {e}")
        return jsonify({"success": False, "error": "Failed to load table"}), 500


@table_bp.route("/<table_id>/activity", methods=["PUT"])
@login_required
def update_table_activity(table_id: str):
    """Update table activity timestamp.

    Args:
        table_id: ID of table to update

    Returns:
        JSON response confirming update
    """
    try:
        success = TableManager.update_table_activity(table_id)
        if not success:
            return jsonify({"success": False, "error": "Table not found"}), 404

        return jsonify({"success": True, "message": "Table activity updated"})
    except Exception as e:
        current_app.logger.error(f"Failed to update table activity: {e}")
        return jsonify({"success": False, "error": "Failed to update table activity"}), 500


@table_bp.route("/<table_id>/join", methods=["POST"])
@login_required
def join_table(table_id: str):
    """Join a table as player or spectator.

    Args:
        table_id: ID of table to join

    Expected JSON payload:
    {
        "buy_in_amount": 1000,
        "invite_code": "ABC123",
        "password": "secret",
        "as_spectator": false
    }

    Returns:
        JSON response with join result
    """
    try:
        data = request.get_json() or {}

        buy_in_amount = data.get("buy_in_amount", 0)
        invite_code = data.get("invite_code")
        password = data.get("password")
        as_spectator = data.get("as_spectator", False)

        # Validate buy-in amount for players
        if not as_spectator and buy_in_amount <= 0:
            return jsonify({"success": False, "error": "Buy-in amount must be positive"}), 400

        success, error_msg, access_record = TableAccessManager.join_table(
            user_id=current_user.id,
            table_id=table_id,
            buy_in_amount=buy_in_amount,
            invite_code=invite_code,
            password=password,
            as_spectator=as_spectator,
        )

        if not success:
            return jsonify({"success": False, "error": error_msg}), 400

        return jsonify(
            {
                "success": True,
                "message": error_msg,  # Success message
                "access_record": access_record.to_dict() if access_record else None,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Failed to join table: {e}")
        return jsonify({"success": False, "error": "Failed to join table"}), 500


@table_bp.route("/<table_id>/leave", methods=["POST"])
@login_required
def leave_table(table_id: str):
    """Leave a table.

    Args:
        table_id: ID of table to leave

    Returns:
        JSON response with leave result
    """
    try:
        success, error_msg = TableAccessManager.leave_table(user_id=current_user.id, table_id=table_id)

        if not success:
            return jsonify({"success": False, "error": error_msg}), 400

        return jsonify({"success": True, "message": error_msg})

    except Exception as e:
        current_app.logger.error(f"Failed to leave table: {e}")
        return jsonify({"success": False, "error": "Failed to leave table"}), 500


@table_bp.route("/<table_id>/players", methods=["GET"])
@login_required
def get_table_players(table_id: str):
    """Get list of players at a table.

    Args:
        table_id: ID of table to get players for

    Returns:
        JSON response with player list
    """
    try:
        # Check if user has access to view this table
        table = TableManager.get_table_by_id(table_id)
        if not table:
            return jsonify({"success": False, "error": "Table not found"}), 404

        # For private tables, only allow access to players/creator
        if table.is_private:
            user_access = (
                db.session.query(TableAccess)
                .filter(
                    TableAccess.table_id == table_id,
                    TableAccess.user_id == current_user.id,
                    TableAccess.is_active == True,
                )
                .first()
            )

            if not user_access and table.creator_id != current_user.id:
                return jsonify({"success": False, "error": "Access denied"}), 403

        players = TableAccessManager.get_table_players(table_id)

        return jsonify({"success": True, "players": players, "count": len(players)})

    except Exception as e:
        current_app.logger.error(f"Failed to get table players: {e}")
        return jsonify({"success": False, "error": "Failed to get table players"}), 500


@table_bp.route("/<table_id>/visibility", methods=["PUT"])
@login_required
def update_table_visibility(table_id: str):
    """Update table visibility (public/private).

    Args:
        table_id: ID of table to update

    Expected JSON payload:
    {
        "is_private": true
    }

    Returns:
        JSON response with update result
    """
    try:
        data = request.get_json()
        if not data or "is_private" not in data:
            return jsonify({"success": False, "error": "is_private field required"}), 400

        is_private = data["is_private"]

        success, error_msg = TableManager.update_table_visibility(
            table_id=table_id, user_id=current_user.id, is_private=is_private
        )

        if not success:
            return jsonify({"success": False, "error": error_msg}), 400

        # Get updated table info
        table = TableManager.get_table_by_id(table_id)

        return jsonify(
            {
                "success": True,
                "message": f"Table visibility updated to {'private' if is_private else 'public'}",
                "table": table.to_dict() if table else None,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Failed to update table visibility: {e}")
        return jsonify({"success": False, "error": "Failed to update table visibility"}), 500


@table_bp.route("/<table_id>/invite-code", methods=["POST"])
@login_required
def regenerate_invite_code(table_id: str):
    """Regenerate invite code for a private table.

    Args:
        table_id: ID of table to update

    Returns:
        JSON response with new invite code
    """
    try:
        success, error_msg, new_code = TableManager.regenerate_invite_code(table_id=table_id, user_id=current_user.id)

        if not success:
            return jsonify({"success": False, "error": error_msg}), 400

        return jsonify({"success": True, "message": "Invite code regenerated", "invite_code": new_code})

    except Exception as e:
        current_app.logger.error(f"Failed to regenerate invite code: {e}")
        return jsonify({"success": False, "error": "Failed to regenerate invite code"}), 500


@table_bp.route("/<table_id>/settings", methods=["PUT"])
@login_required
def update_table_settings(table_id: str):
    """Update table settings.

    Args:
        table_id: ID of table to update

    Expected JSON payload:
    {
        "name": "New Table Name",
        "is_private": true,
        "allow_bots": false
    }

    Returns:
        JSON response with update result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No settings provided"}), 400

        success, message = TableManager.update_table_settings(table_id=table_id, user_id=current_user.id, settings=data)

        if not success:
            return jsonify({"success": False, "error": message}), 400

        # Get updated table info
        table = TableManager.get_table_by_id(table_id)

        return jsonify(
            {"success": True, "message": message, "table": table.to_dict(include_sensitive=True) if table else None}
        )

    except Exception as e:
        current_app.logger.error(f"Failed to update table settings: {e}")
        return jsonify({"success": False, "error": "Failed to update table settings"}), 500


@table_bp.route("/<table_id>/kick", methods=["POST"])
@login_required
def kick_player(table_id: str):
    """Kick a player from the table.

    Args:
        table_id: ID of table

    Expected JSON payload:
    {
        "player_id": "user_id_to_kick",
        "reason": "Optional reason"
    }

    Returns:
        JSON response with kick result
    """
    try:
        data = request.get_json()
        if not data or "player_id" not in data:
            return jsonify({"success": False, "error": "Player ID required"}), 400

        player_id = data["player_id"]
        reason = data.get("reason", "")

        success, message = TableManager.kick_player(
            table_id=table_id, creator_id=current_user.id, player_id=player_id, reason=reason
        )

        if not success:
            return jsonify({"success": False, "error": message}), 400

        return jsonify({"success": True, "message": message})

    except Exception as e:
        current_app.logger.error(f"Failed to kick player: {e}")
        return jsonify({"success": False, "error": "Failed to kick player"}), 500


@table_bp.route("/<table_id>/transfer-host", methods=["POST"])
@login_required
def transfer_host_privileges(table_id: str):
    """Transfer host privileges to another player.

    Args:
        table_id: ID of table

    Expected JSON payload:
    {
        "new_host_id": "user_id_of_new_host"
    }

    Returns:
        JSON response with transfer result
    """
    try:
        data = request.get_json()
        if not data or "new_host_id" not in data:
            return jsonify({"success": False, "error": "New host ID required"}), 400

        new_host_id = data["new_host_id"]

        success, message = TableManager.transfer_host_privileges(
            table_id=table_id, current_creator_id=current_user.id, new_creator_id=new_host_id
        )

        if not success:
            return jsonify({"success": False, "error": message}), 400

        return jsonify({"success": True, "message": message})

    except Exception as e:
        current_app.logger.error(f"Failed to transfer host privileges: {e}")
        return jsonify({"success": False, "error": "Failed to transfer host privileges"}), 500


@table_bp.route("/<table_id>/close", methods=["POST"])
@login_required
def close_table(table_id: str):
    """Manually close a table.

    Args:
        table_id: ID of table to close

    Expected JSON payload:
    {
        "reason": "Optional reason for closure"
    }

    Returns:
        JSON response with closure result
    """
    try:
        data = request.get_json() or {}
        reason = data.get("reason", "Manual closure by host")

        success, message = TableManager.close_table(table_id=table_id, creator_id=current_user.id, reason=reason)

        if not success:
            return jsonify({"success": False, "error": message}), 400

        return jsonify({"success": True, "message": message})

    except Exception as e:
        current_app.logger.error(f"Failed to close table: {e}")
        return jsonify({"success": False, "error": "Failed to close table"}), 500


@table_bp.route("/cleanup", methods=["POST"])
@login_required
def cleanup_inactive_tables():
    """Clean up inactive tables and access records (admin function).

    Returns:
        JSON response with cleanup results
    """
    try:
        # This could be restricted to admin users in the future
        default_timeout = current_app.config.get("TABLE_INACTIVE_TIMEOUT", 30)
        timeout_minutes = request.json.get("timeout_minutes", default_timeout) if request.json else default_timeout

        # Clean up inactive tables
        closed_tables = TableManager.close_inactive_tables(timeout_minutes)

        # Clean up inactive access records
        cleaned_access = TableAccessManager.cleanup_inactive_access(timeout_minutes)

        # Clean up expired private tables
        expired_private = TableManager.cleanup_expired_private_tables()

        return jsonify(
            {
                "success": True,
                "closed_tables": closed_tables,
                "cleaned_access_records": cleaned_access,
                "expired_private_tables": expired_private,
                "message": f"Closed {closed_tables} tables, cleaned {cleaned_access} access records, and {expired_private} expired private tables",
            }
        )
    except Exception as e:
        current_app.logger.error(f"Failed to cleanup: {e}")
        return jsonify({"success": False, "error": "Failed to cleanup"}), 500
