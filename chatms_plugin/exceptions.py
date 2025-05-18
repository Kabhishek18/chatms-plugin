"""
Custom exceptions for the ChatMS plugin.
"""

class ChatMSError(Exception):
    """Base exception for all ChatMS errors."""
    
    def __init__(self, message: str = None, *args, **kwargs):
        self.message = message or "An error occurred in the ChatMS system"
        super().__init__(self.message, *args, **kwargs)


class ConfigurationError(ChatMSError):
    """Raised when there is an error in the configuration."""
    
    def __init__(self, message: str = None, *args, **kwargs):
        self.message = message or "Invalid configuration"
        super().__init__(self.message, *args, **kwargs)


class DatabaseError(ChatMSError):
    """Raised when there is a database error."""
    
    def __init__(self, message: str = None, *args, **kwargs):
        self.message = message or "Database error"
        super().__init__(self.message, *args, **kwargs)


class StorageError(ChatMSError):
    """Raised when there is a storage error."""
    
    def __init__(self, message: str = None, *args, **kwargs):
        self.message = message or "Storage error"
        super().__init__(self.message, *args, **kwargs)


class AuthenticationError(ChatMSError):
    """Raised when there is an authentication error."""
    
    def __init__(self, message: str = None, *args, **kwargs):
        self.message = message or "Authentication error"
        super().__init__(self.message, *args, **kwargs)


class AuthorizationError(ChatMSError):
    """Raised when there is an authorization error."""
    
    def __init__(self, message: str = None, *args, **kwargs):
        self.message = message or "Authorization error"
        super().__init__(self.message, *args, **kwargs)


class ValidationError(ChatMSError):
    """Raised when there is a validation error."""
    
    def __init__(self, message: str = None, field: str = None, *args, **kwargs):
        self.field = field
        if field:
            self.message = message or f"Validation error in field: {field}"
        else:
            self.message = message or "Validation error"
        super().__init__(self.message, *args, **kwargs)


class RateLimitError(ChatMSError):
    """Raised when a rate limit is exceeded."""
    
    def __init__(self, message: str = None, reset_time: int = None, *args, **kwargs):
        self.reset_time = reset_time
        self.message = message or "Rate limit exceeded"
        super().__init__(self.message, *args, **kwargs)


class FileError(ChatMSError):
    """Raised when there is an error with a file."""
    
    def __init__(self, message: str = None, file_name: str = None, *args, **kwargs):
        self.file_name = file_name
        if file_name:
            self.message = message or f"Error with file: {file_name}"
        else:
            self.message = message or "File error"
        super().__init__(self.message, *args, **kwargs)


class FileSizeError(FileError):
    """Raised when a file exceeds the maximum allowed size."""
    
    def __init__(self, file_name: str = None, file_size: int = None, max_size: int = None, *args, **kwargs):
        self.file_size = file_size
        self.max_size = max_size
        
        if file_name and file_size and max_size:
            message = f"File '{file_name}' size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
        elif file_size and max_size:
            message = f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
        else:
            message = "File size exceeds maximum allowed size"
            
        super().__init__(message=message, file_name=file_name, *args, **kwargs)


class FileTypeError(FileError):
    """Raised when a file has an unsupported type/extension."""
    
    def __init__(self, file_name: str = None, file_type: str = None, allowed_types: list = None, *args, **kwargs):
        self.file_type = file_type
        self.allowed_types = allowed_types
        
        if file_name and file_type and allowed_types:
            message = f"File '{file_name}' type '{file_type}' is not supported. Allowed types: {', '.join(allowed_types)}"
        elif file_type and allowed_types:
            message = f"File type '{file_type}' is not supported. Allowed types: {', '.join(allowed_types)}"
        else:
            message = "File type not supported"
            
        super().__init__(message=message, file_name=file_name, *args, **kwargs)


class MessageError(ChatMSError):
    """Raised when there is an error with a message."""
    
    def __init__(self, message: str = None, message_id: str = None, *args, **kwargs):
        self.message_id = message_id
        if message_id:
            self.message = message or f"Error with message: {message_id}"
        else:
            self.message = message or "Message error"
        super().__init__(self.message, *args, **kwargs)


class ChatError(ChatMSError):
    """Raised when there is an error with a chat."""
    
    def __init__(self, message: str = None, chat_id: str = None, *args, **kwargs):
        self.chat_id = chat_id
        if chat_id:
            self.message = message or f"Error with chat: {chat_id}"
        else:
            self.message = message or "Chat error"
        super().__init__(self.message, *args, **kwargs)


class UserError(ChatMSError):
    """Raised when there is an error with a user."""
    
    def __init__(self, message: str = None, user_id: str = None, *args, **kwargs):
        self.user_id = user_id
        if user_id:
            self.message = message or f"Error with user: {user_id}"
        else:
            self.message = message or "User error"
        super().__init__(self.message, *args, **kwargs)


class ConnectionError(ChatMSError):
    """Raised when there is an error with a connection."""
    
    def __init__(self, message: str = None, connection_id: str = None, *args, **kwargs):
        self.connection_id = connection_id
        if connection_id:
            self.message = message or f"Error with connection: {connection_id}"
        else:
            self.message = message or "Connection error"
        super().__init__(self.message, *args, **kwargs)


class NotificationError(ChatMSError):
    """Raised when there is an error with a notification."""
    
    def __init__(self, message: str = None, notification_id: str = None, *args, **kwargs):
        self.notification_id = notification_id
        if notification_id:
            self.message = message or f"Error with notification: {notification_id}"
        else:
            self.message = message or "Notification error"
        super().__init__(self.message, *args, **kwargs)