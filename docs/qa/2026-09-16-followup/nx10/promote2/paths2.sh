#!/usr/bin/env bash
# 승격 2차 배치 — **이동표**(리허설과 본실행이 같은 파일에서 읽는다. 하드코딩하면 리허설이
# 다른 스크립트를 검증하게 된다 — 1차 배치가 그 함정을 실제로 밟았다).
#
# 왜 옮기는가: 이 도구들은 `docs/` 안에 있어 **어떤 게이트도 지키지 않는다**(정적 검사는
# `src/ tests/ scripts/`, 시험 스위트는 `tests/` 만 본다). 오늘 리허설이 카드의 마지막 미완
# 항목을 닫았는데, 계약이 `docs/` 에 있으면 그 판정식이 낡아도 아무도 모른다.
#
# 배치(스테이징 → 승격 위치):
#   1. nx01/restore_rehearsal.py      → scripts/restore_rehearsal.py
#   2. nx03/rollback_rehearsal.py     → scripts/rollback_rehearsal.py
#   3. promote2/test_restore_rehearsal_contract.py  → tests/test_restore_rehearsal_contract.py
#   4. promote2/test_rollback_rehearsal_contract.py → tests/test_rollback_rehearsal_contract.py
#
# 증거 텍스트(`*-rehearsal-output.txt`)는 **옮기지 않는다** — raw artifact 는 `docs/` 가 소유한다
# (1차 배치가 검사기·판정기·프로브를 옮기고 raw 출력은 `docs/` 에 남긴 것과 같다).

REPO="${NX10_REPO:-/Users/mr.k/program/coding/ssak_comp/Ssak-Ai}"
STAGING="docs/qa/2026-09-16-followup"

# "스테이징상대경로:승격상대경로"
MOVE_PAIRS=(
  "$STAGING/nx01/restore_rehearsal.py:scripts/restore_rehearsal.py"
  "$STAGING/nx03/rollback_rehearsal.py:scripts/rollback_rehearsal.py"
  "$STAGING/nx10/promote2/test_restore_rehearsal_contract.py:tests/test_restore_rehearsal_contract.py"
  "$STAGING/nx10/promote2/test_rollback_rehearsal_contract.py:tests/test_rollback_rehearsal_contract.py"
)

# 리허설에서 미러로 가져갈 **작업 트리 파일**(클론은 커밋된 내용만 준다 — 스테이징은 아직 미커밋이다).
# 왜 “전체 복사”가 아닌가: 이 기기의 rsync 는 openrsync 2.6.9 이고, 작업 트리 안의
# 비UTF-8 이름(`.tmp/agk-lock-*/data/search_cache/*.json`)에서 `Illegal byte sequence` 로 죽어
# **복사가 통째로 중단**됐다(실측: 미러에 커밋된 내용만 남아 리허설이 다른 것을 검증했다 —
# 이 배치가 건드리는 파일만 정확히 가져오는 편이 빠르고 정직하다).
COPY_PATHS=(
  "$STAGING/nx01/restore_rehearsal.py"
  "$STAGING/nx01/restore-rehearsal-output.txt"
  "$STAGING/nx03/rollback_rehearsal.py"
  "$STAGING/nx03/rollback-rehearsal-output.txt"
  "$STAGING/nx10/promote2"
)

# 승격 뒤 시험 스위트가 **옛 자리를 더 이상 보지 않아야** 한다(중복 사본이 생기면 낡은 쪽이 가려진다).
PROMOTED_SCRIPTS=("scripts/restore_rehearsal.py" "scripts/rollback_rehearsal.py")
PROMOTED_TESTS=("tests/test_restore_rehearsal_contract.py" "tests/test_rollback_rehearsal_contract.py")

step() { printf '\n=== %s ===\n' "$1"; }
ok() { printf '  [OK  ] %s\n' "$1"; }
bad() {
  printf '  [FAIL] %s\n' "$1"
  fail=$((fail + 1))
}

# 이동표의 sha256(앞 12자) — 증거 기록과 “같은 바이트를 옮겼는가” 확인에 쓴다.
fingerprint_of() {
  python3 - "$1" <<'PY'
import hashlib, sys, pathlib
path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.is_file() else "MISSING")
PY
}
