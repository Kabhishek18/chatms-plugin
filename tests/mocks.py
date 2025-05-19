"""Mock implementations for testing."""

import asyncio
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
import uuid

from chatms_plugin.database.base import DatabaseHandler
from chatms_plugin.models.user import User
from chatms_plugin.models.chat import Chat
from chatms_plugin.models.message import Message, Reaction


class MockDatabaseHandler(DatabaseHandler):
    """Mock database handler for testing."""
    
    def __init__(self, config):
        """Initialize the mock database handler."""
        self.config = config
        self.users = {}
        self.chats = {}
        self.messages = {}
        self.reactions = {}
    
    async def init(self):
        """Initialize the database connection."""
        pass
    
    async def close(self):
        """Close the database connection."""
        pass
    
    # Generic CRUD operations
    async def create(self, model):
        """Create a new record in the database."""
        model.id = str(uuid.uuid4())
        model.created_at = datetime.now()
        model.updated_at = datetime.now()
        return model
    
    async def get(self, collection, id):
        """Get a record by ID."""
        if collection == "users" and id in self.users:
            return self.users[id]
        elif collection == "chats" and id in self.chats:
            return self.chats[id]
        elif collection == "messages" and id in self.messages:
            return self.messages[id]
        return None
    
    async def update(self, collection, id, data):
        """Update a record by ID."""
        if collection == "users" and id in self.users:
            for key, value in data.items():
                setattr(self.users[id], key, value)
            self.users[id].updated_at = datetime.now()
            return self.users[id]
        elif collection == "chats" and id in self.chats:
            for key, value in data.items():
                setattr(self.chats[id], key, value)
            self.chats[id].updated_at = datetime.now()
            return self.chats[id]
        elif collection == "messages" and id in self.messages:
            for key, value in data.items():
                setattr(self.messages[id], key, value)
            self.messages[id].updated_at = datetime.now()
            return self.messages[id]
        return None
    
    async def delete(self, collection, id):
        """Delete a record by ID."""
        if collection == "users" and id in self.users:
            del self.users[id]
            return True
        elif collection == "chats" and id in self.chats:
            del self.chats[id]
            return True
        elif collection == "messages" and id in self.messages:
            del self.messages[id]
            return True
        return False
    
    async def list(self, collection, filters=None, skip=0, limit=100, sort=None):
        """List records with optional filtering, pagination, and sorting."""
        if collection == "users":
            return list(self.users.values())[skip:skip+limit]
        elif collection == "chats":
            return list(self.chats.values())[skip:skip+limit]
        elif collection == "messages":
            return list(self.messages.values())[skip:skip+limit]
        return []
    
    async def count(self, collection, filters=None):
        """Count records with optional filtering."""
        if collection == "users":
            return len(self.users)
        elif collection == "chats":
            return len(self.chats)
        elif collection == "messages":
            return len(self.messages)
        return 0
    
    # Implement other required methods
    async def create_user(self, user):
        """Create a new user."""
        user.id = str(uuid.uuid4())
        user.created_at = datetime.now()
        user.updated_at = datetime.now()
        self.users[user.id] = user
        return user
    
    async def get_user(self, user_id):
        """Get a user by ID."""
        return self.users.get(user_id)
    
    async def get_user_by_username(self, username):
        """Get a user by username."""
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    async def update_user(self, user_id, data):
        """Update a user."""
        if user_id in self.users:
            user = self.users[user_id]
            for key, value in data.items():
                setattr(user, key, value)
            user.updated_at = datetime.now()
            return user
        return None
    
    async def delete_user(self, user_id):
        """Delete a user."""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False
    
    # Implement other required methods (add_chat_member, add_reaction, create_message, etc.)
    # Add stubs for all the abstract methods
    
    async def create_chat(self, chat):
        """Create a new chat."""
        chat.id = str(uuid.uuid4())
        chat.created_at = datetime.now()
        chat.updated_at = datetime.now()
        self.chats[chat.id] = chat
        return chat
        
    async def get_chat(self, chat_id):
        """Get a chat by ID."""
        return self.chats.get(chat_id)
        
    async def update_chat(self, chat_id, data):
        """Update a chat."""
        if chat_id in self.chats:
            chat = self.chats[chat_id]
            for key, value in data.items():
                setattr(chat, key, value)
            chat.updated_at = datetime.now()
            return chat
        return None
        
    async def delete_chat(self, chat_id):
        """Delete a chat."""
        if chat_id in self.chats:
            del self.chats[chat_id]
            return True
        return False
        
    async def get_user_chats(self, user_id, skip=0, limit=100):
        """Get all chats for a user."""
        user_chats = []
        for chat in self.chats.values():
            for member in chat.members:
                if member.user_id == user_id:
                    user_chats.append(chat)
                    break
        return user_chats[skip:skip+limit]
        
    async def add_chat_member(self, chat_id, user_id, role):
        """Add a member to a chat."""
        if chat_id in self.chats:
            from chatms_plugin.models.user import UserInChat
            chat = self.chats[chat_id]
            for member in chat.members:
                if member.user_id == user_id:
                    return True
            chat.members.append(UserInChat(user_id=user_id, role=role))
            return True
        return False
        
    async def remove_chat_member(self, chat_id, user_id):
        """Remove a member from a chat."""
        if chat_id in self.chats:
            chat = self.chats[chat_id]
            for i, member in enumerate(chat.members):
                if member.user_id == user_id:
                    chat.members.pop(i)
                    return True
        return False
        
    async def get_chat_members(self, chat_id):
        """Get all members of a chat."""
        if chat_id in self.chats:
            return self.chats[chat_id].members
        return []
        
    # Message operations
    
    async def create_message(self, message):
        """Create a new message."""
        message.id = str(uuid.uuid4())
        message.created_at = datetime.now()
        message.updated_at = datetime.now()
        self.messages[message.id] = message
        return message
        
    async def get_message(self, message_id):
        """Get a message by ID."""
        return self.messages.get(message_id)
        
    async def update_message(self, message_id, data):
        """Update a message."""
        if message_id in self.messages:
            message = self.messages[message_id]
            for key, value in data.items():
                setattr(message, key, value)
            message.updated_at = datetime.now()
            return message
        return None
        
    async def delete_message(self, message_id, delete_for_everyone=False):
        """Delete a message."""
        if delete_for_everyone and message_id in self.messages:
            del self.messages[message_id]
            return True
        elif message_id in self.messages:
            self.messages[message_id].is_deleted = True
            return True
        return False
        
    async def get_chat_messages(self, chat_id, before_id=None, after_id=None, skip=0, limit=50):
        """Get messages for a chat with pagination."""
        chat_messages = [msg for msg in self.messages.values() if msg.chat_id == chat_id]
        if before_id:
            before_msg = self.messages.get(before_id)
            if before_msg:
                chat_messages = [msg for msg in chat_messages if msg.created_at < before_msg.created_at]
        if after_id:
            after_msg = self.messages.get(after_id)
            if after_msg:
                chat_messages = [msg for msg in chat_messages if msg.created_at > after_msg.created_at]
        return sorted(chat_messages, key=lambda x: x.created_at, reverse=True)[skip:skip+limit]
        
    async def get_message_count(self, chat_id, since=None):
        """Get the number of messages in a chat since a specific time."""
        count = 0
        for msg in self.messages.values():
            if msg.chat_id == chat_id:
                if since:
                    if msg.created_at.isoformat() > since:
                        count += 1
                else:
                    count += 1
        return count
        
    # Reaction operations
    
    async def add_reaction(self, message_id, user_id, reaction_type):
        """Add a reaction to a message."""
        if message_id in self.messages:
            message = self.messages[message_id]
            from chatms_plugin.models.message import Reaction
            reaction = Reaction(user_id=user_id, reaction_type=reaction_type)
            for r in message.reactions:
                if r.user_id == user_id and r.reaction_type == reaction_type:
                    return r
            message.reactions.append(reaction)
            return reaction
        return None
        
    async def remove_reaction(self, message_id, user_id, reaction_type):
        """Remove a reaction from a message."""
        if message_id in self.messages:
            message = self.messages[message_id]
            for i, r in enumerate(message.reactions):
                if r.user_id == user_id and r.reaction_type == reaction_type:
                    message.reactions.pop(i)
                    return True
        return False
        
    async def get_message_reactions(self, message_id):
        """Get all reactions for a message."""
        if message_id in self.messages:
            return self.messages[message_id].reactions
        return []
        
    # Search operations
    
    async def search_messages(self, query, user_id, chat_id=None, skip=0, limit=20):
        """Search for messages."""
        results = []
        for message in self.messages.values():
            if chat_id and message.chat_id != chat_id:
                continue
            if query.lower() in message.content.lower():
                # Check if user has access to this chat
                chat = self.chats.get(message.chat_id)
                if chat and any(member.user_id == user_id for member in chat.members):
                    results.append(message)
        return results[skip:skip+limit]
        
    # Stats and aggregation
    
    async def get_chat_stats(self, chat_id):
        """Get statistics for a chat."""
        return {
            "message_count": sum(1 for msg in self.messages.values() if msg.chat_id == chat_id),
            "member_count": len(self.chats.get(chat_id, {}).members) if chat_id in self.chats else 0,
            "reaction_count": sum(len(msg.reactions) for msg in self.messages.values() if msg.chat_id == chat_id)
        }
        
    async def get_user_stats(self, user_id):
        """Get statistics for a user."""
        return {
            "message_count": sum(1 for msg in self.messages.values() if msg.sender_id == user_id),
            "chat_count": sum(1 for chat in self.chats.values() if any(member.user_id == user_id for member in chat.members)),
            "reaction_count": sum(1 for msg in self.messages.values() for r in msg.reactions if r.user_id == user_id)
        }