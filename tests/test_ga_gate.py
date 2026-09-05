from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "ga_gate.py"


def test_runner_continues_after_required_failure_and_returns_nonzero(tmp_path: Path) -> None:
    # Given: a real manifest whose first command fails and whose second command writes a marker.
    marker = tmp_path / "later-command-ran.txt"
    manifest = tmp_path / "gates.json"
    output = tmp_path / "result.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dependency_locks": ["uv.lock"],
                "gates": [
                    {
                        "id": "expected-failure",
                        "category": "python_backend",
                        "command": [sys.executable, "-c", "raise SystemExit(7)"],
                        "cwd": ".",
                        "timeout_seconds": 10,
                        "required": True,
                        "finding_ids": ["master E2E/Ruff/format"],
                        "task_ids": ["QLT-01"],
                    },
                    {
                        "id": "later-pass",
                        "category": "runtime",
                        "command": [
                            sys.executable,
                            "-c",
                            f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')",
                        ],
                        "cwd": ".",
                        "timeout_seconds": 10,
                        "required": True,
                        "finding_ids": ["CORE-06"],
                        "task_ids": ["TRN-02"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    # When: the CLI runs the manifest through actual subprocesses.
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--manifest", str(manifest), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # Then: the later command ran, both results were persisted, and the CLI failed overall.
    assert completed.returncode == 1
    assert marker.read_text(encoding="utf-8") == "ran"
    report = json.loads(output.read_text(encoding="utf-8"))
    assert [gate["exit_code"] for gate in report["gates"]] == [7, 0]
    assert report["summary"] == {"failed": 1, "passed": 1, "required_failed": 1, "total": 2}
    assert len(report["git"]["sha"]) == 40
    assert report["platform"]["python_version"]
    assert report["dependency_locks"] == [{"path": "uv.lock", "sha256": report["dependency_locks"][0]["sha256"]}]
    assert len(report["dependency_locks"][0]["sha256"]) == 64


def test_runner_rejects_unmapped_gate_before_execution(tmp_path: Path) -> None:
    # Given: a manifest gate with no audit finding or remediation task mapping.
    manifest = tmp_path / "unmapped.json"
    output = tmp_path / "result.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dependency_locks": ["uv.lock"],
                "gates": [
                    {
                        "id": "unmapped",
                        "category": "security",
                        "command": ["/usr/bin/true"],
                        "cwd": ".",
                        "timeout_seconds": 10,
                        "required": True,
                        "finding_ids": [],
                        "task_ids": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # When: the real CLI parses the untrusted manifest boundary.
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--manifest", str(manifest), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # Then: validation fails before any result artifact can claim a gate outcome.
    assert completed.returncode == 2
    assert not output.exists()
