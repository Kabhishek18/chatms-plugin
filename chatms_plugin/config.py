"""
Configuration management for the ChatMS plugin.
Loads and validates configuration from environment variables and configuration files.
"""

import os
import json
import enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

import dotenv
from pydantic import BaseModel, Field, validator, root_validator

# Load environment variables
dotenv.load_dotenv()


class StorageType(str, enum.Enum):
    """Storage type enum for file storage options."""
    LOCAL = "local"
    S3 = "s3"
    GCP = "gcp"
    AZURE = "azure"


class DatabaseType(str, enum.Enum):
    """Database type enum for database options."""
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    SQLITE = "sqlite"  # For testing


class MessageStatus(str, enum.Enum):
    """Message status enum for tracking message delivery."""
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageType(str, enum.Enum):
    """Message type enum for different types of messages."""
    TEXT = "text"
    EMOJI = "emoji"
    FILE = "file"
    IMAGE = "image"
    VIDEO = "video"
    VOICE = "voice"
    REACTION = "reaction"


class ChatType(str, enum.Enum):
    """Chat type enum for different types of chats."""
    ONE_TO_ONE = "one_to_one"
    GROUP = "group"
    BROADCAST = "broadcast"
    NON_BROADCAST = "non_broadcast"


class UserRole(str, enum.Enum):
    """User role enum for different roles in a chat."""
    ADMIN = "admin"
    MEMBER = "member"
    MODERATOR = "moderator"


class Config(BaseModel):
    """Configuration class for the chat system.
    
    This class handles loading configuration from environment variables,
    configuration files, and default values. It also validates and transforms
    configuration values as needed.
    """
    
    # Database configuration
    database_type: DatabaseType = Field(
        default=DatabaseType.POSTGRESQL,
        description="The type of database to use"
    )
    database_url: str = Field(
        default="postgresql://user:password@localhost/chatms",
        description="The database connection URL"
    )
    
    # Storage configuration
    storage_type: StorageType = Field(
        default=StorageType.LOCAL,
        description="The type of storage to use for files"
    )
    storage_path: Optional[str] = Field(
        default="./storage",
        description="The path to the local storage directory (if using local storage)"
    )
    storage_credentials: Optional[Dict[str, str]] = Field(
        default=None,
        description="Credentials for cloud storage (if using cloud storage)"
    )
    storage_bucket: Optional[str] = Field(
        default=None,
        description="Cloud storage bucket name (if using cloud storage)"
    )
    
    # File handling configuration
    max_file_size_mb: int = Field(
        default=10,
        description="Maximum file size in megabytes"
    )
    allowed_extensions: List[str] = Field(
        default=["jpg", "png", "pdf", "docx", "mp4", "mp3"],
        description="List of allowed file extensions"
    )
    enable_virus_scan: bool = Field(
        default=False,
        description="Whether to enable virus scanning for uploaded files"
    )
    virus_scan_api_key: Optional[str] = Field(
        default=None,
        description="API key for virus scanning service (if enabled)"
    )
    
    # Encryption configuration
    enable_encryption: bool = Field(
        default=True,
        description="Whether to enable message encryption"
    )
    encryption_key: Optional[str] = Field(
        default=None,
        description="Key for message encryption (if enabled)"
    )
    
    # Authentication configuration
    jwt_secret: str = Field(
        default="your-secret-key",
        description="Secret key for JWT token generation"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algorithm for JWT token generation"
    )
    jwt_expiration_minutes: int = Field(
        default=60,
        description="JWT token expiration time in minutes"
    )
    
    # WebSocket configuration
    websocket_ping_interval: int = Field(
        default=30,
        description="WebSocket ping interval in seconds"
    )
    
    # Redis configuration for real-time features
    redis_url: str = Field(
        default="redis://localhost",
        description="Redis connection URL"
    )
    
    # Notification configuration
    enable_push_notifications: bool = Field(
        default=False,
        description="Whether to enable push notifications"
    )
    fcm_api_key: Optional[str] = Field(
        default=None,
        description="Firebase Cloud Messaging API key (if enabled)"
    )
    apns_key_file: Optional[str] = Field(
        default=None,
        description="Apple Push Notification Service key file path (if enabled)"
    )
    
    # Rate limiting
    rate_limit_messages_per_minute: int = Field(
        default=60,
        description="Maximum number of messages per minute per user"
    )
    
    # Content moderation
    enable_content_moderation: bool = Field(
        default=False,
        description="Whether to enable content moderation"
    )
    content_moderation_hook: Optional[str] = Field(
        default=None,
        description="URL for content moderation webhook (if enabled)"
    )
    
    # Analytics
    enable_analytics: bool = Field(
        default=False,
        description="Whether to enable analytics"
    )
    analytics_provider: Optional[str] = Field(
        default=None,
        description="Analytics provider (if enabled)"
    )
    
    class Config:
        """Pydantic configuration."""
        env_prefix = "CHATMS_"
        case_sensitive = False
        validate_assignment = True

    @validator("storage_credentials", pre=True)
    def parse_storage_credentials(cls, v):
        """Parse storage credentials from string to dict."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in storage_credentials")
        return v

    @validator("allowed_extensions", pre=True)
    def parse_allowed_extensions(cls, v):
        """Parse allowed extensions from comma-separated string to list."""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @validator("encryption_key", pre=True, always=True)
    def validate_encryption_key(cls, v, values):
        """Generate a random encryption key if not provided and encryption is enabled."""
        if values.get("enable_encryption", True) and not v:
            import os
            return os.urandom(32).hex()
        return v

    @validator("jwt_secret", pre=True, always=True)
    def validate_jwt_secret(cls, v):
        """Generate a random JWT secret if not provided or using default."""
        if not v or v == "your-secret-key":
            import os
            return os.urandom(32).hex()
        return v

    @root_validator(pre=True)
    def load_from_env(cls, values):
        """Load configuration from environment variables."""
        for field in cls.__fields__:
            env_var = f"CHATMS_{field.upper()}"
            if env_var in os.environ and env_var not in values:
                values[field] = os.environ[env_var]
        return values
    
    @classmethod
    def from_file(cls, file_path: Union[str, Path]):
        """Load configuration from a file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        # Load based on file extension
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            with open(file_path, "r") as f:
                config_data = json.load(f)
            return cls(**config_data)
        elif suffix in (".py", ".pyc"):
            import importlib.util
            spec = importlib.util.spec_from_file_location("config_module", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            config_data = {k: v for k, v in module.__dict__.items() 
                          if not k.startswith("__") and not callable(v)}
            return cls(**config_data)
        else:
            raise ValueError(f"Unsupported config file format: {suffix}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary."""
        return self.dict()

    def to_json(self) -> str:
        """Convert configuration to a JSON string."""
        return self.json(indent=2)

    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save configuration to a file."""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        
        if suffix == ".json":
            with open(file_path, "w") as f:
                f.write(self.to_json())
        elif suffix == ".py":
            config_dict = self.to_dict()
            with open(file_path, "w") as f:
                f.write("# ChatMS Plugin Configuration\n\n")
                for key, value in config_dict.items():
                    f.write(f"{key} = {repr(value)}\n")
        else:
            raise ValueError(f"Unsupported config file format: {suffix}")