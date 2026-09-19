#!/usr/bin/env bash
# Bundle Host smoke (does not kill EX soak / does not bind :8000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_ROOT="${SSAK_DMG_APP_ROOT:-$ROOT/build/mac/Ssak-Ai.app/Contents/Resources/app}"
# Prefer in-bundle interpreter when present (SSAK_BUNDLE_PYTHON=1 builds); else .venv / override.
_DEFAULT_BUNDLE_PY="$ROOT/build/mac/Ssak-Ai.app/Contents/Resources/python/bin/python3"
if [[ -z "${SSAK_DMG_PYTHON:-}" ]]; then
  if [[ -x "$_DEFAULT_BUNDLE_PY" ]]; then
    PY="$_DEFAULT_BUNDLE_PY"
  else
    PY="$ROOT/.venv/bin/python3"
  fi
else
  PY="$SSAK_DMG_PYTHON"
fi
PORT="${SSAK_DMG_SMOKE_PORT:-18080}"
LOG="${SSAK_DMG_SMOKE_LOG:-/tmp/ssak-dmg-logs/bundle-smoke-$PORT.log}"
DIR="$(mktemp -d /tmp/ssak-bundle-smoke.XXXXXX)"
mkdir -p "$(dirname "$LOG")"

cleanup() {
  if [[ -n "${SPID:-}" ]]; then kill "$SPID" 2>/dev/null || true; fi
  pkill -f "antigravity_k.cli serve --host 127.0.0.1 --port ${PORT}" 2>/dev/null || true
  rm -rf "$DIR"
}
trap cleanup EXIT

[[ -x "$PY" ]] || { echo "ERROR: python not executable: $PY" >&2; exit 1; }
[[ -d "$APP_ROOT/src" ]] || { echo "ERROR: missing app bundle at $APP_ROOT (run make dmg first)" >&2; exit 1; }
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port $PORT busy" >&2
  exit 1
fi

export PYTHONPATH="$APP_ROOT/src:$APP_ROOT/site-packages${PYTHONPATH:+:$PYTHONPATH}"
cd "$DIR"
nohup "$PY" -m antigravity_k.cli serve --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 &
SPID=$!

READY=0
for _ in $(seq 1 60); do
  code="$(curl -sS -m 1 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/api/auth/status" 2>/dev/null || echo 000)"
  if [[ "$code" == "200" ]]; then READY=1; break; fi
  if ! kill -0 "$SPID" 2>/dev/null; then echo "ERROR: server exited early; see $LOG" >&2; exit 1; fi
  sleep 0.5
done
[[ "$READY" == "1" ]] || { echo "ERROR: health timeout; see $LOG" >&2; exit 1; }

spa="$(curl -sS -m 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/")"
[[ "$spa" == "200" ]] || { echo "ERROR: SPA root HTTP $spa" >&2; exit 1; }

echo "PASS bundle smoke port=$PORT auth=200 spa=200 log=$LOG"
