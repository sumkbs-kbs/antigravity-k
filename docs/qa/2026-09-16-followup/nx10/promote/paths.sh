#!/usr/bin/env bash
# NX-10 승격 **이동표와 경로** — 본실행(`apply_promotion.sh`)과 리허설(`dry_run_promotion.sh`)이
# 이 파일을 **source** 해서 같은 값을 쓴다.
#
# 왜 파일로 뽑았는가: 첫 본실행이 `NXF` 오산(`../../..` vs `../..`)으로 즉시 멈췄다. 리허설은
# 경로를 **하드코딩**해서 통과했으므로 **다른 스크립트를 검증한 셈**이었고, 드리프트는 본실행에서
# 처음 드러났다(다행히 이동 전 전제조건에서). 표를 둘로 두면 같은 일이 반복된다 — 하나만 둔다.
#
# 사용:
#   source "$(dirname "$0")/paths.sh"
#   NX10_PROMOTE_REPO=<트리> 로 저장소를 바꿀 수 있다(리허설 검증용).

_PROMOTE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMOTE_DIR="$_PROMOTE_DIR"
REPO="${NX10_PROMOTE_REPO:-$(git -C "$PROMOTE_DIR" rev-parse --show-toplevel)}"
# 스테이징 루트 = `docs/qa/2026-09-16-followup`   (promote → nx10 → 2026-09-16-followup)
STAGING_ROOT="$(cd "$PROMOTE_DIR/../.." && pwd)"

# 이동표: 스테이징 루트 기준 상대경로 → 저장소 루트 기준 상대경로
TOOL_MAP=(
  "nx10/verify_docs_commands.py:scripts/verify_docs_commands.py"
  "nx10/collect_soak_result.py:scripts/collect_soak_result.py"
  "nx01/cue_lexicon_probe.py:scripts/cue_lexicon_probe.py"
)
TEST_MAP=(
  "nx10/promote/test_docs_toolchain_contract.py:tests/test_docs_toolchain_contract.py"
  "nx10/promote/test_soak_recovery_judge.py:tests/test_soak_recovery_judge.py"
  "nx10/promote/test_cue_lexicon_contract.py:tests/test_cue_lexicon_contract.py"
)
TEST_FILES=(tests/test_docs_toolchain_contract.py tests/test_soak_recovery_judge.py tests/test_cue_lexicon_contract.py)

# 표의 스테이징 쪽 파일이 실제로 있는가 — 없으면 조용히 넘어가지 않는다(이동표와 현실의 대조).
promote_table_check() {
  local missing=0 pair src
  for pair in "${TOOL_MAP[@]}" "${TEST_MAP[@]}"; do
    src="$STAGING_ROOT/${pair%%:*}"
    if [ ! -f "$src" ]; then
      echo "  [STOP] 스테이징 원본 없음: $src (STAGING_ROOT=$STAGING_ROOT)"
      missing=$((missing + 1))
    fi
  done
  [ "$missing" = "0" ] || return 1
  return 0
}
