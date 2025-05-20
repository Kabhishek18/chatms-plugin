# tests/test_websocket.py

"""
Tests for the ChatMS plugin's WebSocket functionality.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from copy import deepcopy

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
    
    async def accept(self):
        """Accept the connection."""
        pass
    
    async def send_json(self, data):
        self.sent_messages.append(data)
    
    async def send_text(self, text):
        self.sent_messages.append(json.loads(text))
    
    async def close(self, code=1000, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.fixture(scope="function")
def config():
    """Create a test configuration."""
    return Config(
        websocket_ping_interval=30
    )


@pytest.fixture(scope="function")
async def connection_manager(config):
    """Create a connection manager for testing."""
    manager = ConnectionManager(config)
    # Don't start the ping task to avoid timing issues
    manager.active_connections = {}
    manager.user_connections = {}
    yield manager
    await manager.close()


@pytest.mark.asyncio
async def test_connection(connection_manager):
    """Test WebSocket connection."""
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


@pytest.mark.asyncio
async def test_chat_room_operations(connection_manager):
    """Test chat room operations."""
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


@pytest.mark.asyncio
async def test_message_broadcasting(connection_manager):
    """Test message broadcasting."""
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
        "type": "message",
        "chat_id": chat_id,
        "content": "Hello, everyone!",
        "sender_id": user1,
        "timestamp": "2023-01-01T12:00:00Z"
    }
    
    await connection_manager.broadcast_message(message)
    
    # Check if message was broadcast to users in the chat
    assert len(websocket1.sent_messages) > 1
    assert len(websocket2.sent_messages) > 1
    
    last_message1 = websocket1.sent_messages[-1]
    last_message2 = websocket2.sent_messages[-1]
    
    assert last_message1["type"] == "message"
    assert last_message1["chat_id"] == chat_id
    assert last_message1["content"] == "Hello, everyone!"
    assert last_message2["type"] == "message"
    assert last_message2["chat_id"] == chat_id
    assert last_message2["content"] == "Hello, everyone!"
    
    # User3 shouldn't receive the message
    assert len(websocket3.sent_messages) == 1  # Only the welcome message
    
    # Cleanup
    await connection_manager.disconnect(websocket1, user1)
    await connection_manager.disconnect(websocket2, user2)
    await connection_manager.disconnect(websocket3, user3)


@pytest.mark.asyncio
async def test_personal_message(connection_manager):
    """Test personal message sending."""
    # Create mock WebSockets for the same user (multiple devices)
    websocket1 = MockWebSocket()
    websocket2 = MockWebSocket()
    
    user_id = "test_user"
    
    # Connect WebSockets
    await connection_manager.connect(websocket1, user_id)
    await connection_manager.connect(websocket2, user_id)
    
    # Send personal message
    message = {
        "type": "personal_message",
        "content": "Personal message",
        "timestamp": "2023-01-01T12:00:00"
    }
    
    result = await connection_manager.send_personal_message(user_id, message)
    assert result is True
    
    # Check if message was sent to all user's connections
    # Should have 2 messages: welcome + personal
    assert len(websocket1.sent_messages) == 2
    assert len(websocket2.sent_messages) == 2
    
    last_message1 = websocket1.sent_messages[-1]
    last_message2 = websocket2.sent_messages[-1]
    
    assert last_message1["type"] == "personal_message"
    assert last_message1["content"] == "Personal message"
    assert last_message2["type"] == "personal_message"
    assert last_message2["content"] == "Personal message"
    
    # Cleanup
    await connection_manager.disconnect(websocket1, user_id)
    await connection_manager.disconnect(websocket2, user_id)


@pytest.mark.asyncio
async def test_notification_methods(connection_manager):
    """Test specialized notification methods."""
    # Create mock WebSocket
    websocket = MockWebSocket()
    user_id = "test_user"
    
    # Connect WebSocket
    await connection_manager.connect(websocket, user_id)
    
    # Test different notification types
    notifications = [
        # New message notification
        ("send_new_message", {"message_id": "msg1", "content": "New message", "chat_id": "chat1"}),
        
        # Message updated notification
        ("send_message_updated", {"message_id": "msg1", "content": "Updated message", "chat_id": "chat1"}),
        
        # Message deleted notification
        ("send_message_deleted", {"message_id": "msg1", "chat_id": "chat1"}),
        
        # Reaction added notification
        ("send_reaction_added", {"message_id": "msg1", "reaction_type": "👍", "chat_id": "chat1"}),
        
        # Typing indicator notification
        ("send_typing_indicator", {"chat_id": "chat1", "is_typing": True, "user_id": user_id})
    ]
    
    for method_name, data in notifications:
        # Get method
        method = getattr(connection_manager, method_name)
        
        # Send notification
        result = await method(user_id, data)
        assert result is True
        
        # Check if notification was sent
        last_message = websocket.sent_messages[-1]
        
        # Check that expected data fields are present
        if method_name == "send_new_message":
            assert last_message["type"] == "new_message"
        elif method_name == "send_message_updated":
            assert last_message["type"] == "message_updated"
        elif method_name == "send_message_deleted":
            assert last_message["type"] == "message_deleted"
        elif method_name == "send_reaction_added":
            assert last_message["type"] == "reaction_added"
        elif method_name == "send_typing_indicator":
            assert last_message["type"] == "typing_indicator"
        
        # Verify data was included in the message
        for key, value in data.items():
            if key in last_message:
                assert last_message[key] == value
    
    # Cleanup
    await connection_manager.disconnect(websocket, user_id)


@pytest.mark.asyncio
async def test_presence_update(connection_manager):
    """Test presence update functionality."""
    # Create mock WebSockets for different users
    websocket1 = MockWebSocket()
    websocket2 = MockWebSocket()
    
    user1 = "user1"
    user2 = "user2"
    
    # Connect WebSockets
    await connection_manager.connect(websocket1, user1)
    await connection_manager.connect(websocket2, user2)
    
    # Update presence
    presence_data = {
        "user_id": user1,
        "status": "online",
        "last_seen": "2023-01-01T12:00:00Z"
    }
    
    await connection_manager.update_presence(presence_data)
    
    # Check if presence update was sent to other users
    # user2 should receive the presence update
    assert len(websocket2.sent_messages) >= 2  # welcome + presence
    last_message = websocket2.sent_messages[-1]
    assert last_message["type"] == "presence_update"
    assert last_message["user_id"] == user1
    assert last_message["status"] == "online"
    
    # user1 should not receive their own presence update
    # Check that user1 only has the welcome message
    presence_messages = [msg for msg in websocket1.sent_messages if msg.get("type") == "presence_update"]
    assert len(presence_messages) == 0
    
    # Cleanup
    await connection_manager.disconnect(websocket1, user1)
    await connection_manager.disconnect(websocket2, user2)


@pytest.mark.asyncio
async def test_connection_cleanup():
    """Test proper cleanup of connections."""
    config = Config(websocket_ping_interval=30)
    connection_manager = ConnectionManager(config)
    
    # Initialize without starting ping task to avoid timing issues
    connection_manager.active_connections = {}
    connection_manager.user_connections = {}
    
    # Create mock WebSocket
    websocket = MockWebSocket()
    user_id = "test_user"
    chat_id = "test_chat"
    
    # Manually add connection (simulating accept)
    connection_manager.user_connections[user_id] = {websocket}
    connection_manager.active_connections[chat_id] = {websocket}
    
    # Disconnect
    await connection_manager.disconnect(websocket, user_id)
    
    # Check cleanup
    assert user_id not in connection_manager.user_connections
    assert chat_id not in connection_manager.active_connections
    
    # Cleanup
    await connection_manager.close()


@pytest.mark.asyncio
async def test_multiple_connections_same_user(connection_manager):
    """Test handling multiple connections for the same user."""
    # Create multiple mock WebSockets for the same user
    websocket1 = MockWebSocket()
    websocket2 = MockWebSocket()
    websocket3 = MockWebSocket()
    
    user_id = "test_user"
    
    # Connect all WebSockets for the same user
    await connection_manager.connect(websocket1, user_id)
    await connection_manager.connect(websocket2, user_id)
    await connection_manager.connect(websocket3, user_id)
    
    # Check that all connections are stored
    assert user_id in connection_manager.user_connections
    assert len(connection_manager.user_connections[user_id]) == 3
    assert websocket1 in connection_manager.user_connections[user_id]
    assert websocket2 in connection_manager.user_connections[user_id]
    assert websocket3 in connection_manager.user_connections[user_id]
    
    # Send a personal message
    message = {"content": "Test message"}
    result = await connection_manager.send_personal_message(user_id, message)
    assert result is True
    
    # All connections should receive the message
    assert len(websocket1.sent_messages) == 2  # welcome + personal message
    assert len(websocket2.sent_messages) == 2  # welcome + personal message
    assert len(websocket3.sent_messages) == 2  # welcome + personal message
    
    # Disconnect one WebSocket
    await connection_manager.disconnect(websocket1, user_id)
    
    # Check that only the disconnected WebSocket was removed
    assert user_id in connection_manager.user_connections
    assert len(connection_manager.user_connections[user_id]) == 2
    assert websocket1 not in connection_manager.user_connections[user_id]
    assert websocket2 in connection_manager.user_connections[user_id]
    assert websocket3 in connection_manager.user_connections[user_id]
    
    # Disconnect remaining WebSockets
    await connection_manager.disconnect(websocket2, user_id)
    await connection_manager.disconnect(websocket3, user_id)
    
    # Now the user should be completely disconnected
    assert user_id not in connection_manager.user_connections


@pytest.mark.asyncio
async def test_empty_message_handling(connection_manager):
    """Test handling of edge cases with messages."""
    # Test broadcasting message without chat_id
    message_without_chat = {
        "type": "message",
        "content": "Hello"
    }
    
    # Should not raise an exception, just log an error
    await connection_manager.broadcast_message(message_without_chat)
    
    # Test sending personal message to non-existent user
    result = await connection_manager.send_personal_message("non_existent_user", {"content": "test"})
    assert result is False
    
    # Test sending presence update without user_id
    await connection_manager.update_presence({"status": "online"})
    # Should not raise an exception, just log an error