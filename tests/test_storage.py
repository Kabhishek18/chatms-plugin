# tests/test_storage.py

"""
Tests for the ChatMS plugin's storage functionality.
"""

import asyncio
import os
import pytest
import shutil
import tempfile
from PIL import Image
from io import BytesIO

from chatms_plugin import Config
from chatms_plugin.exceptions import FileError, FileSizeError, FileTypeError
from chatms_plugin.storage.base import StorageHandler
from chatms_plugin.storage.local import LocalStorageHandler


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def config(temp_dir):
    """Create a test configuration with storage settings."""
    return Config(
        storage_type="local",
        storage_path=temp_dir,
        max_file_size_mb=1,
        allowed_extensions=["jpg", "png", "txt", "pdf"]
    )


@pytest.fixture
async def storage_handler(config):
    """Create and initialize a storage handler for testing."""
    handler = LocalStorageHandler(config)
    await handler.init()
    
    yield handler
    
    await handler.close()


@pytest.fixture
def test_image():
    """Create a test image file."""
    # Create a small RGB image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes.read()


@pytest.fixture
def test_text():
    """Create a test text file."""
    return b"This is a test text file.\nWith multiple lines.\n"


@pytest.mark.asyncio
async def test_file_validation(storage_handler, test_image, test_text):
    """Test file validation."""
    # Valid image file
    await storage_handler.validate_file(
        file_data=test_image,
        file_name="test.jpg",
        max_size_mb=1,
        allowed_extensions=["jpg", "png"]
    )
    
    # Valid text file
    await storage_handler.validate_file(
        file_data=test_text,
        file_name="test.txt",
        max_size_mb=1,
        allowed_extensions=["txt", "log"]
    )
    
    # Invalid extension
    with pytest.raises(FileTypeError):
        await storage_handler.validate_file(
            file_data=test_image,
            file_name="test.jpg",
            max_size_mb=1,
            allowed_extensions=["pdf", "doc"]
        )
    
    # File too large
    large_data = b"x" * (1024 * 1024 * 2)  # 2MB
    with pytest.raises(FileSizeError):
        await storage_handler.validate_file(
            file_data=large_data,
            file_name="large.txt",
            max_size_mb=1,
            allowed_extensions=["txt"]
        )


@pytest.mark.asyncio
async def test_file_save_and_get(storage_handler, test_image):
    """Test saving and retrieving files."""
    # Save file
    file_path = await storage_handler.save_file(
        file_data=test_image,
        file_name="test_image.jpg",
        content_type="image/jpeg"
    )
    
    assert file_path is not None
    
    # Get file
    retrieved_data = await storage_handler.get_file(file_path)
    assert retrieved_data is not None
    assert retrieved_data == test_image
    
    # Get file info
    file_info = await storage_handler.get_file_info(file_path)
    assert file_info is not None
    assert file_info["content_type"] == "image/jpeg"
    assert file_info["size"] == len(test_image)


@pytest.mark.asyncio
async def test_file_deletion(storage_handler, test_text):
    """Test file deletion."""
    # Save file
    file_path = await storage_handler.save_file(
        file_data=test_text,
        file_name="test_delete.txt",
        content_type="text/plain"
    )
    
    # Verify file exists
    retrieved_data = await storage_handler.get_file(file_path)
    assert retrieved_data is not None
    
    # Delete file
    result = await storage_handler.delete_file(file_path)
    assert result is True
    
    # Verify file is deleted
    deleted_data = await storage_handler.get_file(file_path)
    assert deleted_data is None


@pytest.mark.asyncio
async def test_thumbnail_creation(storage_handler, test_image):
    """Test thumbnail creation for images."""
    # Save image
    file_path = await storage_handler.save_file(
        file_data=test_image,
        file_name="thumbnail_test.jpg",
        content_type="image/jpeg"
    )
    
    # Create thumbnail
    thumbnail_path = await storage_handler.create_thumbnail(file_path, 50, 50)
    assert thumbnail_path is not None
    
    # Get thumbnail info
    thumb_info = await storage_handler.get_file_info(thumbnail_path)
    assert thumb_info is not None
    assert thumb_info["width"] <= 50
    assert thumb_info["height"] <= 50


@pytest.mark.asyncio
async def test_file_url_generation(storage_handler, test_text):
    """Test file URL generation."""
    # Save file
    file_path = await storage_handler.save_file(
        file_data=test_text,
        file_name="url_test.txt",
        content_type="text/plain"
    )
    
    # Get URL
    url = await storage_handler.get_file_url(file_path)
    assert url is not None
    assert url == file_path  # For local storage, URL is the path


@pytest.mark.asyncio
async def test_content_type_detection(storage_handler):
    """Test content type detection."""
    # Test common file types
    assert storage_handler.get_content_type("image.jpg") == "image/jpeg"
    assert storage_handler.get_content_type("document.pdf") == "application/pdf"
    assert storage_handler.get_content_type("text.txt") == "text/plain"
    assert storage_handler.get_content_type("unknown.xyz") == "application/octet-stream"


@pytest.mark.asyncio
async def test_storage_path_safety(storage_handler, test_text):
    """Test storage path safety (no directory traversal)."""
    # Save file
    file_path = await storage_handler.save_file(
        file_data=test_text,
        file_name="safety_test.txt",
        content_type="text/plain"
    )
    
    # Try to access with path traversal
    with pytest.raises(Exception):
        await storage_handler.get_file("../../../etc/passwd")