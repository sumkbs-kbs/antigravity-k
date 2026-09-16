#!/usr/bin/env bash
# NX-10 soak 예약 **통제** — arm / status / cancel / orphans / selftest
#
# 왜 이 파일이 생겼는가 (2026-09-16, 실측):
#   ① 예약을 취소했다고 기록했는데 **프로세스가 살아 있었다.** 취소는 `screen -S nx10soak -X quit`
#      였고 기록도 "시작 전 대기 중이었고 시작하지 않았다" 였지만, pgrep 로 확인하니 옛 예약 3건이
#      그대로 대기 중이었다(18:47Z·19:26Z·19:47Z 시작분 + 최초 08:20Z 분 = 총 4개). `login -pflq`
#      래퍼는 SIGHUP 을 무시하므로 화면을 닫아도 프로세스는 살아남는다.
#      → 22:00 에 4개가 동시에 깨어날 뻔했다(그중 3개는 지문 불일치로 abort 했겠지만, 같은 기록
#      파일을 동시에 append 하고 그 사실이 로그에 묻힌다).
#   ② 그래서 "취소 = 프로세스가 실제로 죽었음을 확인하는 일" 로 정의하고, 예약은 **단일**만
#      허용한다(잠금은 `mkdir` 원자성으로 잡는다). 이 도구가 그 두 가지를 강제한다.
#
# 사용:
#   bash docs/qa/2026-09-16-followup/nx10/soak_control.sh status
#   bash docs/qa/2026-09-16-followup/nx10/soak_control.sh arm            # 기본 22:00, 지문은 **지금 트리**에서 계산
#   bash docs/qa/2026-09-16-followup/nx10/soak_control.sh arm --at 23:30 --fp <지문>
#   bash docs/qa/2026-09-16-followup/nx10/soak_control.sh cancel         # 살아 있는 예약을 죽이고 **죽었는지 검증**
#   bash docs/qa/2026-09-16-followup/nx10/soak_control.sh orphans        # 잠금 주인이 아닌 살아 있는 예약 탐지
#   bash docs/qa/2026-09-16-followup/nx10/soak_control.sh selftest       # 임시 디렉터리에서 전 수명주기 검증
#
# 종료 코드: arm/cancel 은 성공 0, 거부 2(이미 예약 있음), 검증 실패 3(죽이지 못했다).
#            status 는 "건강한 단일 예약 + 지문 일치" 일 때만 0, 아니면 1(단순 조회용).
#
# 테스트를 위해 경로를 덮어쓸 수 있다(기본값은 이 저장소): NX10_REPO · NX10_OUT ·
# NX10_SCHEDULER · NX10_RUNNER · NX10_SCHED_PATTERN · NX10_CANCEL_GRACE.

set -u

REPO="${NX10_REPO:-/Users/mr.k/program/coding/ssak_comp/Ssak-Ai}"
OUT="${NX10_OUT:-$REPO/docs/qa/2026-09-16-followup/nx10}"
SCHEDULER="${NX10_SCHEDULER:-$OUT/schedule_nx10_soak.sh}"
RUNNER="${NX10_RUNNER:-$OUT/run_nx10_soak.sh}"
PATTERN="${NX10_SCHED_PATTERN:-schedule_nx10_soak.sh}"
GRACE="${NX10_CANCEL_GRACE:-15}"
SCREEN_NAME="${NX10_SCREEN_NAME:-nx10soak}"
LOCK="$OUT/.soak-arm.lock"          # 예약(대기 중) 단일 잠금 — scheduler 가 만든다
RUNLOCK="$OUT/.soak-run.lock"       # 8시간 실행 단일 잠금 — runner 가 만든다
EXIT_TXT="$OUT/soak-exit.txt"
SCHED_LOG="$OUT/soak-schedule.log"
SCHEDULE="$OUT/soak-schedule.txt"
VENV_PY="$REPO/.venv/bin/python"

_utc() { date -u +%FT%TZ; }

_py() {
  # 지문 계산은 venv 파이썬으로만 한다 — 시스템 `python` 이 3.9 일 수 있고(실측: /usr/bin/python3),
  # 그러면 `ga_gate.py` 의 3.12 문법에서 SyntaxError 가 나 지문이 UNVERIFIED 로 떨어진다.
  if [ -x "$VENV_PY" ]; then printf '%s' "$VENV_PY"; else printf '%s' python3; fi
}

_tree_fingerprint() {
  (cd "$REPO" && "$(_py)" -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))" 2>/dev/null) || echo UNVERIFIED
}

_alive() { kill -0 "$1" 2>/dev/null; }

_descendants() {
  # 부모 → 자식 BFS(손자 포함). heartbeat 파이썬처럼 **패턴에 안 걸리는** 자식을 놓치지 않으려면
  # 프로세스 목록이 아니라 프로세스 트리로 모아야 한다.
  local pid="$1" queue=("$1") child
  while [ "${#queue[@]}" -gt 0 ]; do
    pid="${queue[0]}"
    queue=("${queue[@]:1}")
    for child in $(pgrep -P "$pid" 2>/dev/null); do
      printf '%s\n' "$child"
      queue+=("$child")
    done
  done
}

_tree_pids() { printf '%s\n' "$1"; _descendants "$1"; }

_in_tree() { # $1=root $2=pid
  local p
  for p in $(_tree_pids "$1"); do
    [ "$p" = "$2" ] && return 0
  done
  return 1
}

# 줄 역순 — macOS 에는 GNU `tac` 이 없다(실측: 첫 자기시험이 `tac: command not found` 로
# 아무것도 죽이지 못하고 "취소 성공"인지 아닌지만 실패로 보고했다. 자식부터 죽이려면 역순이 필요하다).
_reverse_lines() { awk '{a[NR]=$0} END {for (i = NR; i >= 1; i--) print a[i]}'; }

_matches() {
  pgrep -f -- "$PATTERN" 2>/dev/null | grep -v -x -e "$$" -e "${PPID:-0}" || true
}

_roots() {
  # 예약 1건은 프로세스 **2개**로 보인다: `login -pflq … schedule_nx10_soak.sh` 래퍼와 그 아래
  # `bash … schedule_nx10_soak.sh`. 그래서 "살아 있는 예약 수" 는 일치 프로세스 수가 아니라
  # **부모가 일치하지 않는 최상위(루트)** 를 세야 한다 — 실측: 오늘 아침 저장소에서 예약 4건이
  # 12개 프로세스(래퍼 4 · bash 4 · heartbeat 4)로 보였다. 루트를 세면 4건이다.
  local all pid ppid
  all="$(_matches)"
  while read -r pid; do
    [ -n "$pid" ] || continue
    ppid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
    printf '%s\n' "$all" | grep -q -x "${ppid:-none}" && continue
    printf '%s\n' "$pid"
  done <<< "$all"
}

# ── 잠금 주인 정보 ──────────────────────────────────────────────────────────
_lock_field() { # $1=key
  [ -f "$LOCK/owner" ] || return 1
  sed -n "s/^$1: //p" "$LOCK/owner" | head -1
}

_lock_owner_pid() { _lock_field pid; }

_lock_state() {
  # armed | stale | none
  if [ ! -d "$LOCK" ]; then printf 'none'; return 0; fi
  local pid
  pid="$(_lock_owner_pid)" || { printf 'stale'; return 0; }
  if [ -n "$pid" ] && _alive "$pid"; then printf 'armed'; else printf 'stale'; fi
}

_print_lock() {
  local state pid
  state="$(_lock_state)"
  printf '  잠금: %s (%s)\n' "$state" "$LOCK"
  [ "$state" = "none" ] && return 0
  pid="$(_lock_owner_pid)"
  printf '    pid=%s alive=%s\n' "${pid:-?}" "$(_alive "${pid:-0}" && echo yes || echo no)"
  printf '    expected_fingerprint=%s\n' "$(_lock_field expected_fingerprint || echo '?')"
  printf '    at_local=%s target_utc=%s\n' "$(_lock_field at_local || echo '?')" "$(_lock_field target_utc || echo '?')"
  printf '    armed_at=%s\n' "$(_lock_field armed_at || echo '?')"
}

_remaining() {
  local t
  t="$(_lock_field target_utc)" || return 1
  [ -n "$t" ] || return 1
  "$(_py)" - "$t" <<'PY' || true
import datetime, sys
target = datetime.datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
now = datetime.datetime.now(datetime.timezone.utc)
print(max(0, int((target - now).total_seconds())))
PY
}

# ── status ──────────────────────────────────────────────────────────────────
cmd_status() {
  local state fp_current fp_expected live roots orphans=() pid owner healthy=1 count
  printf 'NX-10 soak 예약 상태 (%s)\n' "$(_utc)"
  printf '  repo=%s\n  pattern=%s\n' "$REPO" "$PATTERN"

  state="$(_lock_state)"
  _print_lock

  live="$(_matches)"
  roots="$(_roots)"
  count="$(printf '%s\n' "$roots" | grep -c . || true)"
  printf '  살아 있는 예약: %s건 (일치 프로세스 %s개 — 래퍼·heartbeat 포함)\n' \
    "$count" "$(printf '%s\n' "$live" | grep -c . || true)"
  while read -r pid; do
    [ -n "$pid" ] || continue
    printf '    root pid=%s ppid=%s elapsed=%s tree=%s개\n' "$pid" \
      "$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')" \
      "$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')" \
      "$(printf '%s\n' "$(_tree_pids "$pid")" | grep -c .)"
  done <<< "$(printf '%s' "$roots")"

  owner="$(_lock_owner_pid 2>/dev/null || true)"
  while read -r pid; do
    [ -n "$pid" ] || continue
    # 잠금 주인이 자기 트리 안에 있으면 그건 정상 예약이다. 트리 밖에서 도는 것이 고아다
    # (오늘 사고가 난 그 상태 — 취소했다고 기록된 예약이 살아서 대기).
    if [ -n "$owner" ] && _in_tree "$pid" "$owner"; then continue; fi
    orphans+=("$pid")
  done <<< "$(printf '%s' "$roots")"
  printf '  잠금 밖(고아) 예약: %s\n' "${#orphans[@]}"
  [ "${#orphans[@]}" -gt 0 ] && printf '    pids=%s\n' "${orphans[*]}"

  fp_expected="$(_lock_field expected_fingerprint 2>/dev/null || true)"
  fp_current="$(_tree_fingerprint)"
  printf '  지문: 기대=%s\n        현재=%s\n' "${fp_expected:-?}" "$fp_current"
  [ "${#orphans[@]}" -gt 0 ] && healthy=0
  [ "$state" = "armed" ] || healthy=0
  [ "$count" = "1" ] || healthy=0
  if [ -n "$fp_expected" ] && [ "$fp_expected" != "$fp_current" ]; then healthy=0; fi
  if [ "$state" = "armed" ]; then
    printf '  발화까지 남은 초: %s\n' "$(_remaining)"
  fi
  # 8시간 실행 잠금 — 예약과 별개다(대기는 예약 잠금, 실행은 러너가 자기 잠금을 잡는다).
  if [ -d "$RUNLOCK" ]; then
    local rpid
    rpid="$(sed -n 's/^pid: //p' "$RUNLOCK/owner" 2>/dev/null | head -1)"
    printf '  8시간 실행 잠금: pid=%s alive=%s\n' "${rpid:-?}" "$(_alive "${rpid:-0}" && echo yes || echo no)"
  else
    printf '  8시간 실행 잠금: none\n'
  fi
  if [ "$healthy" = "1" ]; then
    printf '  판정: OK — 단일 예약 · 지문 일치\n'
    return 0
  fi
  printf '  판정: ATTENTION — 단일 예약이 아니거나 지문이 다르다(위 참조)\n'
  return 1
}

cmd_orphans() {
  local owner pid found=0
  owner="$(_lock_owner_pid 2>/dev/null || true)"
  while read -r pid; do
    [ -n "$pid" ] || continue
    if [ -n "$owner" ] && _in_tree "$pid" "$owner"; then continue; fi
    printf '%s\n' "$pid"
    found=1
  done <<< "$(_roots)"
  [ "$found" = "1" ] && return 0 || return 1
}

# ── arm ─────────────────────────────────────────────────────────────────────
cmd_arm() {
  local at="22:00" fp="" state owner live roots
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --at) at="$2"; shift 2 ;;
      --fp) fp="$2"; shift 2 ;;
      *) printf '알 수 없는 인자: %s\n' "$1" >&2; return 2 ;;
    esac
  done
  [ -n "$fp" ] || fp="$(_tree_fingerprint)"
  if [ "$fp" = "UNVERIFIED" ]; then
    printf '거부: 지문을 계산하지 못했다(UNVERIFIED). 예약하면 22:00 에 스스로 중단된다.\n' >&2
    return 2
  fi

  roots="$(_roots)"
  if [ -n "$roots" ]; then
    printf '거부: 이미 살아 있는 예약이 있다(중복 예약 금지 — 오늘 사고의 원인).\n' >&2
    printf '%s\n' "$roots" | sed 's/^/  root pid=/' >&2
    printf '먼저 cancel 로 **죽었는지 확인**하고 다시 걸어라.\n' >&2
    return 2
  fi
  state="$(_lock_state)"
  case "$state" in
    armed)
      owner="$(_lock_owner_pid)"
      printf '거부: 잠금 주인(pid=%s)이 살아 있다.\n' "$owner" >&2
      return 2
      ;;
    stale)
      # 죽은 주인의 잠금은 증거로 남기고 물려받는다(지우지 않는다).
      mv "$LOCK" "$LOCK.stale-$(date -u +%Y%m%dT%H%M%SZ)"
      printf '참고: 죽은 주인의 잠금을 %s 로 밀어 두고 새로 건다.\n' "$(basename "$LOCK")".stale-* >&2
      ;;
  esac

  if [ ! -f "$SCHEDULER" ]; then
    printf '거부: 예약 스크립트가 없다: %s\n' "$SCHEDULER" >&2
    return 2
  fi

  printf '예약 발사: at=%s(로컬) fp=%s\n' "$at" "$fp"
  NX10_SOAK_AT="$at" NX10_EXPECT_FINGERPRINT="$fp" NX10_REPO="$REPO" NX10_OUT="$OUT" \
    NX10_RUNNER="$RUNNER" \
    screen -dmS "$SCREEN_NAME" bash "$SCHEDULER"
  local rc=$?
  if [ "$rc" != "0" ]; then
    printf '실패: screen 실행 rc=%s\n' "$rc" >&2
    return "$rc"
  fi
  # 예약 스크립트가 잠금을 잡았는지 확인 — 잡았다는 것은 실제로 대기 중이라는 뜻이다.
  local waited=0
  while [ "$waited" -lt 20 ]; do
    if [ "$(_lock_state)" = "armed" ]; then break; fi
    sleep 1
    waited=$((waited + 1))
  done
  if [ "$(_lock_state)" != "armed" ]; then
    printf '경고: 예약 프로세스가 20초 안에 잠금을 잡지 않았다. status 로 확인하라.\n' >&2
    cmd_status
    return 3
  fi
  printf '예약 완료.\n'
  cmd_status
}

# ── cancel ──────────────────────────────────────────────────────────────────
_die_verified() { # $1=root pid  → 0 = 죽었다(검증됨), 1 = 살아 있다/검증 불가
  local pid="$1" waited=0 p
  local pids
  pids="$(_tree_pids "$pid" | _reverse_lines)"
  if [ -z "$pids" ]; then
    # 열거조차 못 했으면 "죽었다"고 주장하지 않는다(검증 못 한 성공을 만들지 않는다).
    printf '    프로세스 트리 열거 실패 — 죽음을 검증할 수 없다\n'
    return 1
  fi
  for p in $pids; do kill -TERM "$p" 2>/dev/null; done
  while [ "$waited" -lt "$GRACE" ]; do
    local any=0
    for p in $pids; do _alive "$p" && any=1; done
    [ "$any" = "0" ] && return 0
    sleep 1
    waited=$((waited + 1))
  done
  # SIGTERM 을 무시하는 프로세스(트랩 등)는 KILL 로 승격한다 — 조용히 남겨 두지 않는다.
  printf '    TERM 무시 %s초 경과 → KILL 승격\n' "$GRACE"
  for p in $pids; do kill -KILL "$p" 2>/dev/null; done
  sleep 2
  for p in $pids; do _alive "$p" && return 1; done
  return 0
}

cmd_cancel() {
  local live pid state failed=0
  live="$(_roots)"
  if [ -z "$live" ]; then
    state="$(_lock_state)"
    printf '살아 있는 예약 프로세스가 없다(잠금 상태: %s).\n' "$state"
    if [ "$state" = "stale" ]; then
      printf '  죽은 주인의 잠금만 남아 있다 → 해제한다.\n'
      rm -rf "$LOCK"
    elif [ "$state" = "none" ]; then
      printf '  해제할 잠금도 없다.\n'
    fi
    _record_cancel "살아 있는 예약 없음(잠금 상태 $state)" "확인: pgrep 0건"
    return 0
  fi

  printf '취소 대상 %s개:\n' "$(printf '%s\n' "$live" | grep -c .)"
  while read -r pid; do
    [ -n "$pid" ] || continue
    printf '  pid=%s → 트리 종료 시도(자식 포함)\n' "$pid"
    if _die_verified "$pid"; then
      printf '    [OK] 죽음 확인\n'
    else
      printf '    [FAIL] 아직 살아 있다 — 취소가 끝나지 않았다\n'
      failed=1
    fi
  done <<< "$live"

  if [ "$failed" = "0" ]; then
    rm -rf "$LOCK"
    printf '  잠금 해제.\n'
  fi
  # 검증: 다시 훑어서 0건인지 본다(오늘 사고는 바로 이 확인이 없어서 생겼다).
  live="$(_roots)"
  if [ -n "$live" ]; then
    printf '검증 실패: 아직 %s개가 살아 있다:\n' "$(printf '%s\n' "$live" | grep -c .)"
    printf '%s\n' "$live" | sed 's/^/  pid=/'
    failed=1
  else
    printf '검증: 살아 있는 예약 0건.\n'
  fi
  _record_cancel "취소 요청(pgrep -f $PATTERN)" "$(if [ "$failed" = 0 ]; then echo '검증: 0건 — 죽음 확인'; else echo '검증 FAIL: 잔존 프로세스 있음'; fi)"
  [ "$failed" = "0" ] && return 0 || return 3
}

_record_cancel() {
  {
    echo ""
    echo "# ── 운영자 기록: 예약 취소 (soak_control.sh cancel) ──"
    echo "cancel_recorded_at: $(_utc)"
    echo "cancel_method: soak_control.sh cancel (SIGTERM → $GRACE 초 대기 → SIGKILL, 트리 단위)"
    echo "cancel_target: $1"
    echo "cancel_verification: $2"
  } >> "$EXIT_TXT"
  printf '%s cancel: %s / %s\n' "$(_utc)" "$1" "$2" >> "$SCHED_LOG"
}

# ── selftest ────────────────────────────────────────────────────────────────
# 오늘 사고를 그대로 재현해 **막히는지**를 본다. 본 저장소의 예약은 건드리지 않고,
# 임시 디렉터리에서 가짜 예약 프로세스와 진짜 예약 스크립트‌ (임시 OUT·스텁 러너)를 돌린다.
# 종료 코드: 전부 통과 0, 하나라도 실패 1.
_st_total=0
_st_passed=0

_st_ck() { # 이름 기대 실제
  _st_total=$((_st_total + 1))
  if [ "$2" = "$3" ]; then
    _st_passed=$((_st_passed + 1))
    printf '  [OK]   %s\n' "$1"
  else
    printf '  [FAIL] %s (기대=%s 실제=%s)\n' "$1" "$2" "$3"
  fi
}

_st_ck_has() { # 이름 파일 패턴
  _st_total=$((_st_total + 1))
  if grep -q -- "$3" "$2" 2>/dev/null; then
    _st_passed=$((_st_passed + 1))
    printf '  [OK]   %s\n' "$1"
  else
    printf '  [FAIL] %s — %s 에서 %s 를 찾지 못했다\n' "$1" "$2" "$3"
  fi
}

_st_ck_dead() { # 이름 패턴
  local live
  live="$(pgrep -f -- "$2" 2>/dev/null | grep -v -x -e "$$" -e "${PPID:-0}" || true)"
  _st_total=$((_st_total + 1))
  if [ -z "$live" ]; then
    _st_passed=$((_st_passed + 1))
    printf '  [OK]   %s\n' "$1"
  else
    printf '  [FAIL] %s — 잔존 pid=%s\n' "$1" "$live"
  fi
}

_fake_sched() { # $1=경로 $2=본문
  printf '#!/usr/bin/env bash\n%s\n' "$2" > "$1"
  chmod +x "$1"
}

cmd_selftest() {
  local tmp d rc at fp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/nx10-ctl-selftest-XXXXXX")"
  printf 'NX-10 soak 통제 자기시험 — 임시 루트 %s\n' "$tmp"

  # ① 살아 있는 예약이 있으면 예약(arm)이 거부된다 (오늘 사고의 핵심: 중복 예약)
  d="$tmp/t1"
  mkdir -p "$d/out"
  _fake_sched "$d/schedule_nx10_soak.sh" 'sleep 120'
  # 가짜 프로세스의 출력은 파일로 보낸다 — 파이프를 물려받으면 그 프로세스가 살아 있는 동안
  # 호출자가 EOF 를 못 받는다(첫 실행이 정확히 그렇게 타임아웃까지 매달렸다).
  bash "$d/schedule_nx10_soak.sh" > "$d/fake.log" 2>&1 & local fake1=$!
  sleep 1
  NX10_OUT="$d/out" NX10_REPO="$REPO" NX10_SCHEDULER="$d/schedule_nx10_soak.sh" \
    NX10_SCHED_PATTERN="$d/schedule_nx10_soak.sh" \
    bash "$0" arm --at 22:00 > "$d/arm.txt" 2>&1
  _st_ck "① 살아 있는 예약이 있으면 arm 거부(exit 2)" 2 "$?"
  _st_ck_has "① 거부 사유가 '중복 예약 금지'" "$d/arm.txt" "이미 살아 있는 예약"

  # ② 지문을 계산할 수 없으면 예약하지 않는다(22:00 에 스스로 멈출 예약을 걸지 않는다)
  mkdir -p "$d/empty"
  NX10_OUT="$d/out" NX10_REPO="$d/empty" NX10_SCHEDULER="$d/schedule_nx10_soak.sh" \
    NX10_SCHED_PATTERN="$d/no-such-scheduler.sh" \
    bash "$0" arm --at 22:00 > "$d/arm2.txt" 2>&1
  _st_ck "② 지문 UNVERIFIED 면 arm 거부(exit 2)" 2 "$?"
  _st_ck_has "② 거부 사유가 UNVERIFIED" "$d/arm2.txt" "UNVERIFIED"

  # ③ cancel 이 실제로 죽였는지 **검증**한다(TERM 을 따르는 프로세스)
  d="$tmp/t3"
  mkdir -p "$d/out"
  _fake_sched "$d/schedule_nx10_soak.sh" 'sleep 300'
  bash "$d/schedule_nx10_soak.sh" > "$d/fake.log" 2>&1 & sleep 1
  NX10_OUT="$d/out" NX10_SCHED_PATTERN="$d/schedule_nx10_soak.sh" NX10_CANCEL_GRACE=5 \
    bash "$0" cancel > "$d/cancel.txt" 2>&1
  _st_ck "③ cancel 성공(exit 0)" 0 "$?"
  _st_ck_dead "③ cancel 뒤 잔존 프로세스 0건" "$d/schedule_nx10_soak.sh"
  _st_ck_has "③ '죽음 확인'을 문장으로 남긴다" "$d/cancel.txt" "검증: 살아 있는 예약 0건"

  # ④ TERM 을 무시하는 프로세스는 KILL 로 승격해 끝낸다(조용히 남기지 않는다).
  #    승격 경로는 첫 자기시험이 '취소가 아무것도 죽이지 못했음' 을 드러낸 자리다(`tac` 부재).
  d="$tmp/t4"
  mkdir -p "$d/out"
  _fake_sched "$d/schedule_nx10_soak.sh" "trap '' TERM
sleep 300"
  bash "$d/schedule_nx10_soak.sh" > "$d/fake.log" 2>&1 & sleep 1
  NX10_OUT="$d/out" NX10_SCHED_PATTERN="$d/schedule_nx10_soak.sh" NX10_CANCEL_GRACE=3 \
    bash "$0" cancel > "$d/cancel.txt" 2>&1
  _st_ck "④ TERM 무시 프로세스도 cancel 성공(exit 0)" 0 "$?"
  _st_ck_has "④ KILL 승격을 기록했다" "$d/cancel.txt" "KILL 승격"
  _st_ck_dead "④ 승격 뒤 잔존 0건" "$d/schedule_nx10_soak.sh"

  # ⑤b 잠금 주인이 자기 트리 안에 있으면 고아가 아니다(예약 1건이 프로세스 2개로 보이는 것을
  #     오탐으로 올리지 않는다 — 실측: 래퍼 + bash).
  d="$tmp/t5b"
  mkdir -p "$d/out/.soak-arm.lock"
  _fake_sched "$d/schedule_nx10_soak.sh" 'sleep 60'
  bash "$d/schedule_nx10_soak.sh" > "$d/fake.log" 2>&1 & local fake5=$!
  sleep 1
  printf 'pid: %s\nexpected_fingerprint: %s\n' "$fake5" "$(_tree_fingerprint)" > "$d/out/.soak-arm.lock/owner"
  NX10_OUT="$d/out" NX10_REPO="$REPO" NX10_SCHED_PATTERN="$d/schedule_nx10_soak.sh" \
    bash "$0" status > "$d/status.txt" 2>&1
  _st_ck "⑤b 잠금 주인을 품은 예약은 건강(exit 0)" 0 "$?"
  _st_ck_has "⑤b 고아 0건" "$d/status.txt" "잠금 밖(고아) 예약: 0"
  kill -TERM "$fake5" 2>/dev/null || true
  sleep 1

  # ⑦ 러너도 동시 실행을 거부한다 — 예약이 둘로 늘어나도 soak 이 둘로 늘어나지 않게 하는 두 번째 문.
  d="$tmp/t7"
  mkdir -p "$d/out/.soak-run.lock" "$d/work"
  sleep 60 > "$d/keep.log" 2>&1 & local keep=$!
  printf 'pid: %s\nstarted_at: now\n' "$keep" > "$d/out/.soak-run.lock/owner"
  NX10_SOAK_OUT_DIR="$d/out" NX10_SOAK_WORKDIR="$d/work" \
    bash "$RUNNER" > "$d/run.log" 2>&1
  _st_ck "⑦ 이미 soak 이 돌면 러너가 거부(exit 5)" 5 "$?"
  _st_ck_has "⑦ 거부 사유를 증거에 남긴다" "$d/out/soak-exit.txt" "concurrent soak"
  _st_ck "⑦ 거부된 실행은 리포트를 만들지 않는다" "no" "$(test -f "$d/out/soak-28800.json" && echo yes || echo no)"
  kill -TERM "$keep" 2>/dev/null || true

  # ⑤ 죽은 주인의 잠금은 '예약됨'이 아니라 'stale' 로 보인다(상태를 속이지 않는다)
  d="$tmp/t5"
  mkdir -p "$d/out/.soak-arm.lock"
  printf 'pid: 4194303\nexpected_fingerprint: deadbeef\n' > "$d/out/.soak-arm.lock/owner"
  NX10_OUT="$d/out" NX10_SCHED_PATTERN="$d/no-such.sh" bash "$0" status > "$d/status.txt" 2>&1
  _st_ck "⑤ stale 잠금이면 status 가 1" 1 "$?"
  _st_ck_has "⑤ stale 로 표기" "$d/status.txt" "잠금: stale"
  _st_ck_has "⑤ ATTENTION 판정" "$d/status.txt" "ATTENTION"

  # ⑥ 전체 수명주기: 진짜 예약 스크립트(임시 OUT·스텁 러너) → 잠금 → 발화 → 잠금 해제 · 러너 1회 실행
  d="$tmp/t6"
  mkdir -p "$d/out"
  cp "$SCHEDULER" "$d/out/schedule_nx10_soak.sh"
  _fake_sched "$d/stub.sh" 'echo "stub ran $(date -u +%FT%TZ)" >> "$STUB_OUT"'
  read -r at _wait < <("$(_py)" - <<'PY'
import datetime
now = datetime.datetime.now()
target = now + datetime.timedelta(seconds=40)
target = target.replace(second=0, microsecond=0)
if (target - now).total_seconds() < 15:
    target += datetime.timedelta(minutes=1)
print(target.strftime("%H:%M"), int((target - now).total_seconds()))
PY
)
  fp="$(_tree_fingerprint)"
  if [ "$fp" = "UNVERIFIED" ] || ! command -v screen >/dev/null 2>&1; then
    printf '  [SKIP] ⑥ 수명주기 시험(fp=%s, screen=%s)\n' "$fp" "$(command -v screen || echo none)"
  else
    NX10_OUT="$d/out" NX10_REPO="$REPO" NX10_SCHEDULER="$d/out/schedule_nx10_soak.sh" \
      NX10_RUNNER="$d/stub.sh" NX10_SCHED_PATTERN="$d/out/schedule_nx10_soak.sh" \
      NX10_SCREEN_NAME=nx10selftest NX10_NO_CAFFEINATE=1 STUB_OUT="$d/runner-ran.txt" \
      bash "$0" arm --at "$at" --fp "$fp" > "$d/arm.txt" 2>&1
    _st_ck "⑥ arm 이 잠금을 잡고 성공(exit 0)" 0 "$?"
    local waited=0
    while [ "$waited" -lt 120 ] && [ ! -f "$d/runner-ran.txt" ]; do sleep 2; waited=$((waited + 2)); done
    _st_ck "⑥ 발화 시각에 스텁 러너가 실행됐다" "yes" "$(test -f "$d/runner-ran.txt" && echo yes || echo no)"
    local lockstate
    lockstate="$(NX10_OUT="$d/out" NX10_REPO="$REPO" NX10_SCHED_PATTERN="$d/no.sh" \
      bash "$0" status 2>/dev/null | sed -n 's/^  잠금: \([a-z]*\).*/\1/p' | head -1)"
    _st_ck "⑥ 시작 뒤 예약 잠금이 해제됐다" "none" "$lockstate"
    _st_ck_has "⑥ 예약 기록에 시작 지문이 남았다" "$d/out/soak-schedule.txt" "start_check_fingerprint: $fp"
    screen -S nx10selftest -X quit >/dev/null 2>&1 || true
  fi

  # 청소: 임시 디렉터리의 가짜 프로세스가 남지 않게 한다.
  pkill -f -- "$tmp" 2>/dev/null || true
  rm -rf "$tmp"
  printf '\n  SOAK_CONTROL_SELFTEST: %s/%s passed\n' "$_st_passed" "$_st_total"
  [ "$_st_passed" = "$_st_total" ]
}

# ── 진입점 ──────────────────────────────────────────────────────────────────
case "${1:-status}" in
  status) shift; cmd_status "$@" ;;
  arm) shift; cmd_arm "$@" ;;
  cancel) shift; cmd_cancel "$@" ;;
  orphans) shift; cmd_orphans "$@" ;;
  selftest) shift; cmd_selftest "$@" ;;
  -h | --help | help) sed -n '2,30p' "$0" ;;
  *)
    printf '사용: %s {status|arm|cancel|orphans|selftest} [--at HH:MM] [--fp <지문>]\n' "$0" >&2
    exit 2
    ;;
esac
