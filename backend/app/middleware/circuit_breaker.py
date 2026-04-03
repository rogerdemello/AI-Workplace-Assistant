from enum import Enum
from typing import Callable, Any, Optional, Dict
import time
import logging
import os
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"         # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation for Azure AI service.
    
    Prevents cascading failures by stopping requests to a failing service
    and allowing it time to recover.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
        excluded_exceptions: tuple = (),
        name: str = "azure_circuit_breaker"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # Seconds before trying again
        self.success_threshold = success_threshold  # Successes needed to close circuit
        self.excluded_exceptions = excluded_exceptions
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result if successful
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        async with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(f"{self.name}: Circuit transitioning to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"{self.name}: Circuit is OPEN. Service unavailable."
                    )
            
            # Execute the function
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                await self._on_success()
                return result
                
            except Exception as e:
                # Check if exception should be excluded
                if self.excluded_exceptions and isinstance(e, self.excluded_exceptions):
                    raise
                
                await self._on_failure()
                raise
    
    async def _on_success(self):
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"{self.name}: Circuit CLOSED after recovery")
        else:
            # Reset failure count on success in closed state
            self._failure_count = 0
    
    async def _on_failure(self):
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open state opens the circuit again
            self._state = CircuitState.OPEN
            logger.warning(f"{self.name}: Circuit OPENED after failure in HALF_OPEN state")
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"{self.name}: Circuit OPENED after {self._failure_count} failures"
            )
    
    def reset(self):
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        logger.info(f"{self.name}: Circuit manually reset to CLOSED")
    
    def get_status(self) -> Dict:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerDecorator:
    """Decorator to add circuit breaker to async functions."""
    
    def __init__(self, circuit_breaker: CircuitBreaker):
        self.circuit_breaker = circuit_breaker
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.circuit_breaker.call(func, *args, **kwargs)
        return wrapper


# Global circuit breaker instance for Azure AI
azure_circuit_breaker = CircuitBreaker(
    failure_threshold=int(os.getenv("CIRCUIT_BREAKER_FAILURES", "5")),
    recovery_timeout=int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60")),
    success_threshold=int(os.getenv("CIRCUIT_BREAKER_SUCCESS", "2")),
    name="azure_openai"
)


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global Azure circuit breaker instance."""
    return azure_circuit_breaker


def circuit_breaker_call(func: Callable, *args, **kwargs) -> Any:
    """
    Synchronous wrapper for circuit breaker calls.
    For use with sync functions in async context.
    """
    return asyncio.run(azure_circuit_breaker.call(func, *args, **kwargs))
