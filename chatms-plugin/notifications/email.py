"""
Email notification handler for the ChatMS plugin.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from ..config import Config
from ..exceptions import NotificationError
from .base import BaseNotificationHandler


logger = logging.getLogger(__name__)


class EmailNotificationHandler(BaseNotificationHandler):
    """Notification handler for email notifications."""
    
    def __init__(self, config: Config):
        """Initialize the email notification handler.
        
        Args:
            config: Configuration object
        """
        super().__init__(config)
        
        # Email configuration (would normally be in Config)
        self.smtp_server = "smtp.example.com"
        self.smtp_port = 587
        self.smtp_username = "notifications@example.com"
        self.smtp_password = "password"
        self.from_email = "notifications@example.com"
        self.from_name = "ChatMS Notifications"
        
        self.loop = None
    
    async def init(self) -> None:
        """Initialize the email notification handler."""
        self.loop = asyncio.get_event_loop()
        logger.info("Email notification handler initialized")
    
    async def close(self) -> None:
        """Close the email notification handler."""
        # Nothing to close
        pass
    
    async def send_notification(self, user_id: str, title: str, body: str, 
                             data: Optional[Dict[str, Any]] = None) -> bool:
        """Send an email notification to a user.
        
        Args:
            user_id: The user ID
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        try:
            # Get user email address
            user_email = await self._get_user_email(user_id)
            
            if not user_email:
                logger.warning(f"No email address found for user {user_id}")
                return False
            
            # Create email message
            message = await self._create_email_message(user_email, title, body, data)
            
            # Send email
            return await self._send_email(user_email, message)
            
        except Exception as e:
            logger.error(f"Failed to send email notification to user {user_id}: {e}")
            # Fall back to base implementation
            return await super().send_notification(user_id, title, body, data)
    
    async def send_bulk_notification(self, user_ids: List[str], title: str, body: str,
                                  data: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Send an email notification to multiple users.
        
        Args:
            user_ids: The user IDs
            title: The notification title
            body: The notification body
            data: Additional data to include with the notification
            
        Returns:
            Dict[str, bool]: A dictionary mapping user IDs to success status
        """
        results = {}
        
        # Send emails to each user individually
        for user_id in user_ids:
            results[user_id] = await self.send_notification(user_id, title, body, data)
        
        return results
    
    async def _get_user_email(self, user_id: str) -> Optional[str]:
        """Get the email address for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[str]: The user's email address, or None if not found
        """
        # In a real implementation, we would retrieve the email from the database
        # Here, we'll return a dummy email for demonstration
        # This should be replaced with actual database access
        return f"{user_id}@example.com"
    
    async def _create_email_message(self, to_email: str, title: str, body: str,
                                 data: Optional[Dict[str, Any]] = None) -> MIMEMultipart:
        """Create an email message.
        
        Args:
            to_email: The recipient's email address
            title: The email subject
            body: The email body
            data: Additional data to include in the email
            
        Returns:
            MIMEMultipart: The email message
        """
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = title
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = to_email
        
        # Create plain text and HTML versions of the body
        plain_text = body
        html_text = f"<html><body><h1>{title}</h1><p>{body}</p>"
        
        # Add data if provided
        if data:
            plain_text += "\n\nAdditional Information:\n"
            html_text += "<h2>Additional Information:</h2><ul>"
            
            for key, value in data.items():
                plain_text += f"\n{key}: {value}"
                html_text += f"<li><strong>{key}:</strong> {value}</li>"
            
            html_text += "</ul>"
        
        html_text += "</body></html>"
        
        # Attach parts
        message.attach(MIMEText(plain_text, "plain"))
        message.attach(MIMEText(html_text, "html"))
        
        return message
    
    async def _send_email(self, to_email: str, message: MIMEMultipart) -> bool:
        """Send an email.
        
        Args:
            to_email: The recipient's email address
            message: The email message
            
        Returns:
            bool: True if the email was sent, False otherwise
        """
        # In a real implementation, this would actually send the email
        # For demonstration, we'll just log it
        logger.info(f"Email sent to {to_email}: {message['Subject']}")
        
        # TODO: Uncomment this code to actually send emails
        """
        try:
            # Connect to SMTP server
            smtp = await self.loop.run_in_executor(
                None,
                lambda: smtplib.SMTP(self.smtp_server, self.smtp_port)
            )
            
            # Start TLS
            await self.loop.run_in_executor(
                None,
                lambda: smtp.starttls()
            )
            
            # Login
            await self.loop.run_in_executor(
                None,
                lambda: smtp.login(self.smtp_username, self.smtp_password)
            )
            
            # Send email
            await self.loop.run_in_executor(
                None,
                lambda: smtp.send_message(message)
            )
            
            # Close connection
            await self.loop.run_in_executor(
                None,
                lambda: smtp.quit()
            )
            
            logger.info(f"Email sent to {to_email}: {message['Subject']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
        """
        
        return True
    
    async def send_message_notification(self, user_id: str, sender_name: str, chat_name: str,
                                      message_content: str, chat_id: str, message_id: str) -> bool:
        """Send an email notification for a new message.
        
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
        # Create notification title and body
        title = f"New message from {sender_name} in {chat_name}"
        body = message_content
        
        # Create notification data with link to the message
        data = {
            "type": "new_message",
            "chat_id": chat_id,
            "message_id": message_id,
            "sender_name": sender_name,
            "chat_name": chat_name,
            "link": f"https://example.com/chats/{chat_id}/messages/{message_id}"
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)
    
    async def send_chat_created_notification(self, user_id: str, creator_name: str, 
                                          chat_name: str, chat_id: str) -> bool:
        """Send an email notification for a new chat.
        
        Args:
            user_id: The user ID
            creator_name: The name of the chat creator
            chat_name: The name of the chat
            chat_id: The chat ID
            
        Returns:
            bool: True if the notification was sent, False otherwise
        """
        # Create notification title and body
        title = f"You've been added to a new chat: {chat_name}"
        body = f"{creator_name} has added you to the chat '{chat_name}'."
        
        # Create notification data with link to the chat
        data = {
            "type": "chat_created",
            "chat_id": chat_id,
            "creator_name": creator_name,
            "chat_name": chat_name,
            "link": f"https://example.com/chats/{chat_id}"
        }
        
        # Send notification
        return await self.send_notification(user_id, title, body, data)