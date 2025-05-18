"""
Validation utilities for the ChatMS plugin.
"""

import re
from typing import Any, Dict, List, Optional, Union, Callable, Pattern

from pydantic import EmailStr, validator
from ..exceptions import ValidationError


class ValidationUtils:
    """Utilities for validating input data."""
    
    @staticmethod
    def validate_username(username: str) -> str:
        """Validate a username.
        
        Args:
            username: The username to validate
            
        Returns:
            str: The validated username
            
        Raises:
            ValidationError: If the username is invalid
        """
        # Check if username is empty
        if not username:
            raise ValidationError("Username cannot be empty", field="username")
        
        # Check if username is too short
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters long", field="username")
        
        # Check if username is too long
        if len(username) > 30:
            raise ValidationError("Username cannot be longer than 30 characters", field="username")
        
        # Check if username contains only alphanumeric characters and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError(
                "Username can only contain alphanumeric characters and underscores",
                field="username"
            )
        
        return username
    
    @staticmethod
    def validate_password(password: str) -> str:
        """Validate a password.
        
        Args:
            password: The password to validate
            
        Returns:
            str: The validated password
            
        Raises:
            ValidationError: If the password is invalid
        """
        # Check if password is empty
        if not password:
            raise ValidationError("Password cannot be empty", field="password")
        
        # Check if password is too short
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long", field="password")
        
        # Check if password is too long
        if len(password) > 100:
            raise ValidationError("Password cannot be longer than 100 characters", field="password")
        
        # Check if password contains at least one digit
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one digit", field="password")
        
        # Check if password contains at least one lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                "Password must contain at least one lowercase letter",
                field="password"
            )
        
        # Check if password contains at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                "Password must contain at least one uppercase letter",
                field="password"
            )
        
        return password
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Validate an email address.
        
        Args:
            email: The email address to validate
            
        Returns:
            str: The validated email address
            
        Raises:
            ValidationError: If the email address is invalid
        """
        # Check if email is empty
        if not email:
            raise ValidationError("Email address cannot be empty", field="email")
        
        # Check if email is too long
        if len(email) > 100:
            raise ValidationError("Email address cannot be longer than 100 characters", field="email")
        
        # Check if email matches email pattern
        email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email address format", field="email")
        
        return email
    
    @staticmethod
    def validate_chat_name(name: str, chat_type: str) -> Optional[str]:
        """Validate a chat name.
        
        Args:
            name: The chat name to validate
            chat_type: The chat type
            
        Returns:
            Optional[str]: The validated chat name, or None if not required
            
        Raises:
            ValidationError: If the chat name is invalid
        """
        # For one_to_one chats, name is optional
        if chat_type == "one_to_one" and not name:
            return None
        
        # For other chat types, name is required
        if chat_type != "one_to_one" and not name:
            raise ValidationError("Chat name is required for non-one-to-one chats", field="name")
        
        # Check if name is too long
        if name and len(name) > 100:
            raise ValidationError("Chat name cannot be longer than 100 characters", field="name")
        
        return name
    
    @staticmethod
    def validate_chat_members(member_ids: List[str], chat_type: str) -> List[str]:
        """Validate chat members.
        
        Args:
            member_ids: The member IDs to validate
            chat_type: The chat type
            
        Returns:
            List[str]: The validated member IDs
            
        Raises:
            ValidationError: If the members are invalid
        """
        # Check if members list is empty
        if not member_ids:
            raise ValidationError("Chat must have at least one member", field="member_ids")
        
        # Check if there are duplicate members
        if len(member_ids) != len(set(member_ids)):
            raise ValidationError("Duplicate member IDs are not allowed", field="member_ids")
        
        # For one_to_one chats, there must be exactly 2 members
        if chat_type == "one_to_one" and len(member_ids) != 2:
            raise ValidationError(
                "One-to-one chats must have exactly 2 members",
                field="member_ids"
            )
        
        return member_ids
    
    @staticmethod
    def validate_message_content(content: str, message_type: str) -> str:
        """Validate message content.
        
        Args:
            content: The message content to validate
            message_type: The message type
            
        Returns:
            str: The validated message content
            
        Raises:
            ValidationError: If the message content is invalid
        """
        # For text messages, content is required
        if message_type == "text" and not content:
            raise ValidationError("Text messages must have non-empty content", field="content")
        
        # Check if content is too long
        if len(content) > 10000:
            raise ValidationError(
                "Message content cannot be longer than 10,000 characters",
                field="content"
            )
        
        return content
    
    @staticmethod
    def validate_file_name(file_name: str) -> str:
        """Validate a file name.
        
        Args:
            file_name: The file name to validate
            
        Returns:
            str: The validated file name
            
        Raises:
            ValidationError: If the file name is invalid
        """
        # Check if file name is empty
        if not file_name:
            raise ValidationError("File name cannot be empty", field="file_name")
        
        # Check if file name is too long
        if len(file_name) > 255:
            raise ValidationError("File name cannot be longer than 255 characters", field="file_name")
        
        # Check if file name contains invalid characters
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, file_name):
            raise ValidationError(
                "File name contains invalid characters (< > : \" / \\ | ? *)",
                field="file_name"
            )
        
        return file_name
    
    @staticmethod
    def validate_file_type(file_type: str, allowed_types: List[str]) -> str:
        """Validate a file type.
        
        Args:
            file_type: The file type to validate
            allowed_types: The list of allowed file types
            
        Returns:
            str: The validated file type
            
        Raises:
            ValidationError: If the file type is invalid
        """
        # Check if file type is empty
        if not file_type:
            raise ValidationError("File type cannot be empty", field="file_type")
        
        # Check if file type is allowed
        if allowed_types and file_type.lower() not in [t.lower() for t in allowed_types]:
            raise ValidationError(
                f"File type '{file_type}' is not allowed. Allowed types: {', '.join(allowed_types)}",
                field="file_type"
            )
        
        return file_type
    
    @staticmethod
    def validate_reaction_type(reaction_type: str) -> str:
        """Validate a reaction type.
        
        Args:
            reaction_type: The reaction type to validate
            
        Returns:
            str: The validated reaction type
            
        Raises:
            ValidationError: If the reaction type is invalid
        """
        # Check if reaction type is empty
        if not reaction_type:
            raise ValidationError("Reaction type cannot be empty", field="reaction_type")
        
        # Check if reaction type is too long
        if len(reaction_type) > 10:
            raise ValidationError("Reaction type cannot be longer than 10 characters", field="reaction_type")
        
        return reaction_type
    
    @staticmethod
    def validate_url(url: str) -> str:
        """Validate a URL.
        
        Args:
            url: The URL to validate
            
        Returns:
            str: The validated URL
            
        Raises:
            ValidationError: If the URL is invalid
        """
        # Check if URL is empty
        if not url:
            raise ValidationError("URL cannot be empty", field="url")
        
        # Check if URL is too long
        if len(url) > 2000:
            raise ValidationError("URL cannot be longer than 2000 characters", field="url")
        
        # Check if URL is valid
        url_pattern = r'^(https?://)?([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(/[^\s]*)?$'
        if not re.match(url_pattern, url):
            raise ValidationError("Invalid URL format", field="url")
        
        return url
    
    @staticmethod
    def validate_search_query(query: str) -> str:
        """Validate a search query.
        
        Args:
            query: The query to validate
            
        Returns:
            str: The validated query
            
        Raises:
            ValidationError: If the query is invalid
        """
        # Check if query is empty
        if not query:
            raise ValidationError("Search query cannot be empty", field="query")
        
        # Check if query is too long
        if len(query) > 100:
            raise ValidationError("Search query cannot be longer than 100 characters", field="query")
        
        return query
    
    @staticmethod
    def validate_max_length(value: str, max_length: int, field_name: str) -> str:
        """Validate that a string is not longer than a maximum length.
        
        Args:
            value: The string to validate
            max_length: The maximum allowed length
            field_name: The name of the field being validated
            
        Returns:
            str: The validated string
            
        Raises:
            ValidationError: If the string is too long
        """
        if len(value) > max_length:
            raise ValidationError(
                f"{field_name} cannot be longer than {max_length} characters",
                field=field_name
            )
        
        return value
    
    @staticmethod
    def validate_min_length(value: str, min_length: int, field_name: str) -> str:
        """Validate that a string is not shorter than a minimum length.
        
        Args:
            value: The string to validate
            min_length: The minimum allowed length
            field_name: The name of the field being validated
            
        Returns:
            str: The validated string
            
        Raises:
            ValidationError: If the string is too short
        """
        if len(value) < min_length:
            raise ValidationError(
                f"{field_name} must be at least {min_length} characters long",
                field=field_name
            )
        
        return value
    
    @staticmethod
    def validate_regex(value: str, pattern: Union[str, Pattern], field_name: str) -> str:
        """Validate that a string matches a regex pattern.
        
        Args:
            value: The string to validate
            pattern: The regex pattern to match against
            field_name: The name of the field being validated
            
        Returns:
            str: The validated string
            
        Raises:
            ValidationError: If the string does not match the pattern
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        
        if not pattern.match(value):
            raise ValidationError(
                f"{field_name} does not match the required pattern",
                field=field_name
            )
        
        return value
    
    @staticmethod
    def sanitize_input(value: str) -> str:
        """Sanitize input to prevent XSS attacks.
        
        Args:
            value: The input to sanitize
            
        Returns:
            str: The sanitized input
        """
        # Replace < and > with their HTML entities
        value = value.replace("<", "&lt;").replace(">", "&gt;")
        
        # Replace quotes with their HTML entities
        value = value.replace('"', "&quot;").replace("'", "&#39;")
        
        # Replace JavaScript event handlers
        value = re.sub(r'on\w+\s*=', 'disabled=', value, flags=re.IGNORECASE)
        
        return value