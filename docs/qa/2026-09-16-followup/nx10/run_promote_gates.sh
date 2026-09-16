#!/usr/bin/env bash
# NX-10 — **승격 뒤 트리**에서 필수 게이트를 재측정한다(지문은 실행 시점 트리에서 계산한다).
#
# 왜: 코드가 움직이면(승격·판정기 수정·창의 편집) 동결 트리의 `gate-report-freeze002.json`(21/22)은
# **옛 지문의 값**이 되어 후보로 물려받을 수 없다 — 그 지문에서 다시 측정해야 한다.
# 실행 사유는 `NX10_GATE_WHY` 로 주입한다(파일에 박아 두면 다음 attempt 에서 낡는다).
# `NX10_GATE_ATTEMPT` 로 리포트 이름을 바꾸고(재측정을 지우지 않는다),
# `NX10_INCLUDE_CLEAN_MACHINE=1` 이면 커밋 뒤 후보 값이 되는 `clean-machine-runtime` 까지 포함해 23개를 한 리포트로 돌린다.
#
# `run_freeze_gates.sh` 와 같은 게이트 집합·같은 형태다(차이는 리포트·기록 파일 이름뿐).
# 제외: `clean-machine-runtime` — `--ref HEAD` 를 export 하므로 여전히 **커밋 뒤에만** 후보 값이 된다.
#
# 실행: screen -dmS nx10promote bash docs/qa/2026-09-16-followup/nx10/run_promote_gates.sh
#       NX10_GATE_ATTEMPT=promote002 로 리포트 이름을 바꿀 수 있다(재측정을 지우지 않기 위해).
# 확인: cat docs/qa/2026-09-16-followup/nx10/promote-runner-exit.txt ; screen -ls
#
# ⚠ 이 러너는 **측정 중에 코드를 만지지 않는다**는 전제로만 의미가 있다. attempt promote001 은
#   실행 중(09:52Z)에 이 창이 `scripts/verify_docs_commands.py` 를 고쳐 시작/종료 지문이 갈렸고,
#   그래서 값은 남기되 "그 지문의 값"으로만 쓴다(attempt promote002 는 무편집 구간에서 돌린다).

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT_REL="docs/qa/2026-09-16-followup/nx10"
cd "$REPO" || exit 1
OUT="$REPO/$OUT_REL"
PY="$REPO/.venv/bin/python"
MANIFEST="scripts/commercial_ga_gates.json"
ATTEMPT="${NX10_GATE_ATTEMPT:-promote001}"
REPORT="$OUT/gate-report-$ATTEMPT.json"
EXITLOG="$OUT/promote-runner-exit.txt"
LOG="$OUT/promote-runner.log"

fp() {
  "$PY" -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))"
}

ONLY_ARGS=(
  --only python-ruff --only python-format --only python-mypy --only python-basedpyright
  --only python-tests --only python-benchmark
  --only dashboard-install --only dashboard-lint --only dashboard-typecheck
  --only dashboard-test --only dashboard-build
  --only package-build --only docker-build --only sbom-generate
  --only dependency-audit-python --only dependency-audit-dashboard --only security-bandit
  --only master-e2e --only api-e2e --only accessibility-e2e
  --only dashboard-e2e-witnesses --only dashboard-e2e-ambient
)

# 커밋 뒤에는 `clean-machine-runtime` 도 후보 값이 된다(`--ref HEAD` 를 export 하므로 커밋된 트리를 검증한다).
# NX10_INCLUDE_CLEAN_MACHINE=1 로 켜면 그 게이트까지 한 리포트에 들어가 `missing_required` 가 빈다.
if [ "${NX10_INCLUDE_CLEAN_MACHINE:-0}" = "1" ]; then
  ONLY_ARGS+=(--only clean-machine-runtime)
fi

{
  echo "--- promote-gates attempt $(date -u +%FT%TZ) ---"
  echo "# HEAD: $(git rev-parse HEAD)"
  # 사유를 파일에 박아 두면 다음 attempt 에서 낡는다(그게 지문 드리프트 오판의 원인이었다) — 호출자가 준다.
  echo "# why: ${NX10_GATE_WHY:-미기재(환경변수 NX10_GATE_WHY 로 사유를 준다)}"
  if [ "${NX10_INCLUDE_CLEAN_MACHINE:-0}" = "1" ]; then
    echo "# clean-machine-runtime: 포함(--ref HEAD = 커밋된 후보)"
  else
    echo "# excluded: clean-machine-runtime (needs a commit: exports --ref HEAD)"
  fi
  echo "# fingerprint before: $(fp)"
} >> "$EXITLOG"

echo "=== promote-gates START $(date -u +%FT%TZ) ($((${#ONLY_ARGS[@]} / 2)) gates) ===" | tee -a "$LOG"
"$PY" scripts/ga_gate.py --manifest "$MANIFEST" --output "$REPORT" "${ONLY_ARGS[@]}" \
  >> "$LOG" 2>&1
code=$?
echo "promote-gates exit:$code end:$(date -u +%FT%TZ) report:$(basename "$REPORT")" >> "$EXITLOG"
echo "=== promote-gates EXIT:$code $(date -u +%FT%TZ) ===" | tee -a "$LOG"

echo "# fingerprint after: $(fp)" >> "$EXITLOG"

{
  echo
  echo "=== ga_gate_verify (promoted report) ==="
} >> "$LOG"
uv run "$REPO/scripts/ga_gate_verify.py" --report "$REPORT" --manifest "$MANIFEST" \
  >> "$OUT/gate_verify-$ATTEMPT.txt" 2>&1
echo "ga_gate_verify exit:$?" >> "$EXITLOG"
echo "runner done:$(date -u +%FT%TZ)" >> "$EXITLOG"
