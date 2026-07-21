# Measured benchmark results

Reproducible measurements backing the numbers printed in Chapters 6, 8, and 9.
Captured 2026-07-06 on a 4-core Linux sandbox, NumPy 2.2 (OpenBLAS), hnswlib.
Fixed seed = 42, so re-running reproduces these within timing noise.

## 1. ANN retrieval — `ann_benchmark.py`  (HNSW via hnswlib == pgvector's hnsw algorithm)

HNSW(M=16, ef_construction=100, ef_search=64), dim=768, k=10, low-rank embedding manifold:

    catalog |  build |  brute p50   brute p95 |  HNSW p50   HNSW p95 | recall@10 | speedup
      1,000 |  0.27s |    0.036ms     0.051ms |   0.706ms    0.781ms |    99.6%  |   0.1x
     10,000 |  5.18s |    0.310ms     0.373ms |   1.467ms    1.700ms |    90.6%  |   0.2x
     20,000 | 13.18s |    0.609ms     0.729ms |   1.676ms    1.972ms |    83.5%  |   0.4x

Brute-force (numpy BLAS) single-query latency scaling — `brute_scaling.py`:

    catalog |     p50       p95
     50,000 |  1.571ms    3.370ms
    100,000 |  3.325ms    6.375ms
    200,000 |  6.050ms    7.352ms

Reading: brute force is O(n) (0.036 -> 0.31 -> 0.61 -> 1.57 -> 3.33 -> 6.05 ms),
HNSW query latency is roughly flat (~0.7-1.7 ms). Crossover is ~30-50k items;
below it brute force wins (index overhead dominates), above it HNSW wins and the
gap widens toward the asymptotic O(log n) vs O(n) at 10^6+ items. Recall is
tunable via ef_search (higher ef -> higher recall, higher latency).

## 2. Matrix factorization — `mf_eval.py`  (the book's SGD dot-product model)

k=32, lr=0.01, reg=0.05, epochs=40; synthetic planted-rank ratings (seed 42);
per-user leave-one-out ranking with 100 sampled negatives (He et al., 2017):

    Training time            :   6.35 s  (960,000 SGD updates)
    Serve latency (p50/p95)  :  0.0101 / 0.0142 ms  (dot-product scoring)
    RMSE (held-out ratings)  :  0.9156   [global-mean baseline 1.1406]
    HR@10  (leave-one-out)   :  27.9%    [random 9.9%]
    NDCG@10                  :  0.1404

Reading: the factorizer recovers real latent signal — RMSE ~20% below the
global-mean baseline, and HR@10 ~2.8x the random 9.9%. Numbers are modest
because the model is deliberately the book's bias-free MF on sparse data; adding
user/item biases and more epochs lifts all three.

## 3. Two-tower retrieval — `two_tower.py`  (in-batch negative sampling)

ID-embedding two-tower, d=32, in-batch softmax, 60 epochs; same leave-one-out
protocol as `mf_eval.py`:

    Training time            :   1.29 s
    HR@10  (leave-one-out)   :  13.4%   [random 9.9%, pointwise MF 27.9%]
    NDCG@10                  : 0.0572

Reading: the two-tower genuinely learns (above the 9.9% random floor) but does
NOT beat the regression MF on this small, dense 800x400 dataset. That is the
honest, correct lesson — two-tower is a RETRIEVAL architecture whose advantage is
asymptotic (billions of items, rich features, hard negatives), not rating
accuracy on tiny data. It replaces Chapter 7's simulated (random) loss curve.

## 4. MMR diversity re-ranking — `mmr_rerank.py`

Greedy MMR over a 60-item candidate pool, k=10, 300 queries, low-rank embeddings:

     lambda |  relevance@10 |  diversity@10
        1.0 |       0.6017  |       0.6323   (pure relevance baseline)
        0.7 |       0.5893  |       0.6784
        0.5 |       0.5519  |       0.7360
        0.3 |       0.5225  |       0.7696

Reading: lowering lambda trades a small relevance cost (0.60 -> 0.52) for a large
diversity gain (0.63 -> 0.77). This is the re-rank stage's dial.

## 5. Cold-start exploration bandit — `bandit_coldstart.py`

K=20 arms, T=20,000 rounds, 20 runs, Bernoulli CTRs ~ U(0.02, 0.20); cumulative
regret vs always playing the best arm (lower is better):

        policy |  cumulative regret |  vs random
        random |            1590.2  |      100%
        greedy |             812.6  |       51%
       epsilon |             300.5  |       19%
      thompson |             265.4  |       17%

Reading: smart exploration (Thompson, epsilon-greedy) cuts regret to ~1/5 of
random and ~1/3 of pure-exploit greedy. Thompson edges out epsilon-greedy at long
horizon because it stops exploring once confident, while epsilon-greedy keeps
paying a fixed exploration tax.
