# Benchmarks — measured numbers for the ebook

These self-contained scripts produce the **measured** figures cited in the book,
replacing earlier illustrative/simulated values.

    pip install numpy hnswlib
    python3 ann_benchmark.py            # brute-force vs HNSW retrieval (Ch. 8)
    python3 brute_scaling.py            # brute-force latency vs catalog size (Ch. 8)
    python3 mf_eval.py                  # RMSE / HR@10 / NDCG@10 for the MF model (Ch. 6, 9)
    python3 two_tower.py                # two-tower w/ in-batch negatives (Ch. 7)
    python3 mmr_rerank.py               # MMR diversity re-ranking trade-off (Ch. 8)
    python3 bandit_coldstart.py         # cold-start exploration bandit regret (Ch. 5)

All scripts use a fixed seed (42) and print a table to stdout. `ann_benchmark.py`
takes an optional comma-separated size list, e.g. `python3 ann_benchmark.py 1000,10000,20000`.
See `RESULTS.md` for the captured output and how to read it. HNSW is measured with
`hnswlib`, the reference implementation of the same algorithm PostgreSQL
`pgvector`'s `hnsw` index uses; swap `mf_eval.py`'s synthetic loader for MovieLens
tuples to reproduce on real data.
