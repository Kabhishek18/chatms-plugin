"""
MongoDB database handler for the ChatMS plugin.
Main implementation that combines all handlers.
"""

import logging
from typing import Any, Dict, List, Optional

from ..config import Config, UserRole
from ..exceptions import DatabaseError
from ..models.base import DatabaseModel
from ..models.chat import Chat
from ..models.message import Message, Reaction
from ..models.user import User
from .base import DatabaseHandler
from .mongodb_base import MongoDBHandler
from .mongodb_chat import MongoDBChatHandler
from .mongodb_message import MongoDBMessageHandler
from .mongodb_user import MongoDBUserHandler


logger = logging.getLogger(__name__)


class MongoDBCompleteHandler(MongoDBUserHandler, MongoDBChatHandler, MongoDBMessageHandler):
    """Complete MongoDB handler that combines all functionality."""
    
    def __init__(self, config: Config):
        """Initialize the MongoDB handler.
        
        Args:
            config: Configuration object
        """
        super().__init__(config)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics.
        
        Returns:
            Dict[str, Any]: Database statistics
        """
        try:
            stats = {}
            
            # Get collection stats
            for collection in ["users", "chats", "messages"]:
                count = await self.count(collection)
                stats[f"{collection}_count"] = count
            
            # Get user stats
            stats["active_users_count"] = await self.count(
                "users", 
                {"status": {"$ne": "offline"}}
            )
            
            # Get chat stats
            stats["group_chats_count"] = await self.count(
                "chats",
                {"chat_type": "group"}
            )
            
            stats["one_to_one_chats_count"] = await self.count(
                "chats",
                {"chat_type": "one_to_one"}
            )
            
            # Get message stats
            stats["deleted_messages_count"] = await self.count(
                "messages",
                {"is_deleted": True}
            )
            
            stats["pinned_messages_count"] = await self.count(
                "messages",
                {"is_pinned": True}
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    async def get_chat_stats(self, chat_id: str) -> Dict[str, Any]:
        """Get statistics for a chat.
        
        Args:
            chat_id: The chat ID
            
        Returns:
            Dict[str, Any]: Chat statistics
        """
        try:
            stats = {"chat_id": chat_id}
            
            # Get chat info
            chat = await self.get_chat(chat_id)
            if chat:
                stats["chat_name"] = chat.name
                stats["chat_type"] = chat.chat_type
                stats["members_count"] = len(chat.members)
            
            # Get message stats
            stats["messages_count"] = await self.count(
                "messages",
                {"chat_id": chat_id}
            )
            
            stats["deleted_messages_count"] = await self.count(
                "messages",
                {"chat_id": chat_id, "is_deleted": True}
            )
            
            stats["pinned_messages_count"] = await self.count(
                "messages",
                {"chat_id": chat_id, "is_pinned": True}
            )
            
            # Get sender stats
            message_pipeline = [
                {"$match": {"chat_id": chat_id}},
                {"$group": {
                    "_id": "$sender_id",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            top_senders = []
            cursor = self.db.messages.aggregate(message_pipeline)
            async for doc in cursor:
                user_id = doc["_id"]
                user = await self.get_user(user_id)
                username = user.username if user else user_id
                top_senders.append({
                    "user_id": user_id,
                    "username": username,
                    "message_count": doc["count"]
                })
            
            stats["top_senders"] = top_senders
            
            # Get reaction stats
            reaction_pipeline = [
                {"$match": {"chat_id": chat_id}},
                {"$unwind": "$reactions"},
                {"$group": {
                    "_id": "$reactions.reaction_type",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            top_reactions = []
            cursor = self.db.messages.aggregate(reaction_pipeline)
            async for doc in cursor:
                top_reactions.append({
                    "reaction_type": doc["_id"],
                    "count": doc["count"]
                })
            
            stats["top_reactions"] = top_reactions
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get chat stats: {e}")
            return {"chat_id": chat_id, "error": str(e)}
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dict[str, Any]: User statistics
        """
        try:
            stats = {"user_id": user_id}
            
            # Get user info
            user = await self.get_user(user_id)
            if user:
                stats["username"] = user.username
                stats["status"] = user.status
            
            # Get chat stats
            stats["chats_count"] = await self.count(
                "chats",
                {"members.user_id": user_id}
            )
            
            stats["group_chats_count"] = await self.count(
                "chats",
                {"members.user_id": user_id, "chat_type": "group"}
            )
            
            stats["one_to_one_chats_count"] = await self.count(
                "chats",
                {"members.user_id": user_id, "chat_type": "one_to_one"}
            )
            
            # Get message stats
            stats["messages_sent_count"] = await self.count(
                "messages",
                {"sender_id": user_id}
            )
            
            # Get chat activity
            chat_pipeline = [
                {"$match": {"sender_id": user_id}},
                {"$group": {
                    "_id": "$chat_id",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            top_chats = []
            cursor = self.db.messages.aggregate(chat_pipeline)
            async for doc in cursor:
                chat_id = doc["_id"]
                chat = await self.get_chat(chat_id)
                chat_name = chat.name if chat else chat_id
                top_chats.append({
                    "chat_id": chat_id,
                    "chat_name": chat_name,
                    "message_count": doc["count"]
                })
            
            stats["top_chats"] = top_chats
            
            # Get reaction activity
            reaction_pipeline = [
                {"$match": {"reactions.user_id": user_id}},
                {"$unwind": "$reactions"},
                {"$match": {"reactions.user_id": user_id}},
                {"$group": {
                    "_id": "$reactions.reaction_type",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            
            top_reactions = []
            cursor = self.db.messages.aggregate(reaction_pipeline)
            async for doc in cursor:
                top_reactions.append({
                    "reaction_type": doc["_id"],
                    "count": doc["count"]
                })
            
            stats["top_reactions"] = top_reactions
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return {"user_id": user_id, "error": str(e)}