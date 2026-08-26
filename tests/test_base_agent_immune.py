"""테스트: BaseAgent — 페르소나 프롬프트·메시지 히스토리·도구 루프.
============================================
시스템 프롬프트 빌드(i18n), 메시지 관리, mock 실행,
tool_call 파싱 루프를 검증한다.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from antigravity_k.agents.base_agent import BaseAgent


@pytest.fixture
def agent():
    return BaseAgent(
        name="TESTER",
        role="coding",
        system_prompt="당신은 코딩 전문가입니다.",
        model_id="test-model",
    )


class TestSystemPrompt:
    def test_system_prompt_includes_reasoning_instruction(self, agent):
        prompt = agent._build_system_prompt()

        assert "당신은 코딩 전문가입니다" in prompt
        assert "thought" in prompt.lower() or "<thought>" in prompt


class TestMessageHistory:
    def test_add_message_appends(self, agent):
        agent.add_message("user", "안녕")
        agent.add_message("assistant", "반갑습니다")

        assert len(agent.history) == 2
        assert agent.history[0]["role"] == "user"

    def test_get_messages_prepends_system(self, agent):
        agent.add_message("user", "질문")

        messages = agent.get_messages()

        assert messages[0]["role"] == "system"
        assert messages[-1] == {"role": "user", "content": "질문"}
        # system + history
        assert len(messages) == 2


class TestMockRun:
    def test_mock_run_without_manager(self, agent):
        result = agent.run("테스트 컨텍스트", model_manager=None)

        assert "더미 응답" in result
        # user + assistant 메시지 추가 확인
        assert len(agent.history) == 2


class TestRunWithModelManager:
    def test_generate_called_with_messages_and_model_id(self, agent):
        manager = MagicMock()
        manager.generate.return_value = "생성된 응답"

        result = agent.run("컨텍스트", model_manager=manager)

        assert result == "생성된 응답"
        manager.generate.assert_called_once()
        call_kwargs = manager.generate.call_args.kwargs
        assert call_kwargs["target"] == "test-model"

    def test_tool_call_parsed_and_executed(self, agent):
        manager = MagicMock()
        tool_response = '<tool_call>{"name": "search", "arguments": {"q": "test"}}</tool_call>결과: 찾음'
        manager.generate.side_effect = [tool_response]

        fake_tool = MagicMock(return_value="검색 결과 데이터")
        fake_tool.name = "search"

        agent.run("검색해줘", model_manager=manager, tools=[fake_tool])

        # 도구 결과가 히스토리에 tool 메시지로 추가됨
        tool_msgs = [m for m in agent.history if m["role"] == "tool"]
        assert any("검색 결과 데이터" in m["content"] for m in tool_msgs)

    def test_max_iterations_reached_returns_error(self, agent):
        manager = MagicMock()
        # 항상 tool_call을 반환하면 무한 루프 → max_iterations 도달
        manager.generate.return_value = '<tool_call>{"name": "loop", "arguments": {}}</tool_call>'

        fake_tool = MagicMock(return_value="계속")
        fake_tool.name = "loop"

        result = agent.run("무한", model_manager=manager, tools=[fake_tool])

        assert "Maximum iterations" in result

    def test_generation_error_returns_error_message(self, agent):
        manager = MagicMock()
        manager.generate.side_effect = RuntimeError("모델 오류")

        result = agent.run("컨텍스트", model_manager=manager)

        assert result.startswith("Error:")

    def test_dummy_model_triggers_mock_run(self, agent):
        dummy_model = MagicMock()
        dummy_model.__repr__ = lambda self: "Dummy(model)"
        loaded = SimpleNamespace(model=dummy_model, tokenizer=None)
        manager = MagicMock()
        manager.get.return_value = loaded
        manager.router = None

        result = agent.run("x", model_manager=manager)

        assert "더미 응답" in result


# ─── ImmuneSystem ────────────────────────────────────────────────


class FakeImmune:
    """ImmuneSystem의 안전장치 로직만 격리 검증."""

    _session_heal_count = 0
    _MAX_HEAL_ATTEMPTS_PER_SESSION = 3


class TestImmuneSystemSafetyLimits:
    def test_heal_count_limit_enforced(self, monkeypatch):
        import antigravity_k.engine.immune_system as immune_mod

        monkeypatch.setattr(immune_mod.ImmuneSystem, "_session_heal_count", 3)

        system = immune_mod.ImmuneSystem(
            project_root="/tmp",
            model_manager=MagicMock(),
            vault_engine=None,
        )
        result = system.heal("trace", "tool", "{}")

        assert "수동 개입" in result

    def test_session_counter_resets(self, monkeypatch):
        import antigravity_k.engine.immune_system as immune_mod

        immune_mod.ImmuneSystem._session_heal_count = 99
        immune_mod.ImmuneSystem.reset_session_counter()
        assert immune_mod.ImmuneSystem._session_heal_count == 0
