"""Unit tests for table lifecycle management functionality."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from flask import Flask

from src.online_poker.services.table_manager import TableManager, TableValidationError
from src.online_poker.services.table_access_manager import TableAccessManager
from src.online_poker.models.table import PokerTable
from src.online_poker.models.table_access import TableAccess
from src.online_poker.models.user import User
from src.online_poker.database import db
from generic_poker.game.betting import BettingStructure


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


@pytest.fixture
def test_user(app_context):
    """Create a test user."""
    from src.online_poker.services.user_manager import UserManager
    user = UserManager.create_user("testuser", "test@example.com", "password123", 1000)
    return user


@pytest.fixture
def test_table(app_context, test_user):
    """Create a test table."""
    table = PokerTable(
        name="Test Table",
        variant="hold_em",
        betting_structure=BettingStructure.NO_LIMIT.value,
        stakes={"small_blind": 1, "big_blind": 2},
        max_players=6,
        creator_id=test_user.id,
        is_private=False
    )
    db.session.add(table)
    db.session.commit()
    return table


class TestTableLifecycleManagement:
    """Test table lifecycle management functionality."""
    
    def test_hand_in_progress_detection_no_players(self, app_context, test_table):
        """Test hand detection with no players."""
        # Table with no access records should not have hand in progress
        in_progress = TableManager._is_hand_in_progress(test_table)
        assert not in_progress
    
    def test_hand_in_progress_detection_insufficient_players(self, app_context, test_table, test_user):
        """Test hand detection with insufficient players."""
        # Create one player access record
        access = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            is_spectator=False,
            seat_number=1,
            buy_in_amount=100
        )
        access.is_active = True
        test_table.access_records = [access]
        
        in_progress = TableManager._is_hand_in_progress(test_table)
        assert not in_progress  # Need at least 2 players
    
    def test_hand_in_progress_detection_old_activity(self, app_context, test_table, test_user):
        """Test hand detection with old activity."""
        # Create two players but with old activity
        access1 = TableAccess(test_table.id, test_user.id, is_spectator=False, seat_number=1, buy_in_amount=100)
        access1.is_active = True
        access2 = TableAccess(test_table.id, "user2", is_spectator=False, seat_number=2, buy_in_amount=100)
        access2.is_active = True
        test_table.access_records = [access1, access2]
        
        # Set old activity
        test_table.last_activity = datetime.utcnow() - timedelta(minutes=10)
        
        in_progress = TableManager._is_hand_in_progress(test_table)
        assert not in_progress
    
    def test_hand_in_progress_detection_active_hand(self, app_context, test_table, test_user):
        """Test hand detection with active hand."""
        # Create two players with recent activity
        access1 = TableAccess(test_table.id, test_user.id, is_spectator=False, seat_number=1, buy_in_amount=100)
        access1.is_active = True
        access2 = TableAccess(test_table.id, "user2", is_spectator=False, seat_number=2, buy_in_amount=100)
        access2.is_active = True
        test_table.access_records = [access1, access2]
        
        # Set recent activity
        test_table.last_activity = datetime.utcnow() - timedelta(minutes=2)
        
        in_progress = TableManager._is_hand_in_progress(test_table)
        assert in_progress
    
    def test_can_modify_table_settings_nonexistent_table(self, app_context):
        """Test modification check for nonexistent table."""
        can_modify, error = TableManager.can_modify_table_settings("nonexistent", "user123")
        assert not can_modify
        assert "not found" in error.lower()
    
    def test_can_modify_table_settings_wrong_user(self, app_context, test_table):
        """Test modification check for wrong user."""
        can_modify, error = TableManager.can_modify_table_settings(test_table.id, "wrong_user")
        assert not can_modify
        assert "only table creator" in error.lower()
    
    def test_can_modify_table_settings_hand_in_progress(self, app_context, test_table, test_user):
        """Test modification check when hand is in progress."""
        # Set up active hand scenario
        access1 = TableAccess(test_table.id, test_user.id, is_spectator=False, seat_number=1, buy_in_amount=100)
        access1.is_active = True
        access2 = TableAccess(test_table.id, "user2", is_spectator=False, seat_number=2, buy_in_amount=100)
        access2.is_active = True
        test_table.access_records = [access1, access2]
        test_table.last_activity = datetime.utcnow() - timedelta(minutes=2)
        
        can_modify, error = TableManager.can_modify_table_settings(test_table.id, test_user.id)
        assert not can_modify
        assert "hand is in progress" in error.lower()
    
    def test_can_modify_table_settings_success(self, app_context, test_table, test_user):
        """Test successful modification check."""
        # No active hand scenario
        test_table.access_records = []
        
        can_modify, error = TableManager.can_modify_table_settings(test_table.id, test_user.id)
        assert can_modify
        assert error == ""
    
    def test_update_table_settings_name(self, app_context, test_table, test_user):
        """Test updating table name."""
        settings = {'name': 'New Table Name'}
        
        success, message = TableManager.update_table_settings(test_table.id, test_user.id, settings)
        assert success
        assert 'name' in message
        
        # Verify the change
        updated_table = TableManager.get_table_by_id(test_table.id)
        assert updated_table.name == 'New Table Name'
    
    def test_update_table_settings_privacy(self, app_context, test_table, test_user):
        """Test updating table privacy."""
        settings = {'is_private': True}
        
        success, message = TableManager.update_table_settings(test_table.id, test_user.id, settings)
        assert success
        assert 'visibility' in message
        
        # Verify the change
        updated_table = TableManager.get_table_by_id(test_table.id)
        assert updated_table.is_private is True
        assert updated_table.invite_code is not None  # Should generate invite code
    
    def test_update_table_settings_invalid_name(self, app_context, test_table, test_user):
        """Test updating with invalid name."""
        settings = {'name': ''}
        
        success, message = TableManager.update_table_settings(test_table.id, test_user.id, settings)
        assert not success
        assert "cannot be empty" in message
    
    def test_kick_player_nonexistent_table(self, app_context):
        """Test kicking player from nonexistent table."""
        success, error = TableManager.kick_player("nonexistent", "creator", "player", "test")
        assert not success
        assert "not found" in error.lower()
    
    def test_kick_player_wrong_creator(self, app_context, test_table):
        """Test kicking player by non-creator."""
        success, error = TableManager.kick_player(test_table.id, "wrong_user", "player", "test")
        assert not success
        assert "only table creator" in error.lower()
    
    def test_kick_player_self_kick(self, app_context, test_table, test_user):
        """Test creator trying to kick themselves."""
        success, error = TableManager.kick_player(test_table.id, test_user.id, test_user.id, "test")
        assert not success
        assert "cannot kick yourself" in error.lower()
    
    @patch('src.online_poker.services.table_access_manager.TableAccessManager.leave_table')
    def test_kick_player_success(self, mock_leave_table, app_context, test_table, test_user):
        """Test successful player kick."""
        mock_leave_table.return_value = (True, "Player left successfully")
        
        success, message = TableManager.kick_player(test_table.id, test_user.id, "player_to_kick", "disruptive")
        assert success
        assert "kicked successfully" in message
        mock_leave_table.assert_called_once_with("player_to_kick", test_table.id)
    
    def test_transfer_host_privileges_nonexistent_table(self, app_context):
        """Test host transfer for nonexistent table."""
        success, error = TableManager.transfer_host_privileges("nonexistent", "old_host", "new_host")
        assert not success
        assert "not found" in error.lower()
    
    def test_transfer_host_privileges_wrong_creator(self, app_context, test_table):
        """Test host transfer by non-creator."""
        success, error = TableManager.transfer_host_privileges(test_table.id, "wrong_user", "new_host")
        assert not success
        assert "only current table creator" in error.lower()
    
    def test_transfer_host_privileges_to_self(self, app_context, test_table, test_user):
        """Test transferring host privileges to self."""
        success, error = TableManager.transfer_host_privileges(test_table.id, test_user.id, test_user.id)
        assert not success
        assert "cannot transfer privileges to yourself" in error.lower()
    
    def test_transfer_host_privileges_new_host_not_at_table(self, app_context, test_table, test_user):
        """Test transferring to user not at table."""
        success, error = TableManager.transfer_host_privileges(test_table.id, test_user.id, "absent_user")
        assert not success
        assert "must be an active player" in error.lower()
    
    def test_transfer_host_privileges_success(self, app_context, test_table, test_user):
        """Test successful host privilege transfer."""
        # Create access record for new host
        new_host_access = TableAccess(
            table_id=test_table.id,
            user_id="new_host_user",
            is_spectator=False,
            seat_number=1,
            buy_in_amount=100
        )
        new_host_access.is_active = True
        db.session.add(new_host_access)
        db.session.commit()
        
        success, message = TableManager.transfer_host_privileges(test_table.id, test_user.id, "new_host_user")
        assert success
        assert "transferred successfully" in message
        
        # Verify the change
        updated_table = TableManager.get_table_by_id(test_table.id)
        assert updated_table.creator_id == "new_host_user"
    
    def test_close_table_nonexistent(self, app_context):
        """Test closing nonexistent table."""
        success, error = TableManager.close_table("nonexistent", "creator", "test")
        assert not success
        assert "not found" in error.lower()
    
    def test_close_table_wrong_creator(self, app_context, test_table):
        """Test closing table by non-creator."""
        success, error = TableManager.close_table(test_table.id, "wrong_user", "test")
        assert not success
        assert "only table creator" in error.lower()
    
    @patch('src.online_poker.services.table_access_manager.TableAccessManager._cleanup_table_access')
    @patch('src.online_poker.services.table_manager.TableManager._notify_table_closure')
    def test_close_table_success(self, mock_notify, mock_cleanup, app_context, test_table, test_user):
        """Test successful table closure."""
        mock_cleanup.return_value = 2  # Mock cleanup count
        
        success, message = TableManager.close_table(test_table.id, test_user.id, "Manual closure")
        assert success
        assert "closed successfully" in message
        
        # Verify table was deleted
        deleted_table = TableManager.get_table_by_id(test_table.id)
        assert deleted_table is None
        
        mock_notify.assert_called_once()
        mock_cleanup.assert_called_once_with(test_table.id)
    
    def test_close_inactive_tables(self, app_context, test_user):
        """Test closing inactive tables."""
        # Create an inactive table
        inactive_table = PokerTable(
            name="Inactive Table",
            variant="hold_em",
            betting_structure=BettingStructure.NO_LIMIT.value,
            stakes={"small_blind": 1, "big_blind": 2},
            max_players=6,
            creator_id=test_user.id
        )
        inactive_table.last_activity = datetime.utcnow() - timedelta(minutes=45)
        db.session.add(inactive_table)
        db.session.commit()
        
        with patch('src.online_poker.services.table_access_manager.TableAccessManager._cleanup_table_access') as mock_cleanup:
            mock_cleanup.return_value = 0
            
            closed_count = TableManager.close_inactive_tables(30)
            assert closed_count == 1
            
            # Verify table was deleted
            deleted_table = TableManager.get_table_by_id(inactive_table.id)
            assert deleted_table is None


class TestTableAccessCleanup:
    """Test table access cleanup functionality."""
    
    def test_cleanup_table_access(self, app_context, test_table, test_user):
        """Test cleaning up table access records."""
        # Create access records
        access1 = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            is_spectator=False,
            seat_number=1,
            buy_in_amount=100
        )
        access1.current_stack = 150
        access1.is_active = True
        
        access2 = TableAccess(
            table_id=test_table.id,
            user_id="user2",
            is_spectator=True
        )
        access2.is_active = True
        
        db.session.add_all([access1, access2])
        db.session.commit()
        
        # Mock user manager for bankroll update
        with patch('src.online_poker.services.table_access_manager.UserManager') as mock_user_manager:
            mock_user = MagicMock()
            mock_user_manager.return_value.get_user_by_id.return_value = mock_user
            
            cleaned_count = TableAccessManager._cleanup_table_access(test_table.id)
            assert cleaned_count == 2
            
            # Verify bankroll update was called for player with chips
            mock_user.update_bankroll.assert_called_once_with(150)
    
    def test_cleanup_inactive_access(self, app_context, test_table, test_user):
        """Test cleaning up inactive access records."""
        # Create an inactive access record
        access = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            is_spectator=False,
            seat_number=1,
            buy_in_amount=100
        )
        access.current_stack = 80
        access.is_active = True
        access.last_activity = datetime.utcnow() - timedelta(minutes=45)
        
        db.session.add(access)
        db.session.commit()
        
        with patch('src.online_poker.services.table_access_manager.UserManager') as mock_user_manager:
            mock_user = MagicMock()
            mock_user_manager.return_value.get_user_by_id.return_value = mock_user
            
            cleaned_count = TableAccessManager.cleanup_inactive_access(30)
            assert cleaned_count == 1
            
            # Verify access record was deactivated
            updated_access = db.session.query(TableAccess).filter_by(id=access.id).first()
            assert not updated_access.is_active
            assert updated_access.seat_number is None
            
            # Verify bankroll update
            mock_user.update_bankroll.assert_called_once_with(80)


class TestTableInactivityDetection:
    """Test table inactivity detection."""
    
    def test_table_is_inactive_recent_activity(self, app_context, test_table):
        """Test table with recent activity is not inactive."""
        test_table.last_activity = datetime.utcnow()
        assert not test_table.is_inactive(30)
    
    def test_table_is_inactive_old_activity(self, app_context, test_table):
        """Test table with old activity is inactive."""
        test_table.last_activity = datetime.utcnow() - timedelta(minutes=45)
        assert test_table.is_inactive(30)
    
    def test_table_is_inactive_custom_timeout(self, app_context, test_table):
        """Test table inactivity with custom timeout."""
        test_table.last_activity = datetime.utcnow() - timedelta(minutes=10)
        
        # Should not be inactive with 15-minute timeout
        assert not test_table.is_inactive(15)
        
        # Should be inactive with 5-minute timeout
        assert test_table.is_inactive(5)


class TestTableLifecycleIntegration:
    """Test integration between table lifecycle components."""
    
    def test_table_closure_with_players(self, app_context, test_table, test_user):
        """Test table closure properly handles players."""
        # Add a player with chips
        access = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            is_spectator=False,
            seat_number=1,
            buy_in_amount=100
        )
        access.current_stack = 120
        access.is_active = True
        db.session.add(access)
        db.session.commit()
        
        with patch('src.online_poker.services.table_access_manager.UserManager') as mock_user_manager:
            mock_user = MagicMock()
            mock_user_manager.return_value.get_user_by_id.return_value = mock_user
            
            success, message = TableManager.close_table(test_table.id, test_user.id, "Test closure")
            assert success
            
            # Verify player was cashed out
            mock_user.update_bankroll.assert_called_once_with(120)
            
            # Verify table was deleted
            deleted_table = TableManager.get_table_by_id(test_table.id)
            assert deleted_table is None
    
    def test_cleanup_expired_private_tables(self, app_context):
        """Test cleanup of expired private tables."""
        # This method calls close_inactive_tables with 24-hour timeout
        with patch.object(TableManager, 'close_inactive_tables') as mock_close:
            mock_close.return_value = 3
            
            expired_count = TableManager.cleanup_expired_private_tables()
            assert expired_count == 3
            
            # Verify it was called with 24-hour timeout
            mock_close.assert_called_once_with(timeout_minutes=24 * 60)