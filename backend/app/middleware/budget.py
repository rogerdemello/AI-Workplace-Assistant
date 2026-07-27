from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Optional, Union, Any
import time
import redis
import os
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Type alias for Redis client
RedisClient = Optional[redis.Redis]


class BudgetTracker:
    """Tracks monthly AI usage per user to enforce budget limits."""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: RedisClient = None
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        
        # Monthly budget configuration
        self.monthly_budget = int(os.getenv("MONTHLY_AI_BUDGET", "1000"))  # Default 1000 AI calls/month
        self.warning_threshold = 0.8  # Warn at 80% usage
        
        try:
            client = redis.from_url(
                redis_url, decode_responses=True,
                socket_connect_timeout=0.3, socket_timeout=0.3,
            )
            if client:
                client.ping()
                self.redis_client = client
                self.use_redis = True
                return
        except Exception as e:
            logger.warning(f"Redis unavailable for budget tracker, using memory fallback: {e}")
        
        self.use_redis = False
    
    def _get_current_month_key(self) -> str:
        """Get current month key for tracking."""
        return date.today().strftime("%Y-%m")
    
    def _get_user_usage_key(self, user_id: str) -> str:
        """Get Redis key for user's monthly usage."""
        month_key = self._get_current_month_key()
        return f"budget:{user_id}:{month_key}"
    
    def get_user_usage(self, user_id: str) -> int:
        """Get current month's AI usage for user."""
        if self.use_redis and self.redis_client:
            try:
                key = self._get_user_usage_key(user_id)
                usage: Any = self.redis_client.get(key)
                if usage is not None:
                    return int(usage)  # type: ignore[arg-type]
                return 0
            except Exception as e:
                logger.error(f"Redis error getting user usage: {e}")
        
        # Memory fallback
        user_data = self._memory_store.get(user_id)
        if user_data is None:
            return 0
        if user_data.get("month") != self._get_current_month_key():
            return 0
        used_val = user_data.get("used", 0)
        return int(used_val) if used_val else 0
    
    def increment_usage(self, user_id: str, count: int = 1) -> int:
        """Increment AI usage counter for user. Returns new usage count."""
        if self.use_redis and self.redis_client:
            try:
                key = self._get_user_usage_key(user_id)
                # Set expiry to 35 days to cover month boundary
                new_value: Any = self.redis_client.incrby(key, count)
                self.redis_client.expire(key, 35 * 24 * 3600)
                if new_value is not None:
                    return int(new_value)  # type: ignore[arg-type]
                return 0
            except Exception as e:
                logger.error(f"Redis error incrementing usage: {e}")
        
        # Memory fallback
        user_data = self._memory_store.get(user_id)
        if user_data is None:
            user_data = {"used": 0, "month": self._get_current_month_key()}
            self._memory_store[user_id] = user_data
        
        if user_data.get("month") != self._get_current_month_key():
            user_data["used"] = 0
            user_data["month"] = self._get_current_month_key()
        
        current_used = user_data.get("used", 0)
        if current_used is None:
            current_used = 0
        else:
            current_used = int(current_used)
        
        new_used = current_used + count
        user_data["used"] = new_used
        return new_used
    
    def check_budget(self, user_id: str) -> tuple[bool, bool, int, int]:
        """
        Check if user has budget remaining.
        
        Returns:
            tuple: (within_budget, warning_issued, current_usage, budget_limit)
        """
        current_usage = self.get_user_usage(user_id)
        
        if current_usage >= self.monthly_budget:
            return False, False, current_usage, self.monthly_budget
        
        warning_threshold = int(self.monthly_budget * self.warning_threshold)
        warning_issued = current_usage >= warning_threshold
        
        return True, warning_issued, current_usage, self.monthly_budget
    
    def get_budget_status(self, user_id: str) -> Dict:
        """Get detailed budget status for a user."""
        within_budget, warning_issued, usage, limit = self.check_budget(user_id)
        
        return {
            "within_budget": within_budget,
            "warning_issued": warning_issued,
            "current_usage": usage,
            "budget_limit": limit,
            "remaining": max(0, limit - usage),
            "percentage_used": round((usage / limit) * 100, 1) if limit > 0 else 0,
            "reset_date": self._get_month_reset_date()
        }
    
    def _get_month_reset_date(self) -> str:
        """Get the date when the budget resets (first day of next month)."""
        today = date.today()
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        return next_month.isoformat()
    
    def reset_user_budget(self, user_id: str) -> bool:
        """Manually reset a user's budget (admin function)."""
        if self.use_redis and self.redis_client:
            try:
                key = self._get_user_usage_key(user_id)
                self.redis_client.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis error resetting budget: {e}")
                return False
        
        # Memory fallback
        if user_id in self._memory_store:
            del self._memory_store[user_id]
        return True


# Global budget tracker instance
budget_tracker = BudgetTracker()


async def budget_middleware(request: Request, call_next):
    """
    Middleware to track and enforce monthly AI budget limits.
    
    Applies to all /ai/* endpoints.
    """
    # Only track budget for AI endpoints
    if not request.url.path.startswith("/api/v1/ai"):
        return await call_next(request)
    
    # Skip budget check for health/admin endpoints
    if request.url.path in ["/health", "/"]:
        return await call_next(request)
    
    # Extract user_id from request state
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        # Use device_id or IP as fallback for unauthenticated requests
        user_id = getattr(request.state, "device_id", request.client.host if request.client else "anonymous")
    
    # Check budget
    within_budget, warning_issued, usage, limit = budget_tracker.check_budget(user_id)
    
    if not within_budget:
        logger.warning(f"User {user_id} exceeded monthly AI budget")
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Monthly AI budget exceeded. Please upgrade your plan or wait until next month.",
                "current_usage": usage,
                "budget_limit": limit,
                "reset_date": budget_tracker._get_month_reset_date()
            }
        )
    
    # Process request
    response = await call_next(request)
    
    # Only increment budget on successful AI responses (status 2xx)
    if 200 <= response.status_code < 300:
        new_usage = budget_tracker.increment_usage(user_id)
        
        # Add budget headers
        remaining = max(0, limit - new_usage)
        response.headers["X-Budget-Limit"] = str(limit)
        response.headers["X-Budget-Remaining"] = str(remaining)
        
        # Add warning header if threshold exceeded
        if new_usage >= int(limit * budget_tracker.warning_threshold):
            response.headers["X-Budget-Warning"] = "true"
    
    return response


def get_budget_tracker() -> BudgetTracker:
    """Get the global budget tracker instance."""
    return budget_tracker
