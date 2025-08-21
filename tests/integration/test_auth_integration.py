"""Integration tests for authentication system."""

import pytest
from flask import Flask
from flask_login import LoginManager

from online_poker.database import db, init_database
from online_poker.auth import init_login_manager
from online_poker.routes.auth_routes import auth_bp
from online_poker.services.user_manager import UserManager
from online_poker.services.auth_service import SessionManager


@pytest.fixture
def app():
    """Create test Flask app with full authentication setup."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Initialize database
    init_database(app)
    
    # Initialize Flask-Login
    init_login_manager(app)
    
    # Register auth routes
    app.register_blueprint(auth_bp)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        user = UserManager.create_user("testuser", "test@example.com", "password123")
        return user


class TestAuthenticationIntegration:
    """Test authentication system integration."""
    
    def test_user_registration_endpoint(self, client):
        """Test user registration through API endpoint."""
        response = client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'password123',
            'starting_bankroll': 1500
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['user']['username'] == 'newuser'
        assert data['user']['bankroll'] == 1500
    
    def test_user_registration_validation(self, client):
        """Test user registration validation."""
        response = client.post('/api/auth/register', json={
            'username': 'ab',  # Too short
            'email': 'invalid-email',
            'password': 'weak'  # Too weak
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
    
    def test_user_login_endpoint(self, client, test_user):
        """Test user login through API endpoint."""
        response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'password123',
            'remember_me': False
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['user']['username'] == 'testuser'
        assert 'session_token' in data
    
    def test_user_login_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials."""
        response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
    
    def test_user_logout_endpoint(self, client, test_user):
        """Test user logout through API endpoint."""
        # First login
        login_response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'password123'
        })
        assert login_response.status_code == 200
        
        # Then logout
        logout_response = client.post('/api/auth/logout')
        assert logout_response.status_code == 200
        
        data = logout_response.get_json()
        assert data['success'] is True
    
    def test_get_current_user_authenticated(self, client, test_user):
        """Test getting current user when authenticated."""
        # First login
        login_response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'password123'
        })
        assert login_response.status_code == 200
        
        # Get current user
        response = client.get('/api/auth/me')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert data['user']['user']['username'] == 'testuser'
    
    def test_get_current_user_not_authenticated(self, client):
        """Test getting current user when not authenticated."""
        response = client.get('/api/auth/me')
        assert response.status_code == 401
        
        data = response.get_json()
        assert data['success'] is False
    
    def test_check_authentication_endpoint(self, client, test_user):
        """Test authentication check endpoint."""
        # Check when not authenticated
        response = client.get('/api/auth/check-auth')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['is_authenticated'] is False
        
        # Login and check again
        client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'password123'
        })
        
        response = client.get('/api/auth/check-auth')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['is_authenticated'] is True
        assert data['user_id'] is not None
    
    def test_password_reset_flow(self, client, test_user):
        """Test password reset flow."""
        # Request reset token
        response = client.post('/api/auth/forgot-password', json={
            'email': 'test@example.com'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # In a real implementation, the token would be sent via email
        # For testing, we can extract it from the response
        if 'reset_token' in data:
            reset_token = data['reset_token']
            
            # Reset password
            reset_response = client.post('/api/auth/reset-password', json={
                'reset_token': reset_token,
                'new_password': 'newpassword123'
            })
            
            assert reset_response.status_code == 200
            reset_data = reset_response.get_json()
            assert reset_data['success'] is True
            
            # Verify old password no longer works
            old_login = client.post('/api/auth/login', json={
                'username': 'testuser',
                'password': 'password123'
            })
            assert old_login.status_code == 401
            
            # Verify new password works
            new_login = client.post('/api/auth/login', json={
                'username': 'testuser',
                'password': 'newpassword123'
            })
            assert new_login.status_code == 200
    
    def test_session_persistence(self, client, test_user):
        """Test that sessions persist across requests."""
        # Login
        login_response = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'password123'
        })
        assert login_response.status_code == 200
        
        # Make multiple requests to verify session persists
        for _ in range(3):
            response = client.get('/api/auth/me')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['success'] is True
            assert data['user']['user']['username'] == 'testuser'
    
    def test_duplicate_registration_prevention(self, client, test_user):
        """Test that duplicate usernames/emails are prevented."""
        # Try to register with existing username
        response = client.post('/api/auth/register', json={
            'username': 'testuser',  # Already exists
            'email': 'different@example.com',
            'password': 'password123'
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'already exists' in data['message'].lower()
        
        # Try to register with existing email
        response = client.post('/api/auth/register', json={
            'username': 'differentuser',
            'email': 'test@example.com',  # Already exists
            'password': 'password123'
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'already exists' in data['message'].lower()