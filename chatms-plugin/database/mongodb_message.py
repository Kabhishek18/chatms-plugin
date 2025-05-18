"""
MongoDB database handler for the ChatMS plugin - Message operations.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from ..exceptions import DatabaseError
from ..models.message import Message, Reaction
from .mongodb_base import MongoDBHandler


logger = logging.getLogger(__name__)


class MongoDBMessageHandler(MongoDBHandler):
    """MongoDB handler for message operations."""
    
    async def create_message(self, message: Message) -> Message:
        """Create a new message.
        
        Args:
            message: The message to create
            
        Returns:
            Message: The created message
            
        Raises:
            DatabaseError: If there was an error creating the message
        """
        # Create message
        created_message = await self.create(message)
        
        try:
            # Update chat's updated_at
            await self.db.chats.update_one(
                {"_id": self._convert_id(message.chat_id)},
                {"$set": {"updated_at": datetime.datetime.now()}}
            )
        except Exception as e:
            logger.error(f"Failed to update chat updated_at: {e}")
        
        return created_message
    
    async def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message by ID.
        
        Args:
            message_id: The message ID
            
        Returns:
            Optional[Message]: The message, or None if not found
            
        Raises:
            DatabaseError: If there was an error retrieving the message
        """
        message_data = await self.get("messages", message_id)
        
        if not message_data:
            return None
        
        return Message.from_db_dict(message_data)
    
    async def update_message(self, message_id: str, data: Dict[str, Any]) -> Optional[Message]:
        """Update a message.
        
        Args:
            message_id: The message ID
            data: The data to update
            
        Returns:
            Optional[Message]: The updated message, or None if not found
            
        Raises:
            DatabaseError: If there was an error updating the message
        """
        message_data = await self.update("messages", message_id, data)
        
        if not message_data:
            return None
        
        return Message.from_db_dict(message_data)
    
    async def delete_message(self, message_id: str, delete_for_everyone: bool = False) -> bool:
        """Delete a message.
        
        Args:
            message_id: The message ID
            delete_for_everyone: Whether to delete for everyone or just mark as deleted
            
        Returns:
            bool: True if the message was deleted, False otherwise
            
        Raises:
            DatabaseError: If there was an error deleting the message
        """
        try:
            # If delete_for_everyone, actually delete the message
            if delete_for_everyone:
                return await self.delete("messages", message_id)
            
            # Otherwise, just mark as deleted
            message_data = await self.update(
                "messages",
                message_id,
                {
                    "is_deleted": True,
                    "delete_for_everyone": False,
                    "content": "",  # Clear content
                    "attachments": []  # Clear attachments
                }
            )
            
            return message_data is not None
            
        except Exception as e:
            raise DatabaseError(f"Failed to delete message: {e}")
    
    async def get_chat_messages(self, chat_id: str, 
                               before_id: Optional[str] = None,
                               after_id: Optional[str] = None,
                               skip: int = 0, limit: int = 50) -> List[Message]:
        """Get messages for a chat with pagination.
        
        Args:
            chat_id: The chat ID
            before_id: Get messages before this ID
            after_id: Get messages after this ID
            skip: Number of messages to skip
            limit: Maximum number of messages to return
            
        Returns:
            List[Message]: The messages
            
        Raises:
            DatabaseError: If there was an error retrieving the messages
        """
        try:
            # Base query
            query = {"chat_id": chat_id}
            
            # Add before/after constraints
            if before_id:
                before_message = await self.get_message(before_id)
                if before_message:
                    query["created_at"] = {"$lt": before_message.created_at}
            
            if after_id:
                after_message = await self.get_message(after_id)
                if after_message:
                    query["created_at"] = {"$gt": after_message.created_at}
            
            # Get messages
            messages_data = await self.list(
                collection="messages",
                filters=query,
                skip=skip,
                limit=limit,
                sort={"created_at": -1}
            )
            
            # Convert to Message objects
            return [Message.from_db_dict(message_data) for message_data in messages_data]
            
        except Exception as e:
            raise DatabaseError(f"Failed to get chat messages: {e}")
    
    async def get_message_count(self, chat_id: str, since: Optional[str] = None) -> int:
        """Get the number of messages in a chat since a specific time.
        
        Args:
            chat_id: The chat ID
            since: ISO timestamp to count messages since
            
        Returns:
            int: The number of messages
            
        Raises:
            DatabaseError: If there was an error counting the messages
        """
        try:
            # Base query
            query = {"chat_id": chat_id}
            
            # Add time constraint
            if since:
                query["created_at"] = {"$gt": datetime.datetime.fromisoformat(since)}
            
            # Count messages
            return await self.count("messages", query)
            
        except Exception as e:
            raise DatabaseError(f"Failed to count messages: {e}")
    
    async def get_pinned_messages(self, chat_id: str, skip: int = 0, limit: int = 20) -> List[Message]:
        """Get pinned messages for a chat.
        
        Args:
            chat_id: The chat ID
            skip: Number of messages to skip
            limit: Maximum number of messages to return
            
        Returns:
            List[Message]: The pinned messages
            
        Raises:
            DatabaseError: If there was an error retrieving the messages
        """
        try:
            # Query for pinned messages
            query = {
                "chat_id": chat_id,
                "is_pinned": True,
                "is_deleted": {"$ne": True}
            }
            
            # Get messages
            messages_data = await self.list(
                collection="messages",
                filters=query,
                skip=skip,
                limit=limit,
                sort={"created_at": -1}
            )
            
            # Convert to Message objects
            return [Message.from_db_dict(message_data) for message_data in messages_data]
            
        except Exception as e:
            raise DatabaseError(f"Failed to get pinned messages: {e}")
    
    # Reaction operations
    
    async def add_reaction(self, message_id: str, user_id: str, reaction_type: str) -> Optional[Reaction]:
        """Add a reaction to a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            reaction_type: The reaction type
            
        Returns:
            Optional[Reaction]: The created reaction, or None if failed
            
        Raises:
            DatabaseError: If there was an error adding the reaction
        """
        try:
            # Get message
            message = await self.get_message(message_id)
            
            if not message:
                return None
            
            # Check if user already reacted with this type
            for reaction in message.reactions:
                if reaction.user_id == user_id and reaction.reaction_type == reaction_type:
                    return reaction
            
            # Create reaction
            reaction = Reaction(
                user_id=user_id,
                reaction_type=reaction_type,
                created_at=datetime.datetime.now()
            )
            
            # Add reaction to message
            message.reactions.append(reaction)
            
            # Update message
            updated_message = await self.update_message(
                message_id,
                {"reactions": [r.dict() for r in message.reactions]}
            )
            
            if not updated_message:
                return None
            
            return reaction
            
        except Exception as e:
            raise DatabaseError(f"Failed to add reaction: {e}")
    
    async def remove_reaction(self, message_id: str, user_id: str, reaction_type: str) -> bool:
        """Remove a reaction from a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            reaction_type: The reaction type
            
        Returns:
            bool: True if the reaction was removed, False otherwise
            
        Raises:
            DatabaseError: If there was an error removing the reaction
        """
        try:
            # Get message
            message = await self.get_message(message_id)
            
            if not message:
                return False
            
            # Find reaction
            reaction_index = None
            for i, reaction in enumerate(message.reactions):
                if reaction.user_id == user_id and reaction.reaction_type == reaction_type:
                    reaction_index = i
                    break
            
            if reaction_index is None:
                return False
            
            # Remove reaction
            del message.reactions[reaction_index]
            
            # Update message
            updated_message = await self.update_message(
                message_id,
                {"reactions": [r.dict() for r in message.reactions]}
            )
            
            return updated_message is not None
            
        except Exception as e:
            raise DatabaseError(f"Failed to remove reaction: {e}")
    
    async def get_message_reactions(self, message_id: str) -> List[Reaction]:
        """Get all reactions for a message.
        
        Args:
            message_id: The message ID
            
        Returns:
            List[Reaction]: The reactions
            
        Raises:
            DatabaseError: If there was an error retrieving the reactions
        """
        try:
            # Get message
            message = await self.get_message(message_id)
            
            if not message:
                return []
            
            return message.reactions
            
        except Exception as e:
            raise DatabaseError(f"Failed to get message reactions: {e}")
    
    async def search_messages(self, query: str, user_id: str, 
                             chat_id: Optional[str] = None,
                             skip: int = 0, limit: int = 20) -> List[Message]:
        """Search for messages.
        
        Args:
            query: The search query
            user_id: The user ID
            chat_id: The chat ID to restrict search to (optional)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List[Message]: The matching messages
            
        Raises:
            DatabaseError: If there was an error searching for messages
        """
        try:
            # First, get user's chats to ensure they have access
            chat_filters = {"members.user_id": user_id}
            chats_data = await self.list("chats", filters=chat_filters, limit=1000)
            chat_ids = [chat["id"] for chat in chats_data]
            
            if not chat_ids:
                return []
            
            # Restrict to specific chat if provided
            if chat_id:
                if chat_id not in chat_ids:
                    return []
                chat_ids = [chat_id]
            
            # Build search query
            search_query = {
                "$and": [
                    {"chat_id": {"$in": chat_ids}},
                    {"$text": {"$search": query}}
                ]
            }
            
            # Search messages
            messages_data = await self.list(
                collection="messages",
                filters=search_query,
                skip=skip,
                limit=limit,
                sort={"score": {"$meta": "textScore"}}
            )
            
            return [Message.from_db_dict(message_data) for message_data in messages_data]
            
        except Exception as e:
            raise DatabaseError(f"Failed to search messages: {e}")