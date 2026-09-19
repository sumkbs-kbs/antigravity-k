#!/usr/bin/env bash
set -euo pipefail

manifest_path=${1:?manifest path is required}
source_name=${2:?artifact source is required}
: "${AGK_PROVENANCE_API_URL:?AGK_PROVENANCE_API_URL is required}"
: "${AGK_PROVENANCE_TASK_ID:?AGK_PROVENANCE_TASK_ID is required}"
: "${AGK_PROVENANCE_PIN:?AGK_PROVENANCE_PIN is required}"

payload_path=$(mktemp)
trap 'rm -f "$payload_path"' EXIT
python - "$manifest_path" "$source_name" <<'PY' > "$payload_path"
import json
import pathlib
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
payload = {"manifest": manifest, "source": sys.argv[2]}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
PY

curl --fail-with-body --silent --show-error --retry 2 \
  -X POST "${AGK_PROVENANCE_API_URL%/}/api/tasks/${AGK_PROVENANCE_TASK_ID}/provenance/manifest" \
  -H "X-Access-Pin: ${AGK_PROVENANCE_PIN}" \
  -H "Content-Type: application/json" \
  --data-binary "@${payload_path}"
