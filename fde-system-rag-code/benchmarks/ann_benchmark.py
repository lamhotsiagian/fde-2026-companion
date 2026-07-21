#!/usr/bin/env python3
"""
ann_benchmark.py  --  Measured brute-force vs HNSW candidate retrieval.

HNSW is run via `hnswlib`, the reference implementation of the same Hierarchical
Navigable Small World algorithm PostgreSQL `pgvector`'s `hnsw` index uses, so the
latency/recall shape transfers directly to the pgvector serving path.

Corpus model: real embeddings live on a low-dimensional manifold (intrinsic dim
far below the 768 ambient dims). We synthesise vectors as a few latent factors
projected up -> genuine, distinct nearest neighbours (not uniform noise, not
near-duplicate ties).

Run:  python3 ann_benchmark.py [comma,sizes]   Deps: numpy, hnswlib
"""
import sys, time
import numpy as np
import hnswlib

DIM  = 768          # nomic-embed-text dimensionality (matches the project)
RANK = 48           # intrinsic (latent) dim of the embedding manifold
K    = 10
M, EF_C, EF_S = 16, 100, 64
SEED = 42
SIZES = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1000, 10000, 100000]

def unit_rows(x):
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)

def brute_force_topk(corpus, q, k):
    sims = corpus @ q
    idx = np.argpartition(-sims, k)[:k]
    return idx[np.argsort(-sims[idx])]

def pctl_ms(t, p):
    return float(np.percentile(np.array(t) * 1000.0, p))

def bench(n, rng):
    nq = 500 if n <= 10000 else 150
    basis = rng.standard_normal((RANK, DIM)).astype(np.float32)
    corpus  = unit_rows(rng.standard_normal((n,  RANK)).astype(np.float32) @ basis)
    queries = unit_rows(rng.standard_normal((nq, RANK)).astype(np.float32) @ basis)

    bf_lat, gt = [], []
    for q in queries:
        t0 = time.perf_counter()
        top = brute_force_topk(corpus, q, K)
        bf_lat.append(time.perf_counter() - t0)
        gt.append(set(top.tolist()))

    index = hnswlib.Index(space="cosine", dim=DIM)
    index.init_index(max_elements=n, ef_construction=EF_C, M=M)
    t0 = time.perf_counter(); index.add_items(corpus, np.arange(n))
    build_s = time.perf_counter() - t0
    index.set_ef(EF_S)

    ann_lat, hits = [], 0
    for i, q in enumerate(queries):
        t0 = time.perf_counter()
        labels, _ = index.knn_query(q, k=K)
        ann_lat.append(time.perf_counter() - t0)
        hits += len(gt[i] & set(labels[0].tolist()))
    recall = hits / (K * nq)
    return dict(n=n, build_s=build_s, recall=recall,
                bf50=pctl_ms(bf_lat,50), bf95=pctl_ms(bf_lat,95),
                a50=pctl_ms(ann_lat,50), a95=pctl_ms(ann_lat,95))

def main():
    rng = np.random.default_rng(SEED)
    print(f"ANN retrieval benchmark | dim={DIM} rank={RANK} k={K} HNSW(M={M},ef_c={EF_C},ef_s={EF_S})", flush=True)
    print("-"*92, flush=True)
    print(f"{'catalog':>9} | {'build':>7} | {'brute p50':>10} {'brute p95':>10} | {'HNSW p50':>9} {'HNSW p95':>9} | {'recall@10':>9} | {'speedup':>7}", flush=True)
    print("-"*92, flush=True)
    for n in SIZES:
        r = bench(n, rng)
        sp = r["bf50"]/r["a50"] if r["a50"] else 0
        print(f"{r['n']:>9,} | {r['build_s']:>6.2f}s | {r['bf50']:>9.3f}ms {r['bf95']:>9.3f}ms | {r['a50']:>8.3f}ms {r['a95']:>8.3f}ms | {r['recall']*100:>8.1f}% | {sp:>6.1f}x", flush=True)
    print("-"*92, flush=True)
    print("HNSW via hnswlib == the algorithm pgvector's `hnsw` index implements.", flush=True)

if __name__ == "__main__":
    main()
