# chatms-plugin/api/websocket.py

"""
WebSocket API implementation for the ChatMS plugin.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set, Union

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ..config import Config
from ..core.chat_system import ChatSystem
from ..core.connection import ConnectionManager
from ..exceptions import AuthenticationError


logger = logging.getLogger(__name__)


class WebSocketAPI:
    """WebSocket API implementation for the ChatMS plugin."""
    
    def __init__(self, chat_system: ChatSystem, app: Optional[FastAPI] = None):
        """Initialize the WebSocket API.
        
        Args:
            chat_system: The chat system instance
            app: The FastAPI app (optional)
        """
        self.chat_system = chat_system
        self.app = app
        
        # Register route if app is provided
        if app:
            self.register_to_app(app)
    
    def register_to_app(self, app: FastAPI, path: str = "/ws/{user_id}"):
        """Register the WebSocket route to a FastAPI app.
        
        Args:
            app: The FastAPI app
            path: The WebSocket path
        """
        @app.websocket(path)
        async def websocket_endpoint(websocket: WebSocket, user_id: str):
            await self.handle_websocket(websocket, user_id)
    
    async def handle_websocket(self, websocket: WebSocket, user_id: str):
        """Handle WebSocket connections.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
        """
        # Authenticate user
        try:
            token = websocket.query_params.get("token")
            if not token:
                await websocket.close(code=1008, reason="Missing token")
                return
            
            # Verify token
            authenticated_user_id = await self.chat_system.security_manager.get_user_id_from_token(token)
            
            if authenticated_user_id != user_id:
                await websocket.close(code=1008, reason="Invalid token")
                return
            
            # Accept connection
            await self.chat_system.connection_manager.connect(websocket, user_id)
            
            try:
                # Process messages
                while True:
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    
                    # Handle different message types
                    await self._handle_message(websocket, user_id, data)
                    
            except WebSocketDisconnect:
                # Handle disconnection
                await self.chat_system.connection_manager.disconnect(websocket, user_id)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await self.chat_system.connection_manager.disconnect(websocket, user_id)
        
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            await websocket.close(code=1008, reason="Authentication failed")
    
    async def _handle_message(self, websocket: WebSocket, user_id: str, data: Dict[str, Any]):
        """Handle a WebSocket message.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
            data: The message data
            
        Raises:
            ValueError: If message type is invalid
        """
        message_type = data.get("type")
        
        if message_type == "join_chat":
            await self._handle_join_chat(websocket, user_id, data)
        
        elif message_type == "leave_chat":
            await self._handle_leave_chat(websocket, user_id, data)
        
        elif message_type == "send_message":
            await self._handle_send_message(websocket, user_id, data)
        
        elif message_type == "typing":
            await self._handle_typing(websocket, user_id, data)
        
        elif message_type == "read":
            await self._handle_read(websocket, user_id, data)
        
        elif message_type == "ping":
            await self._handle_ping(websocket, data)
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            })
    
    async def _handle_join_chat(self, websocket: WebSocket, user_id: str, data: Dict[str, Any]):
        """Handle a join chat message.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
            data: The message data
        """
        chat_id = data.get("chat_id")
        if not chat_id:
            await websocket.send_json({
                "type": "error",
                "message": "Missing chat_id"
            })
            return
        
        try:
            # Check if user is member of the chat
            chat = await self.chat_system.get_chat(chat_id, user_id)
            if chat:
                await self.chat_system.connection_manager.join_chat(websocket, chat_id)
                
                # Send success response
                await websocket.send_json({
                    "type": "chat_joined",
                    "chat_id": chat_id
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Chat not found or you're not a member"
                })
        except Exception as e:
            logger.error(f"Error joining chat: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error joining chat: {str(e)}"
            })
    
    
    # chatms-plugin/api/websocket.py (continued)

    async def _handle_leave_chat(self, websocket: WebSocket, user_id: str, data: Dict[str, Any]):
        """Handle a leave chat message.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
            data: The message data
        """
        chat_id = data.get("chat_id")
        if not chat_id:
            await websocket.send_json({
                "type": "error",
                "message": "Missing chat_id"
            })
            return
        
        try:
            await self.chat_system.connection_manager.leave_chat(websocket, chat_id)
            
            # Send success response
            await websocket.send_json({
                "type": "chat_left",
                "chat_id": chat_id
            })
        except Exception as e:
            logger.error(f"Error leaving chat: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error leaving chat: {str(e)}"
            })
    
    async def _handle_send_message(self, websocket: WebSocket, user_id: str, data: Dict[str, Any]):
        """Handle a send message message.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
            data: The message data
        """
        chat_id = data.get("chat_id")
        content = data.get("content")
        message_type = data.get("message_type", "text")
        reply_to_id = data.get("reply_to_id")
        mentions = data.get("mentions", [])
        
        if not chat_id or not content:
            await websocket.send_json({
                "type": "error",
                "message": "Missing chat_id or content"
            })
            return
        
        try:
            from ..models.message import MessageCreate
            
            message_data = MessageCreate(
                chat_id=chat_id,
                content=content,
                message_type=message_type,
                reply_to_id=reply_to_id,
                mentions=mentions
            )
            
            message = await self.chat_system.send_message(user_id, message_data)
            
            # Send success response with created message
            await websocket.send_json({
                "type": "message_sent",
                "message": message.dict()
            })
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error sending message: {str(e)}"
            })
    
    async def _handle_typing(self, websocket: WebSocket, user_id: str, data: Dict[str, Any]):
        """Handle a typing message.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
            data: The message data
        """
        chat_id = data.get("chat_id")
        is_typing = data.get("is_typing", True)
        
        if not chat_id:
            await websocket.send_json({
                "type": "error",
                "message": "Missing chat_id"
            })
            return
        
        try:
            result = await self.chat_system.send_typing_indicator(chat_id, user_id, is_typing)
            
            # No response needed, typing indicators are broadcast to other users
        except Exception as e:
            logger.error(f"Error sending typing indicator: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error sending typing indicator: {str(e)}"
            })
    
    async def _handle_read(self, websocket: WebSocket, user_id: str, data: Dict[str, Any]):
        """Handle a message read notification.
        
        Args:
            websocket: The WebSocket connection
            user_id: The user ID
            data: The message data
        """
        chat_id = data.get("chat_id")
        message_ids = data.get("message_ids", [])
        read_until_id = data.get("read_until_id")
        
        if not chat_id:
            await websocket.send_json({
                "type": "error",
                "message": "Missing chat_id"
            })
            return
        
        try:
            result = await self.chat_system.mark_messages_read(
                chat_id=chat_id,
                user_id=user_id,
                message_ids=message_ids,
                read_until_id=read_until_id
            )
            
            # Send success response
            await websocket.send_json({
                "type": "messages_read_success",
                "chat_id": chat_id
            })
        except Exception as e:
            logger.error(f"Error marking messages as read: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error marking messages as read: {str(e)}"
            })
    
    async def _handle_ping(self, websocket: WebSocket, data: Dict[str, Any]):
        """Handle a ping message.
        
        Args:
            websocket: The WebSocket connection
            data: The message data
        """
        timestamp = data.get("timestamp")
        
        # Respond with pong
        await websocket.send_json({
            "type": "pong",
            "timestamp": timestamp
        })