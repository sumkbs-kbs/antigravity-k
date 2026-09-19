"""SEC-01 독립 재현 — 수용기준 핵심 시나리오 직접 검증 (리뷰어 스크립트)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "tests")
os.environ.pop("AGK_ENV", None)  # development

from antigravity_k.api.auth_policy import AuthPolicy
from antigravity_k.engine.auth import hash_pin

results = []


def check(name, cond):
    results.append((name, cond))


tmp = Path(tempfile.mkdtemp())
hash_file = tmp / "auth_hash"


def make_policy(hf: Path, pin: str, host: str = "127.0.0.1") -> AuthPolicy:
    return AuthPolicy(
        stored_pin_hash=lambda: (
            hf.read_text(encoding="utf-8").strip() if hf.exists() and hf.read_text(encoding="utf-8").strip() else None
        ),
        plaintext_pin=lambda: pin,
        host=lambda: host,
    )


# 1. hash-only 서버 (plaintext PIN 없음, hash 파일 존재) → deny (SEC-01 핵심 결함 수정)
hash_file.write_text(hash_pin("secret-pin") + "\n", encoding="utf-8")
p1 = make_policy(hash_file, "")
d1 = p1.resolve()
check("hash-only loopback은 익명 거절 (핵심 결함)", d1.level == "protected")

# 2. credential 전무 + 명시 dev-allow + loopback → open_loopback 허용
os.environ["AGK_SEC_DEV_NO_PIN_ALLOW"] = "1"
p2 = make_policy(tmp / "none", "")
d2 = p2.resolve()
check("dev-allow 3조건 충족 시 anonymous(open_loopback)", d2.level == "open_loopback")
os.environ.pop("AGK_SEC_DEV_NO_PIN_ALLOW", None)

# 3. production에서는 env가 있어도 거절
os.environ["AGK_SEC_DEV_NO_PIN_ALLOW"] = "1"
os.environ["AGK_ENV"] = "production"
p3 = make_policy(tmp / "none", "")
d3 = p3.resolve()
check("production 항상 deny", d3.level != "open_loopback")
os.environ.pop("AGK_ENV", None)
os.environ.pop("AGK_SEC_DEV_NO_PIN_ALLOW", None)

# 4. PIN 삭제 즉시 반영 (캐시 없음)
os.environ["AGK_SEC_DEV_NO_PIN_ALLOW"] = "1"
p4 = make_policy(hash_file, "")
d4a = p4.resolve()
hash_file.unlink()
d4b = p4.resolve()
check("PIN 삭제 즉시 protected→open_loopback 전환", d4a.level == "protected" and d4b.level == "open_loopback")

# 5. non-loopback 바인드 deny
p5 = make_policy(tmp / "none", "", host="0.0.0.0")
d5 = p5.resolve()
check("0.0.0.0 바인드 항상 deny", d5.level != "open_loopback")

# 6. 유효 bearer/pin은 hash-only에서 통과
d6 = p1.resolve()  # hash_file deleted; recreate
hash_file.write_text(hash_pin("secret-pin") + "\n", encoding="utf-8")
d6 = p1.evaluate_credential(token_verified=True, pin=None)
check("hash-only + 유효 토큰 = protected 허용", d6.level == "protected")

failed = [n for n, ok in results if not ok]
for name, ok in results:
    print(("PASS" if ok else "FAIL"), "-", name)
print("SUMMARY:", f"{len(results)-len(failed)}/{len(results)}")
sys.exit(1 if failed else 0)
