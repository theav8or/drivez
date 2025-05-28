from datetime import datetime, timedelta
from fastapi import Depends
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast
import json
import hashlib

# Type variable for generic function typing
F = TypeVar('F', bound=Callable[..., Any])

class Cache:
    """Simple in-memory cache implementation"""
    _instance = None
    _store = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Cache, cls).__new__(cls)
        return cls._instance
    
    def get(self, key: str) -> Any:
        """Get a value from the cache"""
        if key in self._store:
            value, expiry = self._store[key]
            if expiry is None or expiry > datetime.utcnow():
                return value
            del self._store[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with optional TTL in seconds"""
        expiry = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None
        self._store[key] = (value, expiry)
    
    def delete(self, key: str) -> None:
        """Delete a key from the cache"""
        if key in self._store:
            del self._store[key]
    
    def clear(self) -> None:
        """Clear all cached values"""
        self._store = {}

def get_cache_key(*args, **kwargs) -> str:
    """Generate a cache key from function arguments"""
    key_parts = [str(arg) for arg in args] + [f"{k}={v}" for k, v in kwargs.items()]
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode('utf-8')).hexdigest()

def cached(ttl: Optional[int] = 300, key_prefix: str = ""):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live in seconds (None for no expiration)
        key_prefix: Optional prefix for cache keys
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip cache for methods that modify data
            if kwargs.get('skip_cache', False):
                return await func(*args, **kwargs)
                
            cache = Cache()
            cache_key = f"{key_prefix}:{func.__module__}:{func.__name__}:{get_cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
                
            # Call the function and cache the result
            result = await func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, ttl)
                
            return result
            
        return wrapper
    return decorator

# Global cache instance
cache = Cache()
