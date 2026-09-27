"""Query and Semantic Intent Cache for instant conversational replies."""
import hashlib
import re
from typing import Optional
from .ttl_cache import TTLCache


def normalize_conversational_query(text: str) -> str:
    """Normalize input query for caching."""
    q = text.lower().strip()
    q = re.sub(r'[^\w\s]', '', q)
    q = re.sub(r'\s+', ' ', q)
    return q.strip()


class QueryCache:
    """Caches deterministic responses to common user queries and executive commands."""

    def __init__(self, maxsize: int = 1000, default_ttl_seconds: int = 1800):
        # 30-minute default TTL for conversational cache
        self._cache = TTLCache(maxsize=maxsize, default_ttl_seconds=default_ttl_seconds)

    def _get_key(self, user_id: Optional[int], query: str) -> str:
        norm = normalize_conversational_query(query)
        prefix = f"user_{user_id}::" if user_id is not None else "global::"
        return hashlib.sha256((prefix + norm).encode("utf-8")).hexdigest()

    def get(self, query: str, user_id: Optional[int] = None) -> Optional[str]:
        """Retrieve cached response if exists."""
        key = self._get_key(user_id, query)
        return self._cache.get(key)

    def set(self, query: str, response: str, user_id: Optional[int] = None, ttl_seconds: Optional[int] = None) -> None:
        """Cache response for query."""
        key = self._get_key(user_id, query)
        self._cache.set(key, response, ttl_seconds=ttl_seconds)


query_cache = QueryCache()
