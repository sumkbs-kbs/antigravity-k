#!/usr/bin/env bash
# 승격 2차 배치 **리허설** — 본 트리를 건드리지 않고 이동·게이트를 그대로 재현한다.
#
# 왜 미러인가: 지금 8시간 soak 이 돌고 있고(`screen nx10soak`, 종료 18:19 KST), 그 실행의 근거는
# **시작/종료 지문 일치**다. `scripts/`·`tests/` 는 지문 대상이므로 지금 옮기면 그 8시간이 무효가 된다.
# 그래서 저장소를 복제해(작은 클론 + 작업 트리 복사) 이동과 게이트를 실제로 재현한다 — 본 트리 쓰기 0건.
#
# 무엇을 증명하는가:
#   A. 이동 전에도 스테이징 시험은 초록이다(시험이 도구를 탐색해 찾는다)
#   B. 이동 뒤에도 초록이다(승격 위치에서 해석된다)
#   C. 승격 위치에서 정적 게이트를 통과한다
#   D. 도구를 치우면 시험이 **실패한다**(이빨 — 조용한 스킵이 아니다)
#   E. 스테이징에 사본이 남지 않는다(원본은 이동이다)
#
# 사용: bash docs/qa/2026-09-16-followup/nx10/promote2/dry_run_promotion2.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=paths2.sh
source "$HERE/paths2.sh"
# shellcheck source=gates2.sh
source "$HERE/gates2.sh"

PY="$REPO/.venv/bin/python"
M="/tmp/nx10-promote2-dryrun-$(date -u +%Y%m%dT%H%M%SZ)"
SELFLOG="$HERE/dry-run2-output.txt"
exec > >(tee "$SELFLOG") 2>&1

fail=0

step "0. 동결 무해성 — 본 트리는 읽기만 한다 ($REPO)"
printf '  미러: %s\n' "$M"
echo "  본 트리 실행 중 soak: $(pgrep -f val02_staging.py | head -1 || echo '없음')"
echo "  본 트리 지문 대상 경로 쓰기: 0건(아래 이동은 전부 미러에서 수행)"

step "1. 미러 만들기 (객체 공유 클론 + 작업 트리 복사)"
rm -rf "$M"
if git clone -q -s --no-hardlinks "$REPO" "$M" 2>/dev/null; then
  ok "클론 완료(alternates — 2.6 GB .git 을 복사하지 않는다)"
else
  bad "클론 실패 — 기존 커밋을 꺼낼 수 없으면 rollback 리허설의 고정 판을 쓸 수 없다"
  echo "실패: 미러를 만들지 못했다"; exit 1
fi
# 이 배치가 건드리는 **작업 트리 파일만** 가져온다(클론에는 스테이징이 없다).
for path in "${COPY_PATHS[@]}"; do
  mkdir -p "$M/$(dirname "$path")"
  if cp -R "$REPO/$path" "$M/$(dirname "$path")/"; then
    ok "복사: $path"
  else
    bad "복사 실패: $path"
  fi
done
ln -sfn "$REPO/.venv" "$M/.venv" && ok "인터프리터 연결(.venv 심볼릭)"

step "2. 이동 전 — 스테이징에서 초록인가(A)"
if (cd "$M" && PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest "${PROMOTED_TESTS[@]}" -q -p no:randomly >/dev/null 2>&1); then
  bad "승격 시험 파일이 이미 tests/ 에 있다 — 리허설이 이동 시나리오를 재현하지 못한다"
else
  ok "tests/ 에 아직 없다(이동 뒤에만 초록이어야 한다)"
fi
if (cd "$M" && PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest "docs/qa/2026-09-16-followup/nx10/promote2/" -q -p no:randomly 2>&1 | tail -2); then
  ok "스테이징 위치에서 초록(도구를 스테이징에서 찾는다)"
else
  bad "스테이징 위치에서 실패 — 이동 전 기준선이 없다"
fi

step "3. 이동(미러에서)"
for pair in "${MOVE_PAIRS[@]}"; do
  src="${pair%%:*}"; dst="${pair##*:}"
  before=$(fingerprint_of "$M/$src")
  mkdir -p "$(dirname "$M/$dst")"
  if mv "$M/$src" "$M/$dst"; then
    after=$(fingerprint_of "$M/$dst")
    if [[ "$before" == "$after" && "$before" != "MISSING" ]]; then
      ok "$src → $dst (sha256 ${before} 동일)"
    else
      bad "$src → $dst 바이트가 달라졌다($before → $after)"
    fi
  else
    bad "$src → $dst 이동 실패"
  fi
done

step "4. 이동 뒤 게이트(B·C·D)"
run_promoted_gates "$M" "$PY" yes

step "5. 스테이징 잔존 확인(E)"
left=0
for pair in "${MOVE_PAIRS[@]}"; do
  src="${pair%%:*}"
  [[ -e "$M/$src" ]] && { bad "스테이징에 사본이 남았다: $src"; left=$((left + 1)); }
done
[[ "$left" -eq 0 ]] && ok "스테이징 사본 0건(원본은 이동이다)"

step "6. 결과"
if [[ "$fail" -eq 0 ]]; then
  echo "리허설 결과: ALL PASS — 본실행 준비 완료(지문에 닿는 변경은 아직 없다)"
else
  echo "리허설 결과: 실패 $fail 건 — 본실행을 하지 말 것"
fi
rm -rf "$M"
exit $((fail == 0 ? 0 : 1))
