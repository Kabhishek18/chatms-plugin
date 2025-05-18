"""
Analytics service for the ChatMS plugin.
"""

import datetime
import json
import logging
from typing import Any, Dict, List, Optional, Set, Union

from ..config import Config
from ..exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class AnalyticsService:
    """Tracks usage metrics and performance statistics for the chat system."""
    
    def __init__(self, config: Config):
        """Initialize the analytics service.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.enabled = config.enable_analytics
        self.redis = None
        self._counters = {}
        self._timers = {}
    
    async def init(self, redis) -> None:
        """Initialize the analytics service.
        
        Args:
            redis: Redis connection
        """
        self.redis = redis
        logger.info("Analytics service initialized")
    
    async def track_event(self, event_type: str, event_data: Dict[str, Any] = None) -> None:
        """Track an event.
        
        Args:
            event_type: The type of event
            event_data: Additional event data
        """
        if not self.enabled:
            return
        
        # Prepare event data
        event = {
            "type": event_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "data": event_data or {}
        }
        
        try:
            # Store event in Redis
            if self.redis:
                await self.redis.lpush("chatms:analytics:events", json.dumps(event))
                await self.redis.ltrim("chatms:analytics:events", 0, 9999)  # Keep last 10,000 events
            
            # Increment counter
            counter_key = f"event:{event_type}"
            self._increment_counter(counter_key)
            
            # Log event
            logger.debug(f"Tracked event: {event_type}")
        except Exception as e:
            logger.error(f"Failed to track event: {e}")
    
    async def track_message(self, message_id: str, chat_id: str, sender_id: str, 
                          message_type: str, size: int) -> None:
        """Track a message.
        
        Args:
            message_id: The message ID
            chat_id: The chat ID
            sender_id: The sender ID
            message_type: The message type
            size: The message size in bytes
        """
        if not self.enabled:
            return
        
        await self.track_event("message_sent", {
            "message_id": message_id,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "message_type": message_type,
            "size": size
        })
        
        try:
            # Increment counters
            self._increment_counter("messages:total")
            self._increment_counter(f"messages:by_type:{message_type}")
            self._increment_counter(f"messages:by_chat:{chat_id}")
            self._increment_counter(f"messages:by_user:{sender_id}")
            
            # Update size metrics
            self._increment_counter("messages:total_size", size)
            self._increment_counter(f"messages:by_type:{message_type}:size", size)
            
            # Store hourly metrics
            hour = datetime.datetime.now().strftime("%Y-%m-%d-%H")
            self._increment_counter(f"messages:by_hour:{hour}")
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", "messages:total", 1)
                pipeline.hincrby("chatms:analytics:counters", f"messages:by_type:{message_type}", 1)
                pipeline.hincrby("chatms:analytics:counters", f"messages:by_chat:{chat_id}", 1)
                pipeline.hincrby("chatms:analytics:counters", f"messages:by_user:{sender_id}", 1)
                pipeline.hincrby("chatms:analytics:counters", "messages:total_size", size)
                pipeline.hincrby("chatms:analytics:counters", f"messages:by_hour:{hour}", 1)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track message metrics: {e}")
    
    async def track_chat_created(self, chat_id: str, creator_id: str, chat_type: str) -> None:
        """Track chat creation.
        
        Args:
            chat_id: The chat ID
            creator_id: The creator ID
            chat_type: The chat type
        """
        if not self.enabled:
            return
        
        await self.track_event("chat_created", {
            "chat_id": chat_id,
            "creator_id": creator_id,
            "chat_type": chat_type
        })
        
        try:
            # Increment counters
            self._increment_counter("chats:total")
            self._increment_counter(f"chats:by_type:{chat_type}")
            self._increment_counter(f"chats:by_user:{creator_id}")
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", "chats:total", 1)
                pipeline.hincrby("chatms:analytics:counters", f"chats:by_type:{chat_type}", 1)
                pipeline.hincrby("chatms:analytics:counters", f"chats:by_user:{creator_id}", 1)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track chat creation metrics: {e}")
    
    async def track_user_registered(self, user_id: str) -> None:
        """Track user registration.
        
        Args:
            user_id: The user ID
        """
        if not self.enabled:
            return
        
        await self.track_event("user_registered", {
            "user_id": user_id
        })
        
        try:
            # Increment counter
            self._increment_counter("users:total")
            
            # Store registration date
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            self._increment_counter(f"users:by_date:{date}")
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", "users:total", 1)
                pipeline.hincrby("chatms:analytics:counters", f"users:by_date:{date}", 1)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track user registration metrics: {e}")
    
    async def track_auth_success(self, user_id: str) -> None:
        """Track successful authentication.
        
        Args:
            user_id: The user ID
        """
        if not self.enabled:
            return
        
        await self.track_event("auth_success", {
            "user_id": user_id
        })
        
        try:
            # Increment counter
            self._increment_counter("auth:success")
            self._increment_counter(f"auth:success:by_user:{user_id}")
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", "auth:success", 1)
                pipeline.hincrby("chatms:analytics:counters", f"auth:success:by_user:{user_id}", 1)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track authentication metrics: {e}")
    
    async def track_auth_failure(self, username: str, reason: str) -> None:
        """Track failed authentication.
        
        Args:
            username: The username
            reason: The failure reason
        """
        if not self.enabled:
            return
        
        await self.track_event("auth_failure", {
            "username": username,
            "reason": reason
        })
        
        try:
            # Increment counter
            self._increment_counter("auth:failure")
            self._increment_counter(f"auth:failure:by_reason:{reason}")
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", "auth:failure", 1)
                pipeline.hincrby("chatms:analytics:counters", f"auth:failure:by_reason:{reason}", 1)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track authentication failure metrics: {e}")
    
    async def track_file_uploaded(self, file_id: str, user_id: str, file_type: str, size: int) -> None:
        """Track file upload.
        
        Args:
            file_id: The file ID
            user_id: The user ID
            file_type: The file type
            size: The file size in bytes
        """
        if not self.enabled:
            return
        
        await self.track_event("file_uploaded", {
            "file_id": file_id,
            "user_id": user_id,
            "file_type": file_type,
            "size": size
        })
        
        try:
            # Increment counters
            self._increment_counter("files:total")
            self._increment_counter(f"files:by_type:{file_type}")
            self._increment_counter(f"files:by_user:{user_id}")
            
            # Update size metrics
            self._increment_counter("files:total_size", size)
            self._increment_counter(f"files:by_type:{file_type}:size", size)
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", "files:total", 1)
                pipeline.hincrby("chatms:analytics:counters", f"files:by_type:{file_type}", 1)
                pipeline.hincrby("chatms:analytics:counters", f"files:by_user:{user_id}", 1)
                pipeline.hincrby("chatms:analytics:counters", "files:total_size", size)
                pipeline.hincrby("chatms:analytics:counters", f"files:by_type:{file_type}:size", size)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track file upload metrics: {e}")
    
    async def track_error(self, error_type: str, error_message: str, 
                        user_id: Optional[str] = None) -> None:
        """Track an error.
        
        Args:
            error_type: The error type
            error_message: The error message
            user_id: The user ID (optional)
        """
        if not self.enabled:
            return
        
        event_data = {
            "error_type": error_type,
            "error_message": error_message
        }
        
        if user_id:
            event_data["user_id"] = user_id
        
        await self.track_event("error", event_data)
        
        try:
            # Increment counter
            self._increment_counter("errors:total")
            self._increment_counter(f"errors:by_type:{error_type}")
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", "errors:total", 1)
                pipeline.hincrby("chatms:analytics:counters", f"errors:by_type:{error_type}", 1)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track error metrics: {e}")
    
    def start_timer(self, timer_name: str) -> None:
        """Start a timer for measuring operation duration.
        
        Args:
            timer_name: The timer name
        """
        if not self.enabled:
            return
        
        self._timers[timer_name] = datetime.datetime.now()
    
    async def stop_timer(self, timer_name: str, additional_data: Dict[str, Any] = None) -> Optional[float]:
        """Stop a timer and record the duration.
        
        Args:
            timer_name: The timer name
            additional_data: Additional data to include with the timing event
            
        Returns:
            Optional[float]: The duration in milliseconds, or None if the timer wasn't started
        """
        if not self.enabled or timer_name not in self._timers:
            return None
        
        # Calculate duration
        start_time = self._timers.pop(timer_name)
        end_time = datetime.datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        # Track event
        event_data = {
            "timer_name": timer_name,
            "duration_ms": duration_ms
        }
        
        if additional_data:
            event_data.update(additional_data)
        
        await self.track_event("timing", event_data)
        
        try:
            # Update timing metrics
            self._increment_counter(f"timing:{timer_name}:count")
            self._increment_counter(f"timing:{timer_name}:total_ms", duration_ms)
            
            # Calculate average
            count = self._get_counter(f"timing:{timer_name}:count")
            total = self._get_counter(f"timing:{timer_name}:total_ms")
            avg = total / count if count > 0 else 0
            
            # Store in Redis for persistence
            if self.redis:
                pipeline = self.redis.pipeline()
                pipeline.hincrby("chatms:analytics:counters", f"timing:{timer_name}:count", 1)
                pipeline.hincrbyfloat("chatms:analytics:counters", f"timing:{timer_name}:total_ms", duration_ms)
                pipeline.hset("chatms:analytics:values", f"timing:{timer_name}:avg_ms", avg)
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to track timing metrics: {e}")
        
        return duration_ms
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current analytics statistics.
        
        Returns:
            Dict[str, Any]: Current statistics
        """
        if not self.enabled:
            return {}
        
        stats = {
            "counters": self._counters.copy(),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        if self.redis:
            try:
                # Get counters from Redis
                redis_counters = await self.redis.hgetall("chatms:analytics:counters")
                redis_values = await self.redis.hgetall("chatms:analytics:values")
                
                # Convert Redis counters to dictionary
                counters = {
                    k.decode(): int(v.decode()) 
                    for k, v in redis_counters.items()
                }
                
                # Convert Redis values to dictionary
                values = {
                    k.decode(): float(v.decode()) 
                    for k, v in redis_values.items()
                }
                
                # Merge with in-memory counters
                stats["counters"].update(counters)
                stats["values"] = values
            except Exception as e:
                logger.error(f"Failed to get Redis analytics data: {e}")
        
        return stats
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get analytics statistics for a specific user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Dict[str, Any]: User statistics
        """
        if not self.enabled:
            return {}
        
        stats = {
            "user_id": user_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add user-specific counters
        user_counters = {}
        
        for key, value in self._counters.items():
            if f":by_user:{user_id}" in key:
                # Extract metric name from counter key
                metric = key.split(f":by_user:{user_id}")[0]
                user_counters[metric] = value
        
        stats["counters"] = user_counters
        
        if self.redis:
            try:
                # Get all counters from Redis
                redis_counters = await self.redis.hgetall("chatms:analytics:counters")
                
                # Filter for user-specific counters
                for k, v in redis_counters.items():
                    key = k.decode()
                    if f":by_user:{user_id}" in key:
                        metric = key.split(f":by_user:{user_id}")[0]
                        user_counters[metric] = int(v.decode())
            except Exception as e:
                logger.error(f"Failed to get Redis user analytics data: {e}")
        
        return stats
    
    def _increment_counter(self, key: str, value: Union[int, float] = 1) -> None:
        """Increment an in-memory counter.
        
        Args:
            key: The counter key
            value: The value to increment by
        """
        if key not in self._counters:
            self._counters[key] = 0
        
        self._counters[key] += value
    
    def _get_counter(self, key: str) -> Union[int, float]:
        """Get an in-memory counter value.
        
        Args:
            key: The counter key
            
        Returns:
            Union[int, float]: The counter value, or 0 if not found
        """
        return self._counters.get(key, 0)