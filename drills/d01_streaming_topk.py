"""Drill 01 — Streaming top-k by frequency.

Tokens arrive one at a time. At any point, return the k most frequent.

Brute:      recount and sort on every query. O(n log n) per call.
Optimal:    frequency map + heap of size k. O(log k) per insert.
Production: unbounded cardinality eats memory. Count-min sketch, or cap the
            map and evict the long tail. Ask which one you are being graded on.
"""
from __future__ import annotations

import heapq
from collections import Counter


class StreamingTopK:
    def __init__(self, k: int) -> None:
        self.k = k
        self._counts: Counter[str] = Counter()

    def add(self, token: str) -> None:
        raise NotImplementedError

    def top_k(self) -> list[tuple[str, int]]:
        """Most frequent first; ties broken by token, ascending."""
        raise NotImplementedError


def test_topk():
    s = StreamingTopK(2)
    for t in "a b a c a b".split():
        s.add(t)
    assert s.top_k() == [("a", 3), ("b", 2)]


def test_topk_fewer_than_k():
    s = StreamingTopK(5)
    s.add("only")
    assert s.top_k() == [("only", 1)]


def test_topk_empty():
    assert StreamingTopK(3).top_k() == []
