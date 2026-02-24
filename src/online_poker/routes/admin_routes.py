"""Admin routes for platform management."""

import functools
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..database import db
from ..models.disabled_variant import DisabledVariant
from ..models.game_history import GameHistory
from ..models.table import PokerTable
from ..models.table_access import TableAccess
from ..models.transaction import Transaction
from ..models.user import User
from ..services.table_manager import TableManager

admin_bp = Blueprint("admin", __name__, template_folder="../../templates/admin")


def admin_required(f):
    """Decorator that requires the user to be an admin."""

    @functools.wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            # API routes return JSON 403, page routes redirect
            if request.path.startswith("/admin/api/"):
                return jsonify({"success": False, "message": "Admin access required"}), 403
            return redirect(url_for("lobby.index"))
        return f(*args, **kwargs)

    return decorated_function


# --- Page routes ---


@admin_bp.route("/")
@admin_required
def dashboard():
    """Admin dashboard page."""
    return render_template("admin/dashboard.html")


@admin_bp.route("/users")
@admin_required
def users():
    """User management page."""
    return render_template("admin/users.html")


@admin_bp.route("/tables")
@admin_required
def tables():
    """Table management page."""
    return render_template("admin/tables.html")


@admin_bp.route("/variants")
@admin_required
def variants():
    """Variant management page."""
    return render_template("admin/variants.html")


# --- API routes ---


@admin_bp.route("/api/stats")
@admin_required
def api_stats():
    """Get dashboard statistics."""
    try:
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        total_users = db.session.query(func.count(User.id)).scalar()
        active_users_7d = db.session.query(func.count(User.id)).filter(User.last_login >= week_ago).scalar()
        total_bankroll = db.session.query(func.sum(User.bankroll)).scalar() or 0
        total_tables = db.session.query(func.count(PokerTable.id)).scalar()
        hands_today = db.session.query(func.count(GameHistory.id)).filter(GameHistory.completed_at >= today).scalar()
        hands_week = db.session.query(func.count(GameHistory.id)).filter(GameHistory.completed_at >= week_ago).scalar()
        disabled_count = db.session.query(func.count(DisabledVariant.id)).scalar()

        # Live sessions from orchestrator
        try:
            from ..services.game_orchestrator import game_orchestrator

            orchestrator_stats = game_orchestrator.get_orchestrator_stats()
        except Exception:
            orchestrator_stats = {
                "active_sessions": 0,
                "total_players": 0,
                "total_spectators": 0,
            }

        return jsonify(
            {
                "success": True,
                "stats": {
                    "total_users": total_users,
                    "active_users_7d": active_users_7d,
                    "total_bankroll": total_bankroll,
                    "total_tables": total_tables,
                    "hands_today": hands_today,
                    "hands_week": hands_week,
                    "disabled_variants": disabled_count,
                    "live_sessions": orchestrator_stats.get("active_sessions", 0),
                    "live_players": orchestrator_stats.get("total_players", 0),
                    "live_spectators": orchestrator_stats.get("total_spectators", 0),
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/sessions")
@admin_required
def api_sessions():
    """Get live game sessions from orchestrator."""
    try:
        from ..services.game_orchestrator import game_orchestrator

        sessions = game_orchestrator.get_all_sessions()
        session_list = [s.get_session_info() for s in sessions]
        return jsonify({"success": True, "sessions": session_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route("/api/users")
@admin_required
def api_users():
    """Get paginated user list."""
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    sort = request.args.get("sort", "username")

    query = db.session.query(User)

    if search:
        query = query.filter((User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%")))

    sort_map = {
        "username": User.username,
        "bankroll": User.bankroll.desc(),
        "created_at": User.created_at.desc(),
        "last_login": User.last_login.desc(),
    }
    order = sort_map.get(sort, User.username)
    query = query.order_by(order)

    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify(
        {
            "success": True,
            "users": [u.to_dict() for u in users],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        }
    )


@admin_bp.route("/api/users/<user_id>")
@admin_required
def api_user_detail(user_id):
    """Get user detail with recent transactions and hands."""
    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    recent_transactions = (
        db.session.query(Transaction).filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(20).all()
    )

    # Count hands played
    hands_played = db.session.query(func.count(GameHistory.id)).filter(GameHistory.players.contains(user_id)).scalar()

    # Active table sessions
    active_sessions = db.session.query(TableAccess).filter_by(user_id=user_id, is_active=True, is_spectator=False).all()

    return jsonify(
        {
            "success": True,
            "user": user.to_dict(),
            "transactions": [t.to_dict() for t in recent_transactions],
            "hands_played": hands_played,
            "active_sessions": len(active_sessions),
        }
    )


@admin_bp.route("/api/users/<user_id>/bankroll", methods=["POST"])
@admin_required
def api_adjust_bankroll(user_id):
    """Adjust a user's bankroll."""
    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    data = request.get_json()
    if not data or "amount" not in data:
        return jsonify({"success": False, "message": "Amount required"}), 400

    amount = data["amount"]
    if not isinstance(amount, int):
        return jsonify({"success": False, "message": "Amount must be an integer"}), 400

    reason = data.get("reason", "Admin adjustment")

    old_bankroll = user.bankroll
    if not user.update_bankroll(amount):
        return jsonify({"success": False, "message": "Would result in negative bankroll"}), 400

    # Create transaction record
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        transaction_type=Transaction.TYPE_ADJUSTMENT,
        description=f"Admin adjustment by {current_user.username}: {reason}",
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "old_bankroll": old_bankroll,
            "new_bankroll": user.bankroll,
        }
    )


@admin_bp.route("/api/users/<user_id>/toggle-active", methods=["POST"])
@admin_required
def api_toggle_active(user_id):
    """Toggle user active status."""
    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    if user.id == current_user.id:
        return jsonify({"success": False, "message": "Cannot deactivate yourself"}), 400

    user.is_active = not user.is_active
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "is_active": user.is_active,
        }
    )


@admin_bp.route("/api/tables")
@admin_required
def api_tables():
    """Get all tables (including private)."""
    tables = db.session.query(PokerTable).order_by(PokerTable.last_activity.desc()).all()

    table_list = []
    for table in tables:
        table_data = table.to_dict(include_sensitive=True)
        # Add creator username
        creator = db.session.query(User).filter_by(id=table.creator_id).first()
        table_data["creator_username"] = creator.username if creator else "Unknown"
        table_list.append(table_data)

    return jsonify({"success": True, "tables": table_list})


@admin_bp.route("/api/tables/purge-all", methods=["POST"])
@admin_required
def api_purge_all_tables():
    """Delete all tables, clear sessions, and reset bankrolls."""
    from ..services.game_orchestrator import game_orchestrator

    # Clear all game sessions
    sessions_cleared = 0
    tables = db.session.query(PokerTable).all()
    for table in tables:
        try:
            if game_orchestrator.clear_session(table.id):
                sessions_cleared += 1
        except Exception as e:
            current_app.logger.debug(f"Skipping session clear for {table.id}: {e}")

    # Cash out all active players
    active_accesses = db.session.query(TableAccess).filter_by(is_active=True).all()
    for access in active_accesses:
        if access.current_stack and access.current_stack > 0:
            user = db.session.query(User).filter_by(id=access.user_id).first()
            if user:
                user.bankroll += access.current_stack

    # Delete all access records and tables
    access_deleted = db.session.query(TableAccess).delete()
    tables_deleted = db.session.query(PokerTable).delete()

    # Reset seed bankrolls
    seed_bankrolls = {"testuser": 800, "alice": 1000, "bob": 1500, "charlie": 500, "diana": 2000}
    for username, bankroll in seed_bankrolls.items():
        db.session.query(User).filter_by(username=username).update({"bankroll": bankroll})

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "tables_deleted": tables_deleted,
            "access_deleted": access_deleted,
            "sessions_cleared": sessions_cleared,
            "message": f"Purged {tables_deleted} tables, reset bankrolls",
        }
    )


@admin_bp.route("/api/tables/<table_id>/close", methods=["POST"])
@admin_required
def api_close_table(table_id):
    """Force-close a table."""
    table = db.session.query(PokerTable).filter_by(id=table_id).first()
    if not table:
        return jsonify({"success": False, "message": "Table not found"}), 404

    # Clear game session if active
    try:
        from ..services.game_orchestrator import game_orchestrator

        game_orchestrator.clear_session(table_id)
    except Exception as e:
        current_app.logger.warning(f"Failed to clear session for table {table_id}: {e}")

    # Mark all access records as inactive
    active_accesses = db.session.query(TableAccess).filter_by(table_id=table_id, is_active=True).all()
    for access in active_accesses:
        # Cash out players
        if access.current_stack and access.current_stack > 0:
            user = db.session.query(User).filter_by(id=access.user_id).first()
            if user:
                user.bankroll += access.current_stack
                transaction = Transaction(
                    user_id=access.user_id,
                    amount=access.current_stack,
                    transaction_type=Transaction.TYPE_CASHOUT,
                    description=f"Admin force-close of table '{table.name}'",
                    table_id=table_id,
                )
                db.session.add(transaction)
        access.is_active = False
        access.is_ready = False

    db.session.commit()

    return jsonify({"success": True, "message": f"Table '{table.name}' closed"})


@admin_bp.route("/api/tables/<table_id>/delete", methods=["POST"])
@admin_required
def api_delete_table(table_id):
    """Delete a table and all associated records."""
    table = db.session.query(PokerTable).filter_by(id=table_id).first()
    if not table:
        return jsonify({"success": False, "message": "Table not found"}), 404

    table_name = table.name

    # Clear game session if active
    try:
        from ..services.game_orchestrator import game_orchestrator

        game_orchestrator.clear_session(table_id)
    except Exception as e:
        current_app.logger.warning(f"Failed to clear session for table {table_id}: {e}")

    # Cash out active players
    active_accesses = db.session.query(TableAccess).filter_by(table_id=table_id, is_active=True).all()
    for access in active_accesses:
        if access.current_stack and access.current_stack > 0:
            user = db.session.query(User).filter_by(id=access.user_id).first()
            if user:
                user.bankroll += access.current_stack
                transaction = Transaction(
                    user_id=access.user_id,
                    amount=access.current_stack,
                    transaction_type=Transaction.TYPE_CASHOUT,
                    description=f"Admin deleted table '{table_name}'",
                    table_id=table_id,
                )
                db.session.add(transaction)

    # Clear FK references before deleting the table
    from ..models.chat import ChatMessage, ChatModerationAction
    from ..models.game_history import GameHistory
    from ..models.game_session_state import GameSessionState

    # Null out transaction references (keep audit trail)
    db.session.query(Transaction).filter_by(table_id=table_id).update({"table_id": None})
    # Delete related records
    db.session.query(ChatMessage).filter_by(table_id=table_id).delete()
    db.session.query(ChatModerationAction).filter_by(table_id=table_id).delete()
    db.session.query(GameHistory).filter_by(table_id=table_id).delete()
    db.session.query(GameSessionState).filter_by(table_id=table_id).delete()
    db.session.query(TableAccess).filter_by(table_id=table_id).delete()
    db.session.delete(table)
    db.session.commit()

    return jsonify({"success": True, "message": f"Table '{table_name}' deleted"})


@admin_bp.route("/api/variants")
@admin_required
def api_variants():
    """Get all variants with disabled status."""
    all_variants = TableManager.get_available_variants(include_disabled=True)
    disabled = {dv.variant_name for dv in db.session.query(DisabledVariant).all()}
    disabled_details = {dv.variant_name: dv.to_dict() for dv in db.session.query(DisabledVariant).all()}

    result = []
    for v in all_variants:
        v["disabled"] = v["name"] in disabled
        if v["name"] in disabled_details:
            v["disabled_info"] = disabled_details[v["name"]]
        result.append(v)

    # Also include disabled variants that might not appear in the available list
    available_names = {v["name"] for v in result}
    for name, info in disabled_details.items():
        if name not in available_names:
            result.append(
                {
                    "name": name,
                    "display_name": name.replace("_", " ").title(),
                    "category": "Unknown",
                    "disabled": True,
                    "disabled_info": info,
                }
            )

    result.sort(key=lambda x: x.get("display_name", x["name"]))
    return jsonify({"success": True, "variants": result, "total": len(result)})


@admin_bp.route("/api/variants/<name>/disable", methods=["POST"])
@admin_required
def api_disable_variant(name):
    """Disable a variant."""
    existing = db.session.query(DisabledVariant).filter_by(variant_name=name).first()
    if existing:
        return jsonify({"success": False, "message": "Variant already disabled"}), 400

    data = request.get_json() or {}
    reason = data.get("reason", "")

    dv = DisabledVariant()
    dv.variant_name = name
    dv.reason = reason
    dv.disabled_by = current_user.id
    db.session.add(dv)
    db.session.commit()

    return jsonify({"success": True, "message": f"Variant '{name}' disabled"})


@admin_bp.route("/api/variants/<name>/enable", methods=["POST"])
@admin_required
def api_enable_variant(name):
    """Re-enable a variant."""
    dv = db.session.query(DisabledVariant).filter_by(variant_name=name).first()
    if not dv:
        return jsonify({"success": False, "message": "Variant is not disabled"}), 400

    db.session.delete(dv)
    db.session.commit()

    return jsonify({"success": True, "message": f"Variant '{name}' enabled"})
