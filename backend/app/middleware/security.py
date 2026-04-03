from fastapi import Request
from fastapi.responses import JSONResponse
import re
import logging

logger = logging.getLogger(__name__)

# PII patterns to mask
PII_PATTERNS = {
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'phone': r'\b\d{3}-\d{3}-\d{4}\b',
    'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
}

# SQL injection dangerous patterns
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION)\b)",
    r"(--|;|'|\"|%27|%22|%3B)",
    r"(\bOR\b.*\b=\b|\bAND\b.*\b=\b)",
    r"(\bUNION\b.*\bSELECT\b)",
    r"(\bDROP\b.*\bTABLE\b)",
    r"(\bEXEC\b.*\(@|\bEXECUTE\b.*\(@)",
]


def mask_pii(text: str) -> str:
    """Mask PII in text for safe logging."""
    if not text or not isinstance(text, str):
        return text
    for pii_type, pattern in PII_PATTERNS.items():
        text = re.sub(pattern, f'[{pii_type}_masked]', text, flags=re.IGNORECASE)
    return text


def sanitize_sql_input(value: str) -> str:
    """Sanitize input to prevent SQL injection."""
    if not value or not isinstance(value, str):
        return value
    # Escape single quotes
    value = value.replace("'", "''")
    # Remove potentially dangerous characters
    value = re.sub(r'[\x00-\x1F\x7F]', '', value)
    return value


def check_sql_injection(value: str) -> bool:
    """Check if input contains potential SQL injection patterns."""
    if not value or not isinstance(value, str):
        return False
    value_upper = value.upper()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value_upper, re.IGNORECASE):
            return True
    return False


def get_safe_logger(logger_name: str):
    """Get a logger wrapper that automatically masks PII."""
    safe_logger = logging.getLogger(logger_name)
    
    original_debug = safe_logger.debug
    original_info = safe_logger.info
    original_warning = safe_logger.warning
    original_error = safe_logger.error
    
    def masked_debug(msg, *args, **kwargs):
        masked_msg = mask_pii(str(msg))
        original_debug(masked_msg, *args, **kwargs)
    
    def masked_info(msg, *args, **kwargs):
        masked_msg = mask_pii(str(msg))
        original_info(masked_msg, *args, **kwargs)
    
    def masked_warning(msg, *args, **kwargs):
        masked_msg = mask_pii(str(msg))
        original_warning(masked_msg, *args, **kwargs)
    
    def masked_error(msg, *args, **kwargs):
        masked_msg = mask_pii(str(msg))
        original_error(masked_msg, *args, **kwargs)
    
    safe_logger.debug = masked_debug
    safe_logger.info = masked_info
    safe_logger.warning = masked_warning
    safe_logger.error = masked_error
    
    return safe_logger


async def security_headers_middleware(request: Request, call_next):
    """Middleware to add security headers to responses."""
    response = await call_next(request)
    
    # Prevent content type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Strict Transport Security (HSTS)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    
    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions Policy
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response


async def sql_injection_protection_middleware(request: Request, call_next):
    """Middleware to check for SQL injection attempts in request parameters."""
    # Check query parameters
    for key, value in request.query_params.items():
        if check_sql_injection(value):
            logger.warning(f"SQL injection attempt detected in query param '{key}': {mask_pii(value)}")
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid request detected"}
            )
    
    # Check path parameters
    for param in request.path_params.values():
        if param and check_sql_injection(str(param)):
            logger.warning(f"SQL injection attempt detected in path param: {mask_pii(str(param))}")
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid request detected"}
            )
    
    return await call_next(request)


async def xss_protection_middleware(request: Request, call_next):
    """Middleware to sanitize inputs and check for XSS patterns."""
    xss_patterns = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"eval\(",
        r"expression\(",
    ]
    
    # Check query parameters for XSS
    for key, value in request.query_params.items():
        for pattern in xss_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"XSS attempt detected in query param '{key}': {mask_pii(value)}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid request detected"}
                )
    
    return await call_next(request)
