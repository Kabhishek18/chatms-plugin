# tests/test_chat_system.py

"""
Tests for the ChatMS plugin's chat system functionality.
"""

import asyncio
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from chatms_plugin import ChatSystem, Config, ChatType, MessageType, MessageStatus
from chatms_plugin.exceptions import AuthenticationError, AuthorizationError
from chatms_plugin.models.user import UserCreate, UserUpdate, User
from chatms_plugin.models.chat import ChatCreate, ChatUpdate, Chat
from chatms_plugin.models.message import MessageCreate, MessageUpdate, Message
from tests.mocks import MockDatabaseHandler


@pytest.fixture(scope="function")
def config():
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


@pytest.fixture(scope="function")
async def chat_system(config):
    """Create and initialize a chat system for testing."""
    # Create test storage directory if it doesn't exist
    os.makedirs(config.storage_path, exist_ok=True)
    
    # Initialize chat system with mock database handler
    system = ChatSystem(config)
    
    # Create and set mock database handler
    mock_db = MockDatabaseHandler(config)
    await mock_db.init()
    system.db_handler = mock_db
    
    # Mock other components
    system.storage_handler = MagicMock()
    system.storage_handler.init = AsyncMock()
    system.storage_handler.close = AsyncMock()
    system.storage_handler.save_file = AsyncMock(return_value="file_path")
    system.storage_handler.get_file = AsyncMock(return_value=b"file_content")
    
    system.notification_handler = MagicMock()
    system.notification_handler.init = AsyncMock()
    system.notification_handler.close = AsyncMock()
    system.notification_handler.send_notification = AsyncMock(return_value=True)
    
    system.connection_manager = MagicMock()
    system.connection_manager.init = AsyncMock()
    system.connection_manager.close = AsyncMock()
    system.connection_manager.connect = AsyncMock()
    system.connection_manager.disconnect = AsyncMock()
    system.connection_manager.join_chat = AsyncMock()
    system.connection_manager.leave_chat = AsyncMock()
    system.connection_manager.send_new_message = AsyncMock(return_value=True)
    system.connection_manager.send_typing_indicator = AsyncMock(return_value=True)
    system.connection_manager.send_message_updated = AsyncMock(return_value=True)
    system.connection_manager.send_chat_member_added = AsyncMock()
    system.connection_manager.send_chat_member_removed = AsyncMock()
    system.connection_manager.send_message_deleted = AsyncMock(return_value=True)
    system.connection_manager.send_reaction_added = AsyncMock(return_value=True)
    system.connection_manager.send_reaction_removed = AsyncMock(return_value=True)
    system.connection_manager.send_message_pinned = AsyncMock(return_value=True)
    system.connection_manager.send_message_unpinned = AsyncMock(return_value=True)
    system.connection_manager.send_messages_read = AsyncMock(return_value=True)
    system.connection_manager.update_presence = AsyncMock()
    
    system.analytics_service = MagicMock()
    system.analytics_service.init = AsyncMock()
    system.analytics_service.track_user_registered = AsyncMock()
    system.analytics_service.track_auth_success = AsyncMock()
    system.analytics_service.track_auth_failure = AsyncMock()
    system.analytics_service.track_message = AsyncMock()
    system.analytics_service.track_chat_created = AsyncMock()
    system.analytics_service.start_timer = MagicMock()
    system.analytics_service.stop_timer = AsyncMock()
    
    system.security_manager.encrypt = AsyncMock(side_effect=lambda x: x)  # Just return the input
    system.security_manager.decrypt = AsyncMock(side_effect=lambda x: x)  # Just return the input
    
    # Initialize the system
    await system.init()
    
    yield system
    
    # Cleanup
    await system.close()
    
    # Remove test storage directory
    import shutil
    if os.path.exists(config.storage_path):
        shutil.rmtree(config.storage_path)


@pytest.fixture(scope="function")
async def test_user(chat_system):
    """Create a test user."""
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        password="Password123!",
        full_name="Test User"
    )
    
    return await chat_system.register_user(user_data)


@pytest.fixture(scope="function")
async def second_user(chat_system):
    """Create a second test user."""
    user_data = UserCreate(
        username="seconduser",
        email="second@example.com",
        password="Password456!",
        full_name="Second User"
    )
    
    return await chat_system.register_user(user_data)


@pytest.fixture(scope="function")
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
    # Mock the get_user_by_username method to return a user
    chat_system.db_handler.get_user_by_username = AsyncMock(return_value=user)
    
    with pytest.raises(AuthenticationError):
        await chat_system.register_user(user_data)


@pytest.mark.asyncio
async def test_user_authentication(chat_system, test_user):
    """Test user authentication functionality."""
    # Mock get_user_by_username to return the test user
    chat_system.db_handler.get_user_by_username = AsyncMock(return_value=test_user)
    
    # Mock verify_password to return True for valid password
    chat_system.security_manager.verify_password = AsyncMock(side_effect=lambda p, h: p == "Password123!")
    
    # Test valid authentication
    token = await chat_system.authenticate_user(test_user.username, "Password123!")
    assert token is not None
    
    # Test invalid password
    with pytest.raises(AuthenticationError):
        await chat_system.authenticate_user(test_user.username, "WrongPassword")
    
    # Test invalid username
    chat_system.db_handler.get_user_by_username = AsyncMock(return_value=None)
    with pytest.raises(AuthenticationError):
        await chat_system.authenticate_user("nonexistentuser", "Password123!")


@pytest.mark.asyncio
async def test_user_update(chat_system, test_user):
    """Test user update functionality."""
    # Mock get_user to return the test user
    chat_system.db_handler.get_user = AsyncMock(return_value=test_user)
    
    # Update user information
    update_data = UserUpdate(
        full_name="Updated User Name",
        email="updated@example.com"
    )
    
    # Mock update_user to return an updated user
    updated_user = test_user.copy()
    updated_user.full_name = "Updated User Name"
    updated_user.email = "updated@example.com"
    chat_system.db_handler.update_user = AsyncMock(return_value=updated_user)
    
    result = await chat_system.update_user(test_user.id, update_data)
    
    # Check if user was updated correctly
    assert result is not None
    assert result.id == test_user.id
    assert result.full_name == "Updated User Name"
    assert result.email == "updated@example.com"
    assert result.username == test_user.username  # Username should remain unchanged


@pytest.mark.asyncio
async def test_user_status(chat_system, test_user):
    """Test user status update functionality."""
    # Mock get_user to return the test user
    chat_system.db_handler.get_user = AsyncMock(return_value=test_user)
    
    # Mock update_user to return an updated user with status
    updated_user = test_user.copy()
    updated_user.status = "away"
    chat_system.db_handler.update_user = AsyncMock(return_value=updated_user)
    
    # Update user status
    result = await chat_system.update_user_status(test_user.id, "away")
    
    # Check if status was updated correctly
    assert result is not None
    assert result.status == "away"


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
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Update chat information
    update_data = ChatUpdate(
        name="Updated Chat Name",
        description="Updated description"
    )
    
    # Mock update_chat to return an updated chat
    updated_chat = test_chat.copy()
    updated_chat.name = "Updated Chat Name"
    updated_chat.description = "Updated description"
    chat_system.db_handler.update_chat = AsyncMock(return_value=updated_chat)
    
    result = await chat_system.update_chat(test_chat.id, test_user.id, update_data)
    
    # Check if chat was updated correctly
    assert result is not None
    assert result.id == test_chat.id
    assert result.name == "Updated Chat Name"
    assert result.description == "Updated description"


@pytest.mark.asyncio
async def test_chat_membership(chat_system, test_user, second_user, test_chat):
    """Test chat membership functionality."""
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Mock add_chat_member to return True
    chat_system.db_handler.add_chat_member = AsyncMock(return_value=True)
    
    # Add second user to chat
    result = await chat_system.add_chat_member(test_chat.id, test_user.id, second_user.id)
    assert result is True
    
    # Update mock to show second user is a member
    updated_chat = test_chat.copy()
    updated_chat.add_member(second_user.id)
    chat_system.db_handler.get_chat = AsyncMock(return_value=updated_chat)
    
    # Check if second user can access the chat
    chat = await chat_system.get_chat(test_chat.id, second_user.id)
    assert chat is not None
    assert chat.is_member(second_user.id)
    
    # Mock remove_chat_member to return True
    chat_system.db_handler.remove_chat_member = AsyncMock(return_value=True)
    
    # Remove second user from chat
    result = await chat_system.remove_chat_member(test_chat.id, test_user.id, second_user.id)
    assert result is True
    
    # Update mock to show second user is removed
    updated_chat = test_chat.copy()  # Original without second user
    chat_system.db_handler.get_chat = AsyncMock(return_value=updated_chat)
    
    # Check if second user was removed correctly
    chat = await chat_system.get_chat(test_chat.id, test_user.id)
    assert not chat.is_member(second_user.id)
    
    # Second user should no longer be able to access the chat
    with pytest.raises(AuthorizationError):
        await chat_system.get_chat(test_chat.id, second_user.id)


@pytest.mark.asyncio
async def test_message_sending(chat_system, test_user, test_chat):
    """Test message sending functionality."""
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Send a text message
    message_data = MessageCreate(
        chat_id=test_chat.id,
        content="Hello, world!",
        message_type=MessageType.TEXT
    )
    
    # Create a test message
    test_message = Message(
        id=str(uuid4()),
        chat_id=test_chat.id,
        sender_id=test_user.id,
        content="Hello, world!",
        message_type=MessageType.TEXT,
        status=MessageStatus.SENT,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Mock create_message to return the test message
    chat_system.db_handler.create_message = AsyncMock(return_value=test_message)
    
    message = await chat_system.send_message(test_user.id, message_data)
    
    # Check if message was sent correctly
    assert message is not None
    assert message.id is not None
    assert message.chat_id == test_chat.id
    assert message.sender_id == test_user.id
    assert message.content == "Hello, world!"
    assert message.message_type == MessageType.TEXT
    
    # Mock get_chat_messages to return a list with the test message
    chat_system.db_handler.get_chat_messages = AsyncMock(return_value=[test_message])
    
    # Get messages for the chat
    messages = await chat_system.get_chat_messages(test_chat.id, test_user.id)
    assert len(messages) == 1
    assert messages[0].id == message.id


@pytest.mark.asyncio
async def test_message_update(chat_system, test_user, test_chat):
    """Test message update functionality."""
    # Create a test message
    test_message = Message(
        id=str(uuid4()),
        chat_id=test_chat.id,
        sender_id=test_user.id,
        content="Original message",
        message_type=MessageType.TEXT,
        status=MessageStatus.SENT,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Mock get_message to return the test message
    chat_system.db_handler.get_message = AsyncMock(return_value=test_message)
    
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Update the message
    update_data = MessageUpdate(
        content="Updated message"
    )
    
    # Create an updated message
    updated_message = test_message.copy()
    updated_message.content = "Updated message"
    updated_message.edited_at = datetime.now()
    
    # Mock update_message to return the updated message
    chat_system.db_handler.update_message = AsyncMock(return_value=updated_message)
    
    result = await chat_system.update_message(test_message.id, test_user.id, update_data)
    
    # Check if message was updated correctly
    assert result is not None
    assert result.id == test_message.id
    assert result.content == "Updated message"
    assert result.edited_at is not None


@pytest.mark.asyncio
async def test_message_deletion(chat_system, test_user, test_chat):
    """Test message deletion functionality."""
    # Create a test message
    test_message = Message(
        id=str(uuid4()),
        chat_id=test_chat.id,
        sender_id=test_user.id,
        content="Message to be deleted",
        message_type=MessageType.TEXT,
        status=MessageStatus.SENT,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Mock get_message to return the test message
    chat_system.db_handler.get_message = AsyncMock(return_value=test_message)
    
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Mock delete_message to return True
    chat_system.db_handler.delete_message = AsyncMock(return_value=True)
    
    # Delete the message for everyone
    result = await chat_system.delete_message(test_message.id, test_user.id, True)
    assert result is True
    
    # Mock get_chat_messages to return an empty list (no messages)
    chat_system.db_handler.get_chat_messages = AsyncMock(return_value=[])
    
    # Message should no longer be retrievable
    messages = await chat_system.get_chat_messages(test_chat.id, test_user.id)
    assert len(messages) == 0


@pytest.mark.asyncio
async def test_message_reactions(chat_system, test_user, second_user, test_chat):
    """Test message reactions functionality."""
    # Create a test message
    test_message = Message(
        id=str(uuid4()),
        chat_id=test_chat.id,
        sender_id=test_user.id,
        content="Message for reactions",
        message_type=MessageType.TEXT,
        status=MessageStatus.SENT,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        reactions=[]
    )
    
    # Mock get_message to return the test message
    chat_system.db_handler.get_message = AsyncMock(return_value=test_message)
    
    # Mock get_chat to return the test chat with both users as members
    updated_chat = test_chat.copy()
    updated_chat.add_member(second_user.id)
    chat_system.db_handler.get_chat = AsyncMock(return_value=updated_chat)
    
    # Create reactions
    from chatms_plugin.models.message import Reaction
    reaction1 = Reaction(
        id=str(uuid4()),
        user_id=test_user.id,
        reaction_type="👍",
        created_at=datetime.now()
    )
    
    reaction2 = Reaction(
        id=str(uuid4()),
        user_id=second_user.id,
        reaction_type="❤️",
        created_at=datetime.now()
    )
    
    # Mock add_reaction to return the reactions
    chat_system.db_handler.add_reaction = AsyncMock(side_effect=[reaction1, reaction2])
    
    # Add reactions
    result1 = await chat_system.add_reaction(test_message.id, test_user.id, "👍")
    assert result1 is not None
    
    result2 = await chat_system.add_reaction(test_message.id, second_user.id, "❤️")
    assert result2 is not None
    
    # Update test message with reactions
    test_message_with_reactions = test_message.copy()
    test_message_with_reactions.reactions = [reaction1, reaction2]
    chat_system.db_handler.get_message = AsyncMock(return_value=test_message_with_reactions)
    
    # Get message with reactions
    message = await chat_system.get_message(test_message.id, test_user.id)
    assert len(message.reactions) == 2
    
    # Mock remove_reaction to return True
    chat_system.db_handler.remove_reaction = AsyncMock(return_value=True)
    
    # Remove a reaction
    result = await chat_system.remove_reaction(test_message.id, test_user.id, "👍")
    assert result is True
    
    # Update test message with one reaction removed
    test_message_one_reaction = test_message.copy()
    test_message_one_reaction.reactions = [reaction2]
    chat_system.db_handler.get_message = AsyncMock(return_value=test_message_one_reaction)
    
    # Check if reaction was removed
    message = await chat_system.get_message(test_message.id, test_user.id)
    assert len(message.reactions) == 1
    assert message.reactions[0].user_id == second_user.id
    assert message.reactions[0].reaction_type == "❤️"


@pytest.mark.asyncio
async def test_message_pinning(chat_system, test_user, test_chat):
    """Test message pinning functionality."""
    # Create a test message
    test_message = Message(
        id=str(uuid4()),
        chat_id=test_chat.id,
        sender_id=test_user.id,
        content="Message to be pinned",
        message_type=MessageType.TEXT,
        status=MessageStatus.SENT,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        is_pinned=False
    )
    
    # Mock get_message to return the test message
    chat_system.db_handler.get_message = AsyncMock(return_value=test_message)
    
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Create a pinned message
    pinned_message = test_message.copy()
    pinned_message.is_pinned = True
    
    # Mock update_message to return the pinned message
    chat_system.db_handler.update_message = AsyncMock(return_value=pinned_message)
    
    # Pin the message
    result = await chat_system.pin_message(test_message.id, test_user.id)
    assert result is not None
    assert result.is_pinned is True
    
    # Mock get_pinned_messages to return a list with the pinned message
    chat_system.db_handler.list = AsyncMock(return_value=[pinned_message.dict()])
    
    # Get pinned messages
    pinned_messages = await chat_system.get_pinned_messages(test_chat.id, test_user.id)
    assert len(pinned_messages) == 1
    assert pinned_messages[0].id == test_message.id
    
    # Create an unpinned message
    unpinned_message = test_message.copy()
    unpinned_message.is_pinned = False
    
    # Mock update_message to return the unpinned message
    chat_system.db_handler.update_message = AsyncMock(return_value=unpinned_message)
    
    # Unpin the message
    result = await chat_system.unpin_message(test_message.id, test_user.id)
    assert result is not None
    assert result.is_pinned is False
    
    # Mock get_pinned_messages to return an empty list
    chat_system.db_handler.list = AsyncMock(return_value=[])
    
    # Check if message was unpinned
    pinned_messages = await chat_system.get_pinned_messages(test_chat.id, test_user.id)
    assert len(pinned_messages) == 0


@pytest.mark.asyncio
async def test_read_receipts(chat_system, test_user, second_user, test_chat):
    """Test read receipts functionality."""
    # Create test messages
    test_messages = []
    for i in range(3):
        message = Message(
            id=str(uuid4()),
            chat_id=test_chat.id,
            sender_id=test_user.id,
            content=f"Message {i}",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        test_messages.append(message)
    
    # Mock get_chat to return the test chat with both users as members
    updated_chat = test_chat.copy()
    updated_chat.add_member(second_user.id)
    chat_system.db_handler.get_chat = AsyncMock(return_value=updated_chat)
    
    # Mock get_message to return the first message
    chat_system.db_handler.get_message = AsyncMock(return_value=test_messages[0])
    
    # Mock update_message to return the message with read status
    read_message = test_messages[0].copy()
    read_message.status = MessageStatus.READ
    read_message.read_at = datetime.now()
    chat_system.db_handler.update_message = AsyncMock(return_value=read_message)
    
    # Mark specific message as read
    result = await chat_system.mark_messages_read(
        chat_id=test_chat.id,
        user_id=second_user.id,
        message_ids=[test_messages[0].id]
    )
    assert result is True
    
    # Mock get_chat_messages to return messages before the last message
    chat_system.db_handler.get_chat_messages = AsyncMock(return_value=test_messages[:-1])
    
    # Mock get_message to return the last message
    chat_system.db_handler.get_message = AsyncMock(return_value=test_messages[-1])
    
    # Mark all messages up to a point as read
    result = await chat_system.mark_messages_read(
        chat_id=test_chat.id,
        user_id=second_user.id,
        read_until_id=test_messages[-1].id
    )
    assert result is True


@pytest.mark.asyncio
async def test_typing_indicator(chat_system, test_user, test_chat):
    """Test typing indicator functionality."""
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Mock update_chat to return the updated chat
    chat_system.db_handler.update_chat = AsyncMock(return_value=test_chat)
    
    # Send typing indicator
    result = await chat_system.send_typing_indicator(test_chat.id, test_user.id, True)
    assert result is True
    
    # Stop typing indicator
    result = await chat_system.send_typing_indicator(test_chat.id, test_user.id, False)
    assert result is True


@pytest.mark.asyncio
async def test_chat_deletion(chat_system, test_user, test_chat):
    """Test chat deletion functionality."""
    # Mock get_chat to return the test chat
    chat_system.db_handler.get_chat = AsyncMock(return_value=test_chat)
    
    # Mock delete_chat to return True
    chat_system.db_handler.delete_chat = AsyncMock(return_value=True)
    
    # Delete the chat
    result = await chat_system.delete_chat(test_chat.id, test_user.id)
    assert result is True
    
    # Mock get_chat to return None (deleted)
    chat_system.db_handler.get_chat = AsyncMock(return_value=None)
    
    # User shouldn't be able to access the chat anymore
    chat = await chat_system.get_chat(test_chat.id, test_user.id)
    assert chat is None