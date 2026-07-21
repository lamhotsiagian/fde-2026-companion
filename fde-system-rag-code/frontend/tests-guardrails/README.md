# Guardrails UI screenshot suite

Real, reproducible screenshots of each guardrail behaving in the live UI — one
PNG per test, no fabrication.

## Setup (once)

```bash
cd frontend
npm i -D @playwright/test
npx playwright install chromium
# copy these files in:
#   frontend/playwright.config.ts
#   frontend/tests-guardrails/guardrails.spec.ts
```

## Prereqs the tests assume

1. Stack up: backend on :8000, frontend on :3000.
2. Guardrails live: migration applied and `GUARD_ENABLED=true`.
   ```bash
   psql $DATABASE_URL -f backend/scripts/migrations/002_guardrails.sql
   cd backend && python -m scripts.seed_guardrails_demo   # centroids + clean/poisoned docs
   ```
3. A demo login. Export credentials:
   ```bash
   export E2E_EMAIL=demo@example.com E2E_PASSWORD='...'
   ```

## Run

```bash
cd frontend
E2E_BASE_URL=http://localhost:3000 npx playwright test guardrails.spec.ts
```

Screenshots are written to `frontend/test-results/screenshots/`:

| File | What it proves |
|------|----------------|
| `01_seed_catalog.png` | slash command seeds data |
| `02_clean_grounded_answer.png` | clean theory question answered through the guarded RAG path |
| `03_L1_injection_blocked.png` | L1 blocks a direct prompt injection |
| `04_L3_offtopic_deflected.png` | L3 deflects an off-topic request |
| `05_L5_arg_rejected.png` | L5 rejects `n=999999` (out of bounds) |
| `06_L5_hitl_confirm.png` | L5 asks to confirm `/reset-tenant-data` |
| `07_L6_indirect_injection_neutralised.png` | answer never repeats the injected `/reset-tenant-data` from the poisoned doc |

An HTML report (with the screenshots embedded) lands in
`frontend/test-results/report/`.

> These are integration tests against a live local stack; they exercise real
> `llama3.1` / `llama3.2:1b` calls, so timings and exact wording vary run to run.
