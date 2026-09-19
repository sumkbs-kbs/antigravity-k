#!/usr/bin/env bash
# NX-10 승격 **게이트 집합** — 본실행(`apply_promotion.sh`)과 리허설(`dry_run_promotion.sh`)이
# **같은 함수**를 부른다.
#
# 왜 파일로 뽑았는가: 첫 본실행이 게이트 4-4(`verify_docs_commands.py` 자체 실행)에서 멈췄는데,
# 리허설은 그 게이트를 **돌리지 않았다** — 그래서 리허설은 ALL PASS 였고 본실행은 롤백됐다.
# 리허설이 본실행과 다른 게이트를 돌리면 그 차이가 곧 사각지대다. 표(`paths.sh`)와 같은 이유로
# 게이트도 하나만 둔다.
#
# 사용:
#   source "$(dirname "$0")/paths.sh"
#   source "$(dirname "$0")/gates.sh"
#   promotion_gates "$REPO" "$REPO/.venv/bin/python"   # 0 = 전부 통과
#
# 게이트는 **승격 뒤 트리**를 전제로 한다(`scripts/…`, `tests/…`). 그래서 리허설은 이동 뒤에,
# 본실행은 이동 직후에 부른다 — 같은 경로·같은 명령이 된다.

# 승격이 만드는 파일 6종(트리 루트 기준).
PROMOTED_FILES=(
  scripts/verify_docs_commands.py
  scripts/collect_soak_result.py
  scripts/cue_lexicon_probe.py
  tests/test_docs_toolchain_contract.py
  tests/test_soak_recovery_judge.py
  tests/test_cue_lexicon_contract.py
)

_pg_last_output=""

_pg_show() {
  # 실패했을 때만 꼬리를 보여준다 — 초록 로그는 짧게, 빨강 로그는 원인이 보이게.
  [ -n "$_pg_last_output" ] && printf '%s\n' "$_pg_last_output" | tail -6 | sed 's/^/      /'
  return 0
}

_pg_step() {
  printf '\n  [%s] %s\n' "$1" "$2"
}

# ── 게이트 1: ruff check ────────────────────────────────────────────────────
pg_ruff_check() {
  local root="$1" py="$2"
  _pg_step "1" "ruff check (${#PROMOTED_FILES[@]}개 파일) — 승격 위치가 정적 게이트에 들어왔는가"
  if _pg_last_output="$(cd "$root" && "$py" -m ruff check "${PROMOTED_FILES[@]}" 2>&1)"; then
    printf '      OK: %s\n' "$(printf '%s' "$_pg_last_output" | tail -1)"
    return 0
  fi
  _pg_show
  return 1
}

# ── 게이트 2: ruff format --check ───────────────────────────────────────────
pg_ruff_format() {
  local root="$1" py="$2"
  _pg_step "2" "ruff format --check — CI 의 정적 게이트 두 번째"
  if _pg_last_output="$(cd "$root" && "$py" -m ruff format --check "${PROMOTED_FILES[@]}" 2>&1)"; then
    printf '      OK: %s\n' "$(printf '%s' "$_pg_last_output" | tail -1)"
    return 0
  fi
  _pg_show
  return 1
}

# ── 게이트 3: 승격된 계약 시험 ──────────────────────────────────────────────
pg_contract_tests() {
  local root="$1" py="$2"
  _pg_step "3" "계약 시험 3파일 — 도구를 승격 위치에서 찾아 해석하는가"
  if _pg_last_output="$(cd "$root" && "$py" -m pytest tests/test_docs_toolchain_contract.py \
    tests/test_soak_recovery_judge.py tests/test_cue_lexicon_contract.py -q 2>&1)"; then
    printf '      OK: %s\n' "$(printf '%s' "$_pg_last_output" | grep -E 'passed|xfailed' | tail -1)"
    return 0
  fi
  _pg_show
  return 1
}

# ── 게이트 4: 검사기 자체 실행(자기 위치 가정을 실제로 밟는다) ──────────────
pg_docs_tool() {
  local root="$1" py="$2"
  _pg_step "4" "verify_docs_commands.py 자체 실행 — 자기 파일 위치의 깊이에 의존하지 않는가"
  # 이 게이트가 첫 본실행을 롤백시켰다: 검사기가 `parents[4]` 로 저장소를 잡고 있었고,
  # `scripts/` 로 옮기자 `/Users/…/program` 을 저장소로 믿어 .gitignore 를 못 찾았다.
  # 그래서 여기서 **도구를 직접 돌린다**(시험이 부르는 것과 별개로, CLI 경로도 밟는다).
  if _pg_last_output="$(cd "$root" && "$py" "$root/scripts/verify_docs_commands.py" 2>&1)"; then
    printf '      OK: %s\n' "$(printf '%s' "$_pg_last_output" | grep -E '^결과' | tail -1)"
    return 0
  fi
  _pg_show
  return 1
}

# ── 게이트 5: 회수 판정기 자기시험 + 증거 경로 ──────────────────────────────
pg_soak_judge() {
  local root="$1" py="$2"
  _pg_step "5" "collect_soak_result.py --selftest + 회수 기록 경로가 증거 디렉터리인가"
  if ! _pg_last_output="$(cd "$root" && "$py" "$root/scripts/collect_soak_result.py" --selftest 2>&1)"; then
    _pg_show
    return 1
  fi
  printf '      OK: %s\n' "$(printf '%s' "$_pg_last_output" | grep -cE '\[OK' | tr -d ' ')개 자기시험 통과"
  # 승격 뒤에도 회수 기록이 `scripts/` 가 아니라 증거 디렉터리에 쓰여야 한다.
  if ! _pg_last_output="$(cd "$root" && "$py" -c "
import os, sys, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('judge', r'$root/scripts/collect_soak_result.py')
sys.modules[spec.name] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules[spec.name])
print(sys.modules['judge'].OUT)
" 2>&1)"; then
    _pg_show
    return 1
  fi
  case "$_pg_last_output" in
    *docs/qa/2026-09-16-followup/nx10*)
      printf '      OK: OUT = %s\n' "$(printf '%s' "$_pg_last_output" | tail -1)"
      return 0
      ;;
    *)
      printf '      FAIL: OUT 이 증거 디렉터리가 아니다: %s\n' "$_pg_last_output"
      return 1
      ;;
  esac
}

# ── 게이트 6: 측정기 자체 실행 ──────────────────────────────────────────────
pg_cue_probe() {
  local root="$1" py="$2"
  _pg_step "6" 'cue_lexicon_probe.py 자체 실행 — 승격 위치에서 antigravity_k 를 찾고 돈다'
  if _pg_last_output="$(cd "$root" && "$py" "$root/scripts/cue_lexicon_probe.py" 2>&1)"; then
    printf '      OK: %s\n' "$(printf '%s' "$_pg_last_output" | head -1)"
    return 0
  fi
  _pg_show
  return 1
}

# ── 게이트 7: 승격 파일 6종이 실제로 그 위치에 있는가 ──────────────────────
pg_files_present() {
  local root="$1"
  _pg_step "7" "승격 파일 6종이 대상 위치에 있다(사본·누락 0건)"
  local missing=() f
  for f in "${PROMOTED_FILES[@]}"; do
    [ -f "$root/$f" ] || missing+=("$f")
  done
  if [ "${#missing[@]}" -eq 0 ]; then
    printf '      OK: %d개 확인\n' "${#PROMOTED_FILES[@]}"
    return 0
  fi
  printf '      FAIL: 없는 파일: %s\n' "${missing[*]}"
  return 1
}

# ── 전체 게이트 ─────────────────────────────────────────────────────────────
# 성공하면 마지막 줄에 `PROMOTION_GATES: n/n passed` 를 출력하고 0 을 돌려준다.
promotion_gates() {
  local root="$1" py="$2"
  local total=0 passed=0 gate
  printf '\n=== 승격 게이트 (root=%s) ===\n' "$root"
  for gate in pg_ruff_check pg_ruff_format pg_contract_tests pg_docs_tool pg_soak_judge pg_cue_probe pg_files_present; do
    total=$((total + 1))
    if "$gate" "$root" "$py"; then
      passed=$((passed + 1))
    fi
  done
  printf '\n  PROMOTION_GATES: %d/%d passed\n' "$passed" "$total"
  [ "$passed" = "$total" ]
}
