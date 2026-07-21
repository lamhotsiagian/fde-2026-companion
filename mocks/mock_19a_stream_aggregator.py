"""Mock 19A - Streaming Token Aggregator.

Prompt: tokens stream from an LLM one at a time. Each has a string, a logprob
and an index. Implement add(), text(), avg_logprob() and is_stuck() -- where
"stuck" means the same string repeated N times in a row.

The interview answer is StreamAggregator. BoundedStreamAggregator is the
staff-level follow-up: bound memory on very long streams.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    text: str
    logprob: float
    index: int


class StreamAggregator:
    """O(1) per token. Running sum for the mean, fixed window for stuck detection."""

    def __init__(self, stuck_threshold: int = 10) -> None:
        if stuck_threshold < 1:
            raise ValueError("stuck_threshold must be >= 1")
        self._parts: list[str] = []
        self._sum_logprob = 0.0
        self._n = 0
        self._tail: deque[str] = deque(maxlen=stuck_threshold)
        self._threshold = stuck_threshold

    def add(self, t: Token) -> None:
        self._parts.append(t.text)
        self._sum_logprob += t.logprob
        self._n += 1
        self._tail.append(t.text)

    def text(self) -> str:
        return "".join(self._parts)

    def avg_logprob(self) -> float:
        # Empty stream returns 0.0 rather than raising: callers poll this on a
        # live stream and a health check should not throw before token one.
        return self._sum_logprob / self._n if self._n else 0.0

    def is_stuck(self) -> bool:
        return len(self._tail) == self._threshold and len(set(self._tail)) == 1

    def __len__(self) -> int:
        return self._n


class BoundedStreamAggregator(StreamAggregator):
    """Staff-level variant: keeps only the last `keep_chars` of text.

    Long agent runs can emit millions of tokens. Holding every part is a slow
    memory leak that only shows up in production, under the longest sessions,
    which are usually your most valuable customers.
    """

    def __init__(self, stuck_threshold: int = 10, keep_chars: int = 8192) -> None:
        super().__init__(stuck_threshold)
        self._keep = keep_chars
        self._dropped = 0

    def add(self, t: Token) -> None:
        super().add(t)
        while sum(len(p) for p in self._parts[:1]) and self._chars() > self._keep:
            self._dropped += len(self._parts.pop(0))

    def _chars(self) -> int:
        return sum(len(p) for p in self._parts)

    @property
    def dropped_chars(self) -> int:
        return self._dropped


def detect_repeating_ngram(tokens: list[str], n: int = 3, repeats: int = 4) -> bool:
    """Follow-up: detect 'the the the' style loops, not just single-token loops."""
    if len(tokens) < n * repeats:
        return False
    window = tokens[-n * repeats:]
    first = window[:n]
    return all(window[i * n:(i + 1) * n] == first for i in range(repeats))
