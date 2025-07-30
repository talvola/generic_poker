"""Unit tests for UserManager service."""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from sqlalchemy.exc import IntegrityError

from src.online_poker.services.user_manager import UserManager, UserValidationError
from src.online_poker.models.user import User
from src.online_poker.database import db


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.app_context():
        db.init_app(app)
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def app_context(app):
    """Create app context for tests."""
    with app.app_context():
        yield


class TestUserValidation:
    """Test user validation methods."""
    
    def test_validate_username_valid(self, app_context):
        """Test valid username validation."""
        # Should not raise exception
        UserManager.validate_username("valid_user123")
    
    def test_validate_username_empty(self, app_context):
        """Test empty username validation."""
        with pytest.raises(UserValidationError, match="Username is required"):
            UserManager.validate_username("")
    
    def test_validate_username_too_short(self, app_context):
        """Test username too short validation."""
        with pytest.raises(UserValidationError, match="at least 3 characters"):
            UserManager.validate_username("ab")
    
    def test_validate_username_too_long(self, app_context):
        """Test username too long validation."""
        long_username = "a" * 51
        with pytest.raises(UserValidationError, match="no more than 50 characters"):
            UserManager.validate_username(long_username)
    
    def test_validate_username_invalid_characters(self, app_context):
        """Test username with invalid characters."""
        with pytest.raises(UserValidationError, match="letters, numbers, and underscores"):
            UserManager.validate_username("user@name")
    
    def test_validate_username_already_exists(self, app_context):
        """Test username already exists validation."""
        # Create a user first
        user = User("existing_user", "test@example.com", "password123")
        db.session.add(user)
        db.session.commit()
        
        with pytest.raises(UserValidationError, match="Username already exists"):
            UserManager.validate_username("existing_user")
    
    def test_validate_email_valid(self, app_context):
        """Test valid email validation."""
        # Should not raise exception
        UserManager.validate_email("test@example.com")
    
    def test_validate_email_empty(self, app_context):
        """Test empty email validation."""
        with pytest.raises(UserValidationError, match="Email is required"):
            UserManager.validate_email("")
    
    def test_validate_email_invalid_format(self, app_context):
        """Test invalid email format validation."""
        with pytest.raises(UserValidationError, match="Invalid email format"):
            UserManager.validate_email("invalid-email")
    
    def test_validate_email_too_long(self, app_context):
        """Test email too long validation."""
        long_email = "a" * 110 + "@example.com"
        with pytest.raises(UserValidationError, match="no more than 120 characters"):
            UserManager.validate_email(long_email)
    
    def test_validate_email_already_exists(self, app_context):
        """Test email already exists validation."""
        # Create a user first
        user = User("test_user", "existing@example.com", "password123")
        db.session.add(user)
        db.session.commit()
        
        with pytest.raises(UserValidationError, match="Email already exists"):
            UserManager.validate_email("existing@example.com")
    
    def test_validate_password_valid(self, app_context):
        """Test valid password validation."""
        # Should not raise exception
        UserManager.validate_password("password123")
    
    def test_validate_password_empty(self, app_context):
        """Test empty password validation."""
        with pytest.raises(UserValidationError, match="Password is required"):
            UserManager.validate_password("")
    
    def test_validate_password_too_short(self, app_context):
        """Test password too short validation."""
        with pytest.raises(UserValidationError, match="at least 8 characters"):
            UserManager.validate_password("pass123")
    
    def test_validate_password_too_long(self, app_context):
        """Test password too long validation."""
        long_password = "a" * 129
        with pytest.raises(UserValidationError, match="no more than 128 characters"):
            UserManager.validate_password(long_password)
    
    def test_validate_password_no_letter(self, app_context):
        """Test password without letter validation."""
        with pytest.raises(UserValidationError, match="at least one letter"):
            UserManager.validate_password("12345678")
    
    def test_validate_password_no_number(self, app_context):
        """Test password without number validation."""
        with pytest.raises(UserValidationError, match="at least one number"):
            UserManager.validate_password("password")


class TestUserCreation:
    """Test user creation methods."""
    
    def test_create_user_success(self, app_context):
        """Test successful user creation."""
        user = UserManager.create_user("testuser", "test@example.com", "password123")
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.bankroll == 1000
        assert user.check_password("password123")
        assert user.is_active is True
        assert user.id is not None
    
    def test_create_user_custom_bankroll(self, app_context):
        """Test user creation with custom bankroll."""
        user = UserManager.create_user("testuser", "test@example.com", "password123", 2000)
        
        assert user.bankroll == 2000
    
    def test_create_user_negative_bankroll(self, app_context):
        """Test user creation with negative bankroll."""
        with pytest.raises(UserValidationError, match="Starting bankroll cannot be negative"):
            UserManager.create_user("testuser", "test@example.com", "password123", -100)
    
    def test_create_user_duplicate_username(self, app_context):
        """Test creating user with duplicate username."""
        # Create first user
        UserManager.create_user("testuser", "test1@example.com", "password123")
        
        # Try to create second user with same username
        with pytest.raises(UserValidationError, match="Username already exists"):
            UserManager.create_user("testuser", "test2@example.com", "password123")
    
    def test_create_user_duplicate_email(self, app_context):
        """Test creating user with duplicate email."""
        # Create first user
        UserManager.create_user("testuser1", "test@example.com", "password123")
        
        # Try to create second user with same email
        with pytest.raises(UserValidationError, match="Email already exists"):
            UserManager.create_user("testuser2", "test@example.com", "password123")


class TestUserAuthentication:
    """Test user authentication methods."""
    
    def test_authenticate_user_success_username(self, app_context):
        """Test successful authentication with username."""
        # Create user
        UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Authenticate
        user = UserManager.authenticate_user("testuser", "password123")
        
        assert user is not None
        assert user.username == "testuser"
        assert user.last_login is not None
    
    def test_authenticate_user_success_email(self, app_context):
        """Test successful authentication with email."""
        # Create user
        UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Authenticate with email
        user = UserManager.authenticate_user("test@example.com", "password123")
        
        assert user is not None
        assert user.username == "testuser"
    
    def test_authenticate_user_wrong_password(self, app_context):
        """Test authentication with wrong password."""
        # Create user
        UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Try wrong password
        user = UserManager.authenticate_user("testuser", "wrongpassword")
        
        assert user is None
    
    def test_authenticate_user_nonexistent(self, app_context):
        """Test authentication with nonexistent user."""
        user = UserManager.authenticate_user("nonexistent", "password123")
        
        assert user is None
    
    def test_authenticate_user_inactive(self, app_context):
        """Test authentication with inactive user."""
        # Create and deactivate user
        created_user = UserManager.create_user("testuser", "test@example.com", "password123")
        created_user.is_active = False
        db.session.commit()
        
        # Try to authenticate
        user = UserManager.authenticate_user("testuser", "password123")
        
        assert user is None
    
    def test_authenticate_user_empty_credentials(self, app_context):
        """Test authentication with empty credentials."""
        assert UserManager.authenticate_user("", "password") is None
        assert UserManager.authenticate_user("username", "") is None
        assert UserManager.authenticate_user("", "") is None


class TestUserRetrieval:
    """Test user retrieval methods."""
    
    def test_get_user_by_id_success(self, app_context):
        """Test successful user retrieval by ID."""
        # Create user
        created_user = UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Retrieve user
        user = UserManager.get_user_by_id(created_user.id)
        
        assert user is not None
        assert user.id == created_user.id
        assert user.username == "testuser"
    
    def test_get_user_by_id_nonexistent(self, app_context):
        """Test user retrieval with nonexistent ID."""
        user = UserManager.get_user_by_id("nonexistent-id")
        
        assert user is None
    
    def test_get_user_by_username_success(self, app_context):
        """Test successful user retrieval by username."""
        # Create user
        UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Retrieve user
        user = UserManager.get_user_by_username("testuser")
        
        assert user is not None
        assert user.username == "testuser"
    
    def test_get_user_by_email_success(self, app_context):
        """Test successful user retrieval by email."""
        # Create user
        UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Retrieve user
        user = UserManager.get_user_by_email("test@example.com")
        
        assert user is not None
        assert user.email == "test@example.com"


class TestBankrollManagement:
    """Test bankroll management methods."""
    
    def test_update_user_bankroll_success(self, app_context):
        """Test successful bankroll update."""
        # Create user
        user = UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Update bankroll
        success = UserManager.update_user_bankroll(user.id, 500)
        
        assert success is True
        
        # Verify update
        updated_user = UserManager.get_user_by_id(user.id)
        assert updated_user.bankroll == 1500
    
    def test_update_user_bankroll_insufficient_funds(self, app_context):
        """Test bankroll update with insufficient funds."""
        # Create user
        user = UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Try to subtract more than available
        success = UserManager.update_user_bankroll(user.id, -2000)
        
        assert success is False
        
        # Verify bankroll unchanged
        updated_user = UserManager.get_user_by_id(user.id)
        assert updated_user.bankroll == 1000
    
    def test_update_user_bankroll_nonexistent_user(self, app_context):
        """Test bankroll update for nonexistent user."""
        success = UserManager.update_user_bankroll("nonexistent-id", 500)
        
        assert success is False


class TestUserStatistics:
    """Test user statistics methods."""
    
    def test_get_user_statistics_success(self, app_context):
        """Test successful user statistics retrieval."""
        # Create user
        user = UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Get statistics
        stats = UserManager.get_user_statistics(user.id)
        
        assert stats['username'] == "testuser"
        assert stats['bankroll'] == 1000
        assert stats['member_since'] is not None
        assert stats['total_tables_created'] == 0
        assert stats['total_transactions'] == 0
    
    def test_get_user_statistics_nonexistent_user(self, app_context):
        """Test statistics retrieval for nonexistent user."""
        stats = UserManager.get_user_statistics("nonexistent-id")
        
        assert stats == {}


class TestUserDeactivation:
    """Test user deactivation methods."""
    
    def test_deactivate_user_success(self, app_context):
        """Test successful user deactivation."""
        # Create user
        user = UserManager.create_user("testuser", "test@example.com", "password123")
        
        # Deactivate user
        success = UserManager.deactivate_user(user.id)
        
        assert success is True
        
        # Verify deactivation
        updated_user = User.query.filter_by(id=user.id).first()
        assert updated_user.is_active is False
    
    def test_deactivate_user_nonexistent(self, app_context):
        """Test deactivation of nonexistent user."""
        success = UserManager.deactivate_user("nonexistent-id")
        
        assert success is False