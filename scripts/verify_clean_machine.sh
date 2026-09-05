#!/usr/bin/env bash
# ============================================================================
# 클린머신 재현 검증 (Clean-machine Reproduction Check)
# ============================================================================
# HEAD 커밋을 임시 디렉터리에 새로 익스포트한 뒤, 로컬 .venv/캐시의 오염 없이
#   uv sync → 패키지 임포트 → CLI smoke → doctor → API E2E smoke
#   → wheel 빌드 → 신규 venv pip install → 아티팩트 검증(임포트·버전·agk)
# 까지 원클릭으로 통과하는지 검증한다.
#
# 왜 필요한가: "내 머신에서는 되는데"를 차단. uv.lock/pyproject.toml 재현뿐 아니라
# wheel이 실제 클린 환경에서 설치 가능한 배포 아티팩트인지 증명한다 (RELEASE_POLICY 선행 조건).
#
# 사용법:
#   bash scripts/verify_clean_machine.sh                 # 기본 검증
#   bash scripts/verify_clean_machine.sh --keep          # 임시 디렉터리 유지(디버그)
#   bash scripts/verify_clean_machine.sh --skip-e2e      # API E2E 생략(빠른 확인)
#   bash scripts/verify_clean_machine.sh --skip-wheel    # wheel 아티팩트 검증 생략
#   bash scripts/verify_clean_machine.sh --strict-doctor # doctor 실패를 치명적으로
#   bash scripts/verify_clean_machine.sh --ref <ref>     # 다른 커밋/브랜치 검증
#
# 종료코드: 0 = 전체 통과, 1 = 하나라도 FAIL
# ============================================================================
set -Euo pipefail

# ─── 기본값 ─────────────────────────────────────────────────────────────────
KEEP=0
SKIP_E2E=0
SKIP_WHEEL=0
STRICT_DOCTOR=0
REF="HEAD"
EXTRAS="dev rag"   # macOS(darwin)에서는 mlx 자동 추가

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep)         KEEP=1; shift ;;
    --skip-e2e)     SKIP_E2E=1; shift ;;
    --skip-wheel)   SKIP_WHEEL=1; shift ;;
    --strict-doctor) STRICT_DOCTOR=1; shift ;;
    --ref)          REF="${2:?--ref 에는 커밋/브랜치가 필요합니다}"; shift 2 ;;
    -h|--help)      sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1 (--help 참고)"; exit 2 ;;
  esac
done

# ─── 색상/출력 유틸 ────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_G=$'\033[32m'; C_R=$'\033[31m'; C_Y=$'\033[33m'; C_B=$'\033[36m'; C_0=$'\033[0m'
else
  C_G=""; C_R=""; C_Y=""; C_B=""; C_0=""
fi

RESULTS=()   # "이름|상태|소요초"

step() {
  local name="$1"; shift
  printf '%s\n' "${C_B}▶ $name${C_0}"
  local t0=$SECONDS
  if "$@" >"$LOG" 2>&1; then
    RESULTS+=("$name|PASS|$((SECONDS - t0))")
    printf '%s\n' "  ${C_G}✓ PASS${C_0} ($((SECONDS - t0))s)"
    return 0
  else
    local rc=$?
    RESULTS+=("$name|FAIL|$((SECONDS - t0))")
    printf '%s\n' "  ${C_R}✗ FAIL (exit=$rc)${C_0} — 로그: $LOG"
    sed -n '1,30p' "$LOG" | sed 's/^/  │ /'
    return 1
  fi
}
warn_step() {  # 실패해도 치명적이지 않은 단계
  local name="$1"; shift
  if step_probe "$@"; then
    RESULTS+=("$name|PASS|?"); printf '  ✓ PASS\n'
  else
    RESULTS+=("$name|WARN|?")
    printf '%s\n' "  ${C_Y}⚠ WARN (치명 아님, --strict-doctor로 강제 가능)${C_0}"
  fi
}
step_probe() { "$@" >"$LOG" 2>&1; }

trap '[[ $KEEP -eq 1 ]] && echo "임시 디렉터리 유지: $TMP" || rm -rf "$TMP"' EXIT

# ─── 사전조건 ───────────────────────────────────────────────────────────────
command -v git >/dev/null || { echo "git 필요"; exit 2; }
command -v uv  >/dev/null || { echo "uv 필요 — https://docs.astral.sh/uv/ 설치 후 실행"; exit 2; }
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/agk-clean-XXXXXX")"
LOG="$TMP/.last_step.log"

echo "=============================================================="
echo " 클린머신 재현 검증 — ref: $REF"
echo " 임시 디렉터리: $TMP"
echo "=============================================================="

# ─── [1] HEAD 익스포트 (git archive = 트래킹 파일만, 오염 없음) ─────────────
if ! git archive --format=tar "$REF" | tar -xf - -C "$TMP" 2>"$LOG"; then
  echo "git archive $REF 실패:"; cat "$LOG"; exit 2
fi
echo "익스포트 완료: $(find "$TMP" -type f | wc -l | tr -d ' ') 파일"
echo

cd "$TMP"

# macOS면 MLX extra 추가 (Apple Silicon 제품의 1차 플랫폼)
if [[ "$(uname -s)" == "Darwin" ]]; then EXTRAS="$EXTRAS mlx"; fi

EXTRA_ARGS=()
for e in $EXTRAS; do EXTRA_ARGS+=(--extra "$e"); done

FAILED=0

# ─── [2] 의존성 동기화 (잠금파일 강제) ─────────────────────────────────────
step "uv sync (extras: $EXTRAS, locked)" \
  uv sync --locked "${EXTRA_ARGS[@]}" || FAILED=1

# ─── [3] 패키지 임포트 & 버전 ───────────────────────────────────────────────
step "패키지 임포트" \
  uv run python -c 'import antigravity_k; print("antigravity-k", antigravity_k.__version__)' || FAILED=1

# ─── [4] CLI smoke: 진입점과 모델 레지스트리 ────────────────────────────────
cli_smoke() {
  uv run agk --help >/dev/null
  uv run agk model list
}
step "CLI smoke (agk --help / model list)" cli_smoke || FAILED=1

# ─── [5] doctor (기본 warn-only: Ollama 미설치 환경 고려) ──────────────────
if [[ $STRICT_DOCTOR -eq 1 ]]; then
  step "agk doctor (strict)" uv run agk doctor || FAILED=1
else
  warn_step "agk doctor (warn-only)" uv run agk doctor
fi

# ─── [6] API E2E smoke (서버 자동 기동, 에페머럴 포트) ──────────────────────
if [[ $SKIP_E2E -eq 1 ]]; then
  RESULTS+=("API E2E smoke|SKIP|-")
  echo "(--skip-e2e: API E2E 생략)"
else
  step "API E2E smoke (tests/test_e2e_smoke.py)" \
    uv run pytest tests/test_e2e_smoke.py -q --no-header || FAILED=1
fi

# ─── [7] 배포 아티팩트: 클린 트리에서 wheel 빌드 ────────────────────────────
WHL=""
WHEEL_VENV="$TMP/wheel-venv"
NEUTRAL="$TMP/wheel-smoke-cwd"
mkdir -p "$NEUTRAL"   # 소스 트리 밖 cwd — 설치된 패키지로만 임포트되게 보장
if [[ $SKIP_WHEEL -eq 1 ]]; then
  RESULTS+=("wheel 빌드|SKIP|-")
  RESULTS+=("wheel 설치·검증|SKIP|-")
  echo "(--skip-wheel: wheel 아티팩트 검증 생략)"
else
  build_wheel() { uv build --wheel -o dist; }
  if step "wheel 빌드 (클린 트리, setuptools 격리 빌드)" build_wheel; then
    WHL="$(ls -t dist/antigravity_k-*.whl 2>/dev/null | head -1)"
    echo "  → ${WHL:-<없음>} $(du -h "$WHL" 2>/dev/null | cut -f1)"
  else
    FAILED=1
  fi

  # ── [8] 신규 venv + 진짜 pip로 의존성 포함 설치 (PyPI 해석 재현) ───────────
  install_wheel() {
    uv venv --seed "$WHEEL_VENV"          # --seed: 실제 pip가 들어간 venv
    "$WHEEL_VENV/bin/pip" install --no-input "$WHL"
  }
  if [[ -n "$WHL" ]] && ! step "신규 venv pip install (코어 의존성 PyPI 해석)" install_wheel; then
    FAILED=1
  fi

  # ── [9] 아티팩트 검증: 버전 일치·package-data·콘솔 스크립트·pip check ──────
  verify_wheel() {
    local PY="$WHEEL_VENV/bin/python"
    local expected
    expected="$(sed -n 's/^__version__ *= *"\([^"]*\)".*/\1/p' "$TMP/src/antigravity_k/__init__.py" | head -1)"
    [[ -n "$expected" ]] || { echo "소스 버전 추출 실패"; return 1; }
    (
      cd "$NEUTRAL"
      EXPECTED_VERSION="$expected" "$PY" - <<'PYEOF'
import importlib.metadata as md
import os
import pathlib

import antigravity_k

exp = os.environ["EXPECTED_VERSION"]
got = antigravity_k.__version__
assert got == exp, f"소스 v{exp} != wheel __version__ v{got}"
meta = md.version("antigravity-k")
assert got == meta, f"wheel __version__ v{got} != 배포 메타데이터 v{meta}"
sp = pathlib.Path(antigravity_k.__file__).parent
missing = [f for f in ("config.yaml", "py.typed") if not (sp / f).is_file()]
assert not missing, f"package-data 누락: {missing}"
print(f"wheel 임포트 OK — v{got}, package-data(config.yaml, py.typed) 포함")
PYEOF
    ) || return 1
    [[ -x "$WHEEL_VENV/bin/agk" ]] || { echo "콘솔 스크립트 bin/agk 미생성"; return 1; }
    (cd "$NEUTRAL" && "$WHEEL_VENV/bin/agk" --help >/dev/null) || { echo "설치된 agk 실행 실패"; return 1; }
    "$WHEEL_VENV/bin/pip" check >/dev/null || { echo "pip check 실패 (의존성 불일치)"; return 1; }
  }
  if [[ -n "$WHL" && -x "$WHEEL_VENV/bin/python" ]]; then
    step "wheel 아티팩트 검증 (버전·package-data·agk·pip check)" verify_wheel || FAILED=1
  fi
fi

# ─── 요약 ───────────────────────────────────────────────────────────────────
echo
echo "=============================================================="
printf ' %-32s %-6s %s\n' "단계" "결과" "소요(s)"
echo "--------------------------------------------------------------"
for r in "${RESULTS[@]}"; do
  IFS='|' read -r name status dur <<<"$r"
  case "$status" in
    PASS) c=$C_G ;; FAIL) c=$C_R ;; SKIP|WARN) c=$C_Y ;; *) c="" ;;
  esac
  printf ' %-32s %b%-6s%b %s\n' "$name" "$c" "$status" "$C_0" "$dur"
done
echo "=============================================================="

if [[ $FAILED -eq 0 ]]; then
  printf '%s\n' "${C_G}✔ 클린머신 재현 성공 — 이 커밋은 새 환경에서 설치·실행 가능합니다${C_0}"
  exit 0
else
  printf '%s\n' "${C_R}✘ 클린머신 재현 실패 — 위 FAIL 단계의 원인을 수정하세요${C_0}"
  exit 1
fi
