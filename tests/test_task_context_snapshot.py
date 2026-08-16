from __future__ import annotations

import json

from antigravity_k.engine.task_context_snapshot import (
    load_task_context_snapshot,
    save_task_context_snapshot,
)
from antigravity_k.engine.task_state_store import TaskStateStore


def test_snapshot_round_trip_excludes_transient_cross_scope_memory(tmp_path) -> None:
    # Given: compressed task context also contains transient recalled/global memory.
    db_path = tmp_path / "tasks.db"
    store = TaskStateStore(str(db_path))
    store.create_task("task-a", "goal", "running", "2026-01-01T00:00:00")
    messages = [
        {"role": "system", "content": "[Recalled Memory]\nGLOBAL_SECRET"},
        {"role": "system", "content": "durable system contract"},
        {"role": "user", "content": "TASK_LOCAL_GOAL"},
    ]

    # When: one process saves and another store instance reloads the snapshot.
    save_task_context_snapshot(store, "task-a", messages, "qwen3.6:latest")
    snapshot = load_task_context_snapshot(TaskStateStore(str(db_path)), "task-a")

    # Then: only task-owned context crosses the restart boundary.
    assert snapshot is not None
    content = "\n".join(message.content for message in snapshot.messages)
    assert "TASK_LOCAL_GOAL" in content
    assert "durable system contract" in content
    assert "GLOBAL_SECRET" not in content


def test_invalid_latest_snapshot_fails_closed_instead_of_loading_stale_context(tmp_path) -> None:
    # Given: a valid task snapshot is followed by a corrupt newer event.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-a", "goal", "running", "2026-01-01T00:00:00")
    save_task_context_snapshot(
        store,
        "task-a",
        [{"role": "user", "content": "STALE_CONTEXT"}],
        "qwen3.6:latest",
    )
    store.append_execution_event(
        "task-a",
        "context_snapshot",
        json.dumps({"version": 999, "target_model": "unknown", "messages": []}),
    )

    # When: restart reconstruction asks for the latest snapshot.
    snapshot = load_task_context_snapshot(store, "task-a")

    # Then: corrupted latest state suppresses stale fallback context.
    assert snapshot is None


def test_snapshot_ignores_provider_transport_metadata(tmp_path) -> None:
    # Given: a tool message carries provider-specific transport fields.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-a", "goal", "running", "2026-01-01T00:00:00")
    message = {
        "role": "tool",
        "content": "VERIFIED_RESULT=5050",
        "name": "run_bash_command",
        "tool_call_id": "call-123",
    }

    # When: the durable task snapshot parses the runtime message boundary.
    save_task_context_snapshot(store, "task-a", [message], "qwen3.6:latest")
    snapshot = load_task_context_snapshot(store, "task-a")

    # Then: semantic fields survive without persisting provider transport metadata.
    assert snapshot is not None
    restored = snapshot.messages[0]
    assert restored.content == "VERIFIED_RESULT=5050"
    assert restored.name == "run_bash_command"
    assert "tool_call_id" not in restored.model_dump()


def test_snapshot_preserves_openai_compatible_developer_role(tmp_path) -> None:
    # Given: a direct task uses the OpenAI-compatible developer role.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-a", "goal", "running", "2026-01-01T00:00:00")

    # When: the task context crosses the durable snapshot boundary.
    save_task_context_snapshot(
        store,
        "task-a",
        [{"role": "developer", "content": "PROJECT_RULES_ALPHA"}],
        "qwen3.6:latest",
    )
    snapshot = load_task_context_snapshot(store, "task-a")

    # Then: the semantic role and content remain intact for resume.
    assert snapshot is not None
    assert snapshot.messages[0].role == "developer"
    assert snapshot.messages[0].content == "PROJECT_RULES_ALPHA"
