"""Unit tests for game state management."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from flask import Flask

from src.online_poker.services.game_state_manager import GameStateManager
from src.online_poker.models.game_state_view import (
    GameStateView, PlayerView, PotInfo, ActionOption, GamePhase, 
    ActionType, GameStateUpdate, HandResult
)
from src.online_poker.services.game_orchestrator import GameSession
from src.online_poker.models.table import PokerTable
from src.online_poker.models.user import User
from src.online_poker.database import db
from generic_poker.game.betting import BettingStructure
from generic_poker.game.game_state import GameState


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


@pytest.fixture
def mock_game_session(test_table):
    """Create a mock game session."""
    session = MagicMock(spec=GameSession)
    session.session_id = "test-session-id"
    session.table = test_table
    session.hands_played = 5
    session.connected_players = {"user1", "user2"}
    session.disconnected_players = {}
    session.spectators = {"spectator1"}
    
    # Mock game object
    mock_game = MagicMock()
    mock_game.state = GameState.BETTING
    session.game = mock_game
    
    return session


class TestGameStateManager:
    """Test GameStateManager functionality."""
    
    @patch('src.online_poker.services.game_state_manager.game_orchestrator.get_session')
    @patch('src.online_poker.services.game_state_manager.TableAccessManager.get_table_players')
    def test_generate_game_state_view_success(self, mock_get_players, mock_get_session, 
                                            app_context, mock_game_session):
        """Test successful game state view generation."""
        # Mock session
        mock_get_session.return_value = mock_game_session
        
        # Mock players
        mock_get_players.return_value = [
            {
                'user_id': 'user1',
                'username': 'Alice',
                'seat_number': 1,
                'is_spectator': False,
                'current_stack': 500
            },
            {
                'user_id': 'user2', 
                'username': 'Bob',
                'seat_number': 2,
                'is_spectator': False,
                'current_stack': 300
            }
        ]
        
        # Generate game state view
        game_state = GameStateManager.generate_game_state_view("table1", "user1", False)
        
        assert game_state is not None
        assert game_state.table_id == "table1"
        assert game_state.session_id == "test-session-id"
        assert game_state.viewer_id == "user1"
        assert len(game_state.players) == 2
        assert game_state.hand_number == 6  # hands_played + 1
        assert game_state.is_spectator is False
        
        # Check players are sorted by seat number
        assert game_state.players[0].seat_number == 1
        assert game_state.players[1].seat_number == 2
    
    @patch('src.online_poker.services.game_state_manager.game_orchestrator.get_session')
    def test_generate_game_state_view_no_session(self, mock_get_session, app_context):
        """Test game state view generation when no session exists."""
        mock_get_session.return_value = None
        
        game_state = GameStateManager.generate_game_state_view("table1", "user1", False)
        
        assert game_state is None
    
    @patch('src.online_poker.services.game_state_manager.game_orchestrator.get_session')
    @patch('src.online_poker.services.game_state_manager.TableAccessManager.get_table_players')
    def test_generate_game_state_view_no_players(self, mock_get_players, mock_get_session, 
                                               app_context, mock_game_session):
        """Test game state view generation when no players exist."""
        mock_get_session.return_value = mock_game_session
        mock_get_players.return_value = []
        
        game_state = GameStateManager.generate_game_state_view("table1", "user1", False)
        
        assert game_state is None
    
    @patch('src.online_poker.services.game_state_manager.game_orchestrator.get_session')
    @patch('src.online_poker.services.game_state_manager.TableAccessManager.get_table_players')
    def test_generate_game_state_view_spectator(self, mock_get_players, mock_get_session, 
                                              app_context, mock_game_session):
        """Test game state view generation for spectator."""
        mock_get_session.return_value = mock_game_session
        mock_get_players.return_value = [
            {
                'user_id': 'user1',
                'username': 'Alice',
                'seat_number': 1,
                'is_spectator': False,
                'current_stack': 500
            }
        ]
        
        # Generate game state view for spectator
        game_state = GameStateManager.generate_game_state_view("table1", "spectator1", True)
        
        assert game_state is not None
        assert game_state.is_spectator is True
        assert len(game_state.valid_actions) == 0  # Spectators can't act
    
    def test_create_player_view(self, app_context, mock_game_session):
        """Test creating a player view."""
        player_info = {
            'user_id': 'user1',
            'username': 'Alice',
            'seat_number': 1,
            'is_spectator': False,
            'current_stack': 500
        }
        
        with patch.object(GameStateManager, '_get_player_cards', return_value=['As', 'Ks']):
            with patch.object(GameStateManager, '_is_current_player', return_value=True):
                player_view = GameStateManager._create_player_view(
                    player_info, mock_game_session, "user1", False
                )
                
                assert player_view is not None
                assert player_view.user_id == 'user1'
                assert player_view.username == 'Alice'
                assert player_view.seat_number == 1
                assert player_view.chip_stack == 500
                assert player_view.cards == ['As', 'Ks']  # Own cards visible
                assert player_view.is_current_player is True
    
    def test_create_player_view_other_player(self, app_context, mock_game_session):
        """Test creating a player view for another player."""
        player_info = {
            'user_id': 'user2',
            'username': 'Bob',
            'seat_number': 2,
            'is_spectator': False,
            'current_stack': 300
        }
        
        with patch.object(GameStateManager, '_should_show_cards', return_value=False):
            player_view = GameStateManager._create_player_view(
                player_info, mock_game_session, "user1", False
            )
            
            assert player_view is not None
            assert player_view.user_id == 'user2'
            assert player_view.cards == []  # Other player's cards hidden
    
    def test_get_community_cards(self, app_context, mock_game_session):
        """Test getting community cards."""
        # Mock community cards
        mock_cards = ['As', 'Ks', 'Qs']
        mock_game_session.game.table.community_cards = mock_cards
        
        community_cards = GameStateManager._get_community_cards(mock_game_session)
        
        assert 'board' in community_cards
        assert community_cards['board'] == ['As', 'Ks', 'Qs']
    
    def test_get_community_cards_no_game(self, app_context):
        """Test getting community cards when no game exists."""
        session = MagicMock()
        session.game = None
        
        community_cards = GameStateManager._get_community_cards(session)
        
        assert community_cards == {}
    
    def test_get_pot_info(self, app_context, mock_game_session):
        """Test getting pot information."""
        # Mock pot
        mock_pot = MagicMock()
        mock_pot.total = 150
        mock_pot.side_pots = []
        mock_game_session.game.table.pot = mock_pot
        mock_game_session.game.table.current_bet = 50
        
        pot_info = GameStateManager._get_pot_info(mock_game_session)
        
        assert pot_info.main_pot == 150
        assert pot_info.current_bet == 50
        assert pot_info.total_pot == 150
    
    def test_get_current_player(self, app_context, mock_game_session):
        """Test getting current player."""
        # Mock current player
        mock_player = MagicMock()
        mock_player.id = 'user1'
        mock_game_session.game.table.current_player = mock_player
        
        current_player = GameStateManager._get_current_player(mock_game_session)
        
        assert current_player == 'user1'
    
    def test_get_valid_actions_current_player(self, app_context, mock_game_session):
        """Test getting valid actions for current player."""
        with patch.object(GameStateManager, '_is_current_player', return_value=True):
            valid_actions = GameStateManager._get_valid_actions(mock_game_session, 'user1')
            
            assert len(valid_actions) > 0
            action_types = [action.action_type for action in valid_actions]
            assert ActionType.FOLD in action_types
            assert ActionType.CHECK in action_types
            assert ActionType.CALL in action_types
    
    def test_get_valid_actions_not_current_player(self, app_context, mock_game_session):
        """Test getting valid actions for non-current player."""
        with patch.object(GameStateManager, '_is_current_player', return_value=False):
            valid_actions = GameStateManager._get_valid_actions(mock_game_session, 'user1')
            
            assert len(valid_actions) == 0
    
    def test_get_game_phase_waiting(self, app_context, mock_game_session):
        """Test getting game phase when waiting."""
        mock_game_session.game.state = GameState.WAITING
        
        phase = GameStateManager._get_game_phase(mock_game_session)
        
        assert phase == GamePhase.WAITING
    
    def test_get_game_phase_betting_preflop(self, app_context, mock_game_session):
        """Test getting game phase during preflop betting."""
        mock_game_session.game.state = GameState.BETTING
        
        with patch.object(GameStateManager, '_get_community_cards', return_value={'board': []}):
            phase = GameStateManager._get_game_phase(mock_game_session)
            
            assert phase == GamePhase.PREFLOP
    
    def test_get_game_phase_betting_flop(self, app_context, mock_game_session):
        """Test getting game phase during flop betting."""
        mock_game_session.game.state = GameState.BETTING
        
        with patch.object(GameStateManager, '_get_community_cards', return_value={'board': ['As', 'Ks', 'Qs']}):
            phase = GameStateManager._get_game_phase(mock_game_session)
            
            assert phase == GamePhase.FLOP
    
    def test_get_game_phase_showdown(self, app_context, mock_game_session):
        """Test getting game phase during showdown."""
        mock_game_session.game.state = GameState.SHOWDOWN
        
        phase = GameStateManager._get_game_phase(mock_game_session)
        
        assert phase == GamePhase.SHOWDOWN
    
    def test_should_show_cards_showdown(self, app_context, mock_game_session):
        """Test showing cards during showdown."""
        with patch.object(GameStateManager, '_get_game_phase', return_value=GamePhase.SHOWDOWN):
            should_show = GameStateManager._should_show_cards(mock_game_session, 'user1')
            
            assert should_show is True
    
    def test_should_show_cards_normal_play(self, app_context, mock_game_session):
        """Test not showing cards during normal play."""
        with patch.object(GameStateManager, '_get_game_phase', return_value=GamePhase.PREFLOP):
            should_show = GameStateManager._should_show_cards(mock_game_session, 'user1')
            
            assert should_show is False
    
    def test_get_player_cards(self, app_context, mock_game_session):
        """Test getting player cards."""
        # Mock player with cards
        mock_player = MagicMock()
        mock_player.cards = ['As', 'Ks']
        mock_game_session.game.table.players = {'user1': mock_player}
        
        cards = GameStateManager._get_player_cards(mock_game_session, 'user1')
        
        assert cards == ['As', 'Ks']
    
    def test_get_player_cards_no_player(self, app_context, mock_game_session):
        """Test getting cards for non-existent player."""
        mock_game_session.game.table.players = {}
        
        cards = GameStateManager._get_player_cards(mock_game_session, 'user1')
        
        assert cards == []
    
    def test_is_current_player(self, app_context, mock_game_session):
        """Test checking if player is current player."""
        with patch.object(GameStateManager, '_get_current_player', return_value='user1'):
            is_current = GameStateManager._is_current_player(mock_game_session, 'user1')
            assert is_current is True
            
            is_current = GameStateManager._is_current_player(mock_game_session, 'user2')
            assert is_current is False
    
    def test_get_position_name(self, app_context):
        """Test getting position names."""
        assert GameStateManager._get_position_name(1) == "UTG"
        assert GameStateManager._get_position_name(6) == "BTN"
        assert GameStateManager._get_position_name(10) == "Seat 10"
    
    def test_create_game_state_update(self, app_context):
        """Test creating game state update."""
        with patch('src.online_poker.services.game_state_manager.game_orchestrator.get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.session_id = "test-session"
            mock_get_session.return_value = mock_session
            
            update = GameStateManager.create_game_state_update(
                "table1", "test_update", {"key": "value"}, ["user1"]
            )
            
            assert update.table_id == "table1"
            assert update.session_id == "test-session"
            assert update.update_type == "test_update"
            assert update.data == {"key": "value"}
            assert update.affected_players == ["user1"]
    
    def test_process_hand_completion(self, app_context, mock_game_session):
        """Test processing hand completion."""
        with patch.object(GameStateManager, '_get_community_cards', return_value={'board': ['As', 'Ks', 'Qs', 'Js', '10s']}):
            with patch.object(GameStateManager, '_get_pot_info', return_value=PotInfo(150)):
                hand_result = GameStateManager.process_hand_completion(mock_game_session)
                
                assert hand_result is not None
                assert hand_result.table_id == mock_game_session.table.id
                assert hand_result.session_id == mock_game_session.session_id
                assert hand_result.final_board == ['As', 'Ks', 'Qs', 'Js', '10s']
    
    def test_detect_state_changes_phase_change(self, app_context):
        """Test detecting phase changes."""
        old_state = GameStateView(
            table_id="table1",
            session_id="session1", 
            viewer_id="user1",
            players=[],
            game_phase=GamePhase.PREFLOP
        )
        
        new_state = GameStateView(
            table_id="table1",
            session_id="session1",
            viewer_id="user1", 
            players=[],
            game_phase=GamePhase.FLOP
        )
        
        changes = GameStateManager.detect_state_changes(old_state, new_state)
        
        assert len(changes) > 0
        phase_changes = [c for c in changes if c.update_type == "phase_change"]
        assert len(phase_changes) == 1
        assert phase_changes[0].data["old_phase"] == "preflop"
        assert phase_changes[0].data["new_phase"] == "flop"
    
    def test_detect_state_changes_current_player_change(self, app_context):
        """Test detecting current player changes."""
        old_state = GameStateView(
            table_id="table1",
            session_id="session1",
            viewer_id="user1", 
            players=[],
            current_player="user1"
        )
        
        new_state = GameStateView(
            table_id="table1",
            session_id="session1",
            viewer_id="user1",
            players=[],
            current_player="user2"
        )
        
        changes = GameStateManager.detect_state_changes(old_state, new_state)
        
        player_changes = [c for c in changes if c.update_type == "current_player_change"]
        assert len(player_changes) == 1
        assert player_changes[0].data["old_player"] == "user1"
        assert player_changes[0].data["new_player"] == "user2"
    
    def test_detect_state_changes_pot_change(self, app_context):
        """Test detecting pot changes."""
        old_state = GameStateView(
            table_id="table1",
            session_id="session1",
            viewer_id="user1",
            players=[],
            pot_info=PotInfo(100)
        )
        
        new_state = GameStateView(
            table_id="table1", 
            session_id="session1",
            viewer_id="user1",
            players=[],
            pot_info=PotInfo(150)
        )
        
        changes = GameStateManager.detect_state_changes(old_state, new_state)
        
        pot_changes = [c for c in changes if c.update_type == "pot_change"]
        assert len(pot_changes) == 1
        assert pot_changes[0].data["old_pot"] == 100
        assert pot_changes[0].data["new_pot"] == 150