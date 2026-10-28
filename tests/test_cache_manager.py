"""
Tests for Low-RAM CacheManager.
Validates memory ceilings, disk quotas, LRU eviction, and low-resource mode.
"""

import os
import tempfile
import shutil
from storage.cache_manager import CacheManager


def test_memory_cache_lru():
    tmp_dir = tempfile.mkdtemp()
    try:
        cm = CacheManager(cache_dir=tmp_dir, max_mem_entries=3)

        cm.put_memory("a", b"1")
        cm.put_memory("b", b"2")
        cm.put_memory("c", b"3")

        assert cm.get_memory("a") == b"1"
        assert cm.get_memory("b") == b"2"
        assert cm.get_memory("c") == b"3"

        # Putting 4th item should evict the least recently used ('a' was accessed before 'b' and 'c')
        cm.put_memory("d", b"4")
        assert len(cm._mem_cache) == 3
        assert cm.get_memory("d") == b"4"
    finally:
        shutil.rmtree(tmp_dir)


def test_low_resource_mode():
    tmp_dir = tempfile.mkdtemp()
    try:
        cm = CacheManager(cache_dir=tmp_dir, max_mem_entries=40, low_resource_mode=False)
        assert cm.low_resource_mode is False

        # Switch to low resource mode
        cm.low_resource_mode = True
        assert cm.low_resource_mode is True
        assert cm._max_mem_entries == 15
        assert cm._max_disk_bytes == 10 * 1024 * 1024
    finally:
        shutil.rmtree(tmp_dir)


def test_clear_cache():
    tmp_dir = tempfile.mkdtemp()
    try:
        cm = CacheManager(cache_dir=tmp_dir)
        avatar_path = cm.get_avatar_path(12345)
        with open(avatar_path, "wb") as f:
            f.write(b"dummy image data")

        assert cm.has_cached_avatar(12345) is True
        assert cm.get_total_cache_size_bytes() > 0

        cm.clear_cache()
        assert cm.has_cached_avatar(12345) is False
        assert cm.get_total_cache_size_bytes() == 0
    finally:
        shutil.rmtree(tmp_dir)
