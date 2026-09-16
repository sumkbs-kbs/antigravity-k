#!/usr/bin/env bash
# NX-10 — 필수 게이트를 **한 창에서 한 번에** 돌려 **리포트 1개**를 만든다.
#
# 왜 필요한가: 이 창은 호출 예산이 있어 게이트를 쪼개서 측정했다(attempt 004~015, 15개 파일).
# 그런데 마감 도구(`scripts/ga_gate_verify.py`)는 **required 게이트가 한 리포트에 전부 있는지**를
# 본다 — 쪼갠 증거는 그것만으로는 승인 형태가 아니다(실측: `missing_required: …` 22개).
# 게다가 쪼갠 green 을 “한 번에 잰 것”처럼 말하지 않으려면 실제로 한 번에 재야 한다.
#
# `clean-machine-runtime` 은 제외한다 — 깨끗한 지원 호스트가 필요하고(`BLOCKED_EXTERNAL`),
# 개발 기기에서 돌리면 “깨끗하지 않음”을 다시 확인할 뿐이다. 제외 사실은 리포트에서
# `missing_required` 로 드러나므로 숨겨지지 않는다.
#
# 실행: screen -dmS nx10full bash docs/qa/2026-09-16-followup/nx10/run_full_gates.sh
# 확인: cat docs/qa/2026-09-16-followup/nx10/runner-exit.txt ; screen -ls

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT_REL="docs/qa/2026-09-16-followup/nx10"
cd "$REPO" || exit 1
OUT="$REPO/$OUT_REL"
PY="$REPO/.venv/bin/python"
MANIFEST="scripts/commercial_ga_gates.json"
REPORT="$OUT/gate-report-full001.json"

# manifest 에 있는 23개 중 clean-machine-runtime 만 빼고 전부 실행한다.
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
  echo "--- full single-run attempt $(date -u +%FT%TZ) ---"
  echo "# HEAD: $(git rev-parse HEAD)"
  echo "# dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
  echo "# excluded: clean-machine-runtime (BLOCKED_EXTERNAL — 깨끗한 지원 호스트 필요)"
} >> "$OUT/runner-exit.txt"

echo "=== full-gates START $(date -u +%FT%TZ) (22 gates) ===" | tee -a "$OUT/runner.log"
"$PY" scripts/ga_gate.py --manifest "$MANIFEST" --output "$REPORT" "${ONLY_ARGS[@]}" \
  >> "$OUT/runner.log" 2>&1
code=$?
echo "full-gates exit:$code end:$(date -u +%FT%TZ) report:$(basename "$REPORT")" >> "$OUT/runner-exit.txt"
echo "=== full-gates EXIT:$code $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"

# 마감 도구를 같은 실행에서 돌려 **경계를 문서화**한다(통과/실패 무관하게 출력 보존).
"$PY" - <<'PY' >> "$OUT/runner.log" 2>&1
print()
print("=== ga_gate_verify (full report) ===")
PY
uv run "$REPO/scripts/ga_gate_verify.py" --report "$REPORT" --manifest "$MANIFEST" \
  >> "$OUT/gate_verify-full001.txt" 2>&1
echo "ga_gate_verify exit:$?" >> "$OUT/runner-exit.txt"
