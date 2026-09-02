from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Callable, cast

from antigravity_k.engine.task_runner import BackgroundTask, BackgroundTaskRunner, TaskStatus
from antigravity_k.engine.task_steering import TaskSteeringQueue


def test_task_steering_queue_preserves_fifo_order() -> None:
    # Given
    queue = TaskSteeringQueue()
    first = queue.request("task-1", "first")
    second = queue.request("task-1", "second")

    # When
    drained = queue.drain("task-1")

    # Then
    assert [item.steering_id for item in drained] == [first.steering_id, second.steering_id]
    assert queue.drain("task-1") == ()


def test_runner_applies_active_turn_steering_between_provider_turns(tmp_path: Path) -> None:
    # Given
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = "task-steering"
    now = "2026-09-01T00:00:00+00:00"
    _ = runner.state_store.create_task(task_id, "base prompt", TaskStatus.RUNNING, now)
    task = BackgroundTask(task_id, "base prompt")
    task.status = TaskStatus.RUNNING
    _ = setattr(runner, "_tasks", {task_id: task})
    release = threading.Event()
    calls: list[list[dict[str, str]]] = []

    class FakeOrchestrator:
        def run_stream(self, messages: list[dict[str, str]], target_model: str) -> Iterator[str]:
            _ = target_model
            calls.append(messages)
            if len(calls) == 1:
                yield "first"
                _ = release.wait(timeout=2)
            else:
                yield "second"

    stream_method = cast(
        Callable[[BackgroundTask, object, str, list[dict[str, str]]], Iterator[str]],
        getattr(runner, "_stream_task"),
    )
    stream = stream_method(task, FakeOrchestrator(), "test-model", [{"role": "user", "content": "base"}])
    first = next(stream)

    # When
    result = runner.steer_task(task_id, "focus on security")
    _ = release.set()
    rest = list(stream)

    # Then
    assert result is not None
    assert result.status == "accepted"
    assert first == "first"
    assert rest == ["second"]
    assert len(calls) == 2
    assert calls[1][-1] == {"role": "user", "content": "[Active-turn steering]\nfocus on security"}
    events = runner.state_store.list_execution_events(task_id)
    assert [event["event_type"] for event in events] == [
        "task.steering.requested",
        "task.steering.applied",
    ]
    assert events[0]["sequence"] < events[1]["sequence"]
