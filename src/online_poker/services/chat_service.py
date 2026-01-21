"""Chat service for handling table chat functionality."""

import re
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from ..models.chat import ChatMessage, ChatModerationAction, ChatFilter
from ..models.user import User
from ..models.table import PokerTable
from ..database import db


class ChatService:
    """Service for managing table chat functionality."""
    
    def __init__(self):
        """Initialize chat service."""
        self._profanity_patterns = [
            r'\b(damn|hell|crap)\b',  # Mild profanity
            r'\b(shit|fuck|bitch|ass)\b',  # Strong profanity
            r'\b(nigger|faggot|retard)\b',  # Slurs
        ]
        self._spam_patterns = [
            r'(.)\1{4,}',  # Repeated characters (5+ same chars in a row)
            r'^[A-Z\s!]+$',  # All caps messages (no lowercase letters allowed)
            r'(http|www\.)',  # URLs
        ]
        
    def send_message(self, table_id: uuid.UUID, user_id: uuid.UUID, 
                    message: str, message_type: str = 'chat') -> Optional[ChatMessage]:
        """Send a chat message to a table.
        
        Args:
            table_id: ID of the table
            user_id: ID of the user sending the message
            message: Message content
            message_type: Type of message (chat, system, action)
            
        Returns:
            ChatMessage if successful, None if blocked
        """
        # Check if user is muted
        if self.is_user_muted(table_id, user_id):
            return None
            
        # Filter message content
        filtered_message, is_filtered = self._filter_message(message)
        
        # Block message if it's completely inappropriate
        if filtered_message is None:
            return None
            
        # Create chat message
        chat_message = ChatMessage(
            table_id=table_id,
            user_id=user_id,
            message=message,
            filtered_message=filtered_message if is_filtered else None,
            message_type=message_type,
            is_filtered=is_filtered
        )

        db.session.add(chat_message)
        db.session.commit()

        # Refresh to load relationships (user, table)
        db.session.refresh(chat_message)

        return chat_message
    
    def get_table_messages(self, table_id: uuid.UUID, limit: int = 50, 
                          include_system: bool = True) -> List[ChatMessage]:
        """Get recent messages for a table.
        
        Args:
            table_id: ID of the table
            limit: Maximum number of messages to return
            include_system: Whether to include system messages
            
        Returns:
            List of chat messages
        """
        query = db.session.query(ChatMessage).filter(
            ChatMessage.table_id == table_id,
            ChatMessage.is_deleted == False
        )
        
        if not include_system:
            query = query.filter(ChatMessage.message_type == 'chat')
            
        return query.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    
    def mute_user(self, table_id: uuid.UUID, target_user_id: uuid.UUID,
                  moderator_user_id: Optional[uuid.UUID] = None,
                  duration_minutes: Optional[int] = None,
                  reason: Optional[str] = None) -> ChatModerationAction:
        """Mute a user in a table.
        
        Args:
            table_id: ID of the table
            target_user_id: ID of the user to mute
            moderator_user_id: ID of the moderator (None for system)
            duration_minutes: Duration of mute (None for permanent)
            reason: Reason for muting
            
        Returns:
            ChatModerationAction record
        """
        # Deactivate any existing mute actions
        existing_mutes = db.session.query(ChatModerationAction).filter(
            ChatModerationAction.table_id == table_id,
            ChatModerationAction.target_user_id == target_user_id,
            ChatModerationAction.action_type == 'mute',
            ChatModerationAction.is_active == True
        ).all()
        
        for mute in existing_mutes:
            mute.is_active = False
            
        # Create new mute action
        expires_at = None
        if duration_minutes:
            expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)
            
        mute_action = ChatModerationAction(
            table_id=table_id,
            target_user_id=target_user_id,
            moderator_user_id=moderator_user_id,
            action_type='mute',
            reason=reason,
            duration_minutes=duration_minutes,
            expires_at=expires_at,
            is_active=True
        )
        
        db.session.add(mute_action)
        db.session.commit()
        
        return mute_action
    
    def unmute_user(self, table_id: uuid.UUID, target_user_id: uuid.UUID,
                   moderator_user_id: Optional[uuid.UUID] = None) -> Optional[ChatModerationAction]:
        """Unmute a user in a table.
        
        Args:
            table_id: ID of the table
            target_user_id: ID of the user to unmute
            moderator_user_id: ID of the moderator
            
        Returns:
            ChatModerationAction record if successful
        """
        # Deactivate existing mute actions
        existing_mutes = db.session.query(ChatModerationAction).filter(
            ChatModerationAction.table_id == table_id,
            ChatModerationAction.target_user_id == target_user_id,
            ChatModerationAction.action_type == 'mute',
            ChatModerationAction.is_active == True
        ).all()
        
        if not existing_mutes:
            return None
            
        for mute in existing_mutes:
            mute.is_active = False
            
        # Create unmute action
        unmute_action = ChatModerationAction(
            table_id=table_id,
            target_user_id=target_user_id,
            moderator_user_id=moderator_user_id,
            action_type='unmute',
            reason='Manual unmute',
            is_active=True
        )
        
        db.session.add(unmute_action)
        db.session.commit()
        
        return unmute_action
    
    def is_user_muted(self, table_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Check if a user is currently muted in a table.
        
        Args:
            table_id: ID of the table
            user_id: ID of the user
            
        Returns:
            True if user is muted
        """
        active_mutes = db.session.query(ChatModerationAction).filter(
            ChatModerationAction.table_id == table_id,
            ChatModerationAction.target_user_id == user_id,
            ChatModerationAction.action_type == 'mute',
            ChatModerationAction.is_active == True
        ).all()
        
        # Check if any mutes are still valid
        for mute in active_mutes:
            if not mute.is_expired():
                return True
            else:
                # Deactivate expired mute
                mute.is_active = False
                
        if db.session.dirty:
            db.session.commit()
        return False
    
    def get_moderation_actions(self, table_id: uuid.UUID, 
                             limit: int = 100) -> List[ChatModerationAction]:
        """Get moderation actions for a table.
        
        Args:
            table_id: ID of the table
            limit: Maximum number of actions to return
            
        Returns:
            List of moderation actions
        """
        return db.session.query(ChatModerationAction).filter(
            ChatModerationAction.table_id == table_id
        ).order_by(ChatModerationAction.created_at.desc()).limit(limit).all()
    
    def _filter_message(self, message: str) -> tuple[Optional[str], bool]:
        """Filter message content for inappropriate content.
        
        Args:
            message: Original message
            
        Returns:
            Tuple of (filtered_message, is_filtered)
            Returns (None, True) if message should be blocked
        """
        if not message or not message.strip():
            return None, True
            
        filtered_message = message
        is_filtered = False
        
        # Check for spam patterns first (these block the message)
        # Note: Don't use IGNORECASE here - the all-caps pattern needs case-sensitivity
        for pattern in self._spam_patterns:
            if re.search(pattern, message):
                # Block spam messages entirely
                return None, True
                
        # Check message length
        if len(message) > 500:
            return None, True
        
        # Check for profanity (these filter but don't block)
        for pattern in self._profanity_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                # Replace with asterisks
                filtered_message = re.sub(pattern, lambda m: '*' * len(m.group()), 
                                        filtered_message, flags=re.IGNORECASE)
                is_filtered = True
            
        return filtered_message, is_filtered
    
    def add_filter_word(self, pattern: str, filter_type: str = 'profanity',
                       action: str = 'replace', replacement: str = None,
                       severity: int = 1) -> ChatFilter:
        """Add a new chat filter.
        
        Args:
            pattern: Regex pattern to match
            filter_type: Type of filter (profanity, spam, inappropriate)
            action: Action to take (block, replace, warn)
            replacement: Replacement text for replace action
            severity: Severity level (1-5)
            
        Returns:
            ChatFilter record
        """
        chat_filter = ChatFilter(
            pattern=pattern,
            filter_type=filter_type,
            action=action,
            replacement=replacement,
            severity=severity
        )
        
        db.session.add(chat_filter)
        db.session.commit()
        
        return chat_filter
    
    def get_chat_filters(self, active_only: bool = True) -> List[ChatFilter]:
        """Get all chat filters.
        
        Args:
            active_only: Whether to return only active filters
            
        Returns:
            List of chat filters
        """
        query = db.session.query(ChatFilter)
        
        if active_only:
            query = query.filter(ChatFilter.is_active == True)
            
        return query.order_by(ChatFilter.severity.desc()).all()