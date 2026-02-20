"""Integration tests for admin routes.

Tests admin access control, dashboard stats, user management,
table management, and variant management.
"""

import os

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool

from online_poker.auth import init_login_manager
from online_poker.database import db
from online_poker.models.table import PokerTable
from online_poker.models.transaction import Transaction
from online_poker.models.user import User
from online_poker.routes.admin_routes import admin_bp
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.lobby_routes import lobby_bp

# Project root for template/static resolution
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    db.init_app(app)
    init_login_manager(app)

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(lobby_bp, url_prefix="/")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin_user(app):
    """Create an admin user."""
    user = User(username="admin", email="admin@test.com", password="password", bankroll=1000)
    user.is_admin = True
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def regular_user(app):
    """Create a regular user."""
    user = User(username="regular", email="regular@test.com", password="password", bankroll=500)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def login(client, username, password="password"):
    """Log in a user via the auth API."""
    return client.post(
        "/auth/api/login",
        json={"username": username, "password": password},
    )


# --- Access control tests ---


class TestAdminAccessControl:
    """Test that admin routes are properly protected."""

    def test_unauthenticated_redirects_page_routes(self, client, admin_user):
        """Unauthenticated users are redirected on page routes."""
        for path in ["/admin/", "/admin/users", "/admin/tables", "/admin/variants"]:
            resp = client.get(path)
            assert resp.status_code in (302, 308), f"{path} should redirect"

    def test_unauthenticated_redirects_api_routes(self, client, admin_user):
        """Unauthenticated users are redirected on API routes."""
        resp = client.get("/admin/api/stats")
        assert resp.status_code in (302, 308)

    def test_non_admin_redirected_from_page_routes(self, client, regular_user):
        """Non-admin users are redirected from page routes."""
        login(client, "regular")
        resp = client.get("/admin/", follow_redirects=False)
        assert resp.status_code == 302

    def test_non_admin_gets_403_on_api_routes(self, client, regular_user):
        """Non-admin users get 403 on API routes."""
        login(client, "regular")
        resp = client.get("/admin/api/stats")
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False

    def test_admin_can_access_dashboard(self, client, admin_user):
        """Admin users can access the dashboard."""
        login(client, "admin")
        resp = client.get("/admin/")
        assert resp.status_code == 200

    def test_admin_can_access_all_pages(self, client, admin_user):
        """Admin users can access all admin pages."""
        login(client, "admin")
        for path in ["/admin/", "/admin/users", "/admin/tables", "/admin/variants"]:
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} should return 200"


# --- Dashboard stats tests ---


class TestDashboardStats:
    """Test dashboard statistics API."""

    def test_stats_returns_expected_fields(self, client, admin_user, regular_user):
        """Stats API returns all expected fields."""
        login(client, "admin")
        resp = client.get("/admin/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

        stats = data["stats"]
        assert stats["total_users"] == 2  # admin + regular
        assert "active_users_7d" in stats
        assert "total_bankroll" in stats
        assert "total_tables" in stats
        assert "hands_today" in stats
        assert "hands_week" in stats
        assert "disabled_variants" in stats
        assert "live_sessions" in stats

    def test_sessions_api(self, client, admin_user):
        """Sessions API returns a list."""
        login(client, "admin")
        resp = client.get("/admin/api/sessions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["sessions"], list)


# --- User management tests ---


class TestUserManagement:
    """Test user management API."""

    def test_list_users(self, client, admin_user, regular_user):
        """User list returns all users."""
        login(client, "admin")
        resp = client.get("/admin/api/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["total"] == 2

    def test_search_users(self, client, admin_user, regular_user):
        """User search filters by username/email."""
        login(client, "admin")
        resp = client.get("/admin/api/users?search=regular")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["users"][0]["username"] == "regular"

    def test_user_detail(self, client, admin_user, regular_user):
        """User detail returns user info."""
        login(client, "admin")
        resp = client.get(f"/admin/api/users/{regular_user.id}")
        data = resp.get_json()
        assert data["success"] is True
        assert data["user"]["username"] == "regular"

    def test_user_detail_not_found(self, client, admin_user):
        """User detail returns 404 for unknown user."""
        login(client, "admin")
        resp = client.get("/admin/api/users/nonexistent-id")
        assert resp.status_code == 404

    def test_adjust_bankroll(self, client, admin_user, regular_user):
        """Bankroll adjustment updates user and creates transaction."""
        login(client, "admin")
        resp = client.post(
            f"/admin/api/users/{regular_user.id}/bankroll",
            json={"amount": 200, "reason": "Test bonus"},
        )
        data = resp.get_json()
        assert data["success"] is True
        assert data["old_bankroll"] == 500
        assert data["new_bankroll"] == 700

        # Verify transaction was created
        txn = Transaction.query.filter_by(user_id=regular_user.id).first()
        assert txn is not None
        assert txn.amount == 200
        assert txn.transaction_type == Transaction.TYPE_ADJUSTMENT
        assert "Test bonus" in txn.description

    def test_adjust_bankroll_negative(self, client, admin_user, regular_user):
        """Bankroll adjustment rejects negative result."""
        login(client, "admin")
        resp = client.post(
            f"/admin/api/users/{regular_user.id}/bankroll",
            json={"amount": -600},
        )
        data = resp.get_json()
        assert data["success"] is False

    def test_adjust_bankroll_missing_amount(self, client, admin_user, regular_user):
        """Bankroll adjustment requires amount."""
        login(client, "admin")
        resp = client.post(
            f"/admin/api/users/{regular_user.id}/bankroll",
            json={"reason": "No amount"},
        )
        assert resp.status_code == 400

    def test_toggle_user_active(self, client, admin_user, regular_user):
        """Toggle user active status."""
        login(client, "admin")
        resp = client.post(f"/admin/api/users/{regular_user.id}/toggle-active")
        data = resp.get_json()
        assert data["success"] is True
        assert data["is_active"] is False

        # Toggle back
        resp = client.post(f"/admin/api/users/{regular_user.id}/toggle-active")
        data = resp.get_json()
        assert data["is_active"] is True

    def test_cannot_deactivate_self(self, client, admin_user):
        """Admin cannot deactivate their own account."""
        login(client, "admin")
        resp = client.post(f"/admin/api/users/{admin_user.id}/toggle-active")
        data = resp.get_json()
        assert data["success"] is False


# --- Table management tests ---


class TestTableManagement:
    """Test table management API."""

    def test_list_tables(self, client, admin_user):
        """Tables API returns all tables."""
        login(client, "admin")

        # Create a table
        table = PokerTable(
            name="Test Table",
            variant="hold_em",
            betting_structure="no-limit",
            stakes={"small_blind": 1, "big_blind": 2},
            max_players=6,
            creator_id=admin_user.id,
        )
        db.session.add(table)
        db.session.commit()

        resp = client.get("/admin/api/tables")
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["tables"]) == 1
        assert data["tables"][0]["name"] == "Test Table"
        assert data["tables"][0]["creator_username"] == "admin"

    def test_close_table(self, client, admin_user):
        """Force-closing a table works."""
        login(client, "admin")

        table = PokerTable(
            name="Close Me",
            variant="hold_em",
            betting_structure="no-limit",
            stakes={"small_blind": 1, "big_blind": 2},
            max_players=6,
            creator_id=admin_user.id,
        )
        db.session.add(table)
        db.session.commit()
        table_id = table.id

        resp = client.post(f"/admin/api/tables/{table_id}/close")
        data = resp.get_json()
        assert data["success"] is True

    def test_close_nonexistent_table(self, client, admin_user):
        """Closing a nonexistent table returns 404."""
        login(client, "admin")
        resp = client.post("/admin/api/tables/nonexistent-id/close")
        assert resp.status_code == 404


# --- Variant management tests ---


class TestVariantManagement:
    """Test variant management API."""

    def test_list_variants(self, client, admin_user):
        """Variants API returns a list of variants."""
        login(client, "admin")
        resp = client.get("/admin/api/variants")
        data = resp.get_json()
        assert data["success"] is True
        assert data["total"] > 0
        # All should be enabled by default
        assert all(not v["disabled"] for v in data["variants"])

    def test_disable_and_enable_variant(self, client, admin_user):
        """Disable and re-enable a variant."""
        login(client, "admin")

        # Disable
        resp = client.post(
            "/admin/api/variants/hold_em/disable",
            json={"reason": "Testing"},
        )
        data = resp.get_json()
        assert data["success"] is True

        # Verify disabled in list
        resp = client.get("/admin/api/variants")
        data = resp.get_json()
        hold_em = next(v for v in data["variants"] if v["name"] == "hold_em")
        assert hold_em["disabled"] is True
        assert hold_em["disabled_info"]["reason"] == "Testing"

        # Re-enable
        resp = client.post("/admin/api/variants/hold_em/enable")
        data = resp.get_json()
        assert data["success"] is True

        # Verify enabled
        resp = client.get("/admin/api/variants")
        data = resp.get_json()
        hold_em = next(v for v in data["variants"] if v["name"] == "hold_em")
        assert hold_em["disabled"] is False

    def test_disable_already_disabled(self, client, admin_user):
        """Disabling an already disabled variant returns 400."""
        login(client, "admin")
        client.post("/admin/api/variants/hold_em/disable", json={})
        resp = client.post("/admin/api/variants/hold_em/disable", json={})
        assert resp.status_code == 400

    def test_enable_not_disabled(self, client, admin_user):
        """Enabling a variant that isn't disabled returns 400."""
        login(client, "admin")
        resp = client.post("/admin/api/variants/hold_em/enable")
        assert resp.status_code == 400

    def test_disabled_variant_filtered_from_available(self, client, admin_user):
        """Disabled variants are filtered from get_available_variants()."""
        login(client, "admin")

        # Get initial count
        from online_poker.services.table_manager import TableManager

        initial_variants = TableManager.get_available_variants()
        initial_count = len(initial_variants)
        assert any(v["name"] == "hold_em" for v in initial_variants)

        # Disable hold_em
        client.post("/admin/api/variants/hold_em/disable", json={"reason": "Test"})

        # Verify filtered
        filtered_variants = TableManager.get_available_variants()
        assert len(filtered_variants) == initial_count - 1
        assert not any(v["name"] == "hold_em" for v in filtered_variants)

        # Re-enable
        client.post("/admin/api/variants/hold_em/enable")
        restored_variants = TableManager.get_available_variants()
        assert len(restored_variants) == initial_count
