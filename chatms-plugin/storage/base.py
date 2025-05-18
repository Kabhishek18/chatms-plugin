"""
Abstract storage interface for the ChatMS plugin.
"""

import abc
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, BinaryIO, Union

from ..exceptions import FileError, FileSizeError, FileTypeError


class StorageHandler(abc.ABC):
    """Abstract base class for storage handlers.
    
    This defines the interface that all storage implementations must follow.
    """
    
    @abc.abstractmethod
    async def init(self) -> None:
        """Initialize the storage connection."""
        pass
    
    @abc.abstractmethod
    async def close(self) -> None:
        """Close the storage connection."""
        pass
    
    @abc.abstractmethod
    async def save_file(self, file_data: bytes, file_name: str, 
                        content_type: Optional[str] = None) -> str:
        """Save a file and return its URL or path.
        
        Args:
            file_data: The file data as bytes
            file_name: The original file name
            content_type: The MIME type of the file, if known
            
        Returns:
            str: The URL or path where the file can be accessed
            
        Raises:
            FileError: If there was an error saving the file
        """
        pass
    
    @abc.abstractmethod
    async def get_file(self, file_path: str) -> Optional[bytes]:
        """Get a file by its path or URL.
        
        Args:
            file_path: The path or URL of the file
            
        Returns:
            Optional[bytes]: The file data, or None if not found
            
        Raises:
            FileError: If there was an error retrieving the file
        """
        pass
    
    @abc.abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file by its path or URL.
        
        Args:
            file_path: The path or URL of the file
            
        Returns:
            bool: True if the file was deleted, False otherwise
            
        Raises:
            FileError: If there was an error deleting the file
        """
        pass
    
    @abc.abstractmethod
    async def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a file.
        
        Args:
            file_path: The path or URL of the file
            
        Returns:
            Optional[Dict[str, Any]]: Information about the file, or None if not found
            
        Raises:
            FileError: If there was an error getting the file information
        """
        pass
    
    @abc.abstractmethod
    async def get_file_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a URL for a file that can be used to access it.
        
        Args:
            file_path: The path of the file
            expires_in: The number of seconds the URL should be valid for
            
        Returns:
            str: The URL where the file can be accessed
            
        Raises:
            FileError: If there was an error generating the URL
        """
        pass
    
    @abc.abstractmethod
    async def create_thumbnail(self, file_path: str, width: int, height: int) -> Optional[str]:
        """Create a thumbnail for an image or video.
        
        Args:
            file_path: The path or URL of the file
            width: The desired width of the thumbnail
            height: The desired height of the thumbnail
            
        Returns:
            Optional[str]: The path or URL of the thumbnail, or None if not possible
            
        Raises:
            FileError: If there was an error creating the thumbnail
        """
        pass
    
    async def validate_file(self, file_data: bytes, file_name: str, 
                          max_size_mb: int, allowed_extensions: List[str]) -> None:
        """Validate a file.
        
        Args:
            file_data: The file data as bytes
            file_name: The original file name
            max_size_mb: The maximum allowed file size in MB
            allowed_extensions: List of allowed file extensions
            
        Raises:
            FileSizeError: If the file is too large
            FileTypeError: If the file type is not allowed
        """
        # Check file size
        file_size = len(file_data)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            raise FileSizeError(
                file_name=file_name,
                file_size=file_size,
                max_size=max_size_bytes
            )
        
        # Check file extension
        _, ext = os.path.splitext(file_name)
        ext = ext.lstrip(".").lower()
        
        if allowed_extensions and ext not in allowed_extensions:
            raise FileTypeError(
                file_name=file_name,
                file_type=ext,
                allowed_types=allowed_extensions
            )
    
    def get_content_type(self, file_name: str) -> str:
        """Get the MIME type of a file based on its name.
        
        Args:
            file_name: The file name
            
        Returns:
            str: The MIME type, or 'application/octet-stream' if unknown
        """
        content_type, _ = mimetypes.guess_type(file_name)
        return content_type or "application/octet-stream"