"""
AWS S3 storage handler for the ChatMS plugin.
"""

import asyncio
import logging
import mimetypes
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, BinaryIO

import boto3
import botocore
from PIL import Image

from ..config import Config
from ..exceptions import FileError, StorageError
from .base import StorageHandler


logger = logging.getLogger(__name__)


class S3StorageHandler(StorageHandler):
    """Storage handler for AWS S3 storage."""
    
    def __init__(self, config: Config):
        """Initialize the S3 storage handler.
        
        Args:
            config: Configuration object
        """
        super().__init__()
        self.config = config
        self.bucket_name = config.storage_bucket
        self.credentials = config.storage_credentials or {}
        self.s3_client = None
        self.loop = None
    
    async def init(self) -> None:
        """Initialize the storage connection."""
        try:
            # Get the event loop
            self.loop = asyncio.get_event_loop()
            
            # Create S3 client
            self.s3_client = await self.loop.run_in_executor(
                None,
                lambda: boto3.client(
                    's3',
                    aws_access_key_id=self.credentials.get('aws_access_key_id'),
                    aws_secret_access_key=self.credentials.get('aws_secret_access_key'),
                    region_name=self.credentials.get('region_name', 'us-east-1')
                )
            )
            
            # Check if bucket exists and is accessible
            await self.loop.run_in_executor(
                None,
                lambda: self.s3_client.head_bucket(Bucket=self.bucket_name)
            )
            
            logger.info(f"S3 storage initialized with bucket {self.bucket_name}")
            
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                raise StorageError(f"S3 bucket {self.bucket_name} does not exist")
            elif error_code == '403':
                raise StorageError(f"Access denied to S3 bucket {self.bucket_name}")
            else:
                raise StorageError(f"Failed to initialize S3 storage: {e}")
        except Exception as e:
            raise StorageError(f"Failed to initialize S3 storage: {e}")
    
    async def close(self) -> None:
        """Close the storage connection."""
        # Nothing to do for S3 client
        pass
    
    async def save_file(self, file_data: bytes, file_name: str, 
                      content_type: Optional[str] = None) -> str:
        """Save a file to S3 and return its S3 key.
        
        Args:
            file_data: The file data as bytes
            file_name: The original file name
            content_type: The MIME type of the file, if known
            
        Returns:
            str: The S3 key where the file is stored
            
        Raises:
            FileError: If there was an error saving the file
        """
        try:
            # Ensure file_name is safe
            safe_name = self._sanitize_filename(file_name)
            
            # Generate unique key based on date and UUID
            date_prefix = datetime.now().strftime("%Y/%m/%d")
            file_uuid = str(uuid.uuid4())
            _, ext = os.path.splitext(safe_name)
            s3_key = f"{date_prefix}/{file_uuid}{ext}"
            
            # Determine content type
            if not content_type:
                content_type = self.get_content_type(file_name)
            
            # Upload file to S3
            await self.loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=file_data,
                    ContentType=content_type
                )
            )
            
            logger.info(f"File saved to S3: {s3_key}")
            
            return s3_key
            
        except botocore.exceptions.ClientError as e:
            raise FileError(f"Failed to save file to S3: {e}", file_name=file_name)
        except Exception as e:
            raise FileError(f"Failed to save file to S3: {e}", file_name=file_name)
    
    async def get_file(self, file_path: str) -> Optional[bytes]:
        """Get a file from S3 by its key.
        
        Args:
            file_path: The S3 key of the file
            
        Returns:
            Optional[bytes]: The file data, or None if not found
            
        Raises:
            FileError: If there was an error retrieving the file
        """
        try:
            # Get file from S3
            response = await self.loop.run_in_executor(
                None,
                lambda: self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
            )
            
            # Read file data
            body = await self.loop.run_in_executor(
                None,
                lambda: response['Body'].read()
            )
            
            return body
            
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                return None
            else:
                raise FileError(f"Failed to retrieve file from S3: {e}", file_name=file_path)
        except Exception as e:
            raise FileError(f"Failed to retrieve file from S3: {e}", file_name=file_path)
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from S3 by its key.
        
        Args:
            file_path: The S3 key of the file
            
        Returns:
            bool: True if the file was deleted, False otherwise
            
        Raises:
            FileError: If there was an error deleting the file
        """
        try:
            # Delete file from S3
            await self.loop.run_in_executor(
                None,
                lambda: self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
            )
            
            logger.info(f"File deleted from S3: {file_path}")
            
            return True
            
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                return False
            else:
                raise FileError(f"Failed to delete file from S3: {e}", file_name=file_path)
        except Exception as e:
            raise FileError(f"Failed to delete file from S3: {e}", file_name=file_path)
    
    async def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a file in S3.
        
        Args:
            file_path: The S3 key of the file
            
        Returns:
            Optional[Dict[str, Any]]: Information about the file, or None if not found
            
        Raises:
            FileError: If there was an error getting the file information
        """
        try:
            # Get file metadata from S3
            response = await self.loop.run_in_executor(
                None,
                lambda: self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
            )
            
            # Extract file info
            info = {
                "name": os.path.basename(file_path),
                "path": file_path,
                "size": response.get('ContentLength', 0),
                "content_type": response.get('ContentType', 'application/octet-stream'),
                "created_at": response.get('LastModified', datetime.now()).isoformat(),
                "modified_at": response.get('LastModified', datetime.now()).isoformat(),
                "metadata": response.get('Metadata', {})
            }
            
            # If it's an image, try to get dimensions
            if info['content_type'].startswith('image/'):
                # Download the file
                file_data = await self.get_file(file_path)
                if file_data:
                    try:
                        # Use PIL to get image dimensions
                        with BytesIO(file_data) as buffer:
                            with Image.open(buffer) as img:
                                width, height = img.size
                                info['width'] = width
                                info['height'] = height
                    except Exception as e:
                        logger.warning(f"Failed to get image dimensions: {e}")
            
            return info
            
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                return None
            else:
                raise FileError(f"Failed to get file info from S3: {e}", file_name=file_path)
        except Exception as e:
            raise FileError(f"Failed to get file info from S3: {e}", file_name=file_path)
    
    async def get_file_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for an S3 object.
        
        Args:
            file_path: The S3 key of the file
            expires_in: The number of seconds the URL should be valid for
            
        Returns:
            str: The URL where the file can be accessed
            
        Raises:
            FileError: If there was an error generating the URL
        """
        try:
            # Generate presigned URL
            url = await self.loop.run_in_executor(
                None,
                lambda: self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': file_path
                    },
                    ExpiresIn=expires_in
                )
            )
            
            return url
            
        except botocore.exceptions.ClientError as e:
            raise FileError(f"Failed to generate presigned URL: {e}", file_name=file_path)
        except Exception as e:
            raise FileError(f"Failed to generate presigned URL: {e}", file_name=file_path)
    
    async def create_thumbnail(self, file_path: str, width: int, height: int) -> Optional[str]:
        """Create a thumbnail for an image in S3.
        
        Args:
            file_path: The S3 key of the file
            width: The desired width of the thumbnail
            height: The desired height of the thumbnail
            
        Returns:
            Optional[str]: The S3 key of the thumbnail, or None if not possible
            
        Raises:
            FileError: If there was an error creating the thumbnail
        """
        try:
            # Get file info
            info = await self.get_file_info(file_path)
            if not info:
                return None
            
            # Check if it's an image
            if not info.get('content_type', '').startswith('image/'):
                return None
            
            # Download the file
            file_data = await self.get_file(file_path)
            if not file_data:
                return None
            
            # Generate thumbnail key
            path_parts = os.path.splitext(file_path)
            thumbnail_key = f"{path_parts[0]}_thumb_{width}x{height}{path_parts[1]}"
            
            # Create thumbnail
            thumbnail_data = await self.loop.run_in_executor(
                None,
                self._create_thumbnail_sync,
                file_data,
                width,
                height
            )
            
            # Upload thumbnail to S3
            await self.loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=thumbnail_key,
                    Body=thumbnail_data,
                    ContentType=info.get('content_type', 'image/jpeg')
                )
            )
            
            logger.info(f"Thumbnail created in S3: {thumbnail_key}")
            
            return thumbnail_key
            
        except Exception as e:
            raise FileError(f"Failed to create thumbnail: {e}", file_name=file_path)
    
    def _create_thumbnail_sync(self, file_data: bytes, width: int, height: int) -> bytes:
        """Synchronous thumbnail creation (to be run in a thread pool).
        
        Args:
            file_data: The file data
            width: The desired width of the thumbnail
            height: The desired height of the thumbnail
            
        Returns:
            bytes: The thumbnail data
            
        Raises:
            Exception: If there was an error creating the thumbnail
        """
        with BytesIO(file_data) as input_buffer:
            with Image.open(input_buffer) as img:
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
                
                # Save thumbnail to buffer
                output_buffer = BytesIO()
                img.save(output_buffer, format=img.format or 'JPEG', quality=85, optimize=True)
                
                # Return the thumbnail data
                return output_buffer.getvalue()
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename to make it safe for S3.
        
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