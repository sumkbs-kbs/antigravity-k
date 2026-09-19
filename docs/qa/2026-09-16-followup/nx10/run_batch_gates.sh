#!/usr/bin/env bash
# NX-10 동결 배치(SSE 폐기 · journal quota · tombstone GC) 검증 러너.
#
# 왜 스크립트인가: 도구 호출 타임아웃이 **래퍼만** 죽이고 pytest 를 고아로 남기면 exit 를 잃는다
# (NX-00 이 겪은 실패 모드). 출력은 파일로만 흘리고(파이프 금지) 게이트별 exit 를 따로 남긴다.
#
# 실행:
#   screen -dmS nx10batch bash docs/qa/2026-09-16-followup/nx10/run_batch_gates.sh
# 진행/결과:
#   tail -f docs/qa/2026-09-16-followup/nx10/batch-gates.log
#   cat docs/qa/2026-09-16-followup/nx10/batch-runner-exit.txt

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
cd "$REPO" || exit 1
OUT="$REPO/docs/qa/2026-09-16-followup/nx10"
LOG="$OUT/batch-gates.log"
EXITS="$OUT/batch-runner-exit.txt"

FINGERPRINT=(python -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))")

{
  echo "# NX-10 동결 배치 검증 기록"
  echo "generated_at: $(date -u +%FT%TZ)"
  echo "head: $(git rev-parse HEAD)"
  echo "dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
  echo "fingerprint: $("${FINGERPRINT[@]}" 2>/dev/null || echo UNVERIFIED)"
} >> "$EXITS"

echo "=== batch gates START $(date -u +%FT%TZ) ===" >> "$LOG"

uv run --isolated --frozen --extra dev --extra rag --extra documents pytest tests/ -m "not benchmark" -v --tb=short >> "$LOG" 2>&1
python_tests=$?
{
  echo "gate: python-tests"
  echo "exit: $python_tests"
  echo "finished_at: $(date -u +%FT%TZ)"
} >> "$EXITS"

uv run --isolated --frozen --extra dev --extra rag --extra documents pytest tests/ -m benchmark -v --tb=short >> "$LOG" 2>&1
python_benchmark=$?
{
  echo "gate: python-benchmark"
  echo "exit: $python_benchmark"
  echo "finished_at: $(date -u +%FT%TZ)"
} >> "$EXITS"

{
  echo "end_fingerprint: $("${FINGERPRINT[@]}" 2>/dev/null || echo UNVERIFIED)"
  echo "end_head: $(git rev-parse HEAD)"
} >> "$EXITS"

echo "=== batch gates DONE python-tests=$python_tests python-benchmark=$python_benchmark $(date -u +%FT%TZ) ===" >> "$LOG"
exit 0
