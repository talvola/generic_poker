"""Authentication routes for the online poker platform."""

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import limiter
from ..services.auth_service import AuthenticationError, PasswordResetService, SessionManager
from ..services.user_manager import UserManager, UserValidationError

auth_bp = Blueprint("auth", __name__)


# HTML Routes for login/logout
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH_LOGIN"], methods=["POST"])
def login():
    """HTML login page and form handler."""
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username and password:
            try:
                # Try to authenticate user
                user = UserManager.authenticate_user(username, password)
                if user:
                    login_user(user, remember=True)
                    next_page = request.args.get("next")
                    return redirect(next_page) if next_page else redirect(url_for("lobby.index"))
                else:
                    flash("Invalid username or password", "error")
            except Exception:
                flash("Login failed. Please try again.", "error")
        else:
            flash("Please enter both username and password", "error")

    return render_template("auth/login.html", username=username)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH_REGISTER"], methods=["POST"])
def register_page():
    """HTML registration page and form handler."""
    username = ""
    email = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([username, email, password, confirm_password]):
            flash("All fields are required", "error")
        elif password != confirm_password:
            flash("Passwords do not match", "error")
        else:
            try:
                user = UserManager.create_user(username, email, password)
                login_user(user, remember=True)
                flash("Account created successfully!", "success")
                return redirect(url_for("lobby.index"))
            except UserValidationError as e:
                flash(str(e), "error")
            except Exception:
                flash("Registration failed. Please try again.", "error")

    return render_template("auth/register.html", username=username, email=email)


@auth_bp.route("/logout")
@login_required
def logout():
    """HTML logout handler."""
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


# API Routes
@auth_bp.route("/api/register", methods=["POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH_REGISTER"])
def api_register():
    """Register a new user account."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        starting_bankroll = data.get("starting_bankroll", 1000)

        # Create user
        user = UserManager.create_user(username, email, password, starting_bankroll)

        return jsonify({"success": True, "message": "Account created successfully", "user": user.to_dict()}), 201

    except UserValidationError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Registration error: {e}")
        return jsonify({"success": False, "message": "Registration failed"}), 500


@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH_LOGIN"])
def api_login():
    """Login user and create session."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        username = data.get("username", "").strip()
        password = data.get("password", "")
        remember_me = data.get("remember_me", False)

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400

        # Authenticate and create session
        result = SessionManager.login_user_session(username, password, remember_me)

        return jsonify(result), 200 if result["success"] else 401

    except AuthenticationError as e:
        return jsonify({"success": False, "message": str(e)}), 401
    except Exception as e:
        current_app.logger.error(f"Login error: {e}")
        return jsonify({"success": False, "message": "Login failed"}), 500


@auth_bp.route("/api/logout", methods=["POST"])
def api_logout():
    """Logout user and clear session."""
    try:
        result = SessionManager.logout_user_session()
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Logout error: {e}")
        return jsonify({"success": False, "message": "Logout failed"}), 500


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    """Get current authenticated user information."""
    try:
        user_info = SessionManager.get_current_user_info()

        if user_info:
            return jsonify({"success": True, "user": user_info}), 200
        else:
            return jsonify({"success": False, "message": "Not authenticated"}), 401

    except Exception as e:
        current_app.logger.error(f"Get current user error: {e}")
        return jsonify({"success": False, "message": "Failed to get user info"}), 500


@auth_bp.route("/refresh", methods=["POST"])
def refresh_session():
    """Refresh current user session."""
    try:
        success = SessionManager.refresh_session()

        if success:
            return jsonify({"success": True, "message": "Session refreshed"}), 200
        else:
            return jsonify({"success": False, "message": "Session refresh failed"}), 401

    except Exception as e:
        current_app.logger.error(f"Session refresh error: {e}")
        return jsonify({"success": False, "message": "Session refresh failed"}), 500


@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_AUTH_RESET"])
def forgot_password():
    """Request password reset token."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        email = data.get("email", "").strip()
        if not email:
            return jsonify({"success": False, "message": "Email required"}), 400

        result = PasswordResetService.generate_reset_token(email)
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Forgot password error: {e}")
        return jsonify({"success": False, "message": "Failed to process request"}), 500


@auth_bp.route("/reset-password", methods=["POST"])
@limiter.limit("5/hour")
def reset_password():
    """Reset password using reset token."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        reset_token = data.get("reset_token", "")
        new_password = data.get("new_password", "")

        if not reset_token or not new_password:
            return jsonify({"success": False, "message": "Reset token and new password required"}), 400

        result = PasswordResetService.reset_password(reset_token, new_password)
        return jsonify(result), 200 if result["success"] else 400

    except Exception as e:
        current_app.logger.error(f"Reset password error: {e}")
        return jsonify({"success": False, "message": "Failed to reset password"}), 500


@auth_bp.route("/check-auth", methods=["GET"])
def check_authentication():
    """Check if user is authenticated."""
    try:
        is_authenticated = SessionManager.is_user_authenticated()

        return jsonify(
            {
                "success": True,
                "is_authenticated": is_authenticated,
                "user_id": current_user.id if is_authenticated else None,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Check auth error: {e}")
        return jsonify({"success": False, "message": "Failed to check authentication"}), 500


@auth_bp.route("/validate-session", methods=["POST"])
def validate_session():
    """Validate current session and return user info if valid."""
    try:
        auth_error = SessionManager.require_authentication()
        if auth_error:
            return jsonify(auth_error), 401

        user_info = SessionManager.get_current_user_info()
        return jsonify({"success": True, "valid": True, "user": user_info}), 200

    except Exception as e:
        current_app.logger.error(f"Validate session error: {e}")
        return jsonify({"success": False, "message": "Session validation failed"}), 500


# Error handlers for the auth blueprint
@auth_bp.errorhandler(400)
def bad_request(error):
    """Handle bad request errors."""
    return jsonify({"success": False, "message": "Bad request"}), 400


@auth_bp.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized errors."""
    return jsonify({"success": False, "message": "Unauthorized"}), 401


@auth_bp.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    return jsonify({"success": False, "message": "Internal server error"}), 500
