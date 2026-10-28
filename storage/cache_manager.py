"""
Low-RAM Cache Manager for Android Go.
Provides bounded in-memory LRU cache and size-capped disk storage for avatars and thumbnails.
"""

import os
import shutil
import logging
from collections import OrderedDict
from typing import Optional, Dict

logger = logging.getLogger("CacheManager")


class CacheManager:
    """
    Android Go optimized cache manager.
    Enforces strict memory ceilings and disk quotas with LRU eviction.
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_mem_entries: int = 40,
        max_disk_mb: int = 25,
        low_resource_mode: bool = False,
    ):
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = os.path.expanduser("~/.telegram_lite/cache")

        os.makedirs(self.cache_dir, exist_ok=True)
        self.avatars_dir = os.path.join(self.cache_dir, "avatars")
        self.media_dir = os.path.join(self.cache_dir, "media")
        os.makedirs(self.avatars_dir, exist_ok=True)
        os.makedirs(self.media_dir, exist_ok=True)

        self._low_resource_mode = low_resource_mode
        self._max_mem_entries = 15 if low_resource_mode else max_mem_entries
        self._max_disk_bytes = (10 if low_resource_mode else max_disk_mb) * 1024 * 1024

        # In-memory LRU cache for fast widget binding
        self._mem_cache: OrderedDict[str, bytes] = OrderedDict()

    @property
    def low_resource_mode(self) -> bool:
        return self._low_resource_mode

    @low_resource_mode.setter
    def low_resource_mode(self, enabled: bool) -> None:
        self._low_resource_mode = enabled
        if enabled:
            self._max_mem_entries = 15
            self._max_disk_bytes = 10 * 1024 * 1024
            self._trim_memory_cache()
            self._enforce_disk_quota()
        else:
            self._max_mem_entries = 40
            self._max_disk_bytes = 25 * 1024 * 1024

    def get_avatar_path(self, peer_id: int) -> str:
        """Standardized path for an avatar image."""
        return os.path.join(self.avatars_dir, f"peer_{peer_id}.jpg")

    def has_cached_avatar(self, peer_id: int) -> bool:
        """Check if avatar file is already on disk and non-empty."""
        path = self.get_avatar_path(peer_id)
        return os.path.isfile(path) and os.path.getsize(path) > 0

    def put_memory(self, key: str, data: bytes) -> None:
        """Put item into in-memory LRU cache with eviction."""
        if key in self._mem_cache:
            self._mem_cache.move_to_end(key)
        self._mem_cache[key] = data
        self._trim_memory_cache()

    def get_memory(self, key: str) -> Optional[bytes]:
        """Retrieve item from memory cache, updating LRU status."""
        if key in self._mem_cache:
            self._mem_cache.move_to_end(key)
            return self._mem_cache[key]
        return None

    def _trim_memory_cache(self) -> None:
        """Evict oldest items if exceeding memory threshold."""
        while len(self._mem_cache) > self._max_mem_entries:
            self._mem_cache.popitem(last=False)

    def _enforce_disk_quota(self) -> None:
        """Evict oldest files on disk if total cache size exceeds quota."""
        try:
            total_size = 0
            file_list = []
            for root, _, files in os.walk(self.cache_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        st = os.stat(fp)
                        total_size += st.st_size
                        file_list.append((st.st_mtime, fp, st.st_size))
                    except OSError:
                        pass

            if total_size > self._max_disk_bytes:
                # Sort oldest modified first
                file_list.sort(key=lambda x: x[0])
                for _, path, size in file_list:
                    try:
                        os.remove(path)
                        total_size -= size
                        if total_size <= self._max_disk_bytes * 0.8:
                            break
                    except OSError:
                        pass
        except Exception as e:
            logger.error("Error enforcing disk quota: %s", e)

    def get_total_cache_size_bytes(self) -> int:
        """Calculate total cache directory size on disk."""
        total = 0
        try:
            for root, _, files in os.walk(self.cache_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
        except Exception:
            pass
        return total

    def clear_cache(self) -> bool:
        """Purge all cached avatars and media."""
        try:
            self._mem_cache.clear()
            for root, dirs, files in os.walk(self.cache_dir):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except OSError:
                        pass
                for d in dirs:
                    try:
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    except OSError:
                        pass
            os.makedirs(self.avatars_dir, exist_ok=True)
            os.makedirs(self.media_dir, exist_ok=True)
            return True
        except Exception as e:
            logger.error("Failed to clear cache: %s", e)
            return False
