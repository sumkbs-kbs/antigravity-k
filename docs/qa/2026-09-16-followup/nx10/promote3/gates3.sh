#!/usr/bin/env bash
# 승격 게이트(3차) — 리허설과 본실행이 **같은 함수**를 쓴다(`run_promoted_gates3 <루트> <py> <이빨>`).
#
# 무엇을 보는가:
#   A. 승격 위치에서 두 계약 시험이 초록이다(시험이 승격 위치를 먼저 탐색하므로 도구를 찾는다)
#   B. 세 도구를 **직접** 돌려도 초록이다(시험을 거치지 않는 경로도 산다) + 셸 문법 검사
#   C. 정적 게이트(ruff check · ruff format --check)를 통과한다 — `scripts/`·`tests/` 는 게이트가 지킨다
#   D. **이빨**: 도구 파일을 치우면 그 계약 시험이 **실패**한다(초록이 조용한 스킵이 아니다)
#      — D 는 리허설에서 미러로 수행하고 본실행에서는 하지 않는다(본 트리에서 파일을 치웠다 되돌리는
#        일은 위험 대비 이득이 없다. 리허설이 그 성질을 이미 증명한다).
#
# A 의 기록은 `promoted-contract-tests3.txt` 로 남긴다 — 통과가 게이트 리포트 안에만 묻히면
# 19분짜리 리포트를 끝까지 읽지 않은 사람에게는 확인이 없었던 것과 같다(2차 배치의 교훈).

# shellcheck shell=bash

run_promoted_gates3() {
  local root="$1"
  local py="$2"
  local with_teeth="${3:-no}"

  step "A. 승격 위치 계약 시험"
  local report="$HERE/promoted-contract-tests3.txt"
  local head_sha sha rc=0 out
  head_sha="$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  # `pytest | tail` 로 exit 를 받지 않는다: 파이프라인의 상태는 마지막 명령(tail)의 것이고,
  # `pipefail` 이 없는 셸에서 이 게이트는 **실패해도 초록**이 된다(2차 배치가 실제로 그랬다).
  out="$(cd "$root" && PYTHONDONTWRITEBYTECODE=1 "$py" -m pytest "${PROMOTED_TESTS[@]}" -v -p no:randomly 2>&1)" || rc=$?
  {
    echo "# 승격 위치 계약 시험 기록 (gates3.sh · A)"
    echo "실행: $(date -u +%Y-%m-%dT%H:%M:%SZ) · 루트: $root · HEAD: $head_sha"
    echo "명령: pytest ${PROMOTED_TESTS[*]} -v -p no:randomly"
    echo "대상 파일(승격 위치):"
    for sha in "${PROMOTED_TESTS[@]}"; do
      echo "  $sha (sha256 $(fingerprint_of "$root/$sha"))"
    done
    echo "대상 도구(승격 위치):"
    for sha in "${PROMOTED_SCRIPTS[@]}"; do
      echo "  $sha (sha256 $(fingerprint_of "$root/$sha"))"
    done
    echo "exit: $rc"
    echo "--- 출력 ---"
    printf '%s\n' "$out"
  } >"$report"
  printf '%s\n' "$out" | tail -3
  local passed_n failed_n node_first
  passed_n="$(printf '%s\n' "$out" | grep -oE '[0-9]+ passed' | tail -1)"
  failed_n="$(printf '%s\n' "$out" | grep -oE '[0-9]+ (failed|error[s]?)' | tail -1)"
  node_first="^${PROMOTED_TESTS[0]}::"
  {
    echo "판정: exit=$rc · ${passed_n:-passed 미검출} · ${failed_n:-실패 0} · 수집 노드 ${PROMOTED_TESTS[0]}:: $(printf '%s\n' "$out" | grep -cE "$node_first")"
  } >>"$report"
  if [[ "$rc" -eq 0 && -n "$passed_n" && -z "$failed_n" ]]; then
    ok "계약 시험 초록($passed_n) — 기록: ${report#"$root"/}"
  else
    bad "계약 시험 실패(exit $rc, ${passed_n:-passed 미검출} ${failed_n:-}) — 기록: ${report#"$root"/}"
  fi
  if printf '%s\n' "$out" | grep -qE "$node_first"; then
    ok "수집 경로가 승격 위치다(tests/ 의 노드로 실행됨)"
  else
    bad "노드 id 가 승격 위치가 아니다 — 스테이징 사본을 보고 있을 수 있다"
  fi

  step "B. 도구 직접 실행"
  # 도구마다 “살아 있음을 증명하는 최소 명령”을 돌린다(자기시험은 스스로 문을 확인한다).
  if (cd "$root" && PYTHONDONTWRITEBYTECODE=1 "$py" scripts/soak_watch.py --selftest >/dev/null 2>&1); then
    ok "scripts/soak_watch.py --selftest exit 0"
  else
    bad "scripts/soak_watch.py --selftest 실패"
  fi
  if (cd "$root" && PYTHONDONTWRITEBYTECODE=1 "$py" scripts/soak_watch_loop.py --selftest >/dev/null 2>&1); then
    ok "scripts/soak_watch_loop.py --selftest exit 0"
  else
    bad "scripts/soak_watch_loop.py --selftest 실패"
  fi
  if (cd "$root" && bash -n scripts/soak_control.sh); then
    ok "scripts/soak_control.sh 문법 검사(bash -n) 통과"
  else
    bad "scripts/soak_control.sh 문법 검사 실패"
  fi
  # 통제 도구의 자기시험은 수명주기(arm/cancel/run/harvest)를 임시 루트에서 돈다 — **위치가 바뀌어도**
  # 승격 위치에서 같은 결론이 나는지 여기서 한 번 더 본다(A 는 시험을 통해 돌린 것). 출력은 **전문**을
  # 남긴다: 이 행렬은 “더러운 트리에서 귀속 항목을 생략했고 그 사실을 밝혔다” 를 품고, 통과했다는 한 줄만
  # 남으면 그 문장이 사라진다(그 문장이 이 배치에서 고친 결함의 증거다). `tail | grep` 으로 판정하면
  # 파이프 상태가 tail 의 것이 되어 **실패해도 초록**이 될 수 있다 — exit 를 직접 받는다.
  local st_out st_rc=0
  st_out="$(cd "$root" && NX10_PREFLIGHT_SKIP_THROUGHPUT=1 bash scripts/soak_control.sh selftest 2>&1)" || st_rc=$?
  {
    echo "# 승격 위치 자기시험 전문 (gates3.sh · B)"
    echo "실행: $(date -u +%Y-%m-%dT%H:%M:%SZ) · 루트: $root · 도구 sha256 $(fingerprint_of "$root/scripts/soak_control.sh")"
    echo "exit: $st_rc"
    echo "--- 출력 ---"
    printf '%s\n' "$st_out"
  } >"$HERE/promoted-selftest3.txt"
  if [[ "$st_rc" -eq 0 ]] && ! printf '%s\n' "$st_out" | grep -q "\[FAIL\]" \
    && printf '%s\n' "$st_out" | grep -q "SOAK_CONTROL_SELFTEST: "; then
    ok "scripts/soak_control.sh selftest 통과(승격 위치에서) — 기록: promoted-selftest3.txt"
  else
    bad "scripts/soak_control.sh selftest 실패(승격 위치에서, exit $st_rc)"
  fi

  step "C. 정적 게이트"
  local pys=("scripts/soak_watch.py" "scripts/soak_watch_loop.py" "${PROMOTED_TESTS[@]}")
  if (cd "$root" && "$py" -m ruff check "${pys[@]}" >/dev/null 2>&1); then
    ok "ruff check 통과"
  else
    bad "ruff check 실패"
  fi
  if (cd "$root" && "$py" -m ruff format --check "${pys[@]}" >/dev/null 2>&1); then
    ok "ruff format --check 통과"
  else
    bad "ruff format --check 실패"
  fi

  if [[ "$with_teeth" == "yes" ]]; then
    _gates3_teeth "$root" "$py"
  fi
}

# 이빨: 도구를 치우면 계약 시험이 **실패해야** 한다. 실패하지 않으면 빈 껍데기다.
_gates3_teeth() {
  local root="$1"
  local py="$2"
  local pair tool test hidden rc
  for pair in "${TEETH_PAIRS[@]}"; do
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
