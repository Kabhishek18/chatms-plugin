"""
Simple server example for the ChatMS plugin.
"""

import argparse
import asyncio
import json
import logging
import os
from typing import Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from chatms_plugin import ChatSystem, Config
from chatms_plugin.exceptions import (
    AuthenticationError, AuthorizationError, ChatError, ChatMSError,
    ConfigurationError, MessageError, StorageError, UserError, ValidationError
)
from chatms_plugin.models.chat import ChatCreate, ChatUpdate
from chatms_plugin.models.message import MessageCreate, MessageUpdate
from chatms_plugin.models.user import UserCreate, UserUpdate


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("chatms-server")

# Create FastAPI app
app = FastAPI(title="ChatMS Server", description="Chat Messaging System Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Global chat system instance
chat_system = None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Get the current user from the token.
    
    Args:
        token: JWT token
        
    Returns:
        str: User ID
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        return await chat_system.security_manager.get_user_id_from_token(token)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize the chat system on startup."""
    global chat_system
    
    # Load configuration
    config = Config()
    
    # Create chat system
    chat_system = ChatSystem(config)
    
    # Initialize
    await chat_system.init()
    
    logger.info("Chat system initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Close the chat system on shutdown."""
    global chat_system
    
    if chat_system:
        await chat_system.close()
        logger.info("Chat system closed")


@app.exception_handler(ChatMSError)
async def chatms_exception_handler(request: Request, exc: ChatMSError):
    """Handle ChatMS exceptions."""
    status_code = 500
    
    if isinstance(exc, AuthenticationError):
        status_code = 401
    elif isinstance(exc, AuthorizationError):
        status_code = 403
    elif isinstance(exc, ValidationError):
        status_code = 400
    elif isinstance(exc, (UserError, ChatError, MessageError)):
        status_code = 404
    elif isinstance(exc, StorageError):
        status_code = 500
    
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message},
    )


# Authentication endpoints

@app.post("/register")
async def register(user_data: UserCreate):
    """Register a new user."""
    user = await chat_system.register_user(user_data)
    return {"id": user.id, "username": user.username}


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    token = await chat_system.authenticate_user(form_data.username, form_data.password)
    
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"access_token": token, "token_type": "bearer"}


# User endpoints

@app.get("/users/me")
async def get_current_user_info(user_id: str = Depends(get_current_user)):
    """Get current user information."""
    user = await chat_system.get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@app.put("/users/me")
async def update_current_user(
    user_data: UserUpdate,
    user_id: str = Depends(get_current_user)
):
    """Update current user information."""
    user = await chat_system.update_user(user_id, user_data)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@app.put("/users/me/status")
async def update_status(
    status: str,
    user_id: str = Depends(get_current_user)
):
    """Update user status."""
    user = await chat_system.update_user_status(user_id, status)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"status": user.status}


# Chat endpoints

@app.post("/chats")
async def create_chat(
    chat_data: ChatCreate,
    user_id: str = Depends(get_current_user)
):
    """Create a new chat."""
    chat = await chat_system.create_chat(chat_data, user_id)
    return chat


@app.get("/chats")
async def get_chats(user_id: str = Depends(get_current_user)):
    """Get all chats for the current user."""
    chats = await chat_system.get_user_chats(user_id)
    return chats


@app.get("/chats/{chat_id}")
async def get_chat(
    chat_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get a chat by ID."""
    chat = await chat_system.get_chat(chat_id, user_id)
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return chat


@app.put("/chats/{chat_id}")
async def update_chat(
    chat_id: str,
    chat_data: ChatUpdate,
    user_id: str = Depends(get_current_user)
):
    """Update a chat."""
    chat = await chat_system.update_chat(chat_id, user_id, chat_data)
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return chat


@app.post("/chats/{chat_id}/members/{member_id}")
async def add_chat_member(
    chat_id: str,
    member_id: str,
    user_id: str = Depends(get_current_user)
):
    """Add a member to a chat."""
    result = await chat_system.add_chat_member(chat_id, user_id, member_id)
    return {"success": result}


@app.delete("/chats/{chat_id}/members/{member_id}")
async def remove_chat_member(
    chat_id: str,
    member_id: str,
    user_id: str = Depends(get_current_user)
):
    """Remove a member from a chat."""
    result = await chat_system.remove_chat_member(chat_id, user_id, member_id)
    return {"success": result}


# Message endpoints

@app.post("/messages")
async def send_message(
    message_data: MessageCreate,
    user_id: str = Depends(get_current_user)
):
    """Send a message."""
    message = await chat_system.send_message(user_id, message_data)
    return message


@app.get("/chats/{chat_id}/messages")
async def get_messages(
    chat_id: str,
    before_id: Optional[str] = None,
    after_id: Optional[str] = None,
    limit: int = 50,
    user_id: str = Depends(get_current_user)
):
    """Get messages for a chat."""
    messages = await chat_system.get_chat_messages(
        chat_id=chat_id,
        user_id=user_id,
        before_id=before_id,
        after_id=after_id,
        limit=limit
    )
    
    return messages


@app.put("/messages/{message_id}")
async def update_message(
    message_id: str,
    message_data: MessageUpdate,
    user_id: str = Depends(get_current_user)
):
    """Update a message."""
    message = await chat_system.update_message(message_id, user_id, message_data)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return message


@app.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    delete_for_everyone: bool = False,
    user_id: str = Depends(get_current_user)
):
    """Delete a message."""
    result = await chat_system.delete_message(message_id, user_id, delete_for_everyone)
    return {"success": result}


@app.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: str,
    user_id: str = Depends(get_current_user)
):
    """Mark a message as read."""
    # Get message to find chat_id
    message = await chat_system.get_message(message_id, user_id)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    result = await chat_system.mark_messages_read(
        chat_id=message.chat_id,
        user_id=user_id,
        message_ids=[message_id]
    )
    
    return {"success": result}


@app.post("/chats/{chat_id}/read")
async def mark_chat_read(
    chat_id: str,
    read_until_id: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """Mark all messages in a chat as read."""
    result = await chat_system.mark_messages_read(
        chat_id=chat_id,
        user_id=user_id,
        read_until_id=read_until_id
    )
    
    return {"success": result}


@app.post("/messages/{message_id}/reactions/{reaction_type}")
async def add_reaction(
    message_id: str,
    reaction_type: str,
    user_id: str = Depends(get_current_user)
):
    """Add a reaction to a message."""
    result = await chat_system.add_reaction(message_id, user_id, reaction_type)
    return {"success": result}


@app.delete("/messages/{message_id}/reactions/{reaction_type}")
async def remove_reaction(
    message_id: str,
    reaction_type: str,
    user_id: str = Depends(get_current_user)
):
    """Remove a reaction from a message."""
    result = await chat_system.remove_reaction(message_id, user_id, reaction_type)
    return {"success": result}


@app.post("/messages/{message_id}/pin")
async def pin_message(
    message_id: str,
    user_id: str = Depends(get_current_user)
):
    """Pin a message."""
    message = await chat_system.pin_message(message_id, user_id)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return message


@app.post("/messages/{message_id}/unpin")
async def unpin_message(
    message_id: str,
    user_id: str = Depends(get_current_user)
):
    """Unpin a message."""
    message = await chat_system.unpin_message(message_id, user_id)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return message


@app.get("/chats/{chat_id}/pinned")
async def get_pinned_messages(
    chat_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get all pinned messages in a chat."""
    messages = await chat_system.get_pinned_messages(chat_id, user_id)
    return messages


# File endpoints

@app.post("/uploads")
async def upload_file(
    chat_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """Upload a file."""
    file_content = await file.read()
    file_url = await chat_system.upload_file(
        chat_id=chat_id,
        user_id=user_id,
        file_data=file_content,
        file_name=file.filename,
        content_type=file.content_type
    )
    
    return {"file_url": file_url}


@app.post("/messages/file")
async def send_file_message(
    chat_id: str,
    file_url: str,
    file_name: str,
    content_type: str,
    caption: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """Send a file message."""
    message = await chat_system.send_file_message(
        sender_id=user_id,
        chat_id=chat_id,
        file_url=file_url,
        file_name=file_name,
        content_type=content_type,
        caption=caption
    )
    
    return message


# Typing indicator endpoint

@app.post("/chats/{chat_id}/typing")
async def send_typing_indicator(
    chat_id: str,
    is_typing: bool = True,
    user_id: str = Depends(get_current_user)
):
    """Send a typing indicator."""
    result = await chat_system.send_typing_indicator(chat_id, user_id, is_typing)
    return {"success": result}


# Search endpoint

@app.get("/search")
async def search_messages(
    query: str,
    chat_id: Optional[str] = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user)
):
    """Search for messages."""
    messages = await chat_system.search_messages(user_id, query, chat_id, limit)
    return messages


# Analytics endpoints

@app.get("/stats/chat/{chat_id}")
async def get_chat_stats(
    chat_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get statistics for a chat."""
    stats = await chat_system.get_chat_stats(chat_id, user_id)
    return stats


@app.get("/stats/user")
async def get_user_stats(user_id: str = Depends(get_current_user)):
    """Get statistics for the current user."""
    stats = await chat_system.get_user_stats(user_id)
    return stats


# WebSocket endpoint

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time messaging."""
    # Authenticate user
    try:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Missing token")
            return
        
        # Verify token
        authenticated_user_id = await chat_system.security_manager.get_user_id_from_token(token)
        
        if authenticated_user_id != user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Accept connection
        await chat_system.connection_manager.connect(websocket, user_id)
        
        try:
            # Process messages
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                # Handle different message types
                message_type = data.get("type")
                
                if message_type == "join_chat":
                    chat_id = data.get("chat_id")
                    if chat_id:
                        # Check if user is member of the chat
                        chat = await chat_system.get_chat(chat_id, user_id)
                        if chat:
                            await chat_system.connection_manager.join_chat(websocket, chat_id)
                
                elif message_type == "leave_chat":
                    chat_id = data.get("chat_id")
                    if chat_id:
                        await chat_system.connection_manager.leave_chat(websocket, chat_id)
                
                elif message_type == "typing":
                    chat_id = data.get("chat_id")
                    is_typing = data.get("is_typing", True)
                    if chat_id:
                        await chat_system.send_typing_indicator(chat_id, user_id, is_typing)
                
                elif message_type == "read":
                    chat_id = data.get("chat_id")
                    message_ids = data.get("message_ids")
                    read_until_id = data.get("read_until_id")
                    
                    if chat_id:
                        await chat_system.mark_messages_read(
                            chat_id=chat_id,
                            user_id=user_id,
                            message_ids=message_ids,
                            read_until_id=read_until_id
                        )
                
                elif message_type == "ping":
                    # Respond with pong
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": data.get("timestamp")
                    })
                
        except WebSocketDisconnect:
            # Handle disconnection
            await chat_system.connection_manager.disconnect(websocket, user_id)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await chat_system.connection_manager.disconnect(websocket, user_id)
    
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")


def main():
    """Run the server."""
    parser = argparse.ArgumentParser(description="ChatMS Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "chatms_plugin.examples.simple_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()