"""Tests for the Multiplexer module."""

import tempfile
from unittest import mock

import pytest

from antigravity_k.engine.multiplexer import Multiplexer


@pytest.fixture
def temp_project_root():
    """임시 프로젝트 루트 디렉토리."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestMultiplexer:
    """Tests for Multiplexer class."""

    def test_init(self, temp_project_root):
        """초기화 시 project_root와 worktree_manager가 설정되어야 함."""
        mux = Multiplexer(project_root=temp_project_root)
        assert mux.project_root == temp_project_root
        assert mux.worktree_manager is not None
        assert mux.active_runners == []

    def test_init_with_base_repo_path(self, temp_project_root):
        """base_repo_path가 worktree_manager에 전달되어야 함."""
        mux = Multiplexer(project_root=temp_project_root)
        assert mux.worktree_manager.base_repo_path == temp_project_root

    @pytest.mark.asyncio
    async def test_run_parallel_goals_empty(self, temp_project_root):
        """빈 goals 리스트로 실행 시 빈 리스트를 반환해야 함."""
        mux = Multiplexer(project_root=temp_project_root)
        results = await mux.run_parallel_goals([])
        assert results == []

    @pytest.mark.asyncio
    async def test_run_parallel_goals_single(self, temp_project_root):
        """단일 goal 실행 시 worktree 생성 + GoalRunner 실행이 이루어져야 함."""
        mux = Multiplexer(project_root=temp_project_root)

        with mock.patch.object(mux.worktree_manager, "create_worktree", return_value="/tmp/worktree/test-1"):
            with mock.patch(
                "antigravity_k.engine.multiplexer.GoalRunner",
                autospec=True,
            ) as MockRunner:
                mock_runner_instance = MockRunner.return_value
                mock_runner_instance.task_id = "test-task-1"
                mock_runner_instance.instruction = "do something"

                results = await mux.run_parallel_goals(
                    [{"task_id": "test-task-1", "instruction": "do something"}],
                )

                # create_worktree가 올바르게 호출되었는가
                mux.worktree_manager.create_worktree.assert_called_once_with(
                    branch_name="test-task-1",
                    base_branch="main",
                )

                # GoalRunner가 instruction으로 생성되었는가
                MockRunner.assert_called_once_with(instruction="do something")

                # _run_single_agent가 호출되어야 함
                assert len(mux.active_runners) == 1
                assert mux.active_runners[0] is mock_runner_instance
                assert results[0]["task_id"] == "test-task-1"
                assert results[0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_run_parallel_goals_multiple(self, temp_project_root):
        """여러 goal을 병렬로 실행해야 함."""
        mux = Multiplexer(project_root=temp_project_root)

        with mock.patch.object(
            mux.worktree_manager,
            "create_worktree",
            side_effect=["/tmp/wt/task-a", "/tmp/wt/task-b"],
        ):
            with mock.patch(
                "antigravity_k.engine.multiplexer.GoalRunner",
                autospec=True,
            ) as MockRunner:
                mock_a = mock.MagicMock()
                mock_a.task_id = "task-a"
                mock_a.instruction = "instruction a"
                mock_b = mock.MagicMock()
                mock_b.task_id = "task-b"
                mock_b.instruction = "instruction b"
                MockRunner.side_effect = [mock_a, mock_b]

                results = await mux.run_parallel_goals(
                    [
                        {"task_id": "task-a", "instruction": "instruction a"},
                        {"task_id": "task-b", "instruction": "instruction b"},
                    ],
                )

                assert len(results) == 2
                assert results[0]["task_id"] == "task-a"
                assert results[1]["task_id"] == "task-b"
                assert all(r["status"] == "success" for r in results)

    @pytest.mark.asyncio
    async def test_run_parallel_goals_with_auto_task_id(self, temp_project_root):
        """task_id가 없으면 자동 생성되어야 함."""
        mux = Multiplexer(project_root=temp_project_root)

        with mock.patch.object(mux.worktree_manager, "create_worktree", return_value="/tmp/wt/auto"):
            with mock.patch(
                "antigravity_k.engine.multiplexer.GoalRunner",
                autospec=True,
            ) as MockRunner:
                mock_runner = mock.MagicMock()
                mock_runner.task_id = "auto-task"
                mock_runner.instruction = "do it"
                MockRunner.return_value = mock_runner

                results = await mux.run_parallel_goals(
                    [{"instruction": "do it"}],
                )

                # task_id가 제공되지 않으면 자동 생성
                assert results[0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_single_agent_failure(self, temp_project_root):
        """개별 에이전트 실패 시 전체가 아니라 해당 결과만 실패로 표시되어야 함."""
        mux = Multiplexer(project_root=temp_project_root)

        with mock.patch.object(
            mux.worktree_manager,
            "create_worktree",
            side_effect=["/tmp/wt/good", "/tmp/wt/bad"],
        ):
            with mock.patch(
                "antigravity_k.engine.multiplexer.GoalRunner",
                autospec=True,
            ) as MockRunner:
                mock_good = mock.MagicMock()
                mock_good.task_id = "good-task"
                mock_good.instruction = "good"

                mock_bad = mock.MagicMock()
                mock_bad.task_id = "bad-task"
                mock_bad.instruction = "bad"
                mock_bad.run.side_effect = RuntimeError("Agent exploded")
                MockRunner.side_effect = [mock_good, mock_bad]

                results = await mux.run_parallel_goals(
                    [
                        {"task_id": "good-task", "instruction": "good"},
                        {"task_id": "bad-task", "instruction": "bad"},
                    ],
                )

                good_result = next(r for r in results if r["task_id"] == "good-task")
                bad_result = next(r for r in results if r["task_id"] == "bad-task")
                assert good_result["status"] == "success"
                assert bad_result["status"] == "failed"
                assert "Agent exploded" in bad_result["error"]

    @pytest.mark.asyncio
    async def test_workspace_dir_set_on_runner(self, temp_project_root):
        """각 GoalRunner의 workspace_dir이 worktree 경로로 설정되어야 함."""
        mux = Multiplexer(project_root=temp_project_root)

        with mock.patch.object(mux.worktree_manager, "create_worktree", return_value="/tmp/wt/ws"):
            with mock.patch(
                "antigravity_k.engine.multiplexer.GoalRunner",
                autospec=True,
            ) as MockRunner:
                mock_runner = MockRunner.return_value
                mock_runner.task_id = "ws-test"

                await mux.run_parallel_goals(
                    [{"task_id": "ws-test", "instruction": "test"}],
                )

                assert mock_runner.workspace_dir == "/tmp/wt/ws"

    @pytest.mark.asyncio
    async def test_run_single_agent_calls_runner_run(self, temp_project_root):
        """_run_single_agent가 runner.run을 호출해야 함."""
        mux = Multiplexer(project_root=temp_project_root)
        mock_runner = mock.MagicMock()
        mock_runner.task_id = "test"
        mock_runner.instruction = "instruction"

        result = await mux._run_single_agent(mock_runner, "/tmp/worktree")

        mock_runner.run.assert_called_once_with("instruction")
        assert result["task_id"] == "test"
        assert result["status"] == "success"
