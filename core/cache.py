# core/cache.py
"""Cache implementation for WebDAV client."""

import time
from typing import Dict, Optional, Any, Tuple
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class Cache:
    """Thread-safe cache with TTL and size limit."""

    def __init__(self, ttl: int = 300, max_size: int = 100):
        """
        Initialize cache.

        Args:
            ttl: Time to live in seconds
            max_size: Maximum number of items in cache
        """
        self._ttl = ttl
        self._max_size = max_size
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.

        Returns:
            Cached value or None if not found or expired
        """
        with self._lock:
            if key not in self._cache:
                return None

            timestamp, value = self._cache[key]
            if time.time() - timestamp < self._ttl:
                logger.debug(f"Cache hit for {key}")
                return value

            # Expired
            logger.debug(f"Cache expired for {key}")
            del self._cache[key]
            return None

    def set(self, key: str, value: Any):
        """
        Add item to cache.

        If cache is full, removes oldest item.
        """
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Remove oldest
                oldest_key = min(self._cache.keys(),
                                 key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
                logger.debug(f"Removed oldest item {oldest_key} from cache")

            self._cache[key] = (time.time(), value)
            logger.debug(f"Added {key} to cache")

    def remove(self, key: str):
        """Remove item from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Removed {key} from cache")

    def clear(self):
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()
            logger.debug("Cache cleared")

    def invalidate_prefix(self, prefix: str):
        """Invalidate all keys starting with prefix."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
            if keys_to_remove:
                logger.debug(
                    f"Invalidated {len(keys_to_remove)} items with prefix {prefix}")

    @property
    def size(self) -> int:
        """Current cache size."""
        with self._lock:
            return len(self._cache)
