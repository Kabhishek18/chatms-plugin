"""
ChatMS - Chat Messaging System Plugin

A comprehensive chat messaging system plugin for Python applications with support for
various chat types, message formats, and deployment options.

Features:
- Multiple message types: text, files, images, videos, audio, reactions
- Flexible chat types: one-to-one chats, group chats, broadcast channels
- Real-time communication: WebSocket-based messaging with typing indicators and read receipts
- Rich message features: edit, delete, pin, quote, forward, and react to messages
- Flexible storage: support for local, AWS S3, Google Cloud Storage, and Azure Blob
- Database options: PostgreSQL and MongoDB support
- Security: JWT/OAuth2 authentication, end-to-end encryption, rate limiting
- Notifications: Push notifications via FCM/APNs, email alerts
- Analytics: Usage metrics and performance tracking
"""

import logging

from .config import (
    Config, StorageType, DatabaseType, MessageStatus, 
    MessageType, ChatType, UserRole
)
from .core.chat_system import ChatSystem
from .exceptions import (
    ChatMSError, ConfigurationError, DatabaseError, StorageError,
    AuthenticationError, AuthorizationError, ValidationError,
    RateLimitError, FileError, FileSizeError, FileTypeError,
    MessageError, ChatError, UserError, ConnectionError,
    NotificationError
)
from .models.base import DatabaseModel
from .models.user import User, UserCreate, UserUpdate, UserInChat, UserPresence
from .models.chat import Chat, ChatCreate, ChatUpdate, ChatMember, ChatSettings
from .models.message import (
    Message, MessageCreate, MessageUpdate, MessageDelete, MessageReaction,
    MessageRead, MessageDelivery, Attachment, Reaction, Mention
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Silence some loggers
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Package metadata
__version__ = "0.1.0"
__author__ = "Kumar Abhishek"
__email__ = "developer@kabhishek18.com"
__license__ = "MIT"

# Set default exports
__all__ = [
    "ChatSystem",
    "Config",
    "StorageType",
    "DatabaseType",
    "MessageStatus",
    "MessageType",
    "ChatType",
    "UserRole",
    "ChatMSError",
    "ConfigurationError",
    "DatabaseError",
    "StorageError",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    "RateLimitError",
    "FileError",
    "FileSizeError",
    "FileTypeError",
    "MessageError",
    "ChatError",
    "UserError",
    "ConnectionError",
    "NotificationError",
    "DatabaseModel",
    "User",
    "UserCreate",
    "UserUpdate",
    "UserInChat",
    "UserPresence",
    "Chat",
    "ChatCreate",
    "ChatUpdate",
    "ChatMember",
    "ChatSettings",
    "Message",
    "MessageCreate",
    "MessageUpdate",
    "MessageDelete",
    "MessageReaction",
    "MessageRead",
    "MessageDelivery",
    "Attachment",
    "Reaction",
    "Mention",
]