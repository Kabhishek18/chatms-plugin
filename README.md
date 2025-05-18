# ChatMS - Chat Messaging System Plugin

A comprehensive chat messaging system plugin for Python applications with support for various chat types, message formats, and deployment options.

## Features

### Core Capabilities
- **Multiple Message Types**: Text, emoji, files, images, video, voice notes, reactions
- **Flexible Chat Types**: One-to-one chats, group chats, broadcast channels
- **Real-time Communication**: WebSocket-based messaging with typing indicators and read receipts
- **Rich Message Features**: Edit, delete, pin, quote, forward, and react to messages

### Technical Features
- **Flexible Storage**: Support for local, AWS S3, Google Cloud Storage, and Azure Blob
- **Database Options**: PostgreSQL and MongoDB support
- **Security**: JWT/OAuth2 authentication, end-to-end encryption, rate limiting
- **Notifications**: Push notifications via FCM/APNs, email alerts
- **Analytics**: Usage metrics and performance tracking
- **Extensibility**: Middleware hooks for customization

## Installation

```bash
pip install chatms-plugin
```

## Quick Start

```python
import asyncio
from chatms_plugin import ChatSystem, Config

# Create a configuration
config = Config(
    database_url="postgresql://user:password@localhost/chatdb",
    storage_type="local",
    storage_path="./file_storage"
)

# Initialize the chat system
async def main():
    chat_system = ChatSystem(config)
    await chat_system.init()
    
    # Create a user
    user = await chat_system.register_user(
        username="user1",
        email="user1@example.com",
        password="securepassword"
    )
    
    # Create a chat
    chat = await chat_system.create_chat(
        creator_id=user.id,
        name="Test Chat",
        chat_type="group"
    )
    
    # Send a message
    message = await chat_system.send_message(
        sender_id=user.id,
        chat_id=chat.id,
        content="Hello, world!"
    )
    
    # Clean up
    await chat_system.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Documentation

For complete documentation, see the [official docs](https://chatms-plugin.readthedocs.io/).

## Examples

Check out the examples directory for:
- Simple server implementation
- Chat client example
- Configuration examples for different environments

## License

This project is licensed under the MIT License - see the LICENSE file for details.