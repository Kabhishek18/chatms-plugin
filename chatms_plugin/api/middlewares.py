# chatms-plugin/api/middlewares.py

"""
API middleware for the ChatMS plugin.
"""

import logging
import time
from typing import Callable, Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import Config
from ..core.chat_system import ChatSystem


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log information.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log the request
        logger.info(
            f"{request.client.host}:{request.client.port} - "
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {process_time:.4f}s"
        )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""
    
    def __init__(self, app: FastAPI, chat_system: ChatSystem):
        """Initialize the rate limit middleware.
        
        Args:
            app: The FastAPI app
            chat_system: The chat system instance
        """
        super().__init__(app)
        self.chat_system = chat_system
        self.limiter = None
        
        # Initialize rate limiter if available
        if hasattr(chat_system, "rate_limit_manager"):
            self.limiter = chat_system.rate_limit_manager
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and apply rate limiting.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        if not self.limiter:
            return await call_next(request)
        
        # Skip rate limiting for some endpoints
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get IP address
        ip_address = request.client.host
        
        # Apply rate limit
        try:
            key = f"api:{ip_address}:{request.url.path}"
            limit = 100  # Default limit per minute
            
            # Apply different limits for different endpoints
            if request.url.path.startswith("/uploads"):
                limit = 20  # Limit file uploads
            elif request.url.path.startswith("/messages"):
                limit = 60  # Limit message sending
            
            # Check rate limit
            if self.limiter:
                is_limited, reset_time = await self.limiter.limiter.check_rate_limit(key, limit)
                
                if is_limited:
                    # Return rate limit exceeded response
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Rate limit exceeded",
                            "reset_in": reset_time
                        }
                    )
        except Exception as e:
            logger.error(f"Rate limit error: {e}")
        
        # Process the request
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication."""
    
    def __init__(self, app: FastAPI, chat_system: ChatSystem):
        """Initialize the authentication middleware.
        
        Args:
            app: The FastAPI app
            chat_system: The chat system instance
        """
        super().__init__(app)
        self.chat_system = chat_system
        self.public_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/token",
            "/register"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and check authentication.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        # Skip authentication for public paths
        for path in self.public_paths:
            if request.url.path.startswith(path):
                return await call_next(request)
        
        # Check authentication
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Extract token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication credentials"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = parts[1]
        
        # Verify token
        try:
            user_id = await self.chat_system.security_manager.get_user_id_from_token(token)
            
            # Add user_id to request state
            request.state.user_id = user_id
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication credentials"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Process the request
        return await call_next(request)


def setup_middlewares(app: FastAPI, chat_system: ChatSystem, config: Config) -> None:
    """Set up middlewares for the FastAPI app.
    
    Args:
        app: The FastAPI app
        chat_system: The chat system instance
        config: The configuration object
    """
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add logging middleware
    app.add_middleware(LoggingMiddleware)
    
    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, chat_system=chat_system)
    
    # Add authentication middleware
    app.add_middleware(AuthMiddleware, chat_system=chat_system)