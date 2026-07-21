"""Drill 09 — Detect a stuck agent loop.

An agent repeats (tool, args) forever. Catch it before the bill does.

Brute:      compare the last action to the previous one.
Optimal:    hash (tool, canonical-args) and count repeats in a window; also
            catch A-B-A-B cycles, not just A-A-A.
Production: the cheap guard is a hard step cap. The useful guard is this, because
            it tells you *which* tool is looping, which is what you need at 2am.
"""
from __future__ import annotations

import json
from collections import deque


class LoopDetector:
    def __init__(self, window: int = 8, repeat_threshold: int = 3) -> None:
        self.window = window
        self.threshold = repeat_threshold
        self._recent: deque[str] = deque(maxlen=window)

    @staticmethod
    def _key(tool: str, args: dict) -> str:
        # Canonical form: {"b":1,"a":2} and {"a":2,"b":1} are the same call.
        return tool + "|" + json.dumps(args, sort_keys=True, separators=(",", ":"))

    def observe(self, tool: str, args: dict) -> None:
        raise NotImplementedError

    def is_looping(self) -> bool:
        """True if any single action repeats >= threshold times in the window."""
        raise NotImplementedError

    def offending_action(self) -> str | None:
        """The action key that tripped the detector, for the incident log."""
        raise NotImplementedError


def test_detects_simple_repeat():
    d = LoopDetector(window=8, repeat_threshold=3)
    for _ in range(3):
        d.observe("search", {"q": "policy"})
    assert d.is_looping()
    assert "search" in (d.offending_action() or "")


def test_arg_order_does_not_matter():
    d = LoopDetector(repeat_threshold=2)
    d.observe("get", {"a": 1, "b": 2})
    d.observe("get", {"b": 2, "a": 1})
    assert d.is_looping()


def test_alternating_is_not_a_false_positive_below_threshold():
    d = LoopDetector(window=8, repeat_threshold=3)
    for _ in range(2):
        d.observe("a", {}); d.observe("b", {})
    assert not d.is_looping()


def test_window_slides():
    d = LoopDetector(window=3, repeat_threshold=3)
    d.observe("x", {}); d.observe("x", {}); d.observe("y", {})
    assert not d.is_looping()
