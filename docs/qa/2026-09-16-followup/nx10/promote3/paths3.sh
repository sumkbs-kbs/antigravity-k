#!/usr/bin/env bash
# 승격 3차 배치 — **이동표**(리허설과 본실행이 같은 파일에서 읽는다. 하드코딩하면 리허설이
# 다른 것을 검증하게 된다 — 1차 배치가 그 함정을 실제로 밟았다).
#
# 왜 옮기는가: 이 도구들은 `docs/` 안에 있어 **어떤 게이트도 지키지 않는다**(정적 검사는
# `src/ tests/ scripts/`, 스위트는 `tests/` 만 본다). 그런데 이 셋은 오늘 밤 내내 판단을 내렸다 —
# 조기 경보가 실행을 살렸고, 통제 도구는 프로세스를 죽이고 예약을 걸고 회수를 판정한다.
# 판정식이 `docs/` 에 있는 동안 그 셋이 틀리면 아무도 모른다(오늘 세 번 틀렸고 매번 사람이 알아챘다).
#
# 배치(스테이징 → 승격 위치):
#   1. nx10/soak_watch.py        → scripts/soak_watch.py        (조기 경보 판정식)
#   2. nx10/soak_watch_loop.py   → scripts/soak_watch_loop.py   (상시 감시 + 라이브 화면)
#   3. nx10/soak_control.sh      → scripts/soak_control.sh      (예약·실행·취소·회수 통제)
#   4. promote3/test_soak_watch_contract.py   → tests/test_soak_watch_contract.py
#   5. promote3/test_soak_control_contract.py → tests/test_soak_control_contract.py
#
# 옮기지 **않는** 것: 이 레인의 러너(`run_nx10_soak.sh`·`run_freeze_gates.sh`·`run_promote_gates.sh`)와
# 증거 파일. 러너는 “이 카드의 회차”를 만드는 도구라 카드와 함께 사는 편이 맞고, 증거는 `docs/` 가 소유한다.
# 다음 배치 후보로 §1b 에 남긴다.
#
# 승격 위치에서도 파생물(이력·화면·잠금)은 **카드 레인 디렉터리**에 쓴다 — 도구 위치와 증거 위치는
# 다를 수 있다(도구들이 `NX10_OUT` 을 그렇게 계산한다).

REPO="${NX10_REPO:-/Users/mr.k/program/coding/ssak_comp/Ssak-Ai}"
STAGING="docs/qa/2026-09-16-followup"

# "스테이징상대경로:승격상대경로"
MOVE_PAIRS=(
  "$STAGING/nx10/soak_watch.py:scripts/soak_watch.py"
  "$STAGING/nx10/soak_watch_loop.py:scripts/soak_watch_loop.py"
  "$STAGING/nx10/soak_control.sh:scripts/soak_control.sh"
  "$STAGING/nx10/promote3/test_soak_watch_contract.py:tests/test_soak_watch_contract.py"
  "$STAGING/nx10/promote3/test_soak_control_contract.py:tests/test_soak_control_contract.py"
)

# 리허설에서 미러로 가져갈 **작업 트리 파일**(클론은 커밋된 내용만 준다 — 스테이징은 아직 미커밋이다).
# `rsync -a` 를 쓰지 않는 이유는 2차 배치와 같다: 이 기기의 rsync 는 openrsync 이고 작업 트리 안의
# 비UTF-8 이름에서 죽어 **복사가 통째로 중단**된다(그때 리허설이 다른 것을 검증했다).
COPY_PATHS=(
  "$STAGING/nx10/soak_watch.py"
  "$STAGING/nx10/soak_watch_loop.py"
  "$STAGING/nx10/soak_control.sh"
  "$STAGING/nx10/promote3"
)

# 승격 뒤 시험 스위트가 **옛 자리를 더 이상 보지 않아야** 한다(중복 사본이 생기면 낡은 쪽이 가려진다).
PROMOTED_SCRIPTS=("scripts/soak_watch.py" "scripts/soak_watch_loop.py" "scripts/soak_control.sh")
PROMOTED_TESTS=("tests/test_soak_watch_contract.py" "tests/test_soak_control_contract.py")
# 이빨(도구를 치우면 그 시험이 실패해야 한다) 쌍 — 승격 계약이 조용한 스킵이 아님을 증명한다.
TEETH_PAIRS=(
  "scripts/soak_watch.py:tests/test_soak_watch_contract.py"
  "scripts/soak_watch_loop.py:tests/test_soak_watch_contract.py"
  "scripts/soak_control.sh:tests/test_soak_control_contract.py"
)

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
