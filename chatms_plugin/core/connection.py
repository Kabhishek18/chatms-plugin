# chatms_plugin/core/connection.py

"""
WebSocket connection manager for the ChatMS plugin.
"""

import asyncio
import datetime
import json
import logging
from typing import Any, Dict, List, Optional, Set, Union

from fastapi import WebSocket, WebSocketDisconnect

from ..config import Config
from ..exceptions import ConnectionError


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time messaging."""
    
    def __init__(self, config: Config):
        """Initialize the connection manager.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # chat_id -> set of WebSockets
        self.user_connections: Dict[str, Set[WebSocket]] = {}  # user_id -> set of WebSockets
        self.ping_task = None
    
    async def init(self) -> None:
        """Initialize the connection manager."""
        # Start ping task
        self.ping_task = asyncio.create_task(self._ping_clients())
    
    async def close(self) -> None:
        """Close all connections."""
        # Cancel ping task
        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
        
        # Close all WebSocket connections
        for user_id, connections in list(self.user_connections.items()):
            for connection in list(connections):
                try:
                    await connection.close()
                except Exception as e:
                    logger.error(f"Error closing connection for user {user_id}: {e}")
        
        # Clear connection dictionaries
        self.active_connections.clear()
        self.user_connections.clear()
    
    async def _ping_clients(self) -> None:
        """Send periodic pings to clients to keep connections alive."""
        while True:
            try:
                # Sleep first to avoid immediate ping on startup
                await asyncio.sleep(self.config.websocket_ping_interval)
                
                # Ping all connections - create a copy to avoid iteration issues
                user_connections_copy = dict(self.user_connections)
                for user_id, connections in user_connections_copy.items():
                    for connection in list(connections):
                        try:
                            await connection.send_json({"type": "ping", "timestamp": datetime.datetime.now().isoformat()})
                        except Exception as e:
                            logger.error(f"Error pinging user {user_id}: {e}")
                            # Remove failed connection
                            await self.disconnect(connection, user_id)
            except asyncio.CancelledError:
                # Task was cancelled, exit
                break
            except Exception as e:
                logger.error(f"Error in ping task: {e}")
                # Sleep briefly to avoid tight loop in case of persistent error
                await asyncio.sleep(1)
    
    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Connect a user to WebSocket.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
            
        Raises:
            ConnectionError: If there was an error accepting the connection
        """
        try:
            await websocket.accept()
        except Exception as e:
            raise ConnectionError(f"Failed to accept WebSocket connection: {e}")
        
        # Add to user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        
        self.user_connections[user_id].add(websocket)
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        logger.info(f"User {user_id} connected")
    
    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Disconnect a user from WebSocket.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
        """
        # Remove from user connections - avoid iteration issues
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove from all chat rooms - create a copy to avoid iteration issues
        chat_rooms_to_remove = []
        for chat_id, connections in list(self.active_connections.items()):
            connections.discard(websocket)
            if not connections:
                chat_rooms_to_remove.append(chat_id)
        
        # Remove empty chat rooms
        for chat_id in chat_rooms_to_remove:
            self.active_connections.pop(chat_id, None)
        
        logger.info(f"User {user_id} disconnected")
    
    async def join_chat(self, websocket: WebSocket, chat_id: str) -> None:
        """Add a connection to a chat room.
        
        Args:
            websocket: The WebSocket connection
            chat_id: The chat ID
        """
        if chat_id not in self.active_connections:
            self.active_connections[chat_id] = set()
        
        self.active_connections[chat_id].add(websocket)
        
        # Send joined message
        await websocket.send_json({
            "type": "chat_joined",
            "chat_id": chat_id,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        logger.info(f"WebSocket connection joined chat {chat_id}")
    
    async def leave_chat(self, websocket: WebSocket, chat_id: str) -> None:
        """Remove a connection from a chat room.
        
        Args:
            websocket: The WebSocket connection
            chat_id: The chat ID
        """
        if chat_id in self.active_connections:
            self.active_connections[chat_id].discard(websocket)
            if not self.active_connections[chat_id]:
                del self.active_connections[chat_id]
            
            # Send left message
            try:
                await websocket.send_json({
                    "type": "chat_left",
                    "chat_id": chat_id,
                    "timestamp": datetime.datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error sending chat_left message: {e}")
    
    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connections in a chat room.
        
        Args:
            message: The message to broadcast
        """
        chat_id = message.get("chat_id")
        if not chat_id:
            logger.error("Cannot broadcast message without chat_id")
            return
        
        if chat_id in self.active_connections:
            # Add message type if not present
            if "type" not in message:
                message["type"] = "message"
            
            # Add timestamp if not present
            if "timestamp" not in message:
                message["timestamp"] = datetime.datetime.now().isoformat()
            
            # Send to all connections in the chat - create a copy to avoid iteration issues
            connections_copy = list(self.active_connections[chat_id])
            for connection in connections_copy:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast message to chat {chat_id}: {e}")
                    # Connection might be closed, will be removed on next ping
    
    async def send_personal_message(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific user across all their connections.
        
        Args:
            user_id: The user ID
            message: The message to send
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        if user_id not in self.user_connections:
            return False
        
        # Add message type if not present
        if "type" not in message:
            message["type"] = "personal_message"
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.datetime.now().isoformat()
        
        # Send to all user connections - create a copy to avoid iteration issues
        connections_copy = list(self.user_connections[user_id])
        sent = False
        for connection in connections_copy:
            try:
                await connection.send_json(message)
                sent = True
            except Exception as e:
                logger.error(f"Failed to send personal message to user {user_id}: {e}")
                # Connection might be closed, will be removed on next ping
        
        return sent
    
    # Specific message type senders
    
    async def send_new_message(self, user_id: str, message_data: Dict[str, Any]) -> bool:
        """Send a new message notification to a user.
        
        Args:
            user_id: The user ID
            message_data: The message data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        message_data["type"] = "new_message"
        return await self.send_personal_message(user_id, message_data)
    
    async def send_message_updated(self, user_id: str, message_data: Dict[str, Any]) -> bool:
        """Send a message updated notification to a user.
        
        Args:
            user_id: The user ID
            message_data: The message data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        message_data["type"] = "message_updated"
        return await self.send_personal_message(user_id, message_data)
    
    async def send_message_deleted(self, user_id: str, delete_data: Dict[str, Any]) -> bool:
        """Send a message deleted notification to a user.
        
        Args:
            user_id: The user ID
            delete_data: The deletion data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        delete_data["type"] = "message_deleted"
        return await self.send_personal_message(user_id, delete_data)
    
    async def send_message_delivered(self, user_id: str, delivery_data: Dict[str, Any]) -> bool:
        """Send a message delivered notification to a user.
        
        Args:
            user_id: The user ID
            delivery_data: The delivery data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        delivery_data["type"] = "message_delivered"
        return await self.send_personal_message(user_id, delivery_data)
    
    async def send_messages_read(self, user_id: str, read_data: Dict[str, Any]) -> bool:
        """Send a messages read notification to a user.
        
        Args:
            user_id: The user ID
            read_data: The read data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        read_data["type"] = "messages_read"
        return await self.send_personal_message(user_id, read_data)
    
    async def send_reaction_added(self, user_id: str, reaction_data: Dict[str, Any]) -> bool:
        """Send a reaction added notification to a user.
        
        Args:
            user_id: The user ID
            reaction_data: The reaction data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        reaction_data["type"] = "reaction_added"
        return await self.send_personal_message(user_id, reaction_data)
    
    async def send_reaction_removed(self, user_id: str, reaction_data: Dict[str, Any]) -> bool:
        """Send a reaction removed notification to a user.
        
        Args:
            user_id: The user ID
            reaction_data: The reaction data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        reaction_data["type"] = "reaction_removed"
        return await self.send_personal_message(user_id, reaction_data)
    
    async def send_message_pinned(self, user_id: str, pin_data: Dict[str, Any]) -> bool:
        """Send a message pinned notification to a user.
        
        Args:
            user_id: The user ID
            pin_data: The pin data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        pin_data["type"] = "message_pinned"
        return await self.send_personal_message(user_id, pin_data)
    
    async def send_message_unpinned(self, user_id: str, unpin_data: Dict[str, Any]) -> bool:
        """Send a message unpinned notification to a user.
        
        Args:
            user_id: The user ID
            unpin_data: The unpin data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        unpin_data["type"] = "message_unpinned"
        return await self.send_personal_message(user_id, unpin_data)
    
    async def send_chat_created(self, user_id: str, chat_data: Dict[str, Any]) -> bool:
        """Send a chat created notification to a user.
        
        Args:
            user_id: The user ID
            chat_data: The chat data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        message = {
            "type": "chat_created",
            "chat": chat_data.dict() if hasattr(chat_data, "dict") else chat_data
        }
        return await self.send_personal_message(user_id, message)
    
    async def send_chat_updated(self, user_id: str, chat_data: Dict[str, Any]) -> bool:
        """Send a chat updated notification to a user.
        
        Args:
            user_id: The user ID
            chat_data: The chat data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        message = {
            "type": "chat_updated",
            "chat": chat_data.dict() if hasattr(chat_data, "dict") else chat_data
        }
        return await self.send_personal_message(user_id, message)
    
    async def send_chat_deleted(self, user_id: str, chat_id: str) -> bool:
        """Send a chat deleted notification to a user.
        
        Args:
            user_id: The user ID
            chat_id: The chat ID
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        message = {
            "type": "chat_deleted",
            "chat_id": chat_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        return await self.send_personal_message(user_id, message)
    
    async def send_chat_member_added(self, chat_id: str, user_id: str, chat_data: Dict[str, Any]) -> None:
        """Send a chat member added notification to all members of a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The ID of the user who was added
            chat_data: The updated chat data
        """
        message = {
            "type": "chat_member_added",
            "chat_id": chat_id,
            "user_id": user_id,
            "chat": chat_data.dict() if hasattr(chat_data, "dict") else chat_data,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Broadcast to all members, including the new member
        await self.broadcast_message(message)
        
        # Also send directly to the new member in case they're not in the chat room yet
        await self.send_personal_message(user_id, message)
    
    async def send_chat_member_removed(self, chat_id: str, user_id: str, chat_data: Dict[str, Any]) -> None:
        """Send a chat member removed notification to all members of a chat.
        
        Args:
            chat_id: The chat ID
            user_id: The ID of the user who was removed
            chat_data: The updated chat data
        """
        message = {
            "type": "chat_member_removed",
            "chat_id": chat_id,
            "user_id": user_id,
            "chat": chat_data.dict() if hasattr(chat_data, "dict") else chat_data,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Broadcast to all remaining members
        await self.broadcast_message(message)
        
        # Also send directly to the removed member
        await self.send_personal_message(user_id, message)
    
    async def send_typing_indicator(self, user_id: str, typing_data: Dict[str, Any]) -> bool:
        """Send a typing indicator notification to a user.
        
        Args:
            user_id: The user ID
            typing_data: The typing data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        typing_data["type"] = "typing_indicator"
        return await self.send_personal_message(user_id, typing_data)
    
    async def update_presence(self, presence_data: Dict[str, Any]) -> None:
        """Update and broadcast user presence to relevant users.
        
        Args:
            presence_data: The presence data
        """
        user_id = presence_data.get("user_id")
        if not user_id:
            logger.error("Cannot update presence without user_id")
            return
        
        # Add message type if not present
        if "type" not in presence_data:
            presence_data["type"] = "presence_update"
        
        # Add timestamp if not present
        if "timestamp" not in presence_data:
            presence_data["timestamp"] = datetime.datetime.now().isoformat()
        
        # In a real implementation, we would only send presence updates to users
        # who are interested in the user's presence (e.g., in the same chats)
        # For simplicity, we'll broadcast to all connected users
        user_connections_copy = dict(self.user_connections)
        for target_user_id in user_connections_copy:
            if target_user_id != user_id:  # Don't send to the user themselves
                await self.send_personal_message(target_user_id, presence_data)
    
    async def send_mention(self, user_id: str, message_data: Dict[str, Any]) -> bool:
        """Send a mention notification to a user.
        
        Args:
            user_id: The user ID
            message_data: The message data
            
        Returns:
            bool: True if message was sent to at least one connection, False otherwise
        """
        message_data["type"] = "mention"
        return await self.send_personal_message(user_id, message_data)