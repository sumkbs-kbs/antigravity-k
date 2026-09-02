"""Tests for self_evolution_coordinator — SelfEvolutionCoordinator.

Covers data models, EvolutionResult.summary, should_evolve, _deterministic_validate,
_load_current_system_prompt, get_report, render_markdown_report, last_result.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from antigravity_k.engine.self_evolution_coordinator import (
    EvolutionDecision,
    EvolutionHistory,
    EvolutionResult,
    EvolutionTrigger,
    MutationDomain,
    PerformanceSnapshot,
    SelfEvolutionCoordinator,
)


def _history(coord: SelfEvolutionCoordinator) -> list[EvolutionHistory]:
    return cast(list[EvolutionHistory], getattr(coord, "_history"))


def _deterministic_validate(filepath: str, content: str) -> dict[str, object]:
    validate = cast(
        Callable[[str, str], dict[str, object]],
        cast(object, getattr(SelfEvolutionCoordinator, "_deterministic_validate")),
    )
    return validate(filepath, content)


def _load_prompt(coord: SelfEvolutionCoordinator) -> str:
    load = cast(Callable[[], str], cast(object, getattr(coord, "_load_current_system_prompt")))
    return load()

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEvolutionTrigger:
    def test_values(self):
        assert EvolutionTrigger.QUALITY_FAILURE.value == "quality_failure"
        assert EvolutionTrigger.REPETITIVE_FAILURE.value == "repetitive_failure"
        assert EvolutionTrigger.PATTERN_DETECTED.value == "pattern_detected"
        assert EvolutionTrigger.SCHEDULED.value == "scheduled"
        assert EvolutionTrigger.MANUAL.value == "manual"


class TestMutationDomain:
    def test_values(self):
        assert MutationDomain.SYSTEM_PROMPT.value == "system_prompt"
        assert MutationDomain.SKILL.value == "skill"
        assert MutationDomain.CODE.value == "code"
        assert MutationDomain.CONFIG.value == "config"
        assert MutationDomain.SAMPLING.value == "sampling"
        assert MutationDomain.FEW_SHOT.value == "few_shot"


# ---------------------------------------------------------------------------
# EvolutionResult.summary
# ---------------------------------------------------------------------------


class TestEvolutionResultSummary:
    def test_skipped(self):
        result = EvolutionResult(skipped=True)
        assert "⏭" in result.summary

    def test_rolled_back(self):
        result = EvolutionResult(rolled_back=True, error_message="AST parse failed")
        assert "🔄" in result.summary
        assert "AST parse failed" in result.summary

    def test_success(
        self,
        mutation_domain: MutationDomain = MutationDomain.SYSTEM_PROMPT,
        improvement: float = 0.12,
    ):
        result = EvolutionResult(success=True, mutation_domain=mutation_domain, improvement=improvement)
        assert "✅" in result.summary
        assert "+0.12" in result.summary

    def test_failure(self):
        result = EvolutionResult(error_message="LLM call failed")
        assert "❌" in result.summary
        assert "LLM call failed" in result.summary


# ---------------------------------------------------------------------------
# PerformanceSnapshot defaults
# ---------------------------------------------------------------------------


class TestPerformanceSnapshot:
    def test_defaults(self):
        snap = PerformanceSnapshot()
        assert snap.quality_grade == "A"
        assert snap.quality_score == 1.0
        assert snap.quality_issues == []
        assert snap.tool_calls == []
        assert snap.failure_count == 0


# ---------------------------------------------------------------------------
# EvolutionDecision defaults
# ---------------------------------------------------------------------------


class TestEvolutionDecision:
    def test_defaults(self):
        d = EvolutionDecision()
        assert d.domain == MutationDomain.SYSTEM_PROMPT
        assert d.trigger == EvolutionTrigger.QUALITY_FAILURE
        assert d.confidence == 0.0
        assert d.expected_improvement == 0.0
        assert d.target_file == ""
        assert d.mutation_payload == {}


# ---------------------------------------------------------------------------
# EvolutionHistory
# ---------------------------------------------------------------------------


class TestEvolutionHistory:
    def test_defaults(self):
        h = EvolutionHistory()
        assert h.cycle_id == ""
        assert not h.result.success


# ---------------------------------------------------------------------------
# SelfEvolutionCoordinator — init
# ---------------------------------------------------------------------------


class TestCoordinatorInit:
    def test_default_init(self):
        coord = SelfEvolutionCoordinator()
        assert _history(coord) == []
        assert cast(float, getattr(coord, "_last_evolution_time")) == 0.0
        assert cast(int, getattr(coord, "_turns_since_last_evolution")) == 0
        assert cast(bool, getattr(coord, "_deps_initialized")) is False
        assert cast(object, getattr(coord, "_verify_fn")) is None

    def test_custom_init(self):
        coord = SelfEvolutionCoordinator(
            project_root="/tmp/test",
            verify_fn=lambda x: "verified",
        )
        assert cast(str, getattr(coord, "_root")) == "/tmp/test"
        assert cast(object, getattr(coord, "_verify_fn")) is not None


# ---------------------------------------------------------------------------
# should_evolve
# ---------------------------------------------------------------------------


class TestShouldEvolve:
    def test_grade_not_c_or_f_returns_false(self):
        coord = SelfEvolutionCoordinator()
        assert coord.should_evolve("A") is False
        assert coord.should_evolve("B") is False

    def test_grade_c_returns_true_when_cooldown_passed(self):
        coord = SelfEvolutionCoordinator()
        setattr(coord, "_last_evolution_time", 0)  # never evolved
        setattr(coord, "_turns_since_last_evolution", 10)  # enough turns passed
        assert coord.should_evolve("C") is True

    def test_grade_f_returns_true_when_cooldown_passed(self):
        coord = SelfEvolutionCoordinator()
        setattr(coord, "_last_evolution_time", 0)
        setattr(coord, "_turns_since_last_evolution", 5)
        assert coord.should_evolve("F") is True

    def test_cooldown_turns_not_met_returns_false(self):
        coord = SelfEvolutionCoordinator()
        setattr(coord, "_last_evolution_time", 0)
        setattr(coord, "_turns_since_last_evolution", 1)  # less than EVOLUTION_COOLDOWN_TURNS (3)
        assert coord.should_evolve("C") is False

    def test_retry_and_fail_grades(self):
        coord = SelfEvolutionCoordinator()
        setattr(coord, "_turns_since_last_evolution", 10)
        assert coord.should_evolve("retry") is True
        assert coord.should_evolve("fail") is True


# ---------------------------------------------------------------------------
# record_performance
# ---------------------------------------------------------------------------


class TestRecordPerformance:
    def test_records_snapshot(self):
        coord = SelfEvolutionCoordinator()
        snap = PerformanceSnapshot(user_message="hello", quality_grade="C", quality_score=0.5)
        coord.record_performance(snap)
        assert len(_history(coord)) == 1
        assert _history(coord)[0].snapshot.user_message == "hello"
        assert cast(int, getattr(coord, "_turns_since_last_evolution")) == 1

    def test_max_history_size(self):
        coord = SelfEvolutionCoordinator()
        for i in range(25):
            coord.record_performance(PerformanceSnapshot(user_message=f"msg{i}"))
        assert len(_history(coord)) <= coord.MAX_HISTORY_SIZE
        # oldest entries should be removed (keeps last 20 of 25 = msg5 through msg24)
        assert _history(coord)[0].snapshot.user_message == "msg5"


# ---------------------------------------------------------------------------
# _deterministic_validate (static method)
# ---------------------------------------------------------------------------


class TestDeterministicValidate:
    def test_empty_content(self):
        r = _deterministic_validate("test.py", "")
        assert r["passed"] is False
        reason = r["reason"]
        assert isinstance(reason, str)
        assert "비어 있음" in reason

    def test_valid_python(self):
        r = _deterministic_validate("test.py", "x = 1\ny = x + 1")
        assert r["passed"] is True

    def test_invalid_python(self):
        r = _deterministic_validate("test.py", "if True")
        assert r["passed"] is False
        reason = r["reason"]
        assert isinstance(reason, str)
        assert "문법 오류" in reason

    def test_valid_yaml(self):
        r = _deterministic_validate("config.yaml", "key: value\nnested:\n  sub: 42")
        assert r["passed"] is True

    def test_invalid_yaml(self):
        r = _deterministic_validate("config.yaml", "key: : broken")
        assert r["passed"] is False

    def test_valid_json(self):
        r = _deterministic_validate("data.json", '{"key": "value", "num": 42}')
        assert r["passed"] is True

    def test_invalid_json(self):
        r = _deterministic_validate("data.json", "{key: value}")
        assert r["passed"] is False

    def test_unknown_extension_passes(self):
        r = _deterministic_validate("readme.md", "# Hello")
        assert r["passed"] is True

    def test_whitespace_only_fails(self):
        r = _deterministic_validate("test.py", "   \n  \n")
        assert r["passed"] is False


# ---------------------------------------------------------------------------
# _load_current_system_prompt
# ---------------------------------------------------------------------------


class TestLoadSystemPrompt:
    def test_file_not_found_returns_fallback(self, tmp_path: Path):
        coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
        result = _load_prompt(coord)
        assert "Antigravity-K" in result
        assert "Apple Silicon" in result
        assert len(result) > 50

    def test_loads_from_system_prompt_md(self, tmp_path: Path):
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        _ = (prompt_dir / "system_prompt.md").write_text("Custom system prompt content", encoding="utf-8")
        coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
        result = _load_prompt(coord)
        assert result == "Custom system prompt content"


# ---------------------------------------------------------------------------
# get_report / render_markdown_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_get_report_empty(self):
        coord = SelfEvolutionCoordinator()
        report = coord.get_report()
        assert report["total_evolutions"] == 0
        assert report["last_evolution"] == "never"

    def test_get_report_with_history(self):
        coord = SelfEvolutionCoordinator()
        snap = PerformanceSnapshot(quality_grade="C", quality_score=0.5)
        coord.record_performance(snap)
        result = EvolutionResult(success=True, mutation_domain=MutationDomain.SYSTEM_PROMPT, improvement=0.1)
        _history(coord)[-1].result = result
        report = coord.get_report()
        assert report["total_evolutions"] == 1  # non-skipped result
        assert report["recent_successes"] == 1

    def test_render_markdown_empty(self):
        coord = SelfEvolutionCoordinator()
        md = coord.render_markdown_report()
        assert "Self-Evolution" in md
        assert "총 진화 횟수" in md

    def test_last_result_none_when_empty(self):
        coord = SelfEvolutionCoordinator()
        assert coord.last_result is None

    def test_last_result_with_history(self):
        coord = SelfEvolutionCoordinator()
        coord.record_performance(PerformanceSnapshot())
        result = EvolutionResult(success=True, improvement=0.15)
        _history(coord)[-1].result = result
        assert coord.last_result is not None
        assert coord.last_result.improvement == 0.15
