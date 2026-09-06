"""CTX-03: compression failure policy and observability."""

from __future__ import annotations

import json
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.context_budget import (
    HardTokenLimit,
    PromptBudgetExceededError,
    PromptComponentLedger,
)
from antigravity_k.engine.context_compress_observability import (
    ALERT_BUDGET_HEADROOM_PCT,
    ALERT_COMPRESS_FAILURE_RATE,
    CompressFailureCode,
    CompressTelemetryRecord,
    ContextCompressAttempt,
    decide_post_compress_policy,
    headroom_pct,
    should_alert_low_headroom,
    ui_status_line,
)
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


def _base_orch(*, config: object | None = None, prompt: str = "prompt_str") -> MagicMock:
    orch = MagicMock()
    orch.config = _budget_config() if config is None else config
    orch.project_root = "/tmp/test-ctx03"
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
        "SYSTEM",
        "TOOLS",
        "SKILLS",
        prompt,
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
    orch.task_execution_context = None
    orch.context_compressor_for.return_value = None
    return orch


def test_policy_degrade_vs_halt() -> None:
    assert decide_post_compress_policy(compress_failed=True, over_hard_limit=False) == "degraded"
    assert decide_post_compress_policy(compress_failed=True, over_hard_limit=True) == "halted"
    assert decide_post_compress_policy(compress_failed=False, over_hard_limit=True) == "halted"
    assert (
        decide_post_compress_policy(compress_failed=False, over_hard_limit=False, budget_enforce_failed=True)
        == "halted"
    )
    assert decide_post_compress_policy(compress_failed=False, over_hard_limit=False) == "success"


def test_alert_thresholds_documented_constants() -> None:
    assert ALERT_COMPRESS_FAILURE_RATE == 0.05
    assert ALERT_BUDGET_HEADROOM_PCT == 15.0
    assert headroom_pct(input_total=900, hard_limit_input=1000) == pytest.approx(10.0)
    assert should_alert_low_headroom(input_total=900, hard_limit_input=1000) is True
    assert should_alert_low_headroom(input_total=800, hard_limit_input=1000) is False


def test_telemetry_payload_includes_required_fields() -> None:
    record = CompressTelemetryRecord(
        outcome="degraded",
        trigger="tool_loop",
        strategy="summarize",
        digest="deadbeefcafebabe",
        elapsed_ms=12.5,
        failure_code=CompressFailureCode.ADAPTIVE_COMPRESS_ERROR.value,
        usage_before_pct=92.0,
        usage_after_pct=None,
        hard_limit_input=1000,
        serialized_before=1200,
        serialized_after=1200,
        message="boom",
    )
    payload = record.as_payload()
    assert payload["outcome"] == "degraded"
    assert payload["strategy"] == "summarize"
    assert payload["digest"] == "deadbeefcafebabe"
    assert payload["elapsed_ms"] == 12.5
    assert payload["failure_code"] == "adaptive_compress_error"
    assert "tokens_before" in payload and "tokens_after" in payload
    assert payload["alert_thresholds"]["compress_failure_rate"] == 0.05
    assert record.event_type() == "context.compress.degraded"
    assert "degraded" in ui_status_line(record)
    assert "Prompt Budget" in ui_status_line(
        CompressTelemetryRecord(outcome="halted", trigger="tool_loop", failure_code="still_over_limit")
    )
    assert "success" in ui_status_line(
        CompressTelemetryRecord(
            outcome="success",
            trigger="tool_loop",
            usage_before_pct=90.0,
            usage_after_pct=40.0,
            strategy="truncate",
            digest="abc123",
        )
    )


def test_maybe_compress_marks_failure_instead_of_fail_open() -> None:
    orch = _base_orch()
    compressor = MagicMock()
    compressor.needs_compression.return_value = True
    compressor.usage_percent.return_value = 95.0
    compressor.suggest_strategy.return_value = "summarize"
    compressor.adaptive_compress.side_effect = RuntimeError("compress boom")
    orch.context_compressor_for.return_value = compressor
    engine = ToolLoopEngine(cast(object, orch))

    attempt = engine._maybe_compress_context(
        [{"role": "user", "content": "x" * 200}],
        "orig-prompt",
        "qwen3.6:latest",
        "code",
        "sys",
        "tools",
        "skills",
    )
    assert isinstance(attempt, ContextCompressAttempt)
    assert attempt.attempted is True
    assert attempt.failed is True
    assert attempt.failure_code == CompressFailureCode.ADAPTIVE_COMPRESS_ERROR.value
    assert attempt.prompt == "orig-prompt"
    assert attempt.strategy == "summarize"
    assert attempt.elapsed_ms >= 0.0


def test_compress_failure_then_over_limit_halts_before_provider() -> None:
    """Compress failure + hard-limit enforce failure must halt before provider.

    If adaptive compress fails but final fit can still bound the prompt, policy is
    *degraded* (covered elsewhere). Halt requires the final gate to refuse.
    """

    over = "x" * (2008 * 4)
    assert TokenEstimator.estimate_text(over) == 2008
    orch = _base_orch(prompt=over)
    compressor = MagicMock()
    compressor.needs_compression.return_value = True
    compressor.usage_percent.return_value = 99.0
    compressor.suggest_strategy.return_value = "truncate"
    compressor.adaptive_compress.side_effect = RuntimeError("nope")
    orch.context_compressor_for.return_value = compressor
    orch._prepare_agent_prompt.return_value = (
        "qwen3.6:latest",
        "sys",
        "",
        "",
        over,
        [{"role": "user", "content": "a" * 18}],
    )

    ledger = PromptComponentLedger(
        system=0, tools=0, skills=0, memory=0, artifacts=0, messages=2008, output_reserve=128
    )
    hard = HardTokenLimit(
        declared=8192, empirical=None, operator=1000, output_reserve=128, effective=1000, input_budget=872
    )

    engine = ToolLoopEngine(cast(object, orch))
    with patch(
        "antigravity_k.engine.context_budget_enforcer.fit_final_prompt",
        side_effect=PromptBudgetExceededError("still over", ledger=ledger, hard_limit=hard),
    ):
        chunks = list(
            engine.run_loop(
                [{"role": "user", "content": "task"}],
                "CODER",
                "code",
                max_steps=1,
                target_model="qwen3.6:latest",
            )
        )
    joined = "".join(chunks)
    assert "halted" in joined.lower()
    assert "Prompt Budget" in joined
    assert orch.manager.stream_generate.call_count == 0
    assert engine.telemetry.compress_failures >= 1
    assert engine.telemetry.compress_halted >= 1


def test_compress_failure_under_limit_is_degraded_not_halt() -> None:
    orch = _base_orch(config=_budget_config(operator=50_000), prompt="short under budget")
    compressor = MagicMock()
    compressor.needs_compression.return_value = True
    compressor.usage_percent.return_value = 90.0
    compressor.suggest_strategy.return_value = "summarize"
    compressor.adaptive_compress.side_effect = RuntimeError("transient")
    orch.context_compressor_for.return_value = compressor

    engine = ToolLoopEngine(cast(object, orch))
    chunks = list(
        engine.run_loop(
            [{"role": "user", "content": "hello"}],
            "CODER",
            "code",
            max_steps=1,
            target_model="qwen3.6:latest",
        )
    )
    joined = "".join(chunks)
    assert "degraded" in joined.lower()
    assert engine.telemetry.compress_failures >= 1
    assert engine.telemetry.compress_degraded >= 1
    assert engine.telemetry.compress_halted == 0
    # Under hard-limit: provider may still be invoked (limited degrade, not halt).
    assert orch.manager.stream_generate.call_count >= 1


def test_event_payload_json_roundtrip() -> None:
    record = CompressTelemetryRecord(
        outcome="success",
        trigger="stream_pre",
        strategy="move_to_workspace",
        digest="0123456789abcdef",
        elapsed_ms=3.25,
        usage_before_pct=81.0,
        usage_after_pct=60.0,
    )
    parsed = json.loads(record.payload_json())
    assert parsed["trigger"] == "stream_pre"
    assert parsed["tokens_before"]["messages"] == 0
