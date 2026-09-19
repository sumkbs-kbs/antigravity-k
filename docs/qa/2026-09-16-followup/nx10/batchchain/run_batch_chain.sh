#!/usr/bin/env bash
# 회수 뒤 **배치 체인** — `SC6 → PERF → FLUSH → FLUSH2` 를 순서대로 적용하고, 배치마다 커밋한 뒤
# 그 지문에서 필수 23개를 재측정하고, 마지막에 새 8시간 soak 을 재장전한다(선택).
#
# 왜 이 체인이 필요한가 — **FLUSH 는 PERF 없이는 적용되지 않는다**:
#   `fsync/apply_flush_batch.sh` 의 합성 순서 가드(exit 6)는 `scripts/val02_staging.py` 에 PERF 사다리
#   표식(`NX10_DEEP_PROFILE`)이 있어야 통과한다(그 배치가 지문을 움직이므로 마지막이어야 한다는 규칙을
#   코드로 고정한 것이다). 그래서 “soak 끝나면 FLUSH·FLUSH2” 만 걸면 실제로는 아무것도 적용되지 않고
#   exit 6 으로 멈춘다 — 실측(2026-09-17): PERF 표식 0건 · FLUSH/FLUSH2 dry-run 이 exit 9(동결)→ 이후 exit 6.
#   순서를 지키려면 SC6·PERF 가 먼저다(둘은 같은 파일을 차례로 바꾸므로 PERF 의 사전 이미지가 SC6 적용 뒤다).
#
# 왜 배치마다 커밋하는가: 게이트의 `clean-machine-runtime` 은 `--ref HEAD` 를 export 하므로 **커밋된 트리만
#   후보 값**이 된다(기존 3차 배치 체인과 같은 규칙). 그래서 적용 → 명시 경로만 스테이징 → 커밋 → 그 지문에서 게이트.
#
# 이 체인이 **멈추는** 조건(모두 기록을 남기고 쓰기 0건):
#   · 앞 단계(3차 배치 체인)가 끝나지 않았거나 실패 흔적이 있다 · 회수 판정이 PASS 가 아니거나 지문이 갈렸다
#   · 코드 경로(src/tests/scripts/dashboard)에 소유 불명 변경이 있다 · 어떤 배치든 가드 걸려 실패했다
#   · 게이트 측정 **전** 커밋이 실패했다
# 이 체인이 **멈추지 않는** 조건(측정 결과는 기록만 한다):
#   · 게이트가 빨간 것 — 이 저장소에는 이미 기존 실패가 있다(예: `python-tests` 의 CR-14 3건 · NX-07 2건).
#     “게이트 통과 시에만 진행”은 그 실패가 해소될 때까지 파이프라인을 영구히 막는다. 그래서 요약을 남기고
#     계속하되, **지문이 측정 중에 움직였으면** 그 사실을 WARN 으로 남긴다(그 리포트는 후보 값이 아니다).
#
# 사용:
#   bash …/batchchain/run_batch_chain.sh --plan     # 무엇을 할지만 보여 준다(부작용 0)
#   bash …/batchchain/run_batch_chain.sh --wait     # 앞 단계(soak·3차 체인)를 기다렸다가 적용·커밋·게이트
#   bash …/batchchain/run_batch_chain.sh --wait --rearm   # 게이트 뒤 새 8시간 soak 재장전까지
#
# 환경변수:
#   `NX10_WAIT_SECONDS`(7200)      앞 단계 대기 상한
#   `NX10_GATE_LABEL`(batch)       게이트 리포트 이름 접두사 → `gate-report-<label>-sc6.json` …
#   `NX10_SOAK_PROC_PATTERN`(val02_staging.py) · `NX10_CHAIN_PROC_PATTERN`(post_harvest_sequence3.sh)
#   `NX10_GATES_PROC_PATTERN`(run_promote_gates.sh) · `NX10_WATCH_PROC_PATTERN`(soak_watch_loop.py)
#   `NX10_HARVEST_PROC_PATTERN`(soak_control.sh harvest) · `NX10_WATCH_SCREEN`(nx10watch)
#     — 리허설은 이 이름들을 바꿔 **진짜 soak·감시·체인을 건드리지 않는다**(통제 도구의 규칙과 같다).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NX10="$(cd "$HERE/.." && pwd)"
REPO="${NX10_REPO:-$(cd "$NX10/../../../.." && pwd)}"
PY="$REPO/.venv/bin/python"
RECORD="$HERE/batchchain-record.md"
SELFLOG="$HERE/batchchain-output.txt"
FOOTER="🤖 Generated with Codebuff
Co-Authored-By: Codebuff <noreply@codebuff.com>"

PLAN=0
WAIT=0
REARM=0
for arg in "$@"; do
  case "$arg" in
    --plan) PLAN=1 ;;
    --wait) WAIT=1 ;;
    --rearm) REARM=1 ;;
    *) echo "알 수 없는 옵션: $arg" >&2; exit 1 ;;
  esac
done

cd "$REPO" || exit 1
# `--plan` 은 문자 그대로 부작용 0 이어야 한다(계획만 보려는 사람이 로그 파일을 만들면 그 문장이 거짓이 된다).
if [ "$PLAN" -ne 1 ]; then
  exec > >(tee "$SELFLOG") 2>&1
fi

SOAK_PATTERN="${NX10_SOAK_PROC_PATTERN:-val02_staging.py}"
CHAIN_PATTERN="${NX10_CHAIN_PROC_PATTERN:-post_harvest_sequence3.sh}"
GATES_PATTERN="${NX10_GATES_PROC_PATTERN:-run_promote_gates.sh}"
WATCH_PATTERN="${NX10_WATCH_PROC_PATTERN:-soak_watch_loop.py}"
HARVEST_PATTERN="${NX10_HARVEST_PROC_PATTERN:-soak_control.sh harvest}"
WATCH_SCREEN="${NX10_WATCH_SCREEN:-nx10watch}"
LABEL="${NX10_GATE_LABEL:-batch}"
SELF_PID="$$"
started_epoch="$(date +%s)"

# ── 이어받기(`NX10_CHAIN_FROM`) — 죽은 체인을 **손으로 마무리하지 않게** ─────────────────────
# 왜 필요한가(2026-09-18 실측): 4-PERF 의 커밋에서 체인이 멈췄다. 그런데 이 체인은 단계마다 **사전 이미지**를
# 고정하므로 처음부터 다시 돌려 FLUSH 까지 가는 것이 불가능하다 — SC6 의 사전 이미지(`ecd826ce…`)는 이미
# 지나갔고 트리는 PERF 바이트다(다시 돌리면 SC6 가 exit 8 로 멈춘다). 그래서 “어느 단계부터”를 받는다.
#
# 안전장치: 건너뛰는 단계마다 **그 단계의 커밋 제목이 이력에 있어야 한다** — 없으면 멈춘다(가정하지 않는다).
FROM="${NX10_CHAIN_FROM:-SC6}"
case "$FROM" in
  SC6|PERF|FLUSH|FLUSH2) ;;
  *) echo "NX10_CHAIN_FROM 값이 이상하다: $FROM (SC6|PERF|FLUSH|FLUSH2)" >&2; exit 1 ;;
esac
# 각 배치의 커밋 제목 — 건너뛸 때 “그 일이 실제로 끝났는가”의 유일한 근거다.
subject_of() {
  case "$1" in
    SC6) printf '%s' 'feat(nx10): judge SC-6 by the creep outside the warm-up window' ;;
    PERF) printf '%s' 'feat(nx10): make throughput loss a first-class verdict axis' ;;
    FLUSH) printf '%s' 'perf(nx10): read the journal tail once per append' ;;
    FLUSH2) printf '%s' 'perf(nx10): stop rewriting the view on every append by default' ;;
  esac
}
should_run() {  # $1 = 배치 이름 — FROM 이후(포함)면 0, 아니면 1
  local target="$1" name
  for name in SC6 PERF FLUSH FLUSH2; do
    [ "$name" = "$FROM" ] && break
    [ "$name" = "$target" ] && return 1
  done
  return 0
}
require_commit() {  # 건너뛸 단계는 커밋이 있어야 한다(없으면 “이미 됐다”는 가정이 거짓이다)
  local name="$1" subject short
  subject="$(subject_of "$name")"
  # `%h` 는 가변 길이(축약)이므로 위치로 자르면 안 된다 — 실측: 처음에 `index($0,want)==3` 으로 썼다가
  # 본문 위치가 9열이라 **항상 못 찾아** 이어받기가 언제나 멈추었다(리허설 R6 이 잡았다). 탭 구분으로 정확히 본다.
  short="$(git log --format='%h%x09%s' -300 | awk -F'\t' -v want="$subject" '$2 == want { print $1; exit }')"
  [ -n "$short" ] || _stop "$name 를 건너뛰라고 했는데 그 커밋이 이력에 없다 — 이어받기 전제가 거짓이다" "resume-$name"
  ok "$name 는 이미 적용·커밋됐다($short · $subject)"
}

step() { printf '\n=== %s ===\n' "$1"; }
ok() { printf '  [OK  ] %s\n' "$1"; }
note() { printf '  [    ] %s\n' "$1"; }
bad() { printf '  [FAIL] %s\n' "$1"; }

# 무인 실행의 실패는 **기록으로 남기고 멈춘다** — 조용히 다음 단계로 넘어가면 트리가 반쯤 적용된 채 남는다.
_stop() {
  bad "$1"
  {
    printf '\n## 중단 (%s)\n\n' "$(date -u +%FT%TZ)"
    printf -- '- 단계: %s\n- 사유: %s\n' "$2" "$1"
    printf -- '- 트리: `git status --porcelain -- src tests scripts dashboard` %s\n' \
      "$([ -z "$(git status --porcelain -- src tests scripts dashboard | head -1)" ] && echo '깨끗' || echo '변경 있음')"
    printf -- '- 되돌림: 각 배치의 백업은 그 배치 스크립트가 남긴다(`apply*-output`·`--revert` 경로)\n'
  } >>"$RECORD"
  printf '  기록: %s\n' "$RECORD"
  exit 1
}
fp() { "$PY" -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))"; }
mtime_of() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
alive() { pgrep -f -- "$1" 2>/dev/null | grep -v -x "$SELF_PID" | grep -q . ; }
# 화면을 내리고 **프로세스가 사라졌는지 확인**한다(오늘 “취소했다고 기록한 예약이 살아 있었다”로 물렸다).
reap_screen() {
  local name="$1" pattern="$2" waited=0
  screen -S "$name" -X quit >/dev/null 2>&1 || true
  while alive "$pattern" && [ "$waited" -lt 30 ]; do sleep 2; waited=$((waited + 2)); done
  alive "$pattern" && return 1
  ok "$name 정리 완료(프로세스 0건 · ${waited}s)"
  return 0
}

# ── 게이트: 커밋된 트리에서 23개를 재고 요약을 남긴다 ────────────────────────────────────────────
run_gates() {
  local attempt="$1" why="$2" before after rc report verify summary
  before="$(fp)"
  NX10_GATE_ATTEMPT="$attempt" NX10_INCLUDE_CLEAN_MACHINE=1 NX10_GATE_WHY="$why" \
    bash "$NX10/run_promote_gates.sh"
  rc=$?
  after="$(fp)"
  report="$NX10/gate-report-$attempt.json"
  verify="$NX10/gate_verify-$attempt.txt"
  summary="$("$PY" -c '
import json, pathlib, sys
report, verify = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
out = []
if report.is_file():
    s = (json.loads(report.read_text(encoding="utf-8")).get("summary") or {})
    out.append("passed=%s failed=%s not_run=%s total=%s" % (s.get("passed"), s.get("failed"), s.get("not_run"), s.get("total")))
if verify.is_file():
    try:
        v = json.loads(verify.read_text(encoding="utf-8"))
        out.append("verify=%s" % v.get("verdict"))
        out.append("problems=%s" % "; ".join(v.get("problems") or [])[:200])
    except Exception:
        pass
print(" · ".join(out) or "요약을 읽지 못했다 — gate_verify-%s.txt 를 직접 볼 것" % verify.stem)
' "$report" "$verify")"
  note "게이트 러너 exit $rc · 요약: $summary"
  {
    printf '\n### 게이트 재측정 — `%s` (%s)\n\n' "$attempt" "$(date -u +%FT%TZ)"
    printf '  - 러너 exit: %s · 리포트: `gate-report-%s.json`\n' "$rc" "$attempt"
    printf '  - 지문: 측정 전 `%s` · 측정 후 `%s`%s\n' "$before" "$after" \
      "$([ "$before" = "$after" ] && echo ' (동일 — 이 리포트는 후보 값이다)' || echo ' (**갈렸다** — 그 지문의 값으로만 쓴다)')"
    printf '  - 요약: %s\n' "$summary"
  } >>"$RECORD"
  if [ "$before" != "$after" ]; then
    note "[WARN] 측정 중 지문이 움직였다 — 이 리포트를 후보 값으로 쓰지 말 것"
  fi
  [ "$rc" -eq 127 ] && _stop "게이트 러너를 실행하지 못했다(127)" "$3"
  return 0
}

# ── 커밋: 명시 경로만 스테이징하고, 미스테이징 변경이 남으면 멈춘다 ───────────────────────────────
commit_paths() {
  local subject="$1" body="$2" stepname="$3"
  shift 3
  git add -- "$@" >/dev/null 2>&1
  # 두 번째 열이 공백이 아니면 = 스테이징되지 않은 수정이 코드 경로에 남아 있다(후보가 하나로 정해지지 않는다).
  local unstaged
  unstaged="$(git status --porcelain -- src tests scripts | awk 'substr($0,2,1)!=" " {print}' | head -5)"
  if [ -n "$unstaged" ]; then
    printf '%s\n' "$unstaged"
    _stop "스테이징되지 않은 코드 변경이 남아 있다 — 후보가 하나로 정해지지 않는다" "$stepname"
  fi
  git commit -q -m "$subject" -m "$body" -m "$FOOTER" || _stop "커밋 실패 — 스테이징 상태를 확인할 것" "$stepname"
  ok "커밋 $(git rev-parse --short HEAD) — $subject"
  if [ -n "$(git status --porcelain -- src tests scripts dashboard | head -1)" ]; then
    git status --porcelain -- src tests scripts dashboard | head -5
    _stop "커밋 뒤에도 코드 경로가 깨끗하지 않다 — 지금 재는 게이트는 후보 값이 아니다" "$stepname"
  fi
  ok "코드 경로 깨끗(측정 전제 성립)"
  return 0
}

if [ "$PLAN" -eq 1 ]; then
  step "계획(부작용 0)"
  cat <<'TXT'
  ① 앞 단계를 기다린다 — 도는 soak, 3차 배치 체인(post_harvest_sequence3.sh), 게이트 러너, 감시, 회수 대기
  ② 앞 단계가 **성공**했는지 확인한다(아니면 쓰기 0건으로 멈춘다)
       · 3차 배치 산출물(scripts/soak_watch.py 등) + promote3 게이트 리포트 + 회수 판정 PASS + 시작/종료 지문 동일
       · 코드 경로(src/tests/scripts/dashboard)에 소유 불명 변경 0건
  ③ SC6  적용 → 커밋 → 게이트 23개 (scripts/val02_staging.py · tests/test_sc6_criterion_contract.py)
  ④ PERF 적용 → 커밋 → 게이트 23개 (같은 판정기 + tests/test_throughput_gate_contract.py + 실측 픽스처)
       ※ 이 단계가 있어야 FLUSH 의 합성 순서 가드(exit 6)가 통과한다
  ⑤ FLUSH  적용 → 커밋 → 게이트 23개 (src 대화 저널·스토어 + tests/test_flush_budget_contract.py)
  ⑥ FLUSH2 적용 → 커밋 → 게이트 23개 (src 스토어 + tests/test_view_freshness_contract.py · 기본값은 현행)
  ⑦ --rearm 이면: 예약 정리 → preflight → 새 8시간 soak 시작 → 감시 화면 재부착 → 회수 대기 예약
  멈추는 조건: ②가 성립하지 않거나, 어떤 배치의 가드·커밋이 실패했을 때(전부 기록을 남기고 쓰기 0건)
  멈추지 않는 것: 게이트가 빨간 것(기존 실패가 있다 — 요약만 남긴다)

  이어받기: NX10_CHAIN_FROM=FLUSH bash …/run_batch_chain.sh --wait --rearm
    · 이미 끝난 단계는 건너뛴다(사전 이미지 가드 때문에 처음부터 다시 돌릴 수 없다).
    · 건너뛰는 단계마다 **그 커밋이 이력에 있어야 한다** — 없으면 쓰기 0건으로 멈춘다.
TXT
  exit 0
fi

{
  printf '\n# 배치 체인 — 시작 %s\n' "$(date -u +%FT%TZ)"
  if [ "$FROM" != "SC6" ]; then
    printf '  - 이어받기: `NX10_CHAIN_FROM=%s` — 그 앞 단계는 **커밋으로만** 확인한다(사전 이미지 가드 때문에 처음부터 다시 돌릴 수 없다)\n' "$FROM"
  fi
} >>"$RECORD"

# ── 1. 앞 단계 대기 ─────────────────────────────────────────────────────────────────────────────
step "1. 앞 단계 대기(soak · 3차 체인 · 게이트 러너 · 감시 · 회수)"
actors=("$SOAK_PATTERN" "$CHAIN_PATTERN" "$GATES_PATTERN" "$WATCH_PATTERN" "$HARVEST_PATTERN")
running=""
for pattern in "${actors[@]}"; do
  if alive "$pattern"; then running="$running $pattern"; fi
done
if [ -n "$running" ]; then
  if [ "$WAIT" -ne 1 ]; then
    _stop "앞 단계가 아직 돌고 있다($running) — --wait 을 쓰거나 끝난 뒤 실행한다" 1
  fi
  limit="${NX10_WAIT_SECONDS:-7200}"
  note "기다린다(최대 ${limit}s):$running"
  waited=0
  while :; do
    running=""
    for pattern in "${actors[@]}"; do
      if alive "$pattern"; then running="$running $pattern"; fi
    done
    [ -z "$running" ] && break
    if [ "$waited" -ge "$limit" ]; then
      _stop "기다리다 시간 초과(${limit}s) — 남은 대상:$running" 1
    fi
    sleep 60
    waited=$((waited + 60))
    [ $((waited % 600)) -eq 0 ] && note "… 대기 ${waited}s (남은:$running)"
  done
  ok "앞 단계 종료(대기 ${waited}s)"
else
  ok "앞 단계는 이미 끝났다"
fi

# ── 2. 앞 단계가 성공했는지 확인(아니면 쓰기 0건) ───────────────────────────────────────────────
step "2. 앞 단계 결과 확인(쓰기 전 관문)"
recovery="$NX10/soak-recovery-latest.json"
[ -f "$recovery" ] || _stop "회수 판정 JSON 이 없다: $recovery — 판정 없이 코드를 옮기지 않는다" 2
verdict="$("$PY" -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); r=d.get("runner") or {}; print(d.get("verdict"), r.get("start_fingerprint"), r.get("end_fingerprint"))' "$recovery")"
set -- $verdict
verdict_val="${1:-?}"; start_fp="${2:-?}"; end_fp="${3:-?}"
[ "$verdict_val" = "PASS" ] || _stop "회수 판정이 PASS 가 아니다($verdict_val) — 배치를 적용하지 않는다" 2
[ "$start_fp" = "$end_fp" ] || _stop "시작/종료 지문이 갈렸다($start_fp ≠ $end_fp) — 이 실행은 후보에 붙일 수 없다" 2
ok "회수 판정 PASS · 시작 = 종료 지문($(printf '%s' "$start_fp" | cut -c1-12)…)"

missing=""
for marker in scripts/soak_watch.py scripts/soak_control.sh tests/test_soak_watch_contract.py; do
  [ -e "$marker" ] || missing="$missing $marker"
done
[ -z "$missing" ] || _stop "3차 배치 산출물이 없다($missing) — 앞 체인이 승격을 마치지 않았다" 2
ok "3차 배치 산출물 확인(감시·통제 도구가 scripts/·tests/ 에 있다)"

report3="$NX10/gate-report-promote3.json"
[ -f "$report3" ] || _stop "3차 배치 게이트 리포트가 없다: $report3" 2
ok "3차 배치 게이트 리포트 확인($(basename "$report3"))"

dirty="$(git status --porcelain -- src tests scripts dashboard | head -5)"
[ -z "$dirty" ] || { printf '%s\n' "$dirty"; _stop "코드 경로에 소유 불명 변경이 있다 — 그 위에 배치를 얹지 않는다" 2; }
ok "코드 경로 깨끗(src/tests/scripts/dashboard)"

# ── 3. SC6 ─────────────────────────────────────────────────────────────────────────────────────
step "3. SC6 — SC-6 새 기준(창 밖 증가 + 반복당 creep)"
if should_run SC6; then
  bash "$NX10/sc6fix/apply_sc6fix.sh" || _stop "SC6 적용 실패(가드·검증) — 트리는 그 배치가 되돌렸다" 3
  commit_paths "feat(nx10): judge SC-6 by the creep outside the warm-up window" \
    "The soak criterion compared a whole-run peak against a fixed cap, which mixes the start-up ramp into the judgement — the 30 MB spike the watcher printed was a warm-up artefact, not creep. The criterion is now computed by a pure function (warm-up window excluded, per-iteration creep scaled to the cap) with its own contract test, so the number the soak reports is the number the owner decided on." \
    "3-SC6" scripts/val02_staging.py tests/test_sc6_criterion_contract.py
  run_gates "$LABEL-sc6" "SC6 배치(SC-6 새 기준) 뒤 커밋 $(git rev-parse --short HEAD) 에서 필수 23개 재측정" "3-SC6"
else
  require_commit SC6
fi

# ── 4. PERF ────────────────────────────────────────────────────────────────────────────────────
step "4. PERF — 처리량 감소를 1급 판정 축으로(+귀속 사다리)"
if should_run PERF; then
  bash "$NX10/perf/apply_perf_gate.sh" || _stop "PERF 적용 실패(가드·검증) — 트리는 그 배치가 되돌렸다" 4
  commit_paths "feat(nx10): make throughput loss a first-class verdict axis" \
    "A wall-clock drop can be the product getting slower, the machine being busy, or the run simply doing less work — the fourth soak measured -26.5% wall clock while efficiency moved -5.0%, so a wall-clock-only gate would have failed a healthy run exactly at its 27% threshold. The axis now decomposes wall clock into efficiency and utilisation, refuses to judge when load cannot be read, and carries an attribution ladder that names the phase, the function, its call path and the call path's sub-steps before any regression is reported." \
    "4-PERF" scripts/val02_staging.py tests/test_throughput_gate_contract.py tests/live-4th-series.json
  run_gates "$LABEL-perf" "PERF 배치(처리량 축·귀속 사다리) 뒤 커밋 $(git rev-parse --short HEAD) 에서 필수 23개 재측정" "4-PERF"
else
  require_commit PERF
fi

# ── 5. FLUSH ───────────────────────────────────────────────────────────────────────────────────
step "5. FLUSH — append 예산(F1: 꼬리 읽기 3회 → 1회)"
if should_run FLUSH; then
  bash "$NX10/fsync/apply_flush_batch.sh" || _stop "FLUSH 적용 실패(동결 9 / 사전 이미지 8 / 합성 순서 6 / 검증 5)" 5
  commit_paths "perf(nx10): read the journal tail once per append" \
    "Every append read the same tail three times and re-read 113 KiB to answer a question one read answers — the flush budget probe put the cost in counts, not milliseconds, so the fix is deterministic under any disk state. Durability is untouched: the line is still written and fsynced before the view, and the tail is read exactly once inside the flock critical section." \
    "5-FLUSH" src/antigravity_k/engine/conversation_journal.py src/antigravity_k/engine/conversation_store.py tests/test_flush_budget_contract.py
  run_gates "$LABEL-flush" "FLUSH 배치(append 예산) 뒤 커밋 $(git rev-parse --short HEAD) 에서 필수 23개 재측정" "5-FLUSH"
else
  require_commit FLUSH
fi

# ── 6. FLUSH2 ──────────────────────────────────────────────────────────────────────────────────
step "6. FLUSH2 — view 신선도(읽기는 늦추지 않는다 · 기본값은 현행)"
if should_run FLUSH2; then
  bash "$NX10/fsync2/apply_flush2.sh" || _stop "FLUSH2 적용 실패(동결 9 / 사전 이미지 8 = F1 먼저 / 합성 순서 6 / 검증 5)" 6
  commit_paths "perf(nx10): stop rewriting the view on every append by default" \
    "The view is a cache of the journal, so the only thing a delayed rewrite can cost is the view file itself — public reads already reconcile from the journal, and the stale-view decision now compares sequences instead of mtime after a restore rehearsal showed mtime lying about committed turns. The lag stays opt-in and bounded, converges through flush_views(), and the default remains a rewrite per append." \
    "6-FLUSH2" src/antigravity_k/engine/conversation_store.py tests/test_view_freshness_contract.py
  run_gates "$LABEL-flush2" "FLUSH2 배치(view 신선도) 뒤 커밋 $(git rev-parse --short HEAD) 에서 필수 23개 재측정" "6-FLUSH2"
else
  require_commit FLUSH2
fi

# ── 7. 재장전 ──────────────────────────────────────────────────────────────────────────────────
# 도구의 위치: 3차 배치가 감시·통제 도구를 **`scripts/` 로 승격**했다(`docs/` 사본은 이동으로 사라졌다).
# 그래서 이 체인은 문서 사본이 아니라 **승격 위치**를 부른다 — 옛 경로를 부르면 4개 배치를 다 적용한 **뒤에**
# 재장전만 실패해 반쯤 끝난 상태로 남는다(2026-09-17 실측: 승격 직후 문서 사본 3건이 존재하지 않았다).
# 계약 시험 `test_chain_tool_paths_contract.py` 가 이 문장을 고정한다(문서 사본 경로가 다시 들어오면 빨개진다).
CONTROL="$REPO/scripts/soak_control.sh"
WATCHER="$REPO/scripts/soak_watch_loop.py"
if [ "$REARM" -ne 1 ]; then
  step "7. 재장전은 하지 않았다(--rearm 없음)"
  note "필요하면: bash $CONTROL preflight && bash $CONTROL run"
else
  step "7. 새 지문에서 재장전(--rearm)"
  # `run` 은 예약이 남아 있으면 거부한다(“두 개가 뜨지 않도록”). 반대로 **낡은 예약**을 그냥 두면
  # `preflight` 가 “예약이 하나이고 살아 있는가”에서 막힌다 — 그래서 순서는 **상태 → 고아/예약 정리 → preflight → run** 이다.
  # ⚠ `status` 의 문장에 “예약”이라는 단어가 들어가는 경우가 있으므로 **단어로 판단하지 않는다**: 종료 코드와
  # “root pid=” 표시만 근거로 삼는다(오늘 오판 두 번이 다 문장을 근거로 삼은 데서 나왔다).
  bash "$CONTROL" status 2>&1 | sed -n '1,6p'
  status_rc=${PIPESTATUS[0]:-$?}
  if [ "$status_rc" -ne 0 ]; then
    note "status exit $status_rc — 예약 상태를 고아 목록으로 확인한다"
    orphans_out="$(bash "$CONTROL" orphans 2>&1 || true)"
    printf '%s\n' "$orphans_out" | sed -n '1,6p'
    if printf '%s\n' "$orphans_out" | grep -q "root pid="; then
      note "살아 있는/낡은 예약이 있다 — 내린다(두 개가 뜨면 지문이 두 개가 된다)"
      bash "$CONTROL" cancel 2>&1 | tail -3 \
        || note "cancel 이 실패로 끝났다 — 아래 run 이 거부하면 기록을 보고 사람이 확인해야 한다"
    else
      note "고아·예약 없음 — run 이 바로 시작한다"
    fi
  else
    ok "예약 상태 정상(status exit 0)"
  fi
  [ -f "$CONTROL" ] || _stop "승격된 통제 도구가 없다: $CONTROL — 3차 배치가 커밋되지 않았다" 7
  [ -f "$WATCHER" ] || _stop "승격된 감시 도구가 없다: $WATCHER — 3차 배치가 커밋되지 않았다" 7
  bash "$CONTROL" preflight || _stop "preflight 실패 — 8시간을 태우지 않는다(위 점검 항목을 읽을 것)" 7
  bash "$CONTROL" run || _stop "시작 실패 — scripts/soak_control.sh status 로 확인" 7
  ok "새 8시간 soak 시작"
  if alive "$WATCH_PATTERN"; then
    ok "감시 루프는 이미 돌고 있다"
  else
    screen -dmS "$WATCH_SCREEN" caffeinate -i bash -c \
      "cd '$REPO' && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u scripts/soak_watch_loop.py"
    sleep 5
    alive "$WATCH_PATTERN" || _stop "감시 루프를 붙이지 못했다(화면 $WATCH_SCREEN)" 7
    ok "감시 루프 재부착(화면 $WATCH_SCREEN)"
  fi
  bash "$CONTROL" harvest --detach 2>&1 | tail -3 || _stop "회수 대기 예약에 실패 — 8시간 뒤 판정이 붙지 않는다" 7
  ok "회수 대기 예약"
  {
    printf '\n## 7. 재장전 (%s)\n\n' "$(date -u +%FT%TZ)"
    printf '  - 시작: `scripts/soak_control.sh run` · 감시 화면: `%s` · 회수: `scripts/soak_control.sh harvest --detach`\n' "$WATCH_SCREEN"
    printf '  - 기록 갱신 대상: `GATE_LEDGER`(새 attempt) · `handoff` · `PROMOTION_PLAN` · `docs/19`·`docs/20`\n'
  } >>"$RECORD"
fi

printf '\n## 종료 (%s)\n\n- 로그: `%s`\n- 다음: 게이트 요약 4건과 커밋 4건을 GATE_LEDGER·handoff·PROMOTION_PLAN·docs/19·20 에 반영\n' \
  "$(date -u +%FT%TZ)" "$(basename "$SELFLOG")" >>"$RECORD"
echo
ok "체인 완료 — 기록: $RECORD"
