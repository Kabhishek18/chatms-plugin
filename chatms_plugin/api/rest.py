# chatms-plugin/api/rest.py

"""
REST API implementation for the ChatMS plugin.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from ..config import Config
from ..core.chat_system import ChatSystem
from ..exceptions import (
    AuthenticationError, AuthorizationError, ChatError, ChatMSError,
    MessageError, ValidationError
)
from ..models.chat import ChatCreate, ChatUpdate
from ..models.message import MessageCreate, MessageUpdate
from ..models.user import UserCreate, UserUpdate


logger = logging.getLogger(__name__)


class RestAPI:
    """REST API implementation for the ChatMS plugin."""
    
    def __init__(self, chat_system: ChatSystem, app: Optional[FastAPI] = None):
        """Initialize the REST API.
        
        Args:
            chat_system: The chat system instance
            app: The FastAPI app (optional)
        """
        self.chat_system = chat_system
        self.app = app
        self.router = APIRouter()
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        
        # Register routes
        self._register_routes()
    
    def _register_routes(self):
        """Register API routes."""
        # Authentication routes
        self.router.add_api_route(
            "/register", 
            self.register_user, 
            methods=["POST"],
            status_code=201,
            response_model_exclude=["hashed_password"]
        )
        
        self.router.add_api_route(
            "/token", 
            self.login, 
            methods=["POST"]
        )
        
        # User routes
        self.router.add_api_route(
            "/users/me", 
            self.get_current_user_info, 
            methods=["GET"],
            response_model_exclude=["hashed_password"]
        )
        
        self.router.add_api_route(
            "/users/me", 
            self.update_current_user, 
            methods=["PUT"],
            response_model_exclude=["hashed_password"]
        )
        
        self.router.add_api_route(
            "/users/me/status", 
            self.update_status, 
            methods=["PUT"]
        )
        
        # Chat routes
        self.router.add_api_route(
            "/chats", 
            self.create_chat, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/chats", 
            self.get_chats, 
            methods=["GET"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}", 
            self.get_chat, 
            methods=["GET"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}", 
            self.update_chat, 
            methods=["PUT"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}", 
            self.delete_chat, 
            methods=["DELETE"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}/members/{member_id}", 
            self.add_chat_member, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}/members/{member_id}", 
            self.remove_chat_member, 
            methods=["DELETE"]
        )
        
        # Message routes
        self.router.add_api_route(
            "/messages", 
            self.send_message, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}/messages", 
            self.get_messages, 
            methods=["GET"]
        )
        
        self.router.add_api_route(
            "/messages/{message_id}", 
            self.update_message, 
            methods=["PUT"]
        )
        
        self.router.add_api_route(
            "/messages/{message_id}", 
            self.delete_message, 
            methods=["DELETE"]
        )
        
        self.router.add_api_route(
            "/messages/{message_id}/read", 
            self.mark_message_read, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}/read", 
            self.mark_chat_read, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/messages/{message_id}/reactions/{reaction_type}", 
            self.add_reaction, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/messages/{message_id}/reactions/{reaction_type}", 
            self.remove_reaction, 
            methods=["DELETE"]
        )
        
        self.router.add_api_route(
            "/messages/{message_id}/pin", 
            self.pin_message, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/messages/{message_id}/unpin", 
            self.unpin_message, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/chats/{chat_id}/pinned", 
            self.get_pinned_messages, 
            methods=["GET"]
        )
        
        # File routes
        self.router.add_api_route(
            "/uploads", 
            self.upload_file, 
            methods=["POST"]
        )
        
        self.router.add_api_route(
            "/messages/file", 
            self.send_file_message, 
            methods=["POST"]
        )
        
        # Typing indicator route
        self.router.add_api_route(
            "/chats/{chat_id}/typing", 
            self.send_typing_indicator, 
            methods=["POST"]
        )
        
        # Search route
        self.router.add_api_route(
            "/search", 
            self.search_messages, 
            methods=["GET"]
        )
        
        # Analytics routes
        self.router.add_api_route(
            "/stats/chat/{chat_id}", 
            self.get_chat_stats, 
            methods=["GET"]
        )
        
        self.router.add_api_route(
            "/stats/user", 
            self.get_user_stats, 
            methods=["GET"]
        )
    
    def register_to_app(self, app: FastAPI, prefix: str = "/api"):
        """Register the router to a FastAPI app.
        
        Args:
            app: The FastAPI app
            prefix: The API prefix
        """
        app.include_router(self.router, prefix=prefix)
    
    async def get_current_user(self, token: str = Depends(lambda x: x.oauth2_scheme)) -> str:
        """Get the current user from the token.
        
        Args:
            token: JWT token
            
        Returns:
            str: User ID
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            return await self.chat_system.security_manager.get_user_id_from_token(token)
        except AuthenticationError as e:
            raise HTTPException(status_code=401, detail=str(e))
    
    # Authentication endpoints
    
    async def register_user(self, user_data: UserCreate):
        """Register a new user.
        
        Args:
            user_data: User creation data
            
        Returns:
            User: The created user
        """
        user = await self.chat_system.register_user(user_data)
        return user
    
    async def login(self, form_data: OAuth2PasswordRequestForm = Depends()):
        """Login and get access token.
        
        Args:
            form_data: OAuth2 form data
            
        Returns:
            Dict: Access token and token type
            
        Raises:
            HTTPException: If login fails
        """
        token = await self.chat_system.authenticate_user(form_data.username, form_data.password)
        
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"access_token": token, "token_type": "bearer"}
    
    # User endpoints
    
    async def get_current_user_info(self, user_id: str = Depends(get_current_user)):
        """Get current user information.
        
        Args:
            user_id: User ID
            
        Returns:
            User: User information
            
        Raises:
            HTTPException: If user not found
        """
        user = await self.chat_system.get_user(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user
    
    async def update_current_user(
        self,
        user_data: UserUpdate,
        user_id: str = Depends(get_current_user)
    ):
        """Update current user information.
        
        Args:
            user_data: User update data
            user_id: User ID
            
        Returns:
            User: Updated user information
            
        Raises:
            HTTPException: If user not found
        """
        user = await self.chat_system.update_user(user_id, user_data)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user
    
    async def update_status(
        self,
        status: str,
        user_id: str = Depends(get_current_user)
    ):
        """Update user status.
        
        Args:
            status: New status
            user_id: User ID
            
        Returns:
            Dict: Status update result
            
        Raises:
            HTTPException: If user not found
        """
        user = await self.chat_system.update_user_status(user_id, status)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"status": user.status}
    
    # Chat endpoints
    
    async def create_chat(
        self,
        chat_data: ChatCreate,
        user_id: str = Depends(get_current_user)
    ):
        """Create a new chat.
        
        Args:
            chat_data: Chat creation data
            user_id: User ID
            
        Returns:
            Chat: The created chat
        """
        chat = await self.chat_system.create_chat(chat_data, user_id)
        return chat
    
    async def get_chats(self, user_id: str = Depends(get_current_user)):
        """Get all chats for the current user.
        
        Args:
            user_id: User ID
            
        Returns:
            List[Chat]: List of chats
        """
        chats = await self.chat_system.get_user_chats(user_id)
        return chats
    
    async def get_chat(
        self,
        chat_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Get a chat by ID.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            
        Returns:
            Chat: Chat information
            
        Raises:
            HTTPException: If chat not found
        """
        chat = await self.chat_system.get_chat(chat_id, user_id)
        
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return chat
    
    async def update_chat(
        self,
        chat_id: str,
        chat_data: ChatUpdate,
        user_id: str = Depends(get_current_user)
    ):
        """Update a chat.
        
        Args:
            chat_id: Chat ID
            chat_data: Chat update data
            user_id: User ID
            
        Returns:
            Chat: Updated chat information
            
        Raises:
            HTTPException: If chat not found
        """
        chat = await self.chat_system.update_chat(chat_id, user_id, chat_data)
        
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return chat
    
    async def delete_chat(
        self,
        chat_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Delete a chat.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            
        Returns:
            Dict: Success indicator
            
        Raises:
            HTTPException: If chat not found
        """
        result = await self.chat_system.delete_chat(chat_id, user_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return {"success": True}
    
    async def add_chat_member(
        self,
        chat_id: str,
        member_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Add a member to a chat.
        
        Args:
            chat_id: Chat ID
            member_id: Member ID
            user_id: User ID
            
        Returns:
            Dict: Success indicator
        """
        result = await self.chat_system.add_chat_member(chat_id, user_id, member_id)
        return {"success": result}
    
    async def remove_chat_member(
        self,
        chat_id: str,
        member_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Remove a member from a chat.
        
        Args:
            chat_id: Chat ID
            member_id: Member ID
            user_id: User ID
            
        Returns:
            Dict: Success indicator
        """
        result = await self.chat_system.remove_chat_member(chat_id, user_id, member_id)
        return {"success": result}
    
    # Message endpoints
    
    async def send_message(
        self,
        message_data: MessageCreate,
        user_id: str = Depends(get_current_user)
    ):
        """Send a message.
        
        Args:
            message_data: Message creation data
            user_id: User ID
            
        Returns:
            Message: The created message
        """
        message = await self.chat_system.send_message(user_id, message_data)
        return message
    
    async def get_messages(
        self,
        chat_id: str,
        before_id: Optional[str] = None,
        after_id: Optional[str] = None,
        limit: int = 50,
        user_id: str = Depends(get_current_user)
    ):
        """Get messages for a chat.
        
        Args:
            chat_id: Chat ID
            before_id: Get messages before this ID
            after_id: Get messages after this ID
            limit: Maximum number of messages to return
            user_id: User ID
            
        Returns:
            List[Message]: List of messages
        """
        messages = await self.chat_system.get_chat_messages(
            chat_id=chat_id,
            user_id=user_id,
            before_id=before_id,
            after_id=after_id,
            limit=limit
        )
        
        return messages
    
    async def update_message(
        self,
        message_id: str,
        message_data: MessageUpdate,
        user_id: str = Depends(get_current_user)
    ):
        """Update a message.
        
        Args:
            message_id: Message ID
            message_data: Message update data
            user_id: User ID
            
        Returns:
            Message: Updated message
            
        Raises:
            HTTPException: If message not found
        """
        message = await self.chat_system.update_message(message_id, user_id, message_data)
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return message
    
    async def delete_message(
        self,
        message_id: str,
        delete_for_everyone: bool = False,
        user_id: str = Depends(get_current_user)
    ):
        """Delete a message.
        
        Args:
            message_id: Message ID
            delete_for_everyone: Whether to delete for everyone
            user_id: User ID
            
        Returns:
            Dict: Success indicator
        """
        result = await self.chat_system.delete_message(message_id, user_id, delete_for_everyone)
        return {"success": result}
    
    async def mark_message_read(
        self,
        message_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Mark a message as read.
        
        Args:
            message_id: Message ID
            user_id: User ID
            
        Returns:
            Dict: Success indicator
            
        Raises:
            HTTPException: If message not found
        """
        # Get message to find chat_id
        message = await self.chat_system.get_message(message_id, user_id)
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        result = await self.chat_system.mark_messages_read(
            chat_id=message.chat_id,
            user_id=user_id,
            message_ids=[message_id]
        )
        
        return {"success": result}
    
    async def mark_chat_read(
        self,
        chat_id: str,
        read_until_id: Optional[str] = None,
        user_id: str = Depends(get_current_user)
    ):
        """Mark all messages in a chat as read.
        
        Args:
            chat_id: Chat ID
            read_until_id: Read until this message ID
            user_id: User ID
            
        Returns:
            Dict: Success indicator
        """
        result = await self.chat_system.mark_messages_read(
            chat_id=chat_id,
            user_id=user_id,
            read_until_id=read_until_id
        )
        
        return {"success": result}
    
    async def add_reaction(
        self,
        message_id: str,
        reaction_type: str,
        user_id: str = Depends(get_current_user)
    ):
        """Add a reaction to a message.
        
        Args:
            message_id: Message ID
            reaction_type: Reaction type
            user_id: User ID
            
        Returns:
            Dict: Success indicator
        """
        result = await self.chat_system.add_reaction(message_id, user_id, reaction_type)
        return {"success": bool(result)}
    
    async def remove_reaction(
        self,
        message_id: str,
        reaction_type: str,
        user_id: str = Depends(get_current_user)
    ):
        """Remove a reaction from a message.
        
        Args:
            message_id: Message ID
            reaction_type: Reaction type
            user_id: User ID
            
        Returns:
            Dict: Success indicator
        """
        result = await self.chat_system.remove_reaction(message_id, user_id, reaction_type)
        return {"success": result}
    
    async def pin_message(
        self,
        message_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Pin a message.
        
        Args:
            message_id: Message ID
            user_id: User ID
            
        Returns:
            Message: The pinned message
            
        Raises:
            HTTPException: If message not found
        """
        message = await self.chat_system.pin_message(message_id, user_id)
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return message
    
    async def unpin_message(
        self,
        message_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Unpin a message.
        
        Args:
            message_id: Message ID
            user_id: User ID
            
        Returns:
            Message: The unpinned message
            
        Raises:
            HTTPException: If message not found
        """
        message = await self.chat_system.unpin_message(message_id, user_id)
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return message
    
    async def get_pinned_messages(
        self,
        chat_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Get all pinned messages in a chat.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            
        Returns:
            List[Message]: List of pinned messages
        """
        messages = await self.chat_system.get_pinned_messages(chat_id, user_id)
        return messages
    
    # File endpoints
    
    async def upload_file(
        self,
        chat_id: str,
        file: UploadFile = File(...),
        user_id: str = Depends(get_current_user)
    ):
        """Upload a file.
        
        Args:
            chat_id: Chat ID
            file: Uploaded file
            user_id: User ID
            
        Returns:
            Dict: File URL
        """
        file_content = await file.read()
        file_url = await self.chat_system.upload_file(
            chat_id=chat_id,
            user_id=user_id,
            file_data=file_content,
            file_name=file.filename,
            content_type=file.content_type
        )
        
        return {"file_url": file_url}
    
    async def send_file_message(
        self,
        chat_id: str,
        file_url: str,
        file_name: str,
        content_type: str,
        caption: Optional[str] = None,
        user_id: str = Depends(get_current_user)
    ):
        """Send a file message.
        
        Args:
            chat_id: Chat ID
            file_url: File URL
            file_name: File name
            content_type: Content type
            caption: Caption
            user_id: User ID
            
        Returns:
            Message: The created message
        """
        message = await self.chat_system.send_file_message(
            sender_id=user_id,
            chat_id=chat_id,
            file_url=file_url,
            file_name=file_name,
            content_type=content_type,
            caption=caption
        )
        
        return message
    
    # Typing indicator endpoint
    
    async def send_typing_indicator(
        self,
        chat_id: str,
        is_typing: bool = True,
        user_id: str = Depends(get_current_user)
    ):
        """Send a typing indicator.
        
        Args:
            chat_id: Chat ID
            is_typing: Whether the user is typing
            user_id: User ID
            
        Returns:
            Dict: Success indicator
        """
        result = await self.chat_system.send_typing_indicator(chat_id, user_id, is_typing)
        return {"success": result}
    
    # Search endpoint
    
    async def search_messages(
        self,
        query: str,
        chat_id: Optional[str] = None,
        limit: int = 20,
        user_id: str = Depends(get_current_user)
    ):
        """Search for messages.
        
        Args:
            query: Search query
            chat_id: Chat ID (optional)
            limit: Maximum number of results
            user_id: User ID
            
        Returns:
            List[Message]: List of matching messages
        """
        messages = await self.chat_system.search_messages(user_id, query, chat_id, limit)
        return messages
    
    # Analytics endpoints
    
    async def get_chat_stats(
        self,
        chat_id: str,
        user_id: str = Depends(get_current_user)
    ):
        """Get statistics for a chat.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            
        Returns:
            Dict: Chat statistics
        """
        stats = await self.chat_system.get_chat_stats(chat_id, user_id)
        return stats
    
    async def get_user_stats(
        self,
        user_id: str = Depends(get_current_user)
    ):
        """Get statistics for the current user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict: User statistics
        """
        stats = await self.chat_system.get_user_stats(user_id)
        return stats