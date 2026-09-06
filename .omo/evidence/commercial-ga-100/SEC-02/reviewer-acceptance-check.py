"""SEC-02 독립 수용기준 평가 — reviewer 스크립트 (구현자 테스트와 별개).

DAT-02/SEC-01 리뷰와 동일한 방식: 구현자의 테스트를 재실행하는 대신,
리뷰어가 plan §SEC-02의 수용기준 4건을 **독립 시나리오로 직접 재현**한다.

  AC-1  임의 보호 URL에서 PIN 후보를 보내도 PBKDF2 검증이 실행되지 않는다
  AC-2  IP/계정 기준 burst + sustained limit과 lockout이 적용된다
  AC-3  성공/실패/lockout audit가 secret 없이 남는다
  AC-4  공격 요청이 정상 인증 latency 대비 threshold 이상으로 악화되지 않는다

실행: uv run --no-sync python .omo/evidence/commercial-ga-100/SEC-02/reviewer-acceptance-check.py
종료코드: 0 = 전부 PASS, 1 = 결함 존재.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

PASS = 0
FAIL = 0
RESULTS: list[tuple[str, str, str]] = []

repo = Path(__file__).resolve().parents[4]
os.chdir(repo)
sys.path.insert(0, str(repo / "src"))


def check(ac: str, name: str, ok: bool, note: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append((ac, name, f"{tag} {note}".strip()))
    print(f"  [{tag}] {name}" + (f" — {note}" if note else ""))


# ─── 환경 격리: hash 전용 (plaintext PIN 없음) + dev 익명 허용 없음 ──────
_tmp = tempfile.mkdtemp(prefix="sec02_review_")
os.environ["AGK_SEC_PIN_HASH_FILE"] = str(Path(_tmp) / "auth_hash")
os.environ["AGK_SEC_ACCESS_PIN"] = ""
os.environ["AGK_SEC_DEV_NO_PIN_ALLOW"] = "0"
os.environ.pop("PYTHONSTARTUP", None)

from antigravity_k.engine.auth import hash_pin  # noqa: E402

(Path(_tmp) / "auth_hash").write_text(hash_pin("correct-pin"), encoding="utf-8")

# ─── AC-1: 임의 보호 URL — raw PIN 표면 제거 ───────────────────────────
print("\nAC-1 임의 보호 URL에서 PBKDF2 미실행")

from fastapi import Request  # noqa: E402

import antigravity_k.api.auth_routes as auth_routes  # noqa: E402

calls: list[tuple[str, str]] = []


def _spy(pin: str, stored: str) -> bool:
    calls.append((pin, stored))
    return True


auth_routes.verify_pin = _spy  # type: ignore[method-assign]

import re  # noqa: E402

unexpected: list[str] = []
for path in Path("src/antigravity_k").rglob("*.py"):
    if path.name == "auth.py":
        continue
    text = path.read_text(encoding="utf-8")
    if re.search(r"\bverify_pin\(", text):
        unexpected.append(str(path))
allowed = {"src/antigravity_k/api/auth_routes.py"}
check(
    "AC-1",
    "verify_pin 호출처가 rate-limited login/token route뿐",
    not [p for p in unexpected if p not in allowed],
    f"hits={sorted(set(unexpected))}",
)

# 헤더 PIN으로 authenticate_request → False, spy 미호출
request = Request({"type": "http", "headers": [(b"x-access-pin", b"guessed")]})
try:
    authenticated = auth_routes.authenticate_request(request)
    check(
        "AC-1",
        "X-Access-Pin 헤더 → 거부 + PBKDF2 미실행",
        authenticated is False and calls == [],
        f"authenticated={authenticated}, pbkdf2_calls={len(calls)}",
    )
except Exception as exc:  # pragma: no cover
    check("AC-1", "X-Access-Pin 헤더 → 거부", False, f"exception: {exc}")

# WS: 쿼리 ?pin= → 4401 close, PBKDF2 미실행
import asyncio  # noqa: E402

import antigravity_k.api.routes.session_state as session_state  # noqa: E402


class _FakeWS:
    state = type("S", (), {})()

    async def accept(self) -> None: ...

    async def close(self, code: int, reason: str) -> None:
        _FakeWS.closed = (code, reason)

    @property
    def query_params(self) -> dict[str, str]:
        return {"pin": "guessed-pin"}

    @property
    def headers(self) -> dict[str, str]:
        return {}


_FakeWS.closed = None  # type: ignore[attr-defined]
ws = _FakeWS()
try:
    closed = asyncio.run(session_state.close_unauthorized_ws(ws))
    check(
        "AC-1",
        "WS ?pin= → 4401 close + PBKDF2 미실행",
        closed is True and _FakeWS.closed and _FakeWS.closed[0] == 4401 and calls == [],
        f"closed={closed}, code={getattr(_FakeWS, 'closed', None)}, pbkdf2_calls={len(calls)}",
    )
except Exception as exc:  # pragma: no cover
    check("AC-1", "WS ?pin= → 4401 close", False, f"exception: {exc}")

# ─── AC-2: burst + sustained + lockout (IP/계정 key) ────────────────────
print("\nAC-2 burst/sustained limit과 lockout")
from antigravity_k.security.credential_gate import CredentialGate  # noqa: E402

gate = CredentialGate(burst_limit=5, burst_window_sec=60.0, lockout_sec=300.0)
decisions = [gate.record_failure("ip:9.9.9.9") for _ in range(5)]
check(
    "AC-2",
    "burst 5회 실패 → lockout 시작",
    all(d.allowed for d in decisions[:4]) and not decisions[4].allowed,
    f"5th={decisions[4].reason}",
)
again = gate.register("ip:9.9.9.9")
check("AC-2", "lockout 중 register → 즉시 거절", not again.allowed, f"retry_after={again.retry_after_sec:.1f}s")

# sustained: 긴 창 누적
gate2 = CredentialGate(
    burst_limit=100, burst_window_sec=60.0, sustained_limit=10, sustained_window_sec=600.0, lockout_sec=60.0
)
sustained = [gate2.record_failure("user:acct") for _ in range(10)]
check("AC-2", "sustained 누적 10회 → lockout", not sustained[-1].allowed, f"last={sustained[-1].reason}")

# 계정 key 분리
gate3 = CredentialGate(burst_limit=3, burst_window_sec=60.0, lockout_sec=10.0)
for _ in range(3):
    gate3.record_failure("user:victim")
check("AC-2", "다른 계정 key는 독립 판정", gate3.check("user:other").allowed)
gate3.record_success("user:victim")
check("AC-2", "record_success가 lockout 해제", gate3.check("user:victim").allowed)

# ─── AC-3: audit secret-free ────────────────────────────────────────────
print("\nAC-3 secret-free audit")
from antigravity_k.security.auth_audit import (  # noqa: E402
    get_auth_audit_events,
    record_auth_event,
    reset_auth_audit,
)

reset_auth_audit()
record_auth_event("login_failed", "1.2.3.4", "attempt pin=super-secret-123 wrong")
record_auth_event("login_success", "1.2.3.4")
record_auth_event("lockout", "1.2.3.4", "threshold; credential=hunter2 leaked in detail")
events = get_auth_audit_events()
blob = str(events)
check("AC-3", "성공/실패/lockout 이벤트 기록", len(events) == 3, f"events={[e['event'] for e in events]}")
check("AC-3", "credential 값이 어떤 필드에도 없음", "super-secret-123" not in blob and "hunter2" not in blob)

# ─── AC-4: lockout 우회 공격이 정상 latency를 악화시키지 않음 ────────────
print("\nAC-4 부하 — lockout 중 PBKDF2 차단")
# 실제 600k 반복 PBKDF2 한 번의 비용
t0 = time.perf_counter()
hash_pin("latency-baseline", iterations=600_000)
full_cost = time.perf_counter() - t0

locked = CredentialGate(burst_limit=2, burst_window_sec=60.0, lockout_sec=300.0)
locked.record_failure("ip:attacker")
locked.record_failure("ip:attacker")  # → lockout

attempts = 200
t0 = time.perf_counter()
for _ in range(attempts):
    d = locked.register("ip:attacker")
    if d.allowed:
        # lockout 중엔 절대 허용되면 안 된다 — 그런데 허용됐다면 실제 PBKDF2 비용을 유발
        hash_pin("attack", iterations=600_000)
attack_elapsed = time.perf_counter() - t0

all_blocked = True
t0 = time.perf_counter()
for _ in range(attempts):
    if locked.register("ip:attacker").allowed:
        all_blocked = False
gate_elapsed = time.perf_counter() - t0

check("AC-4", "lockout 중 모든 register 거절", all_blocked)
equivalent_full = attempts * full_cost
check(
    "AC-4",
    "공격자가 유발한 CPU < 정상 인증 1회 × 시도수의 1%",
    attack_elapsed < equivalent_full * 0.01,
    f"attack_total={attack_elapsed * 1000:.1f}ms vs equivalent={equivalent_full * 1000:.0f}ms "
    f"(pbkdf2_once={full_cost * 1000:.0f}ms, gate_only={gate_elapsed * 1000:.1f}ms)",
)

# ─── 결과 ────────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print(f"SEC-02 reviewer acceptance: {PASS} PASS / {FAIL} FAIL")
sys.exit(0 if FAIL == 0 else 1)
