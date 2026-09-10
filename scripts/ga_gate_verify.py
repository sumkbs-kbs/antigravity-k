#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
# ─── How to run ───
# uv run scripts/ga_gate_verify.py --report .artifacts/commercial-ga.json \
#   [--manifest scripts/commercial_ga_gates.json] [--expected-sha <full-sha>] \
#   [--soak-artifact val02.json --min-soak-seconds 28800]

"""GA gate 결과 artifact 검증기 (FR-06/09, RP-11/R11-04·11).

gate runner(`ga_gate.py`)의 결과 JSON이 승인 가능한 형태인지 **구조적으로**
판정한다. 검증 항목:

- 필수(required) gate가 하나라도 누락되면 FAIL — 빈 목록 all([])==true 승인 불가
- gate 결과 정합: status "passed" <=> exit_code 0, duration > 0, 시작/종료 시각 존재
- source SHA: 40-hex 형식, --expected-sha 지정 시 완전 일치
- summary 재계산 일치(false metric 방지)
- VAL-02 soak artifact(선택): all_pass, missing_required 공백, 실측 soak duration이
  최소 요구(기본 28800초) 미달이면 FAIL — 60초 리허설을 정식 gate로 위장 불가

exit code: 0 = 승인 가능, 1 = 판정 FAIL, 2 = 사용/파일 오류.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _fail(problems: list[str], label: str, message: str) -> None:
    problems.append(f"{label}: {message}")


def verify_gate_report(report: dict[str, Any], manifest: dict[str, Any], expected_sha: str | None) -> list[str]:
    problems: list[str] = []
    gates_field = report.get("gates")
    if not isinstance(gates_field, list) or not gates_field:
        _fail(problems, "gates", "empty or missing gates list — an executed report must contain gate results")
        return problems

    executed = {}
    for gate in gates_field:
        if not isinstance(gate, dict):
            _fail(problems, "gates", f"non-object gate entry: {gate!r}")
            continue
        gate_id = str(gate.get("id", "<missing-id>"))
        executed[gate_id] = gate
        status = gate.get("status")
        exit_code = gate.get("exit_code")
        if status == "passed" and exit_code != 0:
            _fail(problems, gate_id, f"status 'passed' but exit_code={exit_code}")
        if status != "passed" and exit_code == 0 and status != "interrupted":
            _fail(problems, gate_id, f"exit_code=0 but status={status!r}")
        duration = gate.get("duration_seconds")
        if not isinstance(duration, (int, float)) or duration <= 0:
            _fail(problems, gate_id, f"implausible duration_seconds={duration!r}")
        if not gate.get("started_at") or not gate.get("finished_at"):
            _fail(problems, gate_id, "missing started_at/finished_at")

    required_ids = [g["id"] for g in manifest.get("gates", []) if g.get("required")]
    missing = [rid for rid in required_ids if rid not in executed]
    if missing:
        _fail(problems, "missing_required", f"required gates not executed: {', '.join(missing)}")

    git_info = report.get("git") or {}
    sha = str(git_info.get("sha", ""))
    if not _SHA_RE.match(sha):
        _fail(problems, "git.sha", f"not a full 40-hex sha: {sha!r}")
    elif expected_sha and sha != expected_sha:
        _fail(problems, "git.sha", f"report sha {sha} != expected {expected_sha}")

    summary = report.get("summary") or {}
    actual_passed = sum(1 for g in executed.values() if g.get("status") == "passed")
    actual_total = len(gates_field)
    if summary.get("passed") != actual_passed or summary.get("total") != actual_total:
        _fail(
            problems,
            "summary",
            f"summary mismatch: reported passed/total={summary.get('passed')}/{summary.get('total')} "
            f"but recomputed={actual_passed}/{actual_total}",
        )
    actual_required_failed = sum(
        1 for g in gates_field if isinstance(g, dict) and g.get("required") and g.get("status") != "passed"
    )
    if summary.get("required_failed") != actual_required_failed:
        _fail(
            problems,
            "summary",
            f"required_failed mismatch: reported {summary.get('required_failed')}, actual {actual_required_failed}",
        )

    return problems


def verify_soak_artifact(artifact: dict[str, Any], min_soak_seconds: int) -> list[str]:
    problems: list[str] = []
    if artifact.get("all_pass") is not True:
        _fail(problems, "soak.all_pass", f"VAL-02 all_pass={artifact.get('all_pass')!r}")
    missing = artifact.get("missing_required")
    if missing:
        _fail(problems, "soak.missing_required", f"VAL-02 missing scenarios: {missing}")
    if not artifact.get("scenarios"):
        _fail(problems, "soak.scenarios", "VAL-02 scenario list empty")

    soak = next(
        (s for s in artifact.get("scenarios", []) if str(s.get("scenario", "")).endswith("soak")),
        None,
    )
    if soak is None:
        _fail(problems, "soak.scenario", "no soak scenario present in VAL-02 artifact")
    else:
        actual = soak.get("actual_duration_s", soak.get("duration_s"))
        if not isinstance(actual, (int, float)) or actual < min_soak_seconds:
            _fail(
                problems,
                "soak.duration",
                f"soak actual duration {actual!r}s < required {min_soak_seconds}s "
                "(rehearsal runs must not be accepted as the formal gate)",
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a GA gate report artifact")
    parser.add_argument("--report", required=True, help="ga_gate.py 결과 JSON 경로")
    parser.add_argument("--manifest", default="scripts/commercial_ga_gates.json")
    parser.add_argument("--expected-sha", default=None, help="후보로 고정한 full SHA")
    parser.add_argument("--soak-artifact", default=None, help="VAL-02 결과 JSON 경로")
    parser.add_argument("--min-soak-seconds", type=int, default=28_800)
    args = parser.parse_args()

    report_path = Path(args.report)
    manifest_path = Path(args.manifest)
    if not report_path.is_file():
        print(f"report not found: {report_path}", file=sys.stderr)
        return 2
    if not manifest_path.is_file():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return 2

    problems = verify_gate_report(report, manifest, args.expected_sha)

    if args.soak_artifact:
        soak_path = Path(args.soak_artifact)
        if not soak_path.is_file():
            print(f"soak artifact not found: {soak_path}", file=sys.stderr)
            return 2
        try:
            soak = json.loads(soak_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"invalid soak JSON: {exc}", file=sys.stderr)
            return 2
        problems.extend(verify_soak_artifact(soak, args.min_soak_seconds))

    if problems:
        print(json.dumps({"verdict": "FAIL", "problems": problems}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"verdict": "PASS", "gates": len(report.get("gates", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
