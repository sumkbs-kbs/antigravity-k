#!/usr/bin/env bash
# 승격 3차 배치 **본실행** — 리허설이 ALL PASS 인 상태에서만, 그리고 **동결이 풀린 뒤에만** 돈다.
#
# 왜 동결 가드가 필요한가: `scripts/`·`tests/` 는 정적 게이트 지문의 대상이다. 8시간 soak 이 도는
# 중에 이 스크립트를 돌리면 그 실행의 **종료 지문이 시작 지문과 갈려** 8시간이 무효가 된다.
# 그래서 도는 soak 을 발견하면 **거절**한다(`NX10_PROMOTE3_FORCE=1` 로만 강행).
#
# 순서(회수 뒤): 이 스크립트 → **커밋**(승격은 지문을 옮긴다) → 필수 게이트 재측정
# (`run_promote_gates.sh`, 커밋 뒤에는 `NX10_INCLUDE_CLEAN_MACHINE=1`) → soak 재장전.
# 그 3단계는 `after_promotion3.sh` 가 한 줄로 묶는다.
#
# 사용: bash docs/qa/2026-09-16-followup/nx10/promote3/apply_promotion3.sh
# 되돌리기: 실패하면 자동으로 되돌린다. 사람이 되돌릴 때는 `promotion3-applied.txt` 의 이동표를
#   역순으로 `mv` 하면 된다(백업은 /tmp 에 남긴다).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=paths3.sh
source "$HERE/paths3.sh"
# shellcheck source=gates3.sh
source "$HERE/gates3.sh"

PY="$REPO/.venv/bin/python"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/tmp/nx10-promote3-backup-$STAMP"
RECORD="$HERE/promotion3-applied.txt"
SELFLOG="$HERE/apply3-output.txt"
exec > >(tee "$SELFLOG") 2>&1

fail=0

step "1. 전제조건"
if [[ "$(cd "$REPO" && git status --porcelain -- scripts tests | wc -l | tr -d ' ')" != "0" ]]; then
  bad "scripts/ 또는 tests/ 에 미커밋 변경이 있다 — 소유가 불분명한 변경을 옮기지 않는다"
else
  ok "scripts/·tests/ 작업 트리 깨끗"
fi
soak_pid="$(pgrep -f val02_staging.py | head -1 || true)"
if [[ -n "$soak_pid" ]]; then
  if [[ "${NX10_PROMOTE3_FORCE:-0}" == "1" ]]; then
    echo "  [WARN] 도는 soak(pid $soak_pid)을 무시하고 진행한다 — NX10_PROMOTE3_FORCE=1 (그 8시간은 무효가 된다)"
  else
    bad "8시간 soak 이 돌고 있다(pid $soak_pid) — 지문이 갈리므로 거절한다. 회수 뒤에 실행할 것"
  fi
else
  ok "도는 soak 없음(동결 해제 상태)"
fi
for pair in "${MOVE_PAIRS[@]}"; do
  src="${pair%%:*}"
  dst="${pair##*:}"
  [[ -f "$REPO/$src" ]] || bad "스테이징 파일이 없다: $src"
  [[ -e "$REPO/$dst" ]] && bad "승격 위치에 이미 있다(덮어쓰지 않는다): $dst"
done
if grep -q "리허설 결과: ALL PASS" "$HERE/dry-run3-output.txt" 2>/dev/null; then
  ok "리허설 기록이 ALL PASS 다"
else
  bad "리허설을 먼저 통과시켜라: bash $HERE/dry_run_promotion3.sh"
fi
if [[ "$fail" -ne 0 ]]; then
  echo
  echo "전제조건 실패 $fail 건 — 아무것도 옮기지 않았다."
  exit 1
fi

step "2. 백업(되돌리기용) — $BACKUP"
mkdir -p "$BACKUP"
for pair in "${MOVE_PAIRS[@]}"; do
  src="${pair%%:*}"
  mkdir -p "$BACKUP/$(dirname "$src")"
  cp "$REPO/$src" "$BACKUP/$src" && ok "백업: $src (sha256 $(fingerprint_of "$REPO/$src"))"
done

step "3. 이동"
moved=()
for pair in "${MOVE_PAIRS[@]}"; do
  src="${pair%%:*}"
  dst="${pair##*:}"
  before=$(fingerprint_of "$REPO/$src")
  mkdir -p "$REPO/$(dirname "$dst")"
  if mv "$REPO/$src" "$REPO/$dst" && [[ "$(fingerprint_of "$REPO/$dst")" == "$before" ]]; then
    # 셸 러너는 `scripts/` 관례대로 실행 비트를 준다(호출은 `bash <path>` 지만 관례를 맞춘다).
    [[ "$dst" == *.sh ]] && chmod +x "$REPO/$dst"
    ok "$src → $dst (sha256 $before)"
    moved+=("$src:$dst")
  else
    bad "$src → $dst 이동/검증 실패"
    break
  fi
done

step "4. 승격 위치 게이트(A·B·C — 이빨은 리허설이 이미 증명했다)"
if [[ "$fail" -eq 0 ]]; then
  run_promoted_gates3 "$REPO" "$PY" no
fi

step "5. 결과와 롤백"
if [[ "$fail" -eq 0 ]]; then
  {
    echo "# 승격 3차 배치 실행 기록 (2026-09-17, NX-10 창)"
    echo "실행: $STAMP · 전제조건: 도는 soak 없음 · 리허설 ALL PASS"
    echo "이동표(스테이징 → 승격):"
    for entry in "${moved[@]}"; do echo "  ${entry%%:*} → ${entry##*:}"; done
    echo "백업: $BACKUP (되돌리기는 역순 mv)"
    echo "게이트: 승격 계약 시험 초록($HERE/promoted-contract-tests3.txt) · 도구 직접 실행 초록 · ruff check·format 초록"
    echo "다음(필수, 순서를 지킨다):"
    echo "  1) 커밋 — 승격은 지문을 옮긴다(커밋도 옮길 수 있다)"
    echo "  2) 필수 게이트 재측정: NX10_GATE_ATTEMPT=promote3 NX10_INCLUDE_CLEAN_MACHINE=1 \\"
    echo "       screen -dmS nx10promote3 bash docs/qa/2026-09-16-followup/nx10/run_promote_gates.sh"
    echo "  3) 콜드 재장전: soak_control.sh preflight && soak_control.sh run"
    echo "  (3단계를 묶은 것: bash $HERE/after_promotion3.sh)"
  } >"$RECORD"
  echo "승격 완료 — 기록: $RECORD"
  echo "**지문이 이동했다**: 커밋 → 게이트 재측정 → soak 재장전이 필요하다(기록의 다음 줄 참조)"
else
  echo "실패 $fail 건 — 이동을 되돌린다"
  for entry in "${moved[@]}"; do
    src="${entry%%:*}"
    dst="${entry##*:}"
    if [[ -f "$REPO/$dst" ]]; then
      mv "$REPO/$dst" "$REPO/$src" && echo "  되돌림: $dst → $src"
    fi
  done
  echo "되돌림 완료 — 백업은 $BACKUP 에 남아 있다"
fi
exit $((fail == 0 ? 0 : 1))
