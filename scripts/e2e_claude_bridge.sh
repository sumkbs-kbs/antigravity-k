#!/usr/bin/env bash
#
# Claude Code ↔ Ssak-Ai 브리지 E2E (Phase 37)
# =========================================================
# 실제 Claude Code CLI를 agk serve에 연결해 로컬 모델의 툴 호출 왕복을 검증한다.
# CI나 다른 에이전트가 이 스크립트 하나로 재현할 수 있다.
#
# 사용:
#   ./scripts/e2e_claude_bridge.sh                          # 기본 모델/포트
#   ./scripts/e2e_claude_bridge.sh --model qwen3.8:latest --port 8479
#   CLAUDE_BIN=/path/to/claude ./scripts/e2e_claude_bridge.sh
#   ./scripts/e2e_claude_bridge.sh --install                # claude 미설치 시 npm 설치 시도
#   ./scripts/e2e_claude_bridge.sh --keep                    # 실패해도 워크스페이스/로그 보존
#
# 전제: 로컬 모델이 실행 가능(ollama 등), uv 사용 가능, (--install 시) npm/네트워크.
# 서버가 실행 중이면 그대로 사용하고, 없으면 이 스크립트가 직접 띄운다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${MODEL:-qwen3.8:latest}"
PORT="${PORT:-8479}"
# 일부 셸/CI가 PORT=0을 export — 0이면 기본값으로 (uvicorn 포트 0은 사용 불가)
[[ "$PORT" =~ ^[0-9]+$ && "$PORT" -gt 0 ]] || PORT=8479
KEEP=0
INSTALL=0
PRINT_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    --install) INSTALL=1; shift ;;
    --print-only) PRINT_ONLY=1; shift ;;
    -h|--help) grep '^#' "$0" | head -20; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

log()  { printf '\n\033[1;34m[bridge-e2e]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[bridge-e2e] FAIL\033[0m %s\n' "$*" >&2; exit 1; }
pass() { printf '\033[1;32m[bridge-e2e] PASS\033[0m %s\n' "$*"; }

# ── 0. (--print-only) 서버/CLI 없이 권장 env 블록만 출력 ────────────
if [[ "$PRINT_ONLY" -eq 1 ]]; then
  (cd "$ROOT" && uv run agk start claude --model "$MODEL" --api-base "http://127.0.0.1:$PORT" 2>/dev/null || true)
  exit 0
fi

# ── 1. Claude Code CLI 해석 ─────────────────────────────────────────
CLAUDE_BIN="${CLAUDE_BIN:-}"
if [[ -z "$CLAUDE_BIN" ]]; then
  if command -v claude >/dev/null 2>&1; then
    CLAUDE_BIN="$(command -v claude)"
  elif [[ -x "$ROOT/.tmp/claude_cli/node_modules/@anthropic-ai/claude-code/bin/claude.exe" ]]; then
    CLAUDE_BIN="$ROOT/.tmp/claude_cli/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
  fi
fi
if [[ -z "$CLAUDE_BIN" ]]; then
  if [[ "$INSTALL" -eq 1 ]]; then
    log "claude 미설치 — .tmp/claude_cli에 설치 시도"
    mkdir -p "$ROOT/.tmp/claude_cli"
    ( cd "$ROOT/.tmp/claude_cli" && npm install --no-audit --no-fund "@anthropic-ai/claude-code@^2.1.260" >/dev/null )
    CLAUDE_BIN="$ROOT/.tmp/claude_cli/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
  else
    fail "Claude Code CLI를 찾지 못했습니다. CLAUDE_BIN을 지정하거나 --install을 쓰세요."
  fi
fi
[[ -x "$CLAUDE_BIN" ]] || fail "claude 바이너리 실행 불가: $CLAUDE_BIN"
log "Claude Code: $("$CLAUDE_BIN" --version 2>/dev/null | head -1)"

# ── 2. 포트/워크스페이스 준비 ───────────────────────────────────────
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  log "포트 $PORT 사용 중 — 이미 서버가 실행 중이라 가정"
  SERVER_PID=0
else
  SERVER_PID=0
fi

WS="$(mktemp -d "${TMPDIR:-/tmp}/agk_claude_e2e.XXXXXX")"
SECRET="SECRET-CODE-$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')"
printf '%s\n' "$SECRET" > "$WS/note.txt"
printf '# E2E demo\n' > "$WS/README.md"
LOG="$WS/server.log"

cleanup() {
  if [[ "$KEEP" -eq 0 ]]; then
    rm -rf "$WS"
  else
    log "워크스페이스 보존: $WS"
  fi
}
trap cleanup EXIT

# ── 3. 서버 기동 + 헬스 대기 (이미 실행 중이면 생략) ────────────────
start_server() {
  ( cd "$ROOT" && uv run python -m uvicorn antigravity_k.api.server:app \
      --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 ) &
  SERVER_PID=$!
  for _ in $(seq 1 45); do
    if curl -sf "http://127.0.0.1:$PORT/v1/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "--- server log ---" >&2; tail -20 "$LOG" >&2 || true
  return 1
}

if [[ "$SERVER_PID" -eq 0 ]]; then
  log "agk serve 기동 (127.0.0.1:$PORT)"
  start_server || fail "서버가 45초 내 기동되지 않았습니다."
  trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
fi
HEALTH="$(curl -sf "http://127.0.0.1:$PORT/v1/health" | head -c 60 || true)"
pass "서버 응답: $HEALTH"

# ── 4. 모델 존재/실행 확인 ─────────────────────────────────────────
if ! curl -sf "http://127.0.0.1:$PORT/api/models/local" | grep -Fq "\"$MODEL\""; then
  fail "모델 '$MODEL'이 로컬 목록에 없습니다. (ollama pull 필요?)"
fi
pass "모델 확인: $MODEL"

# ── 5. 권장 env 블록 (agk start와 동일한 컨텍스트 윈도) ────────────
ENV_BLOCK="$(cd "$ROOT" && uv run agk start claude --model "$MODEL" --api-base "http://127.0.0.1:$PORT" 2>/dev/null || true)"
CTX="$(printf '%s' "$ENV_BLOCK" | grep -o 'CLAUDE_CODE_MAX_CONTEXT_TOKENS=[0-9]*' | head -1 | cut -d= -f2 || true)"
CTX="${CTX:-200000}"
log "컨텍스트 윈도: $CTX"

# ── 6. Claude Code CLI 실행 (stdin 파이프 — 위치인자 파싱 실패 회피) ──
PROMPT="Read the file note.txt in the current directory and tell me the exact secret code it contains."
RESULT_JSON="$WS/result.json"
(
  cd "$WS"
  printf '%s\n' "$PROMPT" | \
    ANTHROPIC_BASE_URL="http://127.0.0.1:$PORT" \
    ANTHROPIC_API_KEY="ssak-ai-local" \
    ANTHROPIC_MODEL="$MODEL" \
    CLAUDE_CODE_MAX_CONTEXT_TOKENS="$CTX" \
    ANTHROPIC_SMALL_FAST_MODEL="$MODEL" \
    ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL" \
    ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL" \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_AUTOUPDATER=1 \
    "$CLAUDE_BIN" --print --output-format json --max-turns 6 --allowedTools "Read" \
    > "$RESULT_JSON" 2> "$WS/claude.err"
)
[[ -s "$RESULT_JSON" ]] || { echo "--- claude stderr ---" >&2; tail -20 "$WS/claude.err" >&2; fail "claude 출력이 비어 있습니다."; }

# ── 7. 단언: 비밀코드 + 툴 왕복(turns>=2) ──────────────────────────
python3 - "$RESULT_JSON" "$SECRET" <<'PY'
import json, sys
path, secret = sys.argv[1], sys.argv[2]
d = json.load(open(path))
result = d.get("result", "")
turns = d.get("num_turns", 0) or 0
stop = d.get("stop_reason", "")
turns_ok = turns >= 2
secret_ok = secret in result
print(f"  turns={turns} stop={stop}")
print(f"  result={result[:120]!r}")
if not (turns_ok and secret_ok):
    print(f"  [assert] secret_ok={secret_ok} turns_ok={turns_ok}")
    sys.exit(1)
PY
[[ $? -eq 0 ]] || fail "단언 실패: 비밀코드 또는 툴 왕복 미확인"

pass "비밀코드 툴 왕복 검증 완료 — $SECRET"
pass "모두 통과"
