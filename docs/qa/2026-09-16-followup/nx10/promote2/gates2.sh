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
  if (cd "$root" && PYTHONDONTWRITEBYTECODE=1 "$py" -m pytest "${PROMOTED_TESTS[@]}" -q -p no:randomly 2>&1 | tail -3); then
    ok "계약 시험 초록(승격 위치에서 탐색됨)"
  else
    bad "계약 시험 실패 — 승격 위치에서 도구를 못 찾거나 판정이 달라졌다"
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
