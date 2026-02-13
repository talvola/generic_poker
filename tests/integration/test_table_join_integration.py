"""Integration tests for table joining functionality.

These tests verify the table joining flows including:
- Public table joining
- Private table joining with invite codes
- Buy-in amount handling
- Seat selection
"""

import pytest
from flask import Flask
from flask_login import LoginManager

from online_poker.database import db, init_database
from online_poker.auth import init_login_manager
from online_poker.routes.auth_routes import auth_bp
from online_poker.routes.lobby_routes import lobby_bp
from online_poker.services.user_manager import UserManager
from online_poker.services.table_manager import TableManager
from online_poker.models.table_config import TableConfig
from generic_poker.game.betting import BettingStructure


@pytest.fixture
def app():
    """Create test Flask app with full setup."""
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

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(lobby_bp)

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
    """Create a test user with sufficient bankroll."""
    with app.app_context():
        user = UserManager.create_user("testuser", "test@example.com", "password123")
        UserManager.update_user_bankroll(user.id, 1000)  # Give user $1000
        return user


@pytest.fixture
def second_user(app):
    """Create a second test user."""
    with app.app_context():
        user = UserManager.create_user("alice", "alice@example.com", "password123")
        UserManager.update_user_bankroll(user.id, 1000)
        return user


@pytest.fixture
def logged_in_client(client, test_user):
    """Return a client that is logged in as test_user."""
    client.post('/auth/api/login', json={
        'username': 'testuser',
        'password': 'password123'
    })
    return client


@pytest.fixture
def public_table(app, test_user):
    """Create a public poker table."""
    with app.app_context():
        table_manager = TableManager()
        config = TableConfig(
            name="Test Public Table",
            variant="hold_em",
            betting_structure=BettingStructure.NO_LIMIT,
            stakes={'small_blind': 1, 'big_blind': 2},
            max_players=6,
            is_private=False,
            allow_bots=False
        )
        table = table_manager.create_table(test_user.id, config)
        return table


@pytest.fixture
def private_table(app, test_user):
    """Create a private poker table with invite code."""
    with app.app_context():
        table_manager = TableManager()
        config = TableConfig(
            name="Test Private Table",
            variant="hold_em",
            betting_structure=BettingStructure.NO_LIMIT,
            stakes={'small_blind': 1, 'big_blind': 2},
            max_players=6,
            is_private=True,
            allow_bots=False
        )
        table = table_manager.create_table(test_user.id, config)
        return table


class TestPublicTableJoining:
    """Test public table joining functionality."""

    def test_join_public_table_success(self, logged_in_client, public_table, app):
        """Test successfully joining a public table."""
        with app.app_context():
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={}
            )

            assert response.status_code == 200, f"Response: {response.get_json()}"
            data = response.get_json()
            assert data['success'] is True
            assert data['table_id'] == public_table.id

    def test_join_table_requires_authentication(self, client, public_table, app):
        """Test that joining a table requires authentication."""
        with app.app_context():
            response = client.post(
                f'/api/tables/{public_table.id}/join',
                json={}
            )

            # Should redirect to login or return 401
            assert response.status_code in [401, 302]

    def test_join_nonexistent_table(self, logged_in_client):
        """Test joining a table that doesn't exist."""
        response = logged_in_client.post(
            '/api/tables/nonexistent-id/join',
            json={}
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()

    def test_join_table_deducts_bankroll(self, logged_in_client, public_table, app):
        """Test that joining a table deducts from user bankroll."""
        with app.app_context():
            # Get initial bankroll
            from online_poker.services.user_manager import UserManager
            initial_bankroll = UserManager.get_user_by_username('testuser').bankroll

            # Join table
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={}
            )
            assert response.status_code == 200, f"Response: {response.get_json()}"

            # Check bankroll was deducted
            db.session.expire_all()
            final_bankroll = UserManager.get_user_by_username('testuser').bankroll

            # Should have deducted at least minimum buy-in
            assert final_bankroll < initial_bankroll


class TestPrivateTableJoining:
    """Test private table joining with invite codes."""

    def test_join_private_table_with_valid_invite_code(self, app, private_table, second_user):
        """Test joining a private table with valid invite code."""
        with app.app_context():
            # Get invite code
            from online_poker.models.table import PokerTable
            table = db.session.get(PokerTable, private_table.id)
            invite_code = table.invite_code
            table_id = private_table.id

            # Verify the table exists and has an invite code
            assert invite_code is not None, "Table should have an invite code"
            assert table.is_private == True, "Table should be private"

            # Create a new client and login as second user
            client = app.test_client()
            login_response = client.post('/auth/api/login', json={
                'username': 'alice',
                'password': 'password123'
            })
            assert login_response.status_code == 200, "Login should succeed"

            # Try to join with invite code
            response = client.post('/api/tables/private/join', json={
                'invite_code': invite_code
            })

            # Debug: print response data if it fails
            data = response.get_json()
            if response.status_code != 200:
                print(f"DEBUG: Response status: {response.status_code}")
                print(f"DEBUG: Response data: {data}")
                print(f"DEBUG: Invite code used: {invite_code}")
                print(f"DEBUG: Table ID: {table_id}")

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {data}"
            assert data['success'] is True
            assert data['table_id'] == table_id

    def test_join_private_table_with_invalid_invite_code(self, logged_in_client):
        """Test joining a private table with invalid invite code."""
        response = logged_in_client.post('/api/tables/private/join', json={
            'invite_code': 'INVALID1'
        })

        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'invalid' in data['error'].lower()

    def test_join_private_table_without_invite_code(self, logged_in_client):
        """Test joining a private table without providing invite code."""
        response = logged_in_client.post('/api/tables/private/join', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'invite code required' in data['error'].lower()

    def test_cannot_join_private_table_via_public_endpoint(self, logged_in_client, private_table, app):
        """Test that private tables cannot be joined via public endpoint."""
        with app.app_context():
            response = logged_in_client.post(
                f'/api/tables/{private_table.id}/join',
                json={}
            )

            assert response.status_code == 403
            data = response.get_json()
            assert data['success'] is False
            assert 'private' in data['error'].lower()


class TestBuyInHandling:
    """Test buy-in amount handling."""

    def test_custom_buyin_amount_is_applied(self, logged_in_client, public_table, app):
        """Test that custom buy-in amount is used when specified."""
        with app.app_context():
            from online_poker.models.table import PokerTable
            from online_poker.services.user_manager import UserManager
            from online_poker.models.table_access import TableAccess

            table = db.session.get(PokerTable, public_table.id)
            custom_buyin = 100  # Custom amount within range

            initial_bankroll = UserManager.get_user_by_username('testuser').bankroll

            # Join with custom buy-in amount
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={'buy_in_amount': custom_buyin}
            )
            assert response.status_code == 200

            db.session.expire_all()
            final_bankroll = UserManager.get_user_by_username('testuser').bankroll

            # Bankroll should be reduced by exactly the custom buy-in
            assert initial_bankroll - final_bankroll == custom_buyin

            # Player's stack at table should be the custom buy-in
            access = db.session.query(TableAccess).filter(
                TableAccess.table_id == public_table.id,
                TableAccess.is_active == True,
                TableAccess.is_spectator == False
            ).first()
            assert access is not None
            assert access.buy_in_amount == custom_buyin

    def test_buyin_below_minimum_rejected(self, logged_in_client, public_table, app):
        """Test that buy-in below minimum is rejected."""
        with app.app_context():
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={'buy_in_amount': 10}  # Below minimum of 40
            )
            assert response.status_code == 400
            data = response.get_json()
            assert 'at least' in data['error'].lower()

    def test_buyin_above_maximum_rejected(self, logged_in_client, public_table, app):
        """Test that buy-in above maximum is rejected."""
        with app.app_context():
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={'buy_in_amount': 500}  # Above maximum of 200
            )
            assert response.status_code == 400
            data = response.get_json()
            assert 'exceed' in data['error'].lower()

    def test_minimum_buyin_is_applied(self, logged_in_client, public_table, app):
        """Test that at least minimum buy-in is applied when no amount specified."""
        with app.app_context():
            from online_poker.models.table import PokerTable
            from online_poker.services.user_manager import UserManager

            table = db.session.get(PokerTable, public_table.id)
            min_buyin = table.get_minimum_buyin()

            initial_bankroll = UserManager.get_user_by_username('testuser').bankroll

            # Send empty JSON body (no buy_in_amount specified)
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={}
            )
            assert response.status_code == 200, f"Response: {response.get_json()}"

            db.session.expire_all()
            final_bankroll = UserManager.get_user_by_username('testuser').bankroll

            # Bankroll should be reduced by at least minimum buy-in
            assert initial_bankroll - final_bankroll >= min_buyin

    def test_insufficient_bankroll_rejected(self, app, public_table):
        """Test that joining with insufficient bankroll is rejected."""
        with app.app_context():
            # Create a poor user with low bankroll
            # Default bankroll is $1000, so subtract $990 to get to $10
            poor_user = UserManager.create_user("pooruser", "poor@example.com", "password123")
            UserManager.update_user_bankroll(poor_user.id, -990)  # Reduce to $10

            # Verify bankroll is set correctly
            db.session.expire_all()
            poor_user = UserManager.get_user_by_username("pooruser")
            assert poor_user.bankroll == 10, f"Expected $10 but got ${poor_user.bankroll}"

            client = app.test_client()
            client.post('/auth/api/login', json={
                'username': 'pooruser',
                'password': 'password123'
            })

            response = client.post(
                f'/api/tables/{public_table.id}/join',
                json={}
            )

            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'insufficient' in data['error'].lower()


class TestSeatSelection:
    """Test seat selection during table join."""

    def test_specific_seat_selection(self, logged_in_client, public_table, app):
        """Test that a specific seat can be requested and used."""
        with app.app_context():
            from online_poker.models.table_access import TableAccess

            # Join with specific seat number
            requested_seat = 3
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={'seat_number': requested_seat}
            )

            assert response.status_code == 200, f"Response: {response.get_json()}"

            # Verify player is in the requested seat
            db.session.expire_all()
            access = db.session.query(TableAccess).filter(
                TableAccess.table_id == public_table.id,
                TableAccess.is_active == True,
                TableAccess.is_spectator == False
            ).first()

            assert access is not None
            assert access.seat_number == requested_seat

    def test_invalid_seat_number_rejected(self, logged_in_client, public_table, app):
        """Test that invalid seat numbers are rejected."""
        with app.app_context():
            # Try to join with seat 0 (invalid)
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={'seat_number': 0}
            )
            assert response.status_code == 400
            assert 'invalid seat' in response.get_json()['error'].lower()

            # Try to join with seat > max_players
            response = logged_in_client.post(
                f'/api/tables/{public_table.id}/join',
                json={'seat_number': 10}  # max_players is 6
            )
            assert response.status_code == 400
            assert 'invalid seat' in response.get_json()['error'].lower()

    def test_occupied_seat_rejected(self, app, public_table, test_user, second_user):
        """Test that occupied seats cannot be requested."""
        with app.app_context():
            # First user joins at seat 3
            client1 = app.test_client()
            client1.post('/auth/api/login', json={
                'username': 'testuser',
                'password': 'password123'
            })
            response = client1.post(
                f'/api/tables/{public_table.id}/join',
                json={'seat_number': 3}
            )
            assert response.status_code == 200

            # Second user tries to join at same seat
            client2 = app.test_client()
            client2.post('/auth/api/login', json={
                'username': 'alice',
                'password': 'password123'
            })
            response = client2.post(
                f'/api/tables/{public_table.id}/join',
                json={'seat_number': 3}
            )
            assert response.status_code == 400
            assert 'occupied' in response.get_json()['error'].lower()

    def test_get_available_seats(self, logged_in_client, public_table, app):
        """Test getting available seats for a table."""
        with app.app_context():
            response = logged_in_client.get(f'/api/tables/{public_table.id}/seats')

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert 'seats' in data
            assert len(data['seats']) == 6  # max_players

            # All seats should be available initially
            for seat in data['seats']:
                assert seat['is_available'] is True


class TestTableListFiltering:
    """Test table listing and filtering."""

    def test_get_public_tables_list(self, client, public_table, private_table, app):
        """Test that public tables are listed but private tables are not."""
        with app.app_context():
            response = client.get('/api/tables')

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True

            # Should only include public table
            table_ids = [t['id'] for t in data['tables']]
            assert public_table.id in table_ids
            assert private_table.id not in table_ids

    def test_table_list_includes_correct_info(self, client, public_table, app):
        """Test that table list includes all required information."""
        with app.app_context():
            response = client.get('/api/tables')

            assert response.status_code == 200
            data = response.get_json()

            # Find our table
            our_table = next(t for t in data['tables'] if t['id'] == public_table.id)

            # Verify required fields
            assert 'name' in our_table
            assert 'variant' in our_table
            assert 'betting_structure' in our_table
            assert 'stakes' in our_table
            assert 'max_players' in our_table
            assert 'current_players' in our_table
            assert 'is_private' in our_table
            assert our_table['is_private'] is False


class TestSpectatorMode:
    """Test spectator mode functionality."""

    def test_spectate_public_table(self, logged_in_client, public_table, app):
        """Test joining a public table as spectator."""
        with app.app_context():
            response = logged_in_client.post(f'/api/tables/{public_table.id}/spectate')

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True

    def test_spectate_does_not_deduct_bankroll(self, logged_in_client, public_table, app):
        """Test that spectating doesn't deduct from bankroll."""
        with app.app_context():
            from online_poker.services.user_manager import UserManager

            initial_bankroll = UserManager.get_user_by_username('testuser').bankroll

            response = logged_in_client.post(f'/api/tables/{public_table.id}/spectate')
            assert response.status_code == 200

            db.session.expire_all()
            final_bankroll = UserManager.get_user_by_username('testuser').bankroll

            # Bankroll should be unchanged
            assert final_bankroll == initial_bankroll

    def test_cannot_spectate_private_table_without_invite(self, logged_in_client, private_table, app):
        """Test that private tables cannot be spectated without invite."""
        with app.app_context():
            response = logged_in_client.post(f'/api/tables/{private_table.id}/spectate')

            assert response.status_code == 403
            data = response.get_json()
            assert data['success'] is False
