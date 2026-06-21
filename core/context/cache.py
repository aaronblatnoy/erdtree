"""
core/context/cache.py

Short-TTL in-memory cache for SystemSnapshot.

The live box is ALWAYS the source of truth (design decision #5 / invariant I8).
This cache is a latency optimization ONLY — it keeps repeated reads within a
short window from hammering /proc, rpm, and systemctl on every token.

Cache entries expire after ``ttl`` seconds (default 5 s, tunable).
An expired entry is re-collected on the next read; the caller always gets
fresh data within one TTL window.

No tier names (I6). No AI/LLM language (I2).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from core.context.collector import Collector
from core.context.snapshot import SystemSnapshot

_DEFAULT_TTL: float = 5.0   # seconds — keeps context "instant" (I8)


class SnapshotCache:
    """
    Thread-safe, TTL-based cache wrapping a Collector.

    Usage::

        cache = SnapshotCache()             # default 5-s TTL
        snap = cache.get()                  # collects on first call
        snap2 = cache.get()                 # returns cached if < TTL
        cache.invalidate()                  # force next .get() to re-collect
        fresh = cache.get(force=True)       # force this call to re-collect

    Parameters
    ----------
    collector:
        The Collector to delegate to. Defaults to a fresh ``Collector()``
        with default subprocess runner (mock it in tests).
    ttl:
        Time-to-live in seconds for a cached snapshot. 0 = always re-collect.
    """

    def __init__(
        self,
        collector: Optional[Collector] = None,
        ttl: float = _DEFAULT_TTL,
    ) -> None:
        self._collector: Collector = collector if collector is not None else Collector()
        self._ttl: float = ttl
        self._lock = threading.Lock()
        self._snapshot: Optional[SystemSnapshot] = None
        self._expires_at: float = 0.0   # monotonic epoch; 0 = never cached

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, *, force: bool = False) -> SystemSnapshot:
        """
        Return a SystemSnapshot, re-collecting if the cache is cold or stale.

        Parameters
        ----------
        force:
            If True, always re-collect regardless of TTL.
        """
        with self._lock:
            now = time.monotonic()
            if force or self._snapshot is None or now >= self._expires_at:
                self._snapshot = self._collector.collect()
                self._expires_at = now + self._ttl
            return self._snapshot

    def invalidate(self) -> None:
        """
        Expire the current cache entry. The next call to :meth:`get` will
        re-collect from the live system.
        """
        with self._lock:
            self._snapshot = None
            self._expires_at = 0.0

    @property
    def ttl(self) -> float:
        """The configured TTL in seconds."""
        return self._ttl

    @ttl.setter
    def ttl(self, value: float) -> None:
        if value < 0:
            raise ValueError(f"TTL must be >= 0, got {value!r}")
        with self._lock:
            self._ttl = value

    def is_warm(self) -> bool:
        """True iff there is a non-expired entry in the cache right now."""
        with self._lock:
            return (
                self._snapshot is not None
                and time.monotonic() < self._expires_at
            )
