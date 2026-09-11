from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "ga_gate.py"
PRODUCTION_MANIFEST = ROOT / "scripts" / "commercial_ga_gates.json"


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


def test_runner_records_invalid_utf8_and_continues(tmp_path: Path) -> None:
    # Given: a required child emits an invalid UTF-8 byte before failing, followed by a marker-writing gate.
    marker = tmp_path / "later-command-ran.txt"
    manifest = tmp_path / "invalid-output.json"
    output = tmp_path / "result.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dependency_locks": ["uv.lock"],
                "gates": [
                    {
                        "id": "invalid-output",
                        "category": "runtime",
                        "command": [
                            sys.executable,
                            "-c",
                            "import os; os.write(1, bytes([255])); raise SystemExit(7)",
                        ],
                        "cwd": ".",
                        "timeout_seconds": 10,
                        "required": True,
                        "finding_ids": ["CORE-06"],
                        "task_ids": ["TRN-02"],
                    },
                    {
                        "id": "after-invalid-output",
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

    # When: the real CLI captures both child processes.
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--manifest", str(manifest), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # Then: the invalid byte is deterministic, exit 7 is mapped, continuation occurs, and valid JSON is complete.
    assert completed.returncode == 1
    assert marker.read_text(encoding="utf-8") == "ran"
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["output_decoding"] == {"encoding": "utf-8", "errors": "backslashreplace"}
    assert [(gate["exit_code"], gate["status"]) for gate in report["gates"]] == [(7, "failed"), (0, "passed")]
    assert report["gates"][0]["stdout"] == "\\xff"
    assert report["summary"]["required_failed"] == 1
    assert list(tmp_path.glob(".result.json.*.tmp")) == []


def test_runner_removes_parent_python_environment_from_gate(tmp_path: Path) -> None:
    # Given: parent Python and package-audit variables that point outside the gate checkout.
    observed = tmp_path / "environment.json"
    manifest = tmp_path / "environment-gate.json"
    output = tmp_path / "result.json"
    variables = ["CONDA_DEFAULT_ENV", "CONDA_PREFIX", "PIPAPI_PYTHON_LOCATION", "PYTHONPATH", "VIRTUAL_ENV"]
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dependency_locks": ["uv.lock"],
                "gates": [
                    {
                        "id": "capture-environment",
                        "category": "python_backend",
                        "command": [
                            sys.executable,
                            "-c",
                            (
                                "import json, os, pathlib; "
                                f"pathlib.Path({str(observed)!r}).write_text(json.dumps("
                                f"{{key: os.environ.get(key) for key in {variables!r}}}))"
                            ),
                        ],
                        "cwd": ".",
                        "timeout_seconds": 10,
                        "required": True,
                        "finding_ids": ["master E2E/Ruff/format"],
                        "task_ids": ["QLT-01"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    parent_environment = os.environ.copy()
    parent_environment.update(dict.fromkeys(variables, "/outside/python"))

    # When: the real runner launches the gate subprocess.
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--manifest", str(manifest), "--output", str(output)],
        cwd=ROOT,
        env=parent_environment,
        capture_output=True,
        text=True,
        check=False,
    )

    # Then: none of the parent interpreter selectors reach the gate.
    assert completed.returncode == 0
    assert json.loads(observed.read_text(encoding="utf-8")) == dict.fromkeys(variables)


def test_production_python_gates_use_frozen_isolated_environments() -> None:
    # Given: the production gate manifest and every command executed through `uv run`.
    manifest = json.loads(PRODUCTION_MANIFEST.read_text(encoding="utf-8"))
    uv_run_commands = [gate["command"] for gate in manifest["gates"] if gate["command"][:2] == ["uv", "run"]]

    # When: their environment-control flags are inspected.
    flags = [set(command[2:]) for command in uv_run_commands]

    # Then: every gate resolves the frozen lock into a disposable environment.
    assert uv_run_commands
    assert all({"--frozen", "--isolated"} <= command_flags for command_flags in flags)
    assert all("--no-sync" not in command_flags for command_flags in flags)


def test_production_build_and_dependency_audit_do_not_use_editable_environment() -> None:
    # Given: the production packaging and Python dependency-audit gates.
    manifest = json.loads(PRODUCTION_MANIFEST.read_text(encoding="utf-8"))
    commands = {gate["id"]: gate["command"] for gate in manifest["gates"]}

    # When / Then: the build rejects workspace sources and the audit uses the shipping-lock helper.
    assert commands["python-basedpyright"][-2:] == ["--level", "error"]
    assert commands["package-build"] == ["uv", "build", "--no-sources"]
    assert commands["dependency-audit-python"] == ["bash", "scripts/audit_python_dependencies.sh"]
