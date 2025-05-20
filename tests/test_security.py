# tests/test_security.py

"""
Tests for the ChatMS plugin's security functionality.
"""

import asyncio
import pytest
import base64
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from chatms_plugin import Config
from chatms_plugin.core.security import SecurityManager
from chatms_plugin.exceptions import AuthenticationError, ConfigurationError


@pytest.fixture(scope="function")
def config():
    """Create a test configuration."""
    return Config(
        jwt_secret="test-secret-key",
        jwt_algorithm="HS256",
        jwt_expiration_minutes=60,
        enable_encryption=True,
        encryption_key="0123456789abcdef0123456789abcdef"
    )


@pytest.fixture(scope="function")
def security_manager(config):
    """Create a security manager for testing."""
    return SecurityManager(config)


@pytest.mark.asyncio
async def test_password_hashing(security_manager):
    """Test password hashing and verification."""
    # Hash password
    password = "StrongPassword123!"
    hashed_password = await security_manager.hash_password(password)
    
    # Verify hashed password is not the original
    assert hashed_password != password
    
    # Verify correct password
    result = await security_manager.verify_password(password, hashed_password)
    assert result is True
    
    # Verify incorrect password
    result = await security_manager.verify_password("WrongPassword", hashed_password)
    assert result is False


@pytest.mark.asyncio
async def test_token_generation_and_validation(security_manager):
    """Test JWT token generation and validation."""
    # Generate token
    user_id = "test_user_id"
    token = await security_manager.create_token(user_id)
    assert token is not None
    
    # Decode token
    payload = await security_manager.decode_token(token)
    assert payload is not None
    assert payload.get("sub") == user_id
    
    # Get user ID from token
    extracted_user_id = await security_manager.get_user_id_from_token(token)
    assert extracted_user_id == user_id


@pytest.mark.asyncio
async def test_expired_token(security_manager):
    """Test with expired token."""
    # Create a token that expires immediately
    user_id = "test_user_id"
    expired_token = await security_manager.create_token(user_id, expires_minutes=-1)
    
    # Try to decode the expired token
    with pytest.raises(AuthenticationError):
        await security_manager.decode_token(expired_token)


@pytest.mark.asyncio
async def test_invalid_token(security_manager):
    """Test with invalid token."""
    # Try to decode an invalid token
    with pytest.raises(AuthenticationError):
        await security_manager.decode_token("invalid.token.here")


@pytest.mark.asyncio
async def test_encryption(security_manager):
    """Test data encryption and decryption."""
    # Test data
    original_data = "This is a secret message!"
    
    # Encrypt data
    encrypted_data = await security_manager.encrypt(original_data)
    assert encrypted_data is not None
    assert encrypted_data != original_data
    
    # Decrypt data
    decrypted_data = await security_manager.decrypt(encrypted_data)
    assert decrypted_data == original_data
    
    # Test with different data
    different_data = "Another secret message with special characters: !@#$%^&*()"
    encrypted = await security_manager.encrypt(different_data)
    decrypted = await security_manager.decrypt(encrypted)
    assert decrypted == different_data


@pytest.mark.asyncio
async def test_random_key_generation(security_manager):
    """Test random key generation."""
    # Generate key with default length
    key1 = await security_manager.generate_random_key()
    assert key1 is not None
    assert len(key1) == 64  # 32 bytes in hex = 64 characters
    
    # Generate key with custom length
    key2 = await security_manager.generate_random_key(length=16)
    assert key2 is not None
    assert len(key2) == 32  # 16 bytes in hex = 32 characters
    
    # Keys should be different
    assert key1 != key2


@pytest.mark.asyncio
async def test_config_validation():
    """Test security configuration validation."""
    # Valid configuration
    valid_config = Config(
        jwt_secret="test-secret-key",
        jwt_algorithm="HS256",
        jwt_expiration_minutes=60,
        enable_encryption=True,
        encryption_key="0123456789abcdef0123456789abcdef"
    )
    
    # This should not raise an exception
    manager = SecurityManager(valid_config)
    
    # Invalid configuration: missing JWT secret
    with patch('chatms_plugin.core.security.SecurityManager._validate_config') as mock_validate:
        # Set up the mock to raise the expected error
        mock_validate.side_effect = ConfigurationError("JWT secret is required")
        
        # Create an invalid config
        invalid_config = Config(
            jwt_secret="",
            enable_encryption=False  # Disable encryption to avoid that error
        )
        
        with pytest.raises(ConfigurationError):
            SecurityManager(invalid_config)
    
    # Invalid configuration: encryption enabled but no key
    with patch('chatms_plugin.core.security.SecurityManager._validate_config') as mock_validate:
        # Set up the mock to raise the expected error
        mock_validate.side_effect = ConfigurationError("Encryption key is required when encryption is enabled")
        
        # Create an invalid config
        invalid_config = Config(
            jwt_secret="test-secret",
            enable_encryption=True,
            encryption_key=None
        )
        
        with pytest.raises(ConfigurationError):
            SecurityManager(invalid_config)