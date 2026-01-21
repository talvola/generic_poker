"""Chat system models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import Dict, Any, Optional

from ..database import db


class ChatMessage(db.Model):
    """Model for chat messages."""
    
    __tablename__ = 'chat_messages'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(UUID(as_uuid=True), ForeignKey('poker_tables.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    message = Column(Text, nullable=False)
    filtered_message = Column(Text, nullable=True)  # Message after filtering
    message_type = Column(String(50), nullable=False, default='chat')  # chat, system, action
    is_filtered = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    table = relationship("PokerTable", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")
    
    def to_dict(self, include_original: bool = False) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Args:
            include_original: Whether to include original unfiltered message

        Returns:
            Dictionary representation
        """
        # Get username - try relationship first, then fall back to query
        username = 'Unknown'
        if self.user:
            username = self.user.username
        elif self.user_id:
            # Lazy-load user if relationship not loaded
            # Convert UUID to string for query comparison
            from ..database import db
            from .user import User
            user_id_str = str(self.user_id)
            user = db.session.query(User).filter(User.id == user_id_str).first()
            if user:
                username = user.username

        result = {
            'id': str(self.id),
            'table_id': str(self.table_id),
            'user_id': str(self.user_id),
            'username': username,
            'message': self.filtered_message if self.is_filtered else self.message,
            'message_type': self.message_type,
            'is_filtered': self.is_filtered,
            'created_at': self.created_at.isoformat()
        }
        
        if include_original and self.is_filtered:
            result['original_message'] = self.message
            
        return result


class ChatModerationAction(db.Model):
    """Model for chat moderation actions."""
    
    __tablename__ = 'chat_moderation_actions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id = Column(UUID(as_uuid=True), ForeignKey('poker_tables.id'), nullable=False)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    moderator_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)  # None for auto-moderation
    action_type = Column(String(50), nullable=False)  # mute, unmute, ban, unban, warn
    reason = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=True)  # None for permanent
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    table = relationship("PokerTable")
    target_user = relationship("User", foreign_keys=[target_user_id])
    moderator_user = relationship("User", foreign_keys=[moderator_user_id])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': str(self.id),
            'table_id': str(self.table_id),
            'target_user_id': str(self.target_user_id),
            'target_username': self.target_user.username if self.target_user else 'Unknown',
            'moderator_user_id': str(self.moderator_user_id) if self.moderator_user_id else None,
            'moderator_username': self.moderator_user.username if self.moderator_user else 'System',
            'action_type': self.action_type,
            'reason': self.reason,
            'duration_minutes': self.duration_minutes,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }
    
    def is_expired(self) -> bool:
        """Check if the moderation action has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at


class ChatFilter(db.Model):
    """Model for chat filter words and patterns."""
    
    __tablename__ = 'chat_filters'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern = Column(String(255), nullable=False, unique=True)
    filter_type = Column(String(50), nullable=False)  # profanity, spam, inappropriate
    action = Column(String(50), nullable=False)  # block, replace, warn
    replacement = Column(String(255), nullable=True)  # Replacement text for 'replace' action
    severity = Column(Integer, nullable=False, default=1)  # 1-5, higher is more severe
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': str(self.id),
            'pattern': self.pattern,
            'filter_type': self.filter_type,
            'action': self.action,
            'replacement': self.replacement,
            'severity': self.severity,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }