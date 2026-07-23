"""Tests for the SubagentSpawner module."""

from unittest import mock

import pytest

from antigravity_k.engine.subagent_spawner import SubagentSpawner


@pytest.fixture
def mock_model_manager():
    """ModelManager 목 객체."""
    mm = mock.MagicMock()
    mm.generate.return_value = "mock response"
    return mm


@pytest.fixture
def mock_tool_registry():
    """ToolRegistry 목 객체."""
    return mock.MagicMock()


@pytest.fixture
def spawner(mock_model_manager, mock_tool_registry):
    """SubagentSpawner 인스턴스 (mocked dependencies)."""
    return SubagentSpawner(
        model_manager=mock_model_manager,
        tool_registry=mock_tool_registry,
    )


class TestSubagentSpawner:
    """Tests for SubagentSpawner class."""

    def test_init(self, spawner, mock_model_manager, mock_tool_registry):
        """초기화 시 model_manager와 tool_registry가 설정되어야 함."""
        assert spawner.model_manager is mock_model_manager
        assert spawner.tool_registry is mock_tool_registry
        assert spawner.vault_engine is not None

    @pytest.mark.asyncio
    async def test_spawn_parallel_empty(self, spawner):
        """빈 tasks 리스트로 spawn_parallel 시 빈 리스트를 반환해야 함."""
        results = await spawner.spawn_parallel([])
        assert results == []

    @pytest.mark.asyncio
    async def test_spawn_parallel_single_task(self, spawner):
        """단일 태스크를 spawn_parallel로 실행할 수 있어야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:
            mock_orch_instance = MockOrch.return_value
            mock_orch_instance._get_model_for_role.return_value = "mock-model"
            mock_orch_instance.run_stream.return_value = iter(["result from agent"])

            results = await spawner.spawn_parallel(
                [{"task": "test task", "tools": ["read_file"]}],
            )

            assert len(results) == 1
            assert "Sub-Agent #0 Result" in results[0]
            assert "result from agent" in results[0]
            mock_orch_instance.run_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_parallel_multiple_tasks(self, spawner):
        """여러 태스크를 병렬로 실행해야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:

            def make_orch():
                inst = mock.MagicMock()
                inst._get_model_for_role.return_value = "mock-model"
                inst.run_stream.return_value = iter(["result"])
                return inst

            MockOrch.side_effect = [make_orch(), make_orch()]

            results = await spawner.spawn_parallel(
                [
                    {"task": "task A"},
                    {"task": "task B"},
                ],
            )

            assert len(results) == 2
            assert "Sub-Agent #0" in results[0]
            assert "Sub-Agent #1" in results[1]

    @pytest.mark.asyncio
    async def test_spawn_parallel_task_failure(self, spawner):
        """개별 태스크 실패 시 전체가 아닌 해당 결과만 오류 메시지를 반환해야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:
            # 첫 번째는 성공, 두 번째는 실패
            good_orch = mock.MagicMock()
            good_orch._get_model_for_role.return_value = "mock-model"
            good_orch.run_stream.return_value = iter(["success"])
            good_orch.side_effect = None

            MockOrch.side_effect = [good_orch, RuntimeError("Task crashed")]

            results = await spawner.spawn_parallel(
                [
                    {"task": "good task"},
                    {"task": "bad task"},
                ],
            )

            assert len(results) == 2
            assert "success" in results[0]
            assert "Sub-Agent #1 Error" in results[1]
            assert "Task crashed" in results[1]

    @pytest.mark.asyncio
    async def test_spawn_parallel_default_tools(self, spawner):
        """tools가 제공되지 않으면 기본 도구 목록이 사용되어야 함."""
        with mock.patch(
            "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
            autospec=True,
        ) as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch._get_model_for_role.return_value = "mock-model"
            mock_orch.run_stream.return_value = iter(["ok"])

            await spawner.spawn_parallel(
                [{"task": "no tools specified"}],
            )

            # OrchestratorAgent가 생성되었는지 확인
            MockOrch.assert_called_once()

    def test_spawn_sync(self, spawner):
        """동기 spawn() 메서드가 단일 결과를 반환해야 함."""
        with mock.patch.object(spawner, "spawn_parallel", return_value=["sync result"]):
            result = spawner.spawn("test task", ["read_file"])
            assert result == "sync result"

    def test_spawn_sync_empty_tools(self, spawner):
        """spawn()에 빈 tools 리스트를 전달할 수 있어야 함."""
        with mock.patch.object(spawner, "spawn_parallel", return_value=["result"]):
            result = spawner.spawn("task", [])
            assert result == "result"

    def test_spawn_sync_with_new_event_loop(self, spawner):
        """spawn()이 새 이벤트 루프를 생성할 수 있어야 함."""
        with (
            mock.patch(
                "antigravity_k.engine.subagent_spawner.asyncio.get_event_loop", side_effect=RuntimeError("no loop")
            ),
            mock.patch("antigravity_k.engine.subagent_spawner.asyncio.new_event_loop") as mock_new_loop,
            mock.patch("antigravity_k.engine.subagent_spawner.asyncio.set_event_loop"),
        ):
            mock_loop = mock.MagicMock()
            mock_new_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = ["loop result"]

            result = spawner.spawn("task", ["tool"])
            assert result == "loop result"
