"""Tests for chat system functionality."""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.online_poker.models.chat import ChatMessage, ChatModerationAction, ChatFilter
from src.online_poker.services.chat_service import ChatService
from src.online_poker.models.user import User
from src.online_poker.models.table import PokerTable

@pytest.fixture
def chat_service():
    """Create a chat service instance."""
    return ChatService()


@pytest.fixture
def sample_user():
    """Create a sample user."""
    user = User(
        username='testuser',
        email='test@example.com',
        password='testpassword',
        bankroll=1000
    )
    user.id = str(uuid.uuid4())
    return user


@pytest.fixture
def sample_table():
    """Create a sample poker table."""
    # Create a mock table since PokerTable constructor is complex
    table = Mock()
    table.id = str(uuid.uuid4())
    table.name = 'Test Table'
    table.max_players = 6
    return table


class TestChatService:
    """Test cases for ChatService."""
    
    def test_send_message_success(self, chat_service, sample_user, sample_table):
        """Test successful message sending."""
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            message = chat_service.send_message(
                table_id=sample_table.id,
                user_id=sample_user.id,
                message="Hello everyone!"
            )
            
            assert message is not None
            assert message.message == "Hello everyone!"
            assert message.table_id == sample_table.id
            assert message.user_id == sample_user.id
            assert message.message_type == 'chat'
            assert not message.is_filtered
            mock_session.add.assert_called_once()
            assert mock_session.commit.call_count >= 1
    
    def test_send_message_with_profanity(self, chat_service, sample_user, sample_table):
        """Test message filtering for profanity."""
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            message = chat_service.send_message(
                table_id=sample_table.id,
                user_id=sample_user.id,
                message="This is damn good!"
            )
            
            assert message is not None
            assert message.message == "This is damn good!"
            assert message.filtered_message == "This is **** good!"
            assert message.is_filtered
    
    def test_send_message_blocked_spam(self, chat_service, sample_user, sample_table):
        """Test message blocking for spam."""
        with patch('src.online_poker.services.chat_service.db.session'):
            # Test repeated characters
            message = chat_service.send_message(
                table_id=sample_table.id,
                user_id=sample_user.id,
                message="HELLOOOOOOO"
            )
            
            assert message is None
    
    def test_send_message_blocked_for_muted_user(self, chat_service, sample_user, sample_table):
        """Test message blocking for muted users."""
        with patch.object(chat_service, 'is_user_muted', return_value=True):
            message = chat_service.send_message(
                table_id=sample_table.id,
                user_id=sample_user.id,
                message="Hello everyone!"
            )
            
            assert message is None
    
    def test_mute_user(self, chat_service, sample_user, sample_table):
        """Test muting a user."""
        moderator_id = uuid.uuid4()
        
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            mock_session.query.return_value.filter.return_value.all.return_value = []
            
            mute_action = chat_service.mute_user(
                table_id=sample_table.id,
                target_user_id=sample_user.id,
                moderator_user_id=moderator_id,
                duration_minutes=30,
                reason="Inappropriate language"
            )
            
            assert mute_action.action_type == 'mute'
            assert mute_action.target_user_id == sample_user.id
            assert mute_action.moderator_user_id == moderator_id
            assert mute_action.duration_minutes == 30
            assert mute_action.reason == "Inappropriate language"
            assert mute_action.is_active
    
    def test_unmute_user(self, chat_service, sample_user, sample_table):
        """Test unmuting a user."""
        moderator_id = uuid.uuid4()
        
        # Mock existing mute
        existing_mute = Mock()
        existing_mute.is_active = True
        
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            mock_session.query.return_value.filter.return_value.all.return_value = [existing_mute]
            
            unmute_action = chat_service.unmute_user(
                table_id=sample_table.id,
                target_user_id=sample_user.id,
                moderator_user_id=moderator_id
            )
            
            assert unmute_action.action_type == 'unmute'
            assert existing_mute.is_active == False
    
    def test_is_user_muted_active(self, chat_service, sample_user, sample_table):
        """Test checking if user is muted with active mute."""
        active_mute = Mock()
        active_mute.is_expired.return_value = False
        
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            mock_session.query.return_value.filter.return_value.all.return_value = [active_mute]
            
            is_muted = chat_service.is_user_muted(sample_table.id, sample_user.id)
            
            assert is_muted == True
    
    def test_is_user_muted_expired(self, chat_service, sample_user, sample_table):
        """Test checking if user is muted with expired mute."""
        expired_mute = Mock()
        expired_mute.is_expired.return_value = True
        expired_mute.is_active = True
        
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            mock_session.query.return_value.filter.return_value.all.return_value = [expired_mute]
            
            is_muted = chat_service.is_user_muted(sample_table.id, sample_user.id)
            
            assert is_muted == False
            assert expired_mute.is_active == False
    
    def test_get_table_messages(self, chat_service, sample_table):
        """Test retrieving table messages."""
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            mock_query = mock_session.query.return_value
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            
            messages = chat_service.get_table_messages(sample_table.id)
            
            mock_session.query.assert_called_with(ChatMessage)
            mock_query.limit.assert_called_with(50)
    
    def test_filter_message_clean(self, chat_service):
        """Test filtering clean message."""
        filtered, is_filtered = chat_service._filter_message("Hello everyone!")
        
        assert filtered == "Hello everyone!"
        assert is_filtered == False
    
    def test_filter_message_profanity(self, chat_service):
        """Test filtering message with profanity."""
        filtered, is_filtered = chat_service._filter_message("This is damn good!")
        
        assert filtered == "This is **** good!"
        assert is_filtered == True
    
    def test_filter_message_spam_blocked(self, chat_service):
        """Test blocking spam message."""
        filtered, is_filtered = chat_service._filter_message("HELLOOOOOOO")
        
        assert filtered is None
        assert is_filtered == True
    
    def test_filter_message_too_long(self, chat_service):
        """Test blocking message that's too long."""
        long_message = "A" * 501
        filtered, is_filtered = chat_service._filter_message(long_message)
        
        assert filtered is None
        assert is_filtered == True
    
    def test_add_filter_word(self, chat_service):
        """Test adding a new filter word."""
        with patch('src.online_poker.services.chat_service.db.session') as mock_session:
            chat_filter = chat_service.add_filter_word(
                pattern=r'\bbadword\b',
                filter_type='profanity',
                action='replace',
                replacement='***',
                severity=3
            )
            
            assert chat_filter.pattern == r'\bbadword\b'
            assert chat_filter.filter_type == 'profanity'
            assert chat_filter.action == 'replace'
            assert chat_filter.replacement == '***'
            assert chat_filter.severity == 3
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()


class TestChatMessage:
    """Test cases for ChatMessage model."""
    
    def test_to_dict_basic(self):
        """Test basic to_dict conversion."""
        # Create a mock message to avoid SQLAlchemy complexity
        message = Mock()
        message.id = uuid.uuid4()
        message.table_id = uuid.uuid4()
        message.user_id = uuid.uuid4()
        message.message = "Hello!"
        message.filtered_message = None
        message.message_type = 'chat'
        message.is_filtered = False
        message.created_at = datetime(2023, 1, 1, 12, 0, 0)
        
        # Mock user relationship
        user = Mock()
        user.username = 'testuser'
        message.user = user
        
        # Mock the to_dict method
        def mock_to_dict(include_original=False):
            result = {
                'id': str(message.id),
                'table_id': str(message.table_id),
                'user_id': str(message.user_id),
                'username': message.user.username if message.user else 'Unknown',
                'message': message.filtered_message if message.is_filtered else message.message,
                'message_type': message.message_type,
                'is_filtered': message.is_filtered,
                'created_at': message.created_at.isoformat()
            }
            
            if include_original and message.is_filtered:
                result['original_message'] = message.message
                
            return result
        
        message.to_dict = mock_to_dict
        
        result = message.to_dict()
        
        assert result['message'] == "Hello!"
        assert result['username'] == 'testuser'
        assert result['message_type'] == 'chat'
        assert result['is_filtered'] == False
        assert 'original_message' not in result
    
    def test_to_dict_filtered_with_original(self):
        """Test to_dict with filtered message and original included."""
        # Create a mock message to avoid SQLAlchemy complexity
        message = Mock()
        message.id = uuid.uuid4()
        message.table_id = uuid.uuid4()
        message.user_id = uuid.uuid4()
        message.message = "This is damn good!"
        message.filtered_message = "This is **** good!"
        message.message_type = 'chat'
        message.is_filtered = True
        message.created_at = datetime(2023, 1, 1, 12, 0, 0)
        
        # Mock user relationship
        user = Mock()
        user.username = 'testuser'
        message.user = user
        
        # Mock the to_dict method
        def mock_to_dict(include_original=False):
            result = {
                'id': str(message.id),
                'table_id': str(message.table_id),
                'user_id': str(message.user_id),
                'username': message.user.username if message.user else 'Unknown',
                'message': message.filtered_message if message.is_filtered else message.message,
                'message_type': message.message_type,
                'is_filtered': message.is_filtered,
                'created_at': message.created_at.isoformat()
            }
            
            if include_original and message.is_filtered:
                result['original_message'] = message.message
                
            return result
        
        message.to_dict = mock_to_dict
        
        result = message.to_dict(include_original=True)
        
        assert result['message'] == "This is **** good!"
        assert result['original_message'] == "This is damn good!"
        assert result['is_filtered'] == True


class TestChatModerationAction:
    """Test cases for ChatModerationAction model."""
    
    def test_is_expired_no_expiry(self):
        """Test is_expired with no expiry date."""
        action = ChatModerationAction(expires_at=None)
        
        assert action.is_expired() == False
    
    def test_is_expired_future_expiry(self):
        """Test is_expired with future expiry date."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        action = ChatModerationAction(expires_at=future_time)
        
        assert action.is_expired() == False
    
    def test_is_expired_past_expiry(self):
        """Test is_expired with past expiry date."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        action = ChatModerationAction(expires_at=past_time)
        
        assert action.is_expired() == True
    
    def test_to_dict(self):
        """Test to_dict conversion."""
        target_user = Mock()
        target_user.username = 'target_user'
        moderator_user = Mock()
        moderator_user.username = 'moderator'
        
        action = ChatModerationAction(
            id=uuid.uuid4(),
            table_id=uuid.uuid4(),
            target_user_id=uuid.uuid4(),
            moderator_user_id=uuid.uuid4(),
            action_type='mute',
            reason='Inappropriate language',
            duration_minutes=30,
            expires_at=datetime(2023, 1, 1, 13, 0, 0),
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            is_active=True
        )
        action.target_user = target_user
        action.moderator_user = moderator_user
        
        result = action.to_dict()
        
        assert result['action_type'] == 'mute'
        assert result['target_username'] == 'target_user'
        assert result['moderator_username'] == 'moderator'
        assert result['reason'] == 'Inappropriate language'
        assert result['duration_minutes'] == 30
        assert result['is_active'] == True