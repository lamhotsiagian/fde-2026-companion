#!/usr/bin/env bash
# ============================================================================
#  run_guardrail_ui_tests.sh
#  One-command automation: install Playwright if needed, run the guardrail UI
#  suite against the LIVE local stack, and collect a real screenshot per test.
#
#  Prereqs (see tests-guardrails/README.md):
#    - backend :8000 + frontend :3000 running, GUARD_ENABLED=true
#    - migration applied + `python -m scripts.seed_guardrails_demo`
#    - export E2E_EMAIL / E2E_PASSWORD for a demo account
#
#  Usage:
#    E2E_EMAIL=demo@example.com E2E_PASSWORD='...' ./run_guardrail_ui_tests.sh
# ============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$HERE/frontend"

: "${E2E_BASE_URL:=http://localhost:3000}"
: "${E2E_EMAIL:?set E2E_EMAIL to a demo account email}"
: "${E2E_PASSWORD:?set E2E_PASSWORD to the demo account password}"

echo "==> Checking the app is reachable at $E2E_BASE_URL ..."
curl -sf -o /dev/null "$E2E_BASE_URL" || {
  echo "ERROR: $E2E_BASE_URL is not reachable. Start the stack first."; exit 1; }

cd "$FRONTEND"

if ! npx --no-install playwright --version >/dev/null 2>&1; then
  echo "==> Installing @playwright/test ..."
  npm install -D @playwright/test
fi
echo "==> Ensuring the Chromium browser is installed ..."
npx playwright install chromium

echo "==> Running the guardrail UI suite ..."
E2E_BASE_URL="$E2E_BASE_URL" E2E_EMAIL="$E2E_EMAIL" E2E_PASSWORD="$E2E_PASSWORD" \
  npx playwright test guardrails.spec.ts

echo ""
echo "==> Screenshots:"
ls -1 "$FRONTEND/test-results/screenshots/" 2>/dev/null || echo "  (none — check test output above)"
echo "==> HTML report: $FRONTEND/test-results/report/index.html"
