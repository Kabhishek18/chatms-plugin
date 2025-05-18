"""
Encryption utilities for the ChatMS plugin.
"""

import base64
import hashlib
import os
from typing import Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionUtils:
    """Utilities for encryption and decryption of data."""
    
    @staticmethod
    def generate_key(password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """Generate a key from a password.
        
        Args:
            password: The password
            salt: The salt (optional, will be generated if not provided)
            
        Returns:
            Tuple[bytes, bytes]: The key and the salt
        """
        # Generate a salt if not provided
        if salt is None:
            salt = os.urandom(16)
        
        # Derive a key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        # Get key from password
        key = kdf.derive(password.encode())
        
        return key, salt
    
    @staticmethod
    def encrypt(data: str, password: str) -> str:
        """Encrypt data using a password.
        
        Args:
            data: The data to encrypt
            password: The password to use for encryption
            
        Returns:
            str: The encrypted data as a Base64-encoded string
        """
        # Generate key and salt
        key, salt = EncryptionUtils.generate_key(password)
        
        # Create a Fernet instance
        fernet = Fernet(base64.urlsafe_b64encode(key))
        
        # Encrypt the data
        encrypted_data = fernet.encrypt(data.encode())
        
        # Combine salt and encrypted data
        result = salt + encrypted_data
        
        # Encode as Base64
        return base64.b64encode(result).decode()
    
    @staticmethod
    def decrypt(encrypted_data: str, password: str) -> str:
        """Decrypt data using a password.
        
        Args:
            encrypted_data: The encrypted data as a Base64-encoded string
            password: The password to use for decryption
            
        Returns:
            str: The decrypted data
            
        Raises:
            ValueError: If the data cannot be decrypted
        """
        try:
            # Decode from Base64
            data = base64.b64decode(encrypted_data)
            
            # Extract salt and encrypted data
            salt = data[:16]
            encrypted = data[16:]
            
            # Generate key from password and salt
            key, _ = EncryptionUtils.generate_key(password, salt)
            
            # Create a Fernet instance
            fernet = Fernet(base64.urlsafe_b64encode(key))
            
            # Decrypt the data
            decrypted_data = fernet.decrypt(encrypted)
            
            return decrypted_data.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {str(e)}")
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password securely.
        
        Args:
            password: The password to hash
            
        Returns:
            str: The hashed password
        """
        # Generate a salt
        salt = os.urandom(16)
        
        # Derive a key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        # Hash the password
        hashed = kdf.derive(password.encode())
        
        # Combine salt and hash
        result = salt + hashed
        
        # Encode as Base64
        return base64.b64encode(result).decode()
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify a password against a hash.
        
        Args:
            password: The password to verify
            hashed_password: The hashed password
            
        Returns:
            bool: True if the password matches the hash, False otherwise
        """
        try:
            # Decode from Base64
            data = base64.b64decode(hashed_password)
            
            # Extract salt and hash
            salt = data[:16]
            stored_hash = data[16:]
            
            # Derive a key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            # Hash the password
            try:
                kdf.verify(password.encode(), stored_hash)
                return True
            except Exception:
                return False
        except Exception:
            return False
    
    @staticmethod
    def generate_random_key(length: int = 32) -> str:
        """Generate a random key.
        
        Args:
            length: The length of the key in bytes
            
        Returns:
            str: The key as a hex string
        """
        return os.urandom(length).hex()