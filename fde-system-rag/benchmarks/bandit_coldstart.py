#!/usr/bin/env python3
"""
bandit_coldstart.py -- Exploration for cold-start, measured as cumulative regret.

A new item has no engagement, so pure exploitation never gives it the impressions
needed to learn its true CTR -> the popularity echo chamber. A multi-armed bandit
spends a controlled exploration budget instead. We simulate K arms (e.g. candidate
items) with unknown Bernoulli click-through rates and MEASURE cumulative regret
(reward lost vs always playing the best arm) for four policies.

Run:  python3 bandit_coldstart.py     Deps: numpy
"""
import numpy as np

K, T, EPS, RUNS, SEED = 20, 20000, 0.10, 20, 42


def run_policy(policy, ctr, rng):
    n = np.zeros(K); s = np.zeros(K)            # pulls, successes per arm
    best = ctr.max(); regret = 0.0
    for t in range(T):
        if policy == "random":
            a = rng.integers(K)
        elif policy == "greedy":                # pure exploit (epsilon = 0)
            a = int(np.argmax(np.where(n > 0, s / np.maximum(n, 1), 1.0)))
        elif policy == "epsilon":
            a = rng.integers(K) if rng.random() < EPS else \
                int(np.argmax(np.where(n > 0, s / np.maximum(n, 1), 1.0)))
        else:  # thompson (Beta-Bernoulli)
            a = int(np.argmax(rng.beta(s + 1, n - s + 1)))
        r = 1.0 if rng.random() < ctr[a] else 0.0
        n[a] += 1; s[a] += r
        regret += best - ctr[a]
    return regret


def main():
    rng = np.random.default_rng(SEED)
    policies = ["random", "greedy", "epsilon", "thompson"]
    totals = {p: [] for p in policies}
    for _ in range(RUNS):
        ctr = rng.uniform(0.02, 0.20, K)         # true (unknown) click-through rates
        for p in policies:
            totals[p].append(run_policy(p, ctr, np.random.default_rng(rng.integers(1 << 30))))
    print(f"Cold-start bandit | arms={K} rounds={T} runs={RUNS} eps={EPS}")
    print(f"{'policy':>10} | {'cumulative regret':>18} | {'vs random':>10}")
    print("-" * 46)
    base = np.mean(totals["random"])
    for p in policies:
        m = np.mean(totals[p])
        print(f"{p:>10} | {m:>17.1f}  | {m/base*100:>8.0f}%")
    print("-" * 46)
    print("Lower regret = better. Thompson/epsilon explore smartly; greedy can lock")
    print("onto a wrong early winner; random never exploits.")


if __name__ == "__main__":
    main()
