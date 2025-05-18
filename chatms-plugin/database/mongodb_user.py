"""
MongoDB database handler for the ChatMS plugin - User operations.
"""

import logging
from typing import Any, Dict, List, Optional

from ..config import UserRole
from ..exceptions import DatabaseError
from ..models.user import User
from .mongodb_base import MongoDBHandler


logger = logging.getLogger(__name__)


class MongoDBUserHandler(MongoDBHandler):
    """MongoDB handler for user operations."""
    
    async def create_user(self, user: User) -> User:
        """Create a new user.
        
        Args:
            user: The user to create
            
        Returns:
            User: The created user
            
        Raises:
            DatabaseError: If there was an error creating the user
        """
        return await self.create(user)
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[User]: The user, or None if not found
            
        Raises:
            DatabaseError: If there was an error retrieving the user
        """
        user_data = await self.get("users", user_id)
        
        if not user_data:
            return None
        
        return User.from_db_dict(user_data)
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username.
        
        Args:
            username: The username
            
        Returns:
            Optional[User]: The user, or None if not found
            
        Raises:
            DatabaseError: If there was an error retrieving the user
        """
        try:
            # Find user by username
            user_data = await self.db.users.find_one({"username": username})
            
            if not user_data:
                return None
            
            # Format user data
            formatted_data = self._format_data(user_data)
            
            return User.from_db_dict(formatted_data)
            
        except Exception as e:
            raise DatabaseError(f"Failed to get user by username: {e}")
    
    async def update_user(self, user_id: str, data: Dict[str, Any]) -> Optional[User]:
        """Update a user.
        
        Args:
            user_id: The user ID
            data: The data to update
            
        Returns:
            Optional[User]: The updated user, or None if not found
            
        Raises:
            DatabaseError: If there was an error updating the user
        """
        user_data = await self.update("users", user_id, data)
        
        if not user_data:
            return None
        
        return User.from_db_dict(user_data)
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            bool: True if the user was deleted, False otherwise
            
        Raises:
            DatabaseError: If there was an error deleting the user
        """
        return await self.delete("users", user_id)
    
    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination.
        
        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return
            
        Returns:
            List[User]: The users
            
        Raises:
            DatabaseError: If there was an error retrieving the users
        """
        try:
            users_data = await self.list(
                collection="users",
                skip=skip,
                limit=limit,
                sort={"username": 1}
            )
            
            return [User.from_db_dict(user_data) for user_data in users_data]
            
        except Exception as e:
            raise DatabaseError(f"Failed to get users: {e}")
    
    async def search_users(self, query: str, skip: int = 0, limit: int = 20) -> List[User]:
        """Search for users by username or full name.
        
        Args:
            query: The search query
            skip: Number of users to skip
            limit: Maximum number of users to return
            
        Returns:
            List[User]: The matching users
            
        Raises:
            DatabaseError: If there was an error searching for users
        """
        try:
            # Create text index for username and full_name
            try:
                await self.db.users.create_index([("username", "text"), ("full_name", "text")])
            except Exception:
                pass
            
            # Build search query
            search_query = {"$text": {"$search": query}}
            
            # Search users
            users_data = await self.list(
                collection="users",
                filters=search_query,
                skip=skip,
                limit=limit,
                sort={"score": {"$meta": "textScore"}}
            )
            
            return [User.from_db_dict(user_data) for user_data in users_data]
            
        except Exception as e:
            raise DatabaseError(f"Failed to search users: {e}")