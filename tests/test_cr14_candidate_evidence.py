"""CR-14 — 최종 후보 전체 검증과 GO/NO-GO의 **기계가 검사할 수 있는 부분**.

CR-13은 번들 자기완결성을 만들었지만 마지막에 우회로를 남겼다: `required_gates`를
비워 두면 검증기가 gate 검사를 **통째로 건너뛰었다**. 그래서 "gate를 하나도 선언하지
않은 번들"이 `PASS`로 통과할 수 있었다. CR-14는 그 구멍을 계약으로 닫는다:

  C14-01 종류 고정    `evidence_kind`는 필수다(`release`|`reference`). `release`는
         `required_gates`가 비면 build·verify 모두 거부하고, `reference`는
         `required_gates`가 비어 있어야 하며 CLI가 `PASS` 대신 `REFERENCE_ONLY`
         (exit 3)를 낸다. 즉 참고 번들은 어떤 경로로도 승인이 되지 않는다.

  C14-01b 단계별 실행  20개 gate는 한 프로세스 창에 다 들어가지 않는다.
         `ga_gate.py --merge-into`가 이어받되 **같은 후보·같은 manifest**만
         허용한다. 합쳐진 보고서가 검증기를 통과하는지까지 확인한다.

  C14-01c 인벤토리     CR-14 증거 spec의 `required_gates`는 gate manifest의
         required 목록과 **정확히 같아야** 한다. 숫자를 맞추려고 검사를 빼는 경로를
         막는다(docs/16 CR-14: "숫자 20에 맞추려고 새 검사를 제외하지 않는다").

이 파일은 판정 자체(GO/NO-GO)를 만들지 않는다. 판정은 증거와 외부 조건을 사람이
확인해 기록한다. 여기서 고정하는 것은 그 판정이 **위조될 수 없다**는 사실이다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_SCRIPT = REPO_ROOT / "scripts" / "evidence_bundle.py"
_GATE_SCRIPT = REPO_ROOT / "scripts" / "ga_gate.py"
_GATE_VERIFIER = REPO_ROOT / "scripts" / "ga_gate_verify.py"
_GATE_MANIFEST = REPO_ROOT / "scripts" / "commercial_ga_gates.json"
_CR14_DIR = REPO_ROOT / ".omo" / "evidence" / "commercial-reliability" / "CR-14" / "attempt-001"
_CR14_SPEC = _CR14_DIR / "bundle-spec.json"
_CR14_INVENTORY = _CR14_DIR / "logs" / "gate-inventory.json"
_CANDIDATE_SHA = "c" * 40
_OTHER_SHA = "d" * 40


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bundle_tool() -> ModuleType:
    return _load("cr14_evidence_bundle_under_test", _BUNDLE_SCRIPT)


@pytest.fixture(scope="module")
def gate_runner() -> ModuleType:
    return _load("cr14_ga_gate_under_test", _GATE_SCRIPT)


@pytest.fixture(scope="module")
def gate_verifier() -> ModuleType:
    return _load("cr14_ga_gate_verify_under_test", _GATE_VERIFIER)


def _sources(tmp_path: Path) -> Path:
    sources = tmp_path / "sources"
    sources.mkdir(exist_ok=True)
    (sources / "gate-report.json").write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "python-ruff", "status": "passed", "exit_code": 0, "required": True},
                    {"id": "python-tests", "status": "passed", "exit_code": 0, "required": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    (sources / "run.log").write_text("pytest: 42 passed\n", encoding="utf-8")
    return sources


def _spec(tmp_path: Path, **overrides: Any) -> Path:
    sources = _sources(tmp_path)
    spec: dict[str, Any] = {
        "schema_version": 1,
        "bundle_id": "cr14-synthetic",
        "evidence_kind": "release",
        "source_sha": _CANDIDATE_SHA,
        "candidate": {"label": "synthetic-candidate", "version": "0.0.1"},
        "tool": {"name": "evidence_bundle.py", "schema_version": 1},
        "environment": {"platform": "test"},
        "commands": [{"cmd": "pytest -q", "exit": 0}],
        "lockfiles": [],
        "required_gates": ["python-ruff", "python-tests"],
        "soak": None,
        "redaction": [str(tmp_path)],
        "artifacts": [
            {"id": "gate-report", "role": "gate-report", "source": str(sources / "gate-report.json")},
            {"id": "run-log", "role": "log", "source": str(sources / "run.log")},
        ],
    }
    spec.update(overrides)
    for key, value in overrides.items():
        if value is None:
            spec.pop(key, None)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec_path


def _manifest_of(gate_runner: ModuleType, gate_ids: list[str]) -> Any:
    payload = {
        "schema_version": 1,
        "dependency_locks": ["uv.lock"],
        "gates": [
            {
                "id": gate_id,
                "category": "python_backend",
                "command": ["true"],
                "cwd": ".",
                "timeout_seconds": 60,
                "required": True,
                "finding_ids": ["CR-14"],
                "task_ids": ["CR-14"],
            }
            for gate_id in gate_ids
        ],
    }
    return gate_runner.Manifest.model_validate(payload)


# --------------------------------------------------------------- C14-01 kind


class TestEvidenceKindIsMandatory:
    def test_build_refuses_a_spec_without_evidence_kind(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="evidence_kind"):
            bundle_tool.build_bundle(_spec(tmp_path, evidence_kind=None), tmp_path / "bundle", tmp_path)

    def test_build_refuses_an_unknown_evidence_kind(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="evidence_kind"):
            bundle_tool.build_bundle(_spec(tmp_path, evidence_kind="approval"), tmp_path / "bundle", tmp_path)

    def test_release_evidence_must_declare_required_gates(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """CR-13 우회로: 빈 gate 목록으로 승인받던 경로를 build에서 막는다."""
        with pytest.raises(ValueError, match="required_gates"):
            bundle_tool.build_bundle(
                _spec(
                    tmp_path,
                    required_gates=[],
                    artifacts=[{"id": "run-log", "role": "log", "source": str(tmp_path / "sources" / "run.log")}],
                ),
                tmp_path / "bundle",
                tmp_path,
            )

    def test_reference_evidence_must_not_declare_required_gates(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="reference evidence must not declare required_gates"):
            bundle_tool.build_bundle(_spec(tmp_path, evidence_kind="reference"), tmp_path / "bundle", tmp_path)

    def test_gate_id_list_is_normalised_strictly(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="duplicates"):
            bundle_tool.build_bundle(
                _spec(tmp_path, required_gates=["python-ruff", "python-ruff"]), tmp_path / "bundle", tmp_path
            )
        with pytest.raises(ValueError, match="empty gate ids"):
            bundle_tool.build_bundle(
                _spec(tmp_path, required_gates=["python-ruff", "  "]), tmp_path / "bundle", tmp_path
            )

    def test_reference_evidence_may_not_carry_a_fresh_gate_report(
        self, bundle_tool: ModuleType, tmp_path: Path
    ) -> None:
        sources = tmp_path / "sources"
        with pytest.raises(ValueError, match="may not carry a fresh gate report"):
            bundle_tool.build_bundle(
                _spec(
                    tmp_path,
                    evidence_kind="reference",
                    required_gates=[],
                    artifacts=[
                        {"id": "gate-report", "role": "gate-report", "source": str(sources / "gate-report.json")}
                    ],
                ),
                tmp_path / "bundle",
                tmp_path,
            )


class TestEmptyGateListCanNoLongerApprove:
    def test_untyped_manifest_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = tmp_path / "bundle"
        bundle_tool.build_bundle(_spec(tmp_path), bundle, tmp_path)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("evidence_kind")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _refresh_sidecar(bundle)

        problems = bundle_tool.verify_bundle(bundle, _CANDIDATE_SHA, None)

        assert any("evidence_kind" in problem for problem in problems), problems

    def test_emptied_required_gates_can_no_longer_skip_gate_checks(
        self, bundle_tool: ModuleType, tmp_path: Path
    ) -> None:
        """변조로 `required_gates`를 비워 gate 검사를 건너뛰던 경로가 닫혔는지."""
        bundle = tmp_path / "bundle"
        bundle_tool.build_bundle(_spec(tmp_path), bundle, tmp_path)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["required_gates"] = []
        manifest["gate_report"] = None
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _refresh_sidecar(bundle)

        problems = bundle_tool.verify_bundle(bundle, _CANDIDATE_SHA, None)

        assert any("declares no required gates" in problem for problem in problems), problems

    def test_reference_bundle_is_never_approvable_from_the_cli(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        spec_path = _spec(
            tmp_path,
            evidence_kind="reference",
            required_gates=[],
            artifacts=[{"id": "run-log", "role": "log", "source": str(tmp_path / "sources" / "run.log")}],
        )
        bundle = tmp_path / "reference-bundle"
        assert (
            bundle_tool.main(
                ["build", "--spec", str(spec_path), "--output", str(bundle), "--source-root", str(tmp_path)]
            )
            == 0
        )

        exit_code = bundle_tool.main(["verify", "--bundle", str(bundle), "--expected-sha", _CANDIDATE_SHA])

        assert exit_code == bundle_tool.EXIT_REFERENCE_ONLY != 0, exit_code

    def test_release_bundle_still_returns_the_approvable_exit_code(
        self, bundle_tool: ModuleType, tmp_path: Path
    ) -> None:
        bundle = tmp_path / "release-bundle"
        assert (
            bundle_tool.main(
                ["build", "--spec", str(_spec(tmp_path)), "--output", str(bundle), "--source-root", str(tmp_path)]
            )
            == 0
        )

        assert (
            bundle_tool.main(["verify", "--bundle", str(bundle), "--expected-sha", _CANDIDATE_SHA])
            == bundle_tool.EXIT_APPROVABLE
        )


def _refresh_sidecar(bundle: Path) -> None:
    import hashlib

    manifest_path = bundle / "manifest.json"
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (bundle / "manifest.sha256").write_text(digest + "\n", encoding="utf-8")

    # ------------------------------------------------------- C14-01b staged gate runsclass TestStagedGateRuns:
    def _report(self, tmp_path: Path, **git: object) -> Path:
        report = tmp_path / "report.json"
        report.write_text(
            json.dumps(
                {
                    "git": {"sha": _CANDIDATE_SHA, "tree_fingerprint": "9" * 64, **git},
                    "manifest": {"sha256": "f" * 64},
                    "gates": [{"id": "python-ruff", "status": "passed"}],
                }
            ),
            encoding="utf-8",
        )
        return report

    def test_carried_results_must_belong_to_the_same_candidate(self, gate_runner: ModuleType, tmp_path: Path) -> None:
        report = self._report(tmp_path, sha=_OTHER_SHA)

        with pytest.raises(gate_runner._CarriedError, match="not"):
            gate_runner._load_carried_gates(report, _CANDIDATE_SHA, "f" * 64, "9" * 64)

    def test_carried_results_must_come_from_the_same_manifest(self, gate_runner: ModuleType, tmp_path: Path) -> None:
        report = self._report(tmp_path)

        with pytest.raises(gate_runner._CarriedError, match="gate manifest"):
            gate_runner._load_carried_gates(report, _CANDIDATE_SHA, "e" * 64, "9" * 64)

    def test_carried_results_must_come_from_the_same_working_tree(
        self, gate_runner: ModuleType, tmp_path: Path
    ) -> None:
        """미커밋 후보에서 다른 코드 상태의 초록을 이어 붙이는 경로를 막는다."""
        report = self._report(tmp_path)

        with pytest.raises(gate_runner._CarriedError, match="different working tree"):
            gate_runner._load_carried_gates(report, _CANDIDATE_SHA, "f" * 64, "8" * 64)

    def test_untracked_and_modified_content_changes_the_fingerprint(
        self, gate_runner: ModuleType, tmp_path: Path
    ) -> None:
        import subprocess

        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        tracked = root / "tracked.txt"
        tracked.write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
        before = gate_runner._tree_fingerprint(root)

        tracked.write_text("two\n", encoding="utf-8")
        assert gate_runner._tree_fingerprint(root) != before

        (root / "untracked.txt").write_text("new\n", encoding="utf-8")
        after_untracked = gate_runner._tree_fingerprint(root)
        assert after_untracked != before

        (root / "untracked.txt").unlink()
        assert gate_runner._tree_fingerprint(root) == gate_runner._tree_fingerprint(root)

    def test_documentation_changes_do_not_invalidate_gate_evidence(
        self, gate_runner: ModuleType, tmp_path: Path
    ) -> None:
        """결과 문서·증거를 쓰는 것만으로 gate 결과가 낡으면 안 된다(계획 §CR-14 8)."""
        import subprocess

        root = tmp_path / "repo"
        (root / "docs").mkdir(parents=True)
        (root / ".omo" / "evidence").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / "code.py").write_text("x = 1\n", encoding="utf-8")
        (root / "docs" / "REPORT.md").write_text("before\n", encoding="utf-8")
        (root / ".omo" / "evidence" / "run.json").write_text("{}\n", encoding="utf-8")
        before = gate_runner._tree_fingerprint(root)

        (root / "docs" / "REPORT.md").write_text("after\n", encoding="utf-8")
        (root / ".omo" / "evidence" / "run.json").write_text('{"a": 1}\n', encoding="utf-8")
        assert gate_runner._tree_fingerprint(root) == before

        (root / "code.py").write_text("x = 2\n", encoding="utf-8")
        assert gate_runner._tree_fingerprint(root) != before

    def test_missing_previous_report_is_not_an_error(self, gate_runner: ModuleType, tmp_path: Path) -> None:
        assert gate_runner._load_carried_gates(tmp_path / "absent.json", _CANDIDATE_SHA, "f" * 64, "9" * 64) == {}

    def test_merged_report_follows_manifest_order_and_verifies(
        self, gate_runner: ModuleType, gate_verifier: ModuleType, tmp_path: Path
    ) -> None:
        manifest = _manifest_of(gate_runner, ["python-ruff", "python-format", "python-tests"])
        carried = {
            "python-tests": {"id": "python-tests", "status": "passed", "exit_code": 0, "required": True},
            "python-ruff": {"id": "python-ruff", "status": "passed", "exit_code": 0, "required": True},
        }

        ordered = gate_runner._ordered_gates(manifest, carried)

        assert [gate["id"] for gate in ordered] == ["python-ruff", "python-tests"]
        assert gate_runner._summary(ordered) == {"failed": 0, "passed": 2, "required_failed": 0, "total": 2}

        # 합쳐진 보고서가 검증기를 통과하려면 실행 기록이 실제로 있어야 한다.
        staged = [
            {
                **gate,
                "started_at": "2026-09-12T00:00:00+00:00",
                "finished_at": "2026-09-12T00:00:01+00:00",
                "duration_seconds": 1.0,
            }
            for gate in ordered
        ]
        report = {
            "gates": staged,
            "git": {"sha": _CANDIDATE_SHA},
            "summary": gate_runner._summary(staged),
        }
        manifest_payload = {"gates": [{"id": gate_id, "required": True} for gate_id in ("python-ruff", "python-tests")]}

        assert gate_verifier.verify_gate_report(report, manifest_payload, _CANDIDATE_SHA) == []

    def test_a_same_id_rerun_replaces_the_carried_result(self, gate_runner: ModuleType) -> None:
        manifest = _manifest_of(gate_runner, ["python-ruff"])
        carried = {"python-ruff": {"id": "python-ruff", "status": "failed", "exit_code": 1, "required": True}}
        carried["python-ruff"] = {"id": "python-ruff", "status": "passed", "exit_code": 0, "required": True}

        assert gate_runner._summary(gate_runner._ordered_gates(manifest, carried))["passed"] == 1


# --------------------------------------------------------- C14-01c inventory


# CR-14 필수 gate 인벤토리 — **의도적으로** 여기에 pinned 한다.
#
# 왜 개수가 아니라 목록인가: 이 계약의 목적은 "검사가 조용히 사라지는 경로를 막는 것"이다.
# 숫자만 고정하면 하나를 빼고 하나를 넣어도 통과한다.
#
# 왜 20 → 21 인가 (CR-14 F-21, attempt-013): `python-tests` 가 wall-clock 임계값까지 재고 있었다.
# 고립 실행에서는 2209ms 인 테스트가 6200여 개를 도는 프로세스 안에서는 6084ms 로 임계값(6000ms)을
# 넘겼다 — 머신 부하가 required 게이트를 깨는 구조였다. 검사를 **빼는 대신 옮겼다**: 기능 게이트는
# `-m "not benchmark"`, 전용 `python-benchmark` 게이트가 `-m benchmark` 로 조용한 프로세스에서 돈다.
# 그래서 개수가 늘었고, 이 목록을 함께 고치는 것이 이번 변경의 기록이다.
#
# 왜 21 → 22 인가 (CR-14 F-42, attempt-032): 저장소에는 **브라우저 증인**이 있었는데
# (`dashboard/e2e/tests/cr*.spec.ts` — CR-05/06/07/08/09/10/14 의 제품 경로 증인),
# required 21개 중 **어느 것도 그것들을 돌리지 않았다**(`accessibility-e2e` 는
# `accessibility.spec.ts` 한 파일만 실행한다). 그래서 21/21 초록은 브라우저 슬라이스를
# 한 번도 주장하지 않았고, 그 증인들은 **사람이 기억해서 돌려야만** 돌았다 —
# attempt-030/031 이 F-39·F-41 을 닫을 때 쓴 자리가 정확히 그 자리다.
# 검사를 **빼는 대신 게이트를 세웠다**: `dashboard-e2e-witnesses` 가 그 패밀리를 돈다.
#
# 왜 22 → 23 인가 (CR-14 F-46, attempt-034): ambient 백엔드가 필요한 Playwright 스펙
# (`task-execution`·`ws-contract-e2e`·`file-explorer`·일부 `capture-*`)이 어느 required
# 게이트에도 없었다. 새 required 게이트 `dashboard-e2e-ambient` 가 서버를 세운 뒤 그
# 패밀리를 돈다(스크립트 `scripts/run_dashboard_e2e_ambient.py`). Vite-only
# (`capture-disclosure-*` → :5173 하드코드)는 삼키지 않는다(F-47).
_EXPECTED_REQUIRED_GATES = (
    # python_backend (6)
    "python-ruff",
    "python-format",
    "python-mypy",
    "python-basedpyright",
    "python-tests",
    "python-benchmark",
    # dashboard (5)
    "dashboard-install",
    "dashboard-lint",
    "dashboard-typecheck",
    "dashboard-test",
    "dashboard-build",
    # package / container (2)
    "package-build",
    "docker-build",
    # supply chain (3)
    "sbom-generate",
    "dependency-audit-python",
    "dependency-audit-dashboard",
    # security (1)
    "security-bandit",
    # runtime / release (5)
    "master-e2e",
    "api-e2e",
    "accessibility-e2e",
    "dashboard-e2e-witnesses",
    "dashboard-e2e-ambient",
    "clean-machine-runtime",
)


class TestCandidateGateInventory:
    def test_repository_gate_manifest_required_gates_are_the_pinned_inventory(self) -> None:
        """현재 manifest 의 필수 gate 집합이 pinned 목록과 같다.

        F-21 로 21개가 됐고, F-42 로 22개가 됐고, F-46 로 **23개**가 됐다. 앞으로 늘거나 줄면 이 목록을 함께 고쳐야
        한다 — 즉 변경이 **의도된 편집**으로만 가능하고, 우연히 사라지는 경로는 없다.
        """
        manifest = json.loads(_GATE_MANIFEST.read_text(encoding="utf-8"))
        required = sorted(gate["id"] for gate in manifest["gates"] if gate["required"])

        assert required == sorted(_EXPECTED_REQUIRED_GATES), required

    def test_cr14_recorded_inventory_is_never_removed_from_the_gate_manifest(self) -> None:
        """기록된 인벤토리(attempt-001)의 gate 가 manifest 에서 사라지거나 강등되지 않는다.

        기록 이후의 **추가**는 허용한다(위 pinned 목록이 그 자리를 지킨다) — 금지하는 것은
        기록에 있던 검사를 빼는 일이다. attempt-001 의 기록은 역사이므로 고치지 않는다.
        """
        if not _CR14_INVENTORY.is_file():
            pytest.skip("CR-14 gate inventory not generated in this checkout")

        manifest = json.loads(_GATE_MANIFEST.read_text(encoding="utf-8"))
        inventory = json.loads(_CR14_INVENTORY.read_text(encoding="utf-8"))

        assert all(gate["required"] for gate in inventory), "a required gate was demoted in the record"

        required = {gate["id"] for gate in manifest["gates"] if gate["required"]}
        recorded = {gate["id"] for gate in inventory}
        removed = sorted(recorded - required)
        assert not removed, f"기록에 있던 필수 gate 가 manifest 에서 사라졌다(또는 강등됐다): {removed}"

    def test_cr14_bundle_never_claims_an_approval_it_did_not_earn(self, bundle_tool: ModuleType) -> None:
        """증거 번들이 있으면 그 종류를 실제로 확인한다 — 부분 실행을 승인으로 올리지 않는다."""
        bundle = _CR14_DIR / "bundle"
        if not (bundle / "manifest.json").is_file():
            pytest.skip("CR-14 evidence bundle not generated in this checkout")

        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        reports = sorted(_CR14_DIR.glob("gate-report-part*.json"))
        executed = {
            gate["id"]
            for report_path in reports
            for gate in json.loads(report_path.read_text(encoding="utf-8"))["gates"]
        }
        declared = set(manifest.get("required_gates") or [])

        if declared:
            # 승인 주장을 하려면 선언한 gate가 모두 실행됐고 전부 통과해야 한다.
            assert declared <= executed, sorted(declared - executed)
            assert manifest["evidence_kind"] == bundle_tool.RELEASE_KIND
        else:
            assert manifest["evidence_kind"] == bundle_tool.REFERENCE_KIND
            assert bundle_tool.main(["verify", "--bundle", str(bundle)]) == bundle_tool.EXIT_REFERENCE_ONLY
