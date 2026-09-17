#!/usr/bin/env bash
# 승격 3차 배치 **리허설** — 본 트리를 건드리지 않고 이동·게이트를 그대로 재현한다.
#
# 왜 미러인가: 지금 8시간 soak 이 돌고 있고(`screen nx10soak`, 종료 20:25 KST), 그 실행의 근거는
# **시작/종료 지문 일치**다. `scripts/`·`tests/` 는 지문 대상이므로 지금 옮기면 그 8시간이 무효가 된다.
# 그래서 저장소를 복제해(객체 공유 클론 + 이 배치가 건드리는 파일만 복사) 이동과 게이트를 실제로
# 재현한다 — 본 트리 쓰기 0건.
#
# 사용: bash docs/qa/2026-09-16-followup/nx10/promote3/dry_run_promotion3.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=paths3.sh
source "$HERE/paths3.sh"
# shellcheck source=gates3.sh
source "$HERE/gates3.sh"

PY="$REPO/.venv/bin/python"
M="/tmp/nx10-promote3-dryrun-$(date -u +%Y%m%dT%H%M%SZ)"
SELFLOG="$HERE/dry-run3-output.txt"
exec > >(tee "$SELFLOG") 2>&1

fail=0

step "0. 동결 무해성 — 본 트리는 읽기만 한다 ($REPO)"
printf '  미러: %s\n' "$M"
echo "  본 트리에서 도는 soak: $(pgrep -f val02_staging.py | head -1 || echo '없음')"
echo "  본 트리 지문 대상 경로 쓰기: 0건(아래 이동은 전부 미러에서 수행)"

step "1. 미러 만들기 (객체 공유 클론 + 이 배치가 건드리는 파일만 복사)"
rm -rf "$M"
if git clone -q -s --no-hardlinks "$REPO" "$M" 2>/dev/null; then
  ok "클론 완료(alternates — .git 을 복사하지 않는다)"
else
  bad "클론 실패 — 미러를 만들지 못하면 리허설을 진행할 수 없다"
  echo "실패: 미러를 만들지 못했다"
  exit 1
fi
for path in "${COPY_PATHS[@]}"; do
  mkdir -p "$M/$(dirname "$path")"
  if cp -R "$REPO/$path" "$M/$(dirname "$path")/"; then
    ok "복사: $path"
  else
    bad "복사 실패: $path"
  fi
done
ln -sfn "$REPO/.venv" "$M/.venv" && ok "인터프리터 연결(.venv 심볼릭)"

step "2. 이동 전 상태 — 승격 위치에 아직 없고, 스테이징 시험이 초록인가"
for pair in "${MOVE_PAIRS[@]}"; do
  dst="${pair##*:}"
  if [[ -e "$M/$dst" ]]; then
    bad "승격 위치에 이미 있다: $dst"
  else
    ok "승격 위치 비어 있음: $dst"
  fi
done
if (cd "$M" && PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest "$STAGING/nx10/promote3/" -q -p no:randomly >/dev/null 2>&1); then
  ok "스테이징 위치에서 두 계약 시험 초록(이동 전 기준선)"
else
  bad "스테이징에서 이미 실패 — 이동 뒤 초록과 구분할 수 없다"
fi

step "3. 이동(미러에서)"
for pair in "${MOVE_PAIRS[@]}"; do
  src="${pair%%:*}"
  dst="${pair##*:}"
  before=$(fingerprint_of "$M/$src")
  mkdir -p "$M/$(dirname "$dst")"
  if mv "$M/$src" "$M/$dst" && [[ "$(fingerprint_of "$M/$dst")" == "$before" && "$before" != "MISSING" ]]; then
    ok "$src → $dst (sha256 ${before} 동일)"
  else
    bad "$src → $dst 이동/바이트 검증 실패"
  fi
done

step "4. 이동 뒤 게이트(A·B·C·D)"
run_promoted_gates3 "$M" "$PY" yes

step "5. 스테이징 잔존 확인"
left=0
for pair in "${MOVE_PAIRS[@]}"; do
  src="${pair%%:*}"
  if [[ -e "$M/$src" ]]; then
    bad "스테이징에 사본이 남았다: $src"
    left=$((left + 1))
  fi
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
