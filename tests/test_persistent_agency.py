from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from antigravity_k.engine.event_bus import attach_persistent_agency
from antigravity_k.engine.hook_event_bus import HookEventEmit
from antigravity_k.engine.persistent_agency import (
    AgencyConfig,
    EventType,
    ObjectiveStatus,
    PersistentAgencyController,
)


def test_controller_persists_events_and_projects_recent_summary(tmp_path: Path) -> None:
    controller = PersistentAgencyController(
        project_root=str(tmp_path),
        config=AgencyConfig(enabled=True, recent_event_limit=2, summary_event_limit=1),
    )

    observation = controller.record_observation(
        project_id="demo",
        trajectory_id="main",
        text="A large modding task started",
    )
    _ = controller.record_thought("demo", "main", "Split the task into verifiable units")
    _ = controller.record_summary("demo", "main", "The task is staged and waiting for the next safe action")

    reopened = PersistentAgencyController(
        project_root=str(tmp_path),
        config=AgencyConfig(enabled=True, recent_event_limit=2, summary_event_limit=1),
    )
    projection = reopened.project_context("demo", "main")

    assert observation.event_type is EventType.OBSERVATION
    assert len(projection.event_ids) == 2
    assert "waiting for the next safe action" in projection.text
    assert projection.event_ids[0] != observation.event_id


def test_objective_queue_is_atomic_and_scheduler_is_bounded(tmp_path: Path) -> None:
    controller = PersistentAgencyController(
        project_root=str(tmp_path),
        config=AgencyConfig(enabled=True, base_idle_delay_seconds=5, max_idle_delay_seconds=20),
    )
    objective = controller.enqueue_objective("demo", "Verify the next safe change", priority=10)

    first = controller.claim_next_objective("demo")
    second = controller.claim_next_objective("demo")

    assert first is not None
    assert first.objective_id == objective.objective_id
    assert first.status is ObjectiveStatus.CLAIMED
    assert second is None
    assert controller.scheduler_decision("demo").should_wake is True

    _ = controller.complete_objective(objective.objective_id)
    assert controller.scheduler_decision("demo", idle_cycles=5).delay_seconds == 20


def test_projection_redacts_secrets_and_preserves_raw_event_recall(tmp_path: Path) -> None:
    controller = PersistentAgencyController(
        project_root=str(tmp_path),
        config=AgencyConfig(enabled=True),
    )

    event = controller.append_event(
        project_id="demo",
        trajectory_id="main",
        event_type=EventType.OBSERVATION,
        payload={"text": "token=sk-test-abcdefghijklmnopqrstuvwxyz"},
    )
    projection = controller.project_context("demo", "main", query="token")

    assert "sk-test" not in json.dumps(event.payload)
    assert "[REDACTED]" in projection.text
    assert event.event_id in projection.event_ids


def test_branch_parent_metadata_and_kill_switch_are_durable(tmp_path: Path) -> None:
    controller = PersistentAgencyController(
        project_root=str(tmp_path),
        config=AgencyConfig(enabled=True),
    )
    root = controller.record_observation("demo", "main", "baseline")
    child = controller.append_event(
        "demo",
        "main",
        EventType.THOUGHT,
        {"text": "parallel hypothesis"},
        branch_id="hypothesis-a",
        parent_event_id=root.event_id,
    )

    controller.pause("demo")
    paused = controller.scheduler_decision("demo")
    reopened = PersistentAgencyController(str(tmp_path), AgencyConfig(enabled=True))
    events = reopened.store.list_events("demo", "main")

    assert child.branch_id == "hypothesis-a"
    assert child.parent_event_id == root.event_id
    assert events[-1].branch_id == "hypothesis-a"
    assert paused.reason == "paused"
    assert paused.should_wake is False


def test_stale_claim_is_reclaimed_after_worker_interruption(tmp_path: Path) -> None:
    controller = PersistentAgencyController(
        project_root=str(tmp_path),
        config=AgencyConfig(enabled=True, objective_lease_seconds=0),
    )
    objective = controller.enqueue_objective("demo", "Recover interrupted work")
    first = controller.claim_next_objective("demo")
    second = controller.claim_next_objective("demo")

    assert first is not None
    assert second is not None
    assert second.objective_id == objective.objective_id


def test_external_hook_events_are_redacted_and_projectable(tmp_path: Path) -> None:
    controller = PersistentAgencyController(str(tmp_path), AgencyConfig(enabled=True))
    event = HookEventEmit("lint-error", {"file": "a.py", "token": "sk-test-abcdefghijklmnopqrstuvwxyz"})

    class Bus:
        def __init__(self) -> None:
            self._persistent_agency_bindings: set[tuple[int, str, str]] = set()
            self.callback: Callable[[HookEventEmit], None] | None = None

        def subscribe_all(self, callback: Callable[[HookEventEmit], None]) -> None:
            self.callback = callback

    bus = Bus()
    _ = attach_persistent_agency(controller, controller.project_id, hook_bus=bus)
    assert bus.callback is not None
    bus.callback(event)

    projection = controller.project_context(controller.project_id, "hooks", query="lint-error")
    assert "lint-error" in projection.text
    assert "sk-test" not in projection.text


def test_objective_task_binding_survives_reconciliation(tmp_path: Path) -> None:
    controller = PersistentAgencyController(str(tmp_path), AgencyConfig(enabled=True))
    objective = controller.enqueue_objective("demo", "Run the indexed checks", trajectory_id="main")
    claimed = controller.claim_next_objective("demo")
    assert claimed is not None

    _ = controller.bind_objective_task("task_123", objective.objective_id, "demo", "main")
    assert controller.list_objective_tasks("demo") == ["task_123"]
    assert controller.reconcile_task_status("task_123", "done") is True
    assert controller.reconcile_task_status("task_123", "done") is False
    stored = controller.get_objective(objective.objective_id)

    assert stored is not None
    assert stored.status is ObjectiveStatus.DONE


def test_failed_objective_task_is_requeued_for_retry(tmp_path: Path) -> None:
    controller = PersistentAgencyController(str(tmp_path), AgencyConfig(enabled=True))
    objective = controller.enqueue_objective("demo", "Retry the failed check")
    assert controller.claim_next_objective("demo") is not None
    _ = controller.bind_objective_task("task_failed", objective.objective_id, "demo", "main")

    assert controller.reconcile_task_status("task_failed", "failed") is True
    stored = controller.get_objective(objective.objective_id)

    assert stored is not None
    assert stored.status is ObjectiveStatus.PENDING


def test_task_result_is_bounded_redacted_and_idempotent(tmp_path: Path) -> None:
    controller = PersistentAgencyController(str(tmp_path), AgencyConfig(enabled=True))
    objective = controller.enqueue_objective("demo", "Remember the result")
    _ = controller.claim_next_objective("demo")
    _ = controller.bind_objective_task("task_result", objective.objective_id, "demo", "main")

    event = controller.record_task_result(
        "task_result",
        "done",
        output="token=sk-test-abcdefghijklmnopqrstuvwxyz\n" + ("x" * 8_000),
    )
    duplicate = controller.record_task_result("task_result", "done", output="duplicate")

    assert event is not None
    assert event.event_type is EventType.SUMMARY
    assert len(str(event.payload["text"])) <= 4_100
    assert "sk-test" not in str(event.payload["text"])
    assert duplicate is None
