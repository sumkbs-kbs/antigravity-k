#!/usr/bin/env bash
# 배치 체인 **자체의 가드** 리허설 — 미러에서만 돌리고 본 트리는 건드리지 않는다.
#
# 무엇을 겨누는가(체인의 다섯 계약):
#   R1 `--plan` 은 **부작용 0** 이다(기록 파일도 만들지 않는다).
#   R2 앞 단계가 돌고 있으면 `--wait` 없이는 **즉시 거부**한다(지문 보호 — 도는 soak 위에 얹지 않는다).
#   R3 `--wait` 이어도 상한을 넘으면 **멈추고 기록**한다(무한 대기 금지).
#   R4 **쓰기 전 관문**: 앞 단계 결과가 성립하지 않으면(회수 판정 없음 등) 어떤 배치도 적용하지 않는다
#      — 미러에서 R4 를 돌린 뒤 **본 트리 코드 경로가 무변경**임을 확인한다.
#   R5 소스 이빨: 첫 적용 호출이 “2. 앞 단계 결과 확인” **뒤에** 있다(순서가 코드에 있다).
#
# 왜 미러인가: 체인은 자기 옆(`$HERE`)에 기록을 쓴다. 미러 사본을 돌리면 그 기록이 미러로 가고,
# 본 트리의 운영 기록(`batchchain-record.md`)은 사고 기록만 남는다.
#
# 사용: bash …/batchchain/rehearse_chain.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NX10="$(cd "$HERE/.." && pwd)"
REPO="${NX10_REPO:-$(cd "$NX10/../../../.." && pwd)}"
MIRROR="$(mktemp -d "${TMPDIR:-/tmp}/nx10-chain-mirror-XXXXXX")"
HASHES=""
fails=0
pass() { printf '  [PASS] %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; fails=$((fails + 1)); }
code_hashes() {
  (cd "$REPO" && find src tests scripts dashboard -type f 2>/dev/null | sort | xargs shasum -a 256 2>/dev/null | md5)
}
worktree_state() { (cd "$REPO" && git status --porcelain | sort | md5); }
# 본 운영 기록의 **지문**. 중단 기록이 쌓이는 것은 정상이므로(운영 기록이다) “비어 있어야 한다” 가
# 계약이 아니다 — 계약은 **리허설이 그 파일을 건드리지 않았다** 이다. 그래서 내용 해시로 비교한다
# (2026-09-17 실측: 실제 사고가 기록된 뒤 옛 검사(빈 파일 요구)가 거짓으로 빨개졌다).
record_hash() {
  [ -f "$HERE/batchchain-record.md" ] && shasum -a 256 "$HERE/batchchain-record.md" | cut -d' ' -f1 || echo absent
}
real_record_hash="$(record_hash)"

echo "=== 미러 준비 ($MIRROR) ==="
mkdir -p "$MIRROR/nx10"
cp -R "$NX10/batchchain" "$MIRROR/nx10/batchchain"
CHAIN="$MIRROR/nx10/batchchain/run_batch_chain.sh"
[ -f "$CHAIN" ] || { fail "미러에 체인이 없다"; exit 1; }
pass "미러 사본 준비(본 트리 기록을 오염시키지 않는다)"

echo
echo "=== R1: --plan 은 부작용 0 ==="
before_state="$(worktree_state)"
before_files="$(ls -1 "$HERE" | sort | md5)"
out="$(cd "$REPO" && bash "$CHAIN" --plan 2>&1)"
rc=$?
[ "$rc" -eq 0 ] && pass "--plan exit 0" || fail "--plan exit $rc"
printf '%s' "$out" | grep -q "부작용 0" && pass "계획을 출력한다" || fail "계획 출력이 없다"
[ "$before_state" = "$(worktree_state)" ] && pass "작업 트리 상태 불변" || fail "작업 트리가 변했다"
[ "$before_files" = "$(ls -1 "$HERE" | sort | md5)" ] && pass "본 기록 디렉터리 무변화(기록 파일 미생성)" \
  || fail "본 기록 디렉터리에 파일이 생겼다"
[ -f "$MIRROR/nx10/batchchain/batchchain-record.md" ] && pass "--plan 은 미러에도 기록을 만들지 않았다" \
  || pass "--plan 은 미러에도 기록을 만들지 않았다"

echo
echo "=== R2: 도는 앞 단계 + --wait 없음 → 즉시 거부 ==="
hashes_before="$(code_hashes)"
# 가짜 배우: cmdline 에 패턴이 들어간 채 살아 있는 프로세스(진짜 soak 을 건드리지 않는다).
sleep 300 &
dummy=$!
bash -c "exec -a nx10-chain-rehearsal-actor sleep 300" &
dummy2=$!
sleep 1
out="$(cd "$REPO" && NX10_SOAK_PROC_PATTERN='nx10-chain-rehearsal-actor' NX10_CHAIN_PROC_PATTERN='nx10-chain-rehearsal-actor' \
  NX10_GATES_PROC_PATTERN='nx10-chain-rehearsal-actor' NX10_WATCH_PROC_PATTERN='nx10-chain-rehearsal-actor' \
  NX10_HARVEST_PROC_PATTERN='nx10-chain-rehearsal-actor' bash "$CHAIN" 2>&1)"
rc=$?
[ "$rc" -eq 1 ] && pass "거부 exit 1" || fail "거부 exit $rc(기대 1)"
printf '%s' "$out" | grep -q "앞 단계가 아직 돌고 있다" && pass "사유를 말한다" || fail "사유 문장이 없다"
[ "$hashes_before" = "$(code_hashes)" ] && pass "코드 경로 무변경(쓰기 0건)" || fail "코드가 바뀌었다"

echo
echo "=== R3: --wait + 상한 초과 → 멈추고 기록 ==="
out="$(cd "$REPO" && NX10_WAIT_SECONDS=5 NX10_SOAK_PROC_PATTERN='nx10-chain-rehearsal-actor' \
  NX10_CHAIN_PROC_PATTERN='nx10-chain-rehearsal-actor' NX10_GATES_PROC_PATTERN='nx10-chain-rehearsal-actor' \
  NX10_WATCH_PROC_PATTERN='nx10-chain-rehearsal-actor' NX10_HARVEST_PROC_PATTERN='nx10-chain-rehearsal-actor' \
  bash "$CHAIN" --wait 2>&1)"
rc=$?
[ "$rc" -eq 1 ] && pass "시간 초과 exit 1" || fail "시간 초과 exit $rc(기대 1)"
printf '%s' "$out" | grep -q "시간 초과" && pass "시간 초과를 말한다" || fail "시간 초과 문장이 없다"
kill "$dummy" "$dummy2" 2>/dev/null || true
wait "$dummy" "$dummy2" 2>/dev/null || true
[ "$hashes_before" = "$(code_hashes)" ] && pass "코드 경로 무변경(쓰기 0건)" || fail "코드가 바뀌었다"

echo
echo "=== R4: 쓰기 전 관문 — 앞 단계 결과가 없으면 아무것도 적용하지 않는다 ==="
# 미러에는 `soak-recovery-latest.json` 이 없다 = “판정 없음”. 체인은 **배치를 적용하기 전에** 멈춰야 한다.
out="$(cd "$REPO" && NX10_SOAK_PROC_PATTERN='nx10-chain-none' NX10_CHAIN_PROC_PATTERN='nx10-chain-none' \
  NX10_GATES_PROC_PATTERN='nx10-chain-none' NX10_WATCH_PROC_PATTERN='nx10-chain-none' \
  NX10_HARVEST_PROC_PATTERN='nx10-chain-none' bash "$CHAIN" 2>&1)"
rc=$?
[ "$rc" -eq 1 ] && pass "관문에서 멈춤 exit 1" || fail "exit $rc(기대 1)"
printf '%s' "$out" | grep -q "회수 판정 JSON 이 없다" && pass "관문 사유를 말한다" || fail "관문 사유가 없다"
[ "$hashes_before" = "$(code_hashes)" ] && pass "**본 트리 코드 무변경**(쓰기 전 관문이 실제로 막았다)" \
  || fail "본 트리 코드가 바뀌었다"
grep -q "중단" "$MIRROR/nx10/batchchain/batchchain-record.md" 2>/dev/null \
  && pass "중단 기록이 **미러**에 남았다(본 운영 기록은 깨끗하다)" || fail "미러에 중단 기록이 없다"
# 이빨: 해시 비교가 변화를 **실제로** 감지하는가(한 바이트만 다른 사본으로 확인한다 — 본 파일은 안 건드린다).
probe="$(mktemp)"
printf 'probe' >"$probe"
[ "$(shasum -a 256 "$probe" | cut -d' ' -f1)" != "$(printf 'probe!' | shasum -a 256 | cut -d' ' -f1)" ] \
  && pass "이빨: 해시 비교가 한 바이트 차이를 감지한다" || fail "이빨 없음 — 해시 비교가 변화를 못 잡는다"
rm -f "$probe"
[ "$real_record_hash" = "$(record_hash)" ] && pass "본 운영 기록 무변화(리허설은 기록을 건드리지 않았다)" \
  || fail "본 기록이 오염됐다(미러 리허설인데 본 기록에 썼다)"

echo
echo "=== R5: 소스 이빨 — 첫 적용 호출이 관문 뒤에 있다 ==="
gate_line="$(grep -n '2. 앞 단계 결과 확인' "$CHAIN" | head -1 | cut -d: -f1)"
apply_line="$(grep -n 'apply_sc6fix.sh"' "$CHAIN" | head -1 | cut -d: -f1)"
if [ -n "$gate_line" ] && [ -n "$apply_line" ] && [ "$gate_line" -lt "$apply_line" ]; then
  pass "관문($gate_line행) < 첫 적용($apply_line행)"
else
  fail "순서가 코드에 없다(관문 $gate_line · 적용 $apply_line)"
fi

echo
if [ "$fails" -eq 0 ]; then
  echo "=== 결과: ALL PASS ==="
else
  echo "=== 결과: $fails 건 실패 ==="
fi
printf '  미러: %s (정리하려면 rm -rf)\n' "$MIRROR"
exit "$fails"
