"""Drill 20 — Streaming p95 without storing every sample.

You need p95 latency on a dashboard that runs forever.

Brute:      keep every sample and sort. Works until it doesn't.
Optimal:    two heaps holding a fixed quantile split, or a t-digest.
Production: p95 on a 24h window is nearly useless for incident response. What you
            want is a sliding window, plus the ability to slice by tenant — because
            "p95 is fine" and "your biggest customer is timing out" are both true
            more often than anyone likes.
"""
from __future__ import annotations


class StreamingPercentile:
    """Approximate percentile over a bounded reservoir."""

    def __init__(self, q: float = 0.95, capacity: int = 1000, seed: int = 0) -> None:
        self.q = q
        self.capacity = capacity
        self._seed = seed
        self._n = 0
        self._samples: list[float] = []

    def add(self, x: float) -> None:
        """Reservoir sampling: every observation has equal probability of being kept."""
        raise NotImplementedError

    def value(self) -> float:
        """Current estimate. 0.0 on an empty stream."""
        raise NotImplementedError


def test_empty():
    assert StreamingPercentile().value() == 0.0


def test_exact_below_capacity():
    p = StreamingPercentile(q=0.5, capacity=100)
    for x in range(1, 101):
        p.add(float(x))
    assert 45 <= p.value() <= 55


def test_bounded_memory():
    p = StreamingPercentile(capacity=50)
    for x in range(10_000):
        p.add(float(x))
    assert len(p._samples) <= 50


def test_approximates_high_quantile():
    p = StreamingPercentile(q=0.95, capacity=2000)
    for x in range(1, 10_001):
        p.add(float(x))
    assert 9_000 <= p.value() <= 10_000
