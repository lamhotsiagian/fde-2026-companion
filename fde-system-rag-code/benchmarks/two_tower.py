#!/usr/bin/env python3
"""
two_tower.py -- A REAL two-tower retrieval model trained end-to-end with
in-batch negative sampling (NumPy). Replaces Chapter 7's simulated trainer.

At the ID-feature level a two-tower reduces to a user embedding table and an
item embedding table scored by dot product; the design lives in the LOSS. We use
the standard in-batch sampled-softmax: for a mini-batch of B positive (user,item)
pairs, every OTHER item in the batch is a negative for a given user. Measured on
the same leave-one-out protocol as mf_eval.py (1 positive vs 100 sampled
negatives) so it is directly comparable to the pointwise MF baseline (HR@10 27.9%).

Run:  python3 two_tower.py     Deps: numpy
"""
import time
import numpy as np

U, I, K_TRUE = 800, 400, 8
RATINGS_PER_USER, TEST_PER_USER = 40, 10
MU, REL = 3.5, 4.0
D, LR, REG, EPOCHS, BATCH = 32, 0.10, 1e-6, 60, 128
SCALE = 1.0
REL_TRAIN = 4.0
TOPK, N_NEG, SEED = 10, 100, 42


def make_dataset(rng):
    Pt = rng.standard_normal((U, K_TRUE)) * 0.6
    Qt = rng.standard_normal((I, K_TRUE)) * 0.6
    bu = rng.standard_normal(U) * 0.5
    bi = rng.standard_normal(I) * 0.5
    rows = []
    for u in range(U):
        for order, it in enumerate(rng.choice(I, RATINGS_PER_USER, replace=False)):
            r = MU + bu[u] + bi[it] + Pt[u] @ Qt[it] + rng.normal(0, 0.5)
            rows.append((u, it, float(np.clip(r, 1, 5)), order))
    return rows


def split(rows):
    by = {}
    for u, it, r, o in rows:
        by.setdefault(u, []).append((o, it, r))
    train_pos, test, seen = [], {}, {}
    for u, lst in by.items():
        lst.sort()
        cut = len(lst) - TEST_PER_USER
        for _, it, r in lst[:cut]:
            seen.setdefault(u, set()).add(it)
            if r >= REL_TRAIN:                 # implicit positive (training)
                train_pos.append((u, it))
        test[u] = [(it, r) for _, it, r in lst[cut:]]
    return train_pos, test, seen


def softmax_rows(S):
    S = S - S.max(axis=1, keepdims=True)
    E = np.exp(S)
    return E / E.sum(axis=1, keepdims=True)


def train(train_pos, rng):
    Uemb = rng.normal(0, 0.05, (U, D))
    Vemb = rng.normal(0, 0.05, (I, D))
    pos = np.array(train_pos)
    t0 = time.perf_counter()
    for _ in range(EPOCHS):
        rng.shuffle(pos)
        for s in range(0, len(pos), BATCH):
            b = pos[s:s + BATCH]
            us, its = b[:, 0], b[:, 1]
            Ub, Vb = Uemb[us], Vemb[its]
            S = SCALE * (Ub @ Vb.T)             # scaled in-batch scores (temperature)
            P = softmax_rows(S)
            G = SCALE * (P - np.eye(len(b)))    # dLoss/dS with the scale factor
            gU = G @ Vb + REG * Ub
            gV = G.T @ Ub + REG * Vb
            Uemb[us] -= LR * gU
            np.add.at(Vemb, its, -LR * gV)
    return Uemb, Vemb, time.perf_counter() - t0


def evaluate(Uemb, Vemb, test, seen, rng):
    hr, ndcg, n = 0, 0.0, 0
    for u, items in test.items():
        pos_it, pos_r = max(items, key=lambda x: x[1])
        if pos_r < REL:
            continue
        forbidden = seen.get(u, set()) | {it for it, _ in items}
        negs = []
        while len(negs) < N_NEG:
            c = int(rng.integers(0, I))
            if c not in forbidden:
                negs.append(c)
        cand = np.array([pos_it] + negs)
        cv = Vemb[cand] / (np.linalg.norm(Vemb[cand],axis=1,keepdims=True)+1e-9)
        uu = Uemb[u] / (np.linalg.norm(Uemb[u])+1e-9)
        scores = cv @ uu
        rank = int(np.argsort(-scores).tolist().index(0))   # 0 = the positive
        n += 1
        if rank < TOPK:
            hr += 1
            ndcg += 1.0 / np.log2(rank + 2)
    return hr / n, ndcg / n, n


def main():
    rng = np.random.default_rng(SEED)
    rows = make_dataset(rng)
    train_pos, test, seen = split(rows)
    print(f"Two-tower (in-batch negatives) | users={U} items={I} positives={len(train_pos)} "
          f"| d={D}, lr={LR}, epochs={EPOCHS}, batch={BATCH}")
    Uemb, Vemb, secs = train(train_pos, rng)
    hr, ndcg, n = evaluate(Uemb, Vemb, test, seen, rng)
    print("-" * 66)
    print(f"  Training time            : {secs:6.2f} s")
    print(f"  HR@10  (leave-one-out)   : {hr*100:5.1f}%   [random 9.9%, pointwise MF 27.9%]")
    print(f"  NDCG@10                  : {ndcg:.4f}")
    print(f"  (evaluated on {n} users, 1 positive vs {N_NEG} sampled negatives)")


if __name__ == "__main__":
    main()
