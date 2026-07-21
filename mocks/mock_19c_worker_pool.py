"""Mock 19C - Rate-limited LLM worker pool.

Prompt: async worker pool calling an LLM under three constraints --
max 5 concurrent requests, a token-bucket limit of 60 requests/minute, and
3 attempts with exponential backoff.

The three constraints are independent and compose. Candidates who conflate
concurrency with rate limiting lose the round.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Sequence


class TokenBucket:
    """Refills continuously, not on a timer. Handles bursts correctly."""

    def __init__(self, rate_per_minute: float, capacity: float | None = None) -> None:
        self._rate = rate_per_minute / 60.0
        self._capacity = capacity if capacity is not None else rate_per_minute
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: float = 1.0) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._capacity, self._tokens + (now - self._updated) * self._rate
                )
                self._updated = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                deficit = n - self._tokens
                wait = deficit / self._rate
            await asyncio.sleep(wait)


@dataclass
class RetryPolicy:
    attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 30.0
    jitter: bool = True
    # 429/5xx are retryable; a 400 is a bug in your prompt and retrying it three
    # times just burns money and latency.
    retry_on: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError)

    def delay_for(self, attempt: int) -> float:
        d = min(self.max_delay, self.base_delay * (2 ** attempt))
        return d * (0.5 + random.random()) if self.jitter else d


@dataclass
class PoolStats:
    submitted: int = 0
    succeeded: int = 0
    failed: int = 0
    retries: int = 0
    latencies: list[float] = field(default_factory=list)

    def p95(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        return s[min(len(s) - 1, int(0.95 * len(s)))]


class LLMWorkerPool:
    def __init__(
        self,
        call: Callable[[Any], Awaitable[Any]],
        max_concurrency: int = 5,
        rate_per_minute: float = 60,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._call = call
        self._sem = asyncio.Semaphore(max_concurrency)
        self._bucket = TokenBucket(rate_per_minute)
        self._retry = retry or RetryPolicy()
        self.stats = PoolStats()

    async def _one(self, item: Any) -> Any:
        last: BaseException | None = None
        for attempt in range(self._retry.attempts):
            await self._bucket.acquire()          # rate limit: global
            async with self._sem:                 # concurrency: in-flight cap
                started = time.monotonic()
                try:
                    result = await self._call(item)
                    self.stats.succeeded += 1
                    self.stats.latencies.append(time.monotonic() - started)
                    return result
                except self._retry.retry_on as exc:
                    last = exc
                    self.stats.retries += 1
            if attempt < self._retry.attempts - 1:
                await asyncio.sleep(self._retry.delay_for(attempt))
        self.stats.failed += 1
        raise last if last else RuntimeError("exhausted retries")

    async def map(self, items: Sequence[Any], return_exceptions: bool = True) -> list[Any]:
        self.stats.submitted += len(items)
        return await asyncio.gather(
            *(self._one(i) for i in items), return_exceptions=return_exceptions
        )
