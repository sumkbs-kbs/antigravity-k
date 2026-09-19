"""테스트: RSI 자기개선 엔진과 안전 샌드박스.
====================================
7단계 사이클(관찰→진단→가설→변이→평가→선택→통합)의 수용/롤백/스킵 판정,
위험도 분류, 3중 검증, 이중 감사, 감사 로그 영속화를 검증한다.
"""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.rsi_engine import MutationType, RSIConfig, RSIEngine
from antigravity_k.engine.rsi_sandbox import (
    MutationRecord,
    MutationRisk,
    RSISandbox,
    ValidationResult,
)


def _engine(tmp_path: str) -> RSIEngine:
    engine = RSIEngine(config=RSIConfig(cooldown_sec=0), project_root=tmp_path)
    setattr(engine, "_sandbox", MagicMock())
    archive = MagicMock()
    evolver = MagicMock()
    setattr(archive, "archive", MagicMock())
    setattr(evolver, "evolve_system_prompt", MagicMock(return_value=("진화된 프롬프트", 0.8)))
    setattr(engine, "_archive", archive)
    setattr(engine, "_evolver", evolver)
    return engine


def _archive_call_count(engine: RSIEngine) -> int:
    archive = cast(object, getattr(engine, "_archive"))
    archive_method = cast(object, getattr(archive, "archive"))
    return cast(int, getattr(archive_method, "call_count"))


def _set_evolver_side_effect(engine: RSIEngine, error: Exception) -> None:
    evolver = cast(object, getattr(engine, "_evolver"))
    evolve = cast(object, getattr(evolver, "evolve_system_prompt"))
    setattr(evolve, "side_effect", error)


def _diagnose(engine: RSIEngine, performance_data: dict[str, object], result: object) -> list[str]:
    callback = cast(Callable[[dict[str, object], object], list[str]], getattr(engine, "_diagnose"))
    return callback(performance_data, result)


def _approve(_prompt: str) -> str:
    return "APPROVE: 무리 없음"


def _reject(_prompt: str) -> str:
    return "REJECT: 위험"


def _snapshots(sandbox: RSISandbox) -> list[object]:
    return cast(list[object], getattr(sandbox, "_snapshots"))


# ─── RSI 사이클 판정 ──────────────────────────────────────────────


class TestRSICycleVerdicts:
    def test_improvement_is_accepted_and_archived(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        scores = iter([0.5, 0.7])

        result = engine.run_cycle(benchmark_fn=lambda: next(scores))

        assert result.success is True
        assert abs(result.improvement - 0.2) < 1e-9
        assert result.phase_results["integrate"] == "archived"
        assert _archive_call_count(engine) == 1

    def test_regression_rolls_back_without_archiving(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        scores = iter([0.6, 0.4])

        result = engine.run_cycle(benchmark_fn=lambda: next(scores))

        assert abs(result.improvement + 0.2) < 1e-9
        assert result.success is False
        assert result.rolled_back is True
        assert result.phase_results["integrate"] == "rolled_back"
        assert _archive_call_count(engine) == 0

    def test_meaningless_change_is_skipped(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        scores = iter([0.5, 0.505])

        result = engine.run_cycle(benchmark_fn=lambda: next(scores))

        assert result.success is False
        assert result.phase_results["integrate"] == "skipped"

    def test_failed_mutation_keeps_baseline(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        _set_evolver_side_effect(engine, RuntimeError("evolver down"))
        _ = engine.run_cycle(benchmark_fn=lambda: 0.5)

        result = engine.run_cycle(benchmark_fn=lambda: 0.9)

        # 변이 미적용 → 평가가 기준점 유지 → Δ0 스킵
        mutation = cast(dict[str, object], result.phase_results["mutate"])
        assert mutation["applied"] is False
        assert result.improvement == 0
        assert result.after_score == result.before_score

    def test_benchmark_exception_falls_back_to_defaults(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))

        def broken():
            raise OSError("bench down")

        result = engine.run_cycle(benchmark_fn=broken)

        assert result.before_score == 0.5
        assert result.after_score == 0.5


class TestDiagnoseAndHypothesize:
    def test_keyword_routes_to_sampling_hypothesis_with_top_confidence(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))

        result = engine.run_cycle(
            benchmark_fn=lambda: 0.5,
            performance_data={"weaknesses": ["프롬프트 개선", "sampling error"]},
        )

        # confidence 정렬로 sampling(0.8)이 프롬프트(0.7)보다 우선 적용된다
        assert result.mutation_type == MutationType.SAMPLING.value

    def test_low_baseline_appends_diagnoses(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        weaknesses = _diagnose(engine, {}, SimpleNamespace(before_score=0.3, phase_results={}))

        assert any("벤치마크 점수 저조" in w for w in weaknesses)
        assert any("심각한 성능 저하" in w for w in weaknesses)

    def test_no_weakness_falls_back_to_exploratory(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        weaknesses = _diagnose(engine, {}, SimpleNamespace(before_score=0.9, phase_results={}))

        assert weaknesses == ["특별한 약점 없음 — 탐색적 개선 시도"]


class TestEvolutionLoopAndReports:
    def test_run_evolution_stops_after_three_failures(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        _set_evolver_side_effect(engine, RuntimeError("down"))

        results = engine.run_evolution(max_cycles=10, performance_data={})

        assert len(results) == 3
        assert all(not r.success for r in results)

    def test_empty_report_message(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))

        report = engine.get_evolution_report()

        assert report["cycles"] == 0
        assert "진화 기록 없음" in engine.render_report_markdown()

    def test_markdown_report_after_cycles(self, tmp_path: Path) -> None:
        engine = _engine(str(tmp_path))
        scores = iter([0.5, 0.7])
        _ = engine.run_cycle(benchmark_fn=lambda: next(scores))

        md = engine.render_report_markdown()

        assert "| 총 사이클 | 1 |" in md
        assert "Gen 1" in md


# ─── RSISandbox: 위험도 분류 ──────────────────────────────────────


@pytest.fixture
def sandbox(tmp_path: Path) -> RSISandbox:
    return RSISandbox(project_root=str(tmp_path), audit_dir=str(tmp_path / "audit"))


class TestRiskClassification:
    def test_immutable_files_are_critical(self, sandbox: RSISandbox):
        assert sandbox.is_immutable("x/rsi_sandbox.py") is True
        assert sandbox.classify_risk("deep/path/permission_gate.py", "code") == MutationRisk.CRITICAL

    def test_prompt_and_config_mutations_are_low(self, sandbox: RSISandbox):
        assert sandbox.classify_risk("any/file.py", "prompt") == MutationRisk.LOW
        assert sandbox.classify_risk("any/file.py", "config") == MutationRisk.LOW

    def test_core_engine_files_are_high(self, sandbox: RSISandbox):
        assert sandbox.classify_risk("engine/state_graph.py", "code") == MutationRisk.HIGH

    def test_auto_apply_and_default_are_medium(self, sandbox: RSISandbox):
        assert sandbox.is_auto_apply_allowed("prompt_builder.py") is True
        assert sandbox.classify_risk("prompt_builder.py", "code") == MutationRisk.MEDIUM
        assert sandbox.classify_risk("unknown_module.py", "code") == MutationRisk.MEDIUM


# ─── 3중 검증 ────────────────────────────────────────────────────


class TestValidateMutation:
    def test_syntax_error_short_circuits_to_ast_fail(self, sandbox: RSISandbox):
        results = sandbox.validate_mutation("mod.py", "def broken(:", benchmark_fn=None)

        assert results["ast"] == ValidationResult.FAIL
        assert "tests" not in results

    def test_non_python_absent_file_skips_both_stages(self, sandbox: RSISandbox):
        results = sandbox.validate_mutation("notes.md", "changed", None)

        assert results["ast"] == ValidationResult.SKIP
        assert results["tests"] == ValidationResult.SKIP

    def test_pytest_pass_restores_original_content(
        self,
        sandbox: RSISandbox,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "mod.py"
        _ = target.write_text("VALUE = 1\n", encoding="utf-8")

        class FakeCompleted:
            return_code: int = 0
            stdout: str = ""
            stderr: str = ""

        def fake_runner(*args: object, **kwargs: object) -> FakeCompleted:
            _ = args, kwargs
            return FakeCompleted()

        monkeypatch.setattr("antigravity_k.engine.rsi_sandbox.run_sandboxed_argv", fake_runner)

        results = sandbox.validate_mutation("mod.py", "VALUE = 2\n")

        assert results["tests"] == ValidationResult.PASS
        assert target.read_text(encoding="utf-8") == "VALUE = 1\n"

    def test_pytest_failure_marks_fail_and_restores(
        self,
        sandbox: RSISandbox,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "mod.py"
        _ = target.write_text("VALUE = 1\n", encoding="utf-8")

        class FakeCompleted:
            return_code: int = 1
            stdout: str = ""
            stderr: str = "1 failed"

        def fake_runner(*args: object, **kwargs: object) -> FakeCompleted:
            _ = args, kwargs
            return FakeCompleted()

        monkeypatch.setattr("antigravity_k.engine.rsi_sandbox.run_sandboxed_argv", fake_runner)

        results = sandbox.validate_mutation("mod.py", "VALUE = 2\n")

        assert results["tests"] == ValidationResult.FAIL
        assert target.read_text(encoding="utf-8") == "VALUE = 1\n"

    def test_absent_file_skips_test_stage(self, sandbox: RSISandbox):
        results = sandbox.validate_mutation("ghost/mod.py", "X = 1\n", None)

        assert results["tests"] == ValidationResult.SKIP

    def test_benchmark_gate_pass_fail_and_error(self, sandbox: RSISandbox) -> None:
        def pass_benchmark(_filepath: str, _content: str) -> bool:
            return True

        def fail_benchmark(_filepath: str, _content: str) -> bool:
            return False

        assert sandbox.validate_mutation("a.txt", "x", pass_benchmark)["benchmark"] == (ValidationResult.PASS)
        assert sandbox.validate_mutation("a.txt", "x", fail_benchmark)["benchmark"] == (ValidationResult.FAIL)

        def boom(_filepath: str, _content: str) -> bool:
            raise ValueError("bench")

        assert sandbox.validate_mutation("a.txt", "x", boom)["benchmark"] == (ValidationResult.SKIP)


# ─── 이중 감사 ───────────────────────────────────────────────────


class TestDualAudit:
    def test_single_reject_vetoes_approval(self, sandbox: RSISandbox):
        result = sandbox.dual_audit(
            "f.py",
            "orig",
            "mod",
            audit_fn_1=_approve,
            audit_fn_2=_reject,
        )

        assert result["approved"] is False
        assert "REJECT" in result["auditor_2"]

    def test_shared_fn_runs_once_as_first_auditor(self, sandbox: RSISandbox) -> None:
        calls: list[str] = []

        def auditor(prompt: str) -> str:
            calls.append(prompt)
            return "APPROVE"

        result = sandbox.dual_audit("f.py", "o", "m", audit_fn_1=auditor, audit_fn_2=auditor)

        assert result["approved"] is True
        assert len(calls) == 1
        assert result["auditor_2"] == "skip"

    def test_no_auditors_defaults_to_skip(self, sandbox: RSISandbox) -> None:
        result = sandbox.dual_audit("f.py", "o", "m")

        assert result["approved"] is True
        assert result["auditor_1"] == "skip"

    def test_auditor_exception_recorded_not_fatal(self, sandbox: RSISandbox) -> None:
        def bad(prompt: str) -> str:
            _ = prompt
            raise RuntimeError("llm down")

        result = sandbox.dual_audit("f.py", "o", "m", audit_fn_1=bad)

        assert "error:" in result["auditor_1"]
        assert result["approved"] is True


# ─── 안전 컨텍스트 & 감사 로그 ───────────────────────────────────


class TestSafeMutationAndAuditLog:
    def test_safe_mutation_yields_snapshot(self, sandbox: RSISandbox) -> None:
        with sandbox.safe_mutation("label-1") as snapshot:
            assert snapshot.snapshot_id.startswith("rsi_")
            assert _snapshots(sandbox)[-1] is snapshot

    def test_safe_mutation_rolls_back_on_error(
        self,
        sandbox: RSISandbox,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        rollbacks: list[object] = []

        def rollback(snapshot: object) -> None:
            rollbacks.append(snapshot)

        monkeypatch.setattr(sandbox, "rollback_to", rollback)

        with pytest.raises(RuntimeError), sandbox.safe_mutation("boom"):
            raise RuntimeError("mutate failed")

        assert len(rollbacks) == 1

    def test_mutation_log_persists_across_instances(
        self,
        sandbox: RSISandbox,
        tmp_path: Path,
    ) -> None:
        record = MutationRecord(
            mutation_id="m1",
            timestamp=1.0,
            target_file="a.py",
            mutation_type="code",
            risk_level="medium",
            before_hash="aa",
            after_hash="bb",
        )
        sandbox.record_mutation(record)

        revived = RSISandbox(project_root=str(tmp_path), audit_dir=str(tmp_path / "audit"))

        assert revived.get_mutation_history()[-1]["mutation_id"] == "m1"  # history는 dict 목록
        stats = revived.get_stats()
        assert stats["total_mutations"] == 1
