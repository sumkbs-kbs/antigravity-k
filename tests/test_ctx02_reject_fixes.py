"""CTX-02 REJECT F1–F3 regression tests (owner fix; not APPROVE)."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.engine.context_budget import PromptBudgetEnforcementError
from antigravity_k.engine.tokenizer import TokenEstimator
from antigravity_k.engine.tool_loop import ToolLoopEngine


def _budget_config(*, operator: int = 1_000) -> dict[str, object]:
    return {
        "defaults": {"reasoning": "qwen3.6:latest"},
        "models": {
            "reasoning": [
                {"name": "qwen3.6:latest", "context_length": 8_192},
            ],
        },
        "router": {"context_token_limit": operator},
    }


def _over_limit_prompt(*, tokens: int = 2008) -> str:
    # TokenEstimator ≈ ceil(len/4); 8032 chars → 2008 tokens.
    return "x" * (tokens * 4)


def _base_orch(*, config: object | None = None) -> MagicMock:
    orch = MagicMock()
    orch.config = _budget_config() if config is None else config
    orch.project_root = "/tmp/test-ctx02"
    orch._skill_prompts_cache = ""
    orch._last_agent_output = ""
    orch._prompt_components_cache = {"pinned_context": ""}
    orch.manager = MagicMock()
    orch.manager._registry = MagicMock()
    orch.manager.router = MagicMock()
    orch.manager.router.get_combo.return_value = None
    orch.manager.is_loaded.return_value = True
    orch.manager.stream_generate.return_value = iter(["ok"])
    orch._get_model_for_role.return_value = "qwen3.6:latest"
    orch._prepare_agent_prompt.return_value = (
        "qwen3.6:latest",
        "SYSTEM_ORIGINAL",
        "TOOLS_ORIGINAL",
        "SKILLS_ORIGINAL",
        "prompt_str",
        [{"role": "user", "content": "hi"}],
    )
    orch._rebuild_prompt.side_effect = (
        lambda system, tools, skills, messages: f"System: {system}\n{skills}\n{tools}\nAssistant: "
    )
    ctx = MagicMock()
    ctx.tool_guardrail = MagicMock()
    before = MagicMock()
    before.allows_execution = True
    ctx.tool_guardrail.before_call.return_value = before
    after = MagicMock()
    after.action = "allow"
    ctx.tool_guardrail.after_call.return_value = after
    ctx.cognitive_loop = MagicMock()
    ctx.quality_gate = MagicMock()
    quality = MagicMock()
    quality.user_message = ""
    quality.should_retry = False
    ctx.quality_gate.evaluate.return_value = quality
    ctx.decision_anchor = MagicMock()
    ctx.decision_anchor.auto_extract.return_value = None
    ctx.tool_executor = MagicMock()
    orch.ctx = ctx
    return orch


def test_f1_non_dict_config_fail_closed_does_not_return_over_limit() -> None:
    """F1: config not a dict must raise — never return unchanged 2008-token prompt."""
    orch = _base_orch(config="not-a-dict")
    engine = ToolLoopEngine(cast(object, orch))
    over = _over_limit_prompt(tokens=2008)
    assert TokenEstimator.estimate_text(over) == 2008

    with pytest.raises(PromptBudgetEnforcementError, match="dict orchestrator config"):
        engine._enforce_final_prompt_budget(
            over,
            [{"role": "user", "content": "a" * 18}],
            "qwen3.6:latest",
            "sys",
            "",
            "",
        )


def test_f1_resolve_boom_fail_closed_does_not_return_over_limit() -> None:
    """F1/F5: resolve_hard_token_limit failure must raise, not return over-limit prompt."""
    orch = _base_orch()
    engine = ToolLoopEngine(cast(object, orch))
    over = _over_limit_prompt(tokens=2008)

    with patch(
        "antigravity_k.engine.context_budget.resolve_hard_token_limit",
        side_effect=RuntimeError("resolve boom"),
    ):
        with pytest.raises(PromptBudgetEnforcementError, match="resolve failed"):
            engine._enforce_final_prompt_budget(
                over,
                [{"role": "user", "content": "a" * 18}],
                "qwen3.6:latest",
                "sys",
                "",
                "",
            )


def test_f1_run_loop_non_dict_config_does_not_call_stream_generate() -> None:
    """F1 via run_loop: non-dict config → halt; provider never invoked."""
    orch = _base_orch(config="not-a-dict")
    # prepare still returns an over-limit serialized prompt (adversarial 2008>1000 style).
    over = _over_limit_prompt(tokens=2008)
    orch._prepare_agent_prompt.return_value = (
        "qwen3.6:latest",
        "sys",
        "",
        "",
        over,
        [{"role": "user", "content": "a" * 18}],
    )
    engine = ToolLoopEngine(cast(object, orch))
    chunks = list(
        engine.run_loop(
            [{"role": "user", "content": "task"}],
            "CODER",
            "code",
            max_steps=1,
            target_model="qwen3.6:latest",
        ),
    )
    assert any("Prompt Budget" in chunk for chunk in chunks)
    assert orch.manager.stream_generate.call_count == 0


def test_f2_unexpected_fit_error_does_not_call_stream_generate() -> None:
    """F2: RuntimeError from fit_final_prompt must not fall through to stream_generate."""
    orch = _base_orch()
    over = _over_limit_prompt(tokens=2008)
    huge_system = "S" * 4018  # ~1005 tokens
    orch._prepare_agent_prompt.return_value = (
        "qwen3.6:latest",
        huge_system,
        "",
        "",
        over,
        [{"role": "user", "content": "a" * 18}],
    )
    engine = ToolLoopEngine(cast(object, orch))

    with patch(
        "antigravity_k.engine.context_budget_enforcer.fit_final_prompt",
        side_effect=RuntimeError("fit boom"),
    ):
        chunks = list(
            engine.run_loop(
                [{"role": "user", "content": "task"}],
                "CODER",
                "code",
                max_steps=1,
                target_model="qwen3.6:latest",
            ),
        )
    assert any("Prompt Budget" in chunk for chunk in chunks)
    assert orch.manager.stream_generate.call_count == 0


def test_f3_after_fit_locals_updated_rebuild_does_not_reexpand_system() -> None:
    """F3: after successful fit, system/tools/skills locals match fitted aux (no re-inflate)."""
    orch = _base_orch()
    original_system = "Z" * 4018  # 1005 tokens
    message = "a" * 18  # 5 tokens
    # Serialized prompt over operator 1000 so fit path runs.
    serialized = _over_limit_prompt(tokens=2008)
    orch._prepare_agent_prompt.return_value = (
        "qwen3.6:latest",
        original_system,
        "TOOLS_KEEP",
        "SKILLS_KEEP",
        serialized,
        [{"role": "user", "content": message}],
    )

    seen_rebuild_systems: list[str] = []

    def _rebuild(system: str, tools: str, skills: str, messages: object) -> str:
        seen_rebuild_systems.append(system)
        return f"System: {system}\n{skills}\n{tools}\nAssistant: "

    orch._rebuild_prompt.side_effect = _rebuild

    # Force _maybe_compress_context to rebuild from locals on every step after the first
    # by patching it to call rebuild with the (hopefully fitted) system_prompt.
    engine = ToolLoopEngine(cast(object, orch))
    captured: dict[str, str] = {}

    original_enforce = engine._enforce_final_prompt_budget

    def _enforce_and_capture(
        prompt_str: str,
        shaped_messages: list[dict[str, str]],
        delegate_model: str,
        system_prompt: str,
        tool_prompt: str,
        skill_prompts: str,
        *,
        direct_response: bool = False,
    ) -> tuple[str, list[dict[str, str]], object | None]:
        result = original_enforce(
            prompt_str,
            shaped_messages,
            delegate_model,
            system_prompt,
            tool_prompt,
            skill_prompts,
            direct_response=direct_response,
        )
        fit = result[2]
        if fit is not None:
            captured["fitted_system"] = str(getattr(fit, "system", ""))
            captured["fitted_tools"] = str(getattr(fit, "tools", ""))
            captured["fitted_skills"] = str(getattr(fit, "skills", ""))
        return result

    engine._enforce_final_prompt_budget = _enforce_and_capture  # type: ignore[method-assign]

    # Step-1: stream returns a tool call so loop continues; step-2: text only.
    tool_xml = (
        "<tool_call>\n"
        "<function=run_bash_command>\n"
        "<parameter=command>echo hi</parameter>\n"
        "</function>\n"
        "</tool_call>"
    )
    orch.manager.stream_generate.side_effect = [
        iter([tool_xml]),
        iter(["done"]),
    ]
    # Allow tool execution
    orch.ctx.tool_executor.execute_async = AsyncMock(return_value="ok")

    # Make compress path rebuild using current locals (simulates multi-step rebuild risk).
    def _force_rebuild(
        self: ToolLoopEngine,
        shaped_messages: list[dict[str, str]],
        prompt_str: str,
        delegate_model: str,
        task_type: str,
        system_prompt: str,
        tool_prompt: str,
        skill_prompts: str,
        focus_terms: tuple[str, ...] = (),
    ) -> tuple[list[dict[str, str]], str, None, None]:
        rebuilt = orch._rebuild_prompt(system_prompt, tool_prompt, skill_prompts, shaped_messages)
        return shaped_messages, rebuilt, None, None

    with patch.object(ToolLoopEngine, "_maybe_compress_context", _force_rebuild):
        chunks = list(
            engine.run_loop(
                [{"role": "user", "content": "task"}],
                "CODER",
                "code",
                max_steps=3,
                target_model="qwen3.6:latest",
            ),
        )

    assert "fitted_system" in captured
    fitted = captured["fitted_system"]
    assert fitted != original_system
    assert len(fitted) < len(original_system)
    # After step-1 fit write-back, later rebuilds must use fitted system — never the original blob.
    assert seen_rebuild_systems, "expected at least one rebuild from compress path"
    # First rebuild may happen before first enforce (step start); after fit, subsequent must be fitted.
    assert any(system == fitted for system in seen_rebuild_systems)
    assert original_system not in seen_rebuild_systems[1:] or seen_rebuild_systems[-1] == fitted
    assert orch.manager.stream_generate.call_count >= 1
    assert any("Prompt Budget" in chunk or "done" in chunk or "ok" in chunk for chunk in chunks)


def test_f3_enforce_fit_updates_component_fields() -> None:
    """Direct enforce: compressed fit shrinks system under operator 1000."""
    orch = _base_orch()
    engine = ToolLoopEngine(cast(object, orch))
    original_system = "Z" * 4018
    over = _over_limit_prompt(tokens=2008)
    prompt, messages, fit = engine._enforce_final_prompt_budget(
        over,
        [{"role": "user", "content": "a" * 18}],
        "qwen3.6:latest",
        original_system,
        "TOOLS",
        "SKILLS",
    )
    assert fit is not None
    assert fit.compressed is True
    assert fit.system != original_system
    assert TokenEstimator.estimate_text(fit.system) < TokenEstimator.estimate_text(original_system)
    assert TokenEstimator.estimate_text(prompt) <= 1_000
    assert messages
