"""
User models for the ChatMS plugin.
"""

import datetime
from typing import Dict, List, Optional, Union

from pydantic import EmailStr, Field, validator

from ..config import UserRole
from .base import DatabaseModel


class User(DatabaseModel):
    """User model for chat system users."""
    
    username: str
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    last_seen: Optional[datetime.datetime] = None
    status: str = "offline"
    avatar_url: Optional[str] = None
    is_active: bool = True
    
    @validator("username")
    def username_alphanumeric(cls, v):
        """Validate that username contains only alphanumeric characters and underscores."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v


class UserCreate(DatabaseModel):
    """Model for creating a new user."""
    
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    
    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v
    
    @validator("username")
    def username_alphanumeric(cls, v):
        """Validate that username contains only alphanumeric characters and underscores."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v


class UserUpdate(DatabaseModel):
    """Model for updating an existing user."""
    
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    avatar_url: Optional[str] = None
    
    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserInChat(DatabaseModel):
    """Model for a user in a chat with role information."""
    
    user_id: str
    role: UserRole = UserRole.MEMBER
    joined_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    is_muted: bool = False
    last_read_message_id: Optional[str] = None
    typing_at: Optional[datetime.datetime] = None


class UserPresence(DatabaseModel):
    """Model for user presence information."""
    
    user_id: str
    status: str
    last_seen: datetime.datetime = Field(default_factory=datetime.datetime.now)
    device_info: Optional[Dict[str, str]] = None
    is_typing: bool = False
    typing_in_chat_id: Optional[str] = None