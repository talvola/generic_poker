"""Unit tests for authentication service."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from flask import Flask, session
from flask_login import current_user

from src.online_poker.services.auth_service import (
    SessionManager, PasswordResetService, SessionCleanupService, AuthenticationError
)
from src.online_poker.services.user_manager import UserManager
from src.online_poker.models.user import User
from src.online_poker.database import db


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize Flask-Login
    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from src.online_poker.services.user_manager import UserManager
        return UserManager().get_user_by_id(user_id)
    
    with app.app_context():
        db.init_app(app)
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def app_context(app):
    """Create app context for tests."""
    with app.app_context():
        with app.test_request_context():
            yield


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_user(app_context):
    """Create a test user."""
    user = UserManager.create_user("testuser", "test@example.com", "password123")
    return user


class TestSessionManager:
    """Test SessionManager functionality."""
    
    @patch('src.online_poker.services.auth_service.login_user')
    def test_login_user_session_success(self, mock_login_user, app_context, test_user):
        """Test successful user login and session creation."""
        with patch('flask.session', {}):
            result = SessionManager.login_user_session("testuser", "password123", False)
            
            assert result['success'] is True
            assert result['user']['username'] == "testuser"
            assert 'session_token' in result
            assert result['message'] == 'Login successful'
            mock_login_user.assert_called_once()
    
    def test_login_user_session_invalid_credentials(self, app_context):
        """Test login with invalid credentials."""
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            SessionManager.login_user_session("nonexistent", "wrongpassword", False)
    
    @patch('src.online_poker.services.auth_service.session')
    @patch('src.online_poker.services.auth_service.logout_user')
    @patch('src.online_poker.services.auth_service.current_user')
    def test_logout_user_session_success(self, mock_current_user, mock_logout_user, mock_session, app_context):
        """Test successful user logout."""
        mock_current_user.is_authenticated = True
        mock_current_user.username = "testuser"

        # Ensure clear() is a non-async mock
        mock_session.clear = MagicMock()

        result = SessionManager.logout_user_session()

        assert result['success'] is True
        assert result['message'] == 'Logout successful'
        mock_logout_user.assert_called_once()
        mock_session.clear.assert_called_once()
    
    def test_get_current_user_info_authenticated(self, app_context, test_user):
        """Test getting current user info when authenticated."""
        mock_current_user = MagicMock()
        mock_current_user.is_authenticated = True
        mock_current_user.to_dict.return_value = test_user.to_dict()
        
        mock_session = MagicMock()
        mock_session.get.side_effect = lambda key: {
            'session_token': 'test-token',
            'login_time': datetime.utcnow().isoformat()
        }.get(key)
        
        with patch('src.online_poker.services.auth_service.current_user', mock_current_user):
            with patch('src.online_poker.services.auth_service.session', mock_session):
                with patch.object(SessionManager, '_is_session_valid', return_value=True):
                    result = SessionManager.get_current_user_info()
                    
                    assert result is not None
                    assert result['user']['username'] == "testuser"
                    assert result['session_token'] == 'test-token'
                    assert result['is_authenticated'] is True
    
    @patch('src.online_poker.services.auth_service.current_user')
    def test_get_current_user_info_not_authenticated(self, mock_current_user, app_context):
        """Test getting current user info when not authenticated."""
        mock_current_user.is_authenticated = False
        
        result = SessionManager.get_current_user_info()
        
        assert result is None
    
    @patch('src.online_poker.services.auth_service.current_user')
    def test_refresh_session_success(self, mock_current_user, app_context, test_user):
        """Test successful session refresh."""
        mock_current_user.is_authenticated = True
        mock_current_user.update_last_login = MagicMock()
        
        with patch('flask.session', {}) as mock_session:
            with patch('src.online_poker.database.db.session.commit'):
                result = SessionManager.refresh_session()
                
                assert result is True
                mock_current_user.update_last_login.assert_called_once()
    
    @patch('src.online_poker.services.auth_service.current_user')
    def test_refresh_session_not_authenticated(self, mock_current_user, app_context):
        """Test session refresh when not authenticated."""
        mock_current_user.is_authenticated = False
        
        result = SessionManager.refresh_session()
        
        assert result is False
    
    @patch('src.online_poker.services.auth_service.current_user')
    def test_is_user_authenticated_true(self, mock_current_user, app_context):
        """Test authentication check when user is authenticated."""
        mock_current_user.is_authenticated = True
        
        with patch.object(SessionManager, '_is_session_valid', return_value=True):
            result = SessionManager.is_user_authenticated()
            
            assert result is True
    
    @patch('src.online_poker.services.auth_service.current_user')
    def test_is_user_authenticated_false(self, mock_current_user, app_context):
        """Test authentication check when user is not authenticated."""
        mock_current_user.is_authenticated = False
        
        result = SessionManager.is_user_authenticated()
        
        assert result is False
    
    def test_require_authentication_success(self, app_context):
        """Test require authentication when user is authenticated."""
        with patch.object(SessionManager, 'is_user_authenticated', return_value=True):
            result = SessionManager.require_authentication()
            
            assert result is None
    
    def test_require_authentication_failure(self, app_context):
        """Test require authentication when user is not authenticated."""
        with patch.object(SessionManager, 'is_user_authenticated', return_value=False):
            result = SessionManager.require_authentication()
            
            assert result is not None
            assert result['success'] is False
            assert result['error'] == 'authentication_required'
    
    def test_generate_session_token(self, app_context):
        """Test session token generation."""
        token = SessionManager._generate_session_token()
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_is_session_valid_missing_data(self, app_context):
        """Test session validation with missing session data."""
        with patch('flask.session', {}):
            result = SessionManager._is_session_valid()
            
            assert result is False
    
    def test_is_session_valid_expired_session(self, app_context):
        """Test session validation with expired session."""
        old_time = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        
        with patch('flask.session', {
            'user_id': 'test-id',
            'session_token': 'test-token',
            'login_time': old_time,
            'permanent': False
        }):
            result = SessionManager._is_session_valid()
            
            assert result is False
    
    def test_is_session_valid_inactive_user(self, app_context, test_user):
        """Test session validation with inactive user."""
        test_user.is_active = False
        db.session.commit()
        
        with patch('flask.session', {
            'user_id': test_user.id,
            'session_token': 'test-token',
            'login_time': datetime.utcnow().isoformat()
        }):
            result = SessionManager._is_session_valid()
            
            assert result is False


class TestPasswordResetService:
    """Test PasswordResetService functionality."""
    
    def test_generate_reset_token_existing_user(self, app_context, test_user):
        """Test generating reset token for existing user."""
        with patch('flask.session', {}) as mock_session:
            result = PasswordResetService.generate_reset_token("test@example.com")
            
            assert result['success'] is True
            assert 'reset_token' in result
            assert result['message'] == 'If the email exists, a reset link has been sent'
    
    def test_generate_reset_token_nonexistent_user(self, app_context):
        """Test generating reset token for nonexistent user."""
        with patch('flask.session', {}):
            result = PasswordResetService.generate_reset_token("nonexistent@example.com")
            
            assert result['success'] is True
            assert result['message'] == 'If the email exists, a reset link has been sent'
    
    def test_reset_password_success(self, app_context, test_user):
        """Test successful password reset."""
        # First generate a reset token
        with patch('flask.session', {}) as mock_session:
            token_result = PasswordResetService.generate_reset_token("test@example.com")
            reset_token = token_result['reset_token']
            
            # Now reset the password
            result = PasswordResetService.reset_password(reset_token, "newpassword123")
            
            assert result['success'] is True
            assert result['message'] == 'Password reset successful'
            
            # Verify password was changed
            updated_user = UserManager.get_user_by_id(test_user.id)
            assert updated_user.check_password("newpassword123")
    
    def test_reset_password_invalid_token(self, app_context):
        """Test password reset with invalid token."""
        with patch('flask.session', {}):
            result = PasswordResetService.reset_password("invalid-token", "newpassword123")
            
            assert result['success'] is False
            assert result['message'] == 'Invalid or expired reset token'
    
    def test_reset_password_expired_token(self, app_context, test_user):
        """Test password reset with expired token."""
        # Create an expired token manually
        expired_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        test_token = "test-token"
        
        # Calculate the correct hash for the test token
        import hashlib
        token_hash = hashlib.sha256(test_token.encode()).hexdigest()
        
        # Create a proper mock session
        mock_session = MagicMock()
        session_data = {
            f'reset_token_{test_user.id}': {
                'token_hash': token_hash,
                'expires_at': expired_time,
                'user_id': test_user.id
            }
        }
        
        # Mock session methods
        mock_session.keys.return_value = session_data.keys()
        mock_session.__getitem__.side_effect = session_data.__getitem__
        mock_session.pop.side_effect = session_data.pop
        
        with patch('src.online_poker.services.auth_service.session', mock_session):
            result = PasswordResetService.reset_password(test_token, "newpassword123")
            
            assert result['success'] is False
            assert result['message'] == 'Reset token has expired'
    
    def test_reset_password_invalid_password(self, app_context, test_user):
        """Test password reset with invalid new password."""
        with patch('flask.session', {}) as mock_session:
            token_result = PasswordResetService.generate_reset_token("test@example.com")
            reset_token = token_result['reset_token']
            
            # Try to reset with invalid password
            result = PasswordResetService.reset_password(reset_token, "weak")
            
            assert result['success'] is False
    
    def test_cleanup_expired_tokens(self, app_context):
        """Test cleanup of expired reset tokens."""
        expired_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        valid_time = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        # Use the actual Flask session instead of mocking
        from flask import session
        session['reset_token_expired'] = {
            'token_hash': 'expired-hash',
            'expires_at': expired_time,
            'user_id': 'expired-user'
        }
        session['reset_token_valid'] = {
            'token_hash': 'valid-hash',
            'expires_at': valid_time,
            'user_id': 'valid-user'
        }
        
        PasswordResetService.cleanup_expired_tokens()
        
        # Expired token should be removed
        assert 'reset_token_expired' not in session
        # Valid token should remain
        assert 'reset_token_valid' in session


class TestSessionCleanupService:
    """Test SessionCleanupService functionality."""
    
    def test_cleanup_expired_sessions(self, app_context):
        """Test cleanup of expired sessions."""
        result = SessionCleanupService.cleanup_expired_sessions()
        
        assert isinstance(result, int)
        assert result >= 0
    
    def test_get_active_sessions_count_authenticated(self, app_context):
        """Test getting active sessions count when user is authenticated."""
        with patch.object(SessionManager, 'is_user_authenticated', return_value=True):
            result = SessionCleanupService.get_active_sessions_count()
            
            assert result == 1
    
    def test_get_active_sessions_count_not_authenticated(self, app_context):
        """Test getting active sessions count when user is not authenticated."""
        with patch.object(SessionManager, 'is_user_authenticated', return_value=False):
            result = SessionCleanupService.get_active_sessions_count()
            
            assert result == 0