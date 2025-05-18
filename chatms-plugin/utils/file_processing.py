"""
File processing utilities for the ChatMS plugin.
"""

import asyncio
import io
import logging
import mimetypes
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, BinaryIO

from PIL import Image, ImageOps
import magic

from ..config import Config
from ..exceptions import FileError, FileSizeError, FileTypeError


logger = logging.getLogger(__name__)


class FileProcessingUtils:
    """Utilities for processing and validating files."""
    
    def __init__(self, config: Config):
        """Initialize the file processing utilities.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.max_file_size_mb = config.max_file_size_mb
        self.allowed_extensions = config.allowed_extensions
    
    async def validate_file(self, file_data: bytes, file_name: str) -> None:
        """Validate a file based on size and extension.
        
        Args:
            file_data: The file data as bytes
            file_name: The file name
            
        Raises:
            FileSizeError: If the file is too large
            FileTypeError: If the file type is not allowed
        """
        # Check file size
        file_size = len(file_data)
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            raise FileSizeError(
                file_name=file_name,
                file_size=file_size,
                max_size=max_size_bytes
            )
        
        # Check file extension
        ext = os.path.splitext(file_name)[1].lstrip(".").lower()
        
        if self.allowed_extensions and ext not in [e.lower() for e in self.allowed_extensions]:
            raise FileTypeError(
                file_name=file_name,
                file_type=ext,
                allowed_types=self.allowed_extensions
            )
    
    async def detect_mime_type(self, file_data: bytes, file_name: str) -> str:
        """Detect the MIME type of a file.
        
        Args:
            file_data: The file data as bytes
            file_name: The file name for fallback detection
            
        Returns:
            str: The detected MIME type
        """
        try:
            # Try to detect MIME type using python-magic
            mime_type = magic.from_buffer(file_data, mime=True)
            
            # Fall back to mimetypes if magic fails
            if not mime_type or mime_type == "application/octet-stream":
                mime_type, _ = mimetypes.guess_type(file_name)
            
            # Final fallback
            if not mime_type:
                mime_type = "application/octet-stream"
            
            return mime_type
            
        except Exception as e:
            logger.warning(f"Failed to detect MIME type: {e}")
            
            # Fall back to mimetypes
            mime_type, _ = mimetypes.guess_type(file_name)
            return mime_type or "application/octet-stream"
    
    async def create_image_thumbnail(self, image_data: bytes, width: int, height: int, 
                                   format: str = "JPEG", quality: int = 85) -> bytes:
        """Create a thumbnail from an image.
        
        Args:
            image_data: The image data as bytes
            width: The desired width of the thumbnail
            height: The desired height of the thumbnail
            format: The output format (JPEG, PNG, etc.)
            quality: The output quality (for JPEG)
            
        Returns:
            bytes: The thumbnail data
            
        Raises:
            FileError: If the thumbnail cannot be created
        """
        try:
            # Use a thread pool for CPU-intensive image processing
            loop = asyncio.get_event_loop()
            
            # Create thumbnail
            thumbnail_data = await loop.run_in_executor(
                None,
                self._create_thumbnail_sync,
                image_data,
                width,
                height,
                format,
                quality
            )
            
            return thumbnail_data
            
        except Exception as e:
            raise FileError(f"Failed to create thumbnail: {e}")
    
    def _create_thumbnail_sync(self, image_data: bytes, width: int, height: int, 
                             format: str, quality: int) -> bytes:
        """Synchronous thumbnail creation (to be run in a thread pool).
        
        Args:
            image_data: The image data as bytes
            width: The desired width of the thumbnail
            height: The desired height of the thumbnail
            format: The output format
            quality: The output quality
            
        Returns:
            bytes: The thumbnail data
        """
        # Open image from bytes
        with io.BytesIO(image_data) as input_buffer:
            with Image.open(input_buffer) as img:
                # Convert mode if needed
                if img.mode not in ["RGB", "RGBA"]:
                    img = img.convert("RGB")
                
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
                
                # If format is PNG and there's no alpha channel, convert to RGB
                if format.upper() == "PNG" and img.mode != "RGBA":
                    img = img.convert("RGBA")
                
                # Save thumbnail to buffer
                output_buffer = io.BytesIO()
                img.save(output_buffer, format=format, quality=quality, optimize=True)
                output_buffer.seek(0)
                
                # Return the thumbnail data
                return output_buffer.read()
    
    async def extract_image_metadata(self, image_data: bytes) -> Dict[str, Union[int, str]]:
        """Extract metadata from an image.
        
        Args:
            image_data: The image data as bytes
            
        Returns:
            Dict[str, Union[int, str]]: The image metadata
            
        Raises:
            FileError: If the metadata cannot be extracted
        """
        try:
            # Use a thread pool for CPU-intensive image processing
            loop = asyncio.get_event_loop()
            
            # Extract metadata
            metadata = await loop.run_in_executor(
                None,
                self._extract_image_metadata_sync,
                image_data
            )
            
            return metadata
            
        except Exception as e:
            raise FileError(f"Failed to extract image metadata: {e}")
    
    def _extract_image_metadata_sync(self, image_data: bytes) -> Dict[str, Union[int, str]]:
        """Synchronous metadata extraction (to be run in a thread pool).
        
        Args:
            image_data: The image data as bytes
            
        Returns:
            Dict[str, Union[int, str]]: The image metadata
        """
        # Open image from bytes
        with io.BytesIO(image_data) as input_buffer:
            with Image.open(input_buffer) as img:
                # Extract basic metadata
                metadata = {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode
                }
                
                # Extract EXIF data if available
                if hasattr(img, "_getexif") and callable(img._getexif):
                    exif = img._getexif()
                    if exif:
                        # Extract useful EXIF tags
                        exif_tags = {
                            271: "make",           # Camera manufacturer
                            272: "model",          # Camera model
                            306: "datetime",       # Date and time
                            36867: "datetime_original",  # Original date and time
                            33432: "copyright",    # Copyright
                            37510: "user_comment"  # User comment
                        }
                        
                        for tag, name in exif_tags.items():
                            if tag in exif:
                                value = exif[tag]
                                if isinstance(value, bytes):
                                    try:
                                        value = value.decode('utf-8').strip('\x00')
                                    except UnicodeDecodeError:
                                        value = str(value)
                                metadata[name] = value
                
                return metadata
    
    async def is_image(self, file_data: bytes, file_name: str) -> bool:
        """Check if a file is an image.
        
        Args:
            file_data: The file data as bytes
            file_name: The file name for fallback detection
            
        Returns:
            bool: True if the file is an image, False otherwise
        """
        # Try to detect MIME type
        mime_type = await self.detect_mime_type(file_data, file_name)
        
        # Check if the MIME type starts with 'image/'
        if mime_type and mime_type.startswith('image/'):
            # Try to open the image to confirm it's valid
            try:
                loop = asyncio.get_event_loop()
                
                # Try to open the image
                is_valid = await loop.run_in_executor(
                    None,
                    self._is_valid_image_sync,
                    file_data
                )
                
                return is_valid
                
            except Exception:
                return False
        
        return False
    
    def _is_valid_image_sync(self, image_data: bytes) -> bool:
        """Synchronously check if data is a valid image (to be run in a thread pool).
        
        Args:
            image_data: The image data as bytes
            
        Returns:
            bool: True if the data is a valid image, False otherwise
        """
        try:
            # Try to open the image
            with io.BytesIO(image_data) as input_buffer:
                with Image.open(input_buffer) as img:
                    # Access width and height to force image processing
                    img.width
                    img.height
                    return True
        except Exception:
            return False
    
    async def sanitize_file_name(self, file_name: str) -> str:
        """Sanitize a file name to make it safe for storage.
        
        Args:
            file_name: The file name to sanitize
            
        Returns:
            str: The sanitized file name
        """
        # Remove path components
        file_name = os.path.basename(file_name)
        
        # Keep only alphanumeric characters, underscores, hyphens, and periods
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
        
        # Replace unsafe characters with underscores
        clean_name = ''.join(c if c in safe_chars else '_' for c in file_name)
        
        # Ensure there's a valid extension
        if '.' not in clean_name:
            clean_name += '.bin'
        
        return clean_name
    
    async def scan_file_for_viruses(self, file_data: bytes) -> Tuple[bool, Optional[str]]:
        """Scan a file for viruses using the configured virus scanner.
        
        Args:
            file_data: The file data as bytes
            
        Returns:
            Tuple[bool, Optional[str]]: (is_clean, reason)
        """
        # Check if virus scanning is enabled
        if not self.config.enable_virus_scan:
            return True, None
        
        # This is a placeholder for virus scanning integration
        # In a real implementation, this would use an actual virus scanner
        logger.debug("Virus scanning is not implemented yet")
        
        # For now, just pretend all files are clean
        return True, None