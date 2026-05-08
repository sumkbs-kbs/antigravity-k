#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_FILE="${KSKILL_SECRETS_FILE:-$HOME/.config/k-skill/secrets.env}"

if [[ -f "$SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a
fi

cd "$ROOT_DIR"
exec node packages/k-skill-proxy/src/server.js
