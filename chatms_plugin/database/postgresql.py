"""
PostgreSQL database implementation for the ChatMS plugin.
This is a partial implementation showing the structure of how the SQLAlchemy database handler would work.
"""

import asyncio
import datetime
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, TypeVar, Union

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.orm import relationship, sessionmaker

from ..config import Config, UserRole
from ..exceptions import DatabaseError
from ..models.base import DatabaseModel
from ..models.chat import Chat
from ..models.message import Message, Reaction
from ..models.user import User
from .base import DatabaseHandler, T
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)
Base = declarative_base()


# Define SQLAlchemy models
class SQLUser(Base):
    """SQLAlchemy model for users."""
    
    __tablename__ = "users"
    
    id = sa.Column(sa.String, primary_key=True)
    username = sa.Column(sa.String, unique=True, nullable=False)
    email = sa.Column(sa.String, unique=True, nullable=False)
    hashed_password = sa.Column(sa.String, nullable=False)
    full_name = sa.Column(sa.String, nullable=True)
    last_seen = sa.Column(sa.DateTime, nullable=True)
    status = sa.Column(sa.String, default="offline")
    avatar_url = sa.Column(sa.String, nullable=True)
    is_active = sa.Column(sa.Boolean, default=True)
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.now)
    updated_at = sa.Column(sa.DateTime, nullable=True)
    
    chats = relationship("SQLChatMember", back_populates="user")
    messages = relationship("SQLMessage", back_populates="sender")


class SQLChat(Base):
    """SQLAlchemy model for chats."""
    
    __tablename__ = "chats"
    
    id = sa.Column(sa.String, primary_key=True)
    name = sa.Column(sa.String, nullable=True)
    description = sa.Column(sa.String, nullable=True)
    icon_url = sa.Column(sa.String, nullable=True)
    chat_type = sa.Column(sa.String, nullable=False)
    is_encrypted = sa.Column(sa.Boolean, default=False)
    chat_metadata = sa.Column(sa.JSON, default=dict)
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.now)
    updated_at = sa.Column(sa.DateTime, nullable=True)
    
    members = relationship("SQLChatMember", back_populates="chat")
    messages = relationship("SQLMessage", back_populates="chat")


class SQLChatMember(Base):
    """SQLAlchemy model for chat members."""
    
    __tablename__ = "chat_members"
    
    chat_id = sa.Column(sa.String, sa.ForeignKey("chats.id"), primary_key=True)
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), primary_key=True)
    role = sa.Column(sa.String, default="member")
    joined_at = sa.Column(sa.DateTime, default=datetime.datetime.now)
    is_muted = sa.Column(sa.Boolean, default=False)
    last_read_message_id = sa.Column(sa.String, nullable=True)
    typing_at = sa.Column(sa.DateTime, nullable=True)
    
    chat = relationship("SQLChat", back_populates="members")
    user = relationship("SQLUser", back_populates="chats")


class SQLMessage(Base):
    """SQLAlchemy model for messages."""
    
    __tablename__ = "messages"
    
    id = sa.Column(sa.String, primary_key=True)
    chat_id = sa.Column(sa.String, sa.ForeignKey("chats.id"), nullable=False)
    sender_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False)
    content = sa.Column(sa.Text, nullable=True)
    message_type = sa.Column(sa.String, default="text")
    status = sa.Column(sa.String, default="sending")
    reply_to_id = sa.Column(sa.String, nullable=True)
    forwarded_from_id = sa.Column(sa.String, nullable=True)
    edited_at = sa.Column(sa.DateTime, nullable=True)
    delivered_at = sa.Column(sa.DateTime, nullable=True)
    read_at = sa.Column(sa.DateTime, nullable=True)
    is_pinned = sa.Column(sa.Boolean, default=False)
    is_deleted = sa.Column(sa.Boolean, default=False)
    delete_for_everyone = sa.Column(sa.Boolean, default=False)
    chat_metadata = sa.Column(sa.JSON, default=dict)    
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.now)
    updated_at = sa.Column(sa.DateTime, nullable=True)
    
    chat = relationship("SQLChat", back_populates="messages")
    sender = relationship("SQLUser", back_populates="messages")
    attachments = relationship("SQLAttachment", back_populates="message")
    reactions = relationship("SQLReaction", back_populates="message")
    mentions = relationship("SQLMention", back_populates="message")


class SQLAttachment(Base):
    """SQLAlchemy model for message attachments."""
    
    __tablename__ = "attachments"
    
    id = sa.Column(sa.String, primary_key=True)
    message_id = sa.Column(sa.String, sa.ForeignKey("messages.id"), nullable=False)
    file_name = sa.Column(sa.String, nullable=False)
    file_size = sa.Column(sa.Integer, nullable=False)
    file_type = sa.Column(sa.String, nullable=False)
    file_url = sa.Column(sa.String, nullable=False)
    thumbnail_url = sa.Column(sa.String, nullable=True)
    width = sa.Column(sa.Integer, nullable=True)
    height = sa.Column(sa.Integer, nullable=True)
    duration = sa.Column(sa.Integer, nullable=True)
    chat_metadata = sa.Column(sa.JSON, default=dict)    
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.now)
    
    message = relationship("SQLMessage", back_populates="attachments")


class SQLReaction(Base):
    """SQLAlchemy model for message reactions."""
    
    __tablename__ = "reactions"
    
    id = sa.Column(sa.String, primary_key=True)
    message_id = sa.Column(sa.String, sa.ForeignKey("messages.id"), nullable=False)
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False)
    reaction_type = sa.Column(sa.String, nullable=False)
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.now)
    
    message = relationship("SQLMessage", back_populates="reactions")
    user = relationship("SQLUser")
    
    __table_args__ = (
        sa.UniqueConstraint('message_id', 'user_id', 'reaction_type'),
    )


class SQLMention(Base):
    """SQLAlchemy model for message mentions."""
    
    __tablename__ = "mentions"
    
    id = sa.Column(sa.String, primary_key=True)
    message_id = sa.Column(sa.String, sa.ForeignKey("messages.id"), nullable=False)
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False)
    offset = sa.Column(sa.Integer, nullable=False)
    length = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.now)
    
    message = relationship("SQLMessage", back_populates="mentions")
    user = relationship("SQLUser")


class PostgreSQLHandler(DatabaseHandler):
    """Database handler for PostgreSQL using SQLAlchemy."""
    
    def __init__(self, config: Config):
        """Initialize the PostgreSQL handler.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.engine = None
        self.session_maker = None
        
        # Validate database URL
        db_url = config.database_url
        if not db_url.startswith("postgresql"):
            raise DatabaseError(f"Invalid PostgreSQL URL: {db_url}")
        
        self.db_url = db_url
    
    async def init(self) -> None:
        """Initialize the database connection."""
        try:
            # Create async engine
            self.engine = create_async_engine(
                self.db_url,
                echo=False,
                future=True
            )
            
            # Create session maker
            self.session_maker = sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("PostgreSQL database initialized")
            
        except Exception as e:
            raise DatabaseError(f"Failed to initialize PostgreSQL database: {e}")
    
    async def close(self) -> None:
        """Close the database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("PostgreSQL database connection closed")
    
    async def _get_session(self) -> AsyncSession:
        """Get a database session.
        
        Returns:
            AsyncSession: Database session
        """
        if not self.session_maker:
            raise DatabaseError("Database not initialized")
        
        return self.session_maker()
    
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
            # Generate ID if not provided
            if not hasattr(model, "id") or not model.id:
                model.id = str(uuid.uuid4())
            
            # Get model table name
            table_name = model.__class__.__name__.lower() + "s"
            
            # Convert model to dictionary
            data = model.to_db_dict()
            
            # Process according to model type
            if isinstance(model, User):
                return await self.create_user(model)
            elif isinstance(model, Chat):
                return await self.create_chat(model)
            elif isinstance(model, Message):
                # Need to implement create_message
                raise NotImplementedError("PostgreSQL handler create_message not implemented")
            else:
                # Generic implementation
                async with self._get_session() as session:
                    # Create SQL object
                    sql_obj = self._get_sql_class(table_name)(**data)
                    
                    # Add to session
                    session.add(sql_obj)
                    await session.commit()
                    
                    # Refresh to get generated values
                    await session.refresh(sql_obj)
                    
                    # Convert back to model
                    result = self._convert_to_model(sql_obj, model.__class__)
                    
                    return result
            
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
            # Handle specific collections
            if collection == "users":
                user = await self.get_user(id)
                return user.dict() if user else None
            elif collection == "chats":
                chat = await self.get_chat(id)
                return chat.dict() if chat else None
            elif collection == "messages":
                # Need to implement get_message
                raise NotImplementedError("PostgreSQL handler get_message not implemented")
            
            # Get SQL class
            sql_class = self._get_sql_class(collection)
            
            async with self._get_session() as session:
                # Query record
                result = await session.execute(
                    select(sql_class).where(sql_class.id == id)
                )
                
                # Get first result
                obj = result.scalars().first()
                
                if not obj:
                    return None
                
                # Convert to dictionary
                return self._sql_obj_to_dict(obj)
            
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
            # Handle specific collections
            if collection == "users":
                user = await self.update_user(id, data)
                return user.dict() if user else None
            elif collection == "chats":
                # Need to implement update_chat
                raise NotImplementedError("PostgreSQL handler update_chat not implemented")
            elif collection == "messages":
                # Need to implement update_message
                raise NotImplementedError("PostgreSQL handler update_message not implemented")
            
            # Get SQL class
            sql_class = self._get_sql_class(collection)
            
            async with self._get_session() as session:
                # Query record
                result = await session.execute(
                    select(sql_class).where(sql_class.id == id)
                )
                
                # Get first result
                obj = result.scalars().first()
                
                if not obj:
                    return None
                
                # Update fields
                for key, value in data.items():
                    if hasattr(obj, key):
                        setattr(obj, key, value)
                
                # Set updated_at timestamp
                if hasattr(obj, "updated_at"):
                    setattr(obj, "updated_at", datetime.datetime.now())
                
                # Commit changes
                await session.commit()
                
                # Refresh to get updated values
                await session.refresh(obj)
                
                # Convert to dictionary
                return self._sql_obj_to_dict(obj)
            
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
            # Get SQL class
            sql_class = self._get_sql_class(collection)
            
            async with self._get_session() as session:
                # Query record
                result = await session.execute(
                    select(sql_class).where(sql_class.id == id)
                )
                
                # Get first result
                obj = result.scalars().first()
                
                if not obj:
                    return False
                
                # Delete record
                await session.delete(obj)
                await session.commit()
                
                return True
            
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
            # Get SQL class
            sql_class = self._get_sql_class(collection)
            
            async with self._get_session() as session:
                # Build query
                query = select(sql_class)
                
                # Apply filters
                if filters:
                    for key, value in filters.items():
                        if hasattr(sql_class, key):
                            query = query.where(getattr(sql_class, key) == value)
                
                # Apply sorting
                if sort:
                    order_by = []
                    for key, direction in sort.items():
                        if hasattr(sql_class, key):
                            column = getattr(sql_class, key)
                            if direction < 0:
                                column = column.desc()
                            order_by.append(column)
                    
                    if order_by:
                        query = query.order_by(*order_by)
                
                # Apply pagination
                query = query.offset(skip).limit(limit)
                
                # Execute query
                result = await session.execute(query)
                
                # Get all results
                objs = result.scalars().all()
                
                # Convert to dictionaries
                return [self._sql_obj_to_dict(obj) for obj in objs]
            
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
            # Get SQL class
            sql_class = self._get_sql_class(collection)
            
            async with self._get_session() as session:
                # Build query
                query = select(sa.func.count(sql_class.id))
                
                # Apply filters
                if filters:
                    for key, value in filters.items():
                        if hasattr(sql_class, key):
                            query = query.where(getattr(sql_class, key) == value)
                
                # Execute query
                result = await session.execute(query)
                
                # Get count
                count = result.scalar()
                
                return count
            
        except Exception as e:
            raise DatabaseError(f"Failed to count records in {collection}: {e}")
    
    # User operations
    
    async def create_user(self, user: User) -> User:
        """Create a new user.
        
        Args:
            user: The user to create
            
        Returns:
            User: The created user
        """
        try:
            async with self._get_session() as session:
                # Create SQL user
                sql_user = SQLUser(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    full_name=user.full_name,
                    last_seen=user.last_seen,
                    status=user.status,
                    avatar_url=user.avatar_url,
                    is_active=user.is_active,
                    created_at=user.created_at,
                    updated_at=user.updated_at
                )
                
                # Add to session
                session.add(sql_user)
                await session.commit()
                
                # Refresh to get generated values
                await session.refresh(sql_user)
                
                # Convert to user model
                return self._convert_to_user(sql_user)
            
        except Exception as e:
            raise DatabaseError(f"Failed to create user: {e}")
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID.
        
        Args:
            user_id: The user ID
            
        Returns:
            Optional[User]: The user, or None if not found
        """
        try:
            async with self._get_session() as session:
                # Query user
                result = await session.execute(
                    select(SQLUser).where(SQLUser.id == user_id)
                )
                
                # Get first result
                sql_user = result.scalars().first()
                
                if not sql_user:
                    return None
                
                # Convert to user model
                return self._convert_to_user(sql_user)
            
        except Exception as e:
            raise DatabaseError(f"Failed to get user: {e}")
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username.
        
        Args:
            username: The username
            
        Returns:
            Optional[User]: The user, or None if not found
        """
        try:
            async with self._get_session() as session:
                # Query user
                result = await session.execute(
                    select(SQLUser).where(SQLUser.username == username)
                )
                
                # Get first result
                sql_user = result.scalars().first()
                
                if not sql_user:
                    return None
                
                # Convert to user model
                return self._convert_to_user(sql_user)
            
        except Exception as e:
            raise DatabaseError(f"Failed to get user by username: {e}")
    
    async def update_user(self, user_id: str, data: Dict[str, Any]) -> Optional[User]:
        """Update a user.
        
        Args:
            user_id: The user ID
            data: The data to update
            
        Returns:
            Optional[User]: The updated user, or None if not found
        """
        try:
            async with self._get_session() as session:
                # Query user
                result = await session.execute(
                    select(SQLUser).where(SQLUser.id == user_id)
                )
                
                # Get first result
                sql_user = result.scalars().first()
                
                if not sql_user:
                    return None
                
                # Update fields
                for key, value in data.items():
                    if hasattr(sql_user, key):
                        setattr(sql_user, key, value)
                
                # Set updated_at timestamp
                sql_user.updated_at = datetime.datetime.now()
                
                # Commit changes
                await session.commit()
                
                # Refresh to get updated values
                await session.refresh(sql_user)
                
                # Convert to user model
                return self._convert_to_user(sql_user)
            
        except Exception as e:
            raise DatabaseError(f"Failed to update user: {e}")
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            bool: True if the user was deleted, False otherwise
        """
        try:
            async with self._get_session() as session:
                # Query user
                result = await session.execute(
                    select(SQLUser).where(SQLUser.id == user_id)
                )
                
                # Get first result
                sql_user = result.scalars().first()
                
                if not sql_user:
                    return False
                
                # Delete user
                await session.delete(sql_user)
                await session.commit()
                
                return True
            
        except Exception as e:
            raise DatabaseError(f"Failed to delete user: {e}")
    
    # Chat operations
    
    async def create_chat(self, chat: Chat) -> Chat:
        """Create a new chat.
        
        Args:
            chat: The chat to create
            
        Returns:
            Chat: The created chat
        """
        try:
            async with self._get_session() as session:
                # Create SQL chat
                sql_chat = SQLChat(
                    id=chat.id,
                    name=chat.name,
                    description=chat.description,
                    icon_url=chat.icon_url,
                    chat_type=chat.chat_type.value,
                    is_encrypted=chat.is_encrypted,
                    metadata=chat.metadata,
                    created_at=chat.created_at,
                    updated_at=chat.updated_at
                )
                
                # Add to session
                session.add(sql_chat)
                
                # Add members
                for member in chat.members:
                    sql_member = SQLChatMember(
                        chat_id=chat.id,
                        user_id=member.user_id,
                        role=member.role.value,
                        joined_at=member.joined_at,
                        is_muted=member.is_muted,
                        last_read_message_id=member.last_read_message_id,
                        typing_at=member.typing_at
                    )
                    session.add(sql_member)
                
                await session.commit()
                
                # Refresh to get generated values
                await session.refresh(sql_chat)
                
                # Query the chat with members
                result = await session.execute(
                    select(SQLChat)
                    .options(sa.orm.selectinload(SQLChat.members))
                    .where(SQLChat.id == sql_chat.id)
                )
                
                # Get the chat with members
                sql_chat_with_members = result.scalars().first()
                
                # Convert to chat model
                return self._convert_to_chat(sql_chat_with_members)
            
        except Exception as e:
            raise DatabaseError(f"Failed to create chat: {e}")
    
    async def get_chat(self, chat_id: str) -> Optional[Chat]:
        """Get a chat by ID.
        
        Args:
            chat_id: The chat ID
            
        Returns:
            Optional[Chat]: The chat, or None if not found
        """
        try:
            async with self._get_session() as session:
                # Query chat with members
                result = await session.execute(
                    select(SQLChat)
                    .options(sa.orm.selectinload(SQLChat.members))
                    .where(SQLChat.id == chat_id)
                )
                
                # Get first result
                sql_chat = result.scalars().first()
                
                if not sql_chat:
                    return None
                
                # Convert to chat model
                return self._convert_to_chat(sql_chat)
            
        except Exception as e:
            raise DatabaseError(f"Failed to get chat: {e}")
    
    # Helper methods
    
    def _get_sql_class(self, collection: str) -> Any:
        """Get the SQL class for a collection.
        
        Args:
            collection: The collection name
            
        Returns:
            Any: The SQL class
            
        Raises:
            ValueError: If the collection is invalid
        """
        # Map collection names to SQL classes
        collections = {
            "users": SQLUser,
            "chats": SQLChat,
            "chat_members": SQLChatMember,
            "messages": SQLMessage,
            "attachments": SQLAttachment,
            "reactions": SQLReaction,
            "mentions": SQLMention
        }
        
        if collection not in collections:
            raise ValueError(f"Invalid collection: {collection}")
        
        return collections[collection]
    
    def _sql_obj_to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert a SQL object to a dictionary.
        
        Args:
            obj: The SQL object
            
        Returns:
            Dict[str, Any]: The object as a dictionary
        """
        # Get object attributes
        data = {}
        for key in obj.__table__.columns.keys():
            value = getattr(obj, key)
            
            # Convert datetime objects to ISO format
            if isinstance(value, datetime.datetime):
                value = value.isoformat()
            
            data[key] = value
        
        return data
    
    def _convert_to_model(self, sql_obj: Any, model_class: Any) -> Any:
        """Convert a SQL object to a model.
        
        Args:
            sql_obj: The SQL object
            model_class: The model class
            
        Returns:
            Any: The model
        """
        # Convert to dictionary
        data = self._sql_obj_to_dict(sql_obj)
        
        # Create model from dictionary
        return model_class(**data)
    
    def _convert_to_user(self, sql_user: SQLUser) -> User:
        """Convert a SQL user to a User model.
        
        Args:
            sql_user: The SQL user
            
        Returns:
            User: The User model
        """
        return User(
            id=sql_user.id,
            username=sql_user.username,
            email=sql_user.email,
            hashed_password=sql_user.hashed_password,
            full_name=sql_user.full_name,
            last_seen=sql_user.last_seen,
            status=sql_user.status,
            avatar_url=sql_user.avatar_url,
            is_active=sql_user.is_active,
            created_at=sql_user.created_at,
            updated_at=sql_user.updated_at
        )
    
    def _convert_to_chat(self, sql_chat: SQLChat) -> Chat:
        """Convert a SQL chat to a Chat model.
        
        Args:
            sql_chat: The SQL chat
            
        Returns:
            Chat: The Chat model
        """
        # Convert members
        members = []
        for sql_member in sql_chat.members:
            from ..models.user import UserInChat
            
            member = UserInChat(
                user_id=sql_member.user_id,
                role=UserRole(sql_member.role),
                joined_at=sql_member.joined_at,
                is_muted=sql_member.is_muted,
                last_read_message_id=sql_member.last_read_message_id,
                typing_at=sql_member.typing_at
            )
            members.append(member)
        
        # Create chat model
        from ..config import ChatType
        
        return Chat(
            id=sql_chat.id,
            name=sql_chat.name,
            description=sql_chat.description,
            icon_url=sql_chat.icon_url,
            chat_type=ChatType(sql_chat.chat_type),
            is_encrypted=sql_chat.is_encrypted,
            metadata=sql_chat.metadata,
            members=members,
            created_at=sql_chat.created_at,
            updated_at=sql_chat.updated_at
        )