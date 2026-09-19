#!/usr/bin/env bash
# NX-10 — **동결 트리**(지문 `157311cf…`)에서 필수 게이트를 한 창에서 재측정한다.
#
# 왜: `run_full_gates.sh`(→ `gate-report-full001.json`)는 배치 **이전** 트리에서 돌았다.
# 배치(NX-05 SSE 폐기·NX-02 quota·NX-03 tombstone)가 코드를 바꿨으므로 그 값은 이 후보의
# 것이 아니다. 마감 도구(`ga_gate_verify.py`)는 required 가 **한 리포트에 전부 있는지**를
# 보므로, 후보 지문에서 한 번 더 돌려 승인 형태에 가까운 증거를 만든다.
#
# 제외: `clean-machine-runtime` — `--ref HEAD` 를 export 하므로 **커밋 뒤에만** 후보 값이 된다
# (미커밋 작업분은 그 게이트에 들어가지 않는다). 제외 사실은 리포트의 `missing_required` 로
# 드러난다 — 숨기지 않는다.
#
# 안전: 이 실행은 코드를 바꾸지 않는다(`dashboard-build` 는 이 트리에서 결정론적임을 이미 확인 —
# BATCH_FREEZE §3). 22:00 예약 soak 의 `expected_fingerprint` 가 흔들리면 예약 실행기가 지문
# 불일치로 스스로 중단하므로, 실행 **전후 지문을 기록**해 비교할 수 있게 남긴다.
#
# 실행: screen -dmS nx10freeze bash docs/qa/2026-09-16-followup/nx10/run_freeze_gates.sh
# 확인: cat docs/qa/2026-09-16-followup/nx10/freeze-runner-exit.txt ; screen -ls

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT_REL="docs/qa/2026-09-16-followup/nx10"
cd "$REPO" || exit 1
OUT="$REPO/$OUT_REL"
PY="$REPO/.venv/bin/python"
MANIFEST="scripts/commercial_ga_gates.json"
REPORT="$OUT/gate-report-freeze002.json"
EXITLOG="$OUT/freeze-runner-exit.txt"
LOG="$OUT/freeze-runner.log"

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

{
  echo "--- freeze-gates attempt $(date -u +%FT%TZ) ---"
  echo "# HEAD: $(git rev-parse HEAD)"
  echo "# dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
  echo "# excluded: clean-machine-runtime (needs a commit: exports --ref HEAD)"
  echo "# fingerprint before: $(fp)"
} >> "$EXITLOG"

echo "=== freeze-gates START $(date -u +%FT%TZ) (22 gates) ===" | tee -a "$LOG"
"$PY" scripts/ga_gate.py --manifest "$MANIFEST" --output "$REPORT" "${ONLY_ARGS[@]}" \
  >> "$LOG" 2>&1
code=$?
echo "freeze-gates exit:$code end:$(date -u +%FT%TZ) report:$(basename "$REPORT")" >> "$EXITLOG"
echo "=== freeze-gates EXIT:$code $(date -u +%FT%TZ) ===" | tee -a "$LOG"

echo "# fingerprint after: $(fp)" >> "$EXITLOG"

{
  echo
  echo "=== ga_gate_verify (frozen report) ==="
} >> "$LOG"
uv run "$REPO/scripts/ga_gate_verify.py" --report "$REPORT" --manifest "$MANIFEST" \
  >> "$OUT/gate_verify-freeze002.txt" 2>&1
echo "ga_gate_verify exit:$?" >> "$EXITLOG"
echo "runner done:$(date -u +%FT%TZ)" >> "$EXITLOG"
