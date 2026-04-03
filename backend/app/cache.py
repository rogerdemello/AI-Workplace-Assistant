import json
from typing import Optional, Any, Callable
from functools import wraps
from .config import settings

try:
    import redis
    _redis_client: Optional[redis.Redis] = redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    _redis_client = None

DEFAULT_TTL = 300

def get_cached(key: str) -> Optional[Any]:
    if not _redis_client:
        return None
    try:
        cached = _redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return None

def set_cached(key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
    if not _redis_client:
        return False
    try:
        _redis_client.setex(key, ttl, json.dumps(value))
        return True
    except Exception:
        return False

def delete_cached(key: str) -> bool:
    if not _redis_client:
        return False
    try:
        _redis_client.delete(key)
        return True
    except Exception:
        return False

def invalidate_pattern(pattern: str) -> bool:
    if not _redis_client:
        return False
    try:
        keys = _redis_client.keys(pattern)
        if keys:
            _redis_client.delete(*keys)
        return True
    except Exception:
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
