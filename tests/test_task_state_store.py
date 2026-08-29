import json
import sqlite3
from collections.abc import Callable, Generator
from contextvars import ContextVar
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import cast

import pytest

from antigravity_k.engine.task_events import RunEventMetadata
from antigravity_k.engine.task_runner import BackgroundTask, BackgroundTaskRunner, TaskStatus
from antigravity_k.engine.task_state_store import TaskExecutionContext, TaskStateStore
from antigravity_k.engine.task_state_types import InvalidTaskTransitionError


def _submit_task(runner: BackgroundTaskRunner, prompt: str, **kwargs: object) -> str:
    method = cast(Callable[..., str], getattr(runner, "submit_task"))
    return method(prompt, **kwargs)


def _run_task(runner: BackgroundTaskRunner, task: BackgroundTask, orchestrator: object, target_model: str) -> None:
    method = cast(Callable[..., None], getattr(runner, "_run_task"))
    method(task, orchestrator, target_model)


def _runner_tasks(runner: BackgroundTaskRunner) -> dict[str, BackgroundTask]:
    return cast(dict[str, BackgroundTask], getattr(runner, "_tasks"))


def _graph_execute(graph: object, ctx: object, orchestrator: object) -> list[str]:
    method = cast(Callable[..., Generator[str, None, None]], getattr(graph, "execute"))
    return list(method(ctx, orchestrator=orchestrator))


def test_state_store_persists_terminal_state_and_rejects_reopen(tmp_path: Path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")

    assert store.transition("task-1", "running") is True
    assert store.transition("task-1", "done", output="result") is True

    record = store.get_task("task-1")
    assert record is not None
    assert record["status"] == "done"
    assert record["output"] == "result"
    assert record["completed_at"] is not None

    with pytest.raises(InvalidTaskTransitionError):
        _ = store.transition("task-1", "running")


def test_state_store_prepares_failed_task_for_explicit_resume(tmp_path: Path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")
    _ = store.transition("task-1", "running")
    _ = store.transition("task-1", "failed", error="temporary outage")

    assert store.prepare_resume("task-1") is True
    resumed = store.get_task("task-1")
    assert resumed is not None
    assert resumed["status"] == "resuming"
    assert store.transition("task-1", "running") is True


def test_state_store_refuses_resume_while_current_process_still_owns_task(tmp_path: Path):
    # Given: the current live process owns a running task.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("task-live", "prompt", "pending", "2026-01-01T00:00:00")
    assert store.transition("task-live", "running") is True

    # When: another resume attempt targets that still-owned task.
    resumed = store.prepare_resume("task-live")

    # Then: the store refuses concurrent execution and preserves running state.
    assert resumed is False
    record = store.get_task("task-live")
    assert record is not None
    assert record["status"] == "running"


def test_state_store_preserves_execution_event_order_without_changing_checkpoints(tmp_path: Path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")

    _ = store.append_execution_event("task-1", "state_transition", '{"to_state":"max_execute"}')
    _ = store.append_execution_event("task-1", "state_checkpoint", '{"state":"max_execute"}')

    events = store.list_execution_events("task-1")
    assert [event["event_type"] for event in events] == ["state_transition", "state_checkpoint"]
    assert [event["sequence"] for event in events] == [1, 2]
    assert store.get_last_checkpoint("task-1") is None


def test_state_store_migrates_and_replays_versioned_execution_events(tmp_path: Path):
    db_path = tmp_path / "legacy-events.db"
    with sqlite3.connect(db_path) as connection:
        _ = connection.execute(
            "CREATE TABLE task_execution_events ("
            + "sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, "
            + "event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)",
        )
        _ = connection.execute(
            "INSERT INTO task_execution_events (task_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
            ("task-1", "legacy_event", '{"legacy":true}', "2026-01-01T00:00:00"),
        )

    store = TaskStateStore(str(db_path))
    _ = store.append_execution_event(
        "task-1",
        "tool.completed",
        '{"ok":true}',
        metadata=RunEventMetadata(
            step_id="step-2",
            agent_id="agent-child",
            parent_id="agent-root",
            tool_call_id="tool-7",
            approval_id="approval-3",
            resource_job_id="gpu-job-1",
            correlation_id="request-9",
        ),
    )

    events = store.list_execution_events("task-1")
    assert events[0]["schema_version"] == 1
    assert events[0]["step_id"] is None
    assert events[1]["schema_version"] == 2
    assert events[1]["step_id"] == "step-2"
    assert events[1]["agent_id"] == "agent-child"
    assert events[1]["parent_id"] == "agent-root"
    assert events[1]["tool_call_id"] == "tool-7"
    assert events[1]["approval_id"] == "approval-3"
    assert events[1]["resource_job_id"] == "gpu-job-1"
    assert events[1]["correlation_id"] == "request-9"
    assert store.list_execution_events("task-1", after_sequence=1, limit=1) == [events[1]]


def test_state_graph_records_bound_max_execution_events(tmp_path: Path):
    from antigravity_k.engine.state_graph import AgentState, AgentStateGraph, StateContext

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("task-1", "prompt", "pending", "2026-01-01T00:00:00")
    graph = AgentStateGraph()

    def max_handler(_ctx: object, _orchestrator: object) -> Generator[str, None, None]:
        yield "MAX output"

    _ = graph.set_entry(AgentState.MAX_EXECUTE)
    _ = graph.add_node(AgentState.MAX_EXECUTE, max_handler)
    _ = graph.add_edge(AgentState.MAX_EXECUTE, AgentState.COMPLETE)
    ctx = StateContext()
    orchestrator = SimpleNamespace(
        task_execution_context=TaskExecutionContext(task_id="task-1", state_store=store),
    )

    assert _graph_execute(graph, ctx, orchestrator) == ["MAX output"]

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


def test_orchestrator_task_execution_binding_is_scoped_to_the_current_run(tmp_path: Path):
    from antigravity_k.engine.orchestrator.agent import OrchestratorAgent

    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    setattr(agent, "_task_execution_context", ContextVar("test_task_execution_context", default=None))
    store = TaskStateStore(str(tmp_path / "tasks.db"))

    assert agent.task_execution_context is None
    with agent.bind_task_execution("task-1", store):
        context = agent.task_execution_context
        assert context is not None
        assert context.task_id == "task-1"
        assert context.state_store is store
    assert agent.task_execution_context is None


def test_state_store_returns_existing_task_for_idempotency_key(tmp_path: Path):
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


def test_state_store_scopes_task_reads_events_and_idempotency_to_owner(tmp_path: Path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    first = store.create_task(
        "task-owner",
        "prompt",
        "pending",
        "2026-01-01T00:00:00",
        idempotency_key="request-1",
        owner_subject="alice",
    )
    second = store.create_task(
        "task-other",
        "prompt",
        "pending",
        "2026-01-01T00:00:01",
        idempotency_key="request-1",
        owner_subject="bob",
    )

    assert first == "task-owner"
    assert second == "task-other"
    assert store.get_task("task-owner", owner_subject="bob") is None
    assert [task["task_id"] for task in store.list_tasks(20, owner_subject="alice")] == ["task-owner"]
    _ = store.append_execution_event("task-owner", "task.completed", '{"ok":true}')
    assert store.list_execution_events("task-owner", owner_subject="bob") == []
    assert len(store.list_execution_events("task-owner", owner_subject="alice")) == 1


def test_state_store_migrates_legacy_task_history(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        _ = connection.execute(
            "CREATE TABLE task_history ("
            + "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL UNIQUE, prompt TEXT NOT NULL, "
            + "status TEXT NOT NULL, output TEXT, error TEXT, created_at TEXT NOT NULL, completed_at TEXT)",
        )
        _ = connection.execute(
            "INSERT INTO task_history (task_id, prompt, status, created_at) VALUES (?, ?, ?, ?)",
            ("legacy-task", "prompt", "paused", "2026-01-01T00:00:00"),
        )

    store = TaskStateStore(str(db_path))
    assert store.transition("legacy-task", "running") is True
    record = store.get_task("legacy-task")
    assert record is not None
    assert record["updated_at"]


def test_state_store_migrates_legacy_idempotency_keys_to_owner_scope(tmp_path: Path):
    db_path = tmp_path / "legacy-idempotency.db"
    with sqlite3.connect(db_path) as connection:
        _ = connection.execute(
            "CREATE TABLE task_idempotency ("
            + "idempotency_key TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)",
        )
        _ = connection.execute(
            "INSERT INTO task_idempotency (idempotency_key, task_id, created_at) VALUES (?, ?, ?)",
            ("request-1", "legacy-task", "2026-01-01T00:00:00"),
        )

    store = TaskStateStore(str(db_path))
    assert (
        store.create_task(
            "task-alice",
            "prompt",
            "pending",
            "2026-01-01T00:00:01",
            idempotency_key="request-1",
            owner_subject="alice",
        )
        == "task-alice"
    )
    assert (
        store.create_task(
            "task-bob",
            "prompt",
            "pending",
            "2026-01-01T00:00:02",
            idempotency_key="request-1",
            owner_subject="bob",
        )
        == "task-bob"
    )


def test_runner_deduplicates_submission_by_idempotency_key(tmp_path: Path):
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    first = _submit_task(runner, "prompt", orchestrator=None, idempotency_key="request-1")
    second = _submit_task(runner, "prompt", orchestrator=None, idempotency_key="request-1")

    thread = cast(Thread | None, getattr(_runner_tasks(runner)[first], "_thread"))
    assert thread is not None
    thread.join(timeout=2)
    assert first == second
    assert list(_runner_tasks(runner)) == [first]


def test_runner_does_not_resurrect_cancelled_task(tmp_path: Path):
    class UnexpectedOrchestrator:
        def run_stream(self, _messages: object, _target_model: str) -> None:
            raise AssertionError("cancelled task must not start execution")

    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = "task-cancelled"
    _ = runner.state_store.create_task(task_id, "prompt", "pending", "2026-01-01T00:00:00")
    task = BackgroundTask(task_id, "prompt")
    task.cancel_event.set()
    _runner_tasks(runner)[task_id] = task

    _run_task(runner, task, UnexpectedOrchestrator(), "model")

    assert task.status == TaskStatus.CANCELLED
    record = runner.state_store.get_task(task_id)
    assert record is not None
    assert record["status"] == TaskStatus.CANCELLED
