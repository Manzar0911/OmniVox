"""Audio Synthesis Cache: High-speed zero-latency caching for Neural TTS output."""
import hashlib
import os
from pathlib import Path
import tempfile
import threading
from typing import Optional
from .ttl_cache import TTLCache

CACHE_DIR = Path(tempfile.gettempdir()) / "omnivox_audio_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class AudioCache:
    """Caches synthesized speech audio files to achieve sub-millisecond audio responses."""

    def __init__(self, maxsize: int = 500, default_ttl_seconds: int = 86400):
        # 24-hour default TTL for synthesized audio files
        self._cache = TTLCache(maxsize=maxsize, default_ttl_seconds=default_ttl_seconds)
        self._lock = threading.Lock()

    def _get_key(self, text: str, voice: str) -> str:
        content = f"{voice.strip().lower()}::{text.strip().lower()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_audio_file(self, text: str, voice: str) -> Optional[str]:
        """Return the path to a cached audio file if it exists and is still valid."""
        key = self._get_key(text, voice)
        file_path = self._cache.get(key)
        if file_path and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        return None

    def set_audio_file(self, text: str, voice: str, src_path: str, ttl_seconds: Optional[int] = None) -> str:
        """Cache an audio file by copying or saving it to the persistent cache directory."""
        if not src_path or not os.path.exists(src_path) or os.path.getsize(src_path) == 0:
            return src_path

        key = self._get_key(text, voice)
        ext = Path(src_path).suffix or ".mp3"
        dest_path = str(CACHE_DIR / f"{key}{ext}")

        try:
            with open(src_path, "rb") as sf, open(dest_path, "wb") as df:
                df.write(sf.read())
            self._cache.set(key, dest_path, ttl_seconds=ttl_seconds)
            return dest_path
        except Exception:
            return src_path


audio_cache = AudioCache()
