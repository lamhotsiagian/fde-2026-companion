"""Benchmark the per-layer latency overhead of the guardrail stack.

Mirrors the reporting style of the other scripts in benchmarks/ (p50/p95 on
the same hardware). Run with the stack up:

    python benchmarks/guard_latency.py --iters 50

CI budget suggestion (see tests/guardrails): all non-judge layers combined
p95 < 400 ms; judge layers (semantic NLI, output grounding) reported
separately because they run post-stream.
"""

import argparse
import asyncio
import statistics
import time

from langchain_core.messages import HumanMessage

PROMPTS = [
    "What is the difference between HR@10 and NDCG@10?",
    "Explain user-user collaborative filtering with cosine similarity.",
    "How does the two-tower model generate candidates?",
]


def pct(values: list[float], p: float) -> float:
    values = sorted(values)
    idx = min(int(len(values) * p), len(values) - 1)
    return values[idx]


async def time_layer(name: str, fn, iters: int) -> dict:
    samples: list[float] = []
    for i in range(iters):
        t0 = time.perf_counter()
        await fn(PROMPTS[i % len(PROMPTS)])
        samples.append((time.perf_counter() - t0) * 1000)
    return {"layer": name, "p50": pct(samples, 0.50), "p95": pct(samples, 0.95)}


async def main(iters: int) -> None:
    from app.guardrails.input_guard import _structured_classifier, INPUT_GUARD_PROMPT
    from app.guardrails.intent_guard import _embedder, _max_centroid_similarity
    from app.guardrails.validators import normalize_input, redact_pii

    async def t0_deterministic(prompt: str):
        redact_pii(normalize_input(prompt))

    async def t1_centroid(prompt: str):
        emb = await _embedder.aembed_query(prompt)
        await _max_centroid_similarity(emb)

    async def t2_classifier(prompt: str):
        await _structured_classifier.ainvoke(INPUT_GUARD_PROMPT.format(text=prompt))

    rows = [
        await time_layer("T0 normalize+PII (input)", t0_deterministic, iters),
        await time_layer("T1 centroid intent (pgvector)", t1_centroid, iters),
        await time_layer("T2 classifier (llama3.2:1b)", t2_classifier, max(iters // 5, 5)),
    ]

    print(f"\n{'Layer':<38}{'p50 ms':>10}{'p95 ms':>10}")
    print("-" * 58)
    for r in rows:
        print(f"{r['layer']:<38}{r['p50']:>10.1f}{r['p95']:>10.1f}")
    non_judge_p95 = sum(r["p95"] for r in rows)
    print("-" * 58)
    print(f"{'sum of pre-generation layers':<38}{'':>10}{non_judge_p95:>10.1f}")
    print("\nBudget check: pre-generation p95 should stay under 400 ms.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iters", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(main(args.iters))
