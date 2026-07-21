"""Drill 13 — Token bucket rate limiter.

Respect 60 requests/minute without serialising everything.

Brute:      sleep(1) between calls. Correct, and throws away all your throughput.
Optimal:    continuous refill. Tokens accrue at rate/sec up to a capacity, so a
            burst after an idle period is allowed — which is what you want.
Production: the limit belongs to the provider account, not to your process. Two
            pods each holding a local bucket will together break the limit.
            Redis-backed, or a single limiter service.
"""
from __future__ import annotations

import time


class TokenBucket:
    def __init__(self, rate_per_minute: float, capacity: float | None = None,
                 now: float | None = None) -> None:
        self.rate = rate_per_minute / 60.0
        self.capacity = capacity if capacity is not None else rate_per_minute
        self._tokens = self.capacity
        self._updated = now if now is not None else time.monotonic()

    def try_acquire(self, n: float = 1.0, now: float | None = None) -> bool:
        """Non-blocking. True if n tokens were available and consumed."""
        raise NotImplementedError

    def wait_time(self, n: float = 1.0, now: float | None = None) -> float:
        """Seconds until n tokens would be available. 0.0 if available now."""
        raise NotImplementedError


def test_burst_up_to_capacity():
    b = TokenBucket(rate_per_minute=60, capacity=5, now=0.0)
    assert all(b.try_acquire(now=0.0) for _ in range(5))
    assert not b.try_acquire(now=0.0)


def test_refills_continuously():
    b = TokenBucket(rate_per_minute=60, capacity=1, now=0.0)   # 1/sec
    assert b.try_acquire(now=0.0)
    assert not b.try_acquire(now=0.5)
    assert b.try_acquire(now=1.0)


def test_wait_time_is_reported():
    b = TokenBucket(rate_per_minute=60, capacity=1, now=0.0)
    b.try_acquire(now=0.0)
    assert 0.4 < b.wait_time(now=0.5) < 0.6
    assert b.wait_time(now=2.0) == 0.0


def test_never_exceeds_capacity_after_long_idle():
    b = TokenBucket(rate_per_minute=60, capacity=3, now=0.0)
    assert sum(b.try_acquire(now=10_000.0) for _ in range(10)) == 3
