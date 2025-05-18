"""
Security manager for the ChatMS plugin.
"""

import base64
import datetime
import hashlib
import os
from typing import Any, Dict, Optional, Tuple

import bcrypt
from jose import jwt

from ..config import Config
from ..exceptions import AuthenticationError, ConfigurationError


class SecurityManager:
    """Handles authentication, authorization, and encryption."""
    
    def __init__(self, config: Config):
        """Initialize the security manager.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate security-related configuration.
        
        Raises:
            ConfigurationError: If any required configuration is missing or invalid
        """
        if not self.config.jwt_secret:
            raise ConfigurationError("JWT secret is required")
        
        if self.config.enable_encryption and not self.config.encryption_key:
            raise ConfigurationError("Encryption key is required when encryption is enabled")
    
    async def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.
        
        Args:
            password: The password to hash
            
        Returns:
            str: The hashed password
        """
        # Generate a salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    
    async def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against a hash.
        
        Args:
            password: The password to verify
            hashed_password: The hash to verify against
            
        Returns:
            bool: True if the password matches the hash, False otherwise
        """
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    
    async def create_token(self, user_id: str, expires_minutes: Optional[int] = None) -> str:
        """Create a JWT token for a user.
        
        Args:
            user_id: The user ID
            expires_minutes: Token expiration time in minutes (optional)
            
        Returns:
            str: The JWT token
            
        Raises:
            ConfigurationError: If JWT secret is not configured
        """
        if not self.config.jwt_secret:
            raise ConfigurationError("JWT secret is required")
        
        expires_delta = expires_minutes or self.config.jwt_expiration_minutes
        expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_delta)
        
        # Create token data
        token_data = {
            "sub": user_id,
            "exp": expires,
            "iat": datetime.datetime.utcnow(),
            "type": "access"
        }
        
        # Create token
        token = jwt.encode(
            token_data,
            self.config.jwt_secret,
            algorithm=self.config.jwt_algorithm
        )
        
        return token
    
    async def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token.
        
        Args:
            token: The JWT token
            
        Returns:
            Dict[str, Any]: The decoded token data
            
        Raises:
            AuthenticationError: If the token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm]
            )
            
            # Verify token type
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")
            
            return payload
        except jwt.JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
    
    async def get_user_id_from_token(self, token: str) -> str:
        """Get the user ID from a JWT token.
        
        Args:
            token: The JWT token
            
        Returns:
            str: The user ID
            
        Raises:
            AuthenticationError: If the token is invalid or expired
        """
        payload = await self.decode_token(token)
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token: missing user ID")
        
        return user_id
    
    async def encrypt(self, data: str) -> str:
        """Encrypt data.
        
        Args:
            data: The data to encrypt
            
        Returns:
            str: The encrypted data
            
        Raises:
            ConfigurationError: If encryption is not configured
        """
        if not self.config.enable_encryption:
            return data
        
        if not self.config.encryption_key:
            raise ConfigurationError("Encryption key is required")
        
        # Implementation depends on the encryption method
        # This is a simple example using AES-256-GCM
        # In a real implementation, use a library like cryptography
        
        # For demonstration purposes, we'll implement a simplified version
        # In a real application, use a proper encryption library
        
        # Convert key from hex to bytes
        key = bytes.fromhex(self.config.encryption_key)
        
        # Generate a random 16-byte IV
        iv = os.urandom(16)
        
        # Derive an encryption key using PBKDF2
        derived_key = hashlib.pbkdf2_hmac(
            "sha256",
            key,
            iv,
            100000,  # 100,000 iterations
            32  # 32 bytes = 256 bits
        )
        
        # XOR the data with the derived key (simplified encryption, not secure!)
        data_bytes = data.encode()
        # Repeat the key to match data length
        full_key = derived_key * (len(data_bytes) // len(derived_key) + 1)
        full_key = full_key[:len(data_bytes)]
        
        # XOR each byte
        encrypted_bytes = bytes(a ^ b for a, b in zip(data_bytes, full_key))
        
        # Combine IV and encrypted data
        result = iv + encrypted_bytes
        
        # Encode as base64 for storage/transmission
        return base64.b64encode(result).decode()
    
    async def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data.
        
        Args:
            encrypted_data: The encrypted data
            
        Returns:
            str: The decrypted data
            
        Raises:
            ConfigurationError: If encryption is not configured
            ValueError: If the data is invalid
        """
        if not self.config.enable_encryption:
            return encrypted_data
        
        if not self.config.encryption_key:
            raise ConfigurationError("Encryption key is required")
        
        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data)
            
            # Extract IV (first 16 bytes)
            iv = data[:16]
            encrypted_bytes = data[16:]
            
            # Convert key from hex to bytes
            key = bytes.fromhex(self.config.encryption_key)
            
            # Derive the same encryption key using PBKDF2
            derived_key = hashlib.pbkdf2_hmac(
                "sha256",
                key,
                iv,
                100000,  # 100,000 iterations
                32  # 32 bytes = 256 bits
            )
            
            # Repeat the key to match data length
            full_key = derived_key * (len(encrypted_bytes) // len(derived_key) + 1)
            full_key = full_key[:len(encrypted_bytes)]
            
            # XOR each byte to decrypt
            decrypted_bytes = bytes(a ^ b for a, b in zip(encrypted_bytes, full_key))
            
            # Decode to string
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {str(e)}")
    
    async def generate_random_key(self, length: int = 32) -> str:
        """Generate a random key.
        
        Args:
            length: The length of the key in bytes
            
        Returns:
            str: The key as a hex string
        """
        return os.urandom(length).hex()