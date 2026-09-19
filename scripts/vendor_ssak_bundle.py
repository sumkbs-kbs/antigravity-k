#!/usr/bin/env python3
"""번들 검색 artifact 를 패키지 데이터로 가져온다(핀 고정, task 15).

이 스크립트가 없애려는 실패 모드: "패키징할 때 최신 것을 받아온다". 그러면 설치본마다 다른
바이트가 들어가고, 사용자가 실행하는 것이 무엇인지 아무도 모른다. 그래서 바이트는
`src/antigravity_k/vendor/ssak_search/PINNED.json` 의 sha256 **하나로** 고정된다.

사용법(repo 루트):

    # W 릴리스 디렉터리에서 materialize (bin/ssak-mcp + release/ssak-search-manifest.json 필요)
    python3 scripts/vendor_ssak_bundle.py --from /path/to/W

    # 현재 vendored 바이트가 핀과 일치하는지 검사(패키징 게이트)
    python3 scripts/vendor_ssak_bundle.py --check

    # 핀 자체를 소스에서 새로 만든다(해시를 손으로 적지 않는다)
    python3 scripts/vendor_ssak_bundle.py --print-pin --from /path/to/W

종료코드 0 = 핀과 일치. 1 = 불일치(무엇이 어긋났는지 출력).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO / "src" / "antigravity_k" / "vendor" / "ssak_search"
PIN_FILE = VENDOR_DIR / "PINNED.json"
BINARY_RELATIVE = Path("bin") / "ssak-mcp"
MANIFEST_RELATIVE = Path("release") / "ssak-search-manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pin() -> dict[str, Any]:
    payload = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{PIN_FILE} is not a JSON object")
    return payload


def verify_against_pin(binary: Path, manifest: Path, pin: dict[str, Any]) -> list[str]:
    """핀과 실물을 대조해 문제 목록을 돌려준다(빈 목록 = 통과)."""
    problems: list[str] = []
    if not binary.is_file():
        return [f"artifact is missing: {binary}"]
    if not manifest.is_file():
        problems.append(f"manifest is missing: {manifest}")

    expected = pin.get("artifact", {})
    actual_sha = sha256_file(binary)
    actual_size = binary.stat().st_size
    if actual_sha != expected.get("sha256"):
        problems.append(f"sha256 mismatch: file={actual_sha} pin={expected.get('sha256')}")
    if actual_size != expected.get("size_bytes"):
        problems.append(f"size mismatch: file={actual_size} pin={expected.get('size_bytes')}")

    if manifest.is_file():
        recorded = json.loads(manifest.read_text(encoding="utf-8")).get("artifact", {})
        for key in ("sha256", "platform", "arch"):
            if recorded.get(key) != expected.get(key):
                problems.append(f"manifest {key}={recorded.get(key)!r} disagrees with pin {expected.get(key)!r}")
        recorded_size = recorded.get("size_bytes")
        if recorded_size is not None and recorded_size != expected.get("size_bytes"):
            problems.append(f"manifest size_bytes={recorded_size} disagrees with pin {expected.get('size_bytes')}")
    return problems


def materialize(source: Path, *, binary: Path | None = None, manifest: Path | None = None) -> int:
    """소스에서 vendored 바이트를 복사한다(핀 검증을 먼저 통과해야 한다)."""
    src_binary = binary or source / BINARY_RELATIVE
    src_manifest = manifest or source / MANIFEST_RELATIVE
    if not src_binary.is_file():
        print(f"FAIL: --from {source} has no {BINARY_RELATIVE}", file=sys.stderr)
        return 1
    pin = load_pin()
    problems = verify_against_pin(src_binary, src_manifest, pin)
    if problems:
        print("FAIL: the source does not match the pin — refusing to vendor different bytes", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    (VENDOR_DIR / "bin").mkdir(parents=True, exist_ok=True)
    (VENDOR_DIR / "release").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_binary, VENDOR_DIR / BINARY_RELATIVE)
    (VENDOR_DIR / BINARY_RELATIVE).chmod(0o755)
    shutil.copy2(src_manifest, VENDOR_DIR / MANIFEST_RELATIVE)
    print(f"vendored {VENDOR_DIR / BINARY_RELATIVE} (sha256 {pin['artifact']['sha256'][:16]}…)")
    return 0


def check() -> int:
    pin = load_pin()
    problems = verify_against_pin(VENDOR_DIR / BINARY_RELATIVE, VENDOR_DIR / MANIFEST_RELATIVE, pin)
    if problems:
        print("FAIL: vendored bundle does not match the pin", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("  (run: python3 scripts/vendor_ssak_bundle.py --from <W release dir>)", file=sys.stderr)
        return 1
    print(
        f"OK: vendored bundle matches the pin ({pin['artifact']['sha256'][:16]}…, {pin['artifact']['size_bytes']} bytes)"
    )
    return 0


def print_pin(source: Path, *, binary: Path | None = None, manifest: Path | None = None) -> int:
    """소스에서 핀을 새로 만든다 — 해시는 측정값이지 사람이 적는 값이 아니다."""
    src_binary = binary or source / BINARY_RELATIVE
    src_manifest = manifest or source / MANIFEST_RELATIVE
    if not src_binary.is_file() or not src_manifest.is_file():
        print(f"FAIL: {source} must contain {BINARY_RELATIVE} and {MANIFEST_RELATIVE}", file=sys.stderr)
        return 1
    recorded = json.loads(src_manifest.read_text(encoding="utf-8"))
    artifact = recorded.get("artifact", {})
    pin = load_pin()
    pin["artifact"] = {
        "sha256": sha256_file(src_binary),
        "size_bytes": src_binary.stat().st_size,
        "platform": artifact.get("platform"),
        "arch": artifact.get("arch"),
        "format": artifact.get("format"),
        "product": recorded.get("product", {}).get("name"),
        "version": recorded.get("product", {}).get("version"),
    }
    pin["source"]["commit"] = recorded.get("source", {}).get("commit", pin["source"].get("commit"))
    print(json.dumps(pin, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="source", type=Path, help="W release dir (needs bin/ + release/)")
    parser.add_argument("--binary", type=Path, help="artifact explicitly (defaults to <from>/bin/ssak-mcp)")
    parser.add_argument("--manifest", type=Path, help="manifest explicitly (defaults to <from>/release/...)")
    parser.add_argument("--check", action="store_true", help="verify the vendored bytes against the pin")
    parser.add_argument("--print-pin", action="store_true", help="print a refreshed pin for the source")
    args = parser.parse_args()

    if args.check:
        return check()
    if args.source is None:
        parser.error("either --check or --from is required")
    if args.print_pin:
        return print_pin(args.source, binary=args.binary, manifest=args.manifest)
    return materialize(args.source, binary=args.binary, manifest=args.manifest)


if __name__ == "__main__":
    sys.exit(main())
