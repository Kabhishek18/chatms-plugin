# chatms_plugin/api/django.py

"""
Django integration for the ChatMS plugin.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

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


class DjangoAPI:
    """Django API implementation for the ChatMS plugin."""
    
    def __init__(self, chat_system: ChatSystem):
        """Initialize the Django API.
        
        Args:
            chat_system: The chat system instance
        """
        self.chat_system = chat_system
    
    def get_urls(self, prefix: str = 'chatms/'):
        """Get URL patterns for Django.
        
        Args:
            prefix: URL prefix for all endpoints
            
        Returns:
            List: List of URL patterns
        """
        urlpatterns = [
            # Authentication routes
            path(f'{prefix}register/', self.register_view),
            path(f'{prefix}token/', self.token_view),
            
            # User routes
            path(f'{prefix}users/me/', self.user_me_view),
            path(f'{prefix}users/me/status/', self.user_status_view),
            
            # Chat routes
            path(f'{prefix}chats/', self.chats_view),
            path(f'{prefix}chats/<str:chat_id>/', self.chat_detail_view),
            path(f'{prefix}chats/<str:chat_id>/members/<str:member_id>/', self.chat_member_view),
            
            # Message routes
            path(f'{prefix}messages/', self.messages_view),
            path(f'{prefix}chats/<str:chat_id>/messages/', self.chat_messages_view),
            path(f'{prefix}messages/<str:message_id>/', self.message_detail_view),
            path(f'{prefix}messages/<str:message_id>/read/', self.message_read_view),
            path(f'{prefix}chats/<str:chat_id>/read/', self.chat_read_view),
            
            # Reaction routes
            path(f'{prefix}messages/<str:message_id>/reactions/<str:reaction_type>/', self.message_reaction_view),
            
            # Pin routes
            path(f'{prefix}messages/<str:message_id>/pin/', self.message_pin_view),
            path(f'{prefix}messages/<str:message_id>/unpin/', self.message_unpin_view),
            path(f'{prefix}chats/<str:chat_id>/pinned/', self.chat_pinned_view),
            
            # File routes
            path(f'{prefix}uploads/', self.upload_view),
            path(f'{prefix}messages/file/', self.file_message_view),
            
            # Typing indicator route
            path(f'{prefix}chats/<str:chat_id>/typing/', self.typing_view),
            
            # Search route
            path(f'{prefix}search/', self.search_view),
            
            # Analytics routes
            path(f'{prefix}stats/chat/<str:chat_id>/', self.chat_stats_view),
            path(f'{prefix}stats/user/', self.user_stats_view),
        ]
        
        return urlpatterns
    
    async def get_current_user(self, request: HttpRequest) -> str:
        """Get the current user from the request.
        
        Args:
            request: The HTTP request
            
        Returns:
            str: User ID
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            raise AuthenticationError("Missing authorization header")
        
        # Extract token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise AuthenticationError("Invalid authorization header format")
        
        token = parts[1]
        
        # Verify token
        return await self.chat_system.security_manager.get_user_id_from_token(token)
    
    def _get_request_data(self, request: HttpRequest) -> Dict[str, Any]:
        """Get data from a request.
        
        Args:
            request: The HTTP request
            
        Returns:
            Dict[str, Any]: Request data
        """
        if request.method in ['POST', 'PUT']:
            try:
                return json.loads(request.body)
            except json.JSONDecodeError:
                return request.POST.dict()
        else:
            return request.GET.dict()
    
    def _handle_error(self, e: Exception) -> JsonResponse:
        """Handle an exception and return an appropriate response.
        
        Args:
            e: The exception
            
        Returns:
            JsonResponse: Error response
        """
        status_code = 500
        
        if isinstance(e, AuthenticationError):
            status_code = 401
        elif isinstance(e, AuthorizationError):
            status_code = 403
        elif isinstance(e, ValidationError):
            status_code = 400
        elif isinstance(e, (UserError, ChatError, MessageError)):
            status_code = 404
        
        return JsonResponse({"error": str(e)}, status=status_code)
    
    # Authentication views
    
    @csrf_exempt
    async def register_view(self, request: HttpRequest) -> JsonResponse:
        """View for user registration.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            data = self._get_request_data(request)
            user_data = UserCreate(**data)
            
            # Register user
            user = await self.chat_system.register_user(user_data)
            
            return JsonResponse({
                "id": user.id,
                "username": user.username,
                "email": user.email
            }, status=201)
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def token_view(self, request: HttpRequest) -> JsonResponse:
        """View for token generation.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response with token
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            data = self._get_request_data(request)
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return JsonResponse({"error": "Username and password are required"}, status=400)
            
            # Authenticate user
            token = await self.chat_system.authenticate_user(username, password)
            
            return JsonResponse({
                "access_token": token,
                "token_type": "bearer"
            })
            
        except Exception as e:
            return self._handle_error(e)
    
    # User views
    
    @csrf_exempt
    async def user_me_view(self, request: HttpRequest) -> JsonResponse:
        """View for current user information.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response with user information
        """
        try:
            user_id = await self.get_current_user(request)
            
            if request.method == 'GET':
                # Get user information
                user = await self.chat_system.get_user(user_id)
                
                if not user:
                    return JsonResponse({"error": "User not found"}, status=404)
                
                return JsonResponse(user.dict(exclude={"hashed_password"}))
                
            elif request.method == 'PUT':
                # Update user information
                data = self._get_request_data(request)
                user_data = UserUpdate(**data)
                
                updated_user = await self.chat_system.update_user(user_id, user_data)
                
                if not updated_user:
                    return JsonResponse({"error": "User not found"}, status=404)
                
                return JsonResponse(updated_user.dict(exclude={"hashed_password"}))
                
            else:
                return JsonResponse({"error": "Method not allowed"}, status=405)
                
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def user_status_view(self, request: HttpRequest) -> JsonResponse:
        """View for user status updates.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response with status
        """
        if request.method != 'PUT':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            data = self._get_request_data(request)
            status = data.get('status')
            
            if not status:
                return JsonResponse({"error": "Status is required"}, status=400)
            
            # Update user status
            user = await self.chat_system.update_user_status(user_id, status)
            
            if not user:
                return JsonResponse({"error": "User not found"}, status=404)
            
            return JsonResponse({"status": user.status})
            
        except Exception as e:
            return self._handle_error(e)
    
    # Chat views
    
    @csrf_exempt
    async def chats_view(self, request: HttpRequest) -> JsonResponse:
        """View for listing and creating chats.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response
        """
        try:
            user_id = await self.get_current_user(request)
            
            if request.method == 'GET':
                # List user's chats
                chats = await self.chat_system.get_user_chats(user_id)
                return JsonResponse([chat.dict() for chat in chats], safe=False)
                
            elif request.method == 'POST':
                # Create a new chat
                data = self._get_request_data(request)
                chat_data = ChatCreate(**data)
                
                chat = await self.chat_system.create_chat(chat_data, user_id)
                return JsonResponse(chat.dict(), status=201)
                
            else:
                return JsonResponse({"error": "Method not allowed"}, status=405)
                
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def chat_detail_view(self, request: HttpRequest, chat_id: str) -> JsonResponse:
        """View for chat details, updates, and deletion.
        
        Args:
            request: The HTTP request
            chat_id: The chat ID
            
        Returns:
            JsonResponse: Response
        """
        try:
            user_id = await self.get_current_user(request)
            
            if request.method == 'GET':
                # Get chat details
                chat = await self.chat_system.get_chat(chat_id, user_id)
                
                if not chat:
                    return JsonResponse({"error": "Chat not found"}, status=404)
                
                return JsonResponse(chat.dict())
                
            elif request.method == 'PUT':
                # Update chat
                data = self._get_request_data(request)
                chat_data = ChatUpdate(**data)
                
                updated_chat = await self.chat_system.update_chat(chat_id, user_id, chat_data)
                
                if not updated_chat:
                    return JsonResponse({"error": "Chat not found"}, status=404)
                
                return JsonResponse(updated_chat.dict())
                
            elif request.method == 'DELETE':
                # Delete chat
                result = await self.chat_system.delete_chat(chat_id, user_id)
                
                if not result:
                    return JsonResponse({"error": "Chat not found"}, status=404)
                
                return JsonResponse({"success": True})
                
            else:
                return JsonResponse({"error": "Method not allowed"}, status=405)
                
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def chat_member_view(self, request: HttpRequest, chat_id: str, member_id: str) -> JsonResponse:
        """View for managing chat members.
        
        Args:
            request: The HTTP request
            chat_id: The chat ID
            member_id: The member ID
            
        Returns:
            JsonResponse: Response
        """
        try:
            user_id = await self.get_current_user(request)
            
            if request.method == 'POST':
                # Add member to chat
                result = await self.chat_system.add_chat_member(chat_id, user_id, member_id)
                return JsonResponse({"success": result})
                
            elif request.method == 'DELETE':
                # Remove member from chat
                result = await self.chat_system.remove_chat_member(chat_id, user_id, member_id)
                return JsonResponse({"success": result})
                
            else:
                return JsonResponse({"error": "Method not allowed"}, status=405)
                
        except Exception as e:
            return self._handle_error(e)
    
    # Message views
    
    @csrf_exempt
    async def messages_view(self, request: HttpRequest) -> JsonResponse:
        """View for sending messages.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            data = self._get_request_data(request)
            message_data = MessageCreate(**data)
            
            # Send message
            message = await self.chat_system.send_message(user_id, message_data)
            return JsonResponse(message.dict(), status=201)
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def chat_messages_view(self, request: HttpRequest, chat_id: str) -> JsonResponse:
        """View for listing chat messages.
        
        Args:
            request: The HTTP request
            chat_id: The chat ID
            
        Returns:
            JsonResponse: Response with messages
        """
        if request.method != 'GET':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            data = self._get_request_data(request)
            
            before_id = data.get('before_id')
            after_id = data.get('after_id')
            limit = int(data.get('limit', 50))
            
            # Get chat messages
            messages = await self.chat_system.get_chat_messages(
                chat_id=chat_id,
                user_id=user_id,
                before_id=before_id,
                after_id=after_id,
                limit=limit
            )
            
            return JsonResponse([message.dict() for message in messages], safe=False)
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def message_detail_view(self, request: HttpRequest, message_id: str) -> JsonResponse:
        """View for message updates and deletion.
        
        Args:
            request: The HTTP request
            message_id: The message ID
            
        Returns:
            JsonResponse: Response
        """
        try:
            user_id = await self.get_current_user(request)
            
            if request.method == 'PUT':
                # Update message
                data = self._get_request_data(request)
                message_data = MessageUpdate(**data)
                
                updated_message = await self.chat_system.update_message(message_id, user_id, message_data)
                
                if not updated_message:
                    return JsonResponse({"error": "Message not found"}, status=404)
                
                return JsonResponse(updated_message.dict())
                
            elif request.method == 'DELETE':
                # Delete message
                data = self._get_request_data(request)
                delete_for_everyone = data.get('delete_for_everyone', False)
                
                result = await self.chat_system.delete_message(message_id, user_id, delete_for_everyone)
                return JsonResponse({"success": result})
                
            else:
                return JsonResponse({"error": "Method not allowed"}, status=405)
                
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def message_read_view(self, request: HttpRequest, message_id: str) -> JsonResponse:
        """View for marking a message as read.
        
        Args:
            request: The HTTP request
            message_id: The message ID
            
        Returns:
            JsonResponse: Response
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            
            # Get message to find chat_id
            message = await self.chat_system.get_message(message_id, user_id)
            
            if not message:
                return JsonResponse({"error": "Message not found"}, status=404)
            
            result = await self.chat_system.mark_messages_read(
                chat_id=message.chat_id,
                user_id=user_id,
                message_ids=[message_id]
            )
            
            return JsonResponse({"success": result})
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def chat_read_view(self, request: HttpRequest, chat_id: str) -> JsonResponse:
        """View for marking all chat messages as read.
        
        Args:
            request: The HTTP request
            chat_id: The chat ID
            
        Returns:
            JsonResponse: Response
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            data = self._get_request_data(request)
            read_until_id = data.get('read_until_id')
            
            result = await self.chat_system.mark_messages_read(
                chat_id=chat_id,
                user_id=user_id,
                read_until_id=read_until_id
            )
            
            return JsonResponse({"success": result})
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def message_reaction_view(self, request: HttpRequest, message_id: str, reaction_type: str) -> JsonResponse:
        """View for message reactions.
        
        Args:
            request: The HTTP request
            message_id: The message ID
            reaction_type: The reaction type
            
        Returns:
            JsonResponse: Response
        """
        try:
            user_id = await self.get_current_user(request)
            
            if request.method == 'POST':
                # Add reaction
                result = await self.chat_system.add_reaction(message_id, user_id, reaction_type)
                return JsonResponse({"success": bool(result)})
                
            elif request.method == 'DELETE':
                # Remove reaction
                result = await self.chat_system.remove_reaction(message_id, user_id, reaction_type)
                return JsonResponse({"success": result})
                
            else:
                return JsonResponse({"error": "Method not allowed"}, status=405)
                
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def message_pin_view(self, request: HttpRequest, message_id: str) -> JsonResponse:
        """View for pinning a message.
        
        Args:
            request: The HTTP request
            message_id: The message ID
            
        Returns:
            JsonResponse: Response
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            
            message = await self.chat_system.pin_message(message_id, user_id)
            
            if not message:
                return JsonResponse({"error": "Message not found"}, status=404)
            
            return JsonResponse(message.dict())
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def message_unpin_view(self, request: HttpRequest, message_id: str) -> JsonResponse:
        """View for unpinning a message.
        
        Args:
            request: The HTTP request
            message_id: The message ID
            
        Returns:
            JsonResponse: Response
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            
            message = await self.chat_system.unpin_message(message_id, user_id)
            
            if not message:
                return JsonResponse({"error": "Message not found"}, status=404)
            
            return JsonResponse(message.dict())
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def chat_pinned_view(self, request: HttpRequest, chat_id: str) -> JsonResponse:
        """View for getting pinned messages in a chat.
        
        Args:
            request: The HTTP request
            chat_id: The chat ID
            
        Returns:
            JsonResponse: Response with pinned messages
        """
        if request.method != 'GET':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            
            messages = await self.chat_system.get_pinned_messages(chat_id, user_id)
            return JsonResponse([message.dict() for message in messages], safe=False)
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def upload_view(self, request: HttpRequest) -> JsonResponse:
        """View for file uploads.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response with file URL
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            
            # Get uploaded file from request
            if not request.FILES:
                return JsonResponse({"error": "No file uploaded"}, status=400)
            
            chat_id = request.POST.get('chat_id')
            if not chat_id:
                return JsonResponse({"error": "Chat ID is required"}, status=400)
            
            uploaded_file = request.FILES['file']
            file_content = uploaded_file.read()
            
            # Upload file
            file_url = await self.chat_system.upload_file(
                chat_id=chat_id,
                user_id=user_id,
                file_data=file_content,
                file_name=uploaded_file.name,
                content_type=uploaded_file.content_type
            )
            
            return JsonResponse({"file_url": file_url})
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def file_message_view(self, request: HttpRequest) -> JsonResponse:
        """View for sending file messages.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response with created message
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            data = self._get_request_data(request)
            
            # Extract required fields
            chat_id = data.get('chat_id')
            file_url = data.get('file_url')
            file_name = data.get('file_name')
            content_type = data.get('content_type')
            caption = data.get('caption')
            
            if not all([chat_id, file_url, file_name, content_type]):
                return JsonResponse({"error": "Missing required fields"}, status=400)
            
            # Send file message
            message = await self.chat_system.send_file_message(
                sender_id=user_id,
                chat_id=chat_id,
                file_url=file_url,
                file_name=file_name,
                content_type=content_type,
                caption=caption
            )
            
            return JsonResponse(message.dict(), status=201)
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def typing_view(self, request: HttpRequest, chat_id: str) -> JsonResponse:
        """View for typing indicators.
        
        Args:
            request: The HTTP request
            chat_id: The chat ID
            
        Returns:
            JsonResponse: Response
        """
        if request.method != 'POST':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            data = self._get_request_data(request)
            is_typing = data.get('is_typing', True)
            
            result = await self.chat_system.send_typing_indicator(chat_id, user_id, is_typing)
            return JsonResponse({"success": result})
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def search_view(self, request: HttpRequest) -> JsonResponse:
        """View for searching messages.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response with search results
        """
        if request.method != 'GET':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            data = self._get_request_data(request)
            
            query = data.get('query')
            chat_id = data.get('chat_id')
            limit = int(data.get('limit', 20))
            
            if not query:
                return JsonResponse({"error": "Query is required"}, status=400)
            
            # Search messages
            messages = await self.chat_system.search_messages(user_id, query, chat_id, limit)
            return JsonResponse([message.dict() for message in messages], safe=False)
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def chat_stats_view(self, request: HttpRequest, chat_id: str) -> JsonResponse:
        """View for chat statistics.
        
        Args:
            request: The HTTP request
            chat_id: The chat ID
            
        Returns:
            JsonResponse: Response with chat statistics
        """
        if request.method != 'GET':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            
            stats = await self.chat_system.get_chat_stats(chat_id, user_id)
            return JsonResponse(stats)
            
        except Exception as e:
            return self._handle_error(e)
    
    @csrf_exempt
    async def user_stats_view(self, request: HttpRequest) -> JsonResponse:
        """View for user statistics.
        
        Args:
            request: The HTTP request
            
        Returns:
            JsonResponse: Response with user statistics
        """
        if request.method != 'GET':
            return JsonResponse({"error": "Method not allowed"}, status=405)
        
        try:
            user_id = await self.get_current_user(request)
            
            stats = await self.chat_system.get_user_stats(user_id)
            return JsonResponse(stats)
            
        except Exception as e:
            return self._handle_error(e)


# Django WebSocket implementation using Channels
class DjangoChannelsAPI:
    """Django Channels API implementation for the ChatMS plugin."""
    
    def __init__(self, chat_system: ChatSystem):
        """Initialize the Django Channels API.
        
        Args:
            chat_system: The chat system instance
        """
        self.chat_system = chat_system
    
    def get_consumer(self):
        """Get a Django Channels consumer class.
        
        Returns:
            type: Consumer class
        """
        from channels.generic.websocket import AsyncJsonWebsocketConsumer
        from channels.db import database_sync_to_async
        
        chat_system = self.chat_system
        
        class ChatConsumer(AsyncJsonWebsocketConsumer):
            """WebSocket consumer for chat messages."""
            
            async def connect(self):
                """Handle WebSocket connection."""
                # Get user_id from URL
                self.user_id = self.scope['url_route']['kwargs']['user_id']
                
                # Verify token
                token = self.scope.get('query_string', b'').decode('utf-8')
                if not token:
                    # Try to get token from headers
                    headers = dict(self.scope.get('headers', []))
                    authorization = headers.get(b'authorization', b'')
                    if authorization.startswith(b'Bearer '):
                        token = authorization[7:].decode('utf-8')
                
                if not token:
                    await self.close(code=1008)
                    return
                    
                # Verify token
                try:
                    authenticated_user_id = await chat_system.security_manager.get_user_id_from_token(token)
                    
                    if authenticated_user_id != self.user_id:
                        await self.close(code=1008)
                        return
                    
                    # Accept connection
                    await self.accept()
                    
                    # Connect to connection manager
                    await chat_system.connection_manager.connect(self, self.user_id)
                    
                except Exception as e:
                    logger.error(f"WebSocket authentication error: {e}")
                    await self.close(code=1008)
            
            async def disconnect(self, close_code):
                """Handle WebSocket disconnection."""
                await chat_system.connection_manager.disconnect(self, self.user_id)
            
            async def receive_json(self, content):
                """Handle incoming WebSocket messages."""
                try:
                    # Handle different message types
                    message_type = content.get('type')
                    
                    if message_type == 'join_chat':
                        await self._handle_join_chat(content)
                    
                    elif message_type == 'leave_chat':
                        await self._handle_leave_chat(content)
                    
                    elif message_type == 'send_message':
                        await self._handle_send_message(content)
                    
                    elif message_type == 'typing':
                        await self._handle_typing(content)
                    
                    elif message_type == 'read':
                        await self._handle_read(content)
                    
                    elif message_type == 'ping':
                        await self._handle_ping(content)
                    
                    else:
                        await self.send_json({
                            'type': 'error',
                            'message': f'Unknown message type: {message_type}'
                        })
                
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    await self.send_json({
                        'type': 'error',
                        'message': str(e)
                    })
            
            async def _handle_join_chat(self, content):
                """Handle chat room join."""
                chat_id = content.get('chat_id')
                if not chat_id:
                    await self.send_json({
                        'type': 'error',
                        'message': 'Missing chat_id'
                    })
                    return
                
                try:
                    # Check if user is member of the chat
                    chat = await chat_system.get_chat(chat_id, self.user_id)
                    
                    if chat:
                        await chat_system.connection_manager.join_chat(self, chat_id)
                        
                        # Send success response
                        await self.send_json({
                            'type': 'chat_joined',
                            'chat_id': chat_id
                        })
                    else:
                        await self.send_json({
                            'type': 'error',
                            'message': 'Chat not found or you are not a member'
                        })
                except Exception as e:
                    logger.error(f"Error joining chat: {e}")
                    await self.send_json({
                        'type': 'error',
                        'message': f'Error joining chat: {str(e)}'
                    })
            
            async def _handle_leave_chat(self, content):
                """Handle chat room leave."""
                chat_id = content.get('chat_id')
                if not chat_id:
                    await self.send_json({
                        'type': 'error',
                        'message': 'Missing chat_id'
                    })
                    return
                
                try:
                    await chat_system.connection_manager.leave_chat(self, chat_id)
                    
                    # Send success response
                    await self.send_json({
                        'type': 'chat_left',
                        'chat_id': chat_id
                    })
                except Exception as e:
                    logger.error(f"Error leaving chat: {e}")
                    await self.send_json({
                        'type': 'error',
                        'message': f'Error leaving chat: {str(e)}'
                    })
            
            async def _handle_send_message(self, content):
                """Handle sending messages."""
                chat_id = content.get('chat_id')
                message_content = content.get('content')
                message_type = content.get('message_type', 'text')
                reply_to_id = content.get('reply_to_id')
                mentions = content.get('mentions', [])
                
                if not chat_id or not message_content:
                    await self.send_json({
                        'type': 'error',
                        'message': 'Missing chat_id or content'
                    })
                    return
                
                try:
                    from ..models.message import MessageCreate
                    
                    message_data = MessageCreate(
                        chat_id=chat_id,
                        content=message_content,
                        message_type=message_type,
                        reply_to_id=reply_to_id,
                        mentions=mentions
                    )
                    
                    message = await chat_system.send_message(self.user_id, message_data)
                    
                    # Send success response with created message
                    await self.send_json({
                        'type': 'message_sent',
                        'message': message.dict()
                    })
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    await self.send_json({
                        'type': 'error',
                        'message': f'Error sending message: {str(e)}'
                    })
            
            async def _handle_typing(self, content):
                """Handle typing indicators."""
                chat_id = content.get('chat_id')
                is_typing = content.get('is_typing', True)
                
                if not chat_id:
                    await self.send_json({
                        'type': 'error',
                        'message': 'Missing chat_id'
                    })
                    return
                
                try:
                    await chat_system.send_typing_indicator(chat_id, self.user_id, is_typing)
                    # No response needed, typing indicators are broadcast to other users
                except Exception as e:
                    logger.error(f"Error sending typing indicator: {e}")
                    await self.send_json({
                        'type': 'error',
                        'message': f'Error sending typing indicator: {str(e)}'
                    })
            
            async def _handle_read(self, content):
                """Handle read receipts."""
                chat_id = content.get('chat_id')
                message_ids = content.get('message_ids', [])
                read_until_id = content.get('read_until_id')
                
                if not chat_id:
                    await self.send_json({
                        'type': 'error',
                        'message': 'Missing chat_id'
                    })
                    return
                
                try:
                    result = await chat_system.mark_messages_read(
                        chat_id=chat_id,
                        user_id=self.user_id,
                        message_ids=message_ids,
                        read_until_id=read_until_id
                    )
                    
                    # Send success response
                    await self.send_json({
                        'type': 'messages_read_success',
                        'chat_id': chat_id
                    })
                except Exception as e:
                    logger.error(f"Error marking messages as read: {e}")
                    await self.send_json({
                        'type': 'error',
                        'message': f'Error marking messages as read: {str(e)}'
                    })
            
            async def _handle_ping(self, content):
                """Handle ping messages."""
                timestamp = content.get('timestamp')
                
                # Respond with pong
                await self.send_json({
                    'type': 'pong',
                    'timestamp': timestamp
                })
            
            # Methods for compatibility with connection manager
            async def send_text(self, text):
                """Send a text message (compatibility method)."""
                await self.send(text_data=text)
            
            async def send_json(self, data):
                """Send a JSON message."""
                await super().send_json(data)
        
        return ChatConsumer


# Helper function to integrate with Django
def setup_django_integration(chat_system):
    """Set up Django integration.
    
    Args:
        chat_system: The ChatMS chat system instance
        
    Returns:
        tuple: (DjangoAPI, DjangoChannelsAPI) for URL routing
    """
    # Create API instances
    rest_api = DjangoAPI(chat_system)
    channels_api = DjangoChannelsAPI(chat_system)
    
    return rest_api, channels_api


# Example of Django integration usage
"""
# In your Django urls.py:
from django.urls import path, include
from chatms_plugin import ChatSystem, Config
from chatms_plugin.api.django import setup_django_integration

# Create chat system
config = Config(
    database_url="postgresql://user:password@localhost/chatdb",
    storage_type="local",
    storage_path="./file_storage"
)
chat_system = ChatSystem(config)

# Initialize chat system in Django's AppConfig.ready() method
# For example:
# async def init_chat_system():
#     await chat_system.init()
# import asyncio
# asyncio.run(init_chat_system())

# Set up API
rest_api, channels_api = setup_django_integration(chat_system)

# Add URLs to urlpatterns
urlpatterns = [
    # ... other URL patterns ...
    path('api/', include(rest_api.get_urls()))
]

# In your Django settings.py, add the following for WebSocket support:
# INSTALLED_APPS = [
#     ... other apps ...
#     'channels',
# ]
# 
# ASGI_APPLICATION = 'yourproject.asgi.application'

# In your asgi.py:
# from django.core.asgi import get_asgi_application
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack
# from django.urls import path
# 
# from chatms_plugin.api.django import setup_django_integration
# 
# # Create chat system (same as in urls.py)
# rest_api, channels_api = setup_django_integration(chat_system)
# 
# # Set up WebSocket routing
# websocket_urlpatterns = [
#     path('ws/<str:user_id>/', channels_api.get_consumer().as_asgi()),
# ]
# 
# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),
#     "websocket": AuthMiddlewareStack(
#         URLRouter(websocket_urlpatterns)
#     ),
# })
"""