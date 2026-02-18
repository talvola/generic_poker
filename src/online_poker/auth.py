"""Flask-Login integration for the online poker platform."""

from flask_login import LoginManager

from .services.user_manager import UserManager


def init_login_manager(app):
    """Initialize Flask-Login with the Flask app."""
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        return UserManager.get_user_by_id(user_id)

    return login_manager
