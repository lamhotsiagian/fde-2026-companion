#!/usr/bin/env python3
"""
mf_eval.py -- Measured evaluation of the book's SGD matrix factorization.

Trains the EXACT latent-factor SGD from Chapter 9 (pure dot-product model, no
biases) and reports MEASURED metrics on two axes:

  * Accuracy  : RMSE on held-out ratings (with a global-mean baseline).
  * Ranking   : leave-one-out HR@10 and NDCG@10 with 100 sampled negatives --
                the standard protocol of He et al. (2017); random baseline HR@10
                = 10/101 ~= 9.9%, so anything well above that is real signal.

Dataset: a reproducible synthetic ratings matrix with PLANTED low-rank latent
structure plus noise (the regime MF is designed for). Swap in MovieLens
(user,item,rating,ts) tuples and the metric code is unchanged.

Run:  python3 mf_eval.py     Deps: numpy
"""
import time
import numpy as np

U, I, K_TRUE = 800, 400, 8
RATINGS_PER_USER, TEST_PER_USER = 40, 10
MU = 3.5
K, LR, REG, EPOCHS = 32, 0.01, 0.05, 40
TOPK, REL_THRESH, N_NEG = 10, 4.0, 100
SEED = 42


def make_dataset(rng):
    Pt = rng.standard_normal((U, K_TRUE)) * 0.6
    Qt = rng.standard_normal((I, K_TRUE)) * 0.6
    bu = rng.standard_normal(U) * 0.5
    bi = rng.standard_normal(I) * 0.5
    rows = []
    for u in range(U):
        items = rng.choice(I, size=RATINGS_PER_USER, replace=False)
        for order, it in enumerate(items):
            r = MU + bu[u] + bi[it] + Pt[u] @ Qt[it] + rng.normal(0, 0.5)
            rows.append((u, it, float(np.clip(r, 1.0, 5.0)), order))
    return rows


def split(rows):
    by_user = {}
    for u, it, r, order in rows:
        by_user.setdefault(u, []).append((order, it, r))
    train, test = [], {}
    for u, lst in by_user.items():
        lst.sort()
        cut = len(lst) - TEST_PER_USER
        train += [(u, it, r) for _, it, r in lst[:cut]]
        test[u] = [(it, r) for _, it, r in lst[cut:]]
    return train, test


def train_mf(train, rng):
    P = rng.uniform(-0.1, 0.1, (U, K))
    Q = rng.uniform(-0.1, 0.1, (I, K))
    t0 = time.perf_counter()
    for _ in range(EPOCHS):
        rng.shuffle(train)
        for u, it, r in train:
            err = r - P[u] @ Q[it]
            pu = P[u].copy()
            P[u] += LR * (err * Q[it] - REG * pu)
            Q[it] += LR * (err * pu - REG * Q[it])
    return P, Q, time.perf_counter() - t0


def evaluate(P, Q, train, test, rng):
    seen = {}
    for u, it, r in train:
        seen.setdefault(u, set()).add(it)
    se = n = 0.0
    hits, ndcgs, serve_lat = [], [], []
    for u, items in test.items():
        for it, r in items:
            se += (r - P[u] @ Q[it]) ** 2; n += 1
        # leave-one-out positive: the highest-rated held-out item (if relevant)
        pos_it, pos_r = max(items, key=lambda x: x[1])
        if pos_r < REL_THRESH:
            continue
        # sample N_NEG unseen negatives
        forbidden = seen.get(u, set()) | {it for it, _ in items}
        negs = []
        while len(negs) < N_NEG:
            c = int(rng.integers(0, I))
            if c not in forbidden:
                negs.append(c)
        cand = np.array([pos_it] + negs)
        t0 = time.perf_counter()
        scores = Q[cand] @ P[u]
        order = cand[np.argsort(-scores)]
        serve_lat.append((time.perf_counter() - t0) * 1000)
        rank = int(np.where(order == pos_it)[0][0])   # 0-based rank of positive
        hits.append(1 if rank < TOPK else 0)
        ndcgs.append(1.0 / np.log2(rank + 2) if rank < TOPK else 0.0)
    rmse = (se / n) ** 0.5
    base_rmse = (sum((r - MU) ** 2 for _, its in test.items() for _, r in its) / n) ** 0.5
    return dict(rmse=rmse, base_rmse=base_rmse, hr=np.mean(hits), ndcg=np.mean(ndcgs),
                serve_p50=np.percentile(serve_lat, 50), serve_p95=np.percentile(serve_lat, 95),
                users=len(hits))


def main():
    rng = np.random.default_rng(SEED)
    train, test = split(make_dataset(rng))
    print(f"MF evaluation | users={U} items={I} train={len(train)} test/user={TEST_PER_USER}")
    print(f"model: SGD dot-product  k={K}, lr={LR}, reg={REG}, epochs={EPOCHS}")
    P, Q, secs = train_mf(train, rng)
    m = evaluate(P, Q, train, test, rng)
    print("-" * 68)
    print(f"  Training time             : {secs:6.2f} s  ({len(train)*EPOCHS:,} SGD updates)")
    print(f"  Serve latency (p50/p95)   : {m['serve_p50']:.4f} / {m['serve_p95']:.4f} ms  (dot-product scoring)")
    print("-" * 68)
    print(f"  RMSE (held-out ratings)   : {m['rmse']:.4f}   [global-mean baseline {m['base_rmse']:.4f}]")
    print(f"  HR@{TOPK}  (leave-one-out)   : {m['hr']*100:5.1f}%   [random {TOPK/(N_NEG+1)*100:.1f}%]")
    print(f"  NDCG@{TOPK}                  : {m['ndcg']:.4f}")
    print(f"  (leave-one-out over {m['users']} users, 1 positive vs {N_NEG} sampled negatives)")


if __name__ == "__main__":
    main()
