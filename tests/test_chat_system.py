# tests/test_chat_system.py

"""
Tests for the ChatMS plugin's chat system functionality.
"""

import asyncio
import os
import pytest
from datetime import datetime
from uuid import uuid4

from chatms_plugin import ChatSystem, Config, ChatType, MessageType
from chatms_plugin.exceptions import AuthenticationError, AuthorizationError
from chatms_plugin.models.user import UserCreate, UserUpdate
from chatms_plugin.models.chat import ChatCreate, ChatUpdate
from chatms_plugin.models.message import MessageCreate, MessageUpdate


@pytest.fixture
async def config():
    """Create a test configuration."""
    return Config(
        database_type="sqlite",  # Use SQLite for testing
        database_url="sqlite:///:memory:",
        storage_type="local",
        storage_path="./test_storage",
        jwt_secret="test-secret-key",
        jwt_expiration_minutes=60,
        enable_encryption=True,
        encryption_key="0123456789abcdef0123456789abcdef",
        max_file_size_mb=10,
        allowed_extensions=["jpg", "png", "pdf", "txt"]
    )


@pytest.fixture
async def chat_system(config):
    """Create and initialize a chat system for testing."""
    # Create test storage directory if it doesn't exist
    os.makedirs(config.storage_path, exist_ok=True)
    
    # Initialize chat system
    system = ChatSystem(config)
    await system.init()
    
    yield system
    
    # Cleanup
    await system.close()
    
    # Remove test storage directory
    import shutil
    if os.path.exists(config.storage_path):
        shutil.rmtree(config.storage_path)


@pytest.fixture
async def test_user(chat_system):
    """Create a test user."""
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        password="Password123!",
        full_name="Test User"
    )
    
    return await chat_system.register_user(user_data)


@pytest.fixture
async def second_user(chat_system):
    """Create a second test user."""
    user_data = UserCreate(
        username="seconduser",
        email="second@example.com",
        password="Password456!",
        full_name="Second User"
    )
    
    return await chat_system.register_user(user_data)


@pytest.fixture
async def test_chat(chat_system, test_user):
    """Create a test chat."""
    chat_data = ChatCreate(
        name="Test Chat",
        description="A test chat",
        chat_type=ChatType.GROUP,
        member_ids=[test_user.id],
        is_encrypted=False
    )
    
    return await chat_system.create_chat(chat_data, test_user.id)


@pytest.mark.asyncio
async def test_user_registration(chat_system):
    """Test user registration functionality."""
    # Register a new user
    user_data = UserCreate(
        username="newuser",
        email="new@example.com",
        password="StrongPass123!",
        full_name="New User"
    )
    
    user = await chat_system.register_user(user_data)
    
    # Check if user was created correctly
    assert user is not None
    assert user.id is not None
    assert user.username == "newuser"
    assert user.email == "new@example.com"
    assert user.full_name == "New User"
    assert user.hashed_password != "StrongPass123!"  # Password should be hashed
    
    # Try to register with the same username (should fail)
    with pytest.raises(AuthenticationError):
        await chat_system.register_user(user_data)


@pytest.mark.asyncio
async def test_user_authentication(chat_system, test_user):
    """Test user authentication functionality."""
    # Test valid authentication
    token = await chat_system.authenticate_user(test_user.username, "Password123!")
    assert token is not None
    
    # Test invalid password
    with pytest.raises(AuthenticationError):
        await chat_system.authenticate_user(test_user.username, "WrongPassword")
    
    # Test invalid username
    with pytest.raises(AuthenticationError):
        await chat_system.authenticate_user("nonexistentuser", "Password123!")


@pytest.mark.asyncio
async def test_user_update(chat_system, test_user):
    """Test user update functionality."""
    # Update user information
    update_data = UserUpdate(
        full_name="Updated User Name",
        email="updated@example.com"
    )
    
    updated_user = await chat_system.update_user(test_user.id, update_data)
    
    # Check if user was updated correctly
    assert updated_user is not None
    assert updated_user.id == test_user.id
    assert updated_user.full_name == "Updated User Name"
    assert updated_user.email == "updated@example.com"
    assert updated_user.username == test_user.username  # Username should remain unchanged


@pytest.mark.asyncio
async def test_user_status(chat_system, test_user):
    """Test user status update functionality."""
    # Update user status
    updated_user = await chat_system.update_user_status(test_user.id, "away")
    
    # Check if status was updated correctly
    assert updated_user is not None
    assert updated_user.status == "away"
    
    # Status should be updated in the database as well
    user = await chat_system.get_user(test_user.id)
    assert user.status == "away"


@pytest.mark.asyncio
async def test_chat_creation(chat_system, test_user, second_user):
    """Test chat creation functionality."""
    # Create a group chat
    group_chat_data = ChatCreate(
        name="Group Chat",
        description="A group chat for testing",
        chat_type=ChatType.GROUP,
        member_ids=[test_user.id, second_user.id],
        is_encrypted=True
    )
    
    group_chat = await chat_system.create_chat(group_chat_data, test_user.id)
    
    # Check if group chat was created correctly
    assert group_chat is not None
    assert group_chat.id is not None
    assert group_chat.name == "Group Chat"
    assert group_chat.description == "A group chat for testing"
    assert group_chat.chat_type == ChatType.GROUP
    assert group_chat.is_encrypted is True
    assert len(group_chat.members) == 2
    
    # Check if creator is admin
    for member in group_chat.members:
        if member.user_id == test_user.id:
            assert member.role == "admin"
        else:
            assert member.role == "member"
    
    # Create a one-to-one chat
    one_to_one_chat_data = ChatCreate(
        chat_type=ChatType.ONE_TO_ONE,
        member_ids=[test_user.id, second_user.id],
        is_encrypted=False
    )
    
    one_to_one_chat = await chat_system.create_chat(one_to_one_chat_data, test_user.id)
    
    # Check if one-to-one chat was created correctly
    assert one_to_one_chat is not None
    assert one_to_one_chat.id is not None
    assert one_to_one_chat.chat_type == ChatType.ONE_TO_ONE
    assert len(one_to_one_chat.members) == 2


@pytest.mark.asyncio
async def test_chat_update(chat_system, test_user, test_chat):
    """Test chat update functionality."""
    # Update chat information
    update_data = ChatUpdate(
        name="Updated Chat Name",
        description="Updated description"
    )
    
    updated_chat = await chat_system.update_chat(test_chat.id, test_user.id, update_data)
    
    # Check if chat was updated correctly
    assert updated_chat is not None
    assert updated_chat.id == test_chat.id
    assert updated_chat.name == "Updated Chat Name"
    assert updated_chat.description == "Updated description"


@pytest.mark.asyncio
async def test_chat_membership(chat_system, test_user, second_user, test_chat):
    """Test chat membership functionality."""
    # Add second user to chat
    result = await chat_system.add_chat_member(test_chat.id, test_user.id, second_user.id)
    assert result is True
    
    # Check if second user was added correctly
    chat = await chat_system.get_chat(test_chat.id, test_user.id)
    assert chat.is_member(second_user.id)
    
    # Check if second user can access the chat
    chat = await chat_system.get_chat(test_chat.id, second_user.id)
    assert chat is not None
    
    # Remove second user from chat
    result = await chat_system.remove_chat_member(test_chat.id, test_user.id, second_user.id)
    assert result is True
    
    # Check if second user was removed correctly
    chat = await chat_system.get_chat(test_chat.id, test_user.id)
    assert not chat.is_member(second_user.id)
    
    # Second user should no longer be able to access the chat
    with pytest.raises(AuthorizationError):
        await chat_system.get_chat(test_chat.id, second_user.id)


@pytest.mark.asyncio
async def test_message_sending(chat_system, test_user, test_chat):
    """Test message sending functionality."""
    # Send a text message
    message_data = MessageCreate(
        chat_id=test_chat.id,
        content="Hello, world!",
        message_type=MessageType.TEXT
    )
    
    message = await chat_system.send_message(test_user.id, message_data)
    
    # Check if message was sent correctly
    assert message is not None
    assert message.id is not None
    assert message.chat_id == test_chat.id
    assert message.sender_id == test_user.id
    assert message.content == "Hello, world!"
    assert message.message_type == MessageType.TEXT
    
    # Get messages for the chat
    messages = await chat_system.get_chat_messages(test_chat.id, test_user.id)
    assert len(messages) == 1
    assert messages[0].id == message.id


@pytest.mark.asyncio
async def test_message_update(chat_system, test_user, test_chat):
    """Test message update functionality."""
    # Send a message
    message_data = MessageCreate(
        chat_id=test_chat.id,
        content="Original message",
        message_type=MessageType.TEXT
    )
    
    message = await chat_system.send_message(test_user.id, message_data)
    
    # Update the message
    update_data = MessageUpdate(
        content="Updated message"
    )
    
    updated_message = await chat_system.update_message(message.id, test_user.id, update_data)
    
    # Check if message was updated correctly
    assert updated_message is not None
    assert updated_message.id == message.id
    assert updated_message.content == "Updated message"
    assert updated_message.edited_at is not None


@pytest.mark.asyncio
async def test_message_deletion(chat_system, test_user, test_chat):
    """Test message deletion functionality."""
    # Send a message
    message_data = MessageCreate(
        chat_id=test_chat.id,
        content="Message to be deleted",
        message_type=MessageType.TEXT
    )
    
    message = await chat_system.send_message(test_user.id, message_data)
    
    # Delete the message for everyone
    result = await chat_system.delete_message(message.id, test_user.id, True)
    assert result is True
    
    # Message should no longer be retrievable
    messages = await chat_system.get_chat_messages(test_chat.id, test_user.id)
    assert len(messages) == 0


@pytest.mark.asyncio
async def test_message_reactions(chat_system, test_user, second_user, test_chat):
    """Test message reactions functionality."""
    # Add second user to chat
    await chat_system.add_chat_member(test_chat.id, test_user.id, second_user.id)
    
    # Send a message
    message_data = MessageCreate(
        chat_id=test_chat.id,
        content="Message for reactions",
        message_type=MessageType.TEXT
    )
    
    message = await chat_system.send_message(test_user.id, message_data)
    
    # Add reactions
    reaction1 = await chat_system.add_reaction(message.id, test_user.id, "👍")
    assert reaction1 is not None
    
    reaction2 = await chat_system.add_reaction(message.id, second_user.id, "❤️")
    assert reaction2 is not None
    
    # Get message with reactions
    message = await chat_system.get_message(message.id, test_user.id)
    assert len(message.reactions) == 2
    
    # Remove a reaction
    result = await chat_system.remove_reaction(message.id, test_user.id, "👍")
    assert result is True
    
    # Check if reaction was removed
    message = await chat_system.get_message(message.id, test_user.id)
    assert len(message.reactions) == 1
    assert message.reactions[0].user_id == second_user.id
    assert message.reactions[0].reaction_type == "❤️"


@pytest.mark.asyncio
async def test_message_pinning(chat_system, test_user, test_chat):
    """Test message pinning functionality."""
    # Send a message
    message_data = MessageCreate(
        chat_id=test_chat.id,
        content="Message to be pinned",
        message_type=MessageType.TEXT
    )
    
    message = await chat_system.send_message(test_user.id, message_data)
    
    # Pin the message
    pinned_message = await chat_system.pin_message(message.id, test_user.id)
    assert pinned_message is not None
    assert pinned_message.is_pinned is True
    
    # Get pinned messages
    pinned_messages = await chat_system.get_pinned_messages(test_chat.id, test_user.id)
    assert len(pinned_messages) == 1
    assert pinned_messages[0].id == message.id
    
    # Unpin the message
    unpinned_message = await chat_system.unpin_message(message.id, test_user.id)
    assert unpinned_message is not None
    assert unpinned_message.is_pinned is False
    
    # Check if message was unpinned
    pinned_messages = await chat_system.get_pinned_messages(test_chat.id, test_user.id)
    assert len(pinned_messages) == 0


@pytest.mark.asyncio
async def test_read_receipts(chat_system, test_user, second_user, test_chat):
    """Test read receipts functionality."""
    # Add second user to chat
    await chat_system.add_chat_member(test_chat.id, test_user.id, second_user.id)
    
    # Send multiple messages
    messages = []
    for i in range(3):
        message_data = MessageCreate(
            chat_id=test_chat.id,
            content=f"Message {i}",
            message_type=MessageType.TEXT
        )
        
        message = await chat_system.send_message(test_user.id, message_data)
        messages.append(message)
    
    # Mark specific message as read
    result = await chat_system.mark_messages_read(
        chat_id=test_chat.id,
        user_id=second_user.id,
        message_ids=[messages[0].id]
    )
    assert result is True
    
    # Mark all messages up to a point as read
    result = await chat_system.mark_messages_read(
        chat_id=test_chat.id,
        user_id=second_user.id,
        read_until_id=messages[-1].id
    )
    assert result is True


@pytest.mark.asyncio
async def test_typing_indicator(chat_system, test_user, test_chat):
    """Test typing indicator functionality."""
    # Send typing indicator
    result = await chat_system.send_typing_indicator(test_chat.id, test_user.id, True)
    assert result is True
    
    # Stop typing indicator
    result = await chat_system.send_typing_indicator(test_chat.id, test_user.id, False)
    assert result is True


@pytest.mark.asyncio
async def test_chat_deletion(chat_system, test_user, test_chat):
    """Test chat deletion functionality."""
    # Send some messages
    message_data = MessageCreate(
        chat_id=test_chat.id,
        content="Test message",
        message_type=MessageType.TEXT
    )
    
    await chat_system.send_message(test_user.id, message_data)
    
    # Delete the chat
    result = await chat_system.delete_chat(test_chat.id, test_user.id)
    assert result is True
    
    # User shouldn't be able to access the chat anymore
    with pytest.raises(Exception):
        await chat_system.get_chat(test_chat.id, test_user.id)