"""Asynchronous Image and Thumbnail Downloader with RAM-disk support for pr0-retroconsole.

Downloads media files in background threads without blocking the main Pygame render loop.
Maintains a clean disk cache (max 100 files) and provides in-memory Pygame surfaces.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
import pygame
import requests

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger("pr0.cache")


class MediaCache:
    """Thread-safe background media downloader and cache manager."""

    def __init__(
        self,
        cache_dir: str = "/tmp/pr0cache",
        max_files: int = 100,
        max_memory_surfaces: int = 80,
    ):
        self.max_files = max_files
        self.max_memory_surfaces = max_memory_surfaces
        self.cache_dir = self._resolve_cache_dir(cache_dir)
        logger.info("Using cache directory: %s", self.cache_dir)

        # In-memory Surface cache: url -> (pygame.Surface, last_access_time)
        self._surface_cache: dict[str, tuple[pygame.Surface, float]] = {}
        self._surface_lock = threading.Lock()

        # Track pending / in-progress downloads: url -> timestamp
        self._pending_urls: set[str] = set()
        self._pending_lock = threading.Lock()

        # Fast lookup set of confirmed cached URLs (0% disk overhead)
        self._cached_urls: set[str] = set()

        # Task queue: tuple of (priority, url, local_path, is_thumb)
        # Lower priority number = processed first (0: urgent/fullsize, 1: visible thumb, 2: preload)
        self._queue: queue.PriorityQueue[tuple[int, float, str, str, bool]] = queue.PriorityQueue()

        # Results queue: tuple of (url, local_path, success)
        self._completed_queue: queue.Queue[tuple[str, str, bool]] = queue.Queue()

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _resolve_cache_dir(self, preferred_path: str) -> Path:
        """Resolve a writable cache directory, falling back from /tmp to local tempdir."""
        candidates = [
            Path(preferred_path),
            Path(tempfile.gettempdir()) / "pr0cache",
            Path.cwd() / "cache",
        ]
        for p in candidates:
            try:
                p.mkdir(parents=True, exist_ok=True)
                test_file = p / ".write_test"
                test_file.write_text("ok")
                test_file.unlink()
                return p
            except Exception as e:
                logger.warning("Could not use %s for cache (%s), trying next fallback...", p, e)

        fallback = Path("./cache")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _url_to_path(self, url: str) -> Path:
        """Generate a deterministic local filename from URL hash."""
        ext = os.path.splitext(urllib_path := url.split("?")[0])[1]
        if not ext or len(ext) > 5:
            ext = ".jpg"
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"pr0_{url_hash}{ext}"

    def get_surface(self, url: str, priority: int = 1) -> pygame.Surface | None:
        """Get preloaded Pygame Surface from memory or disk.

        If not cached, requests a background download and returns None.
        Must be called from the main Pygame thread.
        """
        if not url:
            return None

        # 1. Check in-memory cache
        with self._surface_lock:
            if url in self._surface_cache:
                surf, _ = self._surface_cache[url]
                self._surface_cache[url] = (surf, time.time())
                return surf

        local_path = self._url_to_path(url)

        # 2. Check disk cache
        if local_path.is_file() and local_path.stat().st_size > 0:
            surf = self._load_surface_from_disk(local_path)
            if surf is not None:
                self._put_surface(url, surf)
                return surf
            else:
                # Corrupted file, remove it
                try:
                    local_path.unlink()
                except Exception:
                    pass

        # 3. Not in disk or RAM: request download
        self.request_download(url, priority=priority)
        return None

    def _load_surface_from_disk(self, file_path: Path) -> pygame.Surface | None:
        """Load an image file safely into a Pygame Surface using SDL_image."""
        try:
            surf = pygame.image.load(str(file_path))
            return surf.convert_alpha() if surf.get_masks()[3] != 0 else surf.convert()
        except Exception:
            if Image is not None:
                try:
                    with Image.open(file_path) as img:
                        if img.mode not in ("RGB", "RGBA"):
                            img = img.convert("RGBA" if "A" in img.mode else "RGB")
                        return pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                except Exception as e:
                    logger.error("Failed to load image surface %s: %s", file_path, e)
            return None

    def _put_surface(self, url: str, surface: pygame.Surface) -> None:
        """Store surface in LRU memory cache."""
        with self._surface_lock:
            self._surface_cache[url] = (surface, time.time())
            # Evict if over limit
            if len(self._surface_cache) > self.max_memory_surfaces:
                oldest_key = min(self._surface_cache.keys(), key=lambda k: self._surface_cache[k][1])
                del self._surface_cache[oldest_key]

    def request_download(self, url: str, priority: int = 1) -> None:
        """Enqueue a background download if not already queued."""
        if not url:
            return
        local_path = self._url_to_path(url)
        if local_path.is_file() and local_path.stat().st_size > 0:
            return

        with self._pending_lock:
            if url in self._pending_urls:
                return
            self._pending_urls.add(url)

        # Queue item: (priority, timestamp, url, local_path_str, is_thumb)
        is_thumb = "thumb." in url
        self._queue.put((priority, time.time(), url, str(local_path), is_thumb))

    def _worker_loop(self) -> None:
        """Background thread worker pulling download jobs."""
        session = requests.Session()
        session.headers.update({"User-Agent": "pr0-retroconsole/1.0"})

        while self._running:
            try:
                priority, _, url, local_path_str, is_thumb = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue

            local_path = Path(local_path_str)
            success = False

            if not local_path.is_file() or local_path.stat().st_size == 0:
                try:
                    resp = session.get(url, timeout=12.0)
                    if resp.status_code == 200 and resp.content:
                        part_file = local_path.with_suffix(".part")
                        part_file.write_bytes(resp.content)
                        # Atomic rename
                        if local_path.exists():
                            local_path.unlink()
                        part_file.rename(local_path)
                        success = True
                        self._clean_cache_if_needed()
                except Exception as e:
                    logger.debug("Download failed for %s: %s", url, e)

            with self._pending_lock:
                self._pending_urls.discard(url)

            self._completed_queue.put((url, local_path_str, success))
            self._queue.task_done()

    def _clean_cache_if_needed(self) -> None:
        """Enforce maximum file count limit on disk cache."""
        try:
            files = list(self.cache_dir.glob("pr0_*"))
            if len(files) > self.max_files:
                # Sort by mtime ascending (oldest first)
                files.sort(key=lambda f: f.stat().st_mtime)
                to_delete = files[: len(files) - self.max_files]
                for f in to_delete:
                    try:
                        f.unlink()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Cache cleanup error: %s", e)

    def is_cached(self, url: str) -> bool:
        """Check if URL is available in memory or on disk."""
        if not url:
            return False
        if url in self._cached_urls:
            return True
        with self._surface_lock:
            if url in self._surface_cache:
                self._cached_urls.add(url)
                return True
        local_path = self._url_to_path(url)
        if local_path.is_file() and local_path.stat().st_size > 0:
            self._cached_urls.add(url)
            return True
        return False

    def preload_items(self, items: list[dict[str, Any]], count: int = 60) -> None:
        """Enqueue background downloads for feed thumbnails with low priority."""
        for item in items[:count]:
            thumb = item.get("thumb")
            if thumb:
                url = f"https://thumb.pr0gramm.com/{thumb}"
                if not self.is_cached(url):
                    self.request_download(url, priority=2)

    def get_progress(self, items: list[dict[str, Any]]) -> tuple[int, int, float]:
        """Calculate cache progress for the provided list of items.
        Returns: (cached_count, total_count, ratio_float)
        """
        if not items:
            return 0, 0, 1.0
        total = len(items)
        cached = 0
        for it in items:
            thumb = it.get("thumb")
            if thumb:
                url = f"https://thumb.pr0gramm.com/{thumb}"
                if self.is_cached(url):
                    cached += 1
        ratio = cached / total if total > 0 else 1.0
        return cached, total, ratio

    def get_local_path(self, url: str) -> str | None:
        """Return absolute path to cached file if available on disk, else None."""
        if not url:
            return None
        local_path = self._url_to_path(url)
        if local_path.is_file() and local_path.stat().st_size > 0:
            return str(local_path.resolve())
        return None

    def process_completed(self) -> list[str]:
        """Poll completed downloads on the main thread and update state."""
        completed_urls: list[str] = []
        while True:
            try:
                url, local_path_str, success = self._completed_queue.get_nowait()
                if success:
                    completed_urls.append(url)
                    self._cached_urls.add(url)
            except queue.Empty:
                break
        return completed_urls

    def clear_all(self) -> int:
        """Delete all cached files on disk and clear in-memory surfaces. Returns count of deleted files."""
        count = 0
        try:
            for f in self.cache_dir.glob("pr0_*"):
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Error clearing cache: %s", e)

        with self._surface_lock:
            self._surface_cache.clear()
        self._cached_urls.clear()

        logger.info("Cache cleared: %d files deleted.", count)
        return count

    def stop(self) -> None:
        """Terminate the background worker thread."""
        self._running = False
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

