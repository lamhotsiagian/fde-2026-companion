"""Drill 03 — Truncate context to a token budget.

You have retrieved chunks and a hard budget. Something has to go.

Brute:      drop from the end until it fits.
Optimal:    drop from the middle. Models attend most reliably to the start and
            the end of the context; the middle is where recall degrades first.
Production: never split a citation from its chunk, and log what you dropped.
            "Why did it miss that document?" is answerable only if you logged it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    tokens: int
    doc_id: str


def fit_to_budget(chunks: list[Chunk], budget: int,
                  policy: str = "middle") -> tuple[list[Chunk], list[str]]:
    """Return (kept chunks in original order, dropped doc_ids)."""
    raise NotImplementedError


def _c(n, i):
    return Chunk(f"c{i}", n, f"d{i}")


def test_fits_untouched():
    cs = [_c(10, 0), _c(10, 1)]
    kept, dropped = fit_to_budget(cs, 100)
    assert kept == cs and dropped == []


def test_drops_from_middle_first():
    cs = [_c(10, i) for i in range(5)]
    kept, dropped = fit_to_budget(cs, 30, policy="middle")
    assert sum(c.tokens for c in kept) <= 30
    assert "d0" in [c.doc_id for c in kept]      # head survives
    assert "d4" in [c.doc_id for c in kept]      # tail survives
    assert "d2" in dropped                        # middle goes first


def test_reports_what_it_dropped():
    cs = [_c(10, i) for i in range(5)]
    kept, dropped = fit_to_budget(cs, 20)
    assert len(dropped) == 3 and len(kept) == 2
