"""
Rate limiting utilities for the ChatMS plugin.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple, Union

from ..config import Config
from ..exceptions import RateLimitError


logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter implementation for controlling request rate.
    
    This class provides both in-memory and Redis-based rate limiting.
    """
    
    def __init__(self, config: Config, redis=None):
        """Initialize the rate limiter.
        
        Args:
            config: Configuration object
            redis: Redis client (optional)
        """
        self.config = config
        self.redis = redis
        self.in_memory_limits: Dict[str, Dict[str, Union[int, float]]] = {}
    
    async def check_rate_limit(self, key: str, limit: int, window: int = 60) -> Tuple[bool, Optional[int]]:
        """Check if a rate limit has been exceeded.
        
        Args:
            key: The rate limit key (usually user_id:action)
            limit: The maximum number of actions allowed in the time window
            window: The time window in seconds
            
        Returns:
            Tuple[bool, Optional[int]]: (is_limited, reset_time)
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        # Use Redis if available
        if self.redis:
            return await self._check_rate_limit_redis(key, limit, window)
        else:
            return await self._check_rate_limit_memory(key, limit, window)
    
    async def _check_rate_limit_redis(self, key: str, limit: int, window: int) -> Tuple[bool, Optional[int]]:
        """Check rate limit using Redis.
        
        Args:
            key: The rate limit key
            limit: The maximum number of actions allowed
            window: The time window in seconds
            
        Returns:
            Tuple[bool, Optional[int]]: (is_limited, reset_time)
        """
        # Ensure a consistent key format
        redis_key = f"rate_limit:{key}"
        
        # Increment counter
        current = await self.redis.incr(redis_key)
        
        # Set expiry if first increment
        if current == 1:
            await self.redis.expire(redis_key, window)
        
        # Get remaining time
        ttl = await self.redis.ttl(redis_key)
        
        # Check if limit exceeded
        if current > limit:
            return True, ttl
        
        return False, None
    
    async def _check_rate_limit_memory(self, key: str, limit: int, window: int) -> Tuple[bool, Optional[int]]:
        """Check rate limit using in-memory storage.
        
        Args:
            key: The rate limit key
            limit: The maximum number of actions allowed
            window: The time window in seconds
            
        Returns:
            Tuple[bool, Optional[int]]: (is_limited, reset_time)
        """
        now = time.time()
        
        # Initialize limit data if not exists
        if key not in self.in_memory_limits:
            self.in_memory_limits[key] = {
                "count": 0,
                "reset_at": now + window
            }
        
        # Get limit data
        limit_data = self.in_memory_limits[key]
        
        # Check if window has reset
        if now > limit_data["reset_at"]:
            # Reset counter and window
            limit_data["count"] = 1
            limit_data["reset_at"] = now + window
            return False, None
        
        # Increment counter
        limit_data["count"] += 1
        
        # Check if limit exceeded
        if limit_data["count"] > limit:
            reset_time = int(limit_data["reset_at"] - now)
            return True, reset_time
        
        return False, None
    
    async def rate_limit(self, key: str, limit: int, window: int = 60) -> None:
        """Apply rate limiting to an action.
        
        Args:
            key: The rate limit key (usually user_id:action)
            limit: The maximum number of actions allowed in the time window
            window: The time window in seconds
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        is_limited, reset_time = await self.check_rate_limit(key, limit, window)
        
        if is_limited:
            raise RateLimitError(
                message=f"Rate limit exceeded: {limit} requests per {window} seconds",
                reset_time=reset_time
            )
    
    async def clean_expired_limits(self) -> int:
        """Clean expired rate limits from memory.
        
        This is only needed for in-memory rate limiting.
        
        Returns:
            int: Number of expired limits cleaned
        """
        if self.redis:
            return 0  # Redis handles expiry automatically
        
        now = time.time()
        expired_keys = [
            key for key, data in self.in_memory_limits.items()
            if now > data["reset_at"]
        ]
        
        for key in expired_keys:
            del self.in_memory_limits[key]
        
        return len(expired_keys)


class RateLimitManager:
    """Rate limit manager for different types of rate limits."""
    
    def __init__(self, config: Config, redis=None):
        """Initialize the rate limit manager.
        
        Args:
            config: Configuration object
            redis: Redis client (optional)
        """
        self.config = config
        self.limiter = RateLimiter(config, redis)
        self.cleanup_task = None
    
    async def init(self) -> None:
        """Initialize the rate limit manager."""
        # Start cleanup task
        if not self.limiter.redis:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info("Rate limit manager initialized with in-memory storage")
        else:
            logger.info("Rate limit manager initialized with Redis storage")
    
    async def close(self) -> None:
        """Close the rate limit manager."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean expired rate limits."""
        while True:
            try:
                # Sleep first to avoid immediate cleanup on startup
                await asyncio.sleep(60)
                
                # Clean expired limits
                cleaned = await self.limiter.clean_expired_limits()
                
                if cleaned > 0:
                    logger.debug(f"Cleaned {cleaned} expired rate limits")
                    
            except asyncio.CancelledError:
                # Task was cancelled, exit
                break
            except Exception as e:
                logger.error(f"Error in rate limit cleanup task: {e}")
                # Sleep briefly to avoid tight loop in case of persistent error
                await asyncio.sleep(5)
    
    async def limit_messages(self, user_id: str) -> None:
        """Rate limit message sending.
        
        Args:
            user_id: The user ID
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        key = f"{user_id}:messages"
        limit = self.config.rate_limit_messages_per_minute
        
        await self.limiter.rate_limit(key, limit, 60)
    
    async def limit_login_attempts(self, username: str) -> None:
        """Rate limit login attempts.
        
        Args:
            username: The username
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        key = f"{username}:login"
        limit = 5  # Maximum 5 login attempts per 15 minutes
        
        await self.limiter.rate_limit(key, limit, 900)
    
    async def limit_registration(self, ip_address: str) -> None:
        """Rate limit user registration.
        
        Args:
            ip_address: The IP address
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        key = f"{ip_address}:registration"
        limit = 3  # Maximum 3 registrations per day
        
        await self.limiter.rate_limit(key, limit, 86400)
    
    async def limit_file_uploads(self, user_id: str) -> None:
        """Rate limit file uploads.
        
        Args:
            user_id: The user ID
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        key = f"{user_id}:uploads"
        limit = 20  # Maximum 20 file uploads per hour
        
        await self.limiter.rate_limit(key, limit, 3600)
    
    async def limit_chat_creation(self, user_id: str) -> None:
        """Rate limit chat creation.
        
        Args:
            user_id: The user ID
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        key = f"{user_id}:chat_creation"
        limit = 10  # Maximum 10 chats per hour
        
        await self.limiter.rate_limit(key, limit, 3600)
    
    async def limit_api_requests(self, user_id: str, endpoint: str) -> None:
        """Rate limit API requests to a specific endpoint.
        
        Args:
            user_id: The user ID
            endpoint: The API endpoint
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        key = f"{user_id}:api:{endpoint}"
        
        # Different limits for different endpoints
        if endpoint in ["search", "get_chat_messages"]:
            limit = 30  # Higher limit for read operations
            window = 60
        else:
            limit = 10  # Lower limit for write operations
            window = 60
        
        await self.limiter.rate_limit(key, limit, window)
    
    async def limit_custom(self, key: str, limit: int, window: int = 60) -> None:
        """Apply a custom rate limit.
        
        Args:
            key: The rate limit key
            limit: The maximum number of actions allowed
            window: The time window in seconds
            
        Raises:
            RateLimitError: If the rate limit is exceeded
        """
        await self.limiter.rate_limit(key, limit, window)