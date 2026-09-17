#!/usr/bin/env bash
# 리허설 — 승격 체인 ② 단계의 **판정 수용 규칙**만 격리해서 시험한다.
#
# 왜 필요한가: 2026-09-17 에 체인은 회수 판정이 이미 PASS 로 기록돼 있는데도 **자기 손으로 다시 판정**했고,
# 그 재판정이 “측정 후 코드 무변경” 조건을 깨서(그 사이 커밋이 움직인다) 스스로 FAIL 을 만들어냈다.
# 종전 규칙은 “이 체인이 시작된 뒤에 쓰인 산출물”(mtime ≥ 체인 시작)을 요구했기 때문이다.
# 새 규칙은 **이 실행에 대한 판정인가**를 본다:
#   ① 러너 종료시각 뒤에 수집됐다 (`collected_at >= runner.end_time`)
#   ② 그 판정이 **실행 트리에서** 내려졌다 (`worktree_fingerprint_now == runner.start_fingerprint`)
#
# 시험 대상은 **체인 파일에서 그대로 뽑아낸 함수 텍스트**다(사본을 시험하면 사본만 지킨다).
#
# 사용: bash …/promote3/rehearse_verdict_acceptance.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NX10="$(cd "$HERE/.." && pwd)"
REPO="${NX10_REPO:-$(cd "$NX10/../../../.." && pwd)}"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
CHAIN="$HERE/post_harvest_sequence3.sh"

fail=0
ok() { printf '  [OK  ] %s\n' "$1"; }
bad() {
  printf '  [FAIL] %s\n' "$1"
  fail=$((fail + 1))
}

# 함수 텍스트만 뽑는다 — 파일 전체를 source 하면 무인 실행이 딸려 온다.
text="$(awk '/^verdict_is_about_the_run\(\) \{/{f=1} f{print} f&&/^\}$/{exit}' "$CHAIN")"
if [ -z "$text" ]; then
  bad "체인에서 verdict_is_about_the_run() 를 찾지 못했다: $CHAIN"
  exit 1
fi
# shellcheck disable=SC1090
eval "$text"

d="$(mktemp -d)"
trap 'rm -rf "$d"' EXIT
start_fp="$(printf 'a%.0s' $(seq 1 64))"
other_fp="$(printf 'b%.0s' $(seq 1 64))"

write_case() { # $1=파일 $2=collected_at $3=end_time $4=worktree_fp $5=start_fp
  "$PY" - "$1" "$2" "$3" "$4" "$5" <<'PYW'
import json, sys
path, collected, end, now_fp, start_fp = sys.argv[1:6]
json.dump(
    {
        "collected_at": collected,
        "verdict": "PASS",
        "judged_run_start": "2026-09-17T03:25:56Z",
        "runner": {"start_time": "2026-09-17T03:25:56Z", "end_time": end, "exit": "0",
                   "start_fingerprint": start_fp, "end_fingerprint": start_fp},
        "worktree_fingerprint_now": now_fp,
    },
    open(path, "w", encoding="utf-8"),
)
PYW
}

expect() { # $1=기대(accept|reject) $2=파일 $3=설명
  recovery="$2"
  if verdict_is_about_the_run; then got=accept; else got=reject; fi
  if [ "$got" = "$1" ]; then ok "$3 → $got"; else bad "$3 → $got (기대 $1)"; fi
}

# ① 이 실행에 대한 판정(종료 뒤 수집 · 실행 트리에서 판정) → 받는다
write_case "$d/about_run.json" "2026-09-17T11:32:13Z" "2026-09-17T11:26:00Z" "$start_fp" "$start_fp"
expect accept "$d/about_run.json" "종료 뒤 수집 · 실행 트리 판정"

# ② 종료 **전**에 수집된 판정(다른/이전 실행의 것) → 받지 않는다(종전 mtime 규칙이 잡던 위험)
write_case "$d/before_end.json" "2026-09-17T11:20:00Z" "2026-09-17T11:26:00Z" "$start_fp" "$start_fp"
expect reject "$d/before_end.json" "종료 전에 수집된 판정"

# ③ 판정 뒤에 코드가 움직였다(지금 트리 ≠ 실행 트리) → 받지 않는다(그 green 은 후보의 것이 아니다)
write_case "$d/tree_moved.json" "2026-09-17T11:32:13Z" "2026-09-17T11:26:00Z" "$other_fp" "$start_fp"
expect reject "$d/tree_moved.json" "판정 뒤 코드 이동"

# ④ 필드가 없는 JSON → 받지 않는다(조용히 통과 금지 · 닫힌 방향으로 실패)
echo '{}' >"$d/empty.json"
expect reject "$d/empty.json" "필드 없는 JSON"

# ④b 어느 실행을 판정했는지 밝히지 않는 JSON → 받지 않는다(“낡은 판정” 을 잡는 방법이 이것이다)
write_case "$d/no_run.json" "2026-09-17T11:32:13Z" "2026-09-17T11:26:00Z" "$start_fp" "$start_fp"
"$PY" - "$d/no_run.json" <<'PYN'
import json, sys
path = sys.argv[1]
doc = json.load(open(path, encoding="utf-8"))
doc.pop("judged_run_start", None)
json.dump(doc, open(path, "w", encoding="utf-8"))
PYN
expect reject "$d/no_run.json" "판정 대상 미상(judged_run_start 없음)"

# ⑤ **실제 산출물**(체인이 곧 소비할 그것) → 받고, 판정도 보여 준다
real="$NX10/soak-recovery-latest.json"
if [ -f "$real" ]; then
  expect accept "$real" "실제 soak-recovery-latest.json"
  "$PY" - "$real" <<'PYR'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
r = d.get("runner") or {}
print(f"      판정={d.get('verdict')} · 수집={d.get('collected_at')} · 실행={r.get('start_time')} → {r.get('end_time')}")
PYR
else
  bad "실제 산출물이 없다: $real"
fi

printf '\n리허설 결과: %s\n' "$([ "$fail" -eq 0 ] && echo 'ALL PASS' || echo "실패 $fail 건")"
exit $((fail == 0 ? 0 : 1))
