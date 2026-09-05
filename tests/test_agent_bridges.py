"""Phase 3 테스트: 에이전트 브리지 스펙.

벤치마킹 출처: unsloth `unsloth start claude/codex/...` 원커맨드 브리지.
에이전트별 프로토콜 결정, 환경변수 매핑, 폴백 동작을 검증한다.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.agent_bridges import (
    AGENT_BRIDGES,
    ANTHROPIC_ENDPOINT,
    OPENAI_ENDPOINT,
    UnknownAgentError,
    format_bridge_plan,
    resolve_bridge,
)


def test_supported_agents_present() -> None:
    """unsloth start와 동일한 주요 에이전트 집합을 지원해야 한다."""
    assert {"claude", "codex", "opencode", "openclaw", "hermes"} <= set(AGENT_BRIDGES)


def test_claude_uses_anthropic_protocol() -> None:
    spec, env = resolve_bridge(
        "claude",
        model="qwen3.8",
        api_base="http://127.0.0.1:8400",
    )
    assert spec.protocol == "anthropic"
    # anthropic 계열: CC가 /v1/messages를 직접 붙이므로 base에 /v1 금지 (Phase 36 수정)
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8400"
    assert env["ANTHROPIC_MODEL"] == "qwen3.8"
    assert ANTHROPIC_ENDPOINT == "/v1/messages"


def test_claude_recommended_env_block() -> None:
    """Phase 36: 미등록 모델 카탈로그 매핑 env 블록이 포함되는지."""
    _, env = resolve_bridge(
        "claude",
        model="qwen3.8:latest",
        api_base="http://127.0.0.1:8400",
        context_window=262144,
    )
    assert env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "262144"
    assert env["ANTHROPIC_SMALL_FAST_MODEL"] == "qwen3.8:latest"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "qwen3.8:latest"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "qwen3.8:latest"


def test_claude_context_window_defaults_to_200k() -> None:
    """윈도 미지정 시 CC 보수 기본값과 동일한 200000으로 채워진다."""
    _, env = resolve_bridge("claude", model="m", api_base="http://127.0.0.1:8400")
    assert env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "200000"


def test_codex_uses_openai_protocol() -> None:
    spec, env = resolve_bridge(
        "codex",
        model="qwen3.8",
        api_base="http://127.0.0.1:8400",
    )
    assert spec.protocol == "openai"
    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:8400/v1"
    assert OPENAI_ENDPOINT == "/v1/chat/completions"


def test_unknown_agent_raises() -> None:
    with pytest.raises(UnknownAgentError) as exc_info:
        resolve_bridge("notanagent", model="m")
    assert "notanagent" in str(exc_info.value)
    assert "claude" in str(exc_info.value)  # 지원 목록 안내 포함


def test_model_fallback_to_default() -> None:
    _, env = resolve_bridge(
        "claude",
        model="",
        default_model="qwen3.6:latest",
        api_base="http://127.0.0.1:8400",
    )
    assert env["ANTHROPIC_MODEL"] == "qwen3.6:latest"


def test_missing_model_raises() -> None:
    with pytest.raises(UnknownAgentError, match="모델"):
        resolve_bridge("claude", model="", default_model="")


def test_api_base_with_v1_suffix_not_duplicated() -> None:
    _, env = resolve_bridge(
        "codex",
        model="m",
        api_base="http://127.0.0.1:8400/v1",
    )
    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:8400/v1"


def test_trailing_slash_normalized() -> None:
    _, env = resolve_bridge(
        "claude",
        model="m",
        api_base="http://127.0.0.1:8400/",
    )
    # anthropic 계열은 /v1 없이 (CC가 직접 붙임)
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8400"


def test_format_bridge_plan_contains_env_and_endpoint() -> None:
    spec, env = resolve_bridge("claude", model="qwen3.8", api_base="http://127.0.0.1:8400")
    plan = format_bridge_plan(spec, env)
    assert "Claude Code" in plan
    assert "/v1/messages" in plan
    assert "export ANTHROPIC_BASE_URL=http://127.0.0.1:8400" in plan
    assert "agk serve" in plan


def test_claude_plan_documents_model_picker_mapping() -> None:
    """Phase 36: behavesAs/modelPicker 설정 힌트가 플랜에 포함되는지."""
    spec, env = resolve_bridge(
        "claude",
        model="qwen3.8:latest",
        api_base="http://127.0.0.1:8400",
        context_window=262144,
    )
    plan = format_bridge_plan(spec, env)
    assert "modelPicker" in plan
    assert "behavesAs" in plan
    assert "qwen3.8:latest" in plan


def test_codex_plan_documents_responses_config() -> None:
    """Phase 35/36: Codex는 config 오버라이드 안내가 플랜에 포함되는지."""
    spec, _env = resolve_bridge("codex", model="qwen3.8:latest", api_base="http://127.0.0.1:8400")
    plan = format_bridge_plan(spec, _env)
    assert "wire_api" in plan and "responses" in plan
    assert "/dev/null" in plan  # stdin 끊기 안내


def test_agent_name_case_insensitive() -> None:
    spec, _ = resolve_bridge("CLAUDE", model="m", api_base="http://127.0.0.1:8400")
    assert spec.name == "claude"
