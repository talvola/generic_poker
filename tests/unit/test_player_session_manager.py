"""Unit tests for player session management."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from flask import Flask

from src.online_poker.services.player_session_manager import PlayerSessionManager
from src.online_poker.services.game_orchestrator import GameSession
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
        name="Test Game Table",
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


class TestPlayerSessionManager:
    """Test PlayerSessionManager functionality."""
    
    @patch('src.online_poker.services.player_session_manager.TableAccessManager.join_table')
    @patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session')
    @patch('src.online_poker.services.player_session_manager.game_orchestrator.create_session')
    def test_join_table_and_game_success(self, mock_create_session, mock_get_session, 
                                        mock_join_table, app_context, test_user, test_table):
        """Test successful joining of table and game."""
        # Mock table access join
        mock_access_record = MagicMock()
        mock_access_record.current_stack = 500
        mock_access_record.to_dict.return_value = {'stack': 500}
        mock_join_table.return_value = (True, "Joined successfully", mock_access_record)
        
        # Mock game session
        mock_session = MagicMock()
        mock_session.add_player.return_value = (True, "Added to game")
        mock_session.get_session_info.return_value = {'session_id': 'test'}
        mock_get_session.return_value = mock_session
        
        # Test join
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            test_user.id, test_table.id, 500
        )
        
        assert success is True
        assert "Successfully joined" in message
        assert session_info is not None
        assert 'session' in session_info
        assert 'access_record' in session_info
        
        # Verify calls
        mock_join_table.assert_called_once_with(
            test_user.id, test_table.id, 500, None, None, False
        )
        mock_session.add_player.assert_called_once()
    
    @patch('src.online_poker.services.player_session_manager.TableAccessManager.join_table')
    def test_join_table_and_game_table_join_fails(self, mock_join_table, app_context, test_user, test_table):
        """Test joining when table join fails."""
        mock_join_table.return_value = (False, "Table is full", None)
        
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            test_user.id, test_table.id, 500
        )
        
        assert success is False
        assert message == "Table is full"
        assert session_info is None
    
    @patch('src.online_poker.services.player_session_manager.TableAccessManager.join_table')
    @patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session')
    @patch('src.online_poker.services.player_session_manager.game_orchestrator.create_session')
    def test_join_table_and_game_session_creation_fails(self, mock_create_session, mock_get_session,
                                                       mock_join_table, app_context, test_user, test_table):
        """Test joining when game session creation fails."""
        # Mock successful table join
        mock_access_record = MagicMock()
        mock_join_table.return_value = (True, "Joined table", mock_access_record)
        
        # Mock no existing session
        mock_get_session.return_value = None
        
        # Mock failed session creation
        mock_create_session.return_value = (False, "Failed to create session", None)
        
        # Mock leave table for cleanup
        with patch('src.online_poker.services.player_session_manager.TableAccessManager.leave_table') as mock_leave:
            mock_leave.return_value = (True, "Left table")
            
            success, message, session_info = PlayerSessionManager.join_table_and_game(
                test_user.id, test_table.id, 500
            )
            
            assert success is False
            assert "Failed to create game session" in message
            assert session_info is None
            
            # Verify cleanup was called
            mock_leave.assert_called_once_with(test_user.id, test_table.id)
    
    @patch('src.online_poker.services.player_session_manager.TableAccessManager.join_table')
    @patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session')
    def test_join_table_and_game_as_spectator(self, mock_get_session, mock_join_table, 
                                             app_context, test_user, test_table):
        """Test joining as spectator."""
        # Mock table access join
        mock_access_record = MagicMock()
        mock_access_record.to_dict.return_value = {'spectator': True}
        mock_join_table.return_value = (True, "Joined as spectator", mock_access_record)
        
        # Mock game session
        mock_session = MagicMock()
        mock_session.add_spectator.return_value = (True, "Added as spectator")
        mock_session.get_session_info.return_value = {'session_id': 'test'}
        mock_get_session.return_value = mock_session
        
        # Test join as spectator
        success, message, session_info = PlayerSessionManager.join_table_and_game(
            test_user.id, test_table.id, 0, as_spectator=True
        )
        
        assert success is True
        assert session_info is not None
        
        # Verify spectator was added
        mock_session.add_spectator.assert_called_once_with(test_user.id)
    
    def test_leave_table_and_game_success(self, app_context, test_user, test_table):
        """Test successful leaving of table and game."""
        # Create access record
        access_record = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            buy_in_amount=500,
            is_spectator=False
        )
        access_record.current_stack = 600
        db.session.add(access_record)
        db.session.commit()
        
        with patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session') as mock_get_session:
            with patch('src.online_poker.services.player_session_manager.TableAccessManager.leave_table') as mock_leave:
                # Mock game session
                mock_session = MagicMock()
                mock_session.remove_player.return_value = (True, "Removed from game")
                mock_get_session.return_value = mock_session
                
                # Mock table leave
                mock_leave.return_value = (True, "Left table")
                
                success, message, cashout_info = PlayerSessionManager.leave_table_and_game(
                    test_user.id, test_table.id
                )
                
                assert success is True
                assert cashout_info is not None
                assert cashout_info['initial_stack'] == 600
                assert cashout_info['profit_loss'] == 100  # 600 - 500
                
                # Verify calls
                mock_session.remove_player.assert_called_once()
                mock_leave.assert_called_once()
    
    def test_leave_table_and_game_not_at_table(self, app_context, test_user, test_table):
        """Test leaving when not at table."""
        success, message, cashout_info = PlayerSessionManager.leave_table_and_game(
            test_user.id, test_table.id
        )
        
        assert success is False
        assert message == "Not at this table"
        assert cashout_info is None
    
    def test_leave_table_and_game_spectator(self, app_context, test_user, test_table):
        """Test leaving as spectator."""
        # Create spectator access record
        access_record = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            is_spectator=True
        )
        db.session.add(access_record)
        db.session.commit()
        
        with patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session') as mock_get_session:
            with patch('src.online_poker.services.player_session_manager.TableAccessManager.leave_table') as mock_leave:
                # Mock game session
                mock_session = MagicMock()
                mock_get_session.return_value = mock_session
                
                # Mock table leave
                mock_leave.return_value = (True, "Left table")
                
                success, message, cashout_info = PlayerSessionManager.leave_table_and_game(
                    test_user.id, test_table.id
                )
                
                assert success is True
                assert cashout_info is None  # No cashout for spectators
                
                # Verify spectator was removed
                mock_session.remove_spectator.assert_called_once_with(test_user.id)
    
    def test_handle_player_disconnect(self, app_context, test_user, test_table):
        """Test handling player disconnect."""
        # Create access record
        access_record = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            buy_in_amount=500
        )
        db.session.add(access_record)
        db.session.commit()
        
        with patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session') as mock_get_session:
            # Mock game session
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session
            
            success, message = PlayerSessionManager.handle_player_disconnect(
                test_user.id, test_table.id
            )
            
            assert success is True
            assert message == "Disconnect handled"
            
            # Verify game session disconnect was called
            mock_session.handle_player_disconnect.assert_called_once_with(test_user.id)
            
            # Verify access record was updated
            db.session.refresh(access_record)
            assert access_record.last_activity is not None
    
    def test_handle_player_reconnect_success(self, app_context, test_user, test_table):
        """Test successful player reconnect."""
        # Create access record
        access_record = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            buy_in_amount=500
        )
        db.session.add(access_record)
        db.session.commit()
        
        with patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session') as mock_get_session:
            # Mock game session
            mock_session = MagicMock()
            mock_session.handle_player_reconnect.return_value = (True, "Reconnected")
            mock_session.get_session_info.return_value = {'session_id': 'test'}
            mock_get_session.return_value = mock_session
            
            success, message, session_info = PlayerSessionManager.handle_player_reconnect(
                test_user.id, test_table.id
            )
            
            assert success is True
            assert message == "Successfully reconnected"
            assert session_info is not None
            
            # Verify game session reconnect was called
            mock_session.handle_player_reconnect.assert_called_once_with(test_user.id)
    
    def test_handle_player_reconnect_no_access(self, app_context, test_user, test_table):
        """Test reconnect when user has no active access."""
        success, message, session_info = PlayerSessionManager.handle_player_reconnect(
            test_user.id, test_table.id
        )
        
        assert success is False
        assert message == "No active access to this table"
        assert session_info is None
    
    def test_get_player_info_success(self, app_context, test_user, test_table):
        """Test getting player info."""
        # Create access record
        access_record = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            buy_in_amount=500,
            seat_number=1
        )
        access_record.current_stack = 600
        db.session.add(access_record)
        db.session.commit()
        
        with patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session') as mock_get_session:
            # Mock game session
            mock_session = MagicMock()
            mock_session.connected_players = {test_user.id}
            mock_session.disconnected_players = {}
            mock_session.spectators = set()
            mock_get_session.return_value = mock_session
            
            player_info = PlayerSessionManager.get_player_info(test_user.id, test_table.id)
            
            assert player_info is not None
            assert player_info['user_id'] == test_user.id
            assert player_info['username'] == test_user.username
            assert player_info['seat_number'] == 1
            assert player_info['buy_in_amount'] == 500
            assert player_info['current_stack'] == 600
            assert player_info['game_status'] == "connected"
            assert player_info['is_spectator'] is False
    
    def test_get_player_info_not_found(self, app_context, test_user, test_table):
        """Test getting player info when not at table."""
        player_info = PlayerSessionManager.get_player_info(test_user.id, test_table.id)
        assert player_info is None
    
    def test_get_table_session_info_success(self, app_context, test_user, test_table):
        """Test getting table session info."""
        # Create access records
        access_record = TableAccess(
            table_id=test_table.id,
            user_id=test_user.id,
            buy_in_amount=500,
            seat_number=1
        )
        db.session.add(access_record)
        db.session.commit()
        
        with patch('src.online_poker.services.player_session_manager.TableManager.get_table_by_id') as mock_get_table:
            with patch('src.online_poker.services.player_session_manager.TableAccessManager.get_table_players') as mock_get_players:
                with patch('src.online_poker.services.player_session_manager.game_orchestrator.get_session') as mock_get_session:
                    # Mock table
                    mock_get_table.return_value = test_table
                    
                    # Mock players
                    mock_get_players.return_value = [{
                        'user_id': test_user.id,
                        'username': test_user.username,
                        'is_spectator': False,
                        'seat_number': 1
                    }]
                    
                    # Mock session
                    mock_session = MagicMock()
                    mock_session.get_session_info.return_value = {'session_id': 'test'}
                    mock_get_session.return_value = mock_session
                    
                    session_info = PlayerSessionManager.get_table_session_info(test_table.id)
                    
                    assert session_info is not None
                    assert 'table' in session_info
                    assert 'players' in session_info
                    assert 'spectators' in session_info
                    assert 'session' in session_info
                    assert 'stats' in session_info
                    
                    assert session_info['table']['id'] == test_table.id
                    assert session_info['stats']['total_players'] == 1
                    assert session_info['stats']['has_game_session'] is True
    
    def test_validate_buy_in_success(self, app_context, test_user, test_table):
        """Test successful buy-in validation."""
        with patch('src.online_poker.services.player_session_manager.TableManager.get_table_by_id') as mock_get_table:
            mock_get_table.return_value = test_table
            
            is_valid, message = PlayerSessionManager.validate_buy_in(
                test_user.id, test_table.id, 100
            )
            
            assert is_valid is True
            assert message == "Buy-in amount is valid"
    
    def test_validate_buy_in_insufficient_bankroll(self, app_context, test_user, test_table):
        """Test buy-in validation with insufficient bankroll."""
        # Reduce user's bankroll to test insufficient funds
        test_user.bankroll = 50
        
        with patch('src.online_poker.services.player_session_manager.TableManager.get_table_by_id') as mock_get_table:
            mock_get_table.return_value = test_table
            
            # Use an amount within table limits but exceeding user bankroll
            is_valid, message = PlayerSessionManager.validate_buy_in(
                test_user.id, test_table.id, 100  # Within table limits but more than user's bankroll of 50
            )
            
            assert is_valid is False
            assert "Insufficient bankroll" in message
    
    def test_validate_buy_in_below_minimum(self, app_context, test_user, test_table):
        """Test buy-in validation below minimum."""
        with patch('src.online_poker.services.player_session_manager.TableManager.get_table_by_id') as mock_get_table:
            mock_get_table.return_value = test_table
            
            is_valid, message = PlayerSessionManager.validate_buy_in(
                test_user.id, test_table.id, 10  # Below minimum
            )
            
            assert is_valid is False
            assert "Minimum buy-in" in message
    
    @patch('src.online_poker.services.player_session_manager.TableAccessManager.cleanup_inactive_access')
    @patch('src.online_poker.services.player_session_manager.game_orchestrator.cleanup_inactive_sessions')
    def test_cleanup_inactive_sessions(self, mock_cleanup_sessions, mock_cleanup_access, app_context):
        """Test cleanup of inactive sessions."""
        mock_cleanup_access.return_value = 2
        mock_cleanup_sessions.return_value = 1
        
        cleaned_count = PlayerSessionManager.cleanup_inactive_sessions(30)
        
        assert cleaned_count == 3
        mock_cleanup_access.assert_called_once_with(30)
        mock_cleanup_sessions.assert_called_once_with(30)