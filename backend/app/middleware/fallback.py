from typing import Any, Dict, Optional, Callable
import logging
import json
import os
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class FallbackType(Enum):
    """Types of fallback responses available."""
    CIRCUIT_BREAKER = "circuit_breaker"
    RATE_LIMIT = "rate_limit"
    BUDGET_EXCEEDED = "budget_exceeded"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT = "timeout"
    GENERIC_ERROR = "generic_error"


class FallbackResponse:
    """Represents a fallback response with metadata."""
    
    def __init__(
        self,
        fallback_type: FallbackType,
        message: str,
        status_code: int = 503,
        retry_possible: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        self.fallback_type = fallback_type
        self.message = message
        self.status_code = status_code
        self.retry_possible = retry_possible
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "error": self.fallback_type.value,
            "message": self.message,
            "status_code": self.status_code,
            "retry_possible": self.retry_possible,
            **self.details
        }


class FallbackManager:
    """
    Manages fallback responses for various failure scenarios.
    
    Provides configurable fallback messages and responses when
    primary services are unavailable.
    """
    
    def __init__(self, fallback_config_path: Optional[str] = None):
        self.fallbacks: Dict[FallbackType, FallbackResponse] = {}
        self._load_default_fallbacks()
        
        if fallback_config_path:
            self._load_custom_fallbacks(fallback_config_path)
    
    def _load_default_fallbacks(self):
        """Load default fallback responses."""
        # Circuit breaker fallback
        self.fallbacks[FallbackType.CIRCUIT_BREAKER] = FallbackResponse(
            fallback_type=FallbackType.CIRCUIT_BREAKER,
            message="Service temporarily unavailable. Please try again in a moment.",
            status_code=503,
            retry_possible=True,
            details={"reason": "circuit_breaker_open"}
        )
        
        # Rate limit fallback
        self.fallbacks[FallbackType.RATE_LIMIT] = FallbackResponse(
            fallback_type=FallbackType.RATE_LIMIT,
            message="Rate limit exceeded. Please wait before making more requests.",
            status_code=429,
            retry_possible=True,
            details={"reason": "rate_limit_exceeded"}
        )
        
        # Budget exceeded fallback
        self.fallbacks[FallbackType.BUDGET_EXCEEDED] = FallbackResponse(
            fallback_type=FallbackType.BUDGET_EXCEEDED,
            message="Monthly AI budget exceeded. Please upgrade your plan or wait until next month.",
            status_code=403,
            retry_possible=False,
            details={"reason": "budget_exceeded"}
        )
        
        # Service unavailable fallback
        self.fallbacks[FallbackType.SERVICE_UNAVAILABLE] = FallbackResponse(
            fallback_type=FallbackType.SERVICE_UNAVAILABLE,
            message="The AI service is currently unavailable. Please try again later.",
            status_code=503,
            retry_possible=True,
            details={"reason": "service_unavailable"}
        )
        
        # Timeout fallback
        self.fallbacks[FallbackType.TIMEOUT] = FallbackResponse(
            fallback_type=FallbackType.TIMEOUT,
            message="Request timed out. Please try again with a shorter request.",
            status_code=504,
            retry_possible=True,
            details={"reason": "timeout"}
        )
        
        # Generic error fallback
        self.fallbacks[FallbackType.GENERIC_ERROR] = FallbackResponse(
            fallback_type=FallbackType.GENERIC_ERROR,
            message="An unexpected error occurred. Please try again later.",
            status_code=500,
            retry_possible=True,
            details={"reason": "internal_error"}
        )
    
    def _load_custom_fallbacks(self, config_path: str):
        """Load custom fallback responses from JSON config file."""
        try:
            path = Path(config_path)
            if path.exists():
                with open(path) as f:
                    config = json.load(f)
                
                for key, value in config.items():
                    try:
                        fallback_type = FallbackType(key)
                        self.fallbacks[fallback_type] = FallbackResponse(
                            fallback_type=fallback_type,
                            message=value.get("message", ""),
                            status_code=value.get("status_code", 503),
                            retry_possible=value.get("retry_possible", True),
                            details=value.get("details", {})
                        )
                    except ValueError:
                        logger.warning(f"Unknown fallback type: {key}")
        except Exception as e:
            logger.error(f"Error loading custom fallbacks: {e}")
    
    def get_fallback(self, fallback_type: FallbackType) -> FallbackResponse:
        """Get fallback response for a given type."""
        return self.fallbacks.get(
            fallback_type,
            self.fallbacks[FallbackType.GENERIC_ERROR]
        )
    
    def register_fallback(
        self,
        fallback_type: FallbackType,
        response: FallbackResponse
    ):
        """Register a custom fallback response."""
        self.fallbacks[fallback_type] = response
    
    def create_error_response(
        self,
        fallback_type: FallbackType,
        custom_message: Optional[str] = None,
        additional_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create an error response dictionary.
        
        Args:
            fallback_type: Type of fallback to use
            custom_message: Optional custom message to override default
            additional_details: Additional details to include
            
        Returns:
            Dictionary suitable for JSON response
        """
        fallback = self.get_fallback(fallback_type)
        
        response = fallback.to_dict()
        
        if custom_message:
            response["message"] = custom_message
        
        if additional_details:
            response.update(additional_details)
        
        return response


class FallbackHandler:
    """
    Handler for managing fallback logic with circuit breaker integration.
    """
    
    def __init__(self, fallback_manager: Optional[FallbackManager] = None):
        self.fallback_manager = fallback_manager or FallbackManager()
    
    def handle_circuit_breaker_error(
        self,
        error: Exception,
        original_request: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle circuit breaker open error."""
        logger.error(f"Circuit breaker error: {error}")
        
        details = {"error_type": type(error).__name__}
        if original_request:
            details["request"] = original_request
        
        return self.fallback_manager.create_error_response(
            FallbackType.CIRCUIT_BREAKER,
            additional_details=details
        )
    
    def handle_service_error(
        self,
        error: Exception,
        service_name: str = "AI Service"
    ) -> Dict[str, Any]:
        """Handle general service errors."""
        error_message = str(error)
        logger.error(f"{service_name} error: {error_message}")
        
        # Determine fallback type based on error
        fallback_type = FallbackType.GENERIC_ERROR
        
        if "timeout" in error_message.lower():
            fallback_type = FallbackType.TIMEOUT
        elif "unavailable" in error_message.lower():
            fallback_type = FallbackType.SERVICE_UNAVAILABLE
        
        return self.fallback_manager.create_error_response(
            fallback_type,
            additional_details={
                "service": service_name,
                "error": error_message
            }
        )
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for monitoring."""
        from .circuit_breaker import get_circuit_breaker
        
        cb = get_circuit_breaker()
        return cb.get_status()


# Global fallback handler instance
fallback_handler = FallbackHandler()
fallback_manager = fallback_handler.fallback_manager


def get_fallback_handler() -> FallbackHandler:
    """Get the global fallback handler instance."""
    return fallback_handler


def get_fallback_manager() -> FallbackManager:
    """Get the global fallback manager instance."""
    return fallback_manager
