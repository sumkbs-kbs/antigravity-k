#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""CR-13 증거 번들 수집기·검증기 (C13-01 ~ C13-05).

왜 필요한가
===========

RP-13 attempt-002의 `release-manifest.json`은 11개 artifact를 `/tmp/...`,
`/Users/.../ssak-rp12-candidate/...` 같은 **호스트 절대 경로**로 가리켰다. 그래서

  · 그 증거 폴더를 다른 위치로 복사하면 아무것도 검증할 수 없고,
  · 원본 파일이 나중에 바뀌면(`data/benchmark_results.json`이 실제로 그랬다) 검증이
    실패하며,
  · RP-12 후보(`4b202113`)의 증거를 새 후보(`08b8bb2e`)에 그대로 얹어도 거부되지 않는다.

이 도구는 **번들 자기완결성**을 계약으로 만든다:

  build   spec이 가리키는 파일을 `<bundle>/artifacts/<id>/<name>`으로 **복사**하고,
          민감 문자열을 지운(redaction) 뒤에야 최종 size/sha256을 계산해
          `manifest.json`(+ 자기 hash sidecar `manifest.sha256`)을 쓴다.
  verify  번들만 보고 판정한다 — 원본 경로·원본 파일이 필요 없다.

거부 규칙 (하나라도 걸리면 FAIL):

  C13-01 상대 경로   절대 경로, `..`, 심볼릭 링크 탈출, 번들 밖 경로
  C13-02 구조        누락, 중복 id, hash·size 불일치, manifest 변조(sidecar 불일치)
  C13-03 후보 SHA    source_sha가 40-hex가 아니거나 `--expected-sha`와 다름,
                    필수 gate 누락/실패, 짧은 soak, gate summary 재계산 불일치
  C13-04 이식성      원본 없이 검증(원본이 바뀌어도 번들은 그대로),
                    `historical` 증거는 gate/soak 근거로 쓸 수 없음
  C13-05 정직성      BUNDLE에 PASS 자기 주장 금지(판정은 verify의 출력),
                    redaction 후 hash, 원문(명령·exit) 연결
  C14-01 종류 고정   `evidence_kind`(`release`|`reference`)를 **필수**로 받는다.
                    `release`는 `required_gates`가 비어 있으면 build가 거부하고
                    verify도 거부한다 — 빈 gate 목록은 승인이 아니다(CR-13 우회로).
                    `reference`는 `required_gates`가 비어 있어야 하고, `verify`는
                    `PASS`가 아니라 `REFERENCE_ONLY`(exit 3)를 낸다 — 참고 번들은
                    어떤 경우에도 승인 artifact가 되지 않는다.

사용:
  uv run scripts/evidence_bundle.py build --spec spec.json --output .artifacts/bundle
  uv run scripts/evidence_bundle.py verify --bundle .artifacts/bundle --expected-sha <40-hex>

exit: 0 = 승인 가능, 1 = 판정 FAIL, 2 = 사용/파일 오류,
      3 = 구조는 유효하지만 승인 근거가 아님(`evidence_kind: reference`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ARTIFACTS_DIR = "artifacts"
MANIFEST_NAME = "manifest.json"
SIDECAR_NAME = "manifest.sha256"
HISTORICAL_ROLES_FORBIDDEN = ("gate", "gate-report", "soak", "gate_report")
GATE_REPORT_ROLES = ("gate", "gate-report", "gate_report")
EVIDENCE_KINDS = ("release", "reference")
RELEASE_KIND = "release"
REFERENCE_KIND = "reference"
EXIT_APPROVABLE = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_REFERENCE_ONLY = 3
DEFAULT_MIN_SOAK_SECONDS = 28_800
_REDACTED = "\u2039redacted\u203a"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
)
# 번들 안에 남아 있으면 안 되는 호스트 경로 흔적.
_HOST_PATH_RE = re.compile(r"(/tmp/[\w.@%+-]+|/Users/[\w.@%+-]+|/home/[\w.@%+-]+|/private/var/folders/[\w.@%+-]+)")
# PASS 자기 주장 금지 — 판정은 verify가 만든다.
_SELF_VERDICT_KEYS = ("verdict", "status", "approved", "approval", "manifest_verifier")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalize_required_gates(raw: Any) -> list[str]:
    """gate id 목록을 정규화한다. 빈 문자열·비문자열은 조용히 버리지 않고 거부한다."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"required_gates must be a list of gate ids, got {type(raw).__name__}")
    gates: list[str] = []
    for item in raw:
        gate_id = str(item).strip()
        if not gate_id:
            raise ValueError("required_gates must not contain empty gate ids")
        gates.append(gate_id)
    if len(set(gates)) != len(gates):
        raise ValueError(f"required_gates contains duplicates: {gates}")
    return gates


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(raw: str, fallback: str) -> str:
    name = Path(raw).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or fallback


def _redact(payload: bytes, secrets: tuple[bytes, ...]) -> tuple[bytes, int]:
    """민감 문자열을 지운다. 개수는 기록하되 원문은 남기지 않는다."""
    count = 0
    for secret in secrets:
        if not secret:
            continue
        hits = payload.count(secret)
        if hits:
            payload = payload.replace(secret, _REDACTED.encode())
            count += hits
    return payload, count


def _find_secret(payload: bytes) -> str | None:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(payload):
            return pattern.pattern.decode("utf-8", "replace")
    return None


# --------------------------------------------------------------------------- build


def build_bundle(spec_path: Path, output: Path, source_root: Path) -> tuple[Path, dict[str, Any]]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"spec schema_version must be {SCHEMA_VERSION}")

    source_sha = str(spec.get("source_sha", ""))
    if not _SHA_RE.match(source_sha):
        raise ValueError(f"spec source_sha must be a full 40-hex sha: {source_sha!r}")

    # C14-01 — 종류를 먼저 고정한다. 기본값을 두면 우회로가 다시 열린다.
    evidence_kind = str(spec.get("evidence_kind", ""))
    if evidence_kind not in EVIDENCE_KINDS:
        raise ValueError(f"spec evidence_kind must be one of {EVIDENCE_KINDS}: {evidence_kind!r}")
    required_gates = _normalize_required_gates(spec.get("required_gates"))
    if evidence_kind == RELEASE_KIND and not required_gates:
        raise ValueError(
            "release evidence must declare required_gates — an empty gate list can never be an approval (CR-13 hole)"
        )
    if evidence_kind == REFERENCE_KIND and required_gates:
        raise ValueError("reference evidence must not declare required_gates — carry gate coverage in a release bundle")

    artifact_specs = spec.get("artifacts")
    if not isinstance(artifact_specs, list) or not artifact_specs:
        raise ValueError("spec must list at least one artifact")

    redaction = tuple(str(item).encode() for item in spec.get("redaction", []))
    # 호스트 경로는 항상 지운다 — 명시 목록이 없어도 기본 계약이다.
    redaction += (str(Path.home()).encode(), str(source_root.resolve()).encode())

    if output.exists():
        shutil.rmtree(output)
    (output / ARTIFACTS_DIR).mkdir(parents=True)

    artifacts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in artifact_specs:
        artifact_id = str(entry.get("id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact id must be present")
        if artifact_id in seen_ids:
            raise ValueError(f"duplicate artifact id in spec: {artifact_id}")
        seen_ids.add(artifact_id)

        raw_source = entry.get("source")
        if not raw_source:
            raise ValueError(f"{artifact_id}: source is required")
        source = Path(str(raw_source))
        if not source.is_absolute():
            source = source_root / source
        if source.is_symlink():
            raise ValueError(f"{artifact_id}: source may not be a symlink ({source}) — copy the real file")
        if not source.is_file():
            raise FileNotFoundError(f"{artifact_id}: source missing at {source}")

        payload = source.read_bytes()
        secret = _find_secret(payload)
        if secret is not None:
            raise ValueError(f"{artifact_id}: secret-like content matched {secret!r}; refusing to bundle it")

        payload, redactions = _redact(payload, redaction)

        relative = Path(ARTIFACTS_DIR) / artifact_id / _safe_name(str(source), "artifact.bin")
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

        # 최종 hash/size 는 **redaction 이후 복사본**에서 계산한다.
        artifacts.append(
            {
                "id": artifact_id,
                "role": str(entry.get("role", "reference")),
                "path": relative.as_posix(),
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "redactions": redactions,
                "historical": bool(entry.get("historical", False)),
                "origin_sha": str(entry.get("origin_sha", source_sha)),
            }
        )

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": str(spec.get("bundle_id", output.name)),
        "built_at": str(spec.get("built_at", "")),
        "evidence_kind": evidence_kind,
        "source_sha": source_sha,
        "candidate": spec.get("candidate", {}),
        "tool": spec.get("tool", {}),
        "environment": spec.get("environment", {}),
        "commands": spec.get("commands", []),
        "lockfiles": [
            {"path": str(item), "sha256": sha256_file(source_root / str(item))}
            for item in spec.get("lockfiles", [])
            if (source_root / str(item)).is_file()
        ],
        "required_gates": required_gates,
        "gate_report": None,
        "soak": spec.get("soak"),
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "redaction": {"applied": True, "rule_count": len(redaction)},
    }

    _record_gate_report(manifest, output)
    _record_soak(manifest)

    manifest_path = output / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # 자기 hash 는 manifest **바깥**(sidecar)에 둔다 — 순환을 만들지 않는다.
    (output / SIDECAR_NAME).write_text(sha256_file(manifest_path) + "\n", encoding="utf-8")
    return manifest_path, manifest


def _load_bundled_json(output: Path, artifacts: list[dict[str, Any]], roles: tuple[str, ...]) -> dict[str, Any] | None:
    for artifact in artifacts:
        if artifact["role"] in roles:
            path = output / str(artifact["path"])
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            return loaded if isinstance(loaded, dict) else None
    return None


def _record_gate_report(manifest: dict[str, Any], output: Path) -> None:
    artifacts = manifest["artifacts"]
    if any(artifact["role"] in HISTORICAL_ROLES_FORBIDDEN and artifact["historical"] for artifact in artifacts):
        raise ValueError("historical artifacts may not fill a gate/soak role — carry them as role 'reference'")
    if manifest["evidence_kind"] == REFERENCE_KIND:
        fresh = [a["id"] for a in artifacts if a["role"] in GATE_REPORT_ROLES and not a["historical"]]
        if fresh:
            raise ValueError(
                f"reference evidence may not carry a fresh gate report ({', '.join(fresh)}) — "
                "mark it historical or use evidence_kind 'release'"
            )

    report = _load_bundled_json(output, artifacts, GATE_REPORT_ROLES)
    if report is None:
        if manifest["required_gates"]:
            raise ValueError("required_gates declared but no bundled gate report artifact (role 'gate-report')")
        return

    gates = report.get("gates")
    if not isinstance(gates, list):
        raise ValueError("gate report artifact has no 'gates' list")
    executed = {str(gate.get("id")): gate for gate in gates if isinstance(gate, dict) and gate.get("id") is not None}
    missing = [gate_id for gate_id in manifest["required_gates"] if gate_id not in executed]
    if missing:
        raise ValueError(f"gate report is missing required gates: {', '.join(missing)}")

    passed = sum(1 for gate in executed.values() if gate.get("status") == "passed")
    required_failed = sum(
        1 for gate in executed.values() if gate.get("required", True) and gate.get("status") != "passed"
    )
    manifest["gate_report"] = {
        "artifact": next(a["id"] for a in artifacts if a["role"] in GATE_REPORT_ROLES),
        "summary": {
            "passed": passed,
            "failed": len(executed) - passed,
            "required_failed": required_failed,
            "total": len(executed),
        },
        "required_gates_present": True,
    }


def _record_soak(manifest: dict[str, Any]) -> None:
    soak = manifest.get("soak")
    if not isinstance(soak, dict):
        return
    actual = soak.get("actual_duration_s")
    minimum = int(soak.get("min_seconds", DEFAULT_MIN_SOAK_SECONDS))
    soak["actual_duration_s"] = actual
    soak["min_seconds"] = minimum
    soak["meets_minimum"] = isinstance(actual, (int, float)) and actual >= minimum


# --------------------------------------------------------------------------- verify


def _within(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _recompute_gate_summary(bundle: Path, manifest: dict[str, Any], artifact_id: str) -> dict[str, int] | None:
    """번들 안의 gate report 원문에서 요약을 다시 계산한다 — metadata만 PASS로 바꾸지 못하게."""
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict) or str(artifact.get("id")) != artifact_id:
            continue
        path = bundle / str(artifact.get("path"))
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        gates = [gate for gate in report.get("gates", []) if isinstance(gate, dict)]
        passed = sum(1 for gate in gates if gate.get("status") == "passed")
        required_failed = sum(1 for gate in gates if gate.get("required", True) and gate.get("status") != "passed")
        return {
            "passed": passed,
            "failed": len(gates) - passed,
            "required_failed": required_failed,
            "total": len(gates),
        }
    return None


def verify_bundle(bundle: Path, expected_sha: str | None, min_soak_seconds: int | None = None) -> list[str]:
    problems: list[str] = []

    manifest_path = bundle / MANIFEST_NAME
    if not manifest_path.is_file():
        return [f"manifest: missing {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"manifest: invalid JSON ({exc})"]

    if not isinstance(manifest, dict):
        return ["manifest: top level must be an object"]

    # C13-05 — 판정은 검증기의 출력이지 번들의 자기 주장이 아니다.
    self_claims = sorted(key for key in _SELF_VERDICT_KEYS if key in manifest)
    if self_claims:
        problems.append(
            f"manifest: bundle must not assert its own verdict/approval (found {', '.join(self_claims)}) — "
            "PASS is produced by this verifier, not by the evidence"
        )

    # C13-02 — manifest 변조: sidecar 자기 hash
    sidecar = bundle / SIDECAR_NAME
    if not sidecar.is_file():
        problems.append("manifest: missing self-hash sidecar (manifest.sha256)")
    else:
        declared = sidecar.read_text(encoding="utf-8").strip()
        actual = sha256_file(manifest_path)
        if declared != actual:
            problems.append(f"manifest: self-hash mismatch (declared {declared[:16]}…, actual {actual[:16]}…)")

    # C13-03 — 후보 SHA
    source_sha = str(manifest.get("source_sha", ""))
    if not _SHA_RE.match(source_sha):
        problems.append(f"source_sha: not a full 40-hex sha: {source_sha!r}")
    elif expected_sha and source_sha != expected_sha:
        problems.append(
            f"source_sha: bundle was produced for {source_sha} but candidate is {expected_sha} — "
            "evidence from another candidate cannot be reused"
        )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        problems.append("artifacts: empty or missing artifact list")
        return problems

    seen: set[str] = set()
    historical_ids: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            problems.append(f"artifacts: non-object entry {artifact!r}")
            continue
        artifact_id = str(artifact.get("id", "<missing-id>"))
        if artifact_id in seen:
            problems.append(f"{artifact_id}: duplicate artifact id")
        seen.add(artifact_id)

        raw_path = artifact.get("path")
        if not raw_path:
            problems.append(f"{artifact_id}: missing path")
            continue
        relative = Path(str(raw_path))
        if relative.is_absolute():
            problems.append(f"{artifact_id}: absolute path is not allowed in a bundle ({relative})")
            continue
        if ".." in relative.parts:
            problems.append(f"{artifact_id}: parent traversal is not allowed ({relative})")
            continue
        resolved = bundle / relative
        if not _within(bundle, resolved):
            problems.append(f"{artifact_id}: path escapes the bundle via symlink ({relative})")
            continue
        if resolved.is_symlink():
            problems.append(f"{artifact_id}: symlinked artifact is not self-contained ({relative})")
            continue
        if not resolved.is_file():
            problems.append(f"{artifact_id}: artifact missing at {relative}")
            continue

        payload = resolved.read_bytes()
        actual_hash = sha256_bytes(payload)
        if artifact.get("sha256") != actual_hash:
            problems.append(
                f"{artifact_id}: sha256 mismatch (expected {str(artifact.get('sha256'))[:16]}…, got {actual_hash[:16]}…)"
            )
        if isinstance(artifact.get("bytes"), int) and len(payload) != artifact["bytes"]:
            problems.append(f"{artifact_id}: size mismatch (expected {artifact['bytes']}, got {len(payload)})")

        # C13-04 — historical 증거는 gate/soak 근거가 될 수 없다
        if artifact.get("historical"):
            historical_ids.append(artifact_id)
            if artifact.get("role") in HISTORICAL_ROLES_FORBIDDEN:
                problems.append(
                    f"{artifact_id}: historical evidence may not fill role {artifact.get('role')!r} "
                    "(same hash does not turn a past run into this candidate's run)"
                )

        # C13-05 — redaction 이후에도 호스트 경로 흔적이 남아 있으면 안 된다
        if resolved.suffix in (".json", ".txt", ".log", ".md", ".jsonl", ".yaml", ".yml", ".toml"):
            leaks = _HOST_PATH_RE.findall(payload.decode("utf-8", "replace"))
            if leaks:
                problems.append(f"{artifact_id}: host path leaked after redaction ({leaks[0]})")

    # C14-01 — 종류가 없거나 알 수 없으면 승인 근거가 아니다(CR-13 우회로 차단).
    raw_kind = manifest.get("evidence_kind")
    evidence_kind = str(raw_kind) if raw_kind is not None else ""
    if evidence_kind not in EVIDENCE_KINDS:
        problems.append(
            f"evidence_kind: missing or unknown ({raw_kind!r}); expected one of {EVIDENCE_KINDS} — "
            "an untyped bundle cannot be an approval"
        )

    required_gates = manifest.get("required_gates")
    gate_report = manifest.get("gate_report")
    if not isinstance(required_gates, list):
        problems.append(f"required_gates: must be a list, got {type(required_gates).__name__}")
        required_gates = []
    if evidence_kind == RELEASE_KIND and not required_gates:
        problems.append(
            "required_gates: release evidence declares no required gates — an empty gate list is not "
            "an approval (CR-13 hole: a bundle that declares no gates skipped every gate check)"
        )
    if evidence_kind == REFERENCE_KIND and required_gates:
        problems.append("required_gates: reference evidence must not declare gate coverage")
    if evidence_kind == REFERENCE_KIND and isinstance(gate_report, dict):
        problems.append("gate_report: reference evidence must not record a gate report as its own")

    # C13-03 — 필수 gate/soak 음성 시나리오 + summary 재계산(false metric 금지)
    if evidence_kind == RELEASE_KIND and required_gates:
        if not isinstance(gate_report, dict):
            problems.append("gate_report: required gates declared but no bundled gate report was recorded")
        else:
            summary = gate_report.get("summary") or {}
            if summary.get("required_failed"):
                # 비필수 gate 실패는 판정을 막지 않는다(정보로만 남는다). 필수 실패는 승인 불가다.
                problems.append(f"gate_report: required gates failed ({summary.get('required_failed')})")
            recomputed = _recompute_gate_summary(bundle, manifest, str(gate_report.get("artifact", "")))
            if recomputed is None:
                problems.append("gate_report: bundled gate report cannot be re-read (missing or invalid JSON)")
            elif {key: recomputed[key] for key in ("passed", "failed", "required_failed", "total")} != {
                key: summary.get(key) for key in ("passed", "failed", "required_failed", "total")
            }:
                problems.append(
                    "gate_report: recorded summary does not match the bundled gate report "
                    f"(recorded {summary}, recomputed {recomputed})"
                )

    soak = manifest.get("soak")
    if isinstance(soak, dict):
        soak_minimum = (
            min_soak_seconds if min_soak_seconds is not None else int(soak.get("min_seconds", DEFAULT_MIN_SOAK_SECONDS))
        )
        soak_actual = soak.get("actual_duration_s")
        if not isinstance(soak_actual, (int, float)) or soak_actual < soak_minimum:
            problems.append(
                f"soak: actual duration {soak_actual!r}s < required {soak_minimum}s "
                "(a short rehearsal must not be accepted as the formal gate)"
            )
    elif min_soak_seconds is not None:
        problems.append("soak: --min-soak-seconds given but the bundle records no soak evidence")

    return problems


def _bundle_evidence_kind(bundle: Path) -> str | None:
    """main()가 PASS와 REFERENCE_ONLY를 구분하기 위해 종류만 다시 읽는다."""
    try:
        manifest = json.loads((bundle / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    kind = manifest.get("evidence_kind")
    return str(kind) if kind in EVIDENCE_KINDS else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify a self-contained evidence bundle")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="copy artifacts into a bundle and write manifest.json")
    build.add_argument("--spec", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--source-root", default=".")

    verify = sub.add_parser("verify", help="verify a bundle without touching its original sources")
    verify.add_argument("--bundle", required=True)
    verify.add_argument("--expected-sha", default=None, help="candidate full 40-hex sha")
    verify.add_argument("--min-soak-seconds", type=int, default=None)
    verify.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "build":
        spec_path = Path(args.spec)
        if not spec_path.is_file():
            print(f"spec not found: {spec_path}", file=sys.stderr)
            return 2
        try:
            manifest_path, manifest = build_bundle(spec_path, Path(args.output), Path(args.source_root).resolve())
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"bundle build failed: {error}", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {"bundle": str(manifest_path.parent), "artifacts": manifest["artifact_count"]}, ensure_ascii=False
            )
        )
        return 0

    bundle_path = Path(args.bundle)
    if not bundle_path.is_dir():
        print(f"bundle not found: {bundle_path}", file=sys.stderr)
        return 2
    problems = verify_bundle(bundle_path, args.expected_sha, args.min_soak_seconds)
    if problems:
        if args.json:
            print(json.dumps({"verdict": "FAIL", "problems": problems}, ensure_ascii=False, indent=2))
        else:
            for problem in problems:
                print(f"FAIL {problem}")
        return EXIT_FAIL
    # C14-01 — 참고 번들은 구조가 유효해도 승인이 아니다. exit 3은 PASS(0)와 다르다.
    if _bundle_evidence_kind(bundle_path) == REFERENCE_KIND:
        message = (
            "REFERENCE_ONLY: bundle is self-contained and bound to the candidate sha, "
            "but it declares no required gates and can never be used as an approval artifact"
        )
        print(json.dumps({"verdict": "REFERENCE_ONLY", "problems": []}, ensure_ascii=False) if args.json else message)
        return EXIT_REFERENCE_ONLY
    if args.json:
        print(json.dumps({"verdict": "PASS", "problems": []}, ensure_ascii=False))
    else:
        print("PASS: bundle is self-contained, immutable and bound to the candidate sha")
    return EXIT_APPROVABLE


if __name__ == "__main__":
    raise SystemExit(main())
