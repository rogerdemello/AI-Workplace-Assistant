from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Optional, Union, Any
import time
import redis
import os
import logging

logger = logging.getLogger(__name__)

# Type alias for Redis client
RedisClient = Optional[redis.Redis]


class RateLimiter:
    """Per-user rate limiter using Redis as the backend store."""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: RedisClient = None
        try:
            client: Any = redis.from_url(redis_url, decode_responses=True)
            if client:
                client.ping()  # type: ignore[attr-defined]
                self.redis_client = client
                self.use_redis = True
                self._memory_store = {}
                self.limits = {
                    "chat": 50,       # 50 requests per hour
                    "ai": 30,         # 30 AI calls per hour
                    "api": 100        # 100 general API calls per hour
                }
                self.window_size = 3600  # 1 hour in seconds
                return
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
        
        self.use_redis = False
        self._memory_store: Dict[str, tuple[int, float]] = {}  # key -> (count, reset_time)
        
        self.limits = {
            "chat": 50,       # 50 requests per hour
            "ai": 30,         # 30 AI calls per hour
            "api": 100        # 100 general API calls per hour
        }
        self.window_size = 3600  # 1 hour in seconds
    
    def _get_memory_count(self, key: str) -> int:
        """Get current count from memory store, resetting if window expired."""
        if key not in self._memory_store:
            return 0
        count, reset_time = self._memory_store[key]
        if time.time() > reset_time:
            # Window expired, reset
            self._memory_store[key] = (0, time.time() + self.window_size)
            return 0
        return count
    
    def _increment_memory(self, key: str) -> int:
        """Increment count in memory store."""
        if key not in self._memory_store:
            self._memory_store[key] = (1, time.time() + self.window_size)
            return 1
        count, reset_time = self._memory_store[key]
        if time.time() > reset_time:
            # Window expired, reset
            self._memory_store[key] = (1, time.time() + self.window_size)
            return 1
        self._memory_store[key] = (count + 1, reset_time)
        return count + 1
    
    async def check_rate_limit(self, user_id: str, endpoint_type: str) -> tuple[bool, Optional[int]]:
        """
        Check if user has exceeded rate limit for given endpoint type.
        
        Returns:
            tuple: (is_allowed, current_count)
        """
        key = f"rate_limit:{user_id}:{endpoint_type}"
        limit = self.limits.get(endpoint_type, 100)
        
        if self.use_redis and self.redis_client:
            try:
                current: Any = self.redis_client.get(key)
                
                if current is None:
                    self.redis_client.setex(key, self.window_size, 1)
                    return True, 1
                
                current_count = int(current)  # type: ignore[arg-type]
                if current_count >= limit:
                    return False, current_count
                
                self.redis_client.incr(key)
                return True, current_count + 1
            except Exception as e:
                logger.error(f"Redis error in rate limit check: {e}")
        
        # Memory fallback
        current_count = self._get_memory_count(key)
        if current_count >= limit:
            return False, current_count
        
        new_count = self._increment_memory(key)
        return True, new_count
    
    def get_remaining(self, user_id: str, endpoint_type: str) -> int:
        """Get remaining requests for user and endpoint."""
        limit = self.limits.get(endpoint_type, 100)
        
        if self.use_redis and self.redis_client:
            try:
                key = f"rate_limit:{user_id}:{endpoint_type}"
                current: Any = self.redis_client.get(key)
                if current is None:
                    return limit
                return max(0, limit - int(current))  # type: ignore[arg-type]
            except Exception:
                pass
        
        # Memory fallback
        key = f"rate_limit:{user_id}:{endpoint_type}"
        current_count = self._get_memory_count(key)
        return max(0, limit - current_count)


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware to enforce rate limiting on API endpoints.
    
    Returns 429 if rate limit is exceeded.
    """
    # Skip rate limiting for health checks and root
    if request.url.path in ["/health", "/"]:
        return await call_next(request)
    
    # Skip rate limiting for docs and openapi
    if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
        return await call_next(request)
    
    # Extract user_id from request state or use IP
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        # Fall back to IP address
        client_host = request.client.host if request.client else "anonymous"
        user_id = getattr(request.state, "device_id", client_host)
    
    # Determine endpoint type
    endpoint_type = "api"
    path = request.url.path
    
    if "/chat" in path:
        endpoint_type = "chat"
    elif "/ai" in path:
        endpoint_type = "ai"
    
    # Check rate limit
    is_allowed, current_count = await rate_limiter.check_rate_limit(user_id, endpoint_type)
    
    if not is_allowed:
        limit = rate_limiter.limits.get(endpoint_type, 100)
        logger.warning(f"Rate limit exceeded for user {user_id} on {endpoint_type}")
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Please try again later.",
                "retry_after": 3600,
                "limit": limit,
                "current_usage": current_count
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "3600"
            }
        )
    
    # Add rate limit headers to response
    response = await call_next(request)
    remaining = rate_limiter.get_remaining(user_id, endpoint_type)
    limit = rate_limiter.limits.get(endpoint_type, 100)
    
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    
    return response


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return rate_limiter
