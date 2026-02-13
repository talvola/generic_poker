"""
Test-only API routes for E2E testing.

These endpoints are intended for use by automated tests to manage server state.
In production, these should be disabled or protected.
"""

from flask import Blueprint, jsonify, current_app
from ..database import db
from ..models.table import PokerTable
from ..models.table_access import TableAccess
from ..models.user import User

test_bp = Blueprint('test', __name__, url_prefix='/api/test')


@test_bp.route('/cleanup', methods=['POST'])
def cleanup_test_data():
    """
    Clean up all test data and reset game sessions.

    This endpoint:
    1. Removes all tables with names starting with 'Test '
    2. Removes associated table_access records
    3. Clears in-memory game sessions for test tables

    Returns:
        JSON response with cleanup statistics
    """
    try:
        # Find test tables
        test_tables = db.session.query(PokerTable).filter(
            PokerTable.name.like('Test %')
        ).all()

        test_table_ids = [t.id for t in test_tables]

        # Clear game sessions for test tables
        from ..services.game_orchestrator import game_orchestrator
        sessions_cleared = 0
        for table_id in test_table_ids:
            if game_orchestrator.clear_session(table_id):
                sessions_cleared += 1

        # Delete table_access records
        access_deleted = db.session.query(TableAccess).filter(
            TableAccess.table_id.in_(test_table_ids)
        ).delete(synchronize_session='fetch')

        # Delete test tables
        tables_deleted = db.session.query(PokerTable).filter(
            PokerTable.id.in_(test_table_ids)
        ).delete(synchronize_session='fetch')

        # Reset test user bankrolls to their seeded values
        seed_bankrolls = {
            'testuser': 800, 'alice': 1000, 'bob': 1500,
            'charlie': 500, 'diana': 2000
        }
        bankrolls_reset = 0
        for username, bankroll in seed_bankrolls.items():
            updated = db.session.query(User).filter(
                User.username == username
            ).update({'bankroll': bankroll})
            bankrolls_reset += updated

        db.session.commit()

        return jsonify({
            'success': True,
            'tables_deleted': tables_deleted,
            'access_records_deleted': access_deleted,
            'sessions_cleared': sessions_cleared,
            'bankrolls_reset': bankrolls_reset,
            'message': f'Cleaned up {tables_deleted} test tables'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Test cleanup failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@test_bp.route('/reset-table/<table_id>', methods=['POST'])
def reset_table_session(table_id: str):
    """
    Reset the game session for a specific table.

    This clears the in-memory game state, allowing the table
    to start fresh.

    Args:
        table_id: ID of the table to reset

    Returns:
        JSON response with reset result
    """
    try:
        from ..services.game_orchestrator import game_orchestrator

        # Clear the game session
        cleared = game_orchestrator.clear_session(table_id)

        # Also reset table_access ready states
        db.session.query(TableAccess).filter(
            TableAccess.table_id == table_id
        ).update({'is_ready': False})
        db.session.commit()

        return jsonify({
            'success': True,
            'session_cleared': cleared,
            'message': f'Reset table {table_id}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Table reset failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@test_bp.route('/status', methods=['GET'])
def test_status():
    """
    Get test environment status.

    Returns information about test tables and game sessions.

    Returns:
        JSON response with test environment status
    """
    try:
        from ..services.game_orchestrator import game_orchestrator

        # Count test tables
        test_table_count = db.session.query(PokerTable).filter(
            PokerTable.name.like('Test %')
        ).count()

        # Get all tables with active sessions
        active_sessions = game_orchestrator.get_active_session_count()

        return jsonify({
            'success': True,
            'test_tables': test_table_count,
            'active_sessions': active_sessions,
            'environment': 'test'
        })

    except Exception as e:
        current_app.logger.error(f"Test status failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
