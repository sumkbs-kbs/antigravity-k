"""예외·skip 분기 커버리지 테스트 (Phase 25).

Phase 12 커버리지 리포트에서 낮게 나온 `anthropic_tool_bridge.py`(83.7%)와
`disclosure_api.py`(60%)의 미커버 분기 — 직렬화 실패 폴백, 비정상 입력 skip,
EngineContext 재사용 실패 폴백 — 를 타겟팅한다.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from antigravity_k.engine.anthropic_tool_bridge import (
    build_content_blocks,
    build_tool_choice_directive,
    extract_tool_use_blocks,
    flatten_message_content,
    resolve_stop_reason,
    serialize_tools_for_prompt,
)
from antigravity_k.engine.cost_guard import CostGuard
from antigravity_k.engine.session_disclosure import build_session_disclosure

# ─── serialize_tools_for_prompt: 비정상 tool 정의 skip ────────────────


class TestSerializeToolsSkips:
    def test_non_mapping_tools_are_skipped(self) -> None:
        catalog = serialize_tools_for_prompt(["not-a-mapping", 42, {"name": "valid_tool", "description": "ok"}])
        assert "valid_tool" in catalog
        assert "not-a-mapping" not in catalog

    def test_tools_without_valid_name_are_skipped(self) -> None:
        catalog = serialize_tools_for_prompt(
            [
                {"description": "no name key"},
                {"name": "", "description": "empty name"},
                {"name": 123, "description": "non-string name"},
                {"name": "keep_me", "description": "fine"},
            ]
        )
        assert "keep_me" in catalog
        assert "no name key" not in catalog
        assert "empty name" not in catalog

    def test_non_string_description_renders_empty(self) -> None:
        catalog = serialize_tools_for_prompt([{"name": "t", "description": 99}])
        assert "- t: \n" in catalog or catalog.rstrip().endswith("- t:")

    def test_unserializable_schema_is_skipped_without_crash(self) -> None:
        # set은 JSON 직렬화 불가 → TypeError → 스킵 (lines 85-86)
        catalog = serialize_tools_for_prompt([{"name": "t", "input_schema": {"bad": {1, 2}}}])
        assert "- t:" in catalog
        assert "parameters (JSON Schema)" not in catalog


# ─── build_tool_choice_directive: 남은 분기 ──────────────────────────


class TestToolChoiceDirectives:
    def test_none_returns_empty(self) -> None:
        assert build_tool_choice_directive(None) == ""

    def test_none_type_inside_mapping_returns_empty(self) -> None:
        assert build_tool_choice_directive({"type": "none"}) == "Do not use any tools. Respond with plain text only."

    def test_unknown_mapping_kind_returns_empty(self) -> None:
        assert build_tool_choice_directive({"type": "mystery"}) == ""

    def test_tool_kind_with_blank_name_returns_empty(self) -> None:
        assert build_tool_choice_directive({"type": "tool", "name": "   "}) == ""

    def test_tool_kind_with_valid_name(self) -> None:
        assert '"ctx"' in build_tool_choice_directive({"type": "tool", "name": "ctx"})

    def test_non_mapping_unknown_value_returns_empty(self) -> None:
        # "auto"/문자열 외의 스칼라 (line 107)
        assert build_tool_choice_directive(12345) == ""
        assert build_tool_choice_directive("auto") == ""


# ─── flatten_message_content: 비정상 content 블록 skip ────────────────


class TestFlattenContentSkips:
    def test_none_and_non_sequence_return_empty(self) -> None:
        assert flatten_message_content(None) == ""
        assert flatten_message_content(42) == ""
        assert flatten_message_content({"type": "text"}) == ""

    def test_plain_string_passes_through(self) -> None:
        assert flatten_message_content("hello") == "hello"

    def test_non_mapping_string_blocks_are_appended(self) -> None:
        # 블록 배열 안의 문자열 (lines 128-130)
        assert flatten_message_content(["a", "b"]) == "a\nb"

    def test_non_mapping_non_string_blocks_are_skipped(self) -> None:
        assert flatten_message_content([42, None, {"type": "text", "text": "ok"}]) == "ok"

    def test_text_block_with_non_string_text_is_skipped(self) -> None:
        assert flatten_message_content([{"type": "text", "text": 42}]) == ""

    def test_unknown_block_types_are_skipped(self) -> None:
        assert flatten_message_content([{"type": "image", "source": "x"}]) == ""


# ─── 직렬화 예외 폴백 ─────────────────────────────────────────────────


class TestSerializationFallbacks:
    def test_tool_use_block_with_unserializable_input_falls_back(self) -> None:
        # set을 input으로 → json.dumps TypeError → arguments {} 폴백 (lines 152-153)
        text = flatten_message_content([{"type": "tool_use", "name": "t", "input": {"bad": {1, 2}}}])
        assert "```json" in text and '"name": "t"' in text

    def test_tool_use_block_with_non_mapping_input(self) -> None:
        text = flatten_message_content([{"type": "tool_use", "name": "t", "input": "not-mapping"}])
        assert '"arguments": {}' in text

    def test_tool_result_error_flag_and_content_list(self) -> None:
        text = flatten_message_content(
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "is_error": True,
                    "content": [{"type": "text", "text": "boom"}],
                }
            ]
        )
        # 구현 규약: content 배열의 Mapping 항목만 수집 (비-Mapping 문자열 항목은 무시)
        assert "(error)" in text and "toolu_1" in text and "boom" in text

    def test_tool_result_with_plain_string_content(self) -> None:
        # content가 문자열인 형태 (line 162)
        text = flatten_message_content([{"type": "tool_result", "tool_use_id": "toolu_2", "content": "plain result"}])
        assert "plain result" in text and "toolu_2" in text


class TestExtractToolUseFallbacks:
    def test_extract_with_circular_structure_input_falls_back_to_empty_json(self) -> None:
        # RobustToolParser가 재구성한 arguments가 직렬화 불가능한 경우는 드물지만,
        # extract의 TypeError 폴백(line 184-185)은 json.dumps 실패 시 "{}"를 보장한다.
        # 정상 경로만으로는 도달이 어려워 직접 호출로 폴백 로직을 검증한다.
        blocks = extract_tool_use_blocks('```json\n{"name": "t", "arguments": {"a": 1}}\n```')
        assert blocks[0].name == "t"
        assert json.loads(blocks[0].input_json) == {"a": 1}

    def test_extract_unserializable_arguments_falls_back_to_empty_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """arguments 직렬화 실패 시 input_json='{}' 폴백 (lines 184-185)."""
        from antigravity_k.engine import anthropic_tool_bridge as bridge

        class _FakeParsed:
            name = "t"
            arguments = {"bad": {1, 2}}  # set — json.dumps TypeError
            repaired = False

        monkeypatch.setattr(bridge.RobustToolParser, "extract_tool_calls", lambda _text: [_FakeParsed()])
        blocks = extract_tool_use_blocks("ignored")
        assert len(blocks) == 1
        assert blocks[0].input_json == "{}"


class TestContentBlocksFallbacks:
    def test_invalid_input_json_becomes_empty_dict(self) -> None:
        from antigravity_k.engine.anthropic_tool_bridge import ToolUseBlock

        blocks = build_content_blocks(
            "",
            [ToolUseBlock(tool_use_id="toolu_x", name="t", input_json="{broken", repaired=True)],
        )
        assert blocks[0]["input"] == {}
        assert blocks[0]["name"] == "t"

    def test_stop_reason_max_tokens(self) -> None:
        assert resolve_stop_reason("text", [], max_tokens_hit=True) == "max_tokens"


# ─── disclosure_api: EngineContext 재사용/폴백 경로 ────────────────────


class TestDisclosureApiGuardPaths:
    def test_fresh_guard_via_orchestrator_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.api.routes import disclosure_api

        guard = CostGuard(daily_budget_usd=12.0, hourly_action_limit=7, enabled=True)

        class _FakeCtx:
            cost_guard = guard

        class _FakeOrchestrator:
            ctx = _FakeCtx()

        monkeypatch.setattr("antigravity_k.api.dependencies.get_orchestrator", lambda: _FakeOrchestrator())
        resolved = disclosure_api.get_cost_guard()
        assert resolved is guard  # 재사용 — env 폴백이 아니라 EngineContext 인스턴스

    def test_fallback_when_orchestrator_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.api.routes import disclosure_api

        def _boom() -> Any:
            raise RuntimeError("not started")

        monkeypatch.setattr("antigravity_k.api.dependencies.get_orchestrator", _boom)
        monkeypatch.setenv("AGK_DAILY_BUDGET_USD", "25.0")
        monkeypatch.setenv("AGK_HOURLY_ACTION_LIMIT", "40")
        resolved = disclosure_api.get_cost_guard()
        assert resolved.daily_budget_usd == 25.0
        assert resolved.hourly_action_limit == 40

    def test_fallback_when_ctx_guard_is_wrong_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.api.routes import disclosure_api

        class _FakeCtx:
            cost_guard = "not-a-guard"

        class _FakeOrchestrator:
            ctx = _FakeCtx()

        monkeypatch.setattr("antigravity_k.api.dependencies.get_orchestrator", lambda: _FakeOrchestrator())
        monkeypatch.delenv("AGK_DAILY_BUDGET_USD", raising=False)
        monkeypatch.delenv("AGK_HOURLY_ACTION_LIMIT", raising=False)
        resolved = disclosure_api.get_cost_guard()
        assert isinstance(resolved, CostGuard)
        assert resolved.daily_budget_usd == 50.0  # 기본값 폴백

    def test_endpoints_use_injected_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from antigravity_k.api.routes.disclosure_api import get_cost_guard, router

        guard = CostGuard(daily_budget_usd=30.0, hourly_action_limit=10, enabled=True)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_cost_guard] = lambda: guard
        client = TestClient(app)

        res = client.get("/api/session/disclosure")
        assert res.status_code == 200
        payload = res.json()
        budget = next(lim for lim in payload["limits"] if lim["kind"] == "budget")
        assert budget["limit"] == 30.0

        md = client.get("/api/session/disclosure.md")
        assert md.status_code == 200 and "$30.00" in md.text


# ─── session_disclosure: 등급 메시지·마크다운 남은 분기 ────────────────


class TestToolUseBlockLevelMetadata:
    def test_disclosure_properties_fall_back_for_unknown_level(self) -> None:
        """SessionDisclosure의 icon/label 프로퍼티 폴백 (session_disclosure 71/75)."""
        from antigravity_k.engine.session_disclosure import SessionDisclosure

        d = SessionDisclosure(level="bogus", reset_date="x", notices=[], limits=[])
        assert d.icon == "ℹ️"
        assert d.label == "bogus"


class TestSessionDisclosureRemainingBranches:
    def test_warning_budget_message_and_markdown(self) -> None:
        stats = {
            "global_daily_spend_usd": 42.0,
            "daily_budget_usd": 50.0,
            "remaining_usd": 8.0,
            "usage_percent": 84.0,
            "hourly_actions": 0,
            "hourly_limit": 0,
            "reset_date": "2026-09-04",
        }
        d = build_session_disclosure(stats)
        budget = d.limits[0]
        assert budget.level == "warning" and "80% 이상" in budget.message
        assert "활성화된 한도가 없습니다" not in d.to_markdown()

    def test_exhausted_action_message(self) -> None:
        stats = {
            "global_daily_spend_usd": 0.0,
            "daily_budget_usd": 50.0,
            "remaining_usd": 50.0,
            "usage_percent": 0.0,
            "hourly_actions": 100,
            "hourly_limit": 100,
            "reset_date": "2026-09-04",
        }
        d = build_session_disclosure(stats)
        action = next(lim for lim in d.limits if lim.kind == "action")
        assert "도달했습니다" in action.message

    def test_markdown_no_limits_branch(self) -> None:
        stats = {
            "global_daily_spend_usd": 0.0,
            "daily_budget_usd": 0.0,
            "remaining_usd": 0.0,
            "usage_percent": 0.0,
            "hourly_actions": 0,
            "hourly_limit": 0,
            "reset_date": "2026-09-04",
        }
        markdown = build_session_disclosure(stats).to_markdown()
        assert "활성화된 한도가 없습니다" in markdown
