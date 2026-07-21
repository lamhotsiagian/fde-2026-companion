# Coding drills

Five drills ship as complete files: a failing test suite plus a docstring stating the
brute / optimal / production tiers. The other fifteen in the table below are specified but
not yet written — the five here are the template, and writing the rest yourself is the
exercise. Files that exist are marked with a check.
Solve it, run `pytest`, then read `SOLUTIONS.md` — which gives brute / optimal / production
for each, matching the three answer tiers used throughout the book.

```bash
pip install -r ../requirements.txt
pytest drills/            # all should fail on a fresh clone
pytest drills/d01_*.py    # one at a time
```

Do them out loud. The drill is not the algorithm; the drill is narrating the algorithm while
your hands are busy.

| # | Drill | Pattern | LLM twist | File |
|---|---|---|---|---|
| 01 | Streaming top-k by frequency | heap | token frequency on a live stream | `d01_streaming_topk.py` |
| 02 | Sliding window unique | two-pointer | context window packing | — |
| 03 | Token budget truncation | greedy | drop-from-middle policy | `d03_token_budget.py` |
| 04 | Cosine top-k search | sort/heap | normalise first, always | — |
| 05 | Naive BPE merge step | counting | tokeniser internals | — |
| 06 | Malformed JSON repair | parsing | structured-output recovery | — |
| 07 | Prompt cache with TTL | hash map | lazy eviction | — |
| 08 | Agent loop with max steps | state machine | runaway-cost guard | — |
| 09 | Stuck-loop detection | hashing | repeated (action, args) | `d09_stuck_loop.py` |
| 10 | Recency-weighted rerank | sorting | relevance x decay | — |
| 11 | Chunk text with overlap | two-pointer | boundary correctness | — |
| 12 | Merge k sorted result sets | heap | multi-index retrieval | — |
| 13 | Token bucket rate limiter | simulation | provider quotas | `d13_token_bucket.py` |
| 14 | Exponential backoff with jitter | math | thundering herd | — |
| 15 | LRU cache | linked list + map | embedding cache | — |
| 16 | Interval merge | greedy | transcript segment merge | — |
| 17 | Topological sort | graph | tool dependency order | — |
| 18 | Reservoir sampling | probability | online eval sampling | — |
| 19 | Levenshtein distance | 2D DP | fuzzy citation matching | — |
| 20 | Streaming percentile | heaps | p95 latency without storing all | `d20_streaming_percentile.py` |
