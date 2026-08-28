from datetime import UTC, datetime, timedelta
from pathlib import Path

from antigravity_k.engine.scheduled_job_models import (
    JobCreate,
    JobDelivery,
    JobExecution,
    JobSchedule,
    JobUpdate,
)
from antigravity_k.engine.scheduled_job_service import ScheduledJobService
from antigravity_k.engine.scheduled_job_store import ScheduledJobStore


class FakeAgentRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def submit_task(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return f"task-{len(self.calls)}"

    def get_task_status(self, task_id: str) -> dict[str, object]:
        return {"task_id": task_id, "status": "done", "output": "completed output"}


def make_service(tmp_path: Path) -> tuple[ScheduledJobService, FakeAgentRuntime]:
    runtime = FakeAgentRuntime()
    store = ScheduledJobStore(str(tmp_path / "jobs.db"))
    service = ScheduledJobService(store, runtime.submit_task, runtime.get_task_status)
    return service, runtime


def test_interval_job_persists_and_submits_with_selected_model(tmp_path: Path) -> None:
    service, runtime = make_service(tmp_path)
    now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    job = service.create_job(
        JobCreate(
            name="repository check",
            prompt="Inspect the repository",
            model="qwen3.8:27b",
            context={"priority": "high"},
            schedule=JobSchedule(kind="interval", interval_seconds=300),
        ),
        now=now,
    )

    assert job.next_run_at == now + timedelta(seconds=300)
    assert service.get_job(job.job_id) == job
    run = service.trigger_job(job.job_id, now=now)
    assert run.status == "submitted"
    assert run.task_id == "task-1"
    assert runtime.calls == [
        {
            "prompt": "Inspect the repository",
            "context": {"priority": "high", "scheduled_job_id": job.job_id},
            "target_model": "qwen3.8:27b",
            "use_worktree": False,
            "idempotency_key": run.run_id,
        }
    ]


def test_paused_job_does_not_run_until_resumed(tmp_path: Path) -> None:
    service, runtime = make_service(tmp_path)
    now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    job = service.create_job(
        JobCreate(
            name="due job",
            prompt="Run now",
            schedule=JobSchedule(kind="once", run_at=now),
        ),
        now=now,
    )

    service.pause_job(job.job_id)
    assert service.tick(now=now) == []
    service.resume_job(job.job_id, now=now)
    runs = service.tick(now=now)
    assert len(runs) == 1
    assert len(runtime.calls) == 1


def test_cron_job_calculates_next_utc_run(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    now = datetime(2026, 8, 27, 12, 34, tzinfo=UTC)

    job = service.create_job(
        JobCreate(
            name="hourly",
            prompt="Hourly task",
            schedule=JobSchedule(kind="cron", cron="0 * * * *"),
        ),
        now=now,
    )

    assert job.next_run_at == datetime(2026, 8, 27, 13, 0, tzinfo=UTC)


def test_continuation_job_receives_previous_completed_output(tmp_path: Path) -> None:
    service, runtime = make_service(tmp_path)
    now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    job = service.create_job(
        JobCreate(
            name="continuous",
            prompt="Continue investigation",
            context_mode="continue",
            schedule=JobSchedule(kind="interval", interval_seconds=60),
        ),
        now=now,
    )

    first = service.trigger_job(job.job_id, now=now)
    service.reconcile_runs(now=now + timedelta(seconds=1))
    second = service.trigger_job(job.job_id, now=now + timedelta(seconds=60))

    assert first.status == "submitted"
    assert second.status == "submitted"
    assert runtime.calls[1]["context"] == {
        "scheduled_job_id": job.job_id,
        "previous_output": "completed output",
    }


def test_command_job_records_completed_output_without_agent(tmp_path: Path) -> None:
    store = ScheduledJobStore(str(tmp_path / "jobs.db"))
    calls: list[list[str]] = []

    def run_command(command: list[str]) -> tuple[int, str, str]:
        calls.append(command)
        return 0, "healthy", ""

    service = ScheduledJobService(store, lambda **_: "unused", lambda _: None, command_runner=run_command)
    job = service.create_job(
        JobCreate(
            name="health script",
            prompt="Run health script",
            execution=JobExecution(kind="command", command=["python", "health.py"]),
            schedule=JobSchedule(kind="interval", interval_seconds=60),
        )
    )

    run = service.trigger_job(job.job_id)

    assert calls == [["python", "health.py"]]
    assert run.status == "succeeded"
    assert run.output == "healthy"


def test_job_can_be_edited_and_deleted(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    job = service.create_job(
        JobCreate(
            name="old name",
            prompt="Old prompt",
            schedule=JobSchedule(kind="interval", interval_seconds=60),
        )
    )

    updated = service.update_job(job.job_id, JobUpdate(name="new name", model="qwen3.8:27b"))
    assert updated.name == "new name"
    assert updated.model == "qwen3.8:27b"
    assert service.delete_job(job.job_id) is True
    assert service.get_job(job.job_id) is None


def test_completed_job_delivers_signed_webhook_payload(tmp_path: Path, monkeypatch) -> None:
    store = ScheduledJobStore(str(tmp_path / "jobs.db"))
    deliveries: list[tuple[str, dict[str, object], str]] = []

    def deliver(target: str, payload: dict[str, object], secret: str) -> None:
        deliveries.append((target, payload, secret))

    monkeypatch.setenv("AGK_JOB_WEBHOOK_SECRET", "secret-value")
    service = ScheduledJobService(
        store,
        lambda **_: "unused",
        lambda _: None,
        command_runner=lambda _: (0, "delivered output", ""),
        delivery_sender=deliver,
    )
    job = service.create_job(
        JobCreate(
            name="webhook report",
            prompt="Create report",
            execution=JobExecution(kind="command", command=["report"]),
            delivery=JobDelivery(
                kind="webhook",
                target="https://example.com/hooks/report",
                secret_env="AGK_JOB_WEBHOOK_SECRET",
            ),
            schedule=JobSchedule(kind="interval", interval_seconds=60),
        )
    )

    run = service.trigger_job(job.job_id)

    assert run.delivery_status == "sent"
    assert deliveries[0][0] == "https://example.com/hooks/report"
    assert deliveries[0][1]["job_id"] == job.job_id
    assert deliveries[0][1]["output"] == "delivered output"
    assert deliveries[0][2] == "secret-value"
