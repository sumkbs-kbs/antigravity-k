#!/usr/bin/env bash
# NX-10 soak 예약 실행 — 오너가 지정한 시각(기본 22:00 로컬)에 **동결 트리**에서 soak 을 시작한다.
#
# 왜 예약인가: 8시간 soak 은 오너가 정한 창(오늘 22:00 ≈ 종료 06:00)에 돌려야 하고, 그 전에 코드가
# 바뀌면 안 된다. 예약 실행기는 시작 직전에 **지문을 확인**해서, 동결 이후 트리가 움직였으면 8시간을
# 태우지 않고 즉시 기록하고 멈춘다.
#
# 실행:
#   screen -dmS nx10soak bash docs/qa/2026-09-16-followup/nx10/schedule_nx10_soak.sh
# 확인:
#   cat  docs/qa/2026-09-16-followup/nx10/soak-schedule.txt   # 예약 시각·지문·pid
#   tail docs/qa/2026-09-16-followup/nx10/soak-schedule.log    # 대기 heartbeat
#   screen -ls ; tail -3 docs/qa/2026-09-16-followup/nx10/soak-exit.txt
#
# 시각/지문 바꾸기(기본값은 오너 판정 2026-09-16):
#   NX10_SOAK_AT=23:30 NX10_EXPECT_FINGERPRINT=<fp> screen -dmS nx10soak bash .../schedule_nx10_soak.sh
# 계산만 확인(실행 안 함):
#   NX10_SCHEDULE_DRY_RUN=1 bash .../schedule_nx10_soak.sh
# 노트북 잠자기를 막지 않으려면: NX10_NO_CAFFEINATE=1

set -u

REPO="/Users/mr.k/program/coding/ssak_comp/Ssak-Ai"
OUT="$REPO/docs/qa/2026-09-16-followup/nx10"
RUNNER="$OUT/run_nx10_soak.sh"
SCHEDULE="$OUT/soak-schedule.txt"
LOG="$OUT/soak-schedule.log"
AT_LOCAL="${NX10_SOAK_AT:-22:00}"
# 동결 배치(2026-09-16)의 지문. 다르면 예약 실행은 8시간을 쓰지 않고 멈춘다.
EXPECTED_FP="${NX10_EXPECT_FINGERPRINT:-157311cf106f6e1de937331d332c9dcf947ee826c28c856cfdaccead0ddad8ce}"
DRY_RUN="${NX10_SCHEDULE_DRY_RUN:-0}"

cd "$REPO" || exit 1

read -r TARGET_EPOCH TARGET_LOCAL TARGET_UTC WAIT_SECONDS < <(
  python3 - "$AT_LOCAL" <<'PY'
import datetime, sys

spec = sys.argv[1]
hour_text, _, minute_text = spec.partition(":")
tz = datetime.datetime.now().astimezone().tzinfo
now = datetime.datetime.now(tz)
target = now.replace(hour=int(hour_text), minute=int(minute_text or 0), second=0, microsecond=0)
if target <= now:
    target += datetime.timedelta(days=1)
print(
    int(target.timestamp()),
    target.isoformat(timespec="seconds"),
    target.astimezone(datetime.timezone.utc).isoformat(timespec="seconds"),
    int((target - now).total_seconds()),
)
PY
)

if [ "$DRY_RUN" = "1" ]; then
  echo "dry_run=1 at_local=$AT_LOCAL target_local=$TARGET_LOCAL target_utc=$TARGET_UTC wait_seconds=$WAIT_SECONDS epoch=$TARGET_EPOCH"
  echo "expected_fingerprint=$EXPECTED_FP"
  exit 0
fi

# 대기 구간까지 깨어 있게 하려면 NX10_CAFFEINATE_WAIT=1 (기본은 soak 실행 구간만 깨어 있게 한다).
# 뚜껑을 닫으면 caffeinate 로도 잠들기 때문에, 22:00 시작을 지키려면 기계를 열어 두어야 한다.
if [ "${NX10_CAFFEINATE_WAIT:-0}" = "1" ] && [ "${_NX10_CAFFEINATED:-0}" != "1" ] && command -v caffeinate >/dev/null 2>&1; then
  export _NX10_CAFFEINATED=1
  exec caffeinate -i bash "$0" "$@"
fi

{
  echo "# NX-10 soak 예약 기록 (오너 지정 시각 실행)"
  echo "scheduled_at: $(date -u +%FT%TZ)"
  echo "scheduled_local: $(date +%FT%T%z)"
  echo "at_local: $AT_LOCAL"
  echo "target_local: $TARGET_LOCAL"
  echo "target_utc: $TARGET_UTC"
  echo "wait_seconds: $WAIT_SECONDS"
  echo "expected_fingerprint: $EXPECTED_FP"
  echo "runner: $RUNNER"
  echo "pid: $$"
} >> "$SCHEDULE"

echo "=== schedule WAIT until $TARGET_LOCAL ($TARGET_UTC), ${WAIT_SECONDS}s $(date -u +%FT%TZ) ===" >> "$LOG"

# 대기 heartbeat — 자고 있는지/깨어 있는지 사후에 알 수 있게 남긴다.
python3 - "$TARGET_EPOCH" <<'PY' >> "$LOG"
import sys, time

target = int(sys.argv[1])
while True:
    remaining = target - int(time.time())
    if remaining <= 0:
        break
    if remaining % 900 < 60:  # 약 15분마다 한 줄(중복 방지: 60초 창)
        print(f"waiting remaining={remaining}s at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)
    time.sleep(30)
print(f"target reached at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)
PY

# 시작 직전 지문 확인: 동결 이후 코드가 움직였으면 8시간을 태우지 않는다.
CURRENT_FP="$(python -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))" 2>/dev/null || echo UNVERIFIED)"
{
  echo "start_check_at: $(date -u +%FT%TZ)"
  echo "start_check_fingerprint: $CURRENT_FP"
  echo "start_check_head: $(git rev-parse HEAD)"
  echo "start_check_dirty: $(test -n "$(git status --porcelain)" && echo true || echo false)"
} >> "$SCHEDULE"

if [ "$CURRENT_FP" != "$EXPECTED_FP" ]; then
  {
    echo "aborted: true"
    echo "aborted_reason: fingerprint drift (expected $EXPECTED_FP, got $CURRENT_FP) — 동결 트리가 아니므로"
    echo "aborted_at: $(date -u +%FT%TZ)"
  } >> "$SCHEDULE"
  echo "=== schedule ABORTED (fingerprint drift) $(date -u +%FT%TZ) ===" >> "$LOG"
  exit 2
fi

echo "=== schedule START soak $(date -u +%FT%TZ) ===" >> "$LOG"
if [ "${NX10_NO_CAFFEINATE:-0}" = "1" ] || ! command -v caffeinate >/dev/null 2>&1; then
  exec bash "$RUNNER"
fi
# 기본: 오너가 정한 밤 창에 8시간이 실제로 흐르도록 idle sleep 을 막는다(사용자 활동 아님).
exec caffeinate -i bash "$RUNNER"
