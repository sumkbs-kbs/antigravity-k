#!/usr/bin/env bash
# NX-10 승격 **리허설** — 이 창에서 만든 보조도구를 `scripts/`·`tests/` 로 옮기는 일을
# 본 트리를 건드리지 않고 그대로 재현한다.
#
# 왜 미러인가: 본 트리에는 22:00 예약 soak 이 걸려 있고 그 실행기는 시작 직전에
# `worktree_fingerprint` 를 검사해 **다르면 8시간을 태우지 않고 스스로 중단**한다.
# `scripts/`·`tests/` 는 그 지문의 대상이므로 지금 옮길 수 없다. 그래서 저장소를 /tmp 로
# 복제해 **이동·게이트 조건을 실제로 재현**한다(본 트리 쓰기 0건).
#
# 무엇을 증명하는가:
#   A. 이동 전에도 스테이징본 시험은 초록이다(시험이 도구를 **탐색**해서 찾는다)
#   B. 이동 뒤에도 초록이다(승격 위치 `scripts/` 에서 해석된다)
#   C. 도구가 없으면 **그 시험이 실패한다**(초록이 조용한 스킵이 아니다 — 이빨 확인)
#   D. 옮긴 파일이 정적 게이트(ruff check · ruff format --check)를 통과한다
#
# 사용: bash docs/qa/2026-09-16-followup/nx10/promote/dry_run_promotion.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 이동표·스테이징 경로는 **본실행과 같은 파일**에서 온다(`paths.sh`) — 하드코딩하면
# 리허설이 다른 스크립트를 검증하게 된다(본실행의 첫 `NXF` 오산을 리허설이 통과시킨 이유다).
# shellcheck source=paths.sh
source "$HERE/paths.sh"
# shellcheck source=gates.sh
source "$HERE/gates.sh"
PY="$REPO/.venv/bin/python"
M="/tmp/nx10-promote-dryrun-$(date -u +%Y%m%dT%H%M%SZ)"
MIRROR_STAGING="$M/docs/qa/2026-09-16-followup"

# 이 스크립트는 자기 출력을 자기 파일에 남긴다 — 마지막 단계가 **그 파일을 다시 읽어**
# bash 진단(실행 오류)이 섮이지 않았는지 본다. 왜 필요한가: 메시지 문자열을 큰따옴표로 쓰고
# 그 안에 역따옴표를 넣으면 **명령이 실제로 실행**되는데, 결과 줄만 보면 초록으로 위장한다
# (첫 작성이 정확히 그랬다 — `data/auth_hash.bak.pre-0000` 이 실행되고 ALL PASS 가 찍혔다).
SELFLOG="$HERE/dry-run-output.txt"
exec > >(tee "$SELFLOG") 2>&1

fail=0
step() { printf '\n=== %s ===\n' "$1"; }
ok() { printf '  [OK  ] %s\n' "$1"; }
bad() {
  printf '  [FAIL] %s\n' "$1"
  fail=$((fail + 1))
}

# 이동표는 `paths.sh` 에서 왔다(여기서 재정의하지 않는다).

step "0. 동결 무해성 — 본 트리에서 읽기만 한다 ($REPO)"
printf '  미러: %s\n' "$M"
# 승격 배치에 포함된 .gitignore 규칙의 **효력**을 미니 저장소에서 확인한다.
# 전역 exclude(`core.excludesFile`)를 끄고 재야 한다 — 켜 두면 개발자 설정이 판정을 대신한다.
GI="/tmp/nx10-gitignore-check-$$"
rm -rf "$GI"
mkdir -p "$GI/data"
cp "$REPO/.gitignore" "$GI/.gitignore"
: >"$GI/data/auth_hash.bak.pre-0000"
git -C "$GI" init -q 2>/dev/null
if git -C "$GI" -c core.excludesFile=/dev/null check-ignore -q data/auth_hash.bak.pre-0000; then
  bad "음성 대조군 실패 — 현재 규칙이 이미 백업 사본을 가린다(WARN 이 오탑이라는 뜻)"
else
  ok "음성 대조군: 현재 .gitignore 는 백업 사본을 가리지 않는다(무시되지 않은 채 untracked = WARN 의 원인)"
fi
printf 'data/auth_hash.bak*\n' >>"$GI/.gitignore"
if git -C "$GI" -c core.excludesFile=/dev/null check-ignore -q data/auth_hash.bak.pre-0000; then
  # 메시지에 역따옴표를 쓰려면 작은따옴표로 감싼다 — 큰따옴표 안의 `` ` `` 는 **명령 치환**이다.
  # (첫 작성에서 양성 메시지를 큰따옴표로 쓴 바람에 `data/auth_hash.bak.pre-0000` 이 실제로 실행됐다.)
  ok '양성: data/auth_hash.bak* 규칙을 넣으면 그 사본이 가려진다'
else
  bad "규칙을 넣어도 가려지지 않는다 — 규칙 문구를 다시 짜야 한다"
fi
rm -rf "$GI"
printf '  이 스크립트는 본 트리에 **쓰지 않는다** — 지문은 예약 soak 의 기대값 그대로 남는다.\n'
printf '  (지문의 정본은 이 스크립트가 아니라 예약 실행기·`collect_soak_result.py` 가 읽는 러너 기록이다.\n'
printf '   여기서 다시 재면 두 번째 지문 정의가 생겨 §fingerprint-drift 판정이 갈라진다.)\n'

step "1. 미러 트리 구성 (src·scripts·docs·tests 는 **그대로 복사**, 나머지 최상위 항목은 심볼릭)"
# tests/ 를 골격으로 줄이면 안 된다 — 이 창의 시험(`test_local_relative_links_resolve`)이
# `docs/qa/**/*.md` 의 상대 링크를 저장소 전체 기준으로 검사하므로, `tests/` 를 줄이면
# 관계없는 문서 링크가 미러에서만 깨진다(첫 리허설이 실제로 그렇게 거짓 FAIL 을 냈다).
rm -rf "$M"
mkdir -p "$M"
shopt -s dotglob
for entry in "$REPO"/*; do
  name="$(basename "$entry")"
  case "$name" in
    scripts | tests | docs | src | .venv | .git | __pycache__) continue ;;
    *) ln -sfn "$entry" "$M/$name" ;;
  esac
done
shopt -u dotglob
# python3.13 의 `Path.rglob` 은 심볼릭 디렉터리를 따라가지 않는다 — 검사기가 `src` 를 훑으므로 복사한다.
cp -a "$REPO/src" "$M/src"
cp -a "$REPO/scripts" "$M/scripts"
cp -a "$REPO/docs" "$M/docs"
cp -a "$REPO/tests" "$M/tests"
ok "미러 준비 완료 (pyproject·src·scripts·docs·tests 전체)"

step "2. A단계 — 이동 전: 스테이징본이 도구를 찾아 초록인가 (탐색 경로 = docs/)"
( cd "$M" && "$PY" -m pytest "$M/docs/qa/2026-09-16-followup/nx10/promote" -q 2>&1 | tail -4 )
if ( cd "$M" && "$PY" -m pytest "$M/docs/qa/2026-09-16-followup/nx10/promote" -q >/dev/null 2>&1 ); then
  ok "A단계 초록 (이동 전 기준선)"
else
  bad "A단계 실패 — 이동 전 스테이징본이 이미 빨갛다"
fi

step "3. B단계 — 이동 실행(미러 안). 본 트리와 **같은 명령**을 쓴다"
for pair in "${TOOL_MAP[@]}"; do
  src="$MIRROR_STAGING/${pair%%:*}"
  dst="$M/${pair##*:}"
  if [ ! -f "$src" ]; then
    bad "스테이징 도구 없음: ${pair%%:*}"
    continue
  fi
  mkdir -p "$(dirname "$dst")"
  mv "$src" "$dst" && ok "mv ${pair%%:*} → ${pair##*:}"
done
for pair in "${TEST_MAP[@]}"; do
  src="$MIRROR_STAGING/${pair%%:*}"
  dst="$M/${pair##*:}"
  if [ ! -f "$src" ]; then
    bad "스테이징 시험 없음: ${pair%%:*}"
    continue
  fi
  mv "$src" "$dst" && ok "mv ${pair%%:*} → ${pair##*:}"
done
# 이동 뒤 스테이징에 도구 사본이 남으면 두 주인이 생긴다(`scripts/` 우선이라 낡은 사본이 가려진다).
LEFT="$(find "$M/docs/qa/2026-09-16-followup" -name 'verify_docs_commands.py' -o -name 'collect_soak_result.py' -o -name 'cue_lexicon_probe.py' | wc -l | tr -d ' ')"
if [ "$LEFT" = "0" ]; then ok "스테이징에 도구 사본 0건(두 주인 없음)"; else bad "스테이징에 도구 사본 $LEFT 건이 남았다"; fi

step "4. B단계 — 이동 뒤 승격 위치에서 초록인가 (탐색 경로 = scripts/)"
( cd "$M" && "$PY" -m pytest "${TEST_FILES[@]}" -q 2>&1 | tail -4 )
if ( cd "$M" && "$PY" -m pytest "${TEST_FILES[@]}" -q >/dev/null 2>&1 ); then
  ok "B단계 초록 (승격 위치 scripts/ 에서 해석)"
else
  bad "B단계 실패 — 승격 뒤 시험이 빨갛다"
fi
# 건너뛴 것이 있다면 **이유를 보고에 남긴다** — 조용한 스킵은 "다 돌았다"로 읽힌다.
( cd "$M" && "$PY" -m pytest "${TEST_FILES[@]}" -rs -q 2>&1 | grep -E "^SKIPPED" | sed 's/^/  skip: /' | tail -3 )

step "5. 승격 게이트 전체 — 본실행과 ** 같은 함수**(gates.sh)를 미러에서 돌린다"
# 이 단계가 없어서 첫 본실행이 롤백됐다: 리허설은 ruff+pytest 만 보고, 본실행은 도구 자체
# 실행(`verify_docs_commands.py`)까지 본다. 게이트 정의를 공유하니 그 차이가 사라진다.
if promotion_gates "$M" "$PY" 2>&1 | sed 's/^/  /'; then
  ok "승격 게이트 전건 통과(미러)"
else
  bad "승격 게이트 실패(미러) — 본실행에서도 멈춘다. 위 실패 게이트를 먼저 고친다"
fi

step "6. C단계(이빨) — 도구를 치우면 그 시험이 **실패**하는가"
# 한 번에 하나씩 치운다 — "3개 다 지웠더니 빨갛다"는 어느 시험이 어느 도구에 물렸는지 말해주지 않는다.
# 비교 기준은 **제거 전 실제 실패 목록**이다("나머지는 초록"을 가정하면, 저장소가 이미 가진
# 다른 레인의 실패가 이빨 검사를 거짓으로 오염시킨다).
failures_of() { ( cd "$M" && "$PY" -m pytest "$@" -q 2>&1 | grep -E '^(FAILED|ERROR) ' | sort ); }
for idx in 0 1 2; do
  tool="$(basename "${TOOL_MAP[$idx]##*:}")"
  test_file="${TEST_FILES[$idx]}"
  others=()
  for other in "${TEST_FILES[@]}"; do
    [ "$other" = "$test_file" ] || others+=("$other")
  done
  before="$(failures_of "${others[@]}")"
  cp -a "$M/scripts/$tool" "$M/.backup-$tool"
  rm -f "$M/scripts/$tool"
  rm -rf "$M/scripts/__pycache__"
  if ( cd "$M" && "$PY" -m pytest "$test_file" -q >/dev/null 2>&1 ); then
    bad "$tool 제거 → $test_file 이 초록이다(시험이 자기 도구를 실제로 물지 않는다)"
  else
    ok "$tool 제거 → $test_file 실패(정상)"
  fi
  after="$(failures_of "${others[@]}")"
  if [ "$before" = "$after" ]; then
    ok "같은 조건에서 나머지 시험 실패 목록 불변(${before:+$(printf '%s' "$before" | wc -l | tr -d ' ')건} — 이빨이 옆 시험으로 번지지 않는다)"
  else
    bad "$tool 제거가 다른 시험에 영향을 줬다: 전 $before / 후 $after"
  fi
  mv "$M/.backup-$tool" "$M/scripts/$tool"
  rm -rf "$M/scripts/__pycache__"
done
ok "도구 3종 복원(해시 앞 8자: $(cd "$M" && shasum -a 256 scripts/verify_docs_commands.py scripts/collect_soak_result.py scripts/cue_lexicon_probe.py | awk '{print substr($1,1,8)}' | tr '\n' ' '))"

step "6b. 본실행 스크립트와 같은 표를 쓰는가(경로 일치 · 문법)"
# 첫 본실행이 스테이징 루트를 한 단계 잘못 잡아 이동 전 전제조건에서 멈췄다(이동 0건).
# 그 뒷부분을 여기서 직접 막는다: _본실행_ 이 계산하는 STAGING_ROOT 를 **그대로 물어본다_.
APPLY_STAGING="$(NX10_PROMOTE_REPO="$REPO" bash -c "source '$HERE/paths.sh' >/dev/null 2>&1; printf '%s' \"\$STAGING_ROOT\"")"
if [ "$APPLY_STAGING" = "$REPO/docs/qa/2026-09-16-followup" ]; then
  ok "본실행의 STAGING_ROOT 가 실제 스테이징 위치와 일치한다(${APPLY_STAGING#$REPO/})"
else
  bad "본실행의 STAGING_ROOT 가 틀렸다: '$APPLY_STAGING' (기대: $REPO/docs/qa/2026-09-16-followup)"
fi
if bash -n "$HERE/apply_promotion.sh"; then
  ok "본실행 스크립트 문법 OK"
else
  bad "본실행 스크립트에 문법 오류"
fi
# 표에 적힌 스테이징 파일 6건이 실제로 있는가(본실행의 전제조건과 같은 검사).
if promote_table_check >/dev/null 2>&1; then
  ok "이동표 6건이 본실행이 보는 위치에 있다"
else
  bad "이동표와 현실이 어긋난다: $(promote_table_check 2>&1 | head -2)"
fi

step "7. 결과"
# 출력 자체의 위생: bash 진단이 섮였는데 PASS 를 찍는 것은 이 리허설이 막으려는 바로 그 실패다.
NOISE="$(grep -nE "Permission denied|command not found|unbound variable|syntax error" "$SELFLOG" 2>/dev/null | grep -v "grep -nE" | head -3)"
if [ -n "$NOISE" ]; then
  bad "리허설 로그에 bash 진단이 섮였다(초록일 수 없다): $NOISE"
else
  ok "리허설 로그에 bash 진단 0건(자기 점검)"
fi
if [ "$fail" = "0" ]; then
  printf '  ALL PASS — 승격 절차가 미러에서 재현됐다. 본 트리 쓰기 0건.\n'
  printf '  이동 뒤 실행할 실제 명령: bash docs/qa/2026-09-16-followup/nx10/promote/apply_promotion.sh\n'
else
  printf '  FAIL %d건 — 계획(PROMOTION_PLAN.md)의 해당 단계를 고친 뒤 다시 돌린다.\n' "$fail"
fi
printf '  미러 트리는 감사용으로 남긴다: %s\n' "$M"
exit "$fail"
