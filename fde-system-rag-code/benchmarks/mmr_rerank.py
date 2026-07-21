#!/usr/bin/env python3
"""
mmr_rerank.py -- Maximal Marginal Relevance (MMR) diversity re-ranking.

The re-rank stage of the funnel (Chapter 8) trades a little relevance for
diversity so the slate is not ten near-duplicates. MMR selects items greedily:

    next = argmax_{i in cand\\S} [ lambda * rel(i) - (1-lambda) * max_{j in S} sim(i,j) ]

lambda=1 is pure relevance (the ranking baseline); lower lambda buys diversity.
We MEASURE the trade-off: mean relevance@10 vs intra-list diversity
(1 - mean pairwise cosine) over many queries, on low-rank embeddings.

Run:  python3 mmr_rerank.py     Deps: numpy
"""
import numpy as np

DIM, RANK, N_ITEMS, POOL, K, N_QUERIES, SEED = 768, 24, 5000, 60, 10, 300, 42


def unit(x):
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


def mmr(cand_vecs, rel, lam, k):
    selected, remaining = [], list(range(len(cand_vecs)))
    while len(selected) < k and remaining:
        best, best_score = None, -1e9
        for i in remaining:
            div_pen = max((cand_vecs[i] @ cand_vecs[j] for j in selected), default=0.0)
            score = lam * rel[i] - (1 - lam) * div_pen
            if score > best_score:
                best, best_score = i, score
        selected.append(best); remaining.remove(best)
    return selected


def intra_list_diversity(vecs):
    n = len(vecs)
    sims = [vecs[a] @ vecs[b] for a in range(n) for b in range(a + 1, n)]
    return 1.0 - float(np.mean(sims))


def main():
    rng = np.random.default_rng(SEED)
    basis = rng.standard_normal((RANK, DIM)).astype(np.float32)
    items = unit(rng.standard_normal((N_ITEMS, RANK)).astype(np.float32) @ basis)
    print(f"MMR re-ranking | items={N_ITEMS} pool={POOL} k={K} queries={N_QUERIES}")
    print(f"{'lambda':>7} | {'relevance@10':>13} | {'diversity@10':>13}")
    print("-" * 42)
    for lam in [1.0, 0.7, 0.5, 0.3]:
        rels, divs = [], []
        for _ in range(N_QUERIES):
            q = unit(rng.standard_normal((1, RANK)).astype(np.float32) @ basis)[0]
            sims = items @ q
            pool = np.argsort(-sims)[:POOL]           # candidate set from ranker
            sel = mmr(items[pool], sims[pool], lam, K)
            chosen = pool[sel]
            rels.append(float(np.mean(sims[chosen])))
            divs.append(intra_list_diversity(items[chosen]))
        tag = "  (pure relevance)" if lam == 1.0 else ""
        print(f"{lam:>7.1f} | {np.mean(rels):>12.4f}  | {np.mean(divs):>12.4f}{tag}")
    print("-" * 42)
    print("Lower lambda -> small relevance cost, higher intra-list diversity.")


if __name__ == "__main__":
    main()
