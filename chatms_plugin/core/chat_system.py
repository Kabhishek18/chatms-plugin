"""
Main Chat System implementation for the ChatMS plugin.
"""

import asyncio
import datetime
import logging
import mimetypes
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..config import ChatType, Config, MessageStatus, MessageType, UserRole
from ..exceptions import (
    AuthenticationError, AuthorizationError, ChatError, ConfigurationError,
    MessageError, StorageError, UserError, ValidationError
)
from ..models.chat import Chat, ChatCreate, ChatUpdate
from ..models.message import (
    Attachment, Message, MessageCreate, MessageUpdate, Reaction
)
from ..models.user import User, UserCreate, UserInChat, UserPresence, UserUpdate
from .analytics import AnalyticsService
from .connection import ConnectionManager
from .security import SecurityManager


logger = logging.getLogger(__name__)


class ChatSystem:
    """Main chat system class that orchestrates all components."""
    
    def __init__(self, config: Config):
        """Initialize the chat system.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.security_manager = SecurityManager(config)
        self.connection_manager = ConnectionManager(config)
        self.analytics_service = AnalyticsService(config)
        
        # These will be initialized in the init method
        self.db_handler = None
        self.storage_handler = None
        self.notification_handler = None
        self.redis = None
    
    async def init(self) -> None:
        """Initialize all components of the chat system."""
        # Initialize Redis connection
        try:
            import aioredis
            self.redis = await aioredis.from_url(self.config.redis_url)
            logger.info("Connected to Redis")
        except ImportError:
            logger.warning("aioredis not installed, running without Redis support")
            self.redis = None
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self.redis = None
        
        # Initialize database handler
        if self.config.database_type == 'postgresql':
            from ..database.postgresql import PostgreSQLHandler
            self.db_handler = PostgreSQLHandler(self.config)
        elif self.config.database_type == 'mongodb':
            from ..database.mongodb import MongoDBHandler
            self.db_handler = MongoDBHandler(self.config)
        # Add SQLite support for testing
        elif self.config.database_type == 'sqlite':
            # Use a mock database handler for testing
            from unittest.mock import MagicMock
            self.db_handler = MagicMock()
            # Add necessary methods for testing
            self.db_handler.init = MagicMock(return_value=None)
            self.db_handler.close = MagicMock(return_value=None)
            self.db_handler.create_user = MagicMock(return_value=None)
            self.db_handler.get_user = MagicMock(return_value=None)
            # Add more methods as needed
        else:
            raise ConfigurationError(f"Unsupported database type: {self.config.database_type}")
        
        await self.db_handler.init()
        logger.info(f"Database handler initialized: {self.config.database_type}")
        
        # Initialize storage handler
        if self.config.storage_type == 'local':
            from ..storage.local import LocalStorageHandler
            self.storage_handler = LocalStorageHandler(self.config)
        elif self.config.storage_type == 's3':
            from ..storage.s3 import S3StorageHandler
            self.storage_handler = S3StorageHandler(self.config)
        elif self.config.storage_type == 'gcp':
            from ..storage.gcp import GCPStorageHandler
            self.storage_handler = GCPStorageHandler(self.config)
        elif self.config.storage_type == 'azure':
            from ..storage.azure import AzureStorageHandler
            self.storage_handler = AzureStorageHandler(self.config)
        else:
            raise ConfigurationError(f"Unsupported storage type: {self.config.storage_type}")
        
        await self.storage_handler.init()
        logger.info(f"Storage handler initialized: {self.config.storage_type}")
        
        # Initialize notification handler based on configuration
        if self.config.enable_push_notifications:
            # Check for FCM
            if self.config.fcm_api_key:
                from ..notifications.fcm import FCMNotificationHandler
                self.notification_handler = FCMNotificationHandler(self.config)
            # Check for APNs
            elif self.config.apns_key_file:
                from ..notifications.apns import APNSNotificationHandler
                self.notification_handler = APNSNotificationHandler(self.config)
            else:
                from ..notifications.base import BaseNotificationHandler
                self.notification_handler = BaseNotificationHandler(self.config)
                logger.warning("Push notifications enabled but no provider configured")
        else:
            from ..notifications.base import BaseNotificationHandler
            self.notification_handler = BaseNotificationHandler(self.config)
        
        await self.notification_handler.init()
        logger.info("Notification handler initialized")
        
        # Initialize connection manager
        await self.connection_manager.init()
        logger.info("Connection manager initialized")
        
        # Initialize analytics service
        await self.analytics_service.init(self.redis)
        logger.info("Analytics service initialized")
        
        logger.info("Chat system initialized")
    
    async def close(self) -> None:
        """Close all components of the chat system."""
        # Close Redis connection
        if self.redis:
            await self.redis.close()
            
        # Close database connection
        if self.db_handler:
            await self.db_handler.close()
            
        # Close storage connection
        if self.storage_handler:
            await self.storage_handler.close()
            
        # Close notification handler
        if self.notification_handler:
            await self.notification_handler.close()
            
        # Close connection manager
        await self.connection_manager.close()
        
        logger.info("Chat system closed")
    
    # User operations
    
    async def register_user(self, user_data: UserCreate) -> User:
        """Register a new user.
        
        Args:
            user_data: User creation data
            
        Returns:
            User: The created user
            
        Raises:
            ValidationError: If the user data is invalid
            AuthenticationError: If the username is already taken
        """
        # Check if username is already taken
        existing_user = await self.db_handler.get_user_by_username(user_data.username)
        if existing_user:
            raise AuthenticationError(f"Username '{user_data.username}' is already taken")
        
        # Hash password
        hashed_password = await self.security_manager.hash_password(user_data.password)
        
        # Create user
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            status="online",
            last_seen=datetime.datetime.now()
        )
        
        created_user = await self.db_handler.create_user(user)
        
        # Track analytics
        await self.analytics_service.track_user_registered(created_user.id)
        
        logger.info(f"User registered: {created_user.id} ({created_user.username})")
        return created_user
    
    async def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """Authenticate a user and generate a token.
        
        Args:
            username: The username
            password: The password
            
        Returns:
            Optional[str]: The JWT token, or None if authentication failed
            
        Raises:
            AuthenticationError: If the authentication fails
        """
        # Get user by username
        user = await self.db_handler.get_user_by_username(username)
        if not user:
            await self.analytics_service.track_auth_failure(username, "user_not_found")
            raise AuthenticationError("Invalid username or password")
        
        # Verify password
        if not await self.security_manager.verify_password(password, user.hashed_password):
            await self.analytics_service.track_auth_failure(username, "invalid_password")
            raise AuthenticationError("Invalid username or password")
        
        # Update user status and last seen
        await self.update_user(user.id, UserUpdate(
            status="online",
        ))
        
        # Create token
        token = await self.security_manager.create_token(user.id)
        
        # Track analytics
        await self.analytics_service.track_auth_success(user.id)
        
        logger.info(f"User authenticated: {user.id} ({user.username})")
        return token
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[User]: The user, or None if not found
        """
        return await self.db_handler.get_user(user_id)
    
    async def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[User]:
        """Update a user.
        
        Args:
            user_id: The user ID
            user_data: User update data
            
        Returns:
            Optional[User]: The updated user, or None if not found
            
        Raises:
            ValidationError: If the user data is invalid
        """
        # Get existing user
        user = await self.db_handler.get_user(user_id)
        if not user:
            return None
        
        # Prepare update data
        update_data = user_data.dict(exclude_unset=True)
        
        # Hash password if provided
        if "password" in update_data:
            update_data["hashed_password"] = await self.security_manager.hash_password(update_data.pop("password"))
        
        # Update user
        updated_user = await self.db_handler.update_user(user_id, update_data)
        
        if updated_user:
            logger.info(f"User updated: {user_id}")
        
        return updated_user
    
    async def update_user_status(self, user_id: str, status: str) -> Optional[User]:
        """Update a user's status.
        
        Args:
            user_id: The user ID
            status: The new status
            
        Returns:
            Optional[User]: The updated user, or None if not found
        """
        # Get existing user
        user = await self.db_handler.get_user(user_id)
        if not user:
            return None
        
        # Update status and last seen
        update_data = {
            "status": status,
            "last_seen": datetime.datetime.now()
        }
        
        # Update user
        updated_user = await self.db_handler.update_user(user_id, update_data)
        
        if updated_user:
            # Broadcast presence update to relevant users
            presence = UserPresence(
                user_id=user_id,
                status=status,
                last_seen=updated_user.last_seen
            )
            
            await self.connection_manager.update_presence(presence.dict())
            
            logger.info(f"User status updated: {user_id} to {status}")
        
        return updated_user
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            bool: True if the user was deleted, False otherwise
        """
        # Get user's chats
        chats = await self.db_handler.get_user_chats(user_id)
        
        # For each chat, remove the user
        for chat in chats:
            await self.remove_chat_member(chat.id, chat.members[0].user_id, user_id)
        
        # Delete user
        result = await self.db_handler.delete_user(user_id)
        
        if result:
            logger.info(f"User deleted: {user_id}")
        
        return result
    
    # Chat operations
    
    async def create_chat(self, chat_data: ChatCreate, creator_id: str) -> Chat:
        """Create a new chat.
        
        Args:
            chat_data: Chat creation data
            creator_id: ID of the user creating the chat
            
        Returns:
            Chat: The created chat
            
        Raises:
            ValidationError: If the chat data is invalid
            AuthorizationError: If the creator is not allowed to create this chat
        """
        # Ensure creator is in member_ids
        if creator_id not in chat_data.member_ids:
            chat_data.member_ids.append(creator_id)
        
        # Create chat members
        members = []
        for member_id in chat_data.member_ids:
            role = UserRole.ADMIN if member_id == creator_id else UserRole.MEMBER
            members.append(UserInChat(user_id=member_id, role=role))
        
        # Create chat
        chat = Chat(
            name=chat_data.name,
            description=chat_data.description,
            chat_type=chat_data.chat_type,
            is_encrypted=chat_data.is_encrypted,
            icon_url=chat_data.icon_url,
            metadata=chat_data.metadata,
            members=members
        )
        
        created_chat = await self.db_handler.create_chat(chat)
        
        # Track analytics
        await self.analytics_service.track_chat_created(
            created_chat.id, creator_id, created_chat.chat_type.value
        )
        
        # Notify all members
        for member in created_chat.members:
            if member.user_id != creator_id:  # Don't notify the creator
                await self.connection_manager.send_chat_created(member.user_id, created_chat.dict())
                
                # Send push notification
                await self.notification_handler.send_notification(
                    user_id=member.user_id,
                    title="New Chat",
                    body=f"{created_chat.name or 'New chat'} created by {creator_id}",
                    data={
                        "type": "chat_created",
                        "chat_id": created_chat.id
                    }
                )
        
        logger.info(f"Chat created: {created_chat.id} ({created_chat.name}) by {creator_id}")
        return created_chat
    
    async def get_chat(self, chat_id: str, user_id: str) -> Optional[Chat]:
        """Get a chat by ID.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            
        Returns:
            Optional[Chat]: The chat, or None if not found
            
        Raises:
            AuthorizationError: If the user is not a member of the chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            return None
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        return chat
    
    async def update_chat(self, chat_id: str, user_id: str, chat_data: ChatUpdate) -> Optional[Chat]:
        """Update a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            chat_data: Chat update data
            
        Returns:
            Optional[Chat]: The updated chat, or None if not found
            
        Raises:
            ValidationError: If the chat data is invalid
            AuthorizationError: If the user is not allowed to update this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            return None
        
        # Check if user is an admin
        if not chat.is_admin(user_id):
            raise AuthorizationError(f"User {user_id} is not an admin of chat {chat_id}")
        
        # Prepare update data
        update_data = chat_data.dict(exclude_unset=True, exclude_none=True)
        
        # Update chat
        updated_chat = await self.db_handler.update_chat(chat_id, update_data)
        
        if updated_chat:
            # Notify all members
            for member in updated_chat.members:
                await self.connection_manager.send_chat_updated(member.user_id, updated_chat.dict())
            
            logger.info(f"Chat updated: {chat_id} by {user_id}")
        
        return updated_chat
    
    async def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """Delete a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            
        Returns:
            bool: True if the chat was deleted, False otherwise
            
        Raises:
            AuthorizationError: If the user is not allowed to delete this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            return False
        
        # Check if user is an admin
        if not chat.is_admin(user_id):
            raise AuthorizationError(f"User {user_id} is not an admin of chat {chat_id}")
        
        # Notify all members before deletion
        for member in chat.members:
            await self.connection_manager.send_chat_deleted(member.user_id, chat_id)
        
        # Delete chat
        result = await self.db_handler.delete_chat(chat_id)
        
        if result:
            logger.info(f"Chat deleted: {chat_id} by {user_id}")
        
        return result
    
    async def get_user_chats(self, user_id: str) -> List[Chat]:
        """Get all chats for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[Chat]: The user's chats
        """
        return await self.db_handler.get_user_chats(user_id)
    
    async def add_chat_member(self, chat_id: str, admin_id: str, user_id: str, role: UserRole = UserRole.MEMBER) -> bool:
        """Add a member to a chat.
        
        Args:
            chat_id: The chat ID
            admin_id: The admin user ID
            user_id: The user ID to add
            role: The user's role
            
        Returns:
            bool: True if the member was added, False otherwise
            
        Raises:
            AuthorizationError: If the admin is not allowed to add members
            ChatError: If the user is already a member
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            return False
        
        # Check if admin is an admin
        if not chat.is_admin(admin_id):
            raise AuthorizationError(f"User {admin_id} is not an admin of chat {chat_id}")
        
        # Check if user is already a member
        if chat.is_member(user_id):
            raise ChatError(f"User {user_id} is already a member of chat {chat_id}")
        
        # Check if one-to-one chat
        if chat.chat_type == ChatType.ONE_TO_ONE:
            raise ChatError("Cannot add members to one-to-one chat")
        
        # Add member
        result = await self.db_handler.add_chat_member(chat_id, user_id, role.value)
        
        if result:
            # Get updated chat
            updated_chat = await self.db_handler.get_chat(chat_id)
            
            # Notify all members
            await self.connection_manager.send_chat_member_added(chat_id, user_id, updated_chat.dict())
            
            # Send push notification to the new member
            await self.notification_handler.send_notification(
                user_id=user_id,
                title="Added to Chat",
                body=f"You were added to {updated_chat.name or 'a chat'}",
                data={
                    "type": "chat_member_added",
                    "chat_id": chat_id
                }
            )
            
            logger.info(f"Chat member added: {user_id} to {chat_id} by {admin_id}")
        
        return result
    
    async def remove_chat_member(self, chat_id: str, admin_id: str, user_id: str) -> bool:
        """Remove a member from a chat.
        
        Args:
            chat_id: The chat ID
            admin_id: The admin user ID
            user_id: The user ID to remove
            
        Returns:
            bool: True if the member was removed, False otherwise
            
        Raises:
            AuthorizationError: If the admin is not allowed to remove members
            ChatError: If the user is not a member
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            return False
        
        # Check if admin is an admin or self-removal
        if admin_id != user_id and not chat.is_admin(admin_id):
            raise AuthorizationError(f"User {admin_id} is not an admin of chat {chat_id}")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise ChatError(f"User {user_id} is not a member of chat {chat_id}")
        
        # Check if one-to-one chat
        if chat.chat_type == ChatType.ONE_TO_ONE:
            raise ChatError("Cannot remove members from one-to-one chat")
        
        # Remove member
        result = await self.db_handler.remove_chat_member(chat_id, user_id)
        
        if result:
            # Get updated chat
            updated_chat = await self.db_handler.get_chat(chat_id)
            
            # Notify all members
            await self.connection_manager.send_chat_member_removed(chat_id, user_id, updated_chat.dict())
            
            logger.info(f"Chat member removed: {user_id} from {chat_id} by {admin_id}")
        
        return result
    
    # Message operations
    
    async def send_message(self, sender_id: str, message_data: MessageCreate) -> Message:
        """Send a message.
        
        Args:
            sender_id: The sender ID
            message_data: Message creation data
            
        Returns:
            Message: The created message
            
        Raises:
            ValidationError: If the message data is invalid
            AuthorizationError: If the sender is not allowed to send messages to this chat
            RateLimitError: If the sender has exceeded the rate limit
        """
        # Start timer for performance tracking
        self.analytics_service.start_timer("send_message")
        
        # Get chat
        chat = await self.db_handler.get_chat(message_data.chat_id)
        if not chat:
            raise ChatError(f"Chat {message_data.chat_id} not found")
        
        # Check if sender is a member
        if not chat.is_member(sender_id):
            raise AuthorizationError(f"User {sender_id} is not a member of chat {message_data.chat_id}")
        
        # Apply rate limiting
        if self.redis:
            # Check rate limit
            rate_key = f"rate:messages:{sender_id}"
            current = await self.redis.incr(rate_key)
            
            # Set expiry if first increment
            if current == 1:
                await self.redis.expire(rate_key, 60)  # 60 seconds expiry
            
            if current > self.config.rate_limit_messages_per_minute:
                from ..exceptions import RateLimitError
                raise RateLimitError(
                    message=f"Rate limit exceeded: {self.config.rate_limit_messages_per_minute} messages per minute",
                    reset_time=await self.redis.ttl(rate_key)
                )
        
        # Check for mentions and resolve them
        mentions = []
        if message_data.mentions:
            for user_id in message_data.mentions:
                # Verify user exists and is in the chat
                if not await self.db_handler.get_user(user_id):
                    continue
                
                if not chat.is_member(user_id):
                    continue
                
                # Find mention position in text
                username = (await self.db_handler.get_user(user_id)).username
                mention_text = f"@{username}"
                
                if mention_text in message_data.content:
                    offset = message_data.content.index(mention_text)
                    length = len(mention_text)
                    
                    from ..models.message import Mention
                    mentions.append(Mention(
                        user_id=user_id,
                        offset=offset,
                        length=length
                    ))
        
        # Create message
        content = message_data.content
        
        # Encrypt content if chat is encrypted
        if chat.is_encrypted:
            content = await self.security_manager.encrypt(content)
        
        message = Message(
            chat_id=message_data.chat_id,
            sender_id=sender_id,
            content=content,
            message_type=message_data.message_type,
            status=MessageStatus.SENT,
            reply_to_id=message_data.reply_to_id,
            mentions=mentions
        )
        
        # Save message
        created_message = await self.db_handler.create_message(message)
        
        # Stop timer and track analytics
        await self.analytics_service.stop_timer("send_message", {"message_id": created_message.id})
        await self.analytics_service.track_message(
            message_id=created_message.id,
            chat_id=created_message.chat_id,
            sender_id=created_message.sender_id,
            message_type=created_message.message_type.value,
            size=len(created_message.content)
        )
        
        # Broadcast message to all chat members
        for member in chat.members:
            if member.user_id != sender_id:  # Don't send to the sender
                # Create message data for broadcasting
                message_data = created_message.dict()
                
                # Decrypt content for sending
                if chat.is_encrypted:
                    message_data["content"] = await self.security_manager.decrypt(message_data["content"])
                
                await self.connection_manager.send_new_message(member.user_id, message_data)
                
                # Send push notification
                sender = await self.db_handler.get_user(sender_id)
                sender_name = sender.username if sender else "Someone"
                
                notification_body = message_data["content"]
                if len(notification_body) > 100:
                    notification_body = notification_body[:97] + "..."
                
                await self.notification_handler.send_notification(
                    user_id=member.user_id,
                    title=f"{sender_name} in {chat.name or 'chat'}",
                    body=notification_body,
                    data={
                        "type": "new_message",
                        "chat_id": chat.id,
                        "message_id": created_message.id
                    }
                )
        
        # Process mentions - send special notifications
        for mention in mentions:
            if mention.user_id != sender_id:  # Don't notify the sender
                mention_data = {
                    "chat_id": chat.id,
                    "message_id": created_message.id,
                    "sender_id": sender_id,
                    "mentioned_user_id": mention.user_id
                }
                
                await self.connection_manager.send_mention(mention.user_id, mention_data)
                
                # Send push notification
                sender = await self.db_handler.get_user(sender_id)
                sender_name = sender.username if sender else "Someone"
                
                await self.notification_handler.send_notification(
                    user_id=mention.user_id,
                    title=f"{sender_name} mentioned you",
                    body=f"In {chat.name or 'a chat'}: {message_data.content[:50]}...",
                    data={
                        "type": "mention",
                        "chat_id": chat.id,
                        "message_id": created_message.id
                    }
                )
        
        logger.info(f"Message sent: {created_message.id} to chat {message_data.chat_id} by {sender_id}")
        return created_message
    
    async def get_message(self, message_id: str, user_id: str) -> Optional[Message]:
        """Get a message by ID.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            
        Returns:
            Optional[Message]: The message, or None if not found
            
        Raises:
            AuthorizationError: If the user is not allowed to access this message
        """
        # Get message
        message = await self.db_handler.get_message(message_id)
        if not message:
            return None
        
        # Get chat
        chat = await self.db_handler.get_chat(message.chat_id)
        if not chat:
            return None
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {message.chat_id}")
        
        # Decrypt content if needed
        if chat.is_encrypted and message.content:
            message.content = await self.security_manager.decrypt(message.content)
        
        return message
    
    async def get_chat_messages(self, chat_id: str, user_id: str, 
                              before_id: Optional[str] = None,
                              after_id: Optional[str] = None,
                              limit: int = 50) -> List[Message]:
        """Get messages for a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            before_id: Get messages before this ID
            after_id: Get messages after this ID
            limit: Maximum number of messages to return
            
        Returns:
            List[Message]: The messages
            
        Raises:
            AuthorizationError: If the user is not allowed to access this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            raise ChatError(f"Chat {chat_id} not found")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        # Get messages
        messages = await self.db_handler.get_chat_messages(
            chat_id=chat_id,
            before_id=before_id,
            after_id=after_id,
            limit=limit
        )
        
        # Decrypt content if needed
        if chat.is_encrypted:
            for message in messages:
                if message.content:
                    message.content = await self.security_manager.decrypt(message.content)
        
        return messages
    
    async def update_message(self, message_id: str, user_id: str, message_data: MessageUpdate) -> Optional[Message]:
        """Update a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            message_data: Message update data
            
        Returns:
            Optional[Message]: The updated message, or None if not found
            
        Raises:
            ValidationError: If the message data is invalid
            AuthorizationError: If the user is not allowed to update this message
        """
        # Get message
        message = await self.db_handler.get_message(message_id)
        if not message:
            return None
        
        # Check if user is the sender
        if message.sender_id != user_id:
            raise AuthorizationError(f"User {user_id} is not the sender of message {message_id}")
        
        # Prepare update data
        update_data = message_data.dict(exclude_unset=True, exclude_none=True)
        
        # Encrypt content if needed
        chat = await self.db_handler.get_chat(message.chat_id)
        if chat and chat.is_encrypted and "content" in update_data:
            update_data["content"] = await self.security_manager.encrypt(update_data["content"])
        
        # Add edited timestamp
        update_data["edited_at"] = datetime.datetime.now()
        
        # Update message
        updated_message = await self.db_handler.update_message(message_id, update_data)
        
        if updated_message:
            # Decrypt content for sending
            message_data = updated_message.dict()
            if chat and chat.is_encrypted and updated_message.content:
                message_data["content"] = await self.security_manager.decrypt(message_data["content"])
            
            # Notify all chat members
            for member in chat.members:
                if member.user_id != user_id:  # Don't send to the updater
                    await self.connection_manager.send_message_updated(member.user_id, message_data)
            
            logger.info(f"Message updated: {message_id} by {user_id}")
        
        return updated_message
    
    async def delete_message(self, message_id: str, user_id: str, delete_for_everyone: bool = False) -> bool:
        """Delete a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            delete_for_everyone: Whether to delete for everyone or just for the user
            
        Returns:
            bool: True if the message was deleted, False otherwise
            
        Raises:
            AuthorizationError: If the user is not allowed to delete this message
        """
        # Get message
        message = await self.db_handler.get_message(message_id)
        if not message:
            return False
        
        # Get chat
        chat = await self.db_handler.get_chat(message.chat_id)
        if not chat:
            return False
        
        # Check if user is the sender or an admin
        is_sender = message.sender_id == user_id
        is_admin = chat.is_admin(user_id)
        
        if not is_sender and not is_admin:
            # If not sender or admin, can only delete for self, not for everyone
            if delete_for_everyone:
                raise AuthorizationError(f"User {user_id} is not allowed to delete message {message_id} for everyone")
        
        # Delete message
        result = await self.db_handler.delete_message(message_id, delete_for_everyone)
        
        if result:
            # Notify all chat members
            for member in chat.members:
                if member.user_id != user_id or delete_for_everyone:  # Always notify others, notify self only if delete_for_everyone
                    await self.connection_manager.send_message_deleted(member.user_id, {
                        "message_id": message_id,
                        "chat_id": message.chat_id,
                        "delete_for_everyone": delete_for_everyone
                    })
            
            logger.info(f"Message deleted: {message_id} by {user_id} (for everyone: {delete_for_everyone})")
        
        return result
    
    async def mark_messages_read(self, chat_id: str, user_id: str, 
                              message_ids: List[str] = None,
                              read_until_id: Optional[str] = None) -> bool:
        """Mark messages as read.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            message_ids: Specific message IDs to mark as read
            read_until_id: Mark all messages up to this ID as read
            
        Returns:
            bool: True if the messages were marked as read, False otherwise
            
        Raises:
            AuthorizationError: If the user is not allowed to access this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            raise ChatError(f"Chat {chat_id} not found")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        updated_messages = []
        
        # Mark specific messages as read
        if message_ids:
            for message_id in message_ids:
                message = await self.db_handler.get_message(message_id)
                if message and message.chat_id == chat_id:
                    # Update message status for this user
                    # In a real implementation, this would be stored in a separate table
                    # Here we're just updating the message itself for simplicity
                    if message.sender_id != user_id:  # Don't mark own messages as read
                        updated_message = await self.db_handler.update_message(message_id, {
                            "read_at": datetime.datetime.now(),
                            "status": MessageStatus.READ
                        })
                        if updated_message:
                            updated_messages.append(updated_message)
        
        # Mark all messages up to read_until_id as read
        elif read_until_id:
            # Get all unread messages up to read_until_id
            messages = await self.db_handler.get_chat_messages(
                chat_id=chat_id,
                before_id=read_until_id,
                limit=100  # Limit to avoid marking too many messages at once
            )
            
            for message in messages:
                if message.sender_id != user_id:  # Don't mark own messages as read
                    updated_message = await self.db_handler.update_message(message.id, {
                        "read_at": datetime.datetime.now(),
                        "status": MessageStatus.READ
                    })
                    if updated_message:
                        updated_messages.append(updated_message)
        
        # Update user's last_read_message_id in the chat
        if updated_messages and chat:
            # Find the most recent message ID
            most_recent_id = max(updated_messages, key=lambda m: m.created_at).id
            
            # Update user's chat membership with last read message
            for i, member in enumerate(chat.members):
                if member.user_id == user_id:
                    chat.members[i].last_read_message_id = most_recent_id
                    break
            
            await self.db_handler.update_chat(chat.id, {"members": [m.dict() for m in chat.members]})
        
        # Notify the sender of each message
        for message in updated_messages:
            if message.sender_id != user_id:  # Don't notify self
                await self.connection_manager.send_messages_read(message.sender_id, {
                    "message_id": message.id,
                    "chat_id": chat_id,
                    "read_by": user_id,
                    "read_at": datetime.datetime.now().isoformat()
                })
        
        logger.info(f"Messages marked as read in chat {chat_id} by {user_id}")
        return len(updated_messages) > 0
    
    async def add_reaction(self, message_id: str, user_id: str, reaction_type: str) -> Optional[Reaction]:
        """Add a reaction to a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            reaction_type: The reaction type
            
        Returns:
            Optional[Reaction]: The created reaction, or None if failed
            
        Raises:
            AuthorizationError: If the user is not allowed to react to this message
        """
        # Get message
        message = await self.db_handler.get_message(message_id)
        if not message:
            raise MessageError(f"Message {message_id} not found")
        
        # Get chat
        chat = await self.db_handler.get_chat(message.chat_id)
        if not chat:
            raise ChatError(f"Chat {message.chat_id} not found")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {message.chat_id}")
        
        # Add reaction
        reaction = await self.db_handler.add_reaction(message_id, user_id, reaction_type)
        
        if reaction:
            # Get updated message with reactions
            updated_message = await self.db_handler.get_message(message_id)
            
            # Notify all chat members
            for member in chat.members:
                await self.connection_manager.send_reaction_added(member.user_id, {
                    "message_id": message_id,
                    "chat_id": message.chat_id,
                    "user_id": user_id,
                    "reaction_type": reaction_type,
                    "reactions": [r.dict() for r in updated_message.reactions]
                })
            
            logger.info(f"Reaction added: {reaction_type} to message {message_id} by {user_id}")
        
        return reaction
    
    async def remove_reaction(self, message_id: str, user_id: str, reaction_type: str) -> bool:
        """Remove a reaction from a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            reaction_type: The reaction type
            
        Returns:
            bool: True if the reaction was removed, False otherwise
        """
        # Get message
        message = await self.db_handler.get_message(message_id)
        if not message:
            raise MessageError(f"Message {message_id} not found")
        
        # Get chat
        chat = await self.db_handler.get_chat(message.chat_id)
        if not chat:
            raise ChatError(f"Chat {message.chat_id} not found")
        
        # Remove reaction
        result = await self.db_handler.remove_reaction(message_id, user_id, reaction_type)
        
        if result:
            # Get updated message with reactions
            updated_message = await self.db_handler.get_message(message_id)
            
            # Notify all chat members
            for member in chat.members:
                await self.connection_manager.send_reaction_removed(member.user_id, {
                    "message_id": message_id,
                    "chat_id": message.chat_id,
                    "user_id": user_id,
                    "reaction_type": reaction_type,
                    "reactions": [r.dict() for r in updated_message.reactions]
                })
            
            logger.info(f"Reaction removed: {reaction_type} from message {message_id} by {user_id}")
        
        return result
    
    async def pin_message(self, message_id: str, user_id: str) -> Optional[Message]:
        """Pin a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            
        Returns:
            Optional[Message]: The updated message, or None if not found
            
        Raises:
            AuthorizationError: If the user is not allowed to pin messages in this chat
        """
        # Get message
        message = await self.db_handler.get_message(message_id)
        if not message:
            return None
        
        # Get chat
        chat = await self.db_handler.get_chat(message.chat_id)
        if not chat:
            return None
        
        # Check if user is an admin
        if not chat.is_admin(user_id):
            raise AuthorizationError(f"User {user_id} is not an admin of chat {message.chat_id}")
        
        # Pin message
        updated_message = await self.db_handler.update_message(message_id, {"is_pinned": True})
        
        if updated_message:
            # Notify all chat members
            for member in chat.members:
                await self.connection_manager.send_message_pinned(member.user_id, {
                    "message_id": message_id,
                    "chat_id": message.chat_id,
                    "pinned_by": user_id
                })
            
            logger.info(f"Message pinned: {message_id} by {user_id}")
        
        return updated_message
    
    async def unpin_message(self, message_id: str, user_id: str) -> Optional[Message]:
        """Unpin a message.
        
        Args:
            message_id: The message ID
            user_id: The user ID
            
        Returns:
            Optional[Message]: The updated message, or None if not found
            
        Raises:
            AuthorizationError: If the user is not allowed to unpin messages in this chat
        """
        # Get message
        message = await self.db_handler.get_message(message_id)
        if not message:
            return None
        
        # Get chat
        chat = await self.db_handler.get_chat(message.chat_id)
        if not chat:
            return None
        
        # Check if user is an admin
        if not chat.is_admin(user_id):
            raise AuthorizationError(f"User {user_id} is not an admin of chat {message.chat_id}")
        
        # Unpin message
        updated_message = await self.db_handler.update_message(message_id, {"is_pinned": False})
        
        if updated_message:
            # Notify all chat members
            for member in chat.members:
                await self.connection_manager.send_message_unpinned(member.user_id, {
                    "message_id": message_id,
                    "chat_id": message.chat_id,
                    "unpinned_by": user_id
                })
            
            logger.info(f"Message unpinned: {message_id} by {user_id}")
        
        return updated_message
    
    async def get_pinned_messages(self, chat_id: str, user_id: str) -> List[Message]:
        """Get all pinned messages in a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            
        Returns:
            List[Message]: The pinned messages
            
        Raises:
            AuthorizationError: If the user is not allowed to access this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            raise ChatError(f"Chat {chat_id} not found")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        # Get pinned messages
        messages = await self.db_handler.list("messages", {
            "chat_id": chat_id,
            "is_pinned": True,
            "is_deleted": False
        })
        
        # Convert to Message objects
        pinned_messages = []
        for msg_data in messages:
            message = Message.from_db_dict(msg_data)
            
            # Decrypt content if needed
            if chat.is_encrypted and message.content:
                message.content = await self.security_manager.decrypt(message.content)
            
            pinned_messages.append(message)
        
        return pinned_messages
    
    # File operations
    
    async def upload_file(self, chat_id: str, user_id: str, file_data: bytes,
                        file_name: str, content_type: Optional[str] = None) -> str:
        """Upload a file.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            file_data: The file data
            file_name: The file name
            content_type: The file content type
            
        Returns:
            str: The file URL
            
        Raises:
            ValidationError: If the file is invalid
            AuthorizationError: If the user is not allowed to upload files to this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            raise ChatError(f"Chat {chat_id} not found")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        # Validate file
        await self.storage_handler.validate_file(
            file_data=file_data,
            file_name=file_name,
            max_size_mb=self.config.max_file_size_mb,
            allowed_extensions=[ext.lower() for ext in self.config.allowed_extensions]
        )
        
        # Determine content type if not provided
        if not content_type:
            content_type = self.storage_handler.get_content_type(file_name)
        
        # Generate unique file name
        _, ext = os.path.splitext(file_name)
        unique_name = f"{chat_id}/{uuid.uuid4()}{ext}"
        
        # Upload file
        file_url = await self.storage_handler.save_file(
            file_data=file_data,
            file_name=unique_name,
            content_type=content_type
        )
        
        # Track analytics
        await self.analytics_service.track_file_uploaded(
            file_id=unique_name,
            user_id=user_id,
            file_type=ext.lstrip(".").lower(),
            size=len(file_data)
        )
        
        logger.info(f"File uploaded: {unique_name} by {user_id} to chat {chat_id}")
        return file_url
    
    async def send_file_message(self, sender_id: str, chat_id: str, file_url: str,
                              file_name: str, content_type: str,
                              caption: Optional[str] = None) -> Message:
        """Send a file message.
        
        Args:
            sender_id: The sender ID
            chat_id: The chat ID
            file_url: The file URL
            file_name: The file name
            content_type: The file content type
            caption: The message caption
            
        Returns:
            Message: The created message
            
        Raises:
            ValidationError: If the message data is invalid
            AuthorizationError: If the sender is not allowed to send messages to this chat
        """
        # Determine message type based on content type
        message_type = MessageType.FILE
        if content_type.startswith("image/"):
            message_type = MessageType.IMAGE
        elif content_type.startswith("video/"):
            message_type = MessageType.VIDEO
        elif content_type.startswith("audio/"):
            message_type = MessageType.VOICE
        
        # Get file info
        file_info = await self.storage_handler.get_file_info(file_url)
        
        # Create attachment
        attachment = Attachment(
            file_name=file_name,
            file_size=file_info.get("size", 0) if file_info else 0,
            file_type=content_type,
            file_url=file_url
        )
        
        # Create message with attachment
        message_data = MessageCreate(
            chat_id=chat_id,
            content=caption or "",
            message_type=message_type
        )
        
        # Send message
        message = await self.send_message(sender_id, message_data)
        
        # Add attachment to message
        message.attachments.append(attachment)
        
        # Update message with attachment
        updated_message = await self.db_handler.update_message(
            message.id,
            {"attachments": [a.dict() for a in message.attachments]}
        )
        
        return updated_message or message
    
    # Search and analytics
    
    async def search_messages(self, user_id: str, query: str, 
                            chat_id: Optional[str] = None, 
                            limit: int = 20) -> List[Message]:
        """Search for messages.
        
        Args:
            user_id: The user ID
            query: The search query
            chat_id: The chat ID to restrict search to (optional)
            limit: Maximum number of results
            
        Returns:
            List[Message]: The matching messages
            
        Raises:
            AuthorizationError: If the user is not allowed to access this chat
        """
        # If chat_id provided, verify user is a member
        if chat_id:
            chat = await self.db_handler.get_chat(chat_id)
            if not chat:
                raise ChatError(f"Chat {chat_id} not found")
            
            if not chat.is_member(user_id):
                raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        # Search messages
        messages = await self.db_handler.search_messages(
            query=query,
            user_id=user_id,
            chat_id=chat_id,
            limit=limit
        )
        
        # Decrypt content if needed
        for i, message in enumerate(messages):
            chat = await self.db_handler.get_chat(message.chat_id)
            if chat and chat.is_encrypted and message.content:
                messages[i].content = await self.security_manager.decrypt(message.content)
        
        return messages
    
    async def get_chat_stats(self, chat_id: str, user_id: str) -> Dict[str, Any]:
        """Get statistics for a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            
        Returns:
            Dict[str, Any]: Chat statistics
            
        Raises:
            AuthorizationError: If the user is not allowed to access this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            raise ChatError(f"Chat {chat_id} not found")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        # Get stats
        stats = await self.db_handler.get_chat_stats(chat_id)
        
        return stats
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dict[str, Any]: User statistics
        """
        # Get user stats from database
        db_stats = await self.db_handler.get_user_stats(user_id)
        
        # Get analytics stats
        analytics_stats = await self.analytics_service.get_user_stats(user_id)
        
        # Merge stats
        stats = {**db_stats, **analytics_stats}
        
        return stats
    
    # Real-time operations
    
    async def send_typing_indicator(self, chat_id: str, user_id: str, is_typing: bool) -> bool:
        """Send a typing indicator.
        
        Args:
            chat_id: The chat ID
            user_id: The user ID
            is_typing: Whether the user is typing
            
        Returns:
            bool: True if the indicator was sent, False otherwise
            
        Raises:
            AuthorizationError: If the user is not allowed to access this chat
        """
        # Get chat
        chat = await self.db_handler.get_chat(chat_id)
        if not chat:
            raise ChatError(f"Chat {chat_id} not found")
        
        # Check if user is a member
        if not chat.is_member(user_id):
            raise AuthorizationError(f"User {user_id} is not a member of chat {chat_id}")
        
        # Update user typing status in chat
        for i, member in enumerate(chat.members):
            if member.user_id == user_id:
                chat.members[i].typing_at = datetime.datetime.now() if is_typing else None
                break
        
        await self.db_handler.update_chat(chat.id, {"members": [m.dict() for m in chat.members]})
        
        # Get user info
        user = await self.db_handler.get_user(user_id)
        username = user.username if user else user_id
        
        # Send typing indicator to all other members
        for member in chat.members:
            if member.user_id != user_id:
                await self.connection_manager.send_typing_indicator(member.user_id, {
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": username,
                    "is_typing": is_typing,
                    "timestamp": datetime.datetime.now().isoformat()
                })
        
        return True