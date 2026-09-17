#!/usr/bin/env bash
# 회수 뒤 순서 한 줄 — **판정 → 승격 → 게이트 재측정**. 순서를 사람이 기억하지 않아도 되게 묶는다.
#
# 왜 이 순서인가(오늘 하루가 가르친 것):
#   ① 승격은 `scripts/`·`tests/` 를 건드려 **지문을 옮긴다** → 도는 soak 의 종료 지문 일치가 깨진다.
#      그래서 승격은 **회수(실행 종료 + 판정) 뒤**에만 한다.
#   ② 승격 뒤에는 필수 게이트를 **새 지문에서** 재측정해야 한다(옛 리포트는 옛 지문의 값이다).
#   ③ 그 뒤에야 soak 을 재장전할 수 있다(`soak_control.sh preflight` → `run`).
#
# 사용:
#   bash …/promote2/post_harvest_sequence.sh --plan     # 무엇을 할지만 보여 준다(부작용 0)
#   bash …/promote2/post_harvest_sequence.sh --wait     # 종료를 기다렸다가 위 3단계를 실행
#   bash …/promote2/post_harvest_sequence.sh            # 지금 상태로 실행(도는 soak 이 있으면 거절)
#
# 옵션: `--skip-gates`(승격만 하고 게이트는 따로), `NX10_WAIT_SECONDS`(기본 43200),
#       `NX10_GATE_ATTEMPT`(기본 promote2b), `NX10_INCLUDE_CLEAN_MACHINE`(기본 1 = 23개),
#       `NX10_JUDGE_SETTLE`(기본 900 — 떠 있는 감시의 판정을 기다리는 상한),
#       `NX10_PROMOTE_ON_FAIL=1`(판정 FAIL 이어도 강행 — 기본은 멈춘다).
#
# 무인 실행(오너 요청 “동결 해제하면 승격하고 승격 위치에서 통과 확인”):
#   screen -dmS nx10promote caffeinate -i bash -c 'cd <repo> && bash …/post_harvest_sequence.sh --wait \
#     >> …/post-harvest-sequence.log 2>&1'
#   → 실행 종료를 기다렸다가 판정 → (PASS면) 승격 → 새 지문에서 필수 게이트(약 16분, 다른 화면).
#   → 도중에 취소: `screen -S nx10promote -X quit`(승격 전이면 트리 무변경).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NX10="$(cd "$HERE/.." && pwd)"
REPO="${NX10_REPO:-/Users/mr.k/program/coding/ssak_comp/Ssak-Ai}"
PY="$REPO/.venv/bin/python"
PLAN=0
WAIT=0
SKIP_GATES=0
for arg in "$@"; do
  case "$arg" in
    --plan) PLAN=1 ;;
    --wait) WAIT=1 ;;
    --skip-gates) SKIP_GATES=1 ;;
    *) echo "알 수 없는 옵션: $arg"; exit 1 ;;
  esac
done

step() { printf '\n=== %s ===\n' "$1"; }
ok() { printf '  [OK  ] %s\n' "$1"; }
bad() {
  printf '  [FAIL] %s\n' "$1"
  exit 1
}

if [[ "$PLAN" -eq 1 ]]; then
  step "계획(부작용 0)"
  cat <<'TXT'
  1) 실행 종료를 기다린다(도는 soak 이 있으면 --wait 필요) → soak_control.sh harvest 로 판정
     → 판정 원문은 soak-harvest-<UTC>.txt, exit code 가 PASS/FAIL 을 말한다
  2) promote2/apply_promotion2.sh — scripts/·tests/ 로 이동(실패 시 자동 롤백)
     → 이 시점에 **지문이 이동한다**(도는 soak 이 없어야 하는 이유)
  3) NX10_GATE_ATTEMPT=<이름> NX10_INCLUDE_CLEAN_MACHINE=1 run_promote_gates.sh
     → 승격 뒤 지문에서 필수 23개 재측정(약 16분, screen 권장)
  4) 기록: GATE_LEDGER · handoff · PROMOTION_PLAN §1c · docs/19·20 → 그 뒤 soak 재장전
TXT
  echo "  판정이 FAIL 이어도 승격은 진행한다 — 승격은 soak 판정과 독립이다(문서 정정은 별개 단계)."
  exit 0
fi

step "1. 실행 종료 확인"
if pgrep -f val02_staging.py >/dev/null 2>&1; then
  if [[ "$WAIT" -eq 1 ]]; then
    limit="${NX10_WAIT_SECONDS:-43200}"
    printf '  도는 soak 을 기다린다(최대 %ss) — 판정은 기다리지 않는다(끝나야 가능하다)\n' "$limit"
    waited=0
    while pgrep -f val02_staging.py >/dev/null 2>&1; do
      if [[ "$waited" -ge "$limit" ]]; then
        bad "기다리다 시간 초과(${limit}s) — 사람이 확인해야 한다"
      fi
      sleep 60
      waited=$((waited + 60))
      [[ $((waited % 600)) -eq 0 ]] && printf '  … 대기 %ss\n' "$waited"
    done
    ok "실행이 끝났다(대기 ${waited}s)"
  else
    bad "8시간 soak 이 아직 돌고 있다 — 회수 뒤에 실행하거나 --wait 을 쓴다(지문 보호)"
  fi
else
  ok "도는 soak 없음"
fi

step "2. 회수 판정"
# 이미 떠 있는 회수 감시(`screen nx10harvest`)가 먼저 판정을 쓸 수 있다. 둘이 동시에 판정기를
# 돌리면 자물쇠 경합으로 이 순서가 통째로 끊길 수 있으므로, **그 감시가 남긴 원문을 먼저 기다린다**.
# 기다리는 조건은 “방금 쓰였는가”(mtime ≥ 지금) — 오래된 판정 원문을 오늘 것으로 착각하지 않기 위해서다.
mtime_of() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
judge_started="$(date +%s)"
settle="${NX10_JUDGE_SETTLE:-900}"
latest=""
waited=0
while [[ "$waited" -lt "$settle" ]]; do
  latest="$(ls -t "$NX10"/soak-harvest-*.txt 2>/dev/null | head -1 || true)"
  if [[ -n "$latest" && "$(mtime_of "$latest")" -ge "$judge_started" ]]; then
    break
  fi
  latest=""
  sleep 15
  waited=$((waited + 15))
done
judge_rc=0
if [[ -n "$latest" ]]; then
  ok "떠 있던 감시가 판정을 남겼다(대기 ${waited}s): $(basename "$latest")"
else
  echo "  판정 원문이 아직 없다 — harvest 를 돌린다(끝난 실행이면 곧 돌아온다)"
  # 도구의 위치는 승격을 따른다(3차 배치가 `docs/` 사본을 `scripts/` 로 옮겼다).
  CONTROL="$REPO/scripts/soak_control.sh"
  [ -f "$CONTROL" ] || CONTROL="$NX10/soak_control.sh"
  bash "$CONTROL" harvest --timeout 900 >/tmp/nx10-post-harvest-judge.log 2>&1 || judge_rc=$?
  latest="$(ls -t "$NX10"/soak-harvest-*.txt 2>/dev/null | head -1 || true)"
  if [[ "$judge_rc" -eq 0 ]]; then
    ok "harvest exit 0(판정 PASS)"
  else
    echo "  [WARN] harvest exit $judge_rc — 판정 원문을 읽을 것"
  fi
fi
[[ -n "$latest" ]] && ok "판정 원문: $(basename "$latest")" || echo "  [WARN] 판정 원문을 찾지 못했다 — harvest 로그를 직접 확인할 것"
# 판정이 PASS 가 아니면 **사람 없이 트리를 옮기지 않는다**: FAIL 이면 후보에 손을 대야 하므로
# (오늘 SC-6 로 그랬다) 승격 직후 지문이 또 움직인다 — 강행하려면 NX10_PROMOTE_ON_FAIL=1.
if [[ "$judge_rc" -ne 0 && "${NX10_PROMOTE_ON_FAIL:-0}" != "1" ]]; then
  echo
  bad "판정이 PASS 가 아니다(exit $judge_rc) — 승격을 멈춘다(트리 무변경). 읽을 것: ${latest:-판정 원문 없음}"
fi

step "3. 승격(2차 배치)"
bash "$HERE/apply_promotion2.sh" || bad "승격 실패 — 이동은 자동 롤백됐다(기록 확인)"

if [[ "$SKIP_GATES" -eq 1 ]]; then
  echo "  --skip-gates: 게이트 재측정은 따로 실행한다"
  exit 0
fi

step "4. 승격 뒤 필수 게이트 재측정(화면 세션)"
attempt="${NX10_GATE_ATTEMPT:-promote2b}"
screen -dmS "nx10${attempt}" caffeinate -i bash -c \
  "cd '$REPO' && NX10_GATE_ATTEMPT='$attempt' NX10_INCLUDE_CLEAN_MACHINE='${NX10_INCLUDE_CLEAN_MACHINE:-1}' \
   NX10_GATE_WHY='2차 승격 배치(리허설·경보 도구 승격) 뒤 새 지문 재측정' \
   bash '$NX10/run_promote_gates.sh' >> '$NX10/${attempt}-runner.log' 2>&1"
ok "게이트를 screen nx10${attempt} 에서 돌린다(약 16분)"
echo "  확인: tail -5 '$NX10/${attempt}-runner.log' ; cat '$NX10/promote-runner-exit.txt'"
echo
echo "다음(게이트 뒤): 리포트·판정을 대장에 반영하고 soak 을 재장전한다 —"
echo "  bash '$REPO/scripts/soak_control.sh' preflight && bash '$REPO/scripts/soak_control.sh' run"
