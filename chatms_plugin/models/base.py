"""
Base model classes for the ChatMS plugin.
"""

import datetime
import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class ChatMSModel(BaseModel):
    """Base model for all ChatMS models."""
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v),
        }
        orm_mode = True


class TimestampedModel(ChatMSModel):
    """Base model with created_at and updated_at timestamps."""
    
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: Optional[datetime.datetime] = None

    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.datetime.now()
        return self


class IdentifiedModel(TimestampedModel):
    """Base model with ID and timestamps."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    @validator("id", pre=True, always=True)
    def ensure_id_is_str(cls, v):
        """Ensure ID is a string."""
        if isinstance(v, uuid.UUID):
            return str(v)
        return v


class DatabaseModel(IdentifiedModel):
    """Base model for database models with serialization/deserialization methods."""
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary.
        
        Override this method in subclasses if needed.
        """
        return {
            k: v.isoformat() if isinstance(v, datetime.datetime) else v
            for k, v in self.dict().items()
        }
    
    @classmethod
    def from_db_dict(cls, data: Dict[str, Any]) -> "DatabaseModel":
        """Create model from database dictionary.
        
        Override this method in subclasses if needed.
        """
        # Convert string timestamps to datetime objects
        for field_name, field in cls.__fields__.items():
            if field.type_ == datetime.datetime and field_name in data and isinstance(data[field_name], str):
                try:
                    data[field_name] = datetime.datetime.fromisoformat(data[field_name])
                except ValueError:
                    pass
        
        return cls(**data)