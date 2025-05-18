"""
Chat models for the ChatMS plugin.
"""

import datetime
from typing import Dict, List, Optional, Set, Union

from pydantic import Field, validator

from ..config import ChatType, UserRole
from .base import DatabaseModel
from .user import UserInChat


class Chat(DatabaseModel):
    """Chat model for all types of chats (one-to-one, group, etc.)."""
    
    name: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    chat_type: ChatType
    members: List[UserInChat] = []
    is_encrypted: bool = False
    metadata: Dict[str, Union[str, int, bool, List, Dict]] = Field(default_factory=dict)
    
    @validator("name", always=True)
    def validate_name(cls, v, values):
        """Ensure one-to-one chats don't require names."""
        chat_type = values.get("chat_type")
        if chat_type == ChatType.ONE_TO_ONE and v is None:
            return "Direct Message"
        elif chat_type != ChatType.ONE_TO_ONE and not v:
            raise ValueError("Name is required for non-one-to-one chats")
        return v
    
    def add_member(self, user_id: str, role: UserRole = UserRole.MEMBER) -> "Chat":
        """Add a member to the chat."""
        # Check if user is already a member
        for member in self.members:
            if member.user_id == user_id:
                member.role = role  # Update role if already a member
                return self
        
        # Add new member
        self.members.append(UserInChat(user_id=user_id, role=role))
        return self
    
    def remove_member(self, user_id: str) -> "Chat":
        """Remove a member from the chat."""
        self.members = [m for m in self.members if m.user_id != user_id]
        return self
    
    def is_member(self, user_id: str) -> bool:
        """Check if a user is a member of the chat."""
        return any(m.user_id == user_id for m in self.members)
    
    def get_member_role(self, user_id: str) -> Optional[UserRole]:
        """Get the role of a member in the chat."""
        for member in self.members:
            if member.user_id == user_id:
                return member.role
        return None
    
    def is_admin(self, user_id: str) -> bool:
        """Check if a user is an admin of the chat."""
        return self.get_member_role(user_id) == UserRole.ADMIN
    
    def get_member_ids(self) -> List[str]:
        """Get a list of all member IDs."""
        return [member.user_id for member in self.members]


class ChatCreate(DatabaseModel):
    """Model for creating a new chat."""
    
    name: Optional[str] = None
    description: Optional[str] = None
    chat_type: ChatType
    member_ids: List[str]
    is_encrypted: bool = False
    icon_url: Optional[str] = None
    metadata: Dict[str, Union[str, int, bool, List, Dict]] = Field(default_factory=dict)
    
    @validator("member_ids")
    def validate_members(cls, v, values):
        """Validate member IDs based on chat type."""
        chat_type = values.get("chat_type")
        
        if chat_type == ChatType.ONE_TO_ONE and len(v) != 2:
            raise ValueError("One-to-one chats must have exactly 2 members")
        elif chat_type != ChatType.ONE_TO_ONE and len(v) < 1:
            raise ValueError("Chat must have at least 1 member")
        
        # Ensure no duplicate members
        if len(v) != len(set(v)):
            raise ValueError("Duplicate member IDs are not allowed")
            
        return v


class ChatUpdate(DatabaseModel):
    """Model for updating an existing chat."""
    
    name: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    is_encrypted: Optional[bool] = None
    metadata: Optional[Dict[str, Union[str, int, bool, List, Dict]]] = None


class ChatMember(DatabaseModel):
    """Model for adding or updating a chat member."""
    
    user_id: str
    role: UserRole = UserRole.MEMBER
    is_muted: bool = False


class ChatSettings(DatabaseModel):
    """Model for chat settings."""
    
    chat_id: str
    user_id: str
    muted: bool = False
    pinned: bool = False
    notifications_enabled: bool = True
    custom_name: Optional[str] = None
    theme: Optional[str] = None
    notification_sound: Optional[str] = None