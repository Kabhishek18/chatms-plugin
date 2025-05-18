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
## Integration with FastAPI
### ChatMS can be easily integrated with FastAPI applications:
```python
import uvicorn
from fastapi import FastAPI
from chatms_plugin import ChatSystem, Config
from chatms_plugin.api.rest import RestAPI
from chatms_plugin.api.websocket import WebSocketAPI
from chatms_plugin.api.middlewares import setup_middlewares

# Create FastAPI app
app = FastAPI(title="Chat App", description="Real-time chat application")

# Create chat system
config = Config(
    database_url="postgresql://user:password@localhost/chatdb",
    storage_type="local",
    storage_path="./file_storage"
)
chat_system = ChatSystem(config)

# Set up API and middlewares
@app.on_event("startup")
async def startup_event():
    await chat_system.init()
    
    # Set up REST API
    rest_api = RestAPI(chat_system)
    rest_api.register_to_app(app, prefix="/api")
    
    # Set up WebSocket API
    websocket_api = WebSocketAPI(chat_system, app)
    
    # Set up middlewares
    setup_middlewares(app, chat_system, config)

@app.on_event("shutdown")
async def shutdown_event():
    await chat_system.close()

# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

```


## Integration with Django
### ChatMS can be easily integrated with Django applications:

```python
# In your Django settings.py
CHATMS_CONFIG = {
    'database_type': 'postgresql',
    'database_url': 'postgresql://user:password@localhost/chatdb',
    'storage_type': 'local',
    'storage_path': os.path.join(BASE_DIR, 'media', 'chat_files'),
    'jwt_secret': SECRET_KEY,
    'jwt_expiration_minutes': 60,
    'enable_encryption': True,
    'encryption_key': 'your-secure-encryption-key',
}

# In your Django apps.py
from django.apps import AppConfig

class ChatMSConfig(AppConfig):
    name = 'chatms_integration'
    verbose_name = 'Chat Messaging System'
    
    def ready(self):
        from chatms_plugin import ChatSystem, Config
        from chatms_plugin.api.django import setup_django_integration
        from django.conf import settings
        
        # Create config from Django settings
        config = Config(**settings.CHATMS_CONFIG)
        
        # Initialize chat system
        import asyncio
        loop = asyncio.new_event_loop()
        
        chat_system = ChatSystem(config)
        loop.run_until_complete(chat_system.init())
        
        # Store chat system in app config
        self.chat_system = chat_system
        
        # Set up Django integration
        self.rest_api, self.channels_api = setup_django_integration(chat_system)

# In your Django urls.py
from django.urls import path, include
from .apps import ChatMSConfig

urlpatterns = [
    # ... other URL patterns ...
    path('api/chat/', include(ChatMSConfig.rest_api.get_urls())),
]

# In your Django asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from .apps import ChatMSConfig

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')

# Get WebSocket consumer
consumer = ChatMSConfig.channels_api.get_consumer()

# Define WebSocket URL patterns
websocket_urlpatterns = [
    path('ws//', consumer.as_asgi()),
]

# Configure ASGI application
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

## Core Concepts
### Users
#### Users are the entities that interact with the chat system. Each user has a unique ID, username, and password. Users can join chats, send messages, and receive notifications.
```python
# Create a user
user = await chat_system.register_user(
    username="user1",
    email="user1@example.com",
    password="securepassword"
)

# Authenticate a user
token = await chat_system.authenticate_user(
    username="user1",
    password="securepassword"
)

# Update user status
await chat_system.update_user_status(user_id, "online")
```


## Chats
#### Chats are the conversations between users. They can be one-to-one chats, group chats, or broadcast channels.

```python
# Create a one-to-one chat
chat = await chat_system.create_chat(
    creator_id=user_id,
    member_ids=[user_id, other_user_id],
    chat_type="one_to_one"
)

# Create a group chat
chat = await chat_system.create_chat(
    creator_id=user_id,
    name="Team Chat",
    member_ids=[user_id, user2_id, user3_id],
    chat_type="group"
)

# Add a member to a chat
await chat_system.add_chat_member(chat_id, admin_id, new_member_id)
```
## Messages
#### Messages are the content sent in chats. They can be text, emoji, files, images, videos, or voice notes.

```python
# Send a text message
message = await chat_system.send_message(
    sender_id=user_id,
    message_data=MessageCreate(
        chat_id=chat_id,
        content="Hello, world!",
        message_type="text"
    )
)

# Send a file message
file_url = await chat_system.upload_file(
    chat_id=chat_id,
    user_id=user_id,
    file_data=file_content,
    file_name="example.jpg",
    content_type="image/jpeg"
)

message = await chat_system.send_file_message(
    sender_id=user_id,
    chat_id=chat_id,
    file_url=file_url,
    file_name="example.jpg",
    content_type="image/jpeg",
    caption="Check out this photo!"
)

# Add a reaction to a message
await chat_system.add_reaction(
    message_id=message_id,
    user_id=user_id,
    reaction_type="👍"
)
```

## Real-time Features
#### ChatMS supports real-time features such as typing indicators, read receipts, and presence indicators.

```python
# Send typing indicator
await chat_system.send_typing_indicator(
    chat_id=chat_id,
    user_id=user_id,
    is_typing=True
)

# Mark messages as read
await chat_system.mark_messages_read(
    chat_id=chat_id,
    user_id=user_id,
    read_until_id=last_message_id
)
```

## Configuration
### ChatMS is highly configurable. You can customize database connections, storage options, security settings, and more.

```python
# Create a configuration
config = Config(
    # Database configuration
    database_type="postgresql",
    database_url="postgresql://user:password@localhost/chatdb",
    
    # Storage configuration
    storage_type="s3",
    storage_credentials={
        "aws_access_key_id": "your_access_key",
        "aws_secret_access_key": "your_secret_key",
        "region_name": "us-west-2"
    },
    storage_bucket="your-bucket-name",
    
    # Security configuration
    jwt_secret="your-secret-key",
    jwt_expiration_minutes=60,
    enable_encryption=True,
    
    # Rate limiting
    rate_limit_messages_per_minute=60,
    
    # Notification configuration
    enable_push_notifications=True,
    fcm_api_key="your-fcm-api-key"
)
```

## Advanced Features
### End-to-End Encryption
#### ChatMS supports end-to-end encryption for secure messaging.

```python
# Create an encrypted chat
chat = await chat_system.create_chat(
    creator_id=user_id,
    member_ids=[user_id, other_user_id],
    chat_type="one_to_one",
    is_encrypted=True
)
```
## File Storage
#### ChatMS supports various file storage options, including local filesystem, AWS S3, Google Cloud Storage, and Azure Blob.

```python
# Upload a file
file_url = await chat_system.upload_file(
    chat_id=chat_id,
    user_id=user_id,
    file_data=file_content,
    file_name="example.jpg",
    content_type="image/jpeg"
)

# Create a thumbnail
thumbnail_url = await chat_system.storage_handler.create_thumbnail(
    file_path=file_url,
    width=200,
    height=200
)
```
## Analytics
#### ChatMS includes comprehensive analytics for tracking usage and performance.

```python
# Get chat statistics
stats = await chat_system.get_chat_stats(chat_id, user_id)

# Get user statistics
stats = await chat_system.get_user_stats(user_id)
```

## Documentation

For complete documentation, see the [official docs](https://chatms-plugin.readthedocs.io/).

## API Reference
For complete API documentation, see the API Reference.

Examples
Check out the examples directory for:

Simple server implementation
Chat client example
Configuration examples for different environments

Contributing
Contributions are welcome! Please feel free to submit a Pull Request.


## License

This project is licensed under the MIT License - see the LICENSE file for details.