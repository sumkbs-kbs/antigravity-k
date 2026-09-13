"""CR-13 — 이전 후보 증거 재사용 방지와 불변 artifact.

수용 기준(docs/17 C13-01 ~ C13-05)을 문서 설명이 아니라 **번들을 실제로 만들어 보고
망가뜨려 보는 것**으로 고정한다:

  C13-01 상대 경로 독립 번들      → artifact가 번들 안 `artifacts/<id>/<name>`에 복사되고
         manifest에 절대 경로/호스트 경로 흔적이 없다.
  C13-02 변조/누락/탈출/중복 거부  → 없애고, 고치고, `..`로 탈출시키고, 심볼릭 링크로
         빼돌리고, id를 중복시켜 본다.
  C13-03 SHA/gate/soak 음성       → 다른 후보 SHA·필수 gate 누락/실패·짧은 soak·
         요약 재계산 불일치를 거부한다.
  C13-04 외부 원본 변경에도 유지   → 원본을 바꾸고 지우고 번들을 다른 위치로 옮겨도
         검증된다. `historical` 증거는 gate 근거가 될 수 없다.
  C13-05 redaction/hash 순서·정직성 → hash는 **redaction 이후** 바이트에서 계산되고,
         번들은 스스로 PASS를 주장할 수 없다.

RP-11/RP-13 계약(`tests/test_fr11_gate_verifier.py`, `tests/test_fr13_release_manifest.py`)은
그대로 유지된다 — 이 파일은 그 위에 번들 자기완결성 계약을 더한다.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "scripts" / "evidence_bundle.py"
_CANDIDATE_SHA = "a" * 40
_OTHER_SHA = "b" * 40


@pytest.fixture(scope="module")
def bundle_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evidence_bundle_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _gate_report(path: Path, gates: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"gates": gates}, indent=2), encoding="utf-8")
    return path


def _healthy_gates() -> list[dict[str, object]]:
    return [
        {"id": "python-ruff", "status": "passed", "exit_code": 0, "required": True},
        {"id": "python-tests", "status": "passed", "exit_code": 0, "required": True},
        {"id": "dashboard-lint", "status": "passed", "exit_code": 0, "required": False},
    ]


def _spec(tmp_path: Path, gates: list[dict[str, object]] | None = None, **overrides: object) -> Path:
    """synthetic fixture — 실제 데이터·비밀을 쓰지 않는다."""
    sources = tmp_path / "sources"
    sources.mkdir(exist_ok=True)
    (sources / "release-artifact.bin").write_bytes(b"synthetic release artifact payload")
    report = _gate_report(sources / "gate-report.json", gates if gates is not None else _healthy_gates())
    (sources / "test-run.log").write_text("pytest: 42 passed\n", encoding="utf-8")

    spec: dict[str, object] = {
        "schema_version": 1,
        "bundle_id": "cr13-synthetic",
        "evidence_kind": "release",
        "source_sha": _CANDIDATE_SHA,
        "candidate": {"label": "synthetic-candidate", "version": "0.0.1"},
        "tool": {"name": "evidence_bundle.py", "schema_version": 1},
        "environment": {"platform": "test"},
        "commands": [{"cmd": "pytest -q", "exit": 0}],
        "lockfiles": [],
        "required_gates": ["python-ruff", "python-tests"],
        "soak": {"scenario": "val02-soak", "actual_duration_s": 28_800, "min_seconds": 28_800},
        "redaction": [str(tmp_path)],
        "artifacts": [
            {"id": "gate-report", "role": "gate-report", "source": str(report)},
            {"id": "release-artifact", "role": "package", "source": str(sources / "release-artifact.bin")},
            {"id": "test-run-log", "role": "log", "source": str(sources / "test-run.log")},
        ],
    }
    spec.update(overrides)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec_path


def _build(bundle_tool: ModuleType, tmp_path: Path, name: str = "bundle", **overrides: Any) -> Path:
    spec_path = _spec(tmp_path, **overrides)
    output = tmp_path / name
    bundle_tool.build_bundle(spec_path, output, tmp_path)
    return output


def _verify(bundle_tool: ModuleType, bundle: Path, expected_sha: str | None = None) -> list[str]:
    return bundle_tool.verify_bundle(bundle, expected_sha, None)


def _load_manifest(bundle: Path) -> dict[str, Any]:
    return json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(bundle: Path, manifest: dict[str, Any]) -> None:
    """manifest를 고친 뒤 sidecar를 다시 맞춘다 — 변조 시나리오의 전제."""
    path = bundle / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (bundle / "manifest.sha256").write_text(_sha256(path.read_bytes()) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- C13-01


class TestSelfContainedBundle:
    def test_healthy_bundle_verifies(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)

        assert _verify(bundle_tool, bundle, _CANDIDATE_SHA) == []
        assert (bundle / "manifest.sha256").is_file()

    def test_artifacts_live_inside_the_bundle(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        manifest = _load_manifest(bundle)

        assert manifest["artifact_count"] == 3
        for artifact in manifest["artifacts"]:
            relative = Path(artifact["path"])
            assert not relative.is_absolute()
            assert relative.parts[0] == "artifacts"
            assert artifact["id"] in relative.parts
            assert (bundle / relative).is_file()

    def test_manifest_has_no_host_paths(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """원본이 저장소 밖이어도 manifest는 호스트 경로를 남기지 않는다."""
        bundle = _build(bundle_tool, tmp_path)
        text = (bundle / "manifest.json").read_text(encoding="utf-8")

        assert str(tmp_path) not in text
        assert "/tmp/" not in text
        assert "/Users/" not in text

    def test_absolute_path_in_manifest_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        manifest = _load_manifest(bundle)
        manifest["artifacts"][0]["path"] = str(tmp_path / "sources" / "gate-report.json")
        _write_manifest(bundle, manifest)

        problems = _verify(bundle_tool, bundle)

        assert any("absolute path" in problem for problem in problems), problems


# --------------------------------------------------------------------------- C13-02


class TestTamperRejection:
    def test_missing_artifact_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        victim = bundle / _load_manifest(bundle)["artifacts"][1]["path"]
        victim.unlink()

        assert any("artifact missing" in problem for problem in _verify(bundle_tool, bundle))

    def test_tampered_artifact_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        victim = bundle / _load_manifest(bundle)["artifacts"][1]["path"]
        victim.write_bytes(victim.read_bytes() + b"tampered")

        problems = _verify(bundle_tool, bundle)

        assert any("sha256 mismatch" in problem for problem in problems), problems
        assert any("size mismatch" in problem for problem in problems), problems

    def test_duplicate_artifact_id_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        manifest = _load_manifest(bundle)
        manifest["artifacts"].append(dict(manifest["artifacts"][2]))
        _write_manifest(bundle, manifest)

        assert any("duplicate artifact id" in problem for problem in _verify(bundle_tool, bundle))

    def test_parent_traversal_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        outside = tmp_path / "outside.bin"
        outside.write_bytes(b"outside the bundle")
        manifest = _load_manifest(bundle)
        manifest["artifacts"][1]["path"] = "../outside.bin"
        manifest["artifacts"][1]["sha256"] = _sha256(outside.read_bytes())
        manifest["artifacts"][1]["bytes"] = outside.stat().st_size
        _write_manifest(bundle, manifest)

        assert any("parent traversal" in problem for problem in _verify(bundle_tool, bundle))

    def test_symlink_escape_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        victim = bundle / _load_manifest(bundle)["artifacts"][1]["path"]
        payload = victim.read_bytes()
        real = tmp_path / "moved-outside.bin"
        real.write_bytes(payload)
        victim.unlink()
        victim.symlink_to(real)

        problems = _verify(bundle_tool, bundle)

        assert any("symlink" in problem or "escape" in problem for problem in problems), problems

    def test_manifest_tamper_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """sidecar를 다시 맞추지 않은 편집은 자기 hash에서 걸린다."""
        bundle = _build(bundle_tool, tmp_path)
        manifest = _load_manifest(bundle)
        manifest["source_sha"] = _OTHER_SHA
        (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        assert any("self-hash mismatch" in problem for problem in _verify(bundle_tool, bundle))

    def test_symlinked_source_is_refused_at_build(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "real.bin"
        target.write_bytes(b"payload")
        link = tmp_path / "link.bin"
        link.symlink_to(target)

        with pytest.raises(ValueError, match="symlink"):
            bundle_tool.build_bundle(
                _spec(
                    tmp_path,
                    evidence_kind="reference",
                    artifacts=[{"id": "link", "role": "package", "source": str(link)}],
                    required_gates=[],
                    soak=None,
                ),
                tmp_path / "bundle-symlink",
                tmp_path,
            )


# --------------------------------------------------------------------------- C13-03


class TestCandidateAndGateBinding:
    def test_other_candidate_sha_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)

        problems = _verify(bundle_tool, bundle, _OTHER_SHA)

        assert any("another candidate" in problem for problem in problems), problems

    def test_missing_required_gate_is_refused_at_build(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        gates = [gate for gate in _healthy_gates() if gate["id"] != "python-tests"]

        with pytest.raises(ValueError, match="missing required gates"):
            _build(bundle_tool, tmp_path, name="bundle-missing", gates=gates)

    def test_failed_required_gate_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        gates = _healthy_gates()
        gates[1]["status"] = "failed"
        gates[1]["exit_code"] = 1
        bundle = _build(bundle_tool, tmp_path, gates=gates)

        problems = _verify(bundle_tool, bundle)

        assert any("required gates failed" in problem for problem in problems), problems

    def test_short_soak_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(
            bundle_tool,
            tmp_path,
            soak={"scenario": "val02-soak", "actual_duration_s": 60, "min_seconds": 28_800},
        )

        problems = _verify(bundle_tool, bundle)

        assert any("soak" in problem and "60" in problem for problem in problems), problems

    def test_soak_threshold_can_be_raised_from_the_cli(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)

        assert bundle_tool.verify_bundle(bundle, _CANDIDATE_SHA, 28_800) == []
        assert any("soak" in problem for problem in bundle_tool.verify_bundle(bundle, _CANDIDATE_SHA, 100_000))

    def test_recorded_summary_must_match_the_bundled_report(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """metadata만 PASS로 바꾸는 경로를 막는다 — 요약은 원문에서 재계산된다."""
        bundle = _build(bundle_tool, tmp_path)
        manifest = _load_manifest(bundle)
        manifest["gate_report"]["summary"] = {"passed": 99, "failed": 0, "required_failed": 0, "total": 99}
        _write_manifest(bundle, manifest)

        problems = _verify(bundle_tool, bundle)

        assert any("does not match the bundled gate report" in problem for problem in problems), problems

    def test_historically_failed_gate_cannot_be_relabelled(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """원문(gate report)은 그대로인데 요약만 초록으로 바꾸면 재계산에서 걸린다."""
        gates = _healthy_gates()
        gates[0]["status"] = "failed"
        gates[0]["exit_code"] = 1
        bundle = _build(bundle_tool, tmp_path, gates=gates)
        manifest = _load_manifest(bundle)
        manifest["gate_report"]["summary"] = {"passed": 3, "failed": 0, "required_failed": 0, "total": 3}
        _write_manifest(bundle, manifest)

        problems = _verify(bundle_tool, bundle)

        assert any("does not match the bundled gate report" in problem for problem in problems), problems


# --------------------------------------------------------------------------- C13-04


class TestBundleSurvivesOutsideChange:
    def test_bundle_survives_original_change(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """R03: 원본이 바뀌어도 이미 만든 번들은 그대로 검증된다."""
        bundle = _build(bundle_tool, tmp_path)
        (tmp_path / "sources" / "release-artifact.bin").write_bytes(b"the original changed afterwards")
        (tmp_path / "sources" / "gate-report.json").write_text('{"gates": []}', encoding="utf-8")

        assert _verify(bundle_tool, bundle, _CANDIDATE_SHA) == []

    def test_bundle_verifies_after_relocation_without_sources(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        relocated = tmp_path / "relocated" / "bundle"
        relocated.parent.mkdir()
        shutil.copytree(bundle, relocated)
        shutil.rmtree(bundle)
        shutil.rmtree(tmp_path / "sources")

        assert _verify(bundle_tool, relocated, _CANDIDATE_SHA) == []

    def test_historical_artifact_may_be_carried_as_reference(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "sources").mkdir(exist_ok=True)
        prior = tmp_path / "sources" / "prior-gate-report.json"
        prior.write_text(json.dumps({"gates": _healthy_gates()}), encoding="utf-8")
        spec = _spec(tmp_path)
        payload = json.loads(spec.read_text(encoding="utf-8"))
        payload["artifacts"].append(
            {
                "id": "prior-candidate-gate-report",
                "role": "reference",
                "source": str(prior),
                "historical": True,
                "origin_sha": _OTHER_SHA,
            }
        )
        spec.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        bundle = tmp_path / "bundle-historical"
        bundle_tool.build_bundle(spec, bundle, tmp_path)

        assert _verify(bundle_tool, bundle, _CANDIDATE_SHA) == []

    def test_historical_artifact_may_not_fill_gate_role(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """해시가 같다고 과거 실행이 이번 후보의 실행이 되지 않는다."""
        (tmp_path / "sources").mkdir(exist_ok=True)
        prior = tmp_path / "sources" / "prior-gate-report.json"
        prior.write_text(json.dumps({"gates": _healthy_gates()}), encoding="utf-8")
        spec = _spec(
            tmp_path, artifacts=[{"id": "gate-report", "role": "gate-report", "source": str(prior), "historical": True}]
        )

        with pytest.raises(ValueError, match="historical artifacts may not fill"):
            bundle_tool.build_bundle(spec, tmp_path / "bundle-historical-gate", tmp_path)


# --------------------------------------------------------------------------- C13-05


class TestRedactionAndHonesty:
    def test_bundle_may_not_assert_its_own_verdict(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        manifest = _load_manifest(bundle)
        manifest["manifest_verifier"] = "PASS"
        _write_manifest(bundle, manifest)

        problems = _verify(bundle_tool, bundle)

        assert any("must not assert its own verdict" in problem for problem in problems), problems

    def test_hash_is_computed_after_redaction(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        bundle = _build(bundle_tool, tmp_path)
        manifest = _load_manifest(bundle)
        log = next(item for item in manifest["artifacts"] if item["id"] == "test-run-log")
        content = (bundle / log["path"]).read_bytes()

        assert log["sha256"] == _sha256(content)  # 복사·redaction 이후 바이트
        assert log["redactions"] >= 0

    def test_redaction_removes_host_paths_from_content(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "sources").mkdir(exist_ok=True)
        noisy = tmp_path / "sources" / "noisy.log"
        noisy.write_text(f"built in {tmp_path}/sources and /tmp/ssak-rp13/cleanenv\n", encoding="utf-8")
        spec = _spec(
            tmp_path,
            evidence_kind="reference",
            redaction=[str(tmp_path), "/tmp/ssak-rp13"],
            artifacts=[{"id": "noisy-log", "role": "log", "source": str(noisy)}],
            required_gates=[],
            soak=None,
        )
        bundle = tmp_path / "bundle-redacted"
        bundle_tool.build_bundle(spec, bundle, tmp_path)

        bundled = (bundle / "artifacts" / "noisy-log" / "noisy.log").read_text(encoding="utf-8")

        assert str(tmp_path) not in bundled
        assert "/tmp/ssak-rp13" not in bundled
        assert _verify(bundle_tool, bundle) == []

    def test_host_path_leak_is_rejected(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        """redaction 목록에서 빠진 호스트 경로는 검증에서 걸린다."""
        (tmp_path / "sources").mkdir(exist_ok=True)
        leaky = tmp_path / "sources" / "leaky.log"
        leaky.write_text("logs kept in /tmp/ssak-rp13/some-run\n", encoding="utf-8")
        spec = _spec(
            tmp_path,
            evidence_kind="reference",
            artifacts=[{"id": "leaky-log", "role": "log", "source": str(leaky)}],
            required_gates=[],
            soak=None,
        )
        bundle = tmp_path / "bundle-leak"
        bundle_tool.build_bundle(spec, bundle, tmp_path)

        problems = _verify(bundle_tool, bundle)

        assert any("host path leaked" in problem for problem in problems), problems

    def test_secret_like_content_is_refused_at_build(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "sources").mkdir(exist_ok=True)
        secret = tmp_path / "sources" / "leaked.env"
        secret.write_text("OPENAI_API_KEY=sk-" + "a" * 32 + "\n", encoding="utf-8")
        spec = _spec(
            tmp_path,
            evidence_kind="reference",
            artifacts=[{"id": "leaked-env", "role": "log", "source": str(secret)}],
            required_gates=[],
            soak=None,
        )

        with pytest.raises(ValueError, match="secret-like content"):
            bundle_tool.build_bundle(spec, tmp_path / "bundle-secret", tmp_path)

    def test_invalid_source_sha_is_refused_at_build(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="40-hex"):
            _build(bundle_tool, tmp_path, name="bundle-bad-sha", source_sha="HEAD")


# --------------------------------------------------------------------------- CLI


class TestCommandLine:
    def test_cli_build_and_verify(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        spec_path = _spec(tmp_path)
        bundle = tmp_path / "cli-bundle"
        assert (
            bundle_tool.main(
                ["build", "--spec", str(spec_path), "--output", str(bundle), "--source-root", str(tmp_path)]
            )
            == 0
        )
        assert bundle_tool.main(["verify", "--bundle", str(bundle), "--expected-sha", _CANDIDATE_SHA]) == 0

    def test_cli_verify_fails_on_wrong_candidate(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        spec_path = _spec(tmp_path)
        bundle = tmp_path / "cli-bundle-2"
        bundle_tool.main(["build", "--spec", str(spec_path), "--output", str(bundle), "--source-root", str(tmp_path)])

        assert bundle_tool.main(["verify", "--bundle", str(bundle), "--expected-sha", _OTHER_SHA]) == 1

    def test_cli_reports_missing_bundle(self, bundle_tool: ModuleType, tmp_path: Path) -> None:
        assert bundle_tool.main(["verify", "--bundle", str(tmp_path / "nope")]) == 2
