#!/usr/bin/env bash
# NX-10 — 마지막 not_run 게이트(`clean-machine-runtime`) 러너.
#
# 이 게이트를 SCOPE 는 “깨끗한 지원 호스트 필요(BLOCKED_EXTERNAL)” 로 적었다. 그런데
# `scripts/verify_clean_machine.sh` 를 읽어 보면 그것은 **호스트 청결 검사가 아니라 클린룸 재현 검사**다:
#   git archive <ref> → 임시 디렉터리 → uv sync --locked → 임포트/CLI/doctor → API E2E
#   → wheel 빌드 → 새 venv pip install → 아티팩트(버전·bin/agk·pip check) 검증
# 필요 조건은 `git` + `uv`(+ 네트워크)뿐이고, 어느 호스트에서든 돌 수 있다. 그래서 실행한다.
#
# **경계(반드시 함께 기록):** 이 스크립트는 `--ref`(기본 HEAD)를 export 한다. 즉 **커밋된 트리**를
# 검증하며, 미커밋 작업 트리(= 이 카드의 후보)는 들어가지 않는다. 그러므로 여기서 green 이 나와도
# 그것은 후보의 green 이 아니라 **HEAD(`20d529fc`)의 green**이다 — 커밋 뒤 재실행해야 후보 값이 된다.
#
# 실행: screen -dmS nx10clean bash docs/qa/2026-09-16-followup/nx10/run_clean_machine_gate.sh

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT_REL="docs/qa/2026-09-16-followup/nx10"
cd "$REPO" || exit 1
OUT="$REPO/$OUT_REL"
PY="$REPO/.venv/bin/python"
MANIFEST="scripts/commercial_ga_gates.json"

{
  echo "--- clean-machine attempt $(date -u +%FT%TZ) ---"
  echo "# HEAD: $(git rev-parse HEAD)  (이 게이트는 HEAD 를 export 한다 — dirty 후보는 미포함)"
  echo "# dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
} >> "$OUT/runner-exit.txt"

echo "=== clean-machine-runtime START $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"
"$PY" scripts/ga_gate.py --manifest "$MANIFEST" \
  --output "$OUT/gate-report-attempt016.json" \
  --only clean-machine-runtime >> "$OUT/runner.log" 2>&1
code=$?
echo "clean-machine-runtime exit:$code end:$(date -u +%FT%TZ)" >> "$OUT/runner-exit.txt"
echo "=== clean-machine-runtime EXIT:$code $(date -u +%FT%TZ) ===" | tee -a "$OUT/runner.log"
