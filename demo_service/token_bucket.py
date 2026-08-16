"""Asynchronous Token Bucket Rate Limiter — Real-world concurrency control."""

import asyncio
import time
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    """Outcome of a rate limit check."""

    allowed: bool
    remaining_tokens: float
    retry_after_seconds: float


class AsyncTokenBucketLimiter:
    """Thread-safe and async-safe token bucket rate limiter."""

    def __init__(self, capacity: float = 10.0, refill_rate_per_sec: float = 2.0):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate_per_sec)
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens_needed: float = 1.0) -> RateLimitResult:
        """Attempt to acquire tokens atomically."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return RateLimitResult(allowed=True, remaining_tokens=self.tokens, retry_after_seconds=0.0)
            else:
                needed = tokens_needed - self.tokens
                retry_after = needed / self.refill_rate if self.refill_rate > 0 else 1.0
                return RateLimitResult(allowed=False, remaining_tokens=self.tokens, retry_after_seconds=retry_after)
