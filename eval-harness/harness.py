"""A production eval loop small enough to read in one sitting.

Golden set -> scorers -> report -> regression gate. That is the whole shape.
Everything else (dashboards, LLM judges, online sampling) hangs off these four.

Run:  python harness.py golden_set.jsonl --baseline baseline.json --gate 0.02
"""
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable


# --------------------------------------------------------------------------
# 1. Golden set
# --------------------------------------------------------------------------
@dataclass
class Example:
    id: str
    question: str
    expected: str
    contexts: list[str]
    tags: list[str]          # e.g. ["homeowners", "exclusions"] -- slice on these


@dataclass
class Prediction:
    id: str
    answer: str
    retrieved: list[str]
    latency_ms: float
    cost_usd: float


def load_golden(path: str | Path) -> list[Example]:
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    return [Example(**r) for r in rows]


# --------------------------------------------------------------------------
# 2. Scorers -- deterministic first, judges last
# --------------------------------------------------------------------------
Scorer = Callable[[Example, Prediction], float]


def retrieval_recall(ex: Example, pred: Prediction) -> float:
    """Did we retrieve the contexts the answer actually needs?

    Run this before you touch generation quality. Most 'the model is
    hallucinating' tickets are retrieval failures wearing a costume.
    """
    if not ex.contexts:
        return 1.0
    hit = sum(1 for c in ex.contexts if any(c in r for r in pred.retrieved))
    return hit / len(ex.contexts)


def exact_contains(ex: Example, pred: Prediction) -> float:
    return 1.0 if ex.expected.lower() in pred.answer.lower() else 0.0


def is_citation_present(ex: Example, pred: Prediction) -> float:
    return 1.0 if ("[" in pred.answer and "]" in pred.answer) else 0.0


def refusal_when_unsupported(ex: Example, pred: Prediction) -> float:
    """If nothing relevant was retrieved, the correct answer is 'I don't know'."""
    if retrieval_recall(ex, pred) > 0:
        return 1.0
    said_no = any(p in pred.answer.lower()
                  for p in ("i don't know", "i do not know", "not covered", "no basis"))
    return 1.0 if said_no else 0.0


def llm_judge_faithfulness(judge: Callable[[str], float]) -> Scorer:
    """Wrap your judge call. Kept last and kept optional on purpose.

    A judge is the most expensive, least stable scorer you own. Pin the judge
    model, randomise option order, and never let it gate a release alone.
    """
    def _score(ex: Example, pred: Prediction) -> float:
        prompt = (f"Context:\n{chr(10).join(pred.retrieved)}\n\n"
                  f"Answer:\n{pred.answer}\n\n"
                  "Is every claim in the answer supported by the context? "
                  "Reply with a number 0.0-1.0 only.")
        return judge(prompt)
    return _score


DEFAULT_SCORERS: dict[str, Scorer] = {
    "retrieval_recall": retrieval_recall,
    "answer_match": exact_contains,
    "citation_present": is_citation_present,
    "refusal_when_unsupported": refusal_when_unsupported,
}


# --------------------------------------------------------------------------
# 3. Report -- overall and sliced, because the average always lies
# --------------------------------------------------------------------------
@dataclass
class Report:
    n: int
    metrics: dict[str, float]
    by_tag: dict[str, dict[str, float]]
    p50_latency_ms: float
    p95_latency_ms: float
    cost_per_1k_usd: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def evaluate(examples: Iterable[Example], preds: dict[str, Prediction],
             scorers: dict[str, Scorer] | None = None) -> Report:
    scorers = scorers or DEFAULT_SCORERS
    examples = [e for e in examples if e.id in preds]
    if not examples:
        raise ValueError("no predictions matched the golden set")

    raw = {name: [] for name in scorers}
    per_tag: dict[str, dict[str, list[float]]] = {}
    lat, cost = [], []

    for ex in examples:
        p = preds[ex.id]
        lat.append(p.latency_ms)
        cost.append(p.cost_usd)
        for name, fn in scorers.items():
            s = float(fn(ex, p))
            raw[name].append(s)
            for tag in ex.tags:
                per_tag.setdefault(tag, {}).setdefault(name, []).append(s)

    lat_sorted = sorted(lat)
    return Report(
        n=len(examples),
        metrics={k: round(statistics.fmean(v), 4) for k, v in raw.items()},
        by_tag={t: {k: round(statistics.fmean(v), 4) for k, v in m.items()}
                for t, m in sorted(per_tag.items())},
        p50_latency_ms=round(lat_sorted[len(lat_sorted) // 2], 1),
        p95_latency_ms=round(lat_sorted[min(len(lat_sorted) - 1,
                                            int(0.95 * len(lat_sorted)))], 1),
        cost_per_1k_usd=round(statistics.fmean(cost) * 1000, 4),
    )


# --------------------------------------------------------------------------
# 4. Regression gate -- the part that makes it a loop instead of a dashboard
# --------------------------------------------------------------------------
def gate(report: Report, baseline: dict[str, float], tolerance: float = 0.02
         ) -> tuple[bool, list[str]]:
    """Block the release if any tracked metric dropped more than `tolerance`.

    Two percentage points is a defensible default. The number matters less than
    having one at all, agreed in advance, and enforced by CI rather than by
    whoever is loudest in the room.
    """
    failures = []
    for name, base in baseline.items():
        now = report.metrics.get(name)
        if now is None:
            failures.append(f"{name}: missing from this run")
        elif now < base - tolerance:
            failures.append(f"{name}: {now:.3f} < baseline {base:.3f} "
                            f"(-{base - now:.3f}, tolerance {tolerance})")
    return (not failures), failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("golden")
    ap.add_argument("--predictions", default=None,
                    help="JSONL of predictions; omit to run the built-in demo")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--gate", type=float, default=0.02)
    args = ap.parse_args()

    examples = load_golden(args.golden)
    if args.predictions:
        preds = {p["id"]: Prediction(**p)
                 for p in map(json.loads, Path(args.predictions).read_text().splitlines())}
    else:  # demo mode: echo the expected answer so the harness is runnable as-is
        preds = {e.id: Prediction(e.id, f"{e.expected} [1]", e.contexts, 900.0, 0.004)
                 for e in examples}

    report = evaluate(examples, preds)
    print(report.to_json())

    if args.baseline:
        ok, failures = gate(report, json.loads(Path(args.baseline).read_text()), args.gate)
        if not ok:
            print("\nREGRESSION GATE FAILED:")
            for f in failures:
                print("  -", f)
            return 1
        print("\nregression gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
