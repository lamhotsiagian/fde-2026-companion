import time, numpy as np
DIM, RANK, K, SEED = 768, 48, 10, 42
rng = np.random.default_rng(SEED)
def unit(x): return x/(np.linalg.norm(x,axis=1,keepdims=True)+1e-12)
print(f"Brute-force (numpy BLAS) single-query latency vs catalog size | dim={DIM} k={K}", flush=True)
print(f"{'catalog':>10} | {'p50':>9} {'p95':>9}", flush=True)
for n in [50000,100000,200000]:
    basis=rng.standard_normal((RANK,DIM)).astype(np.float32)
    corpus=unit(rng.standard_normal((n,RANK)).astype(np.float32)@basis)
    qs=unit(rng.standard_normal((120,RANK)).astype(np.float32)@basis)
    lat=[]
    for q in qs:
        t0=time.perf_counter()
        sims=corpus@q; idx=np.argpartition(-sims,K)[:K]; idx[np.argsort(-sims[idx])]
        lat.append((time.perf_counter()-t0)*1000)
    print(f"{n:>10,} | {np.percentile(lat,50):>8.3f}ms {np.percentile(lat,95):>8.3f}ms", flush=True)
