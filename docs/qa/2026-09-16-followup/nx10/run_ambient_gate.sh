#!/usr/bin/env bash
# NX-10 마지막 실행 가능 게이트(`dashboard-e2e-ambient`) 전용 러너.
#
# 왜 screen + 별도 exit 파일인가: 이 창에서 게이트를 백그라운드로 띄우면 호출 타임아웃이
# 래퍼(ga_gate)만 죽이고 exit 를 잃는다(실측: 고아 pytest + 리포트 JSON 미기록).
# 같은 실패를 반복하지 않기 위해 `run_remaining_gates.sh` 와 **같은 방식**을 쓴다.
#
# 이 게이트는 스스로 포트를 고르고 격리 서버(`/health` 폴링 후 시작)를 세우므로 상시
# 8012 인스턴스와 포트를 다투지 않는다. 서버는 스크립트가 뜨워서 끝나면 정리한다.

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT_REL="docs/qa/2026-09-16-followup/nx10"
cd "$REPO" || exit 1
OUT="$REPO/$OUT_REL"
PY="$REPO/.venv/bin/python"
MANIFEST="scripts/commercial_ga_gates.json"

{
  echo "--- ambient attempt $(date -u +%FT%TZ) ---"
  echo "# HEAD: $(git rev-parse HEAD)"
  echo "# dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
} >> "$OUT/runner-exit.txt"

echo "=== dashboard-e2e-ambient START $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"
"$PY" scripts/ga_gate.py --manifest "$MANIFEST" \
  --output "$OUT/gate-report-attempt015.json" \
  --only dashboard-e2e-ambient >> "$OUT/runner.log" 2>&1
code=$?
echo "dashboard-e2e-ambient exit:$code end:$(date -u +%FT%TZ)" >> "$OUT/runner-exit.txt"
echo "=== dashboard-e2e-ambient EXIT:$code $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"
