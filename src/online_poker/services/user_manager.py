"""User management service for the online poker platform."""

import re
from typing import Optional, Dict, Any
from sqlalchemy.exc import IntegrityError
from flask import current_app

from ..database import db
from ..models.user import User


class UserValidationError(Exception):
    """Exception raised for user validation errors."""
    pass


class UserManager:
    """Service class for managing user accounts and authentication."""
    
    @staticmethod
    def validate_username(username: str) -> None:
        """Validate username format and availability.
        
        Args:
            username: Username to validate
            
        Raises:
            UserValidationError: If username is invalid
        """
        if not username:
            raise UserValidationError("Username is required")
        
        if len(username) < 3:
            raise UserValidationError("Username must be at least 3 characters long")
        
        if len(username) > 50:
            raise UserValidationError("Username must be no more than 50 characters long")
        
        # Check for valid characters (alphanumeric and underscore)
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise UserValidationError("Username can only contain letters, numbers, and underscores")
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            raise UserValidationError("Username already exists")
    
    @staticmethod
    def validate_email(email: str) -> None:
        """Validate email format and availability.
        
        Args:
            email: Email to validate
            
        Raises:
            UserValidationError: If email is invalid
        """
        if not email:
            raise UserValidationError("Email is required")
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise UserValidationError("Invalid email format")
        
        if len(email) > 120:
            raise UserValidationError("Email must be no more than 120 characters long")
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            raise UserValidationError("Email already exists")
    
    @staticmethod
    def validate_password(password: str) -> None:
        """Validate password strength.
        
        Args:
            password: Password to validate
            
        Raises:
            UserValidationError: If password is invalid
        """
        if not password:
            raise UserValidationError("Password is required")
        
        if len(password) < 8:
            raise UserValidationError("Password must be at least 8 characters long")
        
        if len(password) > 128:
            raise UserValidationError("Password must be no more than 128 characters long")
        
        # Check for at least one letter and one number
        if not re.search(r'[a-zA-Z]', password):
            raise UserValidationError("Password must contain at least one letter")
        
        if not re.search(r'\d', password):
            raise UserValidationError("Password must contain at least one number")
    
    @staticmethod
    def create_user(username: str, email: str, password: str, starting_bankroll: int = 1000) -> User:
        """Create a new user account with validation.
        
        Args:
            username: Unique username
            email: User's email address
            password: Plain text password (will be hashed)
            starting_bankroll: Initial bankroll amount
            
        Returns:
            User: Created user instance
            
        Raises:
            UserValidationError: If validation fails
        """
        # Validate all inputs
        UserManager.validate_username(username)
        UserManager.validate_email(email)
        UserManager.validate_password(password)
        
        if starting_bankroll < 0:
            raise UserValidationError("Starting bankroll cannot be negative")
        
        try:
            # Create new user
            user = User(
                username=username,
                email=email,
                password=password,
                bankroll=starting_bankroll
            )
            
            # Save to database
            db.session.add(user)
            db.session.commit()
            
            current_app.logger.info(f"Created new user: {username} (ID: {user.id})")
            return user
            
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Database integrity error creating user {username}: {e}")
            raise UserValidationError("Username or email already exists")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating user {username}: {e}")
            raise UserValidationError("Failed to create user account")
    
    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password.
        
        Args:
            username: Username or email
            password: Plain text password
            
        Returns:
            User: Authenticated user instance or None if authentication fails
        """
        if not username or not password:
            return None
        
        try:
            # Try to find user by username or email
            user = User.query.filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if user and user.is_active and user.check_password(password):
                # Update last login timestamp
                user.update_last_login()
                db.session.commit()
                
                current_app.logger.info(f"User authenticated: {user.username} (ID: {user.id})")
                return user
            
            current_app.logger.warning(f"Failed authentication attempt for: {username}")
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error during authentication for {username}: {e}")
            return None
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[User]:
        """Get user by ID.
        
        Args:
            user_id: User's unique ID
            
        Returns:
            User: User instance or None if not found
        """
        try:
            return User.query.filter_by(id=user_id, is_active=True).first()
        except Exception as e:
            current_app.logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[User]:
        """Get user by username.
        
        Args:
            username: Username
            
        Returns:
            User: User instance or None if not found
        """
        try:
            return User.query.filter_by(username=username, is_active=True).first()
        except Exception as e:
            current_app.logger.error(f"Error getting user by username {username}: {e}")
            return None
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """Get user by email.
        
        Args:
            email: Email address
            
        Returns:
            User: User instance or None if not found
        """
        try:
            return User.query.filter_by(email=email, is_active=True).first()
        except Exception as e:
            current_app.logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    @staticmethod
    def update_user_bankroll(user_id: str, amount: int) -> bool:
        """Update user's bankroll by the specified amount.
        
        Args:
            user_id: User's unique ID
            amount: Amount to add/subtract from bankroll
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            user = UserManager.get_user_by_id(user_id)
            if not user:
                return False
            
            if user.update_bankroll(amount):
                db.session.commit()
                current_app.logger.info(f"Updated bankroll for user {user.username}: {amount}")
                return True
            else:
                current_app.logger.warning(f"Insufficient funds for user {user.username}: {amount}")
                return False
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating bankroll for user {user_id}: {e}")
            return False
    
    @staticmethod
    def deactivate_user(user_id: str) -> bool:
        """Deactivate a user account.
        
        Args:
            user_id: User's unique ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            user = User.query.filter_by(id=user_id).first()
            if not user:
                return False
            
            user.is_active = False
            db.session.commit()
            
            current_app.logger.info(f"Deactivated user: {user.username} (ID: {user_id})")
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deactivating user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_user_statistics(user_id: str) -> Dict[str, Any]:
        """Get basic user statistics.
        
        Args:
            user_id: User's unique ID
            
        Returns:
            Dict: User statistics or empty dict if user not found
        """
        try:
            user = UserManager.get_user_by_id(user_id)
            if not user:
                return {}
            
            # Basic statistics - can be expanded later
            stats = {
                'username': user.username,
                'bankroll': user.bankroll,
                'member_since': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'total_tables_created': len(user.created_tables),
                'total_transactions': len(user.transactions)
            }
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Error getting statistics for user {user_id}: {e}")
            return {}