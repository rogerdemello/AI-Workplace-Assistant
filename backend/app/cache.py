import json
import time
from typing import Optional, Any, Callable
from functools import wraps
from .config import settings

try:
    import redis
    # Short timeouts so a down/unreachable Redis fails in ~0.3s instead of
    # blocking on the OS default (~seconds) for every cache call.
    _redis_client: Optional[redis.Redis] = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
    )
except Exception:
    _redis_client = None

DEFAULT_TTL = 300

# Circuit breaker: when Redis is unreachable, every call would otherwise pay the
# connect timeout. The chat path touches Redis several times per message, so a
# down Redis turns into seconds of dead wait per request. After a failure we
# skip Redis entirely for the cooldown window, then probe again — so an outage
# costs ~one short timeout per window, not one per call. Degrades to no-cache.
_BREAKER_COOLDOWN = 30.0
_breaker_open_until = 0.0


def _redis_ready() -> bool:
    return bool(_redis_client) and time.monotonic() >= _breaker_open_until


def _trip_breaker() -> None:
    global _breaker_open_until
    _breaker_open_until = time.monotonic() + _BREAKER_COOLDOWN


def get_cached(key: str) -> Optional[Any]:
    if not _redis_ready():
        return None
    try:
        cached = _redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        _trip_breaker()
    return None

def set_cached(key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
    if not _redis_ready():
        return False
    try:
        _redis_client.setex(key, ttl, json.dumps(value))
        return True
    except Exception:
        _trip_breaker()
        return False

def delete_cached(key: str) -> bool:
    if not _redis_ready():
        return False
    try:
        _redis_client.delete(key)
        return True
    except Exception:
        _trip_breaker()
        return False

def invalidate_pattern(pattern: str) -> bool:
    if not _redis_ready():
        return False
    try:
        keys = _redis_client.keys(pattern)
        if keys:
            _redis_client.delete(*keys)
        return True
    except Exception:
        _trip_breaker()
        return False

def cache_result(key_prefix: str, ttl: int = DEFAULT_TTL):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{':'.join(str(a) for a in args if a)}:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
            
            cached = get_cached(cache_key)
            if cached is not None:
                return cached
            
            result = func(*args, **kwargs)
            set_cached(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
