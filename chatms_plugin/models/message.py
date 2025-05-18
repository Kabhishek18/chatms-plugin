"""
Message models for the ChatMS plugin.
"""

import datetime
from typing import Dict, List, Optional, Set, Union

from pydantic import Field, validator

from ..config import MessageStatus, MessageType
from .base import DatabaseModel


class Reaction(DatabaseModel):
    """Model for message reactions."""
    
    user_id: str
    reaction_type: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


class Attachment(DatabaseModel):
    """Model for message attachments."""
    
    file_name: str
    file_size: int
    file_type: str
    file_url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None  # For images and videos
    height: Optional[int] = None  # For images and videos
    duration: Optional[int] = None  # For audio and video (in seconds)
    metadata: Dict[str, Union[str, int, float, bool, List, Dict]] = Field(default_factory=dict)


class Mention(DatabaseModel):
    """Model for user mentions in messages."""
    
    user_id: str
    offset: int  # Position in the message text
    length: int  # Length of the mention in the message text


class Message(DatabaseModel):
    """Model for chat messages."""
    
    chat_id: str
    sender_id: str
    content: str
    message_type: MessageType = MessageType.TEXT
    status: MessageStatus = MessageStatus.SENDING
    
    # Optional fields
    reply_to_id: Optional[str] = None
    forwarded_from_id: Optional[str] = None
    edited_at: Optional[datetime.datetime] = None
    delivered_at: Optional[datetime.datetime] = None
    read_at: Optional[datetime.datetime] = None
    
    # Metadata
    is_pinned: bool = False
    is_deleted: bool = False
    delete_for_everyone: bool = False
    
    # Related data
    attachments: List[Attachment] = Field(default_factory=list)
    reactions: List[Reaction] = Field(default_factory=list)
    mentions: List[Mention] = Field(default_factory=list)
    
    # Additional metadata
    metadata: Dict[str, Union[str, int, bool, List, Dict]] = Field(default_factory=dict)
    
    @validator("content")
    def content_not_empty_if_text(cls, v, values):
        """Validate that text messages have non-empty content."""
        message_type = values.get("message_type", MessageType.TEXT)
        if message_type == MessageType.TEXT and not v:
            raise ValueError("Text messages must have non-empty content")
        return v


class MessageCreate(DatabaseModel):
    """Model for creating a new message."""
    
    chat_id: str
    content: str
    message_type: MessageType = MessageType.TEXT
    reply_to_id: Optional[str] = None
    mentions: List[str] = Field(default_factory=list)  # List of user IDs
    
    @validator("content")
    def content_not_empty_if_text(cls, v, values):
        """Validate that text messages have non-empty content."""
        message_type = values.get("message_type", MessageType.TEXT)
        if message_type == MessageType.TEXT and not v:
            raise ValueError("Text messages must have non-empty content")
        return v


class MessageUpdate(DatabaseModel):
    """Model for updating an existing message."""
    
    content: Optional[str] = None
    is_pinned: Optional[bool] = None
    metadata: Optional[Dict[str, Union[str, int, bool, List, Dict]]] = None
    
    @validator("content")
    def content_not_empty(cls, v):
        """Validate that content is not empty if provided."""
        if v is not None and not v:
            raise ValueError("Content cannot be empty")
        return v


class MessageDelete(DatabaseModel):
    """Model for deleting a message."""
    
    message_id: str
    delete_for_everyone: bool = False


class MessageReaction(DatabaseModel):
    """Model for adding a reaction to a message."""
    
    message_id: str
    reaction_type: str


class MessageRead(DatabaseModel):
    """Model for marking messages as read."""
    
    chat_id: str
    message_ids: List[str] = Field(default_factory=list)
    read_until_id: Optional[str] = None  # Mark all messages up to this ID as read


class MessageDelivery(DatabaseModel):
    """Model for message delivery status updates."""
    
    message_id: str
    status: MessageStatus
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)
    error_message: Optional[str] = None