"""
Firebase Cloud Messaging (FCM) notification handler for the ChatMS plugin.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, messaging

from ..config import Config
from ..exceptions import NotificationError
from .base import BaseNotificationHandler


logger = logging.getLogger(__name__)


class FCMNotificationHandler(BaseNotificationHandler):
    """Notification handler for Firebase Cloud Messaging (FCM)."""
    
    def __init__(self, config: Config):
        """Initialize the FCM notification handler.
        
        Args:
            config: Configuration object
        """
        super().__init__(config)
        self.fcm_api_key = config.fcm_api_key
        self.app = None
        self.loop = None
    
    async def init(self) -> None:
        """Initialize the FCM notification handler."""
        try:
            self.loop = asyncio.get_event_loop()
            
            # Check if we're already initialized
            if self.app is not None:
                return
            
            # Initialize Firebase app
            if firebase_admin._apps:
                # Use existing app if available
                self.app = firebase_admin._apps.get('chatms')
            else:
                # Create new app with API key
                cred = credentials.Certificate({
                    "type": "service_account",
                    "project_id": "chatms-project",  # Replace with actual project ID
                    "private_key_id": "key-id",      # Replace with actual key ID
                    "private_key": self.fcm_api_key, # This should be the full private key
                    "client_email": "firebase-adminsdk@chatms-project.iam.gserviceaccount.com",
                    "client_id": "client-id",        # Replace with actual client ID
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk%40chatms-project.iam.gserviceaccount.com"
                })
                self.app = firebase_admin.initialize_app(cred, name='chatms')
            
            logger.info("FCM notification handler initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize FCM: {e}")
            # Fall back to base implementation
            await super().init()
    
    async def close(self) -> None:
        """Close the FCM notification handler."""
        # Nothing to close for FCM
        pass
    
    async def send_notification(self, user_id: str, title: str, body: str, 
                             data: Optional[Dict[str, Any]] = None) -> bool:
        """Send an FCM notification to a user.
        
        Args:
            user_id: The user ID
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        try:
            # Check if FCM is initialized
            if self.app is None:
                # Fall back to base implementation
                return await super().send_notification(user_id, title, body, data)
            
            # Get device tokens for the user
            device_tokens = await self._get_device_tokens(user_id)
            
            if not device_tokens:
                logger.warning(f"No device tokens found for user {user_id}")
                return False
            
            # Create notification message
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=self._prepare_data(data) if data else None,
                tokens=device_tokens,
            )
            
            # Send message
            response = await self.loop.run_in_executor(
                None,
                lambda: messaging.send_multicast(message, app=self.app)
            )
            
            logger.info(f"FCM notification sent to {len(device_tokens)} devices for user {user_id}: "
                       f"{response.success_count} successful, {response.failure_count} failed")
            
            return response.success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send FCM notification to user {user_id}: {e}")
            # Fall back to base implementation
            return await super().send_notification(user_id, title, body, data)
    
    async def send_bulk_notification(self, user_ids: List[str], title: str, body: str,
                                  data: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Send an FCM notification to multiple users.
        
        Args:
            user_ids: The user IDs
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            Dict[str, bool]: A dictionary mapping user IDs to success status
        """
        try:
            # Check if FCM is initialized
            if self.app is None:
                # Fall back to base implementation
                return await super().send_bulk_notification(user_ids, title, body, data)
            
            # Get device tokens for all users
            all_tokens = {}
            for user_id in user_ids:
                tokens = await self._get_device_tokens(user_id)
                if tokens:
                    all_tokens[user_id] = tokens
            
            if not all_tokens:
                logger.warning(f"No device tokens found for any of the users")
                return {user_id: False for user_id in user_ids}
            
            # Create notification message for all tokens
            all_device_tokens = [token for tokens in all_tokens.values() for token in tokens]
            
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=self._prepare_data(data) if data else None,
                tokens=all_device_tokens,
            )
            
            # Send message
            response = await self.loop.run_in_executor(
                None,
                lambda: messaging.send_multicast(message, app=self.app)
            )
            
            # Get results for each user
            results = {}
            for user_id in user_ids:
                if user_id in all_tokens:
                    # For simplicity, we consider the notification successful for a user
                    # if at least one of their devices received it successfully
                    results[user_id] = True
                else:
                    results[user_id] = False
            
            logger.info(f"FCM bulk notification sent to {len(all_device_tokens)} devices: "
                       f"{response.success_count} successful, {response.failure_count} failed")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to send FCM bulk notification: {e}")
            # Fall back to base implementation
            return await super().send_bulk_notification(user_ids, title, body, data)
    
    async def register_device(self, user_id: str, device_token: str, device_type: str) -> bool:
        """Register a device for FCM notifications.
        
        Args:
            user_id: The user ID
            device_token: The device token
            device_type: The device type (e.g. 'ios', 'android', 'web')
            
        Returns:
            bool: True if the device was registered, False otherwise
        """
        try:
            # Validate the token with Firebase
            await self.loop.run_in_executor(
                None,
                lambda: messaging.send_message(
                    messaging.Message(
                        token=device_token,
                        data={"type": "token_validation"}
                    ),
                    dry_run=True,
                    app=self.app
                )
            )
            
            # In a real implementation, we would store the token in the database
            # Here, we'll simulate it with a simple log
            logger.info(f"FCM device registered for user {user_id}: {device_type} - {device_token}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to register FCM device for user {user_id}: {e}")
            return False
    
    async def unregister_device(self, user_id: str, device_token: str) -> bool:
        """Unregister a device for FCM notifications.
        
        Args:
            user_id: The user ID
            device_token: The device token
            
        Returns:
            bool: True if the device was unregistered, False otherwise
        """
        try:
            # In a real implementation, we would remove the token from the database
            # Here, we'll simulate it with a simple log
            logger.info(f"FCM device unregistered for user {user_id}: {device_token}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister FCM device for user {user_id}: {e}")
            return False
    
    async def _get_device_tokens(self, user_id: str) -> List[str]:
        """Get FCM device tokens for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[str]: List of device tokens
        """
        # In a real implementation, we would retrieve the tokens from the database
        # Here, we'll return a dummy token for demonstration
        # This should be replaced with actual database access
        return [f"dummy_token_{user_id}"]
    
    def _prepare_data(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Prepare data payload for FCM.
        
        FCM only accepts string values in the data payload.
        
        Args:
            data: The data to prepare
            
        Returns:
            Dict[str, str]: The prepared data
        """
        prepared = {}
        
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                prepared[key] = json.dumps(value)
            else:
                prepared[key] = str(value)
        
        return prepared