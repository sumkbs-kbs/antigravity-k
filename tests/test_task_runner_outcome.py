import json
from contextlib import contextmanager

from antigravity_k.engine.self_capability import is_self_capability_request
from antigravity_k.engine.task_runner import BackgroundTask, BackgroundTaskRunner, TaskStatus
from antigravity_k.engine.task_state_store import TaskExecutionContext


class FakeOrchestrator:
    def run_stream(self, messages, target_model):
        return iter(
            [
                "finished output\n",
                '<tool_call>{"name":"read_file","arguments":{"file_path":"README.md"}}</tool_call>',
            ],
        )


def test_runner_records_successful_task_outcome(tmp_path):
    outcomes = []
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / "tasks.db"),
        outcome_recorder=outcomes.append,
    )

    task_id = runner.submit_task(
        "Read README and summarize it",
        context={"expected_tools": ["read_file"]},
        orchestrator=FakeOrchestrator(),
        target_model="qwen3.6:latest",
    )
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    assert runner._tasks[task_id].status == TaskStatus.DONE
    assert len(outcomes) == 1
    assert outcomes[0].case_id == task_id
    assert outcomes[0].success is True
    assert outcomes[0].expected_tools == ("read_file",)
    assert outcomes[0].used_tools == ("read_file",)
    assert outcomes[0].tokens_out > 0
    assert outcomes[0].calibration_eligible is False


def test_runner_redacts_secrets_before_persisting_task_artifact(tmp_path):
    class FakeVault:
        def __init__(self):
            self.write_calls = []

        def write_note(self, **kwargs):
            self.write_calls.append(kwargs)

    api_secret = "sk-proj-" + "a" * 24
    context_secret = "context-password-secret"
    output_secret = "bearer-token-secret"
    vault = FakeVault()
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / "tasks.db"),
        vault_engine=vault,
    )
    task = BackgroundTask(
        "task-redaction",
        f"API_KEY={api_secret} https://user:password-secret@example.com/path?token=url-secret",
        context={"password": context_secret, "nested": {"api_key": "nested-secret"}},
    )
    task.status = TaskStatus.DONE
    task.output = f"Authorization: Bearer {output_secret}"

    runner._save_to_vault(task)

    assert len(vault.write_calls) == 1
    content = vault.write_calls[0]["content"]
    for secret in (api_secret, context_secret, "nested-secret", output_secret, "password-secret", "url-secret"):
        assert secret not in content
    assert "<REDACTED>" in content


def test_runner_records_benchmark_case_id_instead_of_ephemeral_task_id(tmp_path):
    outcomes = []
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / "tasks.db"),
        outcome_recorder=outcomes.append,
    )

    task_id = runner.submit_task(
        "Search for current AI semiconductor news",
        context={"benchmark_case_id": "srch-002", "expected_tools": ["read_file"]},
        orchestrator=FakeOrchestrator(),
        target_model="qwen3.6:latest",
    )
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    assert outcomes[0].case_id == "srch-002"
    assert outcomes[0].calibration_eligible is True


def test_runner_rejects_invalid_benchmark_output_without_persisting_memory(tmp_path):
    class EmptyResponseOrchestrator:
        def run_stream(self, messages, target_model):
            return iter(["</think>"])

    class FakeVault:
        def __init__(self):
            self.snapshot_messages = []
            self.write_calls = []

        def create_snapshot(self, message):
            self.snapshot_messages.append(message)
            return "snapshot-1"

        def write_note(self, **kwargs):
            self.write_calls.append(kwargs)

    outcomes = []
    vault = FakeVault()
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / "tasks.db"),
        vault_engine=vault,
        outcome_recorder=outcomes.append,
    )
    task_id = runner.submit_task(
        "Write fibonacci implementations",
        context={
            "benchmark_case_id": "sim-001",
            "benchmark_read_only": True,
            "expected_keywords": ["def fibonacci", "O(", "raise", "return"],
        },
        orchestrator=EmptyResponseOrchestrator(),
        target_model="qwen3.6:latest",
    )
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    task = runner._tasks[task_id]
    assert task.status == TaskStatus.FAILED
    assert task.error == "Benchmark output missing required content: def fibonacci, O(, raise, return"
    assert outcomes[0].success is False
    assert outcomes[0].completion_reason == "benchmark_validation_failed"
    assert vault.snapshot_messages == []
    assert vault.write_calls == []


def test_runner_keeps_execution_context_out_of_user_intent(tmp_path):
    class CapturingOrchestrator:
        def __init__(self):
            self.messages = []

        def run_stream(self, messages, target_model):
            self.messages = messages
            return iter(["completed"])

    orchestrator = CapturingOrchestrator()
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = runner.submit_task(
        "Python으로 피보나치 함수를 작성하세요.",
        context={"task_plan": {"capability_matrix": [["capability", "value"]]}},
        orchestrator=orchestrator,
        target_model="qwen3.6:latest",
    )
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    assert is_self_capability_request(orchestrator.messages[0]["content"]) is False
    assert orchestrator.messages[1]["role"] == "system"


def test_runner_marks_answer_only_task_as_direct_response(tmp_path):
    class CapturingOrchestrator:
        def __init__(self):
            self.messages = []

        def run_stream(self, messages, target_model):
            self.messages = messages
            return iter(["completed"])

    orchestrator = CapturingOrchestrator()
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = runner.submit_task(
        "Python factorial 함수를 작성해. 파일을 수정하지 말고 코드만 출력해.",
        orchestrator=orchestrator,
        target_model="qwen3.6:latest",
    )
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    execution_context = json.loads(orchestrator.messages[1]["content"].split(": ", 1)[1])
    assert execution_context["direct_response"] is True


def test_runner_records_failed_task_outcome(tmp_path):
    outcomes = []
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / "tasks.db"),
        outcome_recorder=outcomes.append,
    )

    task_id = runner.submit_task("will fail", orchestrator=None, target_model="qwen3.6:latest")
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    assert runner._tasks[task_id].status == TaskStatus.FAILED
    assert len(outcomes) == 1
    assert outcomes[0].success is False
    assert outcomes[0].completion_reason == "failed"
    assert "Orchestrator is required" in outcomes[0].error


def test_runner_preserves_quality_gate_failure_and_rolls_back_snapshot(tmp_path):
    class QualityFailingOrchestrator:
        vault_engine = None

        def __init__(self):
            self.task_execution_context: TaskExecutionContext | None = None

        @contextmanager
        def bind_task_execution(self, task_id, state_store):
            self.task_execution_context = TaskExecutionContext(task_id, state_store)
            try:
                yield
            finally:
                self.task_execution_context = None

        def run_stream(self, messages, target_model):
            assert self.task_execution_context is not None
            self.task_execution_context.state_store.transition(
                self.task_execution_context.task_id,
                "failed",
                output="invalid output",
                error="quality_gate_failed: incomplete answer",
            )
            return iter(["invalid output"])

    class FakeVault:
        def __init__(self):
            self.restored = []

        def create_snapshot(self, message):
            return "snapshot-quality"

        def restore_snapshot(self, snapshot_hash):
            self.restored.append(snapshot_hash)
            return True

    outcomes = []
    vault = FakeVault()
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / "tasks.db"),
        vault_engine=vault,
        outcome_recorder=outcomes.append,
    )
    task_id = runner.submit_task(
        "write code",
        orchestrator=QualityFailingOrchestrator(),
        target_model="qwen3.6:latest",
    )
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    task = runner._tasks[task_id]
    assert task.status == TaskStatus.FAILED
    assert task.error == "quality_gate_failed: incomplete answer"
    assert outcomes[0].success is False
    assert outcomes[0].completion_reason == "quality_gate_failed"
    assert vault.restored == ["snapshot-quality"]


def test_runner_rolls_back_snapshot_on_failure(tmp_path):
    class FailingOrchestrator:
        def run_stream(self, messages, target_model):
            raise RuntimeError("model execution failed")

    class FakeVault:
        def __init__(self):
            self.restored = []

        def create_snapshot(self, message):
            return "snapshot-1"

        def restore_snapshot(self, snapshot_hash):
            self.restored.append(snapshot_hash)
            return True

    vault = FakeVault()
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"), vault_engine=vault)
    task_id = "task-rollback"
    runner.state_store.create_task(task_id, "will fail", "pending", "2026-01-01T00:00:00")
    task = BackgroundTask(task_id, "will fail")

    runner._run_task(task, FailingOrchestrator(), "qwen3.6:latest")

    assert task.status == TaskStatus.FAILED
    assert vault.restored == ["snapshot-1"]


def test_runner_records_cancelled_task_outcome(tmp_path):
    outcomes = []
    runner = BackgroundTaskRunner(
        db_path=str(tmp_path / "tasks.db"),
        outcome_recorder=outcomes.append,
    )
    task_id = "task-cancelled"
    runner.state_store.create_task(task_id, "cancel me", "pending", "2026-01-01T00:00:00")
    task = BackgroundTask(task_id, "cancel me")
    task.cancel_event.set()
    runner._tasks[task_id] = task

    runner._run_task(task, FakeOrchestrator(), "qwen3.6:latest")

    assert len(outcomes) == 1
    assert outcomes[0].success is False
    assert outcomes[0].completion_reason == "cancelled"


def test_runner_cancel_keeps_in_memory_status_in_sync_with_durable_state(tmp_path):
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    task_id = "task-cancel-api"
    runner.state_store.create_task(task_id, "cancel me", "pending", "2026-01-01T00:00:00")
    task = BackgroundTask(task_id, "cancel me")
    runner._tasks[task_id] = task

    assert runner.cancel_task(task_id) is True

    status = runner.get_status(task_id)
    record = runner.state_store.get_task(task_id)
    assert status is not None
    assert record is not None
    assert status["status"] == TaskStatus.CANCELLED
    assert status["error"] == "Task was manually cancelled by the user."
    assert record["status"] == TaskStatus.CANCELLED
    assert record["error"] == status["error"]
