#!/usr/bin/env bash
# NX-10 — SC-1~6 8시간(28,800s) soak 러너. **아직 실행하지 않았다** (8시간 + 기기 점유 결정 필요).
#
# NX-00 이 남긴 세 가지 실패 모드를 코드로 막는다:
#   ① 실행 명령이 사라진다 → 이 파일이 원문 명령을 소유하고, 러너가 자기 명령을 로그에 남긴다.
#   ② 시작/종료 코드 후보가 귀속되지 않는다(`run_sha_binding: UNVERIFIED`) → 시작·종료 시점의
#      HEAD SHA 와 코드 지문을 **따로** 기록해 리포트가 어느 트리의 것인지 사후에 확정할 수 있게 한다.
#   ③ 래퍼 exit 를 잃는다(`finished exit:141` + stdout 절단) → 출력은 파일로만 흘리고(파이프 금지),
#      종료 코드를 별도 파일에 남긴다.
#
# 실행:
#   screen -dmS nx10soak bash docs/qa/2026-09-16-followup/nx10/run_nx10_soak.sh
# 진행 확인:
#   screen -ls ; tail -f docs/qa/2026-09-16-followup/nx10/soak-run.log
#   tail -3 docs/qa/2026-09-16-followup/nx10/soak-exit.txt
#
# 끝난 뒤:
#   uv run scripts/ga_gate_verify.py --report docs/qa/2026-09-16-followup/nx10/gate-report-full001.json \
#     --manifest scripts/commercial_ga_gates.json --expected-sha <FULL_CANDIDATE_SHA> \
#     --soak-artifact docs/qa/2026-09-16-followup/nx10/soak-28800.json --min-soak-seconds 28800

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT_REL="docs/qa/2026-09-16-followup/nx10"
cd "$REPO" || exit 1
OUT="$REPO/$OUT_REL"
PY="$REPO/.venv/bin/python"
SOAK_SECONDS="${SOAK_SECONDS:-28800}"
REPORT="$OUT/soak-${SOAK_SECONDS}.json"
# 작업 디렉토리는 **저장소 밖**에 둔다 — 8시간 soak 은 수백 MB~수 GB 를 쓰므로 공유 체크아웃을
# 더럽히면 다른 레인의 `git status`/프라이어블 worktree 판정에 끼어든다. (60초 리허설은
# 저장소 안에 만들었던 적이 있다 — 그 디렉토리들은 증거로 남기고, 정식 실행부터는 /tmp 를 쓴다.)
WORKDIR="${NX10_SOAK_WORKDIR:-/tmp/nx10-soak-work-$(date -u +%Y%m%dT%H%M%SZ)}"
FINGERPRINT_CMD=(python -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))")

{
  echo "# NX-10 SC-1~6 soak 러너 기록"
  echo "generated_at: $(date -u +%FT%TZ)"
  echo "soak_seconds: $SOAK_SECONDS"
  echo "report: $REPORT"
  echo "workdir: $WORKDIR"
  echo "command: PYTHONPATH=src $PY scripts/val02_staging.py --output $REPORT --scenarios SC-1,SC-2,SC-3,SC-4,SC-5,SC-6 --soak-seconds $SOAK_SECONDS --workdir $WORKDIR"
} >> "$OUT/soak-exit.txt"

# ② 시작 시점의 후보 귀속 (종료 시점에도 다시 찍는다)
{
  echo "start_time: $(date -u +%FT%TZ)"
  echo "start_head: $(git rev-parse HEAD)"
  echo "start_dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
  echo "start_fingerprint: $("${FINGERPRINT_CMD[@]}" 2>/dev/null || echo UNVERIFIED)"
} >> "$OUT/soak-exit.txt"

echo "=== soak START $(date -u +%FT%TZ) (${SOAK_SECONDS}s) ===" | tee -a "$OUT/soak-run.log"

# ③ 파이프 없이 파일로만 — stdout 절단/SIGPIPE 를 만들지 않는다.
PYTHONPATH="$REPO/src" "$PY" scripts/val02_staging.py \
  --output "$REPORT" \
  --scenarios SC-1,SC-2,SC-3,SC-4,SC-5,SC-6 \
  --soak-seconds "$SOAK_SECONDS" \
  --workdir "$WORKDIR" >> "$OUT/soak-run.log" 2>&1
code=$?

{
  echo "exit: $code"
  echo "end_time: $(date -u +%FT%TZ)"
  echo "end_head: $(git rev-parse HEAD)"
  echo "end_dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
  echo "end_fingerprint: $("${FINGERPRINT_CMD[@]}" 2>/dev/null || echo UNVERIFIED)"
} >> "$OUT/soak-exit.txt"

echo "=== soak EXIT:$code $(date -u +%FT%TZ) ===" | tee -a "$OUT/soak-run.log"
exit "$code"
