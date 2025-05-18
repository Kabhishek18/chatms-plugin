"""
Apple Push Notification Service (APNs) handler for the ChatMS plugin.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import jwt
from aioapns import APNs, NotificationRequest, NotificationResponse, PushType
from aioapns.exceptions import APNSException

from ..config import Config
from ..exceptions import NotificationError
from .base import BaseNotificationHandler


logger = logging.getLogger(__name__)


class APNSNotificationHandler(BaseNotificationHandler):
    """Notification handler for Apple Push Notification Service (APNs)."""
    
    def __init__(self, config: Config):
        """Initialize the APNs notification handler.
        
        Args:
            config: Configuration object
        """
        super().__init__(config)
        self.key_file_path = config.apns_key_file
        self.bundle_id = None
        self.team_id = None
        self.key_id = None
        self.is_prod = True  # Use production environment by default
        self.apns_client = None
        
        # Extract additional configuration from credentials if available
        if config.storage_credentials and isinstance(config.storage_credentials, dict):
            self.bundle_id = config.storage_credentials.get('bundle_id')
            self.team_id = config.storage_credentials.get('team_id')
            self.key_id = config.storage_credentials.get('key_id')
            self.is_prod = config.storage_credentials.get('is_prod', True)
    
    async def init(self) -> None:
        """Initialize the APNs notification handler."""
        try:
            # Validate configuration
            if not self.key_file_path or not Path(self.key_file_path).exists():
                raise NotificationError(f"APNs key file not found: {self.key_file_path}")
            
            if not self.bundle_id:
                raise NotificationError("APNs bundle ID is required")
            
            if not self.team_id:
                raise NotificationError("APNs team ID is required")
            
            if not self.key_id:
                raise NotificationError("APNs key ID is required")
            
            # Read key file
            with open(self.key_file_path, 'rb') as f:
                key = f.read()
            
            # Initialize APNs client
            self.apns_client = APNs(
                key=key,
                key_id=self.key_id,
                team_id=self.team_id,
                bundle_id=self.bundle_id,
                use_sandbox=not self.is_prod,
            )
            
            logger.info("APNs notification handler initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize APNs: {e}")
            # Fall back to base implementation
            await super().init()
    
    async def close(self) -> None:
        """Close the APNs notification handler."""
        if self.apns_client:
            await self.apns_client.close()
    
    async def send_notification(self, user_id: str, title: str, body: str, 
                             data: Optional[Dict[str, Any]] = None) -> bool:
        """Send an APNs notification to a user.
        
        Args:
            user_id: The user ID
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        try:
            # Check if APNs is initialized
            if not self.apns_client:
                # Fall back to base implementation
                return await super().send_notification(user_id, title, body, data)
            
            # Get device tokens for the user
            device_tokens = await self._get_device_tokens(user_id)
            
            if not device_tokens:
                logger.warning(f"No APNs device tokens found for user {user_id}")
                return False
            
            # Track successful sends
            success_count = 0
            
            # Send notifications to all devices
            for token in device_tokens:
                # Create payload
                payload = {
                    "aps": {
                        "alert": {
                            "title": title,
                            "body": body
                        },
                        "sound": "default",
                        "badge": 1,
                        "mutable-content": 1
                    }
                }
                
                # Add custom data
                if data:
                    payload.update(data)
                
                # Create notification request
                notification = NotificationRequest(
                    device_token=token,
                    message=payload,
                    push_type=PushType.ALERT
                )
                
                # Send notification
                try:
                    response = await self.apns_client.send_notification(notification)
                    
                    if response.is_successful:
                        success_count += 1
                    else:
                        logger.warning(f"Failed to send APNs notification to device {token}: {response.description}")
                        
                        # Handle token invalidation
                        if response.status == "410" or (response.status == "400" and "BadDeviceToken" in response.description):
                            # Token is invalid or expired, remove it
                            await self.unregister_device(user_id, token)
                            
                except APNSException as e:
                    logger.error(f"APNs error: {e}")
            
            logger.info(f"APNs notification sent to {success_count}/{len(device_tokens)} devices for user {user_id}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send APNs notification to user {user_id}: {e}")
            # Fall back to base implementation
            return await super().send_notification(user_id, title, body, data)
    
    async def send_bulk_notification(self, user_ids: List[str], title: str, body: str,
                                  data: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Send an APNs notification to multiple users.
        
        Args:
            user_ids: The user IDs
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            Dict[str, bool]: A dictionary mapping user IDs to success status
        """
        results = {}
        
        # Process each user
        for user_id in user_ids:
            results[user_id] = await self.send_notification(user_id, title, body, data)
        
        return results
    
    async def register_device(self, user_id: str, device_token: str, device_type: str) -> bool:
        """Register a device for APNs notifications.
        
        Args:
            user_id: The user ID
            device_token: The device token
            device_type: The device type (should be 'ios')
            
        Returns:
            bool: True if the device was registered, False otherwise
        """
        try:
            # Validate device type
            if device_type.lower() != 'ios':
                logger.warning(f"Invalid device type for APNs: {device_type}")
                return False
            
            # Validate token format (simple validation)
            if not device_token or len(device_token) < 32:
                logger.warning(f"Invalid APNs device token format: {device_token}")
                return False
            
            # In a real implementation, store the token in the database
            # For now, we'll just log it
            logger.info(f"APNs device registered for user {user_id}: {device_token}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to register APNs device for user {user_id}: {e}")
            return False
    
    async def unregister_device(self, user_id: str, device_token: str) -> bool:
        """Unregister a device for APNs notifications.
        
        Args:
            user_id: The user ID
            device_token: The device token
            
        Returns:
            bool: True if the device was unregistered, False otherwise
        """
        try:
            # In a real implementation, remove the token from the database
            # For now, we'll just log it
            logger.info(f"APNs device unregistered for user {user_id}: {device_token}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister APNs device for user {user_id}: {e}")
            return False
    
    async def _get_device_tokens(self, user_id: str) -> List[str]:
        """Get APNs device tokens for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[str]: List of device tokens
        """
        # In a real implementation, retrieve tokens from the database
        # For now, return a dummy token for demonstration
        return [f"dummy_apns_token_{user_id}"]
    
    async def send_message_notification(self, user_id: str, sender_name: str, chat_name: str,
                                      message_content: str, chat_id: str, message_id: str) -> bool:
        """Send an APNs notification for a new message.
        
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
        title = f"{sender_name}"
        body = message_content
        
        # Create notification data
        data = {
            "chatms-data": {
                "type": "new_message",
                "chat_id": chat_id,
                "message_id": message_id,
                "sender_name": sender_name,
                "chat_name": chat_name
            }
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)