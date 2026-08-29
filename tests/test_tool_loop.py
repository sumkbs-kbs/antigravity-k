"""Tests for tool_loop.py — ToolLoopEngine.

Covers:
- __init__ with mock orchestrator
- _native_tools_kwargs: disabled, enabled with unsupported provider, enabled with openrouter
- _post_loop_checks: cognitive_loop, quality_gate, decision_anchor, event_bus (success + error)
- _run_tool_task_async: guardrail blocks, successful execution, cognitive verify error
- run_loop: model not loaded, capacity halt/warn, text only, tool call success,
  error compress/retryable/non-retryable, tool blocked, approval required, step limit
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Generator, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.engine.benchmark_harness import TaskOutcome
from antigravity_k.engine.quality_gate import QualityGrade, QualityScore
from antigravity_k.engine.task_context_snapshot import load_task_context_snapshot
from antigravity_k.engine.task_state_store import TaskExecutionContext, TaskStateStore
from antigravity_k.engine.tool_call_parser import ToolCall
from antigravity_k.engine.tool_loop import TaskOutcomeRecorder, ToolExecutionResult, ToolLoopEngine


def _format_tool_response(
    engine: ToolLoopEngine,
    tool_call: ToolCall,
    tool_result: str,
    focus_terms: tuple[str, ...] = (),
) -> str:
    method = cast(Callable[[ToolCall, str, tuple[str, ...]], str], getattr(engine, "_format_tool_response"))
    return method(tool_call, tool_result, focus_terms)


def _native_tools_kwargs(
    engine: ToolLoopEngine,
    delegate_model: str,
    required_tools: tuple[str, ...] | None = None,
) -> dict[str, object]:
    method = cast(
        Callable[[str, tuple[str, ...] | None], dict[str, object]],
        getattr(engine, "_native_tools_kwargs"),
    )
    return method(delegate_model, required_tools)


def _post_loop_checks(
    engine: ToolLoopEngine,
    messages: list[dict[str, str]],
    task_type: str,
    full_output: str,
    user_task: str,
    delegate_model: str | None = None,
    evidence_context: str = "",
) -> Generator[str, None, QualityScore | None]:
    method = cast(
        Callable[
            [list[dict[str, str]], str, str, str, str | None, str],
            Generator[str, None, QualityScore | None],
        ],
        getattr(engine, "_post_loop_checks"),
    )
    return method(messages, task_type, full_output, user_task, delegate_model, evidence_context)


def _quality_revision(
    engine: ToolLoopEngine,
    user_task: str,
    full_output: str,
    feedback: str,
    delegate_model: str | None,
    evidence_context: str = "",
) -> str:
    method = cast(Callable[[str, str, str, str | None, str], str], getattr(engine, "_quality_revision"))
    return method(user_task, full_output, feedback, delegate_model, evidence_context)


async def _run_tool_task_async(engine: ToolLoopEngine, tool_call: ToolCall) -> ToolExecutionResult:
    method = cast(Callable[[ToolCall], Awaitable[ToolExecutionResult]], getattr(engine, "_run_tool_task_async"))
    return await method(tool_call)


def _maybe_compress_context(
    engine: ToolLoopEngine,
    shaped_messages: list[dict[str, str]],
    prompt_str: str,
    delegate_model: str,
    task_type: str,
    system_prompt: str,
    tool_prompt: str,
    skill_prompts: str,
    focus_terms: tuple[str, ...] = (),
) -> tuple[list[dict[str, str]], str, float | None, float | None]:
    method = cast(
        Callable[
            [list[dict[str, str]], str, str, str, str, str, str, tuple[str, ...]],
            tuple[list[dict[str, str]], str, float | None, float | None],
        ],
        getattr(engine, "_maybe_compress_context"),
    )
    return method(
        shaped_messages,
        prompt_str,
        delegate_model,
        task_type,
        system_prompt,
        tool_prompt,
        skill_prompts,
        focus_terms,
    )


def _refresh_checkpoint_context(engine: ToolLoopEngine, messages: list[dict[str, str]]) -> None:
    method = cast(Callable[[list[dict[str, str]]], None], getattr(engine, "_refresh_checkpoint_context"))
    method(messages)


def _expected_tools(engine: ToolLoopEngine) -> tuple[str, ...]:
    method = cast(Callable[[], tuple[str, ...]], getattr(engine, "_expected_tools"))
    return method()


def _outcome_recorder(outcomes: list[TaskOutcome]) -> TaskOutcomeRecorder:
    def record(outcome: TaskOutcome) -> TaskOutcome:
        outcomes.append(outcome)
        return outcome

    return cast(TaskOutcomeRecorder, record)


def _mock_path(root: MagicMock, path: tuple[str, ...]) -> MagicMock:
    current: object = root
    for name in path:
        current = cast(MagicMock, cast(object, getattr(current, name)))
    return cast(MagicMock, current)


def _set_mock_return(root: MagicMock, path: tuple[str, ...], value: object) -> None:
    setattr(_mock_path(root, path), "return_value", value)


def _set_mock_side_effect(root: MagicMock, path: tuple[str, ...], value: object) -> None:
    setattr(_mock_path(root, path), "side_effect", value)


def _get_mock_attr(root: MagicMock, path: tuple[str, ...]) -> object:
    current: object = root
    for name in path:
        current = cast(object, getattr(cast(MagicMock, cast(object, current)), name))
    return current


def _assert_mock_called_once_with(root: MagicMock, path: tuple[str, ...], **kwargs: object) -> None:
    method = cast(Callable[..., object], cast(object, getattr(_mock_path(root, path), "assert_called_once_with")))
    method(**kwargs)


class _RaisingIter:
    """Iterator that raises exc on first __next__().

    Use as stream_generate.return_value to test exception handling
    inside the try/except block (not during stream_generate() call,
    which is OUTSIDE the try block).
    """

    def __init__(self, exc: Exception):
        self.exc: Exception = exc

    def __iter__(self) -> _RaisingIter:
        return self

    def __next__(self) -> str:
        raise self.exc


# ─── Mock Orchestrator Fixture ──────────────────────────────────


@pytest.fixture
def mock_orch() -> MagicMock:
    """Mock orchestrator with minimal attributes for ToolLoopEngine."""
    orch = MagicMock()
    orch.config = {}
    orch.project_root = "/tmp/test"
    orch._skill_prompts_cache = ""
    orch._last_agent_output = ""
    orch.manager = MagicMock()
    orch.manager._registry = MagicMock()
    orch.manager.router = MagicMock()
    _set_mock_return(orch, ("manager", "is_loaded"), True)
    _set_mock_return(
        orch,
        ("_prepare_agent_prompt",),
        (
            "delegate_model",
            "system_prompt_part",
            "tool_prompt_part",
            "skill_prompts_part",
            "prompt_str",
            [{"role": "user", "content": "test"}],
        ),
    )

    # Context with guardrail
    ctx = MagicMock()
    ctx.tool_guardrail = MagicMock()
    before_call_result = MagicMock()
    setattr(before_call_result, "allows_execution", True)
    _set_mock_return(ctx, ("tool_guardrail", "before_call"), before_call_result)
    after_call_result = MagicMock()
    setattr(after_call_result, "action", "allow")
    _set_mock_return(ctx, ("tool_guardrail", "after_call"), after_call_result)
    setattr(_mock_path(ctx, ("tool_guardrail",)), "reset", MagicMock())
    ctx.cognitive_loop = MagicMock()
    ctx.quality_gate = MagicMock()
    quality_result = MagicMock()
    setattr(quality_result, "user_message", "")
    setattr(quality_result, "should_retry", False)
    _set_mock_return(ctx, ("quality_gate", "evaluate"), quality_result)
    ctx.decision_anchor = MagicMock()
    _set_mock_return(ctx, ("decision_anchor", "auto_extract"), None)
    ctx.tool_executor = MagicMock()
    ctx.tool_executor.execute_async = AsyncMock(return_value="result_ok")

    orch.ctx = ctx
    return orch


# ─── Init ────────────────────────────────────────────────────────


class TestToolLoopEngineInit:
    def test_stores_orchestrator(self, mock_orch: MagicMock):
        engine = ToolLoopEngine(mock_orch)
        assert engine.orch is mock_orch

    def test_accepts_task_outcome_recorder(self, mock_orch: MagicMock):
        recorder = MagicMock()
        engine = ToolLoopEngine(mock_orch, outcome_recorder=recorder)
        assert engine.outcome_recorder is recorder

    def test_compacts_large_tool_result_with_source_provenance(self, mock_orch: MagicMock):
        raw_result = "BEGIN\n" + ("x" * 20_000) + "\nEND"
        formatted = _format_tool_response(
            ToolLoopEngine(mock_orch),
            ToolCall(name="read_file", arguments={"file_path": "README.md"}),
            raw_result,
        )

        assert len(formatted) < 7_000
        assert '"source": "README.md"' in formatted
        assert '"original_chars": 20010' in formatted
        assert '"context_artifact_ref": "artifact-' in formatted
        assert '"context_artifact_tool": "read_context_artifact"' in formatted
        assert "BEGIN" in formatted
        assert "END" in formatted

    def test_restores_stored_tool_artifact(self, mock_orch: MagicMock):
        engine = ToolLoopEngine(mock_orch)
        formatted = _format_tool_response(
            engine,
            ToolCall(name="read_file", arguments={"file_path": "README.md"}),
            "A" * 20_000,
        )
        marker = '"context_artifact_ref": "'
        ref_id = formatted.split(marker, 1)[1].split('"', 1)[0]

        assert engine.restore_context_artifact(ref_id) == "A" * 20_000

    def test_preserves_query_matched_middle_evidence_when_compacting(self, mock_orch: MagicMock):
        raw_result = "header\n" + ("x" * 8_000) + "\nagent_models:\n  default: qwen3.6:latest\n" + ("y" * 8_000)
        formatted = _format_tool_response(
            ToolLoopEngine(mock_orch),
            ToolCall(name="read_file", arguments={"file_path": "config.yaml"}),
            raw_result,
            focus_terms=("agent_models",),
        )

        assert "agent_models:" in formatted
        assert "default: qwen3.6:latest" in formatted

    def test_redacts_secrets_in_tool_result_before_context_injection(self, mock_orch: MagicMock):
        raw_result = "NVIDIA_API_KEY=nvapi-abc123def456789012345678901234567890\nexport OPENAI_API_KEY=sk-proj-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        formatted = _format_tool_response(
            ToolLoopEngine(mock_orch),
            ToolCall(name="read_file", arguments={"file_path": ".env"}),
            raw_result,
        )

        assert "nvapi-abc123def456789012345678901234567890" not in formatted
        assert "sk-proj-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in formatted
        assert "<REDACTED>" in formatted

    def test_redacts_secrets_even_when_large_tool_result_is_truncated(self, mock_orch: MagicMock):
        # Secret sits near the head so it lands in the truncated head slice.
        raw_result = "OPENAI_API_KEY=sk-proj-ZZZZZZZZZZZZZZZZZZZZZZZZZZZZ" + chr(10) + ("x" * 20_000) + chr(10) + "END"
        formatted = _format_tool_response(
            ToolLoopEngine(mock_orch),
            ToolCall(name="read_file", arguments={"file_path": "big.env"}),
            raw_result,
        )

        assert "sk-proj-ZZZZZZZZZZZZZZZZZZZZZZZZZZZZ" not in formatted
        assert "<REDACTED>" in formatted


class TestToolLoopEngineNativeToolsKwargs:
    def test_disabled_by_default(self, mock_orch: MagicMock):
        engine = ToolLoopEngine(mock_orch)
        result = _native_tools_kwargs(engine, "some-model")
        assert result == {}

    def test_enabled_but_unsupported_provider(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        profile = MagicMock()
        setattr(profile, "provider", "mlx")
        _set_mock_return(mock_orch, ("manager", "_registry", "get_model"), profile)
        engine = ToolLoopEngine(mock_orch)
        result = _native_tools_kwargs(engine, "some-model")
        assert result == {}

    def test_enabled_with_openrouter_success(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        profile = MagicMock()
        setattr(profile, "provider", "openrouter")
        _set_mock_return(mock_orch, ("manager", "_registry", "get_model"), profile)
        tool_registry = MagicMock()
        _set_mock_return(tool_registry, ("to_openai_schemas",), [{"name": "run_bash"}])
        setattr(mock_orch, "tool_registry", tool_registry)
        engine = ToolLoopEngine(mock_orch)
        result = _native_tools_kwargs(engine, "some-model")
        assert "tools" in result
        assert result["tools"] == [{"name": "run_bash"}]

    def test_enabled_with_ollama_success(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        profile = MagicMock()
        setattr(profile, "provider", "ollama")
        _set_mock_return(mock_orch, ("manager", "_registry", "get_model"), profile)
        _set_mock_return(mock_orch, ("manager", "provider_capability"), {"native_tool_calling": "supported"})
        tool_registry = MagicMock()
        _set_mock_return(tool_registry, ("to_openai_schemas",), [{"name": "read_file"}])
        setattr(mock_orch, "tool_registry", tool_registry)
        engine = ToolLoopEngine(mock_orch)

        result = _native_tools_kwargs(engine, "qwen3.6:latest")

        assert result["tools"] == [{"name": "read_file"}]

    def test_enabled_ollama_limits_schemas_to_required_tools(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        profile = MagicMock()
        setattr(profile, "provider", "ollama")
        _set_mock_return(mock_orch, ("manager", "_registry", "get_model"), profile)
        _set_mock_return(mock_orch, ("manager", "provider_capability"), {"native_tool_calling": "supported"})
        tool_registry = MagicMock()
        _set_mock_return(tool_registry, ("to_openai_schemas",), [{"name": "read_file"}])
        setattr(mock_orch, "tool_registry", tool_registry)

        result = _native_tools_kwargs(ToolLoopEngine(mock_orch), "qwen3.6:latest", ("read_file",))

        assert result["tools"] == [{"name": "read_file"}]
        _assert_mock_called_once_with(tool_registry, ("to_openai_schemas",), names=["read_file"])

    def test_enabled_with_lmstudio_native_capability_success(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        profile = MagicMock()
        setattr(profile, "provider", "lmstudio")
        _set_mock_return(mock_orch, ("manager", "_registry", "get_model"), profile)
        _set_mock_return(mock_orch, ("manager", "provider_capability"), {"native_tool_calling": "supported"})
        tool_registry = MagicMock()
        _set_mock_return(tool_registry, ("to_openai_schemas",), [{"name": "read_file"}])
        setattr(mock_orch, "tool_registry", tool_registry)
        engine = ToolLoopEngine(mock_orch)

        result = _native_tools_kwargs(engine, "lmstudio/qwen3.6")

        assert result["tools"] == [{"name": "read_file"}]

    def test_enabled_with_explicitly_unsupported_local_capability_uses_xml(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        profile = MagicMock()
        setattr(profile, "provider", "ollama")
        _set_mock_return(mock_orch, ("manager", "_registry", "get_model"), profile)
        _set_mock_return(mock_orch, ("manager", "provider_capability"), {"native_tool_calling": "unsupported"})
        tool_registry = MagicMock()
        _set_mock_return(tool_registry, ("to_openai_schemas",), [{"name": "read_file"}])
        setattr(mock_orch, "tool_registry", tool_registry)
        engine = ToolLoopEngine(mock_orch)

        result = _native_tools_kwargs(engine, "legacy-local")

        assert result == {}

    def test_enabled_with_openrouter_empty_schemas(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        profile = MagicMock()
        setattr(profile, "provider", "openrouter")
        _set_mock_return(mock_orch, ("manager", "_registry", "get_model"), profile)
        tool_registry = MagicMock()
        _set_mock_return(tool_registry, ("to_openai_schemas",), [])
        setattr(mock_orch, "tool_registry", tool_registry)
        engine = ToolLoopEngine(mock_orch)
        result = _native_tools_kwargs(engine, "some-model")
        assert result == {}

    def test_registry_get_model_raises_exception(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", {"tool_loop": {"native_function_calling": True}})
        _set_mock_side_effect(mock_orch, ("manager", "_registry", "get_model"), ValueError("not found"))
        engine = ToolLoopEngine(mock_orch)
        result = _native_tools_kwargs(engine, "some-model")
        assert result == {}

    def test_config_not_dict(self, mock_orch: MagicMock):
        setattr(mock_orch, "config", None)
        engine = ToolLoopEngine(mock_orch)
        result = _native_tools_kwargs(engine, "some-model")
        assert result == {}


# ─── Post-Loop Checks ──────────────────────────────────────────


class TestToolLoopEnginePostLoopChecks:
    def test_uses_source_title_fallback_when_no_model_claim_is_supported(self, mock_orch: MagicMock):
        # Given: usable search records but no claim the model grounded correctly.
        evidence_context = (
            "1. [citation:python-docs] **Python 3.13 release notes**\n"
            "   [untrusted_web_content]\n"
            "Python 3.13 introduces an experimental JIT compiler.\n"
            "   [/untrusted_web_content]\n"
            "   🔗 https://docs.python.org/3/whatsnew/3.13.html\n"
        )
        invalid_output = "Python 3.13 runs a perfect JIT. [citation:wrong-id]"
        _set_mock_return(mock_orch, ("manager", "generate"), invalid_output)
        setattr(_mock_path(mock_orch, ("ctx",)), "analysis", {})
        engine = ToolLoopEngine(mock_orch)

        # When: model correction and claim filtering cannot retain a factual claim.
        outputs = list(
            _post_loop_checks(
                engine,
                [{"role": "user", "content": "Python 3.13 JIT 기능을 알려줘"}],
                "search",
                invalid_output,
                "Python 3.13 JIT 기능을 알려줘",
                "qwen3.6:latest",
                evidence_context=evidence_context,
            ),
        )

        # Then: only an exact source title and its known ID are returned.
        assert cast(bool, getattr(engine, "_citation_validation_failed")) is False
        assert (
            cast(str, _get_mock_attr(mock_orch, ("_last_agent_output",)))
            == "- Python 3.13 release notes [citation:python-docs]"
        )
        analysis = cast(dict[str, object], _get_mock_attr(mock_orch, ("ctx", "analysis")))
        assert analysis["citation_recovery"] == "deterministic_source_titles"
        assert any("Citation Recovery" in output for output in outputs)

    def test_recovers_only_supported_claims_after_invalid_citation_revision(self, mock_orch: MagicMock):
        # Given: one supported claim, one unknown citation, and one unsupported claim.
        evidence_context = (
            "1. [citation:python-docs] **Python 3.13 release notes**\n"
            "   [untrusted_web_content]\n"
            "Python 3.13 introduces an experimental JIT compiler.\n"
            "   [/untrusted_web_content]\n"
            "   🔗 https://docs.python.org/3/whatsnew/3.13.html\n"
        )
        invalid_output = (
            "Python 3.13 introduces an experimental JIT compiler. "
            "[citation:python-docs][citation:wrong-id]\n"
            "Python 3.13 removes all GIL limitations. [citation:python-docs]"
        )
        _set_mock_return(mock_orch, ("manager", "generate"), invalid_output)
        setattr(_mock_path(mock_orch, ("ctx",)), "analysis", {})
        engine = ToolLoopEngine(mock_orch)

        # When: the model revision preserves invalid citations and unsupported content.
        outputs = list(
            _post_loop_checks(
                engine,
                [{"role": "user", "content": "Python 3.13 JIT 기능을 알려줘"}],
                "chat",
                invalid_output,
                "Python 3.13 JIT 기능을 알려줘",
                "qwen3.6:latest",
                evidence_context=evidence_context,
            ),
        )

        # Then: only the mechanically supported claim remains with its known citation.
        assert cast(bool, getattr(engine, "_citation_validation_failed")) is False
        assert cast(str, _get_mock_attr(mock_orch, ("_last_agent_output",))) == (
            "- Python 3.13 introduces an experimental JIT compiler. [citation:python-docs]"
        )
        analysis = cast(dict[str, object], _get_mock_attr(mock_orch, ("ctx", "analysis")))
        assert analysis["citation_recovery"] == "deterministic_claim_filter"
        citation_evaluation = cast(dict[str, object], analysis["citation_evaluation"])
        assert citation_evaluation["unknown_citation_count"] == 0
        assert any("Citation Recovery" in output for output in outputs)

    def test_revises_uncited_web_claim_with_available_evidence(self, mock_orch: MagicMock):
        # Given: a final answer without the available web citation.
        evidence_context = (
            "1. [citation:python-docs] **Python 3.13 release notes**\n"
            "   [untrusted_web_content]\n"
            "Python 3.13 introduces an experimental JIT compiler.\n"
            "   [/untrusted_web_content]\n"
            "   🔗 https://docs.python.org/3/whatsnew/3.13.html\n"
        )
        _set_mock_return(
            mock_orch,
            ("manager", "generate"),
            ("Python 3.13 introduces an experimental JIT compiler. [citation:python-docs]"),
        )
        engine = ToolLoopEngine(mock_orch)

        # When: post-loop checks receive an unsupported factual claim.
        outputs = list(
            _post_loop_checks(
                engine,
                [{"role": "user", "content": "Python 3.13의 JIT 기능을 알려줘"}],
                "chat",
                "Python 3.13 offers a JIT compiler.",
                "Python 3.13의 JIT 기능을 알려줘",
                "qwen3.6:latest",
                evidence_context=evidence_context,
            ),
        )

        # Then: the corrected answer is grounded and replaces the original output.
        assert cast(bool, getattr(engine, "_citation_validation_failed")) is False
        assert cast(str, _get_mock_attr(mock_orch, ("_last_agent_output",))).endswith("[citation:python-docs]")
        assert any("Citation Revision" in output for output in outputs)

    def test_quality_gate_uses_orchestrator_context_without_direct_attribute(self):
        quality_gate = MagicMock()
        quality_gate.evaluate.return_value = QualityScore(
            grade=QualityGrade.A,
            score=1.0,
            feedback="",
            user_message="",
            should_retry=False,
            issues=[],
        )
        orchestrator = SimpleNamespace(
            ctx=SimpleNamespace(cognitive_loop=None, quality_gate=quality_gate, decision_anchor=None),
            project_root="/tmp/test",
        )

        _ = list(
            _post_loop_checks(
                ToolLoopEngine(orchestrator),
                [{"role": "user", "content": "write code"}],
                "code",
                "```python\ndef valid():\n    return 1\n```",
                "write code",
            )
        )

        quality_gate.evaluate.assert_called_once()

    def test_cognitive_loop_reflect_called(self, mock_orch: MagicMock):
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))
        mock_orch.ctx.cognitive_loop.reflect.assert_called_once_with("do something", "output")

    def test_quality_gate_evaluate_called(self, mock_orch: MagicMock):
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))
        mock_orch.ctx.quality_gate.evaluate.assert_called_once()

    def test_quality_gate_user_message_yielded(self, mock_orch: MagicMock):
        mock_orch.ctx.quality_gate.evaluate.return_value.user_message = "Quality issue detected"
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        res = list(_post_loop_checks(engine, messages, "code", "output", "do something"))
        assert any("Quality issue detected" in r for r in res)

    def test_quality_gate_retry_marked(self, mock_orch: MagicMock):
        mock_orch.ctx.quality_gate.evaluate.return_value.should_retry = True
        mock_orch.ctx.quality_gate.evaluate.return_value.feedback = "needs improvement"
        mock_orch.ctx.quality_gate.evaluate.return_value.user_message = ""
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))
        mock_orch.ctx.quality_gate.mark_retry.assert_called_once()

    def test_quality_gate_revision_replaces_output_and_outcome(self, mock_orch: MagicMock):
        initial = MagicMock(user_message="", should_retry=True, feedback="보완 필요", score=0.3)
        revised = MagicMock(user_message="", should_retry=False, feedback="", score=0.9)
        mock_orch.ctx.quality_gate.evaluate.side_effect = [initial, revised]
        mock_orch._get_model_for_role.return_value = "qwen3.6:latest"
        mock_orch.manager.stream_generate.return_value = iter(["초안"])
        mock_orch.manager.generate.return_value = "보완된 최종 답변"
        outcomes: list[TaskOutcome] = []

        with patch("antigravity_k.engine.event_bus.global_event_bus") as event_bus:
            engine = ToolLoopEngine(mock_orch, outcome_recorder=_outcome_recorder(outcomes))
            result = list(engine.run_loop([{"role": "user", "content": "요청"}], "CODER", "chat"))

        assert any("보완된 최종 답변" in chunk for chunk in result)
        assert mock_orch._last_agent_output == "보완된 최종 답변"
        assert outcomes[0].retry_count == 1
        assert outcomes[0].tokens_out == len("보완된 최종 답변") // 4
        event_bus.publish.assert_called_once_with(
            "AgentTurnCompleted",
            user_message="요청",
            assistant_response="보완된 최종 답변",
            project_root="/tmp/test",
        )
        mock_orch.manager.generate.assert_called_once()

    def test_quality_revision_retries_until_gate_budget_is_exhausted(self, mock_orch: MagicMock):
        initial = MagicMock(user_message="", should_retry=True, feedback="중국어 혼입", score=0.3)
        first_revision = MagicMock(user_message="", should_retry=True, feedback="여전히 중국어 혼입", score=0.7)
        second_revision = MagicMock(user_message="", should_retry=False, feedback="", score=0.95)
        mock_orch.ctx.quality_gate.max_retries = 2
        mock_orch.ctx.quality_gate.evaluate.side_effect = [initial, first_revision, second_revision]
        mock_orch.manager.generate.side_effect = ["개선되었지만 중국어 포함", "최종 한국어 답변"]

        chunks = list(
            _post_loop_checks(
                ToolLoopEngine(mock_orch),
                [{"role": "user", "content": "request"}],
                "coding",
                "draft",
                "request",
                "qwen3.6:latest",
            )
        )

        assert mock_orch.manager.generate.call_count == 2
        assert mock_orch._last_agent_output == "최종 한국어 답변"
        assert any("최종 한국어 답변" in chunk for chunk in chunks)

    def test_quality_gate_receives_normalized_local_language_output(self, mock_orch: MagicMock):
        initial = MagicMock(user_message="", should_retry=False, feedback="", score=1.0)
        mock_orch.ctx.quality_gate.evaluate.return_value = initial

        _ = list(
            _post_loop_checks(
                ToolLoopEngine(mock_orch),
                [{"role": "user", "content": "request"}],
                "coding",
                "시간复杂도와 공간复杂도를 설명합니다.",
                "request",
            )
        )

        assert mock_orch.ctx.quality_gate.evaluate.call_args.args[2] == "시간복잡도와 공간복잡도를 설명합니다."
        assert mock_orch._last_agent_output == "시간복잡도와 공간복잡도를 설명합니다."

    def test_qwen_quality_revision_uses_measured_stable_sampling(self, mock_orch: MagicMock):
        mock_orch.manager.generate.return_value = "revised"

        _ = _quality_revision(
            ToolLoopEngine(mock_orch),
            "request",
            "draft",
            "feedback",
            "qwen3.6:latest",
        )

        kwargs = mock_orch.manager.generate.call_args.kwargs
        assert kwargs["temperature"] == 0.08
        assert kwargs["repeat_penalty"] == 1.15

    def test_quality_gate_keeps_original_grade_when_revision_scores_lower(self, mock_orch: MagicMock):
        initial = QualityScore(
            grade=QualityGrade.C,
            score=0.5,
            feedback="draft feedback",
            user_message="",
            should_retry=True,
            issues=["draft issue"],
        )
        revised = QualityScore(
            grade=QualityGrade.F,
            score=0.0,
            feedback="revision feedback",
            user_message="",
            should_retry=False,
            issues=["revision issue"],
        )
        mock_orch.ctx.quality_gate.evaluate.side_effect = [initial, revised]
        mock_orch.manager.stream_generate.return_value = iter(["draft output"])
        mock_orch.manager.generate.return_value = "revision output"
        outcomes: list[TaskOutcome] = []

        _ = list(
            ToolLoopEngine(mock_orch, outcome_recorder=_outcome_recorder(outcomes)).run_loop(
                [{"role": "user", "content": "request"}],
                "CODER",
                "chat",
            )
        )

        assert mock_orch._last_agent_output == "draft output"
        assert outcomes[0].error == "quality_gate_failed: draft feedback"

    def test_decomposition_recovery_used_when_revision_still_fails(self, mock_orch: MagicMock):
        initial = MagicMock(user_message="", should_retry=True, feedback="워크플로 누락", score=0.3)
        revised = MagicMock(user_message="", should_retry=True, feedback="여전히 누락", score=0.2)
        decomposed = MagicMock(user_message="", should_retry=False, feedback="", score=0.9)
        mock_orch.config = {
            "amplification": {
                "task_decomposition": {"escalate_on_revision_failure": True},
            },
        }
        mock_orch.ctx.quality_gate.evaluate.side_effect = [initial, revised, decomposed]
        mock_orch.manager.generate.return_value = "여전히 부족한 재생성"
        mock_orch.manager.generate_decomposed.return_value = "분해로 복구된 워크플로"

        chunks = list(
            _post_loop_checks(
                ToolLoopEngine(mock_orch),
                [{"role": "user", "content": ""}],
                "long_horizon",
                "초안",
                "코드 마이그레이션 워크플로를 복구하세요",
                "qwen3.6:latest",
            )
        )

        mock_orch.manager.generate_decomposed.assert_called_once()
        assert mock_orch._last_agent_output == "분해로 복구된 워크플로"
        assert any("분해로 복구된 워크플로" in chunk for chunk in chunks)

    def test_decomposition_recovery_respects_config_toggle(self, mock_orch: MagicMock):
        initial = MagicMock(user_message="", should_retry=True, feedback="워크플로 누락", score=0.3)
        revised = MagicMock(user_message="", should_retry=True, feedback="여전히 누락", score=0.2)
        mock_orch.config = {
            "amplification": {
                "task_decomposition": {"escalate_on_revision_failure": False},
            },
        }
        mock_orch.ctx.quality_gate.evaluate.side_effect = [initial, revised]
        mock_orch.manager.generate.return_value = "여전히 부족한 재생성"

        _ = list(
            _post_loop_checks(
                ToolLoopEngine(mock_orch),
                [{"role": "user", "content": ""}],
                "long_horizon",
                "초안",
                "코드 마이그레이션 워크플로를 복구하세요",
                "qwen3.6:latest",
            )
        )

        mock_orch.manager.generate_decomposed.assert_not_called()

    def test_decomposition_recovery_keeps_original_when_it_scores_lower(self, mock_orch: MagicMock):
        initial = MagicMock(user_message="", should_retry=True, feedback="워크플로 누락", score=0.3)
        revised = MagicMock(user_message="", should_retry=True, feedback="여전히 누락", score=0.2)
        decomposed = MagicMock(user_message="", should_retry=True, feedback="악화", score=0.1)
        mock_orch.config = {
            "amplification": {
                "task_decomposition": {"escalate_on_revision_failure": True},
            },
        }
        mock_orch.ctx.quality_gate.evaluate.side_effect = [initial, revised, decomposed]
        mock_orch.manager.generate.return_value = "여전히 부족한 재생성"
        mock_orch.manager.generate_decomposed.return_value = "더 나쁜 분해 결과"
        mock_orch._last_agent_output = "초안"

        _ = list(
            _post_loop_checks(
                ToolLoopEngine(mock_orch),
                [{"role": "user", "content": ""}],
                "long_horizon",
                "초안",
                "코드 마이그레이션 워크플로를 복구하세요",
                "qwen3.6:latest",
            )
        )

        assert mock_orch._last_agent_output == "초안"

    def test_quality_revision_preserves_verified_tool_execution_evidence(self, mock_orch: MagicMock):
        # Given: a coding task whose tool loop produced real run_bash_command evidence.
        initial = MagicMock(user_message="", should_retry=True, feedback="구조 보완", score=0.5)
        revised = MagicMock(user_message="", should_retry=False, feedback="", score=0.9)
        mock_orch.ctx.quality_gate.evaluate.side_effect = [initial, revised]
        mock_orch._get_model_for_role.return_value = "qwen3.6:latest"
        mock_orch.manager.stream_generate.return_value = iter(["초안 5050"])
        mock_orch.manager.generate.return_value = "보완된 답변"
        evidence_context = (
            "\n<tool_response>\n"
            '[TOOL_EVIDENCE] {"tool": "run_bash_command", "source": "python3 -c ..."}\n'
            "[UNTRUSTED_TOOL_RESULT]\nsum_to(100) = 5050\n[//UNTRUSTED_TOOL_RESULT]\n"
            "</tool_response>"
        )
        engine = ToolLoopEngine(mock_orch)

        # When: post-loop checks run with that execution evidence present.
        _ = list(
            _post_loop_checks(
                engine,
                [{"role": "user", "content": ""}],
                "code",
                "초안 5050",
                "sum_to를 실행해줘",
                "qwen3.6:latest",
                evidence_context=evidence_context,
            )
        )

        # Then: the revision prompt is constrained by the verified execution result so a
        # surface-only rewrite cannot drop or contradict the real tool output.
        revision_prompt = mock_orch.manager.generate.call_args.kwargs["prompt"]
        assert "5050" in revision_prompt
        assert "run_bash_command" in revision_prompt

    def test_decision_anchor_extract(self, mock_orch: MagicMock):
        mock_orch.ctx.decision_anchor.auto_extract.return_value = {
            "decision": "refactor",
            "category": "code",
        }
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))
        mock_orch.ctx.decision_anchor.add.assert_called_once()

    def test_event_bus_published(self, mock_orch: MagicMock):
        with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
            engine = ToolLoopEngine(mock_orch)
            messages = [{"role": "user", "content": "do something"}]
            _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))
            mock_bus.publish.assert_called_once_with(
                "AgentTurnCompleted",
                user_message="do something",
                assistant_response="output",
                project_root="/tmp/test",
            )

    def test_exception_in_reflect_does_not_block(self, mock_orch: MagicMock):
        mock_orch.ctx.cognitive_loop.reflect.side_effect = RuntimeError("reflect fail")
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))
        mock_orch.ctx.quality_gate.evaluate.assert_called_once()

    def test_no_cognitive_loop_skips(self, mock_orch: MagicMock):
        mock_orch.ctx.cognitive_loop = None
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))

    def test_no_quality_gate_skips(self, mock_orch: MagicMock):
        mock_orch.ctx.quality_gate = None
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))

    def test_no_decision_anchor_skips(self, mock_orch: MagicMock):
        mock_orch.ctx.decision_anchor = None
        engine = ToolLoopEngine(mock_orch)
        messages = [{"role": "user", "content": "do something"}]
        _ = list(_post_loop_checks(engine, messages, "code", "output", "do something"))


# ─── Run Tool Task Async ────────────────────────────────────────


class TestToolLoopEngineRunToolTaskAsync:
    @pytest.mark.asyncio
    async def test_read_only_benchmark_blocks_mutating_tool(self, mock_orch: MagicMock, tmp_path: Path):
        from antigravity_k.engine.tool_call_parser import ToolCall

        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("benchmark-read-only", "benchmark prompt", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint(
            "benchmark-read-only",
            0,
            json.dumps({"benchmark_read_only": True}),
            "",
        )
        mock_orch.task_execution_context = TaskExecutionContext("benchmark-read-only", store)
        tc = ToolCall(name="write_file", arguments={"path": "result.py", "content": "print('changed')"})

        _, pre_decision, _, tool_result, blocked = await _run_tool_task_async(ToolLoopEngine(mock_orch), tc)

        assert blocked is True
        assert pre_decision is None
        assert "BENCHMARK READ-ONLY" in str(tool_result)
        mock_orch.ctx.tool_guardrail.before_call.assert_not_called()
        mock_orch.ctx.tool_executor.execute_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_guardrail_blocks_execution(self, mock_orch: MagicMock):
        from antigravity_k.engine.tool_call_parser import ToolCall

        pre_decision = MagicMock()
        pre_decision.allows_execution = False
        pre_decision.message = "Tool blocked by guardrail"
        pre_decision.action = "block"
        pre_decision.should_halt = False
        pre_decision.reason = "security"
        pre_decision.to_dict.return_value = {
            "action": "block",
            "message": "Tool blocked by guardrail",
            "reason": "security",
        }
        mock_orch.ctx.tool_guardrail.before_call.return_value = pre_decision

        tc = ToolCall(name="run_bash", arguments={"command": "ls"})
        engine = ToolLoopEngine(mock_orch)
        result = await _run_tool_task_async(engine, tc)
        _, _, _, synthetic, blocked = result
        assert blocked is True
        assert "blocked" in str(synthetic).lower()
        mock_orch.ctx.tool_executor.execute_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_orch: MagicMock):
        from antigravity_k.engine.tool_call_parser import ToolCall

        mock_orch.ctx.tool_executor.execute_async.return_value = "command output"
        tc = ToolCall(name="run_bash", arguments={"command": "ls"})
        engine = ToolLoopEngine(mock_orch)
        result = await _run_tool_task_async(engine, tc)
        _, _, _, tool_result, blocked = result
        assert blocked is False
        assert tool_result == "command output"
        mock_orch.ctx.tool_executor.execute_async.assert_called_once_with("run_bash", {"command": "ls"})
        mock_orch.ctx.tool_guardrail.after_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_cognitive_verify_error_handled(self, mock_orch: MagicMock):
        from antigravity_k.engine.tool_call_parser import ToolCall

        mock_orch.ctx.cognitive_loop.verify_tool_result.side_effect = ValueError("verify fail")
        tc = ToolCall(name="search", arguments={"query": "test"})
        engine = ToolLoopEngine(mock_orch)
        result = await _run_tool_task_async(engine, tc)
        _, _, _, tool_result, blocked = result
        assert blocked is False
        assert tool_result is not None

    @pytest.mark.asyncio
    async def test_event_bus_exception_handled(self, mock_orch: MagicMock):
        from antigravity_k.engine.tool_call_parser import ToolCall

        with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
            mock_bus.publish.side_effect = RuntimeError("bus down")
            tc = ToolCall(name="bash", arguments={"cmd": "ls"})
            engine = ToolLoopEngine(mock_orch)
            result = await _run_tool_task_async(engine, tc)
            _, _, _, tool_result, _ = result
            assert tool_result is not None


# ─── Run Loop ───────────────────────────────────────────────────


class TestToolLoopEngineRunLoop:
    """run_loop — stream_generate mock, DAG execution batching, error handling."""

    mock_orch: MagicMock = MagicMock()

    @pytest.fixture(autouse=True)
    def _setup_run_loop_mocks(self, mock_orch: MagicMock) -> None:
        """Common mocks for run_loop: prepare_agent_prompt, manager, combo check."""
        self.mock_orch = mock_orch
        # NOTE: get_combo must return None (not False) — run_loop checks
        # `is not None` to detect combo mode. False is not None = True,
        # which incorrectly skips the is_loaded check!
        mock_orch.manager.router.get_combo.return_value = None
        mock_orch.manager.is_loaded.return_value = True
        # Don't set _capacity_checkpoint — MagicMock auto-creates it,
        # and its check_step_budget().action returns a MagicMock that won't
        # match any CapacityAction enum, making capacity check a no-op.

    def _run(
        self,
        messages: list[dict[str, str]] | None = None,
        delegate_to: str = "CODER",
        task_type: str = "code",
        max_steps: int = 5,
        target_model: str | None = None,
    ) -> list[str]:
        """Helper: create engine and collect run_loop output."""
        engine = ToolLoopEngine(self.mock_orch)
        msgs = messages or [{"role": "user", "content": "test task"}]
        return list(engine.run_loop(msgs, delegate_to, task_type, max_steps, target_model))

    def test_model_not_loaded(self):
        """is_loaded=False and not a combo -> model not loaded error."""
        self.mock_orch.manager.router.get_combo.return_value = None
        self.mock_orch.manager.is_loaded.return_value = False
        results = self._run()
        assert any("모델" in r and "로드되지 않았" in r for r in results)

    def test_combo_skips_loaded_check(self):
        """combo name (coding-swarm 등)은 is_loaded 체크를 건너뜀."""
        self.mock_orch.manager.router.get_combo.return_value = "coding-swarm"
        self.mock_orch.manager.is_loaded.return_value = False  # Would fail if checked
        self.mock_orch.manager.stream_generate.return_value = iter([])
        results = self._run()
        assert all("로드되지 않았" not in r for r in results)

    def test_qwen_agent_stream_uses_stable_local_sampling(self):
        """qwen3 도구 에이전트 경로도 실측된 안정 샘플링 파라미터를 사용한다."""
        self.mock_orch.manager.stream_generate.return_value = iter(["completed"])

        _ = self._run(target_model="qwen3.6:latest")

        kwargs = self.mock_orch.manager.stream_generate.call_args.kwargs
        assert kwargs["temperature"] == 0.2
        assert kwargs["repeat_penalty"] == 1.1
        assert kwargs["min_p"] == 0.0

    def test_capacity_halt(self):
        """CapacityAction.HALT -> capacity limit and return."""
        from antigravity_k.engine.capacity_flow import CapacityAction

        mock_cap = MagicMock()
        mock_cap.check_step_budget.return_value.action = CapacityAction.HALT
        self.mock_orch._capacity_checkpoint = mock_cap
        results = self._run()
        assert any("Capacity Limit" in r for r in results)

    def test_capacity_warn(self):
        """CapacityAction.WARN -> warning yield, then continues to stream."""
        from antigravity_k.engine.capacity_flow import CapacityAction

        mock_cap = MagicMock()
        mock_cap.check_step_budget.return_value.action = CapacityAction.WARN
        self.mock_orch._capacity_checkpoint = mock_cap
        self.mock_orch.manager.stream_generate.return_value = iter([])
        results = self._run()
        assert any("Capacity Warning" in r for r in results)

    def test_text_only_no_tool_calls(self):
        """stream yields text only, no tool calls -> breaks and does post_loop."""
        self.mock_orch.manager.stream_generate.return_value = iter(["Hello ", "world"])
        results = self._run()
        assert any("Hello" in r for r in results)
        assert any("world" in r for r in results)

    def test_tool_call_success(self):
        """stream yields a tool call -> executes tool -> formats result."""
        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "run_bash", "arguments": {"command": "ls"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        self.mock_orch.manager.stream_generate.return_value = iter([tool_xml])
        results = self._run()
        result_text = " ".join(results)
        assert "tool" in result_text.lower() or "실행" in result_text
        assert "run_bash" in result_text or "Executing" in result_text

    def test_dag_execution_batching(self):
        """waitForPreviousTools -> multiple execution batches."""
        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "search", "arguments": {"query": "test"}}\n'
            "</tool_call>\n</action_call>\n"
            "<action_call>\n<tool_call>\n"
            '{"name": "write_file", "arguments": {"path": "f.txt", "waitForPreviousTools": true}}\n'
            "</tool_call>\n</action_call>\n"
        )
        self.mock_orch.manager.stream_generate.return_value = iter([tool_xml])
        results = self._run()
        result_text = " ".join(results)
        # Should have executed both tools
        assert "search" in result_text or "Executing" in result_text
        assert len(results) > 3

    def test_stream_error_retryable(self):
        """stream raises exception classified as retryable -> retry."""

        class RetryableError(Exception):
            pass

        def mock_classify(e: Exception, **kw: object):
            from antigravity_k.engine.error_classifier import ClassifiedError, FailoverReason

            _ = (e, kw)
            return ClassifiedError(reason=FailoverReason.timeout, retryable=True)

        with patch("antigravity_k.engine.tool_loop.classify_api_error", side_effect=mock_classify):
            # stream_generate returns a RaisingIter — exception is raised
            # INSIDE the for-loop try/except, not during the call (which
            # is outside the try block)
            self.mock_orch.manager.stream_generate.return_value = _RaisingIter(
                RetryableError("timeout"),
            )
            results = self._run(max_steps=3)
            assert any("재시도" in r or "일시적" in r for r in results)

    def test_stream_error_non_retryable(self):
        """stream raises non-retryable exception -> error message and return."""

        class FatalError(Exception):
            pass

        def mock_classify(e: Exception, **kw: object):
            from antigravity_k.engine.error_classifier import ClassifiedError, FailoverReason

            _ = (e, kw)
            return ClassifiedError(reason=FailoverReason.format_error, retryable=False)

        with patch("antigravity_k.engine.tool_loop.classify_api_error", side_effect=mock_classify):
            self.mock_orch.manager.stream_generate.return_value = _RaisingIter(
                FatalError("bad request"),
            )
            results = self._run()
            assert any("에러" in r or "오류" in r for r in results)

    def test_stream_error_compress(self):
        """should_compress=True -> compress context and continue."""

        class ContextOverflow(Exception):
            pass

        def mock_classify(e: Exception, **kw: object):
            from antigravity_k.engine.error_classifier import ClassifiedError, FailoverReason

            _ = (e, kw)
            return ClassifiedError(reason=FailoverReason.context_overflow, retryable=True, should_compress=True)

        mock_shaper = MagicMock()
        mock_shaper.shape.return_value = [{"role": "user", "content": "compressed"}]
        self.mock_orch.context_shaper = mock_shaper

        # stream_generate returns RaisingIter on 1st call, normal iter on 2nd
        self.mock_orch.manager.stream_generate.side_effect = [
            _RaisingIter(ContextOverflow("context too long")),
            iter(["after compress"]),
        ]

        with patch("antigravity_k.engine.tool_loop.classify_api_error", side_effect=mock_classify):
            results = self._run(max_steps=3)
            assert any("압축" in r for r in results)

    def test_tool_blocked_by_guardrail(self):
        """pre_decision.allows_execution=False -> blocked tool message."""
        pre_decision = MagicMock()
        pre_decision.allows_execution = False
        pre_decision.message = "Not allowed"
        pre_decision.action = "block"
        pre_decision.should_halt = True
        pre_decision.reason = "policy"
        pre_decision.to_dict.return_value = {
            "action": "block",
            "message": "Not allowed",
            "reason": "policy",
        }

        mock_orch = self.mock_orch
        mock_orch.ctx.tool_guardrail.before_call.return_value = pre_decision

        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "run_bash", "arguments": {"command": "ls"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        mock_orch.manager.stream_generate.return_value = iter([tool_xml])
        mock_orch.ctx.tool_executor.execute_async.return_value = "result"

        results = self._run()
        result_text = " ".join(results)
        assert "Tool Blocked" in result_text or "Guardrail" in result_text

    def test_approval_required_break(self):
        """tool_result contains APPROVAL REQUIRED -> breaks loop."""
        mock_orch = self.mock_orch
        mock_orch.ctx.tool_executor.execute_async.return_value = "[APPROVAL REQUIRED] Please confirm"

        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "write_file", "arguments": {"path": "test.txt"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        mock_orch.manager.stream_generate.return_value = iter([tool_xml])
        results = self._run()
        assert any("APPROVAL REQUIRED" in r for r in results)

    def test_step_limit_reached(self):
        """max_steps reached with tool calls -> step limit message."""
        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "run_bash", "arguments": {"command": "ls"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        self.mock_orch.manager.stream_generate.return_value = iter([tool_xml])
        results = self._run(max_steps=1)
        assert any("Step Limit" in r for r in results)

    def test_excessive_max_steps_is_bounded(self):
        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "run_bash", "arguments": {"command": "ls"}}\n'
            "</tool_call>\n</action_call>\n"
        )

        def stream_generate(**kwargs: object) -> Iterator[str]:
            _ = kwargs
            return iter([tool_xml])

        self.mock_orch.manager.stream_generate.side_effect = stream_generate
        self.mock_orch.ctx.tool_executor.execute_async.return_value = "result"

        results = self._run(max_steps=51)

        assert any("최대 도구 호출 횟수(50)" in r for r in results)
        assert self.mock_orch.manager.stream_generate.call_count == 50

    def test_non_positive_max_steps_still_runs_once(self):
        self.mock_orch.manager.stream_generate.return_value = iter(["completed"])

        _ = self._run(max_steps=0)

        assert self.mock_orch.manager.stream_generate.call_count == 1

    def test_empty_messages_post_loop(self):
        """messages가 비어 있으면 post_loop는 user_task=''로 실행."""
        self.mock_orch.manager.stream_generate.return_value = iter(["output"])
        results = self._run(messages=[])
        assert isinstance(results, list)

    def test_quality_gate_uses_original_request_when_prompt_was_refined(self):
        """state graph이 refined+RAG 프롬프트로 메시지를 바꿔도 원요청으로 평가한다."""
        augmented_message = {
            "role": "user",
            "content": "architecture context: [web evidence] Python 3.13 ...",
        }
        self.mock_orch.manager.stream_generate.return_value = iter(["completed"])

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [augmented_message],
                "CODER",
                "coding",
                evaluation_user_task="Python 3.13 출시일을 알려줘",
            )
        )

        assert self.mock_orch.ctx.quality_gate.evaluate.call_args.args[1] == "Python 3.13 출시일을 알려줘"

    def test_records_successful_text_task_outcome(self):
        outcomes: list[TaskOutcome] = []
        self.mock_orch.task_id = "loop-001"
        self.mock_orch.expected_tools = ()
        self.mock_orch.manager.stream_generate.return_value = iter(["completed"])
        engine = ToolLoopEngine(self.mock_orch, outcome_recorder=_outcome_recorder(outcomes))

        _ = list(engine.run_loop([{"role": "user", "content": "finish"}], "CODER", "code"))

        assert len(outcomes) == 1
        assert outcomes[0].case_id == "loop-001"
        assert outcomes[0].success is True
        assert outcomes[0].completion_reason == "done"

    def test_records_used_tools_and_expected_tools(self):
        outcomes: list[TaskOutcome] = []
        self.mock_orch.task_id = "loop-002"
        self.mock_orch.expected_tools = ("run_bash",)
        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "run_bash", "arguments": {"command": "ls"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        self.mock_orch.manager.stream_generate.return_value = iter([tool_xml])
        engine = ToolLoopEngine(self.mock_orch, outcome_recorder=_outcome_recorder(outcomes))

        _ = list(engine.run_loop([{"role": "user", "content": "inspect"}], "CODER", "code"))

        assert len(outcomes) == 1
        assert outcomes[0].used_tools == ("run_bash",)
        assert outcomes[0].tool_accuracy == 1.0

    def test_web_search_answer_is_citation_revised_before_completion(self):
        # Given: a web-search tool result and an uncited final model response.
        primary_url = "https://docs.python.org/3/whatsnew/3.13.html"
        citation = "python-docs"
        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "web_search", "arguments": {"query": "Python 3.13 JIT"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        tool_result = (
            f"1. [citation:{citation}] **Python 3.13 release notes**\n"
            "   [untrusted_web_content]\n"
            "Python 3.13 introduces an experimental JIT compiler.\n"
            "   [/untrusted_web_content]\n"
            f"   🔗 {primary_url}\n"
        )
        self.mock_orch.expected_tools = ("web_search",)
        self.mock_orch.ctx.tool_executor.execute_async.return_value = tool_result
        self.mock_orch.manager.stream_generate.side_effect = [
            iter([tool_xml]),
            iter(["Python 3.13 offers a JIT compiler."]),
        ]
        self.mock_orch.manager.generate.return_value = (
            f"Python 3.13 introduces an experimental JIT compiler. [citation:{citation}]"
        )
        outcomes: list[TaskOutcome] = []

        # When: the loop executes the search and evaluates its final answer.
        outputs = list(
            ToolLoopEngine(self.mock_orch, outcome_recorder=_outcome_recorder(outcomes)).run_loop(
                [{"role": "user", "content": "Python 3.13 JIT 기능을 알려줘"}],
                "SELF",
                "chat",
            ),
        )

        # Then: the corrected, cited answer is the completed task output.
        assert outcomes[0].success is True
        assert outcomes[0].completion_reason == "done"
        assert self.mock_orch._last_agent_output.endswith(f"[citation:{citation}]")
        assert any("Citation Revision" in output for output in outputs)

    def test_reads_expected_tools_from_durable_execution_context(self, tmp_path: Path):
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("tool-contract", "read README", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint(
            "tool-contract",
            0,
            '{"expected_tools": ["read_file"]}',
            "",
        )
        self.mock_orch.task_execution_context = TaskExecutionContext("tool-contract", store)

        expected_tools = _expected_tools(ToolLoopEngine(self.mock_orch))

        assert expected_tools == ("read_file",)

    def test_missing_required_tool_marks_durable_task_failed(self, tmp_path: Path):
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("required-tool", "read README", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint(
            "required-tool",
            0,
            '{"expected_tools": ["read_file"]}',
            "",
        )
        self.mock_orch.task_execution_context = TaskExecutionContext("required-tool", store)
        self.mock_orch.ctx.quality_gate = None
        self.mock_orch.manager.stream_generate.return_value = iter(["ungrounded answer"])

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "read README"}],
                "SELF",
                "chat",
            )
        )

        record = store.get_task("required-tool")
        assert record is not None
        assert record["status"] == "failed"
        assert record["error"] == "required_tools_missing: read_file"

    def test_omits_satisfied_native_tools_from_follow_up_turn(self, tmp_path: Path):
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("read-once", "read README", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint(
            "read-once",
            0,
            '{"expected_tools": ["read_file"]}',
            "",
        )
        self.mock_orch.task_execution_context = TaskExecutionContext("read-once", store)
        self.mock_orch.config = {"tool_loop": {"native_function_calling": True}}
        profile = MagicMock()
        profile.provider = "ollama"
        self.mock_orch.manager._registry.get_model.return_value = profile
        self.mock_orch.manager.provider_capability.return_value = {"native_tool_calling": "supported"}
        self.mock_orch.tool_registry.to_openai_schemas.return_value = [{"name": "read_file"}]
        self.mock_orch.ctx.tool_executor.execute_async.return_value = "README contents"
        self.mock_orch.ctx.quality_gate = None
        tool_call = '<tool_call>\n{"name": "read_file", "arguments": {"file_path": "README.md"}}\n</tool_call>\n'
        self.mock_orch.manager.stream_generate.side_effect = [iter([tool_call]), iter(["grounded summary"])]

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "read README"}],
                "SELF",
                "chat",
                target_model="qwen3.6:latest",
            )
        )

        first_call, second_call = self.mock_orch.manager.stream_generate.call_args_list
        assert first_call.kwargs["tools"] == [{"name": "read_file"}]
        assert "tools" not in second_call.kwargs

    def test_recovers_a_qwen_scratchpad_action_for_one_required_tool(self, tmp_path: Path):
        # Given: Qwen plans the sole required read instead of emitting its tool-call tag.
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("qwen-plan", "read README", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint("qwen-plan", 0, '{"expected_tools": ["read_file"]}', "")
        self.mock_orch.task_execution_context = TaskExecutionContext("qwen-plan", store)
        self.mock_orch.ctx.quality_gate = None
        self.mock_orch.ctx.tool_executor.execute_async.return_value = "README contents"
        self.mock_orch.manager.stream_generate.side_effect = [
            iter(
                [
                    "<scratch_pad>\nActions: Call read_file with file_path='README.md'.\n</scratch_pad>",
                ],
            ),
            iter(["grounded summary"]),
        ]

        # When: the required-tool loop processes Qwen's completed planning turn.
        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "read README"}],
                "SELF",
                "chat",
                target_model="qwen3.6:latest",
            )
        )

        # Then: it executes the planned read and completes with the grounded follow-up.
        record = store.get_task("qwen-plan")
        assert record is not None
        assert record["status"] == "done"
        self.mock_orch.ctx.tool_executor.execute_async.assert_awaited_once_with(
            "read_file",
            {"file_path": "README.md"},
        )

    def test_recovers_each_qwen_scratchpad_action_in_a_multistep_contract(self, tmp_path: Path):
        # Given: Qwen plans each of two required tools in separate scratch-pad turns.
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("qwen-multistep", "inspect README", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint(
            "qwen-multistep",
            0,
            '{"expected_tools": ["read_file", "grep_search"]}',
            "",
        )
        self.mock_orch.task_execution_context = TaskExecutionContext("qwen-multistep", store)
        self.mock_orch.ctx.quality_gate = None
        self.mock_orch.ctx.tool_executor.execute_async.side_effect = ["README contents", "matching defaults"]
        self.mock_orch.manager.stream_generate.side_effect = [
            iter(["<scratch_pad>\nActions: Call read_file with file_path='README.md'.\n</scratch_pad>"]),
            iter(["<scratch_pad>\nActions: Call grep_search with query='defaults'.\n</scratch_pad>"]),
            iter(["grounded summary"]),
        ]

        # When: the tool loop completes the sequential Qwen planning turns.
        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "inspect README"}],
                "SELF",
                "chat",
                target_model="qwen3.6:latest",
            )
        )

        # Then: both contract tools execute once before the final grounded answer.
        record = store.get_task("qwen-multistep")
        assert record is not None
        assert record["status"] == "done"
        assert self.mock_orch.ctx.tool_executor.execute_async.await_args_list == [
            (("read_file", {"file_path": "README.md"}), {}),
            (("grep_search", {"query": "defaults"}), {}),
        ]

    def test_resume_uses_checkpointed_tool_progress_and_evidence(self, tmp_path: Path):
        # Given: a paused task whose required file read already completed before interruption.
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("resumed-read", "read README", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint(
            "resumed-read",
            4,
            json.dumps(
                {
                    "expected_tools": ["read_file"],
                    "tool_loop": {
                        "used_tools": ["read_file"],
                        "tool_evidence_context": '{"source": "README.md", "content": "local evidence"}',
                    },
                },
            ),
            "partial output",
        )
        self.mock_orch.task_execution_context = TaskExecutionContext("resumed-read", store)
        self.mock_orch.ctx.quality_gate = None
        self.mock_orch.manager.stream_generate.return_value = iter(["resumed summary"])

        # When: the durable task resumes its tool loop.
        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "read README"}],
                "SELF",
                "chat",
            )
        )

        # Then: the existing tool completion satisfies the contract without a duplicate execution.
        record = store.get_task("resumed-read")
        assert record is not None
        assert record["status"] == "done"
        self.mock_orch.ctx.tool_executor.execute_async.assert_not_called()

    def test_records_step_limit_as_unsuccessful(self):
        outcomes: list[TaskOutcome] = []
        tool_xml = (
            "<action_call>\n<tool_call>\n"
            '{"name": "run_bash", "arguments": {"command": "ls"}}\n'
            "</tool_call>\n</action_call>\n"
        )
        self.mock_orch.manager.stream_generate.return_value = iter([tool_xml])
        engine = ToolLoopEngine(self.mock_orch, outcome_recorder=_outcome_recorder(outcomes))

        _ = list(engine.run_loop([{"role": "user", "content": "inspect"}], "CODER", "code", max_steps=1))

        assert len(outcomes) == 1
        assert outcomes[0].success is False
        assert outcomes[0].completion_reason == "step_limit"

    def test_quality_gate_failure_marks_durable_task_failed(self, tmp_path: Path):
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("quality-failed", "write code", "pending", "2026-01-01T00:00:00")
        self.mock_orch.task_execution_context = TaskExecutionContext("quality-failed", store)
        self.mock_orch.manager.stream_generate.return_value = iter(["invalid output"])
        self.mock_orch.ctx.quality_gate.evaluate.return_value = QualityScore(
            grade=QualityGrade.F,
            score=0.0,
            feedback="[QUALITY GATE] required implementation is missing",
            user_message="",
            should_retry=False,
            issues=["incomplete"],
        )
        outcomes: list[TaskOutcome] = []

        _ = list(
            ToolLoopEngine(self.mock_orch, outcome_recorder=_outcome_recorder(outcomes)).run_loop(
                [{"role": "user", "content": "write code"}],
                "CODER",
                "code",
            )
        )

        record = store.get_task("quality-failed")
        assert record is not None
        assert record["status"] == "failed"
        assert record["error"] == "quality_gate_failed: [QUALITY GATE] required implementation is missing"
        assert outcomes[0].success is False
        assert outcomes[0].completion_reason == "quality_gate_failed"

    def test_persists_approval_wait_with_tool_step_checkpoint(self, tmp_path: Path):
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("loop-durable", "write a file", "pending", "2026-01-01T00:00:00")
        self.mock_orch.task_execution_context = TaskExecutionContext("loop-durable", store)
        self.mock_orch.ctx.tool_executor.execute_async.return_value = "[APPROVAL REQUIRED] confirm write"
        self.mock_orch.manager.stream_generate.return_value = iter(
            [
                "<action_call>\n<tool_call>\n"
                + '{"name": "write_file", "arguments": {"path": "report.md"}}\n'
                + "</tool_call>\n</action_call>\n",
            ],
        )

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "write a file"}],
                "CODER",
                "code",
                target_model="qwen3.8",
            ),
        )

        record = store.get_task("loop-durable")
        checkpoint = store.get_last_checkpoint("loop-durable")
        assert record is not None
        assert record["status"] == "paused"
        assert checkpoint is not None
        assert checkpoint["step"] == 1
        assert '"completion_reason": "approval_required"' in checkpoint["context_json"]
        assert '"write_file"' in checkpoint["context_json"]
        assert '"tool_evidence_context"' in checkpoint["context_json"]
        snapshot = load_task_context_snapshot(store, "loop-durable")
        assert snapshot is not None
        assert snapshot.target_model == "qwen3.8"
        assert any(message.content == "test" for message in snapshot.messages)
        assert '"working_memory"' in checkpoint["context_json"]

    def test_read_only_benchmark_defers_completion_to_task_runner(self, tmp_path: Path):
        store = TaskStateStore(str(tmp_path / "tasks.db"))
        _ = store.create_task("benchmark-deferred", "benchmark prompt", "pending", "2026-01-01T00:00:00")
        store.save_checkpoint(
            "benchmark-deferred",
            0,
            '{"benchmark_read_only": true}',
            "",
        )
        self.mock_orch.task_execution_context = TaskExecutionContext("benchmark-deferred", store)
        self.mock_orch.manager.stream_generate.return_value = iter(
            ["def fibonacci(n: int): return n  # O(1), raise ValueError"]
        )
        outcomes: list[TaskOutcome] = []

        _ = list(
            ToolLoopEngine(self.mock_orch, outcome_recorder=_outcome_recorder(outcomes)).run_loop(
                [{"role": "user", "content": "write fibonacci"}],
                "CODER",
                "code",
            )
        )

        record = store.get_task("benchmark-deferred")
        assert record is not None
        assert record["status"] == "running"
        assert outcomes == []

    def test_explicit_target_model_overrides_delegate_role(self):
        self.mock_orch._get_model_for_role.return_value = "role-default"
        self.mock_orch.manager.stream_generate.return_value = iter(["completed"])

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "complete this"}],
                "CODER",
                "code",
                target_model="qwen3.6:latest",
            )
        )

        self.mock_orch.manager.is_loaded.assert_called_once_with("qwen3.6:latest")
        assert self.mock_orch.manager.stream_generate.call_args.kwargs["target"] == "qwen3.6:latest"

    def test_quality_gate_uses_latest_user_message_when_execution_context_follows(self):
        self.mock_orch.manager.stream_generate.return_value = iter(["completed"])

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [
                    {"role": "user", "content": "user request"},
                    {"role": "system", "content": "Task execution context: {}"},
                ],
                "CODER",
                "chat",
            )
        )

        assert self.mock_orch.ctx.quality_gate.evaluate.call_args.args[1] == "user request"

    def test_direct_response_skips_agent_prompt_and_native_tool_schemas(self):
        self.mock_orch.config = {"tool_loop": {"native_function_calling": True}}
        self.mock_orch.manager.generate.return_value = "completed"

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "answer only"}],
                "SELF",
                "chat",
                target_model="qwen3.6:latest",
                direct_response=True,
            )
        )

        self.mock_orch._prepare_agent_prompt.assert_not_called()
        self.mock_orch.manager.stream_generate.assert_not_called()
        assert self.mock_orch.manager.generate.call_args.kwargs["temperature"] == 0.2
        assert self.mock_orch.manager.generate.call_args.kwargs["repeat_penalty"] == 1.1

    def test_direct_response_uses_model_aware_context_shaper(self, tmp_path: Path):
        from antigravity_k.engine.context_shaper import ContextShaper

        shaper = ContextShaper(storage_dir=str(tmp_path / "context"))
        shaper.shape_for_model = MagicMock(
            return_value=[{"role": "user", "content": "condensed request"}],
        )
        self.mock_orch.context_shaper = shaper
        self.mock_orch.config = {"models": {"reasoning": [{"name": "qwen3.8:27b"}]}}
        self.mock_orch.manager.generate.return_value = "completed"

        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                [{"role": "user", "content": "very large request"}],
                "SELF",
                "chat",
                target_model="qwen3.8:27b",
                direct_response=True,
            ),
        )

        shaper.shape_for_model.assert_called_once()
        assert shaper.shape_for_model.call_args.args[2] == "qwen3.8:27b"
        assert "condensed request" in self.mock_orch.manager.generate.call_args.kwargs["prompt"]

    def test_direct_response_prompt_includes_structured_memory_context(self):
        # Given: direct mode receives one authoritative memory system record.
        self.mock_orch.manager.generate.return_value = "SQLite"
        messages = [
            {
                "role": "system",
                "content": (
                    "[Recalled Memory]\n[resolved:project:decision:database source=project scope=project] sqlite"
                ),
            },
            {"role": "user", "content": "데이터베이스 이름만 답해줘"},
        ]

        # When: ToolLoop generates a tool-free direct answer.
        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                messages,
                "SELF",
                "chat",
                target_model="qwen3.6:latest",
                direct_response=True,
            ),
        )

        # Then: the machine-readable memory marker reaches the model prompt.
        prompt = self.mock_orch.manager.generate.call_args.kwargs["prompt"]
        assert "[resolved:project:decision:database source=project scope=project] sqlite" in prompt

    def test_verified_authoritative_memory_answer_skips_prose_revision(self):
        # Given: direct mode returns the exact value from an authoritative memory marker.
        self.mock_orch.manager.generate.return_value = "sqlite"
        self.mock_orch.ctx.quality_gate.evaluate.return_value = QualityScore(
            grade=QualityGrade.F,
            score=0.1,
            feedback="too short",
            user_message="retry",
            should_retry=True,
            issues=["short"],
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "[Recalled Memory]\n[resolved:project:decision:database source=project scope=project] sqlite"
                ),
            },
            {"role": "user", "content": "데이터베이스 이름만 답해줘"},
        ]

        # When: the tool-free direct response completes.
        output = "".join(
            ToolLoopEngine(self.mock_orch).run_loop(
                messages,
                "SELF",
                "chat",
                target_model="qwen3.6:latest",
                direct_response=True,
            ),
        )

        # Then: generic prose scoring cannot overwrite the verified short answer.
        assert output == "sqlite"
        assert self.mock_orch._last_agent_output == "sqlite"
        self.mock_orch.ctx.quality_gate.evaluate.assert_not_called()
        self.mock_orch.manager.generate.assert_called_once()

    def test_contradictory_memory_answer_still_runs_quality_gate(self):
        # Given: direct mode returns a negated sentence containing the authoritative value.
        self.mock_orch.manager.generate.return_value = "not sqlite"
        messages = [
            {
                "role": "system",
                "content": (
                    "[Recalled Memory]\n[resolved:project:decision:database source=project scope=project] sqlite"
                ),
            },
            {"role": "user", "content": "데이터베이스 이름만 답해줘"},
        ]

        # When: the tool-free response completes with the contradictory text.
        _ = list(
            ToolLoopEngine(self.mock_orch).run_loop(
                messages,
                "SELF",
                "chat",
                target_model="qwen3.6:latest",
                direct_response=True,
            ),
        )

        # Then: substring overlap alone cannot bypass normal quality evaluation.
        self.mock_orch.ctx.quality_gate.evaluate.assert_called_once()

    def test_recorder_failure_does_not_fail_tool_loop(self):
        recorder = MagicMock(side_effect=RuntimeError("metrics unavailable"))
        self.mock_orch.manager.stream_generate.return_value = iter(["completed"])
        engine = ToolLoopEngine(self.mock_orch, outcome_recorder=recorder)

        results = list(engine.run_loop([{"role": "user", "content": "finish"}], "CODER", "code"))

        assert any("completed" in result for result in results)
        recorder.assert_called_once()


class TestToolLoopEngineContextCompression:
    """_maybe_compress_context — ContextCompressor 자동 트리거 가드."""

    def _long_messages(self, count: int = 20) -> list[dict[str, str]]:
        return [{"role": "system", "content": "system prompt"}] + [
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"long message {i}: " + "내용 " * 50,
            }
            for i in range(count)
        ]

    def test_compresses_when_over_budget(self, mock_orch: MagicMock):
        from antigravity_k.engine.context_compressor import ContextCompressor

        compressor = ContextCompressor(token_limit=500, keep_last_n=3)
        mock_orch.context_compressor_for.return_value = compressor
        mock_orch._rebuild_prompt.return_value = "rebuilt-prompt"
        engine = ToolLoopEngine(mock_orch)

        shaped, prompt, usage_before, usage_after = _maybe_compress_context(
            engine,
            self._long_messages(),
            "orig-prompt",
            "qwen3.6:latest",
            "code",
            "sys",
            "tools",
            "skills",
        )

        assert usage_before is not None
        assert usage_after is not None
        assert usage_after < usage_before
        assert prompt == "rebuilt-prompt"
        assert shaped != self._long_messages()
        assert shaped[0]["role"] == "system"  # 시스템 메시지 항상 보존

    def test_reinjects_relevant_artifact_after_compression(self, mock_orch: MagicMock):
        engine = ToolLoopEngine(mock_orch)
        raw_result = "header\n" + ("x" * 8_000) + "\nagent_models:\n  default: qwen3.6:latest\n" + ("y" * 8_000)
        formatted = _format_tool_response(
            engine,
            ToolCall(name="read_file", arguments={"file_path": "config.yaml"}),
            raw_result,
        )
        compressor = MagicMock()
        compressor.needs_compression.return_value = True
        compressor.usage_percent.side_effect = [90.0, 20.0]
        compressor.adaptive_compress.return_value = [
            {"role": "user", "content": "continue"},
        ]
        mock_orch.context_compressor_for.return_value = compressor
        mock_orch._rebuild_prompt.return_value = "rebuilt-prompt"

        shaped, prompt, usage_before, usage_after = _maybe_compress_context(
            engine,
            [
                {"role": "user", "content": "inspect agent_models routing"},
                {"role": "assistant", "content": formatted},
            ],
            "orig-prompt",
            "qwen3.6:latest",
            "code",
            "sys",
            "tools",
            "skills",
            focus_terms=("agent_models",),
        )

        assert shaped == [{"role": "user", "content": "continue"}]
        assert prompt.startswith("rebuilt-prompt\n[CONTEXT_ARTIFACT_RECALL]")
        assert '"ref_id":"artifact-' in prompt
        assert "agent_models" in prompt
        assert usage_before == 90.0
        assert usage_after == 20.0

    def test_noop_within_budget(self, mock_orch: MagicMock):
        from antigravity_k.engine.context_compressor import ContextCompressor

        compressor = ContextCompressor(token_limit=5000, keep_last_n=3)
        mock_orch.context_compressor_for.return_value = compressor
        engine = ToolLoopEngine(mock_orch)

        messages = [{"role": "user", "content": "short"}]
        shaped, prompt, usage_before, usage_after = _maybe_compress_context(
            engine, messages, "orig-prompt", "qwen3.6:latest", "code", "sys", "tools", "skills"
        )

        assert usage_before is None and usage_after is None
        assert shaped == messages
        assert prompt == "orig-prompt"

    def test_mock_compressor_skipped(self, mock_orch: MagicMock):
        engine = ToolLoopEngine(mock_orch)  # context_compressor_for → MagicMock

        messages = [{"role": "user", "content": "x"}]
        shaped, prompt, usage_before, _usage_after = _maybe_compress_context(
            engine, messages, "p", "qwen3.6:latest", "code", "s", "t", "k"
        )

        assert usage_before is None
        assert shaped == messages
        assert prompt == "p"

    def test_none_compressor_skipped(self, mock_orch: MagicMock):
        mock_orch.context_compressor_for.return_value = None
        engine = ToolLoopEngine(mock_orch)

        messages = [{"role": "user", "content": "x"}]
        shaped, prompt, usage_before, _usage_after = _maybe_compress_context(
            engine, messages, "p", "qwen3.6:latest", "code", "s", "t", "k"
        )

        assert usage_before is None
        assert shaped == messages
        assert prompt == "p"

    def test_checkpoint_context_is_bounded_for_long_sessions(self, mock_orch: MagicMock):
        messages = [{"role": "user", "content": f"turn-{index}"} for index in range(300)]

        engine = ToolLoopEngine(mock_orch)
        _refresh_checkpoint_context(engine, messages)

        checkpoint_messages = cast(list[dict[str, str]], getattr(engine, "_checkpoint_messages"))
        assert len(checkpoint_messages) == 256
        assert checkpoint_messages[-1]["content"] == "turn-299"
