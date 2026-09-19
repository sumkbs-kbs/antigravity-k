"""FR-11 regression: the gate-verifier must reject false approvals.

Covers plan RP-11 R11-04/R11-11 negative fixtures against
``scripts/ga_gate_verify.py``:

- empty or missing gate list cannot pass (``all([])`` approval blocked)
- a required gate missing from the report fails
- status/exit-code inconsistencies and zero durations are flagged
- malformed or mismatched source SHAs are rejected; expected SHA must match
- summary mismatches (false metrics) are rejected
- a 60-second soak rehearsal is rejected when 28,800s is required
- missing artifacts exit non-zero; a healthy report passes
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ga_gate_verify.py"


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ga_gate_verify_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def verifier() -> ModuleType:
    return _load_verifier()


@pytest.fixture()
def manifest() -> dict:
    return {
        "schema_version": 1,
        "dependency_locks": ["uv.lock"],
        "gates": [
            {
                "id": "python-ruff",
                "category": "python_backend",
                "command": ["ruff"],
                "cwd": ".",
                "timeout_seconds": 60,
                "required": True,
                "finding_ids": ["x"],
                "task_ids": ["y"],
            },
            {
                "id": "python-tests",
                "category": "python_backend",
                "command": ["pytest"],
                "cwd": ".",
                "timeout_seconds": 60,
                "required": True,
                "finding_ids": ["x"],
                "task_ids": ["y"],
            },
            {
                "id": "optional-probe",
                "category": "runtime",
                "command": ["true"],
                "cwd": ".",
                "timeout_seconds": 60,
                "required": False,
                "finding_ids": ["x"],
                "task_ids": ["y"],
            },
        ],
    }


def _gate(
    gid: str, *, status: str = "passed", exit_code: int = 0, required: bool = True, duration: float = 1.5
) -> dict:
    return {
        "id": gid,
        "category": "python_backend",
        "command": [gid],
        "cwd": ".",
        "required": required,
        "started_at": "2026-09-11T00:00:00+00:00",
        "finished_at": "2026-09-11T00:00:02+00:00",
        "duration_seconds": duration,
        "exit_code": exit_code,
        "status": status,
        "stdout": "",
        "stderr": "",
    }


def _report(gates: list[dict], *, sha: str = "a" * 40, passed: int | None = None, total: int | None = None) -> dict:
    actual_passed = sum(1 for g in gates if g["status"] == "passed")
    return {
        "schema_version": 1,
        "generated_at": "2026-09-11T00:00:00+00:00",
        "git": {"sha": sha, "dirty": False},
        "gates": gates,
        "summary": {
            "passed": actual_passed if passed is None else passed,
            "failed": len(gates) - actual_passed,
            "required_failed": sum(1 for g in gates if g["required"] and g["status"] != "passed"),
            "total": len(gates) if total is None else total,
        },
    }


class TestGateReportVerification:
    def test_healthy_report_passes(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests")])
        assert verifier.verify_gate_report(report, manifest, None) == []

    def test_empty_gates_rejected(self, verifier: ModuleType, manifest: dict) -> None:
        problems = verifier.verify_gate_report(_report([]), manifest, None)
        assert any("empty or missing gates list" in p for p in problems)

    def test_missing_required_gate_rejected(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff")])  # python-tests missing
        problems = verifier.verify_gate_report(report, manifest, None)
        assert any("python-tests" in p and "required gates not executed" in p for p in problems)

    def test_status_exit_code_mismatch_rejected(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests", exit_code=2)])
        problems = verifier.verify_gate_report(report, manifest, None)
        assert any("status 'passed' but exit_code" in p for p in problems)

    def test_zero_duration_rejected(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests", duration=0)])
        problems = verifier.verify_gate_report(report, manifest, None)
        assert any("implausible duration" in p for p in problems)

    def test_short_sha_rejected(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests")], sha="abc123")
        problems = verifier.verify_gate_report(report, manifest, None)
        assert any("not a full 40-hex sha" in p for p in problems)

    def test_expected_sha_mismatch_rejected(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests")], sha="b" * 40)
        problems = verifier.verify_gate_report(report, manifest, "c" * 40)
        assert any("!= expected" in p for p in problems)

    def test_summary_false_metric_rejected(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests")], passed=7)
        problems = verifier.verify_gate_report(report, manifest, None)
        assert any("summary mismatch" in p for p in problems)

    def test_optional_gate_missing_is_allowed(self, verifier: ModuleType, manifest: dict) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests")])
        assert verifier.verify_gate_report(report, manifest, None) == []

    def test_failed_required_gate_fails_verification(self, verifier: ModuleType, manifest: dict) -> None:
        # Structurally valid but red report must NOT verify green (R11-04).
        report = _report([_gate("python-ruff"), _gate("python-tests", status="failed", exit_code=1)])
        problems = verifier.verify_gate_report(report, manifest, None)
        assert any("required gates failed" in p and "python-tests" in p for p in problems)


class TestSoakArtifactVerification:
    def _soak(self, *, duration: float = 29_000.0, all_pass: bool = True) -> dict:
        return {
            "task_id": "VAL-02",
            "all_pass": all_pass,
            "missing_required": [],
            "scenarios": [
                {"scenario": "SC-6-soak", "pass": True, "actual_duration_s": duration, "duration_s": duration},
                {"scenario": "SC-1-task-cas-race", "pass": True},
            ],
        }

    def test_full_soak_passes(self, verifier: ModuleType) -> None:
        assert verifier.verify_soak_artifact(self._soak(), 28_800) == []

    def test_60s_rehearsal_rejected_as_formal_gate(self, verifier: ModuleType) -> None:
        problems = verifier.verify_soak_artifact(self._soak(duration=60.0), 28_800)
        assert any("soak actual duration" in p and "rehearsal" in p for p in problems)

    def test_all_pass_false_rejected(self, verifier: ModuleType) -> None:
        problems = verifier.verify_soak_artifact(self._soak(all_pass=False), 28_800)
        assert any("all_pass" in p for p in problems)

    def test_missing_required_scenarios_rejected(self, verifier: ModuleType) -> None:
        artifact = self._soak()
        artifact["missing_required"] = ["SC-4", "SC-5"]
        problems = verifier.verify_soak_artifact(artifact, 28_800)
        assert any("missing scenarios" in p for p in problems)

    def test_empty_scenario_list_rejected(self, verifier: ModuleType) -> None:
        artifact = self._soak()
        artifact["scenarios"] = []
        problems = verifier.verify_soak_artifact(artifact, 28_800)
        assert any("scenario list empty" in p or "no soak scenario" in p for p in problems)


class TestCli:
    def test_missing_report_exits_two(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--report", str(tmp_path / "nope.json")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2

    def test_failing_report_exits_one(self, tmp_path: Path) -> None:
        report = _report([_gate("python-ruff")])
        (tmp_path / "r.json").write_text(json.dumps(report), encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "dependency_locks": ["uv.lock"],
            "gates": [
                {"id": "python-ruff", "required": True},
                {"id": "python-tests", "required": True},
            ],
        }
        (tmp_path / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--report",
                str(tmp_path / "r.json"),
                "--manifest",
                str(tmp_path / "m.json"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert '"verdict": "FAIL"' in result.stdout

    def test_missing_soak_artifact_exits_two(self, tmp_path: Path) -> None:
        report = _report([_gate("python-ruff"), _gate("python-tests")])
        (tmp_path / "r.json").write_text(json.dumps(report), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--report",
                str(tmp_path / "r.json"),
                "--soak-artifact",
                str(tmp_path / "missing-val02.json"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2
