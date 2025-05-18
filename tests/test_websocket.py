# tests/test_websocket.py

"""
Tests for the ChatMS plugin's WebSocket functionality.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from chatms_plugin import Config
from chatms_plugin.core.connection import ConnectionManager
from chatms_plugin.exceptions import ConnectionError


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.sent_messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
    
    async def send_json(self, data):
        self.sent_messages.append(data)
    
    async def send_text(self, text):
        self.sent_messages.append(json.loads(text))
    
    async def close(self, code=1000, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config(
        websocket_ping_interval=30
    )


@pytest.fixture
def connection_manager(config):
    """Create a connection manager for testing."""
    return ConnectionManager(config)


@pytest.mark.asyncio
async def test_connection(connection_manager):
    """Test WebSocket connection."""
    # Initialize connection manager
    await connection_manager.init()
    
    # Create mock WebSocket
    websocket = MockWebSocket()
    user_id = "test_user"
    
    # Connect WebSocket
    await connection_manager.connect(websocket, user_id)
    
    # Check if user is connected
    assert user_id in connection_manager.user_connections
    assert websocket in connection_manager.user_connections[user_id]
    
    # Check if welcome message was sent
    assert len(websocket.sent_messages) == 1
    assert websocket.sent_messages[0]["type"] == "connected"
    assert websocket.sent_messages[0]["user_id"] == user_id
    
    # Disconnect WebSocket
    await connection_manager.disconnect(websocket, user_id)
    
    # Check if user is disconnected
    assert user_id not in connection_manager.user_connections
    
    # Cleanup
    await connection_manager.close()


@pytest.mark.asyncio
async def test_chat_room_operations(connection_manager):
    """Test chat room operations."""
    # Initialize connection manager
    await connection_manager.init()
    
    # Create mock WebSocket
    websocket = MockWebSocket()
    user_id = "test_user"
    chat_id = "test_chat"
    
    # Connect WebSocket
    await connection_manager.connect(websocket, user_id)
    
    # Join chat
    await connection_manager.join_chat(websocket, chat_id)
    
    # Check if WebSocket is in chat room
    assert chat_id in connection_manager.active_connections
    assert websocket in connection_manager.active_connections[chat_id]
    
    # Check if joined message was sent
    assert websocket.sent_messages[-1]["type"] == "chat_joined"
    assert websocket.sent_messages[-1]["chat_id"] == chat_id
    
    # Leave chat
    await connection_manager.leave_chat(websocket, chat_id)
    
    # Check if WebSocket left chat room
    assert chat_id not in connection_manager.active_connections
    
    # Check if left message was sent
    assert websocket.sent_messages[-1]["type"] == "chat_left"
    assert websocket.sent_messages[-1]["chat_id"] == chat_id
    
    # Cleanup
    await connection_manager.disconnect(websocket, user_id)
    await connection_manager.close()


@pytest.mark.asyncio
async def test_message_broadcasting(connection_manager):
    """Test message broadcasting."""
    # Initialize connection manager
    await connection_manager.init()
    
    # Create mock WebSockets
    websocket1 = MockWebSocket()
    websocket2 = MockWebSocket()
    websocket3 = MockWebSocket()
    
    user1 = "user1"
    user2 = "user2"
    user3 = "user3"
    chat_id = "test_chat"
    
    # Connect WebSockets
    await connection_manager.connect(websocket1, user1)
    await connection_manager.connect(websocket2, user2)
    await connection_manager.connect(websocket3, user3)
    
    # Join chat
    await connection_manager.join_chat(websocket1, chat_id)
    await connection_manager.join_chat(websocket2, chat_id)
    # User3 doesn't join the chat
    
    # Broadcast message to chat
    message = {
        "chat_id": chat_id,
        "content": "Hello, everyone!",
        "sender_id": user1
    }
    
    await connection_manager.broadcast_message(message)
    
    # Check if message was broadcast to users in the chat
    assert len(websocket1.sent_messages) > 1
    assert len(websocket2.sent_messages) > 1
    
    last_message1 = websocket1.sent_messages[-1]
    last_message2 = websocket2.sent_messages[-1]
    
    assert last_message1["chat_id"] == chat_id
    assert last_message1["content"] == "Hello, everyone!"
    assert last_message2["chat_id"] == chat_id
    assert last_message2["content"] == "Hello, everyone!"
    
    # User3 shouldn't receive the message
    assert len(websocket3.sent_messages) == 1  # Only the welcome message
    
    # Cleanup
    await connection_manager.disconnect(websocket1, user1)
    await connection_manager.disconnect(websocket2, user2)
    await connection_manager.disconnect(websocket3, user3)
    await connection_manager.close()


@pytest.mark.asyncio
async def test_personal_message(connection_manager):
    """Test personal message sending."""
    # Initialize connection manager
    await connection_manager.init()
    
    # Create mock WebSockets for the same user (multiple devices)
    websocket1 = MockWebSocket()
    websocket2 = MockWebSocket()
    
    user_id = "test_user"
    
    # Connect WebSockets
    await connection_manager.connect(websocket1, user_id)
    await connection_manager.connect(websocket2, user_id)
    
    # Send personal message
    message = {
        "content": "Personal message",
        "timestamp": "2023-01-01T12:00:00"
    }
    
    result = await connection_manager.send_personal_message(user_id, message)
    assert result is True
    
    # Check if message was sent to all user's connections
    assert len(websocket1.sent_messages) > 1
    assert len(websocket2.sent_messages) > 1
    
    last_message1 = websocket1.sent_messages[-1]
    last_message2 = websocket2.sent_messages[-1]
    
    assert last_message1["content"] == "Personal message"
    assert last_message2["content"] == "Personal message"
    
    # Cleanup
    await connection_manager.disconnect(websocket1, user_id)
    await connection_manager.disconnect(websocket2, user_id)
    await connection_manager.close()


@pytest.mark.asyncio
async def test_notification_methods(connection_manager):
    """Test specialized notification methods."""
    # Initialize connection manager
    await connection_manager.init()
    
    # Create mock WebSocket
    websocket = MockWebSocket()
    user_id = "test_user"
    
    # Connect WebSocket
    await connection_manager.connect(websocket, user_id)
    
    # Test different notification types
    notifications = [
        # New message notification
        ("send_new_message", {"message_id": "msg1", "content": "New message"}),
        
        # Message updated notification
        ("send_message_updated", {"message_id": "msg1", "content": "Updated message"}),
        
        # Message deleted notification
        ("send_message_deleted", {"message_id": "msg1", "chat_id": "chat1"}),
        
        # Reaction added notification
        ("send_reaction_added", {"message_id": "msg1", "reaction_type": "👍"}),
        
        # Typing indicator notification
        ("send_typing_indicator", {"chat_id": "chat1", "is_typing": True})
    ]
    
    for method_name, data in notifications:
        # Get method
        method = getattr(connection_manager, method_name)
        
        # Send notification
        result = await method(user_id, data)
        assert result is True
        
        # Check if notification was sent
        last_message = websocket.sent_messages[-1]
        for key, value in data.items():
            assert last_message[key] == value
    
    # Cleanup
    await connection_manager.disconnect(websocket, user_id)
    await connection_manager.close()