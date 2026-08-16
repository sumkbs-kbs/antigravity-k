import json
import sqlite3
from contextvars import ContextVar
from types import SimpleNamespace

import pytest

from antigravity_k.engine.task_runner import BackgroundTask, BackgroundTaskRunner, TaskStatus
from antigravity_k.engine.task_state_store import (
    InvalidTaskTransitionError,
    TaskExecutionContext,
    TaskStateStore,
)


def test_state_store_persists_terminal_state_and_rejects_reopen(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")

    assert store.transition("task-1", "running") is True
    assert store.transition("task-1", "done", output="result") is True

    record = store.get_task("task-1")
    assert record is not None
    assert record["status"] == "done"
    assert record["output"] == "result"
    assert record["completed_at"] is not None

    with pytest.raises(InvalidTaskTransitionError):
        store.transition("task-1", "running")


def test_state_store_prepares_failed_task_for_explicit_resume(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")
    store.transition("task-1", "running")
    store.transition("task-1", "failed", error="temporary outage")

    assert store.prepare_resume("task-1") is True
    resumed = store.get_task("task-1")
    assert resumed is not None
    assert resumed["status"] == "resuming"
    assert store.transition("task-1", "running") is True


def test_state_store_preserves_execution_event_order_without_changing_checkpoints(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")

    store.append_execution_event("task-1", "state_transition", '{"to_state":"max_execute"}')
    store.append_execution_event("task-1", "state_checkpoint", '{"state":"max_execute"}')

    events = store.list_execution_events("task-1")
    assert [event["event_type"] for event in events] == ["state_transition", "state_checkpoint"]
    assert [event["sequence"] for event in events] == [1, 2]
    assert store.get_last_checkpoint("task-1") is None


def test_state_graph_records_bound_max_execution_events(tmp_path):
    from antigravity_k.engine.state_graph import AgentState, AgentStateGraph, StateContext

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")
    graph = AgentStateGraph()

    def max_handler(_ctx, _orchestrator):
        yield "MAX output"

    graph.set_entry(AgentState.MAX_EXECUTE)
    graph.add_node(AgentState.MAX_EXECUTE, max_handler)
    graph.add_edge(AgentState.MAX_EXECUTE, AgentState.COMPLETE)
    ctx = StateContext()
    orchestrator = SimpleNamespace(
        task_execution_context=TaskExecutionContext(task_id="task-1", state_store=store),
    )

    assert list(graph.execute(ctx, orchestrator=orchestrator)) == ["MAX output"]

    events = store.list_execution_events("task-1")
    payloads = [json.loads(event["payload_json"]) for event in events]
    assert [event["event_type"] for event in events] == [
        "state_transition",
        "state_checkpoint",
        "state_transition",
    ]
    assert payloads[0]["from_state"] == AgentState.INIT.value
    assert payloads[0]["to_state"] == AgentState.MAX_EXECUTE.value
    assert payloads[1]["state"] == AgentState.MAX_EXECUTE.value
    assert payloads[2]["to_state"] == AgentState.COMPLETE.value


def test_orchestrator_task_execution_binding_is_scoped_to_the_current_run(tmp_path):
    from antigravity_k.engine.orchestrator.agent import OrchestratorAgent

    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    agent._task_execution_context = ContextVar("test_task_execution_context", default=None)
    store = TaskStateStore(str(tmp_path / "tasks.db"))

    assert agent.task_execution_context is None
    with agent.bind_task_execution("task-1", store):
        context = agent.task_execution_context
        assert context is not None
        assert context.task_id == "task-1"
        assert context.state_store is store
    assert agent.task_execution_context is None


def test_state_store_returns_existing_task_for_idempotency_key(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    first = store.create_task(
        "task-1",
        "prompt",
        "pending",
        "2026-01-01T00:00:00",
        idempotency_key="request-1",
    )
    second = store.create_task(
        "task-2",
        "prompt",
        "pending",
        "2026-01-01T00:00:01",
        idempotency_key="request-1",
    )

    assert first == "task-1"
    assert second == "task-1"
    assert store.get_task("task-2") is None


def test_state_store_migrates_legacy_task_history(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE task_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL UNIQUE, prompt TEXT NOT NULL, "
            "status TEXT NOT NULL, output TEXT, error TEXT, created_at TEXT NOT NULL, completed_at TEXT)",
        )
        connection.execute(
            "INSERT INTO task_history (task_id, prompt, status, created_at) VALUES (?, ?, ?, ?)",
            ("legacy-task", "prompt", "paused", "2026-01-01T00:00:00"),
        )

    store = TaskStateStore(str(db_path))
    assert store.transition("legacy-task", "running") is True
    record = store.get_task("legacy-task")
    assert record is not None
    assert record["updated_at"]


def test_runner_deduplicates_submission_by_idempotency_key(tmp_path):
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    first = runner.submit_task("prompt", orchestrator=None, idempotency_key="request-1")
    second = runner.submit_task("prompt", orchestrator=None, idempotency_key="request-1")

    thread = runner._tasks[first]._thread
    assert thread is not None
    thread.join(timeout=2)
    assert first == second
    assert list(runner._tasks) == [first]


def test_runner_does_not_resurrect_cancelled_task(tmp_path):
    class UnexpectedOrchestrator:
        def run_stream(self, messages, target_model):
            raise AssertionError("cancelled task must not start execution")

    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = "task-cancelled"
    runner.state_store.create_task(task_id, "prompt", "pending", "2026-01-01T00:00:00")
    task = BackgroundTask(task_id, "prompt")
    task.cancel_event.set()
    runner._tasks[task_id] = task

    runner._run_task(task, UnexpectedOrchestrator(), "model")

    assert task.status == TaskStatus.CANCELLED
    record = runner.state_store.get_task(task_id)
    assert record is not None
    assert record["status"] == TaskStatus.CANCELLED
