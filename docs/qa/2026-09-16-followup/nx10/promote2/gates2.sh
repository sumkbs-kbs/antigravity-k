#!/usr/bin/env bash
# 승격 게이트 — 리허설과 본실행이 **같은 함수**를 쓴다(`run_promoted_gates <루트>`).
#
# 무엇을 보는가:
#   A. 승격 위치에서 두 계약 시험이 초록이다(시험이 승격 위치를 먼저 탐색하므로 도구를 찾는다)
#   B. 두 도구를 **직접** 돌려도 초록이다(시험을 거치지 않는 경로도 산다)
#   C. 정적 게이트(ruff check · ruff format --check)를 통과한다 — `scripts/`·`tests/` 는 게이트가 지킨다
#   D. **이빨**: 도구 파일을 치우면 그 계약 시험이 **실패**한다(초록이 조용한 스킵이 아니다)
#      — D 는 리허설에서는 미러에서 실제로 수행하고, 본실행에서는 **하지 않는다**(본 트리에서 파일을
#        치웠다 되돌리는 일은 위험 대비 이득이 없다. 리허설이 그 성질을 이미 증명한다).

# shellcheck shell=bash

run_promoted_gates() {
  local root="$1"
  local py="$2"
  local with_teeth="${3:-no}"

  step "A. 승격 위치 계약 시험"
  # 기록을 남긴다 — 오너 요청(“승격된 위치에서 전부 통과하는지 확인”)의 산출물이 게이트 리포트
  # 안에만 묻혀 있으면, 16분짜리 게이트를 끝까지 읽지 않은 사람에게는 확인이 없었던 것과 같다.
  local report="$HERE/promoted-contract-tests.txt"
  local head_sha sha line rc=0 out
  head_sha="$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  # `pytest | tail` 로 exit 를 받지 않는다: 파이프라인의 상태는 마지막 명령(tail)의 것이고,
  # `pipefail` 이 없는 셸에서 이 게이트는 조용히 초록이 된다 — 이 카드가 계속 쫓는 “조용한 초록”이다.
  out="$(cd "$root" && PYTHONDONTWRITEBYTECODE=1 "$py" -m pytest "${PROMOTED_TESTS[@]}" -v -p no:randomly 2>&1)" || rc=$?
  {
    echo "# 승격 위치 계약 시험 기록 (gates2.sh · A)"
    echo "실행: $(date -u +%Y-%m-%dT%H:%M:%SZ) · 루트: $root · HEAD: $head_sha"
    echo "명령: pytest ${PROMOTED_TESTS[*]} -v -p no:randomly"
    echo "대상 파일(승격 위치):"
    for sha in "${PROMOTED_TESTS[@]}"; do
      echo "  $sha (sha256 $(fingerprint_of "$root/$sha"))"
    done
    echo "exit: $rc"
    echo "--- 출력 ---"
    printf '%s\n' "$out"
  } >"$report"
  printf '%s\n' "$out" | tail -3
  # 수집된 노드가 전부 승격 위치인지 + 실제로 통과했는지(0건 수집은 초록이 아니다).
  # 주의: 변수 확장을 하려면 패턴을 큰따옴표로 써야 한다(작은따옴표로 썼다가 첫 시도가 거짓 FAIL 을 냈다).
  line="$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -1)"
  local failed_n node_first
  failed_n="$(printf '%s\n' "$out" | grep -oE '[0-9]+ (failed|error[s]?)' | tail -1)"
  node_first="^${PROMOTED_TESTS[0]}::"
  {
    echo "판정: exit=$rc · ${line:-passed 미검출} · ${failed_n:-실패 0} · 수집 노드 ${PROMOTED_TESTS[0]}:: $(printf '%s\n' "$out" | grep -cE "$node_first")"
  } >>"$report"
  if [[ "$rc" -eq 0 && -n "$line" && -z "$failed_n" ]]; then
    ok "계약 시험 초록($line) — 기록: ${report#$root/}"
  else
    bad "계약 시험 실패(exit $rc, ${line:-passed 미검출} ${failed_n:-}) — 기록: ${report#$root/}"
  fi
  if printf '%s\n' "$out" | grep -qE "$node_first"; then
    ok "수집 경로가 승격 위치다(tests/ 의 노드로 실행됨)"
  else
    bad "노드 id 가 승격 위치가 아니다 — 스테이징 사본을 보고 있을 수 있다"
  fi

  step "B. 도구 직접 실행"
  local tool
  for tool in "${PROMOTED_SCRIPTS[@]}"; do
    if (cd "$root" && PYTHONDONTWRITEBYTECODE=1 "$py" "$tool" >/dev/null 2>&1); then
      ok "$tool exit 0"
    else
      bad "$tool 이 실패했다"
    fi
  done

  step "C. 정적 게이트"
  if (cd "$root" && "$py" -m ruff check "${PROMOTED_SCRIPTS[@]}" "${PROMOTED_TESTS[@]}" >/dev/null 2>&1); then
    ok "ruff check 통과"
  else
    bad "ruff check 실패"
  fi
  if (cd "$root" && "$py" -m ruff format --check "${PROMOTED_SCRIPTS[@]}" "${PROMOTED_TESTS[@]}" >/dev/null 2>&1); then
    ok "ruff format --check 통과"
  else
    bad "ruff format --check 실패"
  fi

  if [[ "$with_teeth" == "yes" ]]; then
    _gates_teeth "$root" "$py"
  fi
}

# 이빨: 도구를 치우면 계약 시험이 **실패해야** 한다. 실패하지 않으면 그 시험은 스킵하는 빈 껍데기다.
_gates_teeth() {
  local root="$1"
  local py="$2"
  local pairs=(
    "scripts/restore_rehearsal.py:tests/test_restore_rehearsal_contract.py"
    "scripts/rollback_rehearsal.py:tests/test_rollback_rehearsal_contract.py"
  )
  local pair tool test hidden rc
  for pair in "${pairs[@]}"; do
    tool="${pair%%:*}"
    test="${pair##*:}"
    hidden="$tool.hidden"
    step "D. 이빨 — $test 는 $tool 없이 실패해야 한다"
    mv "$root/$tool" "$root/$hidden"
    rc=0
    (cd "$root" && PYTHONDONTWRITEBYTECODE=1 "$py" -m pytest "$test" -q -p no:randomly >/dev/null 2>&1) || rc=$?
    mv "$root/$hidden" "$root/$tool"
    if [[ "$rc" -ne 0 ]]; then
      ok "도구 없으면 실패한다(exit $rc) — 조용한 스킵이 아니다"
    else
      bad "도구가 없는데도 초록이다 — 시험이 승격되지 않은 사본을 보고 있다"
    fi
  done
}
