#!/usr/bin/env bash
# NX-10 잔여 필수 게이트(전용 창) 실행기.
#
# 왜 스크립트 + screen 인가: 이 창에서 게이트를 백그라운드로 띄우면 **래퍼가 죽고 exit 가 사라진다**
# (실측: ga_gate 프로세스만 죽고 pytest 가 고아로 남았고, 리포트 JSON 도 기록되지 않았다).
# NX-00 이 "래퍼 파이프와 무관한 실제 exit 보존"을 요구한 이유가 바로 이 실패 모드다.
# 그래서 게이트마다 exit 코드를 **별도 파일에** 남기고(`runner-exit.txt`), 세션은 screen 으로
# 이 도구의 프로세스 그룹 밖에 둔다.
#
# 사용:
#   screen -dmS nx10gates bash docs/qa/2026-09-16-followup/nx10/run_remaining_gates.sh
# 진행 확인:
#   screen -ls ; tail -f docs/qa/2026-09-16-followup/nx10/runner.log

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT_REL="docs/qa/2026-09-16-followup/nx10"
cd "$REPO" || exit 1
OUT="$REPO/$OUT_REL"
PY="$REPO/.venv/bin/python"
MANIFEST="scripts/commercial_ga_gates.json"

: > "$OUT/runner-exit.txt"
{
  echo "# NX-10 잔여 게이트 실행 기록"
  echo "# 시작: $(date -u +%FT%TZ)"
  echo "# HEAD: $(git rev-parse HEAD)"
  echo "# dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
} >> "$OUT/runner-exit.txt"

run_gate() {
  local id="$1"
  local report="$2"
  echo "=== $id START $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"
  "$PY" scripts/ga_gate.py --manifest "$MANIFEST" --output "$OUT/$report" --only "$id" >> "$OUT/runner.log" 2>&1
  local code=$?
  echo "$id exit:$code end:$(date -u +%FT%TZ)" >> "$OUT/runner-exit.txt"
  echo "=== $id EXIT:$code $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"
  return 0
}

run_gate python-tests gate-report-attempt012.json
run_gate python-benchmark gate-report-attempt013.json
run_gate master-e2e gate-report-attempt014.json

echo "runner done:$(date -u +%FT%TZ)" >> "$OUT/runner-exit.txt"
echo "=== runner DONE $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"
