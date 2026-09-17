#!/usr/bin/env bash
# 회수 뒤 순서 한 줄(3차 배치) — **판정 → 승격 → 커밋 → 새 지문에서 필수 23개 재측정**.
#
# 왜 이 순서인가(오늘 하루가 세 번 가르쳤다):
#   ① 승격은 `scripts/`·`tests/` 를 옮겨 **지문을 움직인다** → 도는 soak 의 시작/종료 지문 일치가 깨진다.
#      그래서 승격은 **실행 종료 + 회수 판정 뒤**에만 한다(3차 soak 을 1시간에 끊어야 했던 이유가 그것이다).
#   ② 승격 뒤에는 **커밋**이 필요하다: `clean-machine-runtime` 은 `--ref HEAD` 를 export 하므로
#      커밋된 트리만 후보 값이 된다(커밋 없이 돌린 23개는 "작업 트리의 값"으로만 쓸 수 있다).
#   ③ 커밋 뒤 **그 지문에서** 필수 23개를 다시 잰다 — 옛 리포트는 옛 지문의 값이다.
#
# 사용:
#   bash …/promote3/post_harvest_sequence3.sh --plan          # 무엇을 할지만 보여 준다(부작용 0)
#   bash …/promote3/post_harvest_sequence3.sh --wait          # 종료를 기다렸다가 ①~⑤ 를 무인 실행
#   bash …/promote3/post_harvest_sequence3.sh                 # 지금 상태로 실행(도는 soak 이면 거절)
#
# 옵션/환경변수:
#   `--wait`                      실행 종료를 기다린다(없으면 도는 soak 이 있을 때 거절)
#   `--skip-commit`               승격까지만 하고 커밋에서 멈춘다(사람이 커밋)
#   `--skip-gates`                승격·커밋까지만(게이트는 따로)
#   `--rearm`                     게이트 뒤 새 8시간 soak 을 재장전한다(기본은 하지 않는다)
#   `NX10_WAIT_SECONDS`(43200)    실행 종료 대기 상한
#   `NX10_JUDGE_SETTLE`(900)      떠 있는 회수 감시가 판정을 쓸 때까지 기다리는 상한
#   `NX10_PROMOTE_ON_FAIL=1`      판정 FAIL 이어도 승격을 강행(기본은 **멈춘다**)
#   `NX10_GATE_ATTEMPT`(promote3) 리포트 이름
#   `NX10_SOAK_PROC_PATTERN`(val02_staging.py) — 실행·감시를 식별하는 패턴. **시험용**으로 바꿀 수 있다
#     (`soak_control.sh` 와 같은 이름·같은 뜻). 리허설은 이 이름들을 바꿔 진짜 soak·감시를 건드리지 않는다.
#
# 무인 실행(오너 요청 “회수가 끝나면 승격하고 새 지문에서 게이트 재측정”):
#   screen -dmS nx10promote3 caffeinate -i bash -c \
#     'cd <repo> && bash …/promote3/post_harvest_sequence3.sh --wait >> …/promote3/post-harvest-sequence3.log 2>&1'
#   취소: `screen -S nx10promote3 -X quit` — 승격 **전**이면 트리 무변경(그 뒤면 커밋이 롤백 지점이다).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NX10="$(cd "$HERE/.." && pwd)"
REPO="${NX10_REPO:-$(cd "$NX10/../../../.." && pwd)}"
PY="$REPO/.venv/bin/python"
RECORD="$HERE/post-harvest-record3.md"
SELFLOG="$HERE/post-harvest-sequence3-output.txt"

PLAN=0
WAIT=0
SKIP_COMMIT=0
SKIP_GATES=0
REARM=0
for arg in "$@"; do
  case "$arg" in
    --plan) PLAN=1 ;;
    --wait) WAIT=1 ;;
    --skip-commit) SKIP_COMMIT=1 ;;
    --skip-gates) SKIP_GATES=1 ;;
    --rearm) REARM=1 ;;
    *) echo "알 수 없는 옵션: $arg" >&2; exit 1 ;;
  esac
done

cd "$REPO" || exit 1
# `--plan` 은 **문자 그대로 부작용 0** 이어야 한다(계획만 보려는 사람이 로그 파일을 만들면 그 문장이 거짓이 된다).
if [ "$PLAN" -ne 1 ]; then
  exec > >(tee "$SELFLOG") 2>&1
fi

# 식별 패턴 — 기본값이 운영 경로다. 리허설(승격 전 리허설처럼 전체 순서를 미러에서 돌리는 경우)은
# 이 이름들을 바꿔 **진짜 soak·감시를 건드리지 않는다**(오늘 “취소한 예약이 살아 있었다” 를 겪은 뒤로
# 통제 도구는 대상을 문장이 아니라 이름으로 지목하고, 시험은 그 이름을 통제한다는 규칙을 따른다).
SOAK_PATTERN="${NX10_SOAK_PROC_PATTERN:-val02_staging.py}"
WATCH_SCREEN="${NX10_WATCH_SCREEN:-nx10watch}"
WATCH_PATTERN="${NX10_WATCH_PROC_PATTERN:-soak_watch_loop.py}"
HARVEST_SCREEN="${NX10_HARVEST_SCREEN:-nx10harvest}"
HARVEST_PATTERN="${NX10_HARVEST_PROC_PATTERN:-soak_control.sh harvest}"
SELF_PID="$$"


started_epoch="$(date +%s)"
step() { printf '\n=== %s ===\n' "$1"; }
ok() { printf '  [OK  ] %s\n' "$1"; }
note() { printf '  [    ] %s\n' "$1"; }

# 무인 실행의 실패는 **기록으로 남기고 멈춘다** — 조용히 다음 단계로 넘어가면 트리가 옮겨진 채 남는다.
_stop() {
  printf '  [FAIL] %s\n' "$1"
  {
    printf '\n## 중단 (%s)\n\n' "$(date -u +%FT%TZ)"
    printf '  - 단계: %s\n- 사유: %s\n' "$2" "$1"
    printf '  - 트리 상태: `git status --porcelain -- src tests scripts dashboard` %s\n' \
      "$([ -z "$(git status --porcelain -- src tests scripts dashboard | head -1)" ] && echo '깨끗' || echo '변경 있음')"
  } >>"$RECORD"
  printf '  기록: %s\n' "$RECORD"
  exit 1
}
fp() { "$PY" -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))"; }
mtime_of() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }
screen_alive() { pgrep -f -- "$1" 2>/dev/null | grep -v -x "$SELF_PID" | grep -q . ; }
# 화면을 내리고 **프로세스가 사라졌는지 확인**한다 — 오늘 “취소했다고 기록한 예약이 살아 있었다” 로 한 번 물렸다.
reap_screen() {
  local name="$1" pattern="$2" waited=0
  screen -S "$name" -X quit >/dev/null 2>&1 || true
  while screen_alive "$pattern" && [ "$waited" -lt 30 ]; do
    sleep 2
    waited=$((waited + 2))
  done
  if screen_alive "$pattern"; then
    return 1
  fi
  ok "$name 정리 완료(프로세스 0건 · ${waited}s)"
  return 0
}

if [ "$PLAN" -eq 1 ]; then
  step "계획(부작용 0)"
  cat <<'TXT'
  ① 실행 종료를 기다린다(도는 soak 이 있으면 --wait 필요)
  ② 회수 판정 — 이미 내려진 판정 중 **이 실행에 대한 것**(러너 종료 뒤 수집 · 실행 트리에서 판정)을
     먼저 집고, 없으면 직접 harvest 한다
     → 문장을 긁지 않고 `soak-recovery-latest.json` 의 `verdict`·`runner.exit`·시작/종료 지문을 읽는다
     → PASS 가 아니거나 지문이 갈렸으면 **여기서 멈춘다**(트리 무변경)
  ③ 감시 도구 정리(감시 루프·회수 대기) — 프로세스 0건까지 확인
  ④ 승격(promote3/apply_promotion3.sh) — 이동 5건 + 승격 위치 게이트(A·B·C), 실패 시 자동 롤백
  ⑤ 커밋 — 승격 파일 5건 + 기록(clean-machine-runtime 이 `--ref HEAD` 를 쓰므로 커밋이 전제다)
  ⑥ 필수 23개 재측정(NX10_INCLUDE_CLEAN_MACHINE=1, 약 19분) — 새 지문에서
  ⑦ 기록(`post-harvest-record3.md`) → 재장전은 `--rearm` 을 준 경우에만
  멈추는 조건: 판정이 PASS 가 아니면 ④로 가지 않는다(NX10_PROMOTE_ON_FAIL=1 로만 강행).
TXT
  exit 0
fi

{ printf '\n# 회수 뒤 무인 순서(3차 배치) — 시작 %s\n\n' "$(date -u +%FT%TZ)"; } >>"$RECORD"

step "1. 실행 종료 확인"
if screen_alive "$SOAK_PATTERN"; then
  if [ "$WAIT" -ne 1 ]; then
    _stop "8시간 soak 이 아직 돌고 있다 — 회수 뒤에 실행하거나 --wait 을 쓴다(지문 보호)" 1
  fi
  limit="${NX10_WAIT_SECONDS:-43200}"
  note "도는 soak 을 기다린다(최대 ${limit}s) — 남은 초는 soak_control.sh status 로 확인할 수 있다"
  waited=0
  while screen_alive "$SOAK_PATTERN"; do
    if [ "$waited" -ge "$limit" ]; then
      _stop "기다리다 시간 초과(${limit}s) — 사람이 확인해야 한다" 1
    fi
    sleep 60
    waited=$((waited + 60))
    [ $((waited % 600)) -eq 0 ] && note "… 대기 ${waited}s"
  done
  ok "실행이 끝났다(대기 ${waited}s)"
else
  ok "도는 soak 없음"
fi

step "2. 회수 판정"
settle="${NX10_JUDGE_SETTLE:-900}"
# 판정의 **기계 판독 가능한 원문**은 `soak-recovery-latest.json` 이다(판정기가 `verdict`·`runner`·
# 체크 목록을 남기고, 계약 시험이 그 필드를 지킨다). 문장을 긁는 대신 이 파일을 읽는다.
#
# 받아들이는 조건은 “이 **실행**에 대한 판정인가”이지 “이 체인이 시작된 뒤에 쓰였는가”가 아니다.
# 종전 규칙(mtime ≥ 체인 시작)은 이미 내려진 정당한 판정을 **낡은 것으로 오해**해 스스로 다시
# 판정하게 만들었고, 그 재판정은 이 체인이 지키려는 지문 조건(측정 후 코드 무변경)을 **자기 손으로**
# 깨뜨렸다 — 재판정 시점에는 이미 커밋/문서가 움직였을 수 있기 때문이다(2026-09-17 실측).
# 그래서 조건을 **내용으로만** 본다: ① 러너 종료시각 뒤에 수집됐다 ② 그 판정이 **실행 트리에서**
# 내려졌다(`worktree_fingerprint_now == runner.start_fingerprint`) ③ 어느 실행을 판정했는지 밝힌다
# (`judged_run_start`). mt–ime 은 근거로 쓰지 않는다: `git stash/restore`(프리커밋 훅)가 파일을
# 다시 쓰면서 시각을 바꾸고, 판정기 자체 실행(`collect_soak_result.py`)은 JSON 만 새로 쓰고 텍스트를
# 남기지 않아 “새 JSON + 옛 txt” 를 낡은 것으로 오인하게 만들었다(2026-09-17 실측).
# 못 받으면 종전과 같이 직접 harvest 한다(닫힌 방향으로 실패한다).
recovery="$NX10/soak-recovery-latest.json"
verdict_is_about_the_run() {
  [ -f "$recovery" ] || return 1
  "$PY" - "$recovery" <<'PYX'
import json, sys
try:
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(1)
run = doc.get("runner") or {}
end = run.get("end_time")
collected = doc.get("collected_at")
# 어느 실행을 판정했는지 밝히지 않는 JSON 은 근거로 쓰지 않는다(그것이 “낡은 판정” 을 잡는 방법이다).
if not doc.get("judged_run_start"):
    sys.exit(1)
if not isinstance(end, str) or not isinstance(collected, str):
    sys.exit(1)
# ① 종료 뒤에 수집(같은 ISO8601 Z 형식이므로 문자열 비교가 시각 비교다)
if collected < end:
    sys.exit(1)
# ② 실행 트리에서 내려진 판정만 받는다 — 판정 뒤에 코드가 움직였으면 그 green 은 후보의 것이 아니다
if str(doc.get("worktree_fingerprint_now") or "") != str(run.get("start_fingerprint") or ""):
    sys.exit(1)
sys.exit(0)
PYX
}
latest=""
waited=0
while [ "$waited" -lt "$settle" ]; do
  latest="$(ls -t "$NX10"/soak-harvest-*.txt 2>/dev/null | head -1 || true)"
  if [ -n "$latest" ] && verdict_is_about_the_run; then
    break
  fi
  latest=""
  sleep 15
  waited=$((waited + 15))
done
judge_rc=0
if [ -n "$latest" ]; then
  ok "이 실행에 대한 판정이 이미 있다(대기 ${waited}s): $(basename "$latest")"
  basis="$("$PY" - "$recovery" <<'PYB'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
r = d.get("runner") or {}
print(f"수집 {d.get('collected_at')} ≥ 종료 {r.get('end_time')} · 판정 지문 == 실행 지문 {str(r.get('start_fingerprint'))[:16]}… · 판정 대상 {d.get('judged_run_start')}")
PYB
)"
  note "받아들인 근거: $basis"
  # 텍스트 원문이 JSON 보다 옛것일 수 있다(판정기를 직접 돌린 경우). 읽는 사람이 그것을 오해하지 않게 밝힌다.
  if [ "$(mtime_of "$recovery")" -gt "$(mtime_of "$latest")" ]; then
    note "[참고] 원문 txt($(basename "$latest"))는 이 JSON 보다 오래됐다 — **판정의 출처는 JSON** 이고 txt 는 그 이전 판정의 글이다"
  fi
else
  note "판정 원문이 아직 없다 — harvest 를 직접 돌린다"
  bash "$NX10/soak_control.sh" harvest --timeout 900 || judge_rc=$?
  latest="$(ls -t "$NX10"/soak-harvest-*.txt 2>/dev/null | head -1 || true)"
  if [ "$judge_rc" -eq 0 ]; then
    ok "harvest exit 0(판정 PASS)"
  else
    note "harvest exit $judge_rc — 판정기를 직접 읽어 확정한다"
  fi
fi
[ -n "$latest" ] || _stop "판정 원문을 찾지 못했다 — harvest 로그를 직접 확인할 것" 2
[ -f "$recovery" ] || _stop "판정 JSON(soak-recovery-latest.json)이 없다 — 판정을 확정할 수 없다" 2

# bash 3.2(macOS 기본)에는 mapfile 이 없다 — 줄 단위로 읽어 배열에 담는다.
jfields=()
while IFS= read -r line; do jfields+=("$line"); done < <("$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
r = d.get("runner") or {}
for value in (d.get("verdict"), r.get("exit"), r.get("start_fingerprint"), r.get("end_fingerprint"),
              r.get("start_time"), r.get("end_time"), d.get("collected_at")):
    print("?" if value is None else value)
' "$recovery")
verdict="${jfields[0]:-?}"
run_exit="${jfields[1]:-?}"
start_fp="${jfields[2]:-?}"
end_fp="${jfields[3]:-?}"
run_start="${jfields[4]:-?}"
run_end="${jfields[5]:-?}"
collected="${jfields[6]:-?}"
{
  printf '\n## 2. 회수 판정 (%s)\n\n' "$(date -u +%FT%TZ)"
  printf '  - 판정 원문: `%s` (판정기 exit %s) · JSON: `soak-recovery-latest.json` (collected_at %s)\n' \
    "$(basename "$latest")" "$judge_rc" "$collected"
  printf '  - 실행: %s → %s · 러너 exit %s\n' "$run_start" "$run_end" "$run_exit"
  printf '  - 판정: **%s**\n' "$verdict"
  printf '  - 시작 지문: `%s`\n- 종료 지문: `%s`\n' "$start_fp" "$end_fp"
} >>"$RECORD"
note "판정: $verdict · 러너 exit $run_exit · 실행 $run_start → $run_end"
if [ "$verdict" != "PASS" ]; then
  if [ "${NX10_PROMOTE_ON_FAIL:-0}" = "1" ]; then
    note "[WARN] 판정이 PASS 가 아니다($verdict) — NX10_PROMOTE_ON_FAIL=1 로 강행한다(FAIL 원인이 후보 코드면 승격 뒤 지문이 또 움직인다)"
  else
    _stop "판정이 PASS 가 아니다($verdict) — 승격을 멈춘다(트리 무변경). 읽을 것: $latest" 2
  fi
fi
if [ "$start_fp" = "?" ] || [ "$end_fp" = "?" ]; then
  _stop "판정 JSON 에 시작/종료 지문이 없다 — 귀속을 확인할 수 없다(승격 근거가 없다)" 2
fi
if [ "$start_fp" != "$end_fp" ]; then
  _stop "시작/종료 지문이 갈렸다 — 이 실행은 후보에 붙일 수 없다(승격 근거가 없다)" 2
fi
ok "귀속 성립(시작 == 종료)"

step "3. 감시 도구 정리(할 일이 끝났다)"
# 자기 자신(`$$`)은 대상이 아니다 — 이 스크립트의 argv 에도 패턴이 들어 있기 때문이다(실측 함정).
if screen_alive "$WATCH_PATTERN"; then
  reap_screen "$WATCH_SCREEN" "$WATCH_PATTERN" || _stop "감시 루프가 죽지 않았다 — 다음 단계로 가지 않는다" 3
else
  ok "감시 루프는 이미 종료"
fi
if screen_alive "$HARVEST_PATTERN"; then
  reap_screen "$HARVEST_SCREEN" "$HARVEST_PATTERN" || _stop "회수 대기 프로세스가 죽지 않았다" 3
else
  ok "회수 대기 프로세스는 이미 종료(판정을 마쳤다)"
fi

step "4. 승격(3차 배치)"
if [ -n "$(git status --porcelain -- scripts tests | head -1)" ]; then
  _stop "scripts/·tests/ 에 미커밋 변경이 있다 — 소유가 불분명한 변경 위에 승격하지 않는다" 4
fi
bash "$HERE/apply_promotion3.sh" || _stop "승격 실패 — 이동은 자동 롤백됐다(apply3-output.txt 확인)" 4
new_fp="$(fp)"
ok "승격 완료 — 지문이 이동했다: $new_fp"

if [ "$SKIP_COMMIT" -eq 1 ]; then
  note "--skip-commit: 커밋에서 멈춘다(사람이 커밋한 뒤 --skip-commit 없이 다시 실행하면 게이트부터 돈다)"
  printf '\n## 4. 승격 완료 · 커밋 대기 (%s)\n\n- 새 지문: `%s`\n' "$(date -u +%FT%TZ)" "$new_fp" >>"$RECORD"
  exit 0
fi

step "5. 커밋(커밋된 후보여야 clean-machine-runtime 이 후보 값이 된다)"
# 명시 경로만 스테이징한다(`git add -A` 는 다른 창의 파일을 삼킬 수 있다).
git add scripts/soak_watch.py scripts/soak_watch_loop.py scripts/soak_control.sh \
  tests/test_soak_watch_contract.py tests/test_soak_control_contract.py \
  "$HERE/promotion3-applied.txt" \
  "$NX10/soak_watch.py" "$NX10/soak_watch_loop.py" "$NX10/soak_control.sh" \
  "$HERE/test_soak_watch_contract.py" "$HERE/test_soak_control_contract.py" \
  "$latest" "$SELFLOG" "$HERE/apply3-output.txt" >/dev/null 2>&1
if [ -n "$(git status --porcelain -- scripts tests | grep -v '^A ' | grep -v '^D ' | head -1)" ]; then
  git status --porcelain -- scripts tests | head -5
  _stop "승격 경로 밖에 커밋되지 않은 코드 변경이 남아 있다 — 후보가 하나로 정해지지 않는다" 5
fi
git commit -q -m "test(nx10): promote the soak watcher and control tools under the gates" \
  -m "The three tools that judged the fourth soak — the watcher verdict, the live trend view, and the arm/run/cancel/harvest control — move into scripts/ with their contract tests, so the static gates and the suite start guarding judgement code that until now lived only in docs/, where nothing watched it. Candidate committed before the gate re-measure because clean-machine-runtime validates HEAD." \
  -m "🤖 Generated with Codebuff
Co-Authored-By: Codebuff <noreply@codebuff.com>" || _stop "커밋 실패 — 스테이징 상태를 확인할 것" 5
commit_sha="$(git rev-parse --short HEAD)"
ok "커밋 $commit_sha"
if [ -n "$(git status --porcelain -- src tests scripts dashboard | head -1)" ]; then
  git status --porcelain -- src tests scripts dashboard | head -5
  _stop "커밋 뒤에도 코드 경로가 깨끗하지 않다 — 지금 잰 게이트는 후보 값이 아니다" 5
fi
ok "코드 경로 깨끗(측정 전제 성립)"
{
  printf '\n## 5. 승격·커밋 (%s)\n\n' "$(date -u +%FT%TZ)"
  printf '  - 커밋: `%s` · 새 지문: `%s`\n' "$commit_sha" "$new_fp"
} >>"$RECORD"

if [ "$SKIP_GATES" -eq 1 ]; then
  note "--skip-gates: 게이트 재측정은 따로 실행한다"
  exit 0
fi

step "6. 새 지문에서 필수 게이트 재측정(23개 · 약 19분)"
attempt="${NX10_GATE_ATTEMPT:-promote3}"
before="$(fp)"
NX10_GATE_ATTEMPT="$attempt" NX10_INCLUDE_CLEAN_MACHINE=1 \
  NX10_GATE_WHY="3차 승격 배치(감시·통제 도구) 뒤 커밋 $commit_sha 에서 필수 23개 재측정" \
  bash "$NX10/run_promote_gates.sh"
gate_rc=$?
after="$(fp)"
report="$NX10/gate-report-$attempt.json"
verify="$NX10/gate_verify-$attempt.txt"
summary="$("$PY" -c '
import json, pathlib, sys
report, verify = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
out = []
if report.is_file():
    summary = (json.loads(report.read_text(encoding="utf-8")).get("summary") or {})
    out.append("passed=%s failed=%s not_run=%s total=%s" % (
        summary.get("passed"), summary.get("failed"), summary.get("not_run"), summary.get("total")))
if verify.is_file():
    try:
        v = json.loads(verify.read_text(encoding="utf-8"))
        out.append("verify=%s" % v.get("verdict"))
        out.append("problems=%s" % "; ".join(v.get("problems") or []))
    except Exception:
        pass
print(" · ".join(out) or "요약을 읽지 못했다 — gate_verify-%s.txt 를 직접 볼 것")
' "$report" "$verify")"
{
  printf '\n## 6. 필수 23개 재측정 (%s)\n\n' "$(date -u +%FT%TZ)"
  printf '  - attempt: `%s` · 러너 exit: %s · 리포트: `gate-report-%s.json`\n' "$attempt" "$gate_rc" "$attempt"
  printf '  - 지문: 측정 전 `%s` · 측정 후 `%s`%s\n' "$before" "$after" \
    "$([ "$before" = "$after" ] && echo ' (동일 — 이 리포트는 후보 값이다)' || echo ' (**갈렸다** — 그 지문의 값으로만 쓴다)')"
  printf '  - 요약: %s\n' "${summary:-gate_verify-$attempt.txt 를 읽을 것}"
} >>"$RECORD"
note "게이트 러너 exit $gate_rc · 요약: ${summary:-확인 필요}"
if [ "$before" != "$after" ]; then
  note "[WARN] 측정 중 지문이 움직였다 — 리포트를 후보 값으로 쓰지 말 것"
fi

if [ "$REARM" -eq 1 ]; then
  step "7. 재장전(--rearm)"
  bash "$NX10/soak_control.sh" preflight || _stop "preflight 실패 — 8시간을 태우지 않는다" 7
  bash "$NX10/soak_control.sh" run || _stop "시작 실패 — soak_control.sh status 로 확인" 7
  ok "재장전 완료"
else
  step "7. 재장전은 하지 않았다(--rearm 없음)"
  note "필요하면: bash $NX10/soak_control.sh preflight && bash $NX10/soak_control.sh run"
fi

printf '\n## 7. 종료 (%s)\n\n- 로그: `%s`\n- 다음: 기록을 GATE_LEDGER·handoff·PROMOTION_PLAN §1e·docs/19·20 에 반영\n' \
  "$(date -u +%FT%TZ)" "$(basename "$SELFLOG")" >>"$RECORD"
echo
ok "순서 완료 — 기록: $RECORD"
