"""In-memory per-user rate limiting (sliding windows).

One limit: batches per rolling hour (a coarse spam guard on top of the
DB-backed daily quotas in services/quota.py). Counters live in memory only and
reset on restart — acceptable per spec.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

_HOUR = 3600


class RateLimiter:
    def __init__(self, max_batches_per_hour: int) -> None:
        self._max_batches = max_batches_per_hour
        self._batches: dict[int, deque[float]] = defaultdict(deque)

    @staticmethod
    def _prune(timestamps: deque[float], window: float, now: float) -> None:
        while timestamps and now - timestamps[0] >= window:
            timestamps.popleft()

    def _check(self, store: dict[int, deque[float]], user_id: int, limit: int, window: float):
        """Return (allowed, seconds_until_reset)."""
        now = time.monotonic()
        timestamps = store[user_id]
        self._prune(timestamps, window, now)
        if len(timestamps) < limit:
            return True, 0.0
        # Reset when the oldest timestamp falls out of the window.
        reset_in = window - (now - timestamps[0])
        return False, max(reset_in, 0.0)

    # --- Batches ---------------------------------------------------------
    def check_batch(self, user_id: int) -> tuple[bool, float]:
        return self._check(self._batches, user_id, self._max_batches, _HOUR)

    def record_batch(self, user_id: int) -> None:
        self._batches[user_id].append(time.monotonic())
