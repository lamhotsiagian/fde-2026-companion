# FDE 2026 — companion repository

Companion to *Cracking the Forward Deployed AI Engineer Interview* (2026 edition).

Premium Guide: https://shop.beacons.ai/aiengineeringinsider/9e9d6725-9511-41a2-afd8-9b07d6e307a4

<img width="1241" height="1754" alt="FDE_Ebook_2026-1-30-1-15_page-0001" src="https://github.com/user-attachments/assets/2cdf252c-80c8-48ae-9373-34127be8dd9d" />


Everything the book tells you to build, in a form you can run rather than retype out of a PDF.

```bash
git clone <this repo> && cd fde-2026-companion
pip install -r requirements.txt
pytest                       # drills fail (they're exercises); mocks pass (they're solutions)
```

## What's here

| Path | What it is |
|---|---|
| `drills/` | Coding drills as failing pytest suites. Five written, fifteen specified. Each docstring states the brute / optimal / production tiers. |
| `mocks/` | Worked solutions to Mocks 19A, 19B, 19C, with the tests that prove them — including the edge cases interviewers actually probe. |
| `eval-harness/` | A production eval loop small enough to read in one sitting: golden set → scorers → sliced report → regression gate. Runs out of the box. |
| `templates/` | All 14 artifacts from Appendix E as editable Markdown. |
| `capacity/` | `fde_capacity_model.xlsx` — five live-formula models for GPU sizing, query cost, voice latency, self-host break-even and business value. `build_model.py` regenerates the workbook; see `capacity/README.md` for what each sheet answers. |
| `market-data.md` | The volatile half of Chapter 2 — companies, posted ranges, and the method for re-running the search yourself. Last verified 2026-05-06; re-verified quarterly. |
| `fde-system-rag/` | The complete reference implementation dissected in **Chapter 12**: FastAPI + LangGraph + pgvector + Next.js, hybrid retrieval, a ten-layer guardrail stack, long-term memory and NDJSON streaming. `docker-compose up --build` and it runs, fully local. It's tracked as its own git repository (own `.git`, `.gitignore`), so it isn't affected by this repo's `.gitignore`. |

## Start here, depending on why you came

**Interview in two weeks.** `mocks/` first — read the solutions, then delete them and rewrite
from the tests. Then `templates/14-reverse-interview-questions.md`.

**Interview in two months.** `drills/` daily, out loud, one per morning. `eval-harness/` on a
weekend — being able to say "here is the eval harness I built" is worth more in an FDE loop
than another twenty LeetCode problems.

**Already in the job.** `templates/` and `capacity/`. The spreadsheet is designed to be filled
in live on a customer call.

**Building the portfolio project.** `fde-system-rag/`, with Chapter 12 open beside it. The
chapter includes an honest audit of what in that codebase is production-shaped and what is
not — the defect list is deliberate, and fixing it is the exercise.

## The eval harness

```bash
cd eval-harness
python harness.py golden_set.jsonl --baseline baseline.json --gate 0.02
```

Reports overall and per-slice metrics, p50/p95 latency and cost per 1,000 queries, then exits
non-zero if any tracked metric dropped more than two points against baseline. That last part
is the whole point: an eval you look at is a dashboard, an eval that can block a merge is a loop.

## Contributing

Corrections welcome, especially to `market-data.md` — it is the file most likely to be wrong
by the time you read it.

`.gitignore` excludes `__pycache__/`, `.pytest_cache/`, `.venv/`, and `.DS_Store` from this
repo. `fde-system-rag/` is a separate git repository with its own `.gitignore` (Node,
Next.js build output, logs, LaTeX build artifacts, etc.) — nothing there is duplicated here.

## Licence

Code MIT. Book text is not included here and remains © the author.
# fde-2026-companion
