"""Thread-safe High-Performance In-Memory TTL & LRU Cache."""
from collections import OrderedDict
import threading
import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    """Thread-safe LRU Cache with individual entry Time-To-Live (TTL) expiration."""

    def __init__(self, maxsize: int = 1000, default_ttl_seconds: int = 3600):
        self.maxsize = maxsize
        self.default_ttl = default_ttl_seconds
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve item if present and not expired; moves item to MRU position."""
        with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if time.time() > expiry:
                # Expired
                del self._cache[key]
                return None
            # Move to end (Most Recently Used)
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store item with TTL expiration; evicts LRU if capacity is exceeded."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = time.time() + ttl

        with self._lock:
            if key in self._cache:
                self._cache[key] = (value, expiry)
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.maxsize:
                    # Evict least recently used (first item)
                    self._cache.popitem(last=False)
                self._cache[key] = (value, expiry)

    def delete(self, key: str) -> bool:
        """Remove a key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries in the cache."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Return current count of unexpired items in cache."""
        with self._lock:
            self.cleanup_expired()
            return len(self._cache)

    def cleanup_expired(self) -> int:
        """Remove all expired entries and return number of deleted entries."""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)
