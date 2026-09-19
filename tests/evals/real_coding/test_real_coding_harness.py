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


def test_automation_tasks_structure() -> None:
    from tests.evals.real_coding.automation_tasks import TASKS as AUTOMATION_TASKS
    from tests.evals.real_coding.automation_tasks import AutomationTask

    assert len(AUTOMATION_TASKS) > 0
    for t in AUTOMATION_TASKS:
        assert isinstance(t, AutomationTask)
        assert t.task_id
        assert t.prompt
        assert t.verify


def test_swe_tasks_structure() -> None:
    from tests.evals.real_coding.swe_tasks import TASKS as SWE_TASKS
    from tests.evals.real_coding.swe_tasks import SWETask

    assert len(SWE_TASKS) > 0
    for t in SWE_TASKS:
        assert isinstance(t, SWETask)
        assert t.task_id
        assert t.scenario
        assert t.buggy_code
        assert t.test_code


def test_multi_dependency_tasks_structure() -> None:
    from tests.evals.real_coding.multi_dependency_tasks import TASKS as DEP_TASKS
    from tests.evals.real_coding.multi_dependency_tasks import DependencyTask

    assert len(DEP_TASKS) > 0
    for t in DEP_TASKS:
        assert isinstance(t, DependencyTask)
        assert t.task_id
        assert t.scenario
        assert t.module_code
        assert t.test_code


def test_web_grounded_tasks_structure() -> None:
    from tests.evals.real_coding.web_grounded_tasks import TASKS as WEB_TASKS
    from tests.evals.real_coding.web_grounded_tasks import GroundedQATask

    assert len(WEB_TASKS) > 0
    for t in WEB_TASKS:
        assert isinstance(t, GroundedQATask)
        assert t.task_id
        assert t.question
        assert len(t.must_contain) > 0


def test_scale_tasks_structure() -> None:
    from tests.evals.real_coding.scale_tasks import TASKS as SCALE_TASKS
    from tests.evals.real_coding.scale_tasks import ScaleQuestion

    assert len(SCALE_TASKS) > 0
    for t in SCALE_TASKS:
        assert isinstance(t, ScaleQuestion)
        assert t.qid
        assert t.question
        assert len(t.expected_symbols) > 0
        assert len(t.expected_files) > 0


def test_coding_tasks_structure() -> None:
    from tests.evals.real_coding.tasks import TASKS as CODING_TASKS
    from tests.evals.real_coding.tasks import CodingTask

    assert len(CODING_TASKS) > 0
    for t in CODING_TASKS:
        assert isinstance(t, CodingTask)
        assert t.task_id
        assert t.problem
        assert t.test_code
        assert t.expected_solution


def test_eval_summarizers() -> None:
    from tests.evals.real_coding.composite_eval import CompositeResult
    from tests.evals.real_coding.composite_eval import summarize as summarize_composite
    from tests.evals.real_coding.unified_eval import UnifiedResult
    from tests.evals.real_coding.unified_eval import summarize as summarize_unified
    from tests.evals.real_coding.web_grounded_eval import QAResult
    from tests.evals.real_coding.web_grounded_eval import summarize as summarize_web

    # Unified eval summarize
    u_res = [
        UnifiedResult("t1", "code", True, False, True, 1.0, 2),
        UnifiedResult("t2", "web", True, True, False, 0.8, 1),
    ]
    u_sum = summarize_unified(u_res)
    assert u_sum["total"] == 2
    assert u_sum["passed"] == 2
    assert u_sum["used_web"] == 1
    assert u_sum["used_graphify"] == 1

    # Composite eval summarize
    c_res = [
        CompositeResult("c1", "code", True, False, True, 1.2),
        CompositeResult("c2", "explore", False, False, True, 0.5),
    ]
    c_sum = summarize_composite(c_res)
    assert c_sum["total"] == 2
    assert c_sum["passed"] == 1

    # Web eval summarize
    w_res = [
        QAResult("w1", True, True),
        QAResult("w2", False, False),
    ]
    w_sum = summarize_web(w_res)
    assert w_sum["total"] == 2
    assert w_sum["passed"] == 1
    assert w_sum["web_tasks"]["total"] == 1
    assert w_sum["local_tasks"]["total"] == 1
