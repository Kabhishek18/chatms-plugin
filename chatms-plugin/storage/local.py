"""
Local filesystem storage handler for the ChatMS plugin.
"""

import asyncio
import logging
import mimetypes
import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, BinaryIO

import aiofiles
from PIL import Image

from ..config import Config
from ..exceptions import FileError, StorageError
from .base import StorageHandler


logger = logging.getLogger(__name__)


class LocalStorageHandler(StorageHandler):
    """Storage handler for local filesystem storage."""
    
    def __init__(self, config: Config):
        """Initialize the local storage handler.
        
        Args:
            config: Configuration object
        """
        super().__init__()
        self.config = config
        self.storage_path = config.storage_path
        self.base_path = None
    
    async def init(self) -> None:
        """Initialize the storage connection."""
        # Ensure the storage directory exists
        self.base_path = Path(self.storage_path).expanduser().resolve()
        
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Local storage initialized at {self.base_path}")
        except Exception as e:
            raise StorageError(f"Failed to initialize local storage: {e}")
    
    async def close(self) -> None:
        """Close the storage connection."""
        # Nothing to close for local storage
        pass
    
    async def save_file(self, file_data: bytes, file_name: str, 
                      content_type: Optional[str] = None) -> str:
        """Save a file and return its path.
        
        Args:
            file_data: The file data as bytes
            file_name: The original file name
            content_type: The MIME type of the file, if known
            
        Returns:
            str: The path where the file can be accessed
            
        Raises:
            FileError: If there was an error saving the file
        """
        try:
            # Ensure file_name is safe
            safe_name = self._sanitize_filename(file_name)
            
            # Generate unique directory structure based on date
            date_path = datetime.now().strftime("%Y/%m/%d")
            rel_dir_path = Path(date_path)
            abs_dir_path = self.base_path / rel_dir_path
            
            # Create directory if it doesn't exist
            abs_dir_path.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            file_uuid = str(uuid.uuid4())
            _, ext = os.path.splitext(safe_name)
            unique_name = f"{file_uuid}{ext}"
            
            # Full path to the file
            rel_file_path = rel_dir_path / unique_name
            abs_file_path = self.base_path / rel_file_path
            
            # Write file
            async with aiofiles.open(abs_file_path, "wb") as f:
                await f.write(file_data)
            
            logger.info(f"File saved: {abs_file_path}")
            
            # Return relative path as string
            return str(rel_file_path).replace("\\", "/")  # Use forward slashes for consistency
        
        except Exception as e:
            raise FileError(f"Failed to save file: {e}", file_name=file_name)
    
    async def get_file(self, file_path: str) -> Optional[bytes]:
        """Get a file by its path.
        
        Args:
            file_path: The path of the file
            
        Returns:
            Optional[bytes]: The file data, or None if not found
            
        Raises:
            FileError: If there was an error retrieving the file
        """
        try:
            # Ensure the path is safe
            safe_path = self._sanitize_path(file_path)
            abs_file_path = self.base_path / safe_path
            
            # Check if file exists
            if not abs_file_path.is_file():
                return None
            
            # Read file
            async with aiofiles.open(abs_file_path, "rb") as f:
                data = await f.read()
            
            return data
        
        except FileNotFoundError:
            return None
        
        except Exception as e:
            raise FileError(f"Failed to retrieve file: {e}", file_name=file_path)
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file by its path.
        
        Args:
            file_path: The path of the file
            
        Returns:
            bool: True if the file was deleted, False otherwise
            
        Raises:
            FileError: If there was an error deleting the file
        """
        try:
            # Ensure the path is safe
            safe_path = self._sanitize_path(file_path)
            abs_file_path = self.base_path / safe_path
            
            # Check if file exists
            if not abs_file_path.is_file():
                return False
            
            # Delete file
            abs_file_path.unlink()
            
            logger.info(f"File deleted: {abs_file_path}")
            return True
        
        except FileNotFoundError:
            return False
        
        except Exception as e:
            raise FileError(f"Failed to delete file: {e}", file_name=file_path)
    
    async def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a file.
        
        Args:
            file_path: The path of the file
            
        Returns:
            Optional[Dict[str, Any]]: Information about the file, or None if not found
            
        Raises:
            FileError: If there was an error getting the file information
        """
        try:
            # Ensure the path is safe
            safe_path = self._sanitize_path(file_path)
            abs_file_path = self.base_path / safe_path
            
            # Check if file exists
            if not abs_file_path.is_file():
                return None
            
            # Get file stats
            stats = abs_file_path.stat()
            
            # Get content type
            content_type, _ = mimetypes.guess_type(str(abs_file_path))
            
            # Get dimensions for images
            width = None
            height = None
            duration = None
            
            if content_type and content_type.startswith('image/'):
                try:
                    # Use asyncio to run PIL in a thread pool
                    loop = asyncio.get_event_loop()
                    with Image.open(abs_file_path) as img:
                        width, height = await loop.run_in_executor(None, lambda: img.size)
                except Exception as e:
                    logger.warning(f"Failed to get image dimensions: {e}")
            
            # Construct file info
            info = {
                "name": abs_file_path.name,
                "path": str(safe_path),
                "size": stats.st_size,
                "content_type": content_type or "application/octet-stream",
                "created_at": datetime.fromtimestamp(stats.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stats.st_mtime).isoformat(),
            }
            
            # Add dimensions if available
            if width is not None and height is not None:
                info["width"] = width
                info["height"] = height
            
            # Add duration if available
            if duration is not None:
                info["duration"] = duration
            
            return info
        
        except FileNotFoundError:
            return None
        
        except Exception as e:
            raise FileError(f"Failed to get file info: {e}", file_name=file_path)
    
    async def get_file_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a URL for a file that can be used to access it.
        
        For local storage, this is just the path. In a real-world implementation,
        this would need to be combined with a base URL where the files are served.
        
        Args:
            file_path: The path of the file
            expires_in: The number of seconds the URL should be valid for (ignored for local storage)
            
        Returns:
            str: The URL where the file can be accessed
            
        Raises:
            FileError: If there was an error generating the URL
        """
        # Ensure the path is safe
        safe_path = self._sanitize_path(file_path)
        abs_file_path = self.base_path / safe_path
        
        # Check if file exists
        if not abs_file_path.is_file():
            raise FileError(f"File not found: {file_path}")
        
        # For local storage, just return the path
        # In a real implementation, this would be combined with a base URL
        return str(safe_path)
    
    async def create_thumbnail(self, file_path: str, width: int, height: int) -> Optional[str]:
        """Create a thumbnail for an image.
        
        Args:
            file_path: The path of the file
            width: The desired width of the thumbnail
            height: The desired height of the thumbnail
            
        Returns:
            Optional[str]: The path of the thumbnail, or None if not possible
            
        Raises:
            FileError: If there was an error creating the thumbnail
        """
        try:
            # Ensure the path is safe
            safe_path = self._sanitize_path(file_path)
            abs_file_path = self.base_path / safe_path
            
            # Check if file exists
            if not abs_file_path.is_file():
                return None
            
            # Check if it's an image
            content_type, _ = mimetypes.guess_type(str(abs_file_path))
            if not content_type or not content_type.startswith('image/'):
                return None
            
            # Generate thumbnail path
            thumbnail_name = f"{abs_file_path.stem}_thumb_{width}x{height}{abs_file_path.suffix}"
            thumbnail_path = abs_file_path.parent / thumbnail_name
            rel_thumbnail_path = Path(file_path).parent / thumbnail_name
            
            # Create thumbnail
            loop = asyncio.get_event_loop()
            
            await loop.run_in_executor(None, self._create_thumbnail_sync, 
                                    str(abs_file_path), str(thumbnail_path), width, height)
            
            logger.info(f"Thumbnail created: {thumbnail_path}")
            
            # Return relative path as string
            return str(rel_thumbnail_path).replace("\\", "/")  # Use forward slashes for consistency
        
        except Exception as e:
            raise FileError(f"Failed to create thumbnail: {e}", file_name=file_path)
    
    def _create_thumbnail_sync(self, source_path: str, thumbnail_path: str, width: int, height: int) -> None:
        """Synchronous thumbnail creation (to be run in a thread pool).
        
        Args:
            source_path: The path of the source file
            thumbnail_path: The path where the thumbnail should be saved
            width: The desired width of the thumbnail
            height: The desired height of the thumbnail
            
        Raises:
            Exception: If there was an error creating the thumbnail
        """
        with Image.open(source_path) as img:
            # Calculate aspect ratio
            img_width, img_height = img.size
            aspect = img_width / img_height
            
            # Determine thumbnail size while maintaining aspect ratio
            if width / height > aspect:
                new_width = int(height * aspect)
                new_height = height
            else:
                new_width = width
                new_height = int(width / aspect)
            
            # Resize image
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Save thumbnail
            img.save(thumbnail_path, quality=85, optimize=True)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename to make it safe for storage.
        
        Args:
            filename: The filename to sanitize
            
        Returns:
            str: The sanitized filename
        """
        # Remove path components
        filename = os.path.basename(filename)
        
        # Keep only alphanumeric characters, underscores, hyphens, and periods
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
        
        # Replace unsafe characters with underscores
        clean_name = ''.join(c if c in safe_chars else '_' for c in filename)
        
        # Ensure there's a valid extension
        if '.' not in clean_name:
            clean_name += '.bin'
        
        return clean_name
    
    def _sanitize_path(self, path: str) -> Path:
        """Sanitize a path to make it safe for accessing files.
        
        Args:
            path: The path to sanitize
            
        Returns:
            Path: The sanitized path
            
        Raises:
            ValueError: If the path is unsafe
        """
        # Normalize the path and convert to Path object
        path = Path(path.replace('\\', '/')).as_posix()
        normalized = Path(path).resolve()
        
        # Ensure the path is within the base path
        try:
            normalized.relative_to(self.base_path)
        except ValueError:
            # If the normalized path is not within the base path, use the path as is
            # but ensure it doesn't escape the base path
            normalized = self.base_path / Path(path).relative_to(Path(path).anchor)
        
        return normalized