from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from typing import cast

from antigravity_k.engine.direct_task_execution import TaskStoreRunnerPort
from antigravity_k.engine.orchestrator.agent import OrchestratorAgent
from antigravity_k.engine.subagent_execution import start_subagent_stream
from antigravity_k.engine.task_state_store import (
    TaskExecutionContext,
    TaskStateStore,
)


class BoundSubagent:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self._execution_context: ContextVar[TaskExecutionContext | None] = ContextVar(
            "subagent_test_execution_context",
            default=None,
        )
        self.bound_task_ids: list[str] = []

    @property
    def task_execution_context(self) -> TaskExecutionContext | None:
        return self._execution_context.get()

    @contextmanager
    def bind_task_execution(self, task_id: str, state_store: TaskStateStore) -> Iterator[None]:
        self.bound_task_ids.append(task_id)
        token = self._execution_context.set(TaskExecutionContext(task_id, state_store))
        try:
            yield
        finally:
            self._execution_context.reset(token)

    def run_stream(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> Iterator[str]:
        del messages, target_model, max_steps, ephemeral_message
        assert self.task_execution_context is not None
        yield from self._chunks


def test_subagent_stream_reuses_parent_task_and_records_events(tmp_path) -> None:
    # Given: a running parent task and a child orchestrator.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("parent-task", "parent prompt", "pending", "2026-01-01T00:00:00+00:00")
    store.transition("parent-task", "running")
    child = BoundSubagent(["child ", "result"])
    parent = OrchestratorAgent.__new__(OrchestratorAgent)
    parent._task_execution_context = ContextVar("parent_test_execution_context", default=None)

    # When: the child stream starts under the parent execution context.
    with parent.bind_task_execution("parent-task", store):
        stream = start_subagent_stream(
            child,
            task_runner=cast(TaskStoreRunnerPort, cast(object, SimpleNamespace(state_store=store))),
            messages=[{"role": "user", "content": "inspect this"}],
            target_model="qwen3.6:latest",
            subagent_kind="agent_spawn",
        )
        output = "".join(stream.chunks)

    # Then: it preserves the parent task and records child lifecycle events there.
    assert stream.task_id == "parent-task"
    assert output == "child result"
    assert child.bound_task_ids == ["parent-task"]
    assert [event["event_type"] for event in store.list_execution_events("parent-task")] == [
        "subagent_started",
        "subagent_completed",
    ]


def test_subagent_stream_creates_a_durable_task_when_unbound(tmp_path) -> None:
    # Given: a standalone child orchestrator with a task state store.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    child = BoundSubagent(["standalone result"])

    # When: the child stream has no parent execution context.
    stream = start_subagent_stream(
        child,
        task_runner=cast(TaskStoreRunnerPort, cast(object, SimpleNamespace(state_store=store))),
        messages=[{"role": "user", "content": "inspect this"}],
        target_model="qwen3.6:latest",
        subagent_kind="browser_subagent",
    )
    output = "".join(stream.chunks)

    # Then: it creates and completes its own durable direct task.
    assert stream.task_id is not None
    record = store.get_task(stream.task_id)
    assert output == "standalone result"
    assert record is not None
    assert record["status"] == "done"
    assert [event["event_type"] for event in store.list_execution_events(stream.task_id)] == [
        "subagent_registered",
        "context_snapshot",
        "subagent_started",
        "subagent_completed",
    ]
