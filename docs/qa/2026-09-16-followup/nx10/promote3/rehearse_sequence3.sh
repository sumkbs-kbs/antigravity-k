#!/usr/bin/env bash
# 회수 뒤 순서(`post_harvest_sequence3.sh`)의 **리허설** — 미러에서 세 경로를 실제로 돌린다.
#
#   A. 판정 PASS + 지문 일치 → 승격 + 커밋까지 간다(게이트 23개는 `--skip-gates` 로 미룬다)
#   B. 판정 FAIL            → 승격하지 않는다(**트리 무변경**이 이 카드의 안전 요구다)
#   C. 지문 갈림(start≠end) → 승격하지 않는다(귀속 불성립 — 후보에 붙일 수 없다)
#
# 왜 리허설하는가: 이 순서는 **무인으로** 돌면서 커밋까지 만든다. 잘못 걸면 사람이 자는 사이에 트리가
# 옮겨지고, 그 순간 후보 지문이 움직인다. 그래서 “멈춰야 할 때 실제로 멈추는가”를 미러에서 확인하고,
# 진짜 soak·감시를 건드리지 않기 위해 식별 패턴(`NX10_*_PROC_PATTERN`)을 시험용 이름으로 바꾼다.
#
# 사용: bash docs/qa/2026-09-16-followup/nx10/promote3/rehearse_sequence3.sh
# 산출: promote3/sequence3-rehearsal.txt (전문) · 본 트리 쓰기 0건
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=paths3.sh
source "$HERE/paths3.sh"

PY="$REPO/.venv/bin/python"
OUT="$HERE/sequence3-rehearsal.txt"
exec > >(tee "$OUT") 2>&1
fail=0
step() { printf '\n=== %s ===\n' "$1"; }
ok() { printf '  [OK  ] %s\n' "$1"; }
bad() {
  printf '  [FAIL] %s\n' "$1"
  fail=$((fail + 1))
}

make_mirror() { # $1 = 경로
  local m="$1"
  rm -rf "$m"
  git clone -q -s --no-hardlinks "$REPO" "$m" 2>/dev/null || return 1
  for path in "${COPY_PATHS[@]}"; do
    mkdir -p "$m/$(dirname "$path")"
    cp -R "$REPO/$path" "$m/$(dirname "$path")/" || return 1
  done
  ln -sfn "$REPO/.venv" "$m/.venv"
  return 0
}

# 판정 산출물 픽스처 — 순서 스크립트는 `soak-recovery-latest.json`(기계 판독)과 `soak-harvest-*.txt`
# (사람이 읽는 원문) **둘 다 방금 쓰인 것**을 요구한다. 그래야 낡은 판정을 오늘 것으로 쓰지 않는다.
make_verdict() { # $1 = 미러, $2 = verdict, $3 = start_fp, $4 = end_fp
  local m="$1" verdict="$2" sfp="$3" efp="$4"
  local nx="$m/docs/qa/2026-09-16-followup/nx10"
  local stamp
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  "$PY" - "$nx/soak-recovery-latest.json" "$verdict" "$sfp" "$efp" <<'PY'
import json, pathlib, sys
path, verdict, sfp, efp = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
payload = {
    "collected_at": "2026-09-17T00:00:00Z",
    "verdict": verdict,
    "judged_run_start": "2026-09-16T12:00:00Z",
    "runner": {
        "start_time": "2026-09-16T12:00:00Z",
        "end_time": "2026-09-16T20:00:00Z",
        "exit": "0",
        "start_fingerprint": sfp,
        "end_fingerprint": efp,
    },
    "checks": [],
}
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
  {
    printf '\n  ── 판정 ──\n'
    printf '    [OK  ] SC-1 — 픽스처\n'
    printf '\n  판정: %s\n' "$verdict"
    printf '  시작 지문=%s\n  종료 지문=%s\n' "$sfp" "$efp"
  } >"$nx/soak-harvest-$stamp.txt"
}

run_case() { # $1 = A|B|C, $2 = verdict, $3 = 같은 지문?, $4 = 기대 exit
  local case_id="$1" verdict="$2" same="$3" want_rc="$4"
  local m="/tmp/nx10-seq3-rehearsal-$case_id"
  local nx="$m/docs/qa/2026-09-16-followup/nx10"
  step "$case_id — 판정 $verdict · 지문 $([ "$same" = yes ] && echo '일치' || echo '갈림')"
  make_mirror "$m" || { bad "$case_id: 미러 생성 실패"; return; }
  ok "미러: $m"
  # 지문은 **미러에서** 계산한다 — 서문에서 미리 재면 아직 없는 경로를 import 해 조용히 빈 값이 된다
  # (이 리허설의 첫 판이 그렇게 되어 케이스 A 가 거짓으로 멈쳤다 — 그게 리허설의 값이다).
  local real_fp
  real_fp="$("$PY" -c "import sys,pathlib; sys.path.insert(0,'$m/scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('$m')))")"
  [ -n "$real_fp" ] || { bad "$case_id: 미러 지문을 계산하지 못했다"; return; }
  if [ "$same" = yes ]; then
    make_verdict "$m" "$verdict" "$real_fp" "$real_fp"
  else
    make_verdict "$m" "$verdict" "$real_fp" "0000000000000000000000000000000000000000000000000000000000000000"
  fi
  ok "판정 픽스처 기록(soak-recovery-latest.json + soak-harvest-*.txt · 방금 mtime)"
  local staging_before
  staging_before="$(cd "$m" && shasum -a 256 "$STAGING/nx10/soak_watch.py" "$STAGING/nx10/soak_control.sh" | shasum -a 256 | cut -c1-12)"
  local rc=0
  (cd "$m" && NX10_REPO="$m" \
    NX10_SOAK_PROC_PATTERN="nx10-no-such-soak-$$" \
    NX10_WATCH_SCREEN="nx10seq3watch" NX10_WATCH_PROC_PATTERN="nx10-no-such-watch-$$" \
    NX10_HARVEST_SCREEN="nx10seq3harvest" NX10_HARVEST_PROC_PATTERN="nx10-no-such-harvest-$$" \
    NX10_JUDGE_SETTLE=5 NX10_GATE_ATTEMPT="seq3rehearsal" \
    bash "$nx/promote3/post_harvest_sequence3.sh" --skip-gates >"$m/sequence.log" 2>&1) || rc=$?

  if [ "$rc" = "$want_rc" ]; then
    ok "$case_id: exit $rc (기대 $want_rc)"
  else
    bad "$case_id: exit $rc (기대 $want_rc) — '$m/sequence.log' 를 볼 것"
    tail -12 "$m/sequence.log" | sed 's/^/      /'
  fi

  local moved=no
  [ -e "$m/scripts/soak_watch.py" ] && moved=yes
  if [ "$case_id" = A ]; then
    [ "$moved" = yes ] && ok "$case_id: 승격됐다(scripts/soak_watch.py 존재)" || bad "$case_id: 승격되지 않았다"
    [ -e "$m/$STAGING/nx10/soak_watch.py" ] && bad "$case_id: 스테이징 사본이 남았다(이동이어야 한다)" \
      || ok "$case_id: 스테이징은 비었다(이동)"
    local subject
    subject="$(cd "$m" && git log -1 --format=%s || true)"
    case "$subject" in
      *"promote the soak watcher"*) ok "$case_id: 커밋이 만들어졌다 — $subject" ;;
      *) bad "$case_id: 커밋이 없다(HEAD: ${subject:-없음})" ;;
    esac
    if [ -z "$(cd "$m" && git status --porcelain -- src tests scripts dashboard | head -1)" ]; then
      ok "$case_id: 커밋 뒤 코드 경로 깨끗(게이트 측정 전제 성립)"
    else
      bad "$case_id: 커밋 뒤에도 코드 경로가 더럽다 — 23개를 재면 후보 값이 아니다"
      (cd "$m" && git status --porcelain -- src tests scripts dashboard | head -5 | sed 's/^/      /')
    fi
  else
    [ "$moved" = no ] && ok "$case_id: 승격되지 않았다(scripts/soak_watch.py 없음)" || bad "$case_id: 승격됐다 — 멈춰야 한다"
    local staging_after
    staging_after="$(cd "$m" && shasum -a 256 "$STAGING/nx10/soak_watch.py" "$STAGING/nx10/soak_control.sh" | shasum -a 256 | cut -c1-12)"
    [ "$staging_before" = "$staging_after" ] && ok "$case_id: 스테이징 바이트 동일($staging_after) — 트리 무변경" \
      || bad "$case_id: 스테이징이 바뀌었다"
    if grep -q "^## 중단" "$nx/promote3/post-harvest-record3.md" 2>/dev/null; then
      ok "$case_id: 중단 사실이 기록됐다"
    else
      bad "$case_id: 중단 기록이 없다 — 무인 실행에서 조용히 끝나면 안 된다"
    fi
  fi
  rm -rf "$m"
}

step "0. 본 트리 무해성"
echo "  본 트리: $REPO"
echo "  본 트리에서 도는 soak: $(pgrep -f val02_staging.py | head -1 || echo '없음') — 이 리허설은 미러만 쓴다"
echo "  미러는 /tmp 에 만들고 각 경로 끝에서 지운다(쓰기 0건)"

run_case A PASS yes 0
run_case B FAIL yes 1
run_case C PASS no 1

step "결과"
if [ "$fail" -eq 0 ]; then
  echo "순서 리허설: ALL PASS — 세 경로가 기대대로 멈추고/진행한다"
else
  echo "순서 리허설: 실패 $fail 건 — 무인으로 걸지 말 것"
fi
exit $((fail == 0 ? 0 : 1))
