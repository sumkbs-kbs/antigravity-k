"""Tests for the SubagentSpawner module."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Protocol, cast
from unittest import mock

import pytest

from antigravity_k.engine.subagent_spawner import SubagentSpawner


class _CallInfo(Protocol):
    args: tuple[object, ...]
    kwargs: Mapping[str, object]


class _MockMethod(Protocol):
    return_value: object
    side_effect: object
    call_args: _CallInfo | None

    def __call__(self, *args: object, **kwargs: object) -> object: ...

    def assert_called_once(self) -> None: ...

    def assert_called_once_with(self, *args: object, **kwargs: object) -> None: ...

    def assert_not_called(self) -> None: ...

    def assert_awaited_once_with(self, *args: object, **kwargs: object) -> None: ...


class _OrchestratorDouble(Protocol):
    _get_model_for_role: _MockMethod
    run_stream: _MockMethod


class _ModelManagerDouble(Protocol):
    generate: _MockMethod


def _orchestrator(value: object) -> _OrchestratorDouble:
    return cast(_OrchestratorDouble, value)


def _configure_orchestrator(value: object, chunks: list[str]) -> _OrchestratorDouble:
    orchestrator = _orchestrator(value)
    get_model = cast(_MockMethod, getattr(orchestrator, "_get_model_for_role"))
    get_model.return_value = "mock-model"
    orchestrator.run_stream.return_value = iter(chunks)
    return orchestrator


def _spawn_parallel(spawner: SubagentSpawner, tasks: Sequence[Mapping[str, object]]) -> Awaitable[list[str]]:
    method = cast(Callable[[Sequence[Mapping[str, object]]], Awaitable[list[str]]], getattr(spawner, "spawn_parallel"))
    return method(tasks)


def _spawn(spawner: SubagentSpawner, task: str, tools: list[str]) -> str:
    method = cast(Callable[[str, list[str]], str], getattr(spawner, "spawn"))
    return method(task, tools)


@pytest.fixture
def mock_model_manager() -> object:
    """ModelManager 목 객체."""
    mm = cast(_ModelManagerDouble, mock.MagicMock())
    mm.generate.return_value = "mock response"
    return mm


@pytest.fixture
def mock_tool_registry() -> object:
    """ToolRegistry 목 객체."""
    return mock.MagicMock()


@pytest.fixture
def spawner(mock_model_manager: object, mock_tool_registry: object) -> SubagentSpawner:
    """SubagentSpawner 인스턴스 (mocked dependencies)."""
    return SubagentSpawner(
        model_manager=mock_model_manager,
        tool_registry=mock_tool_registry,
    )


class TestSubagentSpawner:
    """Tests for SubagentSpawner class."""

    def test_init(self, spawner: SubagentSpawner, mock_model_manager: object, mock_tool_registry: object) -> None:
        """초기화 시 model_manager와 tool_registry가 설정되어야 함."""
        assert getattr(spawner, "model_manager") is mock_model_manager
        assert getattr(spawner, "tool_registry") is mock_tool_registry
        assert getattr(spawner, "vault_engine") is not None

    @pytest.mark.asyncio
    async def test_spawn_parallel_empty(self, spawner: SubagentSpawner) -> None:
        """빈 tasks 리스트로 spawn_parallel 시 빈 리스트를 반환해야 함."""
        results = await _spawn_parallel(spawner, [])
        assert results == []

    @pytest.mark.asyncio
    async def test_spawn_parallel_single_task(self, spawner: SubagentSpawner) -> None:
        """단일 태스크를 spawn_parallel로 실행할 수 있어야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:
            factory = cast(_MockMethod, MockOrch)
            mock_orch_instance = _configure_orchestrator(factory.return_value, ["result from agent"])

            results = await _spawn_parallel(spawner, [
                [{"task": "test task", "tools": ["read_file"]}],
            ][0])

            assert len(results) == 1
            assert "Sub-Agent #0 Result" in results[0]
            assert "result from agent" in results[0]
            mock_orch_instance.run_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_parallel_multiple_tasks(self, spawner: SubagentSpawner) -> None:
        """여러 태스크를 병렬로 실행해야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:

            def make_orch() -> _OrchestratorDouble:
                return _configure_orchestrator(mock.MagicMock(), ["result"])

            factory = cast(_MockMethod, MockOrch)
            factory.side_effect = [make_orch(), make_orch()]

            results = await _spawn_parallel(spawner, [
                [
                    {"task": "task A"},
                    {"task": "task B"},
                ],
            ][0])

            assert len(results) == 2
            assert "Sub-Agent #0" in results[0]
            assert "Sub-Agent #1" in results[1]

    @pytest.mark.asyncio
    async def test_spawn_parallel_task_failure(self, spawner: SubagentSpawner) -> None:
        """개별 태스크 실패 시 전체가 아닌 해당 결과만 오류 메시지를 반환해야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:
            # 첫 번째는 성공, 두 번째는 실패
            good_orch = _configure_orchestrator(mock.MagicMock(), ["success"])

            factory = cast(_MockMethod, MockOrch)
            factory.side_effect = [good_orch, RuntimeError("Task crashed")]

            results = await _spawn_parallel(spawner, [
                [
                    {"task": "good task"},
                    {"task": "bad task"},
                ],
            ][0])

            assert len(results) == 2
            assert "success" in results[0]
            assert "Sub-Agent #1 Error" in results[1]
            assert "Task crashed" in results[1]

    @pytest.mark.asyncio
    async def test_spawn_parallel_default_tools(self, spawner: SubagentSpawner) -> None:
        """tools가 제공되지 않으면 기본 도구 목록이 사용되어야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:
            factory = cast(_MockMethod, MockOrch)
            _ = _configure_orchestrator(factory.return_value, ["ok"])

            _ = await _spawn_parallel(spawner, [
                [{"task": "no tools specified"}],
            ][0])

            # OrchestratorAgent가 생성되었는지 확인
            factory.assert_called_once()

    def test_spawn_sync(self, spawner: SubagentSpawner) -> None:
        """동기 spawn() 메서드가 단일 결과를 반환해야 함."""
        with mock.patch.object(
            spawner,
            "spawn_parallel",
            new_callable=mock.AsyncMock,
            return_value=["sync result"],
        ) as spawn_parallel_raw:
            spawn_parallel = cast(_MockMethod, spawn_parallel_raw)
            result = _spawn(spawner, "test task", ["read_file"])
            assert result == "sync result"
            spawn_parallel.assert_awaited_once_with(
                [{"task": "test task", "tools": ["read_file"]}],
                4096,
            )

    def test_spawn_sync_empty_tools(self, spawner: SubagentSpawner) -> None:
        """spawn()에 빈 tools 리스트를 전달할 수 있어야 함."""
        with mock.patch.object(
            spawner,
            "spawn_parallel",
            new_callable=mock.AsyncMock,
            return_value=["result"],
        ) as spawn_parallel_raw:
            spawn_parallel = cast(_MockMethod, spawn_parallel_raw)
            result = _spawn(spawner, "task", [])
            assert result == "result"
            expected_tasks: list[dict[str, object]] = [{"task": "task", "tools": []}]
            spawn_parallel.assert_awaited_once_with(expected_tasks, 4096)

    def test_spawn_sync_uses_a_fresh_asyncio_run_boundary(self, spawner: SubagentSpawner) -> None:
        def close_and_return(awaitable: object) -> list[str]:
            close = cast(Callable[[], None], getattr(awaitable, "close"))
            close()
            return ["loop result"]

        with (
            mock.patch.object(
                spawner,
                "spawn_parallel",
                new_callable=mock.AsyncMock,
                return_value=["loop result"],
            ),
            mock.patch(
                "antigravity_k.engine.subagent_spawner.asyncio.run",
                side_effect=close_and_return,
            ) as run_raw,
        ):
            run = cast(_MockMethod, run_raw)
            result = _spawn(spawner, "task", ["tool"])

        assert result == "loop result"
        run.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_sync_rejects_a_running_event_loop_before_creating_work(self, spawner: SubagentSpawner) -> None:
        current_loop = asyncio.get_running_loop()
        with mock.patch.object(spawner, "spawn_parallel", return_value=current_loop.create_future()) as spawn_parallel_raw:
            spawn_parallel = cast(_MockMethod, spawn_parallel_raw)
            with pytest.raises(RuntimeError, match="await spawn_parallel"):
                _ = _spawn(spawner, "task", ["tool"])

        spawn_parallel.assert_not_called()
