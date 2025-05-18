"""
Abstract database interface for the ChatMS plugin.
"""

import abc
from typing import Any, Dict, List, Optional, TypeVar, Generic

from ..models.base import DatabaseModel
from ..models.user import User
from ..models.chat import Chat
from ..models.message import Message, Reaction

T = TypeVar('T', bound=DatabaseModel)


class DatabaseHandler(abc.ABC):
    """Abstract base class for database handlers.
    
    This defines the interface that all database implementations must follow.
    """
    
    @abc.abstractmethod
    async def init(self) -> None:
        """Initialize the database connection."""
        pass
    
    @abc.abstractmethod
    async def close(self) -> None:
        """Close the database connection."""
        pass
    
    # Generic CRUD operations
    @abc.abstractmethod
    async def create(self, model: T) -> T:
        """Create a new record in the database."""
        pass
    
    @abc.abstractmethod
    async def get(self, collection: str, id: str) -> Optional[Dict[str, Any]]:
        """Get a record by ID."""
        pass
    
    @abc.abstractmethod
    async def update(self, collection: str, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record by ID."""
        pass
    
    @abc.abstractmethod
    async def delete(self, collection: str, id: str) -> bool:
        """Delete a record by ID."""
        pass
    
    @abc.abstractmethod
    async def list(self, collection: str, filters: Dict[str, Any] = None, 
                   skip: int = 0, limit: int = 100, 
                   sort: Dict[str, int] = None) -> List[Dict[str, Any]]:
        """List records with optional filtering, pagination, and sorting."""
        pass
    
    @abc.abstractmethod
    async def count(self, collection: str, filters: Dict[str, Any] = None) -> int:
        """Count records with optional filtering."""
        pass
    
    # User operations
    @abc.abstractmethod
    async def create_user(self, user: User) -> User:
        """Create a new user."""
        pass
    
    @abc.abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        pass
    
    @abc.abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        pass
    
    @abc.abstractmethod
    async def update_user(self, user_id: str, data: Dict[str, Any]) -> Optional[User]:
        """Update a user."""
        pass
    
    @abc.abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        pass
    
    # Chat operations
    @abc.abstractmethod
    async def create_chat(self, chat: Chat) -> Chat:
        """Create a new chat."""
        pass
    
    @abc.abstractmethod
    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        """Get a chat by ID."""
        pass
    
    @abc.abstractmethod
    async def update_chat(self, chat_id: str, data: Dict[str, Any]) -> Optional[Chat]:
        """Update a chat."""
        pass
    
    @abc.abstractmethod
    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat."""
        pass
    
    @abc.abstractmethod
    async def get_user_chats(self, user_id: str, 
                             skip: int = 0, limit: int = 100) -> List[Chat]:
        """Get all chats for a user."""
        pass
    
    @abc.abstractmethod
    async def add_chat_member(self, chat_id: str, user_id: str, role: str) -> bool:
        """Add a member to a chat."""
        pass
    
    @abc.abstractmethod
    async def remove_chat_member(self, chat_id: str, user_id: str) -> bool:
        """Remove a member from a chat."""
        pass
    
    @abc.abstractmethod
    async def get_chat_members(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get all members of a chat."""
        pass
    
    # Message operations
    @abc.abstractmethod
    async def create_message(self, message: Message) -> Message:
        """Create a new message."""
        pass
    
    @abc.abstractmethod
    async def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        pass
    
    @abc.abstractmethod
    async def update_message(self, message_id: str, data: Dict[str, Any]) -> Optional[Message]:
        """Update a message."""
        pass
    
    @abc.abstractmethod
    async def delete_message(self, message_id: str, delete_for_everyone: bool = False) -> bool:
        """Delete a message."""
        pass
    
    @abc.abstractmethod
    async def get_chat_messages(self, chat_id: str, 
                               before_id: Optional[str] = None,
                               after_id: Optional[str] = None,
                               skip: int = 0, limit: int = 50) -> List[Message]:
        """Get messages for a chat with pagination."""
        pass
    
    @abc.abstractmethod
    async def get_message_count(self, chat_id: str, since: Optional[str] = None) -> int:
        """Get the number of messages in a chat since a specific time."""
        pass
    
    # Reaction operations
    @abc.abstractmethod
    async def add_reaction(self, message_id: str, user_id: str, reaction_type: str) -> Optional[Reaction]:
        """Add a reaction to a message."""
        pass
    
    @abc.abstractmethod
    async def remove_reaction(self, message_id: str, user_id: str, reaction_type: str) -> bool:
        """Remove a reaction from a message."""
        pass
    
    @abc.abstractmethod
    async def get_message_reactions(self, message_id: str) -> List[Reaction]:
        """Get all reactions for a message."""
        pass
    
    # Search operations
    @abc.abstractmethod
    async def search_messages(self, query: str, user_id: str, 
                             chat_id: Optional[str] = None,
                             skip: int = 0, limit: int = 20) -> List[Message]:
        """Search for messages."""
        pass
    
    # Stats and aggregation
    @abc.abstractmethod
    async def get_chat_stats(self, chat_id: str) -> Dict[str, Any]:
        """Get statistics for a chat."""
        pass
    
    @abc.abstractmethod
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user."""
        pass