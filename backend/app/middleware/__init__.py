"""
Middleware package for rate limiting, budget tracking, circuit breaker, and fallback responses.
"""

from .rate_limit import rate_limiter, rate_limit_middleware, get_rate_limiter
from .budget import budget_tracker, budget_middleware, get_budget_tracker
from .circuit_breaker import (
    azure_circuit_breaker,
    get_circuit_breaker,
    CircuitBreaker,
    CircuitBreakerOpenError
)
from .fallback import (
    fallback_handler,
    fallback_manager,
    get_fallback_handler,
    get_fallback_manager,
    FallbackType,
    FallbackResponse,
    FallbackManager,
    FallbackHandler
)

__all__ = [
    # Rate limiting
    "rate_limiter",
    "rate_limit_middleware",
    "get_rate_limiter",
    
    # Budget tracking
    "budget_tracker",
    "budget_middleware",
    "get_budget_tracker",
    
    # Circuit breaker
    "azure_circuit_breaker",
    "get_circuit_breaker",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    
    # Fallback responses
    "fallback_handler",
    "fallback_manager",
    "get_fallback_handler",
    "get_fallback_manager",
    "FallbackType",
    "FallbackResponse",
    "FallbackManager",
    "FallbackHandler",
]
