#!/usr/bin/env bash
# 승격 3차 배치 **뒤**의 순서를 한 줄로 묶는다 — apply → 게이트 재측정 → soak 재장전.
#
# 왜 묶는가: 승격은 지문을 옮기므로 **그 지문에서 다시 재고 다시 장전**해야 한다. 순서를 사람이
# 기억해야 하는 상태는 오늘 이미 두 번 사고를 냈다(측정 중 편집 · 측정 전 재장전). 그래서 순서를
# 스크립트가 소유한다.
#
# 커밋은 **사람이 한다**(오너 결정 사항이고, 커밋은 기록을 남기는 행위다). 이 스크립트는 커밋 **전**
# 상태에서 게이트를 돌리지 않는다 — `clean-machine-runtime` 은 `--ref HEAD` 를 export 하므로
# 커밋된 트리만 후보 값이 된다. 그래서 기본 동작은:
#   ① 승격 적용  ② 커밋 안내(멈춤) ③ --continue 로 게이트 재측정 + 재장전
#
# 사용:
#   bash docs/qa/2026-09-16-followup/nx10/promote3/after_promotion3.sh            # 적용하고 커밋 안내
#   bash docs/qa/2026-09-16-followup/nx10/promote3/after_promotion3.sh --continue # 커밋 뒤: 게이트 + 재장전
#   … --plan    # 무엇을 할지만 보여 주고 아무것도 하지 않는다
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NX10="$(cd "$HERE/.." && pwd)"
REPO="${NX10_REPO:-$(cd "$NX10/../../../.." && pwd)}"
PY="$REPO/.venv/bin/python"
LOG="$HERE/after-promotion3.log"
SELFLOG="$HERE/after3-output.txt"
MODE="apply"

for arg in "$@"; do
  case "$arg" in
    --plan) MODE="plan" ;;
    --continue) MODE="continue" ;;
    *) echo "알 수 없는 인자: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$1" | tee -a "$LOG"; }
fp() { "$PY" -c "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; print(ga_gate.worktree_fingerprint(pathlib.Path('.')))"; }

cd "$REPO" || exit 1
exec > >(tee "$SELFLOG") 2>&1

if [[ "$MODE" == "plan" ]]; then
  cat <<'PLAN'
계획(부작용 0):
  1) promote3/apply_promotion3.sh        — 이동 5건 + 승격 위치 게이트(동결 가드: 도는 soak 이면 거절)
  2) 사람: 커밋                         — 승격은 지문을 옮긴다(커밋도 옮길 수 있다)
  3) run_promote_gates.sh              — NX10_GATE_ATTEMPT=promote3 NX10_INCLUDE_CLEAN_MACHINE=1 로 23개 재측정
  4) soak_control.sh preflight && run  — 새 지문에서 8시간 재장전
PLAN
  exit 0
fi

if [[ "$MODE" == "apply" ]]; then
  say "① 승격 적용"
  bash "$HERE/apply_promotion3.sh" || { say "승격 실패 — 여기서 멈춘다(트리는 되돌려졌다)"; exit 1; }
  say "② 사람이 할 일: 커밋 (승격 파일 5건 + 기록)"
  cat <<NEXT

  git add scripts/soak_watch.py scripts/soak_watch_loop.py scripts/soak_control.sh \\
          tests/test_soak_watch_contract.py tests/test_soak_control_contract.py \\
          $REPO/docs/qa/2026-09-16-followup/nx10/promote3/promotion3-applied.txt
  git commit -m "test(nx10): promote the soak watcher and control tools under the gates"

  그 뒤: bash $HERE/after_promotion3.sh --continue
NEXT
  exit 0
fi

say "③ 커밋 뒤 게이트 재측정(23개) — 이 창은 측정이 끝날 때까지 ad_code 를 만지지 않는다"
# 커밋된 트리 == 작업 트리인지 먼저 본다 — 아니면 측정이 또 다른 지문을 가리킨다(오늘 두 번 겪었다).
if [[ -n "$(git status --porcelain -- src tests scripts dashboard | head -1)" ]]; then
  say "거부: 커밋되지 않은 코드 변경이 있다 — 커밋된 후보를 재야 하므로 지금은 재지 않는다"
  git status --porcelain -- src tests scripts dashboard | head -5
  exit 1
fi
before="$(fp)"
say "지문(측정 전): $before"
NX10_GATE_ATTEMPT="promote3" NX10_INCLUDE_CLEAN_MACHINE=1 NX10_GATE_WHY="승격 3차 배치(감시·통제 도구 승격) 뒤 커밋된 후보에서 필수 23개 재측정" \
  bash "$NX10/run_promote_gates.sh"
after="$(fp)"
say "지문(측정 후): $after"
if [[ "$before" != "$after" ]]; then
  say "주의: 측정 중 지문이 움직였다 — 그 리포트는 '그 지문의 값'으로만 쓴다(후보 값이 아니다)"
fi

say "④ 새 지문에서 재장전(사전 점검 → 시작)"
# 도구는 승격을 따른다: 감시·통제 도구가 `docs/` → `scripts/` 로 옮겨졌다(3차 배치).
# 문서 사본을 부르면 "파일 없음" 으로 죽으므로 승격 위치를 먼저 본다(2026-09-17 실측).
CONTROL="$REPO/scripts/soak_control.sh"
[ -f "$CONTROL" ] || CONTROL="$NX10/soak_control.sh"
bash "$CONTROL" preflight || { say "preflight 실패 — 재장전하지 않는다(8시간을 태우지 않는다)"; exit 1; }
bash "$CONTROL" run || { say "시작 실패 — soak_control.sh status 로 확인"; exit 1; }
say "재장전 완료 — 회수: bash $CONTROL harvest --detach"
say "기록 갱신: GATE_LEDGER(새 attempt) · handoff · PROMOTION_PLAN §1e · docs/19·20"
