"""
Base notification handler for the ChatMS plugin.
"""

import abc
import logging
from typing import Any, Dict, List, Optional

from ..config import Config


logger = logging.getLogger(__name__)


class BaseNotificationHandler:
    """Base notification handler for the ChatMS plugin.
    
    This class defines the interface for all notification handlers and provides
    a default implementation that simply logs notifications.
    """
    
    def __init__(self, config: Config):
        """Initialize the notification handler.
        
        Args:
            config: Configuration object
        """
        self.config = config
    
    async def init(self) -> None:
        """Initialize the notification handler."""
        logger.info("Base notification handler initialized")
    
    async def close(self) -> None:
        """Close the notification handler."""
        pass
    
    async def send_notification(self, user_id: str, title: str, body: str, 
                             data: Optional[Dict[str, Any]] = None) -> bool:
        """Send a notification to a user.
        
        Args:
            user_id: The user ID
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Base implementation just logs the notification
        logger.info(f"Notification for user {user_id}: {title} - {body}")
        
        if data:
            logger.debug(f"Notification data: {data}")
        
        return True
    
    async def send_bulk_notification(self, user_ids: List[str], title: str, body: str,
                                  data: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Send a notification to multiple users.
        
        Args:
            user_ids: The user IDs
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            Dict[str, bool]: A dictionary mapping user IDs to success status
        """
        # Base implementation sends notifications individually
        results = {}
        
        for user_id in user_ids:
            results[user_id] = await self.send_notification(user_id, title, body, data)
        
        return results
    
    async def send_message_notification(self, user_id: str, sender_name: str, chat_name: str,
                                      message_content: str, chat_id: str, message_id: str) -> bool:
        """Send a notification for a new message.
        
        Args:
            user_id: The user ID
            sender_name: The name of the message sender
            chat_name: The name of the chat
            message_content: The message content
            chat_id: The chat ID
            message_id: The message ID
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Truncate message content if too long
        if len(message_content) > 100:
            message_content = message_content[:97] + "..."
        
        # Create notification title and body
        title = f"{sender_name} in {chat_name}"
        body = message_content
        
        # Create notification data
        data = {
            "type": "new_message",
            "chat_id": chat_id,
            "message_id": message_id,
            "sender_name": sender_name
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)
    
    async def send_mention_notification(self, user_id: str, sender_name: str, chat_name: str,
                                      message_content: str, chat_id: str, message_id: str) -> bool:
        """Send a notification for a mention.
        
        Args:
            user_id: The user ID
            sender_name: The name of the message sender
            chat_name: The name of the chat
            message_content: The message content
            chat_id: The chat ID
            message_id: The message ID
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Truncate message content if too long
        if len(message_content) > 100:
            message_content = message_content[:97] + "..."
        
        # Create notification title and body
        title = f"{sender_name} mentioned you"
        body = f"In {chat_name}: {message_content}"
        
        # Create notification data
        data = {
            "type": "mention",
            "chat_id": chat_id,
            "message_id": message_id,
            "sender_name": sender_name
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)
    
    async def send_chat_created_notification(self, user_id: str, creator_name: str, 
                                          chat_name: str, chat_id: str) -> bool:
        """Send a notification for a new chat.
        
        Args:
            user_id: The user ID
            creator_name: The name of the chat creator
            chat_name: The name of the chat
            chat_id: The chat ID
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Create notification title and body
        title = "New Chat"
        body = f"{creator_name} added you to '{chat_name}'"
        
        # Create notification data
        data = {
            "type": "chat_created",
            "chat_id": chat_id,
            "creator_name": creator_name
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)
    
    async def send_chat_member_added_notification(self, user_id: str, adder_name: str,
                                              chat_name: str, chat_id: str) -> bool:
        """Send a notification when a user is added to a chat.
        
        Args:
            user_id: The user ID
            adder_name: The name of the user who added them
            chat_name: The name of the chat
            chat_id: The chat ID
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Create notification title and body
        title = "Added to Chat"
        body = f"{adder_name} added you to '{chat_name}'"
        
        # Create notification data
        data = {
            "type": "chat_member_added",
            "chat_id": chat_id,
            "adder_name": adder_name
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)
    
    async def send_chat_member_removed_notification(self, user_id: str, remover_name: str,
                                                chat_name: str, chat_id: str) -> bool:
        """Send a notification when a user is removed from a chat.
        
        Args:
            user_id: The user ID
            remover_name: The name of the user who removed them
            chat_name: The name of the chat
            chat_id: The chat ID
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Create notification title and body
        title = "Removed from Chat"
        body = f"{remover_name} removed you from '{chat_name}'"
        
        # Create notification data
        data = {
            "type": "chat_member_removed",
            "chat_id": chat_id,
            "remover_name": remover_name
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)
    
    async def send_message_reaction_notification(self, user_id: str, reactor_name: str,
                                             reaction: str, chat_name: str,
                                             chat_id: str, message_id: str) -> bool:
        """Send a notification when someone reacts to a message.
        
        Args:
            user_id: The user ID
            reactor_name: The name of the user who reacted
            reaction: The reaction emoji or type
            chat_name: The name of the chat
            chat_id: The chat ID
            message_id: The message ID
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Create notification title and body
        title = f"New Reaction in {chat_name}"
        body = f"{reactor_name} reacted with {reaction} to your message"
        
        # Create notification data
        data = {
            "type": "message_reaction",
            "chat_id": chat_id,
            "message_id": message_id,
            "reactor_name": reactor_name,
            "reaction": reaction
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)
    
    async def register_device(self, user_id: str, device_token: str, device_type: str) -> bool:
        """Register a device for push notifications.
        
        Args:
            user_id: The user ID
            device_token: The device token
            device_type: The device type (e.g. 'ios', 'android', 'web')
            
        Returns:
            bool: True if the device was registered, False otherwise
        """
        # Base implementation just logs the registration
        logger.info(f"Device registered for user {user_id}: {device_type} - {device_token}")
        return True
    
    async def unregister_device(self, user_id: str, device_token: str) -> bool:
        """Unregister a device for push notifications.
        
        Args:
            user_id: The user ID
            device_token: The device token
            
        Returns:
            bool: True if the device was unregistered, False otherwise
        """
        # Base implementation just logs the unregistration
        logger.info(f"Device unregistered for user {user_id}: {device_token}")
        return True
    
    async def get_user_devices(self, user_id: str) -> List[Dict[str, str]]:
        """Get all devices registered for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[Dict[str, str]]: A list of device information
        """
        # Base implementation returns an empty list
        return []