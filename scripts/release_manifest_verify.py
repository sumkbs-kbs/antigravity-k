#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""RP-13 release manifest 검증기 (FR-09/R13-09·10).

manifest JSON이 가리키는 모든 artifact가 존재하고 SHA256이 일치하며,
source SHA가 full 40-hex 형식인지 확인한다. 하나라도 없거나 변조되면
FAIL(nonzero). ``--source-root``가 지정되면 상대 경로를 그 아래에서 해석한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(manifest: dict[str, Any], source_root: Path | None) -> list[str]:
    problems: list[str] = []
    source_sha = str(manifest.get("source_sha", ""))
    if not _SHA_RE.match(source_sha):
        problems.append(f"source_sha: not a full 40-hex sha: {source_sha!r}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        problems.append("artifacts: empty or missing artifact list")
        return problems

    seen_ids: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            problems.append(f"artifacts: non-object entry {artifact!r}")
            continue
        artifact_id = str(artifact.get("id", "<missing-id>"))
        if artifact_id in seen_ids:
            problems.append(f"{artifact_id}: duplicate artifact id")
        seen_ids.add(artifact_id)

        raw_path = artifact.get("path")
        if not raw_path:
            problems.append(f"{artifact_id}: missing path")
            continue
        path = Path(str(raw_path))
        resolved = path if path.is_absolute() else (source_root or Path.cwd()) / path
        if not resolved.is_file():
            problems.append(f"{artifact_id}: artifact missing at {resolved}")
            continue
        expected = artifact.get("sha256")
        if not expected:
            problems.append(f"{artifact_id}: missing sha256")
            continue
        actual = _sha256(resolved)
        if actual != expected:
            problems.append(f"{artifact_id}: sha256 mismatch (expected {expected}, got {actual})")
        declared_size = artifact.get("size_bytes")
        if isinstance(declared_size, int) and resolved.stat().st_size != declared_size:
            problems.append(f"{artifact_id}: size mismatch (expected {declared_size}, got {resolved.stat().st_size})")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an RP-13 release manifest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-root", default=None, help="상대 경로 artifact의 기준 루트")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid manifest JSON: {exc}", file=sys.stderr)
        return 2

    root = Path(args.source_root).resolve() if args.source_root else None
    problems = verify_manifest(manifest, root)
    if problems:
        print(json.dumps({"verdict": "FAIL", "problems": problems}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"verdict": "PASS", "artifacts": len(manifest.get("artifacts", []))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
