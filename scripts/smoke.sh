#!/usr/bin/env bash
# Small local smoke check (expects `docker compose up` running).
set -euo pipefail
BASE="${BASE_URL:-http://localhost:8000}"
KEY="${DEMO_API_KEY:-demo-local-key}"
IDEMPOTENCY="pulseops-smoke-$(date +%s)"
curl --fail --silent "${BASE}/healthz" | python -m json.tool
curl --fail --silent -X POST "${BASE}/api/jobs" \
  -H 'Content-Type: application/json' \
  -H "X-Demo-Key: ${KEY}" \
  -H "Idempotency-Key: ${IDEMPOTENCY}" \
  -d '{"channel":"linkedin","content":"Synthetic smoke test delivery","failure_mode":"none"}' \
  | python -m json.tool
printf '\nFollow live job updates at %s\n' "${BASE}/"
