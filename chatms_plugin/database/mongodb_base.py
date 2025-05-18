"""
MongoDB database handler for the ChatMS plugin - Base implementation.
"""

import asyncio
import datetime
import logging
from typing import Any, Dict, List, Optional, TypeVar, Union

import motor.motor_asyncio
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, TEXT

from ..config import Config
from ..exceptions import DatabaseError
from ..models.base import DatabaseModel
from .base import DatabaseHandler


logger = logging.getLogger(__name__)
T = TypeVar('T', bound=DatabaseModel)


class MongoDBHandler(DatabaseHandler):
    """Database handler for MongoDB using motor."""
    
    def __init__(self, config: Config):
        """Initialize the MongoDB handler.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.client = None
        self.db = None
        
        # Parse database URL
        db_url = config.database_url
        if not db_url.startswith("mongodb"):
            raise DatabaseError(f"Invalid MongoDB URL: {db_url}")
        
        # Get database name from URL
        db_name = db_url.split("/")[-1]
        if not db_name:
            db_name = "chatms"
        
        self.db_url = db_url
        self.db_name = db_name
    
    async def init(self) -> None:
        """Initialize the database connection."""
        try:
            # Connect to MongoDB
            self.client = motor.motor_asyncio.AsyncIOMotorClient(self.db_url)
            self.db = self.client[self.db_name]
            
            # Create indexes
            await self._create_indexes()
            
            logger.info(f"Connected to MongoDB database: {self.db_name}")
            
        except Exception as e:
            raise DatabaseError(f"Failed to connect to MongoDB: {e}")
    
    async def _create_indexes(self) -> None:
        """Create indexes for collections."""
        try:
            # Users collection indexes
            await self.db.users.create_index("username", unique=True)
            await self.db.users.create_index("email", unique=True)
            
            # Chats collection indexes
            await self.db.chats.create_index("members.user_id")
            
            # Messages collection indexes
            await self.db.messages.create_index("chat_id")
            await self.db.messages.create_index("sender_id")
            await self.db.messages.create_index([("content", TEXT)])
            await self.db.messages.create_index([("created_at", DESCENDING)])
            await self.db.messages.create_index([("chat_id", ASCENDING), ("created_at", DESCENDING)])
            
            logger.info("MongoDB indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise DatabaseError(f"Failed to create MongoDB indexes: {e}")
    
    async def close(self) -> None:
        """Close the database connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    # Helper methods
    
    def _convert_id(self, id: str) -> ObjectId:
        """Convert string ID to ObjectId.
        
        Args:
            id: String ID
            
        Returns:
            ObjectId: MongoDB ObjectId
        """
        try:
            return ObjectId(id)
        except Exception:
            # If id is not a valid ObjectId, use it as is
            return id
    
    def _prepare_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for MongoDB.
        
        Args:
            data: Data to prepare
            
        Returns:
            Dict[str, Any]: Prepared data
        """
        prepared_data = data.copy()
        
        # Convert string IDs to ObjectId
        if "_id" in prepared_data and isinstance(prepared_data["_id"], str):
            prepared_data["_id"] = self._convert_id(prepared_data["_id"])
        
        # Process nested objects
        for key, value in prepared_data.items():
            if isinstance(value, dict):
                prepared_data[key] = self._prepare_data(value)
            elif isinstance(value, list):
                prepared_data[key] = [
                    self._prepare_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
        
        return prepared_data
    
    def _format_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data from MongoDB.
        
        Args:
            data: Data to format
            
        Returns:
            Dict[str, Any]: Formatted data
        """
        if not data:
            return data
        
        formatted_data = data.copy()
        
        # Convert ObjectId to string
        if "_id" in formatted_data:
            formatted_data["id"] = str(formatted_data["_id"])
            del formatted_data["_id"]
        
        # Format nested documents
        for key, value in list(formatted_data.items()):
            if isinstance(value, dict):
                formatted_data[key] = self._format_data(value)
            elif isinstance(value, list):
                formatted_data[key] = [
                    self._format_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, ObjectId):
                formatted_data[key] = str(value)
        
        return formatted_data
    
    # Generic CRUD operations
    
    async def create(self, model: T) -> T:
        """Create a new record in the database.
        
        Args:
            model: The model to create
            
        Returns:
            T: The created model
            
        Raises:
            DatabaseError: If there was an error creating the record
        """
        try:
            collection = model.__class__.__name__.lower() + "s"
            data = model.to_db_dict()
            
            # Generate ID if not provided
            if "id" not in data:
                data["id"] = str(ObjectId())
            
            # Remove id and use it as _id
            id_value = data.pop("id")
            data["_id"] = self._convert_id(id_value)
            
            # Update timestamps
            now = datetime.datetime.now()
            data["created_at"] = now
            data["updated_at"] = now
            
            # Insert into database
            await self.db[collection].insert_one(data)
            
            # Return the model with ID
            result = model.dict()
            result["id"] = str(data["_id"])
            result["created_at"] = now
            result["updated_at"] = now
            
            return model.__class__(**result)
            
        except Exception as e:
            raise DatabaseError(f"Failed to create {model.__class__.__name__}: {e}")
    
    async def get(self, collection: str, id: str) -> Optional[Dict[str, Any]]:
        """Get a record by ID.
        
        Args:
            collection: The collection name
            id: The record ID
            
        Returns:
            Optional[Dict[str, Any]]: The record, or None if not found
            
        Raises:
            DatabaseError: If there was an error retrieving the record
        """
        try:
            # Convert ID to ObjectId
            obj_id = self._convert_id(id)
            
            # Get record
            record = await self.db[collection].find_one({"_id": obj_id})
            
            if not record:
                return None
            
            # Format record
            return self._format_data(record)
            
        except Exception as e:
            raise DatabaseError(f"Failed to get record from {collection}: {e}")
    
    async def update(self, collection: str, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record by ID.
        
        Args:
            collection: The collection name
            id: The record ID
            data: The data to update
            
        Returns:
            Optional[Dict[str, Any]]: The updated record, or None if not found
            
        Raises:
            DatabaseError: If there was an error updating the record
        """
        try:
            # Convert ID to ObjectId
            obj_id = self._convert_id(id)
            
            # Prepare data
            update_data = self._prepare_data(data.copy())
            
            # Remove id field if present
            if "id" in update_data:
                del update_data["id"]
            
            # Update timestamp
            update_data["updated_at"] = datetime.datetime.now()
            
            # Update record
            result = await self.db[collection].update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return None
            
            # Get updated record
            updated = await self.db[collection].find_one({"_id": obj_id})
            
            # Format record
            return self._format_data(updated)
            
        except Exception as e:
            raise DatabaseError(f"Failed to update record in {collection}: {e}")
    
    async def delete(self, collection: str, id: str) -> bool:
        """Delete a record by ID.
        
        Args:
            collection: The collection name
            id: The record ID
            
        Returns:
            bool: True if the record was deleted, False otherwise
            
        Raises:
            DatabaseError: If there was an error deleting the record
        """
        try:
            # Convert ID to ObjectId
            obj_id = self._convert_id(id)
            
            # Delete record
            result = await self.db[collection].delete_one({"_id": obj_id})
            
            return result.deleted_count > 0
            
        except Exception as e:
            raise DatabaseError(f"Failed to delete record from {collection}: {e}")
    
    async def list(self, collection: str, filters: Dict[str, Any] = None, 
                   skip: int = 0, limit: int = 100, 
                   sort: Dict[str, int] = None) -> List[Dict[str, Any]]:
        """List records with optional filtering, pagination, and sorting.
        
        Args:
            collection: The collection name
            filters: Optional filters
            skip: Number of records to skip
            limit: Maximum number of records to return
            sort: Sorting criteria
            
        Returns:
            List[Dict[str, Any]]: The records
            
        Raises:
            DatabaseError: If there was an error listing the records
        """
        try:
            # Prepare filters
            query = filters or {}
            query = self._prepare_data(query)
            
            # Prepare sort
            sort_criteria = sort or {"created_at": -1}
            
            # Convert sort to list of tuples
            sort_list = []
            for key, value in sort_criteria.items():
                sort_list.append((key, ASCENDING if value > 0 else DESCENDING))
            
            # Query records
            cursor = self.db[collection].find(query).skip(skip).limit(limit).sort(sort_list)
            
            # Get all records
            records = await cursor.to_list(length=limit)
            
            # Format records
            return [self._format_data(record) for record in records]
            
        except Exception as e:
            raise DatabaseError(f"Failed to list records from {collection}: {e}")
    
    async def count(self, collection: str, filters: Dict[str, Any] = None) -> int:
        """Count records with optional filtering.
        
        Args:
            collection: The collection name
            filters: Optional filters
            
        Returns:
            int: The number of records
            
        Raises:
            DatabaseError: If there was an error counting the records
        """
        try:
            # Prepare filters
            query = filters or {}
            query = self._prepare_data(query)
            
            # Count records
            return await self.db[collection].count_documents(query)
            
        except Exception as e:
            raise DatabaseError(f"Failed to count records in {collection}: {e}")