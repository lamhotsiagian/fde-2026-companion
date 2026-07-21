"""Mock 19B - Embedding-based deduplication.

Prompt: given strings and an embedding function, collapse any pair with cosine
similarity above a threshold, keeping the first occurrence.

deduplicate()      - the interview answer, exact, fine to ~10K items.
deduplicate_ann()  - the staff answer, approximate, for 100K+.
tune_threshold()   - the part candidates forget: the threshold is a decision
                     you make against labelled data, not a magic number.
"""
from __future__ import annotations

from typing import Callable, Iterable, Sequence

import numpy as np


def _l2_normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    # Zero vectors would produce NaN and silently poison every comparison.
    norms[norms == 0] = 1.0
    return m / norms


def deduplicate(
    items: Sequence[str],
    embed: Callable[[Sequence[str]], np.ndarray],
    threshold: float = 0.9,
) -> list[str]:
    if not items:
        return []
    embs = _l2_normalize(np.asarray(embed(items), dtype=np.float32))
    keep: list[str] = []
    kept: list[np.ndarray] = []
    for s, e in zip(items, embs):
        if kept and float(np.max(np.stack(kept) @ e)) >= threshold:
            continue
        keep.append(s)
        kept.append(e)
    return keep


def deduplicate_ann(
    items: Sequence[str],
    embed: Callable[[Sequence[str]], np.ndarray],
    threshold: float = 0.9,
    top_k: int = 25,
) -> list[str]:
    """Incremental HNSW dedup. Falls back to exact if faiss is unavailable."""
    try:
        import faiss  # type: ignore
    except ImportError:
        return deduplicate(items, embed, threshold)

    embs = _l2_normalize(np.asarray(embed(items), dtype=np.float32))
    index = faiss.IndexHNSWFlat(embs.shape[1], 32)
    index.metric_type = faiss.METRIC_INNER_PRODUCT

    keep: list[str] = []
    for s, e in zip(items, embs):
        if index.ntotal:
            sims, _ = index.search(e.reshape(1, -1), min(top_k, index.ntotal))
            if float(sims.max()) >= threshold:
                continue
        index.add(e.reshape(1, -1))
        keep.append(s)
    return keep


def tune_threshold(
    pairs: Iterable[tuple[str, str, bool]],
    embed: Callable[[Sequence[str]], np.ndarray],
    grid: Sequence[float] = tuple(np.arange(0.70, 0.99, 0.01)),
) -> tuple[float, float]:
    """Pick the threshold that maximises F1 on labelled (a, b, is_dup) pairs.

    This is the answer to "how do you choose the threshold for a customer who
    hasn't seen the data yet?" -- you don't. You build 200 labelled pairs with
    them in an hour and let the data choose.
    """
    pairs = list(pairs)
    if not pairs:
        raise ValueError("need labelled pairs to tune a threshold")
    a = _l2_normalize(np.asarray(embed([p[0] for p in pairs]), dtype=np.float32))
    b = _l2_normalize(np.asarray(embed([p[1] for p in pairs]), dtype=np.float32))
    sims = np.sum(a * b, axis=1)
    y = np.array([p[2] for p in pairs], dtype=bool)

    best = (0.0, 0.0)
    for t in grid:
        pred = sims >= t
        tp = int(np.sum(pred & y))
        fp = int(np.sum(pred & ~y))
        fn = int(np.sum(~pred & y))
        if tp == 0:
            continue
        prec, rec = tp / (tp + fp), tp / (tp + fn)
        f1 = 2 * prec * rec / (prec + rec)
        if f1 > best[1]:
            best = (float(t), f1)
    return best
