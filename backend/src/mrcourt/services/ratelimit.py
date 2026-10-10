"""Small in-process sliding-window rate limiter.

Good enough for a single API process (constitution principle VI). If the API is ever run as
several processes, swap the storage for a shared one without changing callers.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_buckets: dict[str, deque[float]] = defaultdict(deque)


def hit(key: str, limit: int, window_seconds: int) -> None:
    """Record an attempt; raise 429 when the limit inside the window is exceeded."""
    now = time.monotonic()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again later.")
    bucket.append(now)


def reset_all() -> None:
    _buckets.clear()
