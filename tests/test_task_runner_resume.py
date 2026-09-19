import json
import sqlite3
import threading
from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import cast, final

import pytest

from antigravity_k.engine.task_context_snapshot import load_task_context_snapshot
from antigravity_k.engine.task_runner import BackgroundTask, BackgroundTaskRunner
from antigravity_k.engine.task_state_store import TaskStateStore


@final
class _FakeOrchestrator:
    vault_engine: object | None = None

    def run_stream(self, messages: list[dict[str, str]], target_model: str) -> Iterator[str]:
        _ = messages
        _ = target_model
        return iter(["new output"])


def _task(runner: BackgroundTaskRunner, task_id: str) -> BackgroundTask:
    tasks = cast(dict[str, BackgroundTask], getattr(runner, "_tasks"))
    return tasks[task_id]


def _thread(task: BackgroundTask) -> threading.Thread:
    thread = cast(threading.Thread | None, getattr(task, "_thread"))
    assert thread is not None
    return thread


def _connection(runner: BackgroundTaskRunner) -> AbstractContextManager[sqlite3.Connection]:
    opener = cast(Callable[[], AbstractContextManager[sqlite3.Connection]], getattr(runner, "_get_connection"))
    return opener()


def _save_checkpoint(
    runner: BackgroundTaskRunner,
    task_id: str,
    step: int,
    context: dict[str, object],
    output: str,
) -> None:
    saver = cast(Callable[[str, int, dict[str, object], str], None], getattr(runner, "_save_checkpoint"))
    saver(task_id, step, context, output)


def test_background_run_persists_initial_context_snapshot(tmp_path: Path) -> None:
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = runner.submit_task(
        "inspect the large project",
        context={"phase": "discovery", "persist_context_snapshot": True},
        orchestrator=_FakeOrchestrator(),
        target_model="qwen3.8:27b",
    )
    _thread(_task(runner, task_id)).join(timeout=2)

    snapshot = load_task_context_snapshot(runner.state_store, task_id)
    assert snapshot is not None
    assert snapshot.target_model == "qwen3.8:27b"
    assert any(message.content == "inspect the large project" for message in snapshot.messages)


def test_worktree_task_enables_context_snapshot_without_extra_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    def create_worktree(task_id: str) -> str:
        return str(tmp_path / task_id)

    def remove_worktree(_task_id: str) -> None:
        return None

    monkeypatch.setattr(
        runner.worktree_manager,
        "create_worktree",
        create_worktree,
    )
    monkeypatch.setattr(runner.worktree_manager, "remove_worktree", remove_worktree)

    task_id = runner.submit_task(
        "refactor the large project",
        orchestrator=_FakeOrchestrator(),
        target_model="qwen3.8:27b",
        use_worktree=True,
    )
    _thread(_task(runner, task_id)).join(timeout=2)

    snapshot = load_task_context_snapshot(runner.state_store, task_id)
    assert snapshot is not None
    assert _task(runner, task_id).context["use_worktree"] is True


def test_resume_task_preserves_checkpoint_step_and_output(tmp_path: Path) -> None:
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = "task_resume"

    with _connection(runner) as conn:
        _ = conn.execute(
            "INSERT INTO task_history (task_id, prompt, status, created_at) VALUES (?, ?, ?, ?)",
            (task_id, "continue this task", "paused", "2026-01-01T00:00:00"),
        )
        conn.commit()
    _save_checkpoint(
        runner,
        task_id,
        9,
        {"phase": "build", "working_memory": "Next Action: run focused tests"},
        "previous output",
    )

    assert runner.resume_task(task_id, orchestrator=_FakeOrchestrator(), target_model="model") is True
    task = _task(runner, task_id)
    assert "Next Action: run focused tests" in task.prompt
    _thread(task).join(timeout=2)

    assert task.output == "previous outputnew output"
    checkpoint = runner.get_last_checkpoint(task_id)
    assert checkpoint is not None
    assert checkpoint["step"] == 10
    assert checkpoint["output_so_far"] == "previous outputnew output"


def test_wait_task_returns_terminal_state_after_resume_thread_finishes(tmp_path: Path) -> None:
    # Given: a paused task has a resumable checkpoint.
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = "task-wait"
    _ = runner.state_store.create_task(task_id, "continue", "paused", "2026-01-01T00:00:00")
    _ = runner.state_store.save_checkpoint(task_id, 1, "{}", "partial-")
    assert runner.resume_task(task_id, orchestrator=_FakeOrchestrator(), target_model="model") is True

    # When: the public wait boundary joins the active resume execution.
    status = runner.wait_task(task_id, timeout=2)

    # Then: callers observe the terminal state and accumulated output.
    assert status is not None
    assert status["status"] == "done"
    assert runner.get_output(task_id) == "partial-new output"


def test_default_runner_honors_operator_task_database_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: an operator selects an isolated durable task database.
    db_path = tmp_path / "operator" / "tasks.db"
    monkeypatch.setenv("AGK_TASK_DB_PATH", str(db_path))

    # When: the runner uses its default constructor.
    runner = BackgroundTaskRunner()

    # Then: all task state is rooted at the configured path.
    assert Path(runner.db_path) == db_path
    assert db_path.exists()


def test_runner_checkpoint_preserves_tool_loop_state_from_newer_tool_round(tmp_path: Path) -> None:
    # Given: the tool loop has written durable evidence before the stream-level checkpoint.
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = "checkpoint-tool-state"
    _ = runner.state_store.create_task(task_id, "read README", "running", "2026-01-01T00:00:00")
    _ = runner.state_store.save_checkpoint(
        task_id,
        4,
        '{"expected_tools": ["read_file"], "tool_loop": {"used_tools": ["read_file"], '
        + '"tool_evidence_context": "README evidence"}}',
        "tool output",
    )

    # When: the background runner stores its later periodic checkpoint.
    _save_checkpoint(runner, task_id, 10, {"task_plan": {"objective": "read README"}}, "stream output")

    # Then: the resume-critical tool state remains available at the latest checkpoint.
    checkpoint = runner.get_last_checkpoint(task_id)
    assert checkpoint is not None
    assert checkpoint["step"] == 10
    checkpoint_context = checkpoint["context"]
    assert isinstance(checkpoint_context, dict)
    tool_loop = checkpoint_context["tool_loop"]
    assert isinstance(tool_loop, dict)
    assert tool_loop["used_tools"] == ["read_file"]
    assert tool_loop["tool_evidence_context"] == "README evidence"


def test_resume_task_recovers_a_failed_task_from_its_initial_checkpoint(tmp_path: Path) -> None:
    @final
    class RecoveringOrchestrator:
        vault_engine: object | None = None

        def __init__(self) -> None:
            self.calls = 0

        def run_stream(self, messages: list[dict[str, str]], target_model: str) -> Iterator[str]:
            _ = messages
            _ = target_model
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary model outage")
            return iter(["recovered output"])

    orchestrator = RecoveringOrchestrator()
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = runner.submit_task(
        "recover this task",
        context={"task_plan": {"objective": "recover this task"}},
        orchestrator=orchestrator,
        target_model="qwen3.6:latest",
    )
    _thread(_task(runner, task_id)).join(timeout=2)

    failed = runner.state_store.get_task(task_id)
    checkpoint = runner.get_last_checkpoint(task_id)
    assert failed is not None
    assert failed["status"] == "failed"
    assert checkpoint is not None
    assert checkpoint["step"] == 0
    checkpoint_context = checkpoint["context"]
    assert isinstance(checkpoint_context, dict)
    task_plan = checkpoint_context["task_plan"]
    assert isinstance(task_plan, dict)
    assert task_plan["objective"] == "recover this task"

    assert runner.resume_task(task_id, orchestrator=orchestrator, target_model="qwen3.6:latest") is True
    _thread(_task(runner, task_id)).join(timeout=2)

    recovered = runner.state_store.get_task(task_id)
    assert recovered is not None
    assert recovered["status"] == "done"
    assert runner.get_output(task_id) == "recovered output"


def test_background_runner_binds_task_state_for_the_full_stream_lifetime(tmp_path: Path) -> None:
    @final
    class BoundOrchestrator:
        vault_engine: object | None = None

        def __init__(self) -> None:
            self.bindings: list[tuple[str, object]] = []
            self.active_task_id = ""

        @contextmanager
        def bind_task_execution(self, task_id: str, state_store: TaskStateStore) -> Generator[None, None, None]:
            self.bindings.append((task_id, state_store))
            self.active_task_id = task_id
            try:
                yield
            finally:
                self.active_task_id = ""

        def run_stream(self, messages: list[dict[str, str]], target_model: str) -> Iterator[str]:
            _ = messages
            _ = target_model
            assert self.active_task_id
            return iter(["bound output"])

    orchestrator = BoundOrchestrator()
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = runner.submit_task("bind task", orchestrator=orchestrator, target_model="qwen3.6:latest")
    _thread(_task(runner, task_id)).join(timeout=2)

    assert orchestrator.bindings == [(task_id, runner.state_store)]
    assert orchestrator.active_task_id == ""


def test_background_runner_preserves_an_approval_pause_from_the_tool_loop(tmp_path: Path) -> None:
    @final
    class ApprovalOrchestrator:
        vault_engine: object | None = None
        task_id: str = ""
        state_store: TaskStateStore | None = None

        @contextmanager
        def bind_task_execution(self, task_id: str, state_store: TaskStateStore) -> Generator[None, None, None]:
            self.task_id = task_id
            self.state_store = state_store
            yield

        def run_stream(self, messages: list[dict[str, str]], target_model: str) -> Iterator[str]:
            _ = messages
            _ = target_model
            state_store = self.state_store
            assert state_store is not None
            _ = state_store.transition(self.task_id, "paused", output="approval required")
            return iter(["[APPROVAL REQUIRED] confirm write"])

    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = runner.submit_task(
        "write a file",
        orchestrator=ApprovalOrchestrator(),
        target_model="qwen3.6:latest",
    )
    _thread(_task(runner, task_id)).join(timeout=2)

    task = _task(runner, task_id)
    record = runner.state_store.get_task(task_id)
    assert task.status == "paused"
    assert record is not None
    assert record["status"] == "paused"
    assert runner.get_output(task_id) == "[APPROVAL REQUIRED] confirm write"


def test_resume_after_store_reopen_injects_only_its_task_context_snapshot(tmp_path: Path) -> None:
    @final
    class CapturingOrchestrator:
        vault_engine: object | None = None

        def __init__(self) -> None:
            self.messages: list[dict[str, str]] = []

        @contextmanager
        def bind_task_execution(self, _task_id: str, _state_store: TaskStateStore) -> Generator[None, None, None]:
            yield

        def run_stream(self, messages: list[dict[str, str]], target_model: str) -> Iterator[str]:
            _ = target_model
            self.messages = messages
            return iter(["resumed output"])

    # Given: two paused tasks have different durable compressed contexts in one DB.
    db_path = tmp_path / "tasks.db"
    initial = BackgroundTaskRunner(db_path=str(db_path))
    for task_id in ("task-alpha", "task-beta"):
        _ = initial.state_store.create_task(task_id, "continue", "paused", "2026-01-01T00:00:00")
        _ = initial.state_store.save_checkpoint(task_id, 4, "{}", "previous output")
    for task_id, marker in (("task-alpha", "ALPHA_CONTEXT"), ("task-beta", "BETA_CONTEXT")):
        _ = initial.state_store.append_execution_event(
            task_id,
            "context_snapshot",
            json.dumps(
                {
                    "version": 1,
                    "target_model": "qwen3.6:latest",
                    "messages": [{"role": "system", "content": marker}],
                },
            ),
        )

    # When: a new runner instance resumes only task alpha from the same SQLite file.
    resumed = BackgroundTaskRunner(db_path=str(db_path))
    orchestrator = CapturingOrchestrator()
    assert resumed.resume_task("task-alpha", orchestrator=orchestrator, target_model="qwen3.6:latest") is True
    _thread(_task(resumed, "task-alpha")).join(timeout=2)

    # Then: alpha context is model-visible while beta context remains isolated.
    restored = "\n".join(message["content"] for message in orchestrator.messages)
    assert "[Restored Task Context]" in restored
    assert "ALPHA_CONTEXT" in restored
    assert "BETA_CONTEXT" not in restored
