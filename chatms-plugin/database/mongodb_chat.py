"""
MongoDB database handler for the ChatMS plugin - Chat operations.
"""

import logging
from typing import Any, Dict, List, Optional

from ..config import UserRole
from ..exceptions import DatabaseError
from ..models.chat import Chat
from .mongodb_base import MongoDBHandler


logger = logging.getLogger(__name__)


class MongoDBChatHandler(MongoDBHandler):
    """MongoDB handler for chat operations."""
    
    async def create_chat(self, chat: Chat) -> Chat:
        """Create a new chat.
        
        Args:
            chat: The chat to create
            
        Returns:
            Chat: The created chat
            
        Raises:
            DatabaseError: If there was an error creating the chat
        """
        return await self.create(chat)
    
    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        """Get a chat by ID.
        
        Args:
            chat_id: The chat ID
            
        Returns:
            Optional[Chat]: The chat, or None if not found
            
        Raises:
            DatabaseError: If there was an error retrieving the chat
        """
        chat_data = await self.get("chats", chat_id)
        
        if not chat_data:
            return None
        
        return Chat.from_db_dict(chat_data)
    
    async def update_chat(self, chat_id: str, data: Dict[str, Any]) -> Optional[Chat]:
        """Update a chat.
        
        Args:
            chat_id: The chat ID
            data: The data to update
            
        Returns:
            Optional[Chat]: The updated chat, or None if not found
            
        Raises:
            DatabaseError: If there was an error updating the chat
        """
        chat_data = await self.update("chats", chat_id, data)
        
        if not chat_data:
            return None
        
        return Chat.from_db_dict(chat_data)
    
    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat.
        
        Args:
            chat_id: The chat ID
            
        Returns:
            bool: True if the chat was deleted, False otherwise
            
        Raises:
            DatabaseError: If there was an error deleting the chat
        """
        # Delete all messages in the chat
        try:
            await self.db.messages.delete_many({"chat_id": chat_id})
        except Exception as e:
            logger.error(f"Failed to delete messages for chat {chat_id}: {e}")
        
        # Delete the chat
        return await self.delete("chats", chat_id)
    
    async def get_user_chats(self, user_id: str, 
                             skip: int = 0, limit: int = 100) -> List[Chat]:
        """Get all chats for a user.
        
        Args:
            user_id: The user ID
            skip: Number of chats to skip
            limit: Maximum number of chats to return
            
        Returns:
            List[Chat]: The user's chats
            
        Raises:
            DatabaseError: If there was an error retrieving the chats
        """
        try:
            # Find chats where user is a member
            chats_data = await self.list(
                collection="chats",
                filters={"members.user_id": user_id},
                skip=skip,
                limit=limit,
                sort={"updated_at": -1}
            )
            
            # Convert to Chat objects
            return [Chat.from_db_dict(chat_data) for chat_data in chats_data]
            
        except Exception as e:
            raise DatabaseError(f"Failed to get user chats: {e}")
    
    async def add_chat_member(self, chat_id: str, user_id: str, role: str) -> bool:
        """Add a member to a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            role: The user's role
            
        Returns:
            bool: True if the member was added, False otherwise
            
        Raises:
            DatabaseError: If there was an error adding the member
        """
        try:
            # Get chat
            chat = await self.get_chat(chat_id)
            
            if not chat:
                return False
            
            # Check if user is already a member
            if chat.is_member(user_id):
                return True
            
            # Add member
            chat.add_member(user_id, UserRole(role))
            
            # Update chat
            updated_chat = await self.update_chat(chat_id, {"members": [m.dict() for m in chat.members]})
            
            return updated_chat is not None
            
        except Exception as e:
            raise DatabaseError(f"Failed to add chat member: {e}")
    
    async def remove_chat_member(self, chat_id: str, user_id: str) -> bool:
        """Remove a member from a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            
        Returns:
            bool: True if the member was removed, False otherwise
            
        Raises:
            DatabaseError: If there was an error removing the member
        """
        try:
            # Get chat
            chat = await self.get_chat(chat_id)
            
            if not chat:
                return False
            
            # Check if user is a member
            if not chat.is_member(user_id):
                return True
            
            # Remove member
            chat.remove_member(user_id)
            
            # Update chat
            updated_chat = await self.update_chat(chat_id, {"members": [m.dict() for m in chat.members]})
            
            return updated_chat is not None
            
        except Exception as e:
            raise DatabaseError(f"Failed to remove chat member: {e}")
    
    async def get_chat_members(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get all members of a chat.
        
        Args:
            chat_id: The chat ID
            
        Returns:
            List[Dict[str, Any]]: The chat members
            
        Raises:
            DatabaseError: If there was an error retrieving the members
        """
        try:
            # Get chat
            chat = await self.get_chat(chat_id)
            
            if not chat:
                return []
            
            # Get member details
            members = []
            
            for member in chat.members:
                user_data = await self.get("users", member.user_id)
                if user_data:
                    members.append({
                        "user_id": member.user_id,
                        "role": member.role,
                        "username": user_data.get("username"),
                        "full_name": user_data.get("full_name"),
                        "avatar_url": user_data.get("avatar_url"),
                        "joined_at": member.joined_at.isoformat(),
                        "is_muted": member.is_muted,
                        "last_read_message_id": member.last_read_message_id,
                        "typing_at": member.typing_at.isoformat() if member.typing_at else None
                    })
            
            return members
            
        except Exception as e:
            raise DatabaseError(f"Failed to get chat members: {e}")
    
    async def search_chats(self, query: str, user_id: str, 
                          skip: int = 0, limit: int = 20) -> List[Chat]:
        """Search for chats by name or description.
        
        Args:
            query: The search query
            user_id: The user ID (to limit results to chats the user is a member of)
            skip: Number of chats to skip
            limit: Maximum number of chats to return
            
        Returns:
            List[Chat]: The matching chats
            
        Raises:
            DatabaseError: If there was an error searching for chats
        """
        try:
            # Create text index for name and description
            try:
                await self.db.chats.create_index([("name", "text"), ("description", "text")])
            except Exception:
                pass
            
            # Build search query
            search_query = {
                "$and": [
                    {"members.user_id": user_id},
                    {"$text": {"$search": query}}
                ]
            }
            
            # Search chats
            chats_data = await self.list(
                collection="chats",
                filters=search_query,
                skip=skip,
                limit=limit,
                sort={"score": {"$meta": "textScore"}}
            )
            
            return [Chat.from_db_dict(chat_data) for chat_data in chats_data]
            
        except Exception as e:
            raise DatabaseError(f"Failed to search chats: {e}")