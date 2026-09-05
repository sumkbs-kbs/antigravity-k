"""테스트: BaseAgent — 페르소나 프롬프트·메시지 히스토리·도구 루프.
============================================
시스템 프롬프트 빌드(i18n), 메시지 관리, mock 실행,
tool_call 파싱 루프를 검증한다.
"""

from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import Protocol, cast, final, override
from unittest.mock import MagicMock

import pytest

from antigravity_k.agents.base_agent import BaseAgent


class _CallInfo(Protocol):
    kwargs: Mapping[str, object]


class _MockMethod(Protocol):
    return_value: object
    side_effect: object
    call_args: _CallInfo | None

    def assert_called_once(self) -> None: ...


class _ManagerDouble(Protocol):
    generate: _MockMethod
    get: _MockMethod
    router: object


class _ToolDouble(Protocol):
    name: str

    def __call__(self, **kwargs: object) -> str: ...


def _call_kwargs(method: _MockMethod) -> Mapping[str, object]:
    call_args = method.call_args
    assert call_args is not None
    return call_args.kwargs


def _run(agent: BaseAgent, context: str, model_manager: object | None = None, tools: list[_ToolDouble] | None = None) -> str:
    run = cast(object, getattr(agent, "run"))
    runner = cast(Callable[..., str], run)
    return runner(context, model_manager=model_manager, tools=cast(object, tools))


@pytest.fixture
def agent() -> BaseAgent:
    return BaseAgent(
        name="TESTER",
        role="coding",
        system_prompt="당신은 코딩 전문가입니다.",
        model_id="test-model",
    )


class TestSystemPrompt:
    def test_system_prompt_includes_reasoning_instruction(self, agent: BaseAgent) -> None:
        prompt = cast(str, getattr(agent, "_build_system_prompt")())

        assert "당신은 코딩 전문가입니다" in prompt
        assert "thought" in prompt.lower() or "<thought>" in prompt


class TestMessageHistory:
    def test_add_message_appends(self, agent: BaseAgent) -> None:
        agent.add_message("user", "안녕")
        agent.add_message("assistant", "반갑습니다")

        assert len(agent.history) == 2
        assert agent.history[0]["role"] == "user"

    def test_get_messages_prepends_system(self, agent: BaseAgent) -> None:
        agent.add_message("user", "질문")

        messages = agent.get_messages()

        assert messages[0]["role"] == "system"
        assert messages[-1] == {"role": "user", "content": "질문"}
        # system + history
        assert len(messages) == 2


class TestMockRun:
    def test_mock_run_without_manager(self, agent: BaseAgent) -> None:
        result = _run(agent, "테스트 컨텍스트")

        assert "더미 응답" in result
        # user + assistant 메시지 추가 확인
        assert len(agent.history) == 2


class TestRunWithModelManager:
    def test_generate_called_with_messages_and_model_id(self, agent: BaseAgent) -> None:
        manager = cast(_ManagerDouble, MagicMock())
        manager.generate.return_value = "생성된 응답"

        result = _run(agent, "컨텍스트", manager)

        assert result == "생성된 응답"
        manager.generate.assert_called_once()
        call_kwargs = _call_kwargs(manager.generate)
        assert call_kwargs["target"] == "test-model"

    def test_tool_call_parsed_and_executed(self, agent: BaseAgent) -> None:
        manager = cast(_ManagerDouble, MagicMock())
        tool_response = '<tool_call>{"name": "search", "arguments": {"q": "test"}}</tool_call>결과: 찾음'
        manager.generate.side_effect = [tool_response]

        fake_tool = cast(_ToolDouble, MagicMock(return_value="검색 결과 데이터"))
        fake_tool.name = "search"

        _ = _run(agent, "검색해줘", manager, [fake_tool])

        # 도구 결과가 히스토리에 tool 메시지로 추가됨
        tool_msgs = [m for m in agent.history if m["role"] == "tool"]
        assert any("검색 결과 데이터" in m["content"] for m in tool_msgs)

    def test_max_iterations_reached_returns_error(self, agent: BaseAgent) -> None:
        manager = cast(_ManagerDouble, MagicMock())
        # 항상 tool_call을 반환하면 무한 루프 → max_iterations 도달
        manager.generate.return_value = '<tool_call>{"name": "loop", "arguments": {}}</tool_call>'

        fake_tool = cast(_ToolDouble, MagicMock(return_value="계속"))
        fake_tool.name = "loop"

        result = _run(agent, "무한", manager, [fake_tool])

        assert "Maximum iterations" in result

    def test_generation_error_returns_error_message(self, agent: BaseAgent) -> None:
        manager = cast(_ManagerDouble, MagicMock())
        manager.generate.side_effect = RuntimeError("모델 오류")

        result = _run(agent, "컨텍스트", manager)

        assert result.startswith("Error:")

    def test_dummy_model_triggers_mock_run(self, agent: BaseAgent) -> None:
        @final
        class DummyModel:
            name: str = "Dummy"

            @override
            def __repr__(self) -> str:
                return "Dummy(model)"

        dummy_model = DummyModel()
        loaded = SimpleNamespace(model=dummy_model, tokenizer=None)
        manager = cast(_ManagerDouble, MagicMock())
        manager.get.return_value = loaded
        manager.router = None

        result = _run(agent, "x", manager)

        assert "더미 응답" in result


# ─── ImmuneSystem ────────────────────────────────────────────────


@final
class FakeImmune:
    """ImmuneSystem의 안전장치 로직만 격리 검증."""

    _session_heal_count: int = 0
    _MAX_HEAL_ATTEMPTS_PER_SESSION: int = 3


class TestImmuneSystemSafetyLimits:
    def test_heal_count_limit_enforced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import antigravity_k.engine.immune_system as immune_mod

        monkeypatch.setattr(immune_mod.ImmuneSystem, "_session_heal_count", 3)

        system = immune_mod.ImmuneSystem(
            project_root="/tmp",
            model_manager=MagicMock(),
            vault_engine=None,
        )
        result = system.heal("trace", "tool", "{}")

        assert "수동 개입" in result

    def test_session_counter_resets(self) -> None:
        import antigravity_k.engine.immune_system as immune_mod

        setattr(immune_mod.ImmuneSystem, "_session_heal_count", 99)
        immune_mod.ImmuneSystem.reset_session_counter()
        assert getattr(immune_mod.ImmuneSystem, "_session_heal_count") == 0
