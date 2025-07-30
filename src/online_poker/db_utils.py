"""Database utility functions."""

from typing import List, Optional, Dict, Any
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text
from .database import db, get_db_session
from .models import User, PokerTable, Transaction, GameHistory
import logging

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom database error."""
    pass


def safe_commit() -> bool:
    """Safely commit database session with error handling."""
    try:
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database commit failed: {e}")
        return False


def safe_add_and_commit(obj) -> bool:
    """Safely add object to session and commit."""
    try:
        db.session.add(obj)
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Failed to add and commit object: {e}")
        return False


def create_user_with_validation(username: str, email: str, password: str, 
                               bankroll: int = 1000) -> Optional[User]:
    """Create user with validation and error handling."""
    try:
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                raise DatabaseError("Username already exists")
            else:
                raise DatabaseError("Email already exists")
        
        # Create new user
        user = User(username=username, email=email, password=password, bankroll=bankroll)
        
        if safe_add_and_commit(user):
            logger.info(f"User created successfully: {username}")
            return user
        else:
            raise DatabaseError("Failed to create user")
            
    except SQLAlchemyError as e:
        logger.error(f"Database error creating user: {e}")
        raise DatabaseError(f"Database error: {str(e)}")


def create_table_with_validation(name: str, variant: str, betting_structure: str,
                                stakes: Dict[str, int], max_players: int, creator_id: str,
                                is_private: bool = False, allow_bots: bool = False,
                                password: Optional[str] = None) -> Optional[PokerTable]:
    """Create poker table with validation."""
    try:
        # Validate creator exists
        creator = User.query.get(creator_id)
        if not creator:
            raise DatabaseError("Creator user not found")
        
        # Create table
        table = PokerTable(
            name=name,
            variant=variant,
            betting_structure=betting_structure,
            stakes=stakes,
            max_players=max_players,
            creator_id=creator_id,
            is_private=is_private,
            allow_bots=allow_bots,
            password=password
        )
        
        if safe_add_and_commit(table):
            logger.info(f"Table created successfully: {name}")
            return table
        else:
            raise DatabaseError("Failed to create table")
            
    except SQLAlchemyError as e:
        logger.error(f"Database error creating table: {e}")
        raise DatabaseError(f"Database error: {str(e)}")


def process_transaction(user_id: str, amount: int, transaction_type: str,
                       description: str, table_id: Optional[str] = None) -> bool:
    """Process a bankroll transaction atomically."""
    try:
        # Start transaction
        user = User.query.get(user_id)
        if not user:
            raise DatabaseError("User not found")
        
        # Check if user can afford debit transactions
        if amount < 0 and user.bankroll + amount < 0:
            raise DatabaseError("Insufficient funds")
        
        # Update user bankroll
        user.bankroll += amount
        
        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            table_id=table_id
        )
        
        db.session.add(transaction)
        
        if safe_commit():
            logger.info(f"Transaction processed: {transaction_type} for user {user_id}")
            return True
        else:
            raise DatabaseError("Failed to process transaction")
            
    except SQLAlchemyError as e:
        logger.error(f"Database error processing transaction: {e}")
        raise DatabaseError(f"Database error: {str(e)}")


def get_user_transaction_history(user_id: str, limit: int = 50) -> List[Transaction]:
    """Get user's transaction history."""
    try:
        transactions = Transaction.query.filter_by(user_id=user_id)\
                                      .order_by(Transaction.created_at.desc())\
                                      .limit(limit)\
                                      .all()
        return transactions
    except SQLAlchemyError as e:
        logger.error(f"Error fetching transaction history: {e}")
        return []


def get_public_tables() -> List[PokerTable]:
    """Get all public tables."""
    try:
        tables = PokerTable.query.filter_by(is_private=False)\
                                .order_by(PokerTable.created_at.desc())\
                                .all()
        return tables
    except SQLAlchemyError as e:
        logger.error(f"Error fetching public tables: {e}")
        return []


def get_table_by_invite_code(invite_code: str) -> Optional[PokerTable]:
    """Get table by invite code."""
    try:
        return PokerTable.query.filter_by(invite_code=invite_code).first()
    except SQLAlchemyError as e:
        logger.error(f"Error fetching table by invite code: {e}")
        return None


def cleanup_inactive_tables(timeout_minutes: int = 30) -> int:
    """Clean up inactive tables and return count of cleaned tables."""
    try:
        inactive_tables = PokerTable.query.all()
        cleaned_count = 0
        
        for table in inactive_tables:
            if table.is_inactive(timeout_minutes):
                db.session.delete(table)
                cleaned_count += 1
        
        if safe_commit():
            logger.info(f"Cleaned up {cleaned_count} inactive tables")
            return cleaned_count
        else:
            return 0
            
    except SQLAlchemyError as e:
        logger.error(f"Error cleaning up inactive tables: {e}")
        return 0


def get_user_statistics(user_id: str) -> Dict[str, Any]:
    """Get comprehensive user statistics."""
    try:
        user = User.query.get(user_id)
        if not user:
            return {}
        
        # Get transaction statistics
        transactions = Transaction.query.filter_by(user_id=user_id).all()
        total_buyins = sum(t.amount for t in transactions if t.transaction_type == Transaction.TYPE_BUYIN)
        total_cashouts = sum(t.amount for t in transactions if t.transaction_type == Transaction.TYPE_CASHOUT)
        total_winnings = sum(t.amount for t in transactions if t.transaction_type == Transaction.TYPE_WINNINGS)
        
        # Get game history statistics
        game_count = GameHistory.query.join(PokerTable)\
                                    .filter(GameHistory.players.contains(user_id))\
                                    .count()
        
        return {
            'user_id': user_id,
            'username': user.username,
            'current_bankroll': user.bankroll,
            'total_buyins': abs(total_buyins),
            'total_cashouts': total_cashouts,
            'total_winnings': total_winnings,
            'net_profit': total_cashouts + total_winnings + total_buyins,  # buyins are negative
            'games_played': game_count,
            'account_created': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Error getting user statistics: {e}")
        return {}


def execute_raw_query(query: str, params: Optional[Dict] = None) -> List[Dict]:
    """Execute raw SQL query safely."""
    try:
        result = db.session.execute(text(query), params or {})
        return [dict(row) for row in result]
    except SQLAlchemyError as e:
        logger.error(f"Error executing raw query: {e}")
        return []


def get_database_health() -> Dict[str, Any]:
    """Get database health information."""
    try:
        health = {
            'status': 'healthy',
            'user_count': User.query.count(),
            'active_tables': PokerTable.query.count(),
            'total_transactions': Transaction.query.count(),
            'total_games': GameHistory.query.count(),
        }
        
        # Test database connection
        db.session.execute(text('SELECT 1'))
        
        return health
        
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }