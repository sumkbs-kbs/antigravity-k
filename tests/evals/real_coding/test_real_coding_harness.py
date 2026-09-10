"""Unit tests for the real coding evaluation harness."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from tests.evals.real_coding.hard_composite_tasks import TASKS, CompositeTask
from tests.evals.real_coding.stability_eval import StabilityResult, run_stability, summarize
from tests.evals.real_coding.unified_tasks import TASKS as UNIFIED_TASKS
from tests.evals.real_coding.unified_tasks import UnifiedTask


def test_unified_tasks_structure() -> None:
    assert len(UNIFIED_TASKS) > 0
    for task in UNIFIED_TASKS:
        assert isinstance(task, UnifiedTask)
        assert task.task_id
        assert task.task_type in {"explore", "web", "code", "answer"}
        assert task.prompt
        assert len(task.must_contain) > 0
        if task.task_type == "code":
            assert task.test_code is not None


def test_composite_tasks_structure() -> None:
    assert len(TASKS) > 0
    for task in TASKS:
        assert isinstance(task, CompositeTask)
        assert task.task_id
        assert task.task_type in {"explore", "web", "code", "answer"}
        assert task.prompt
        assert len(task.must_contain) > 0


def test_summarize_results() -> None:
    results = [
        StabilityResult(task_id="code_impl_decoder", mode="adaptive", passed=True, seconds=1.2),
        StabilityResult(task_id="code_impl_decoder", mode="adaptive", passed=False, seconds=1.5),
        StabilityResult(task_id="code_impl_stack_min", mode="adaptive", passed=True, seconds=0.8),
    ]
    summary = summarize(results)
    assert summary["mode"] == "adaptive"
    assert summary["overall_pass_rate"] == "2/3"
    assert summary["by_task"]["code_impl_decoder"] == "1/2"
    assert summary["by_task"]["code_impl_stack_min"] == "1/1"


def test_run_stability_mocked() -> None:
    single_task = (
        CompositeTask(
            task_id="code_impl_stack_min",
            task_type="code",
            prompt="Implement min_stack",
            must_contain=("min_stack",),
            test_code="def test_ok(): pass",
        ),
    )

    def mock_generate(prompt: str, **kwargs: Any) -> str:
        return "```python\ndef min_stack(): pass\n```"

    with patch("antigravity_k.engine.unified_agent.UnifiedAgent.run") as mock_run:
        from antigravity_k.engine.unified_agent import AgentOutcome, AgentStep

        mock_run.return_value = AgentOutcome(
            task="Implement min_stack",
            answer="def min_stack(): pass",
            steps=[AgentStep("code", "passed")],
            total_seconds=0.3,
            passed=True,
        )

        results = run_stability(
            mock_generate,
            model="mock:latest",
            trials=2,
            mode="adaptive",
            target_tasks=single_task,
        )

        assert len(results) == 2
        assert all(r.passed is True for r in results)
        assert all(r.mode == "adaptive" for r in results)
        assert mock_run.call_count == 2
