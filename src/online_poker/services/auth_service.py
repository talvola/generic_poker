"""Authentication service for the online poker platform."""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import session, current_app
from flask_login import login_user, logout_user, current_user

from ..database import db
from ..models.user import User
from .user_manager import UserManager


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""
    pass


class SessionManager:
    """Manages user sessions and authentication state."""
    
    SESSION_TIMEOUT_HOURS = 24
    REMEMBER_ME_DAYS = 30
    
    @staticmethod
    def login_user_session(username: str, password: str, remember_me: bool = False) -> Dict[str, Any]:
        """Authenticate user and create session.
        
        Args:
            username: Username or email
            password: Plain text password
            remember_me: Whether to create persistent session
            
        Returns:
            Dict containing login result and user info
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Authenticate user
            user = UserManager.authenticate_user(username, password)
            if not user:
                raise AuthenticationError("Invalid username or password")
            
            # Create Flask-Login session
            login_user(user, remember=remember_me, duration=timedelta(days=SessionManager.REMEMBER_ME_DAYS))
            
            # Store additional session data
            session['user_id'] = user.id
            session['username'] = user.username
            session['login_time'] = datetime.utcnow().isoformat()
            session['session_token'] = SessionManager._generate_session_token()
            
            # Set session timeout
            if not remember_me:
                session.permanent = True
                current_app.permanent_session_lifetime = timedelta(hours=SessionManager.SESSION_TIMEOUT_HOURS)
            
            current_app.logger.info(f"User logged in: {user.username} (ID: {user.id})")
            
            return {
                'success': True,
                'user': user.to_dict(),
                'session_token': session['session_token'],
                'message': 'Login successful'
            }
            
        except AuthenticationError:
            raise
        except Exception as e:
            current_app.logger.error(f"Login error for {username}: {e}")
            raise AuthenticationError("Login failed due to system error")
    
    @staticmethod
    def logout_user_session() -> Dict[str, Any]:
        """Logout user and clear session.
        
        Returns:
            Dict containing logout result
        """
        try:
            username = getattr(current_user, 'username', 'Unknown') if current_user.is_authenticated else 'Unknown'
            
            # Clear Flask-Login session
            logout_user()
            
            # Clear session data
            session.clear()
            
            current_app.logger.info(f"User logged out: {username}")
            
            return {
                'success': True,
                'message': 'Logout successful'
            }
            
        except Exception as e:
            current_app.logger.error(f"Logout error: {e}")
            return {
                'success': False,
                'message': 'Logout failed'
            }
    
    @staticmethod
    def get_current_user_info() -> Optional[Dict[str, Any]]:
        """Get current authenticated user information.
        
        Returns:
            Dict containing user info or None if not authenticated
        """
        try:
            if not current_user.is_authenticated:
                return None
            
            # Verify session is still valid
            if not SessionManager._is_session_valid():
                SessionManager.logout_user_session()
                return None
            
            return {
                'user': current_user.to_dict(),
                'session_token': session.get('session_token'),
                'login_time': session.get('login_time'),
                'is_authenticated': True
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting current user info: {e}")
            return None
    
    @staticmethod
    def refresh_session() -> bool:
        """Refresh current user session.
        
        Returns:
            bool: True if session refreshed successfully
        """
        try:
            if not current_user.is_authenticated:
                return False
            
            # Update session timestamp
            session['last_activity'] = datetime.utcnow().isoformat()
            
            # Update user's last login
            current_user.update_last_login()
            db.session.commit()
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error refreshing session: {e}")
            return False
    
    @staticmethod
    def is_user_authenticated() -> bool:
        """Check if current user is authenticated.
        
        Returns:
            bool: True if user is authenticated and session is valid
        """
        try:
            return current_user.is_authenticated and SessionManager._is_session_valid()
        except Exception:
            return False
    
    @staticmethod
    def require_authentication() -> Optional[Dict[str, Any]]:
        """Require user authentication, return error if not authenticated.
        
        Returns:
            Dict containing error info if not authenticated, None if authenticated
        """
        if not SessionManager.is_user_authenticated():
            return {
                'success': False,
                'error': 'authentication_required',
                'message': 'Authentication required'
            }
        return None
    
    @staticmethod
    def _generate_session_token() -> str:
        """Generate secure session token.
        
        Returns:
            str: Secure session token
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def _is_session_valid() -> bool:
        """Check if current session is valid.
        
        Returns:
            bool: True if session is valid
        """
        try:
            # Check if session has required data
            if 'user_id' not in session or 'session_token' not in session:
                return False
            
            # Check session timeout for non-persistent sessions
            if not session.permanent and 'login_time' in session:
                login_time = datetime.fromisoformat(session['login_time'])
                if datetime.utcnow() - login_time > timedelta(hours=SessionManager.SESSION_TIMEOUT_HOURS):
                    return False
            
            # Verify user still exists and is active
            user = UserManager.get_user_by_id(session['user_id'])
            if not user or not user.is_active:
                return False
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error validating session: {e}")
            return False


class PasswordResetService:
    """Handles password reset functionality."""
    
    RESET_TOKEN_EXPIRY_HOURS = 1
    
    @staticmethod
    def generate_reset_token(email: str) -> Dict[str, Any]:
        """Generate password reset token for user.
        
        Args:
            email: User's email address
            
        Returns:
            Dict containing reset token info
        """
        try:
            # Find user by email
            user = UserManager.get_user_by_email(email)
            if not user:
                # Don't reveal if email exists or not for security
                return {
                    'success': True,
                    'message': 'If the email exists, a reset link has been sent'
                }
            
            # Generate secure reset token
            reset_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
            
            # Store reset token in session (in production, use database or cache)
            session[f'reset_token_{user.id}'] = {
                'token_hash': token_hash,
                'expires_at': (datetime.utcnow() + timedelta(hours=PasswordResetService.RESET_TOKEN_EXPIRY_HOURS)).isoformat(),
                'user_id': user.id
            }
            
            current_app.logger.info(f"Password reset token generated for user: {user.username}")
            
            # In production, send email with reset link
            # For now, return token for testing
            return {
                'success': True,
                'message': 'If the email exists, a reset link has been sent',
                'reset_token': reset_token  # Remove this in production
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating reset token for {email}: {e}")
            return {
                'success': False,
                'message': 'Failed to generate reset token'
            }
    
    @staticmethod
    def reset_password(reset_token: str, new_password: str) -> Dict[str, Any]:
        """Reset user password using reset token.
        
        Args:
            reset_token: Password reset token
            new_password: New password
            
        Returns:
            Dict containing reset result
        """
        try:
            # Validate new password
            UserManager.validate_password(new_password)
            
            # Hash the provided token
            token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
            
            # Find matching reset token in session
            user_id = None
            for key in session.keys():
                if key.startswith('reset_token_'):
                    token_data = session[key]
                    if token_data['token_hash'] == token_hash:
                        # Check if token is expired
                        expires_at = datetime.fromisoformat(token_data['expires_at'])
                        if datetime.utcnow() > expires_at:
                            session.pop(key)
                            return {
                                'success': False,
                                'message': 'Reset token has expired'
                            }
                        
                        user_id = token_data['user_id']
                        session.pop(key)  # Remove used token
                        break
            
            if not user_id:
                return {
                    'success': False,
                    'message': 'Invalid or expired reset token'
                }
            
            # Get user and update password
            user = UserManager.get_user_by_id(user_id)
            if not user:
                return {
                    'success': False,
                    'message': 'User not found'
                }
            
            # Update password
            user.set_password(new_password)
            db.session.commit()
            
            current_app.logger.info(f"Password reset successful for user: {user.username}")
            
            return {
                'success': True,
                'message': 'Password reset successful'
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error resetting password: {e}")
            return {
                'success': False,
                'message': 'Failed to reset password'
            }
    
    @staticmethod
    def cleanup_expired_tokens() -> None:
        """Clean up expired reset tokens from session."""
        try:
            current_time = datetime.utcnow()
            expired_keys = []
            
            for key in session.keys():
                if key.startswith('reset_token_'):
                    token_data = session[key]
                    expires_at = datetime.fromisoformat(token_data['expires_at'])
                    if current_time > expires_at:
                        expired_keys.append(key)
            
            for key in expired_keys:
                session.pop(key)
                
        except Exception as e:
            current_app.logger.error(f"Error cleaning up expired tokens: {e}")


class SessionCleanupService:
    """Handles session cleanup and maintenance."""
    
    @staticmethod
    def cleanup_expired_sessions() -> int:
        """Clean up expired sessions.
        
        Returns:
            int: Number of sessions cleaned up
        """
        try:
            # In production, this would clean up database-stored sessions
            # For now, just clean up password reset tokens
            PasswordResetService.cleanup_expired_tokens()
            
            current_app.logger.info("Session cleanup completed")
            return 0
            
        except Exception as e:
            current_app.logger.error(f"Error during session cleanup: {e}")
            return 0
    
    @staticmethod
    def get_active_sessions_count() -> int:
        """Get count of active sessions.
        
        Returns:
            int: Number of active sessions
        """
        try:
            # In production, this would query database for active sessions
            # For now, return 1 if current user is authenticated
            return 1 if SessionManager.is_user_authenticated() else 0
            
        except Exception as e:
            current_app.logger.error(f"Error getting active sessions count: {e}")
            return 0