import asyncio

import numpy as np
import pytest

from mock_19a_stream_aggregator import (
    BoundedStreamAggregator, StreamAggregator, Token, detect_repeating_ngram)
from mock_19b_dedup import deduplicate, tune_threshold
from mock_19c_worker_pool import LLMWorkerPool, RetryPolicy, TokenBucket


# ---- 19A -------------------------------------------------------------------
def test_aggregator_basic():
    a = StreamAggregator()
    for i, (s, lp) in enumerate([("Hel", -0.1), ("lo", -0.3)]):
        a.add(Token(s, lp, i))
    assert a.text() == "Hello"
    assert a.avg_logprob() == pytest.approx(-0.2)
    assert not a.is_stuck()


def test_empty_stream_does_not_raise():
    assert StreamAggregator().avg_logprob() == 0.0
    assert StreamAggregator().is_stuck() is False


def test_stuck_detection_needs_full_window():
    a = StreamAggregator(stuck_threshold=3)
    a.add(Token("x", -0.1, 0)); a.add(Token("x", -0.1, 1))
    assert not a.is_stuck()            # shorter than the window
    a.add(Token("x", -0.1, 2))
    assert a.is_stuck()
    a.add(Token("y", -0.1, 3))
    assert not a.is_stuck()            # window slides, recovers


def test_bounded_aggregator_drops_old_text():
    a = BoundedStreamAggregator(keep_chars=10)
    for i in range(50):
        a.add(Token("abcde", -0.1, i))
    assert len(a.text()) <= 15
    assert a.dropped_chars > 0
    assert len(a) == 50                # count is still exact


def test_repeating_ngram():
    assert detect_repeating_ngram(["the", "cat", "sat"] * 4, n=3, repeats=4)
    assert not detect_repeating_ngram(["a", "b", "c", "d"], n=3, repeats=4)


# ---- 19B -------------------------------------------------------------------
def _fake_embed(items):
    # One-hot on the first letter plus a small length signal. Words sharing a
    # first letter are near-duplicates; others are near-orthogonal.
    out = np.zeros((len(items), 27), dtype=np.float32)
    for i, s in enumerate(items):
        out[i, (ord(s[0].lower()) - 97) % 26] = 1.0
        out[i, 26] = len(s) * 0.01
    return out


def test_dedup_collapses_near_duplicates():
    out = deduplicate(["apple", "apricot", "banana"], _fake_embed, threshold=0.999)
    assert out == ["apple", "banana"]


def test_dedup_preserves_first_occurrence_and_handles_empty():
    assert deduplicate([], _fake_embed) == []
    assert deduplicate(["zebra"], _fake_embed) == ["zebra"]


def test_tune_threshold_picks_a_separating_value():
    pairs = [("apple", "apricot", True), ("apple", "banana", False)]
    t, f1 = tune_threshold(pairs, _fake_embed)
    assert 0.0 < t < 1.0 and f1 > 0.0


# ---- 19C -------------------------------------------------------------------
def test_token_bucket_enforces_rate():
    async def run():
        b = TokenBucket(rate_per_minute=600, capacity=2)   # 10/sec, burst 2
        import time as _t
        start = _t.monotonic()
        for _ in range(5):
            await b.acquire()
        return _t.monotonic() - start
    # 2 free, then 3 more at 10/sec => >= ~0.3s
    assert asyncio.run(run()) >= 0.25


def test_pool_retries_then_succeeds():
    calls = {"n": 0}

    async def flaky(_):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    pool = LLMWorkerPool(flaky, max_concurrency=2, rate_per_minute=6000,
                         retry=RetryPolicy(attempts=3, base_delay=0.01))
    assert asyncio.run(pool.map(["a"])) == ["ok"]
    assert pool.stats.retries == 2 and pool.stats.succeeded == 1


def test_pool_respects_concurrency_cap():
    live = {"now": 0, "max": 0}

    async def watched(_):
        live["now"] += 1
        live["max"] = max(live["max"], live["now"])
        await asyncio.sleep(0.02)
        live["now"] -= 1
        return 1

    pool = LLMWorkerPool(watched, max_concurrency=3, rate_per_minute=100000)
    asyncio.run(pool.map(list(range(20))))
    assert live["max"] <= 3


def test_pool_surfaces_permanent_failure():
    async def always_fail(_):
        raise ConnectionError("down")

    pool = LLMWorkerPool(always_fail, rate_per_minute=100000,
                         retry=RetryPolicy(attempts=2, base_delay=0.01))
    out = asyncio.run(pool.map(["x"], return_exceptions=True))
    assert isinstance(out[0], ConnectionError)
    assert pool.stats.failed == 1
