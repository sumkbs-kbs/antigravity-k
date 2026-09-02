#!/usr/bin/env bash
set -euo pipefail

source_name=${1:?artifact source is required}
idempotency_key=${2:?idempotency key is required}
: "${AGK_PROVENANCE_API_URL:?AGK_PROVENANCE_API_URL is required}"
: "${AGK_PROVENANCE_PIN:?AGK_PROVENANCE_PIN is required}"

response=$(curl --fail-with-body --silent --show-error --retry 2 \
  -X POST "${AGK_PROVENANCE_API_URL%/}/api/tasks/provenance/register" \
  -H "X-Access-Pin: ${AGK_PROVENANCE_PIN}" \
  -H "Content-Type: application/json" \
  --data "{\"source\":\"${source_name}\",\"idempotency_key\":\"${idempotency_key}\"}")

python - "$response" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
task_id = payload.get("task_id")
if payload.get("status") != "registered" or not isinstance(task_id, str) or not task_id:
    raise SystemExit("provenance task registration returned an invalid response")
print(task_id)
PY
