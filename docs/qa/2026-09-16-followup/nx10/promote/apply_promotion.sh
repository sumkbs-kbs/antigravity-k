#!/usr/bin/env bash
# NX-10 승격 **본실행** — 동결 해제 뒤 이 한 줄로 스테이징본을 `scripts/`·`tests/` 로 옮긴다.
#
# 리허설(같은 이동표·같은 게이트): `dry_run_promotion.sh` — 미러 트리에서 먼저 통과시킨다.
#
# 이 스크립트가 지키는 것:
#   ① 순서 — soak 판정이 끝나기 전에는 옮기지 않는다(옮기면 예약 soak 의 지문이 바뀌어 무효).
#   ② 원자성 — 게이트가 하나라도 실패하면 **되돌린다**(mv 역방향) + 원래 해시와 대조.
#   ③ 증거 — 이동 전후 파일 해시·게이트 출력·트리 상태를 `promotion-applied.txt` 에 남긴다.
#   ④ 이중 주인 금지 — 이동이므로 스테이징에 사본이 남지 않는다(사본이 남으면 `scripts/` 우선
#      해석 때문에 낡은 사본이 가려져 "고쳤는데 안 고쳐진" 상태가 된다).
#
# 사용:
#   bash docs/qa/2026-09-16-followup/nx10/promote/apply_promotion.sh                 # 정상
#   bash .../apply_promotion.sh --allow-incomplete-soak                             # soak 판정 없이
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 이동표·경로·REPO 는 **리허설과 공유**한다(`paths.sh`). 여기서 따로 계산하면 두 스크립트가
# 다른 것을 검증하게 되고, 드리프트는 본실행에서 처음 드러난다(첫 실행의 `NXF` 오산이 그랬다).
# shellcheck source=paths.sh
source "$HERE/paths.sh"
# shellcheck source=gates.sh
source "$HERE/gates.sh"
PY="$REPO/.venv/bin/python"
NXD="$(cd "$HERE/.." && pwd)"
LOG="$HERE/promotion-applied.txt"
ALLOW_INCOMPLETE_SOAK=0
[ "${1:-}" = "--allow-incomplete-soak" ] && ALLOW_INCOMPLETE_SOAK=1


say() { printf '%s\n' "$*" | tee -a "$LOG"; }
step() { say ""; say "=== $* ==="; }

# 지문은 **여기서 정의하지 않는다** — `scripts/ga_gate.py` 의 `worktree_fingerprint()` 를 부른다.
# 두 번째 지문 정의를 만들면 "같은 트리인가" 판정이 갈라진다(CLOSURE_RUNBOOK §1 과 같은 이유).
fp() {
  "$PY" - "$REPO" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("ga_gate_fp", root / "scripts" / "ga_gate.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
print(module.worktree_fingerprint(root)[:16])
PYEOF
}

cd "$REPO" || exit 1
say "NX-10 승격 실행 — $(date -u +%Y-%m-%dT%H:%M:%SZ) (호스트 시각 $(date +%H:%M:%S))"
say "저장소: $REPO"
say "브랜치: $(git rev-parse --abbrev-ref HEAD) · HEAD $(git rev-parse --short HEAD)"

# ── ① 전제조건 ────────────────────────────────────────────────────────────
step "1. 전제조건"
if [ "$ALLOW_INCOMPLETE_SOAK" = "0" ]; then
  REC="$NXD/soak-recovery-latest.json"
  if [ -f "$REC" ] && "$PY" -c "
import json, sys
d = json.load(open('$REC'))
sys.exit(0 if str(d.get('verdict', '')).startswith('PASS') else 1)
" 2>/dev/null; then
    say "  [OK  ] soak 회수 판정 = PASS ($REC)"
  else
    say "  [STOP] soak 회수 판정이 PASS 가 아니다 — 먼저 회수한다:"
    say "         \$PY $NXD/collect_soak_result.py --wait    # 판정 결과가 $REC 에 쓰인다"
    say "         (의도적으로 건너뛰려면 --allow-incomplete-soak — 그러면 승격 전후 지문을 보고에 남긴다)"
    exit 2
  fi
else
  say "  [WARN] soak 판정 확인을 건너뛴다(--allow-incomplete-soak) — 동결 해제가 다른 경로로 확인됐다는 뜻이어야 한다"
  if screen -ls 2>/dev/null | grep -q nx10soak; then
    say "  [STOP] 그래도 예약/실행 중인 soak 세션이 살아 있다: $(screen -ls | grep nx10soak)"
    exit 2
  fi
fi

promote_table_check || exit 2
say "  [OK  ] 이동표 6건이 스테이징에 있다(STAGING_ROOT=${STAGING_ROOT#$REPO/})"

conflicts=0
for pair in "${TOOL_MAP[@]}" "${TEST_MAP[@]}"; do
  dst="${pair##*:}"
  [ -e "$dst" ] && { say "  [STOP] 승격 위치에 이미 있다: $dst"; conflicts=$((conflicts + 1)); }
done
[ "$conflicts" -gt 0 ] && { say "  → 이미 승격됐거나 다른 주인이 있다. 덮어쓰지 않는다."; exit 2; }

say "  작업 트리(이동 대상 외 변경이 있는지 눈으로 확인한다):"
git status --porcelain | sed 's/^/    /' | head -20 | tee -a "$LOG"

# ── ② 이동 전 기록 ────────────────────────────────────────────────────────
step "2. 이동 전 해시·지문 기록"
BEFORE_FP="$(fp 2>/dev/null | tail -1 || true)"
say "  이동 전 코드지문(ga_gate.worktree_fingerprint): ${BEFORE_FP:-측정 불가}"
for pair in "${TOOL_MAP[@]}" "${TEST_MAP[@]}"; do
  src="$STAGING_ROOT/${pair%%:*}"
  printf '  %s %s\n' "$(shasum -a 256 "$src" | awk '{print substr($1,1,12)}')" "${pair%%:*}" | tee -a "$LOG"
done

# ── ③ 이동 ────────────────────────────────────────────────────────────────
step "3. 이동 (mv — 사본을 남기지 않는다)"
moved=()
for pair in "${TOOL_MAP[@]}" "${TEST_MAP[@]}"; do
  src="$STAGING_ROOT/${pair%%:*}"
  dst="$REPO/${pair##*:}"
  mkdir -p "$(dirname "$dst")"
  if mv "$src" "$dst"; then
    moved+=("${pair##*:}")
    say "  mv ${pair%%:*} → ${pair##*:}"
  else
    say "  [FAIL] mv 실패: ${pair%%:*}"
    break
  fi
done

rollback() {
  step "ROLLBACK — 게이트 실패로 스테이징 위치에 되돌린다"
  for pair in "${TOOL_MAP[@]}" "${TEST_MAP[@]}"; do
    dst="$REPO/${pair##*:}"
    src="$STAGING_ROOT/${pair%%:*}"
    [ -f "$dst" ] && mv "$dst" "$src" && say "  mv ${pair##*:} → ${pair%%:*}"
  done
  # `.gitignore`도 함께 되돌린다(백업본을 남겨 두었다).
  if [ -n "${GITIGNORE_BACKUP:-}" ] && [ -f "$GITIGNORE_BACKUP" ]; then
    cp -a "$GITIGNORE_BACKUP" "$REPO/.gitignore" && say "  .gitignore 복원(백업본에서)"
  fi
  say "  (.gitignore 백업은 감사용으로 남긴다: ${GITIGNORE_BACKUP:-없음})"
  say "  되돌림 후 해시(§2 와 같아야 한다):"
  for pair in "${TOOL_MAP[@]}" "${TEST_MAP[@]}"; do
    src="$STAGING_ROOT/${pair%%:*}"
    printf '  %s %s\n' "$(shasum -a 256 "$src" | awk '{print substr($1,1,12)}')" "${pair%%:*}" | tee -a "$LOG"
  done
  say "RESULT: ROLLED_BACK — 승격되지 않았다(계획 §3 게이트를 고친 뒤 다시 실행)."
  exit 1
}

# ── ③b .gitignore (문서 검사기 WARN 1건의 종결) ───────────────────────────────
# `data/auth_hash.bak.pre-0000` 은 **인증 해시 사본**인데 이 저장소의 `.gitignore` 는
# `data/auth_hash` 만 막아 그 사본은 무시되지 않는다(`docs-command-verification.txt` WARN).
# 규칙의 효력은 리허설에서 미니 저장소로 음성·양성 대조군으로 확인했다(전역 exclude 를 끄고).
step "3b. .gitignore 에 data/auth_hash.bak* 추가 (인증 해시 사본이 git add -A 에 걸리지 않게)"
# 이 저장소는 **이미 추적 중인데 무시되는 파일**이 있다(기준선 567건) — 그래서 게이트는
# "0건"이 아니라 "새 규칙으로 **늘어나지 않았다**"이다. 늘어나면 그 이름을 출력한다.
TRACKED_IGNORED_BEFORE="$(git ls-files -i -c --exclude-standard | sort)"
say "  기준선: 추적 중인데 무시되는 파일 $(printf '%s\n' "$TRACKED_IGNORED_BEFORE" | grep -c . )건(새 규칙 이전)"
GITIGNORE_BACKUP="$HERE/.gitignore.bak-$(date -u +%Y%m%dT%H%M%SZ)"
if grep -qxF 'data/auth_hash.bak*' "$REPO/.gitignore"; then
  say "  [SKIP] 규칙이 이미 있다"
else
  cp -a "$REPO/.gitignore" "$GITIGNORE_BACKUP"
  printf 'data/auth_hash.bak*\n' >>"$REPO/.gitignore"
  say "  추가: data/auth_hash.bak* (백업: $(basename "$GITIGNORE_BACKUP"))"
fi
if git -c core.excludesFile=/dev/null check-ignore -q data/auth_hash.bak.pre-0000; then
  say "  [OK  ] 사본이 이제 무시된다(git check-ignore, 전역 exclude 끔)"
else
  say "  [FAIL] 규칙을 넣었는데도 가려지지 않는다"
  rollback
fi
# 규칙이 **추적 중인** 파일을 새로 가리면 게이트·빌드가 조용해진다 — 그 자리를 먼저 막는다.
TRACKED_IGNORED_AFTER="$(git ls-files -i -c --exclude-standard | sort)"
NEWLY_IGNORED="$(comm -13 <(printf '%s\n' "$TRACKED_IGNORED_BEFORE") <(printf '%s\n' "$TRACKED_IGNORED_AFTER"))"
if [ -z "$NEWLY_IGNORED" ]; then
  say "  [OK  ] 새 규칙으로 무시된 추적 파일 0건(기준선 $(printf '%s\n' "$TRACKED_IGNORED_BEFORE" | grep -c .)건 불변, git ls-files -i -c)"
else
  say "  [FAIL] 새 규칙이 추적 중 파일을 새로 가렸다: $(printf '%s\n' "$NEWLY_IGNORED" | head -5 | tr '\n' ' ')"
  rollback
fi

# ── ④ 게이트 ──────────────────────────────────────────────────────────────
step "4. 게이트 (하나라도 실패하면 되돌린다) — 리허설과 ** 같은 함수**를 부른다"
# 게이트 정의는 `gates.sh` 하나만 있다 — 리허설이 다른 게이트 집합을 돌리면 그 차이가 곧
# 사각지대가 되고(첫 본실행이 그렇게 롤백됐다), 본실행에서 처음 드러난다.
promotion_gates "$REPO" "$PY" 2>&1 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" = "0" ] || rollback
say "  커밋되지 않은 새 파일(승격 6건이 스테이징 대상으로 보여야 한다):"
git status --porcelain | grep -E "^\?\? (scripts|tests)/" | tee -a "$LOG" || {
  say "  [FAIL] 승격 파일이 새 파일로 보이지 않는다(이미 추적 중이거나 어딘가에서 가려졌다)"
  rollback
}

# ── ⑤ 후속 ────────────────────────────────────────────────────────────────
step "5. 이동 뒤 해시·지문"
AFTER_FP="$(fp 2>/dev/null | tail -1 || true)"
say "  이동 후 코드지문(ga_gate.worktree_fingerprint): ${AFTER_FP:-측정 불가}"
if [ -n "$BEFORE_FP" ] && [ "$AFTER_FP" = "$BEFORE_FP" ]; then
  say "  [WARN] 지문이 그대로다 — 승격이 반영되지 않았을 수 있다(파일 6개가 지문 대상인지 확인)."
else
  say "  [OK  ] 지문 이동: ${BEFORE_FP:-?} → ${AFTER_FP:-?} (승격이 지문에 반영됐다)"
fi
say "  ※ 지문이 바뀌는 것은 정상이다 — 승격은 코드 이동이다. 바뀌면 **새 지문에서 게이트를 다시 돌린다**:"
say "    \$PY scripts/ga_gate.py --manifest scripts/commercial_ga_gates.json --output gate-report-promote001.json"
say "    \$PY scripts/ga_gate_verify.py --report gate-report-promote001.json"
say "    (동결 트리의 21/22 는 이제 옛 지문의 값이다 — 후보를 그대로 물려받지 않는다)"
say "  이어서 사람이 손봐야 하는 문서 참조(자동 수정하지 않는다 — 경로를 문자열로 바꾸면 링크가 조용히 깨진다):"
say "    · docs/qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md — 회수·점검 명령의 nx10/collect_soak_result.py → scripts/"
say "    · docs/qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md §5 — 미룬 코드 작업에서 승격 항목을 '완료'로"
say "    · docs/19_RELIABILITY_AND_CONNECTOME_CHECKLIST.md — 산출물 목록의 nx10/verify_docs_commands.py → scripts/"
say "    · docs/qa/2026-09-16-followup/nx01/cue-lexicon-measurement.md — 측정기 경로 → scripts/"
say "    · nx10/handoff.md · nx10/BATCH_FREEZE.md — 승격 완료 사실과 실행 기록"
say "    · scripts/verify_docs_commands.py 의 REFERENCED_PATHS/문서 목록에 새 승격 파일 3종 추가"
say "RESULT: APPLIED — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
say "기록: $LOG"
