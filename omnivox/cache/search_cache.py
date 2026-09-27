"""Search Cache with query normalization, TTL expiration, and in-flight deduplication."""
import asyncio
import hashlib
import re
import threading
from typing import Callable, Optional
from .ttl_cache import TTLCache


def normalize_search_query(query: str) -> str:
    """Normalize query by lowercasing, removing extra whitespace, and stripping punctuation."""
    q = query.lower().strip()
    # Strip common search boilerplate
    q = re.sub(r'^(?:search for|research|look up|find info on|what is|tell me about)\s+', '', q)
    # Remove punctuation
    q = re.sub(r'[^\w\s]', '', q)
    # Normalize whitespace
    q = re.sub(r'\s+', ' ', q).strip()
    return q


class SearchCache:
    """Intelligent cache for web research queries (Tavily / DDG) with de-duplication."""

    def __init__(self, maxsize: int = 500, default_ttl_seconds: int = 3600):
        # 1-hour default TTL for search research
        self._cache = TTLCache(maxsize=maxsize, default_ttl_seconds=default_ttl_seconds)
        self._inflight: dict[str, threading.Event] = {}
        self._inflight_results: dict[str, str] = {}
        self._lock = threading.Lock()

    def _get_key(self, query: str) -> str:
        normalized = normalize_search_query(query)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[str]:
        """Get cached research result if available."""
        key = self._get_key(query)
        return self._cache.get(key)

    def set(self, query: str, result: str, ttl_seconds: Optional[int] = None) -> None:
        """Store research result in cache."""
        key = self._get_key(query)
        self._cache.set(key, result, ttl_seconds=ttl_seconds)

    def get_or_compute(self, query: str, compute_fn: Callable[[str], str], ttl_seconds: Optional[int] = None) -> str:
        """Fetch from cache or execute compute_fn with in-flight deduplication."""
        key = self._get_key(query)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # Check if already computing in another thread
        is_initiator = False
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

            if key in self._inflight:
                event = self._inflight[key]
            else:
                event = threading.Event()
                self._inflight[key] = event
                is_initiator = True

        if not is_initiator:
            # Wait for the computing thread to finish
            event.wait(timeout=20.0)
            with self._lock:
                return self._inflight_results.get(key) or compute_fn(query)

        # We are the initiator, compute and broadcast
        try:
            result = compute_fn(query)
            self.set(query, result, ttl_seconds=ttl_seconds)
            with self._lock:
                self._inflight_results[key] = result
            return result
        finally:
            with self._lock:
                event.set()
                if key in self._inflight:
                    del self._inflight[key]
                if key in self._inflight_results:
                    del self._inflight_results[key]


search_cache = SearchCache()
