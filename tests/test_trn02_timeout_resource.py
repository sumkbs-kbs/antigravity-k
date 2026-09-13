"""TRN-02 — 학습 timeout·취소·자원 반환 검증.

docs/11_COMMERCIAL_GA_100_PLAN.md §TRN-02 수용 기준:
- 무출력 hung process가 timeout 허용 오차 안에 종료된다.
- cancel이 parent/descendant 모두 종료하고 GPU/메모리 reservation을 반환한다.
- checkpoint가 있으면 명시적 resume 가능, 없으면 실패 원인을 보존한다.
- 중복 cancel과 late child registration이 idempotent하다.

감독 계층: training_supervision.supervise_command (공용) →
lora_pipeline.run_training / finetune.training_adapter.run_resolved_training →
training_jobs_api (cancel_event/timeout 배선).

실행: uv run --no-sync pytest tests/test_trn02_timeout_resource.py -q
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from antigravity_k.engine.lora_pipeline import LoRAPipeline, TrainingRunResult
from antigravity_k.finetune.training_supervision import (
    supervise_command,
    terminate_process_group,
)

_SLEEP_CMD = [sys.executable, "-c", "import time; time.sleep(30)"]
_SILENT_CMD = [sys.executable, "-c", "import time; time.sleep(30)"]  # 출력 없음 = hang


def _hang_argv(seconds: int = 30) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def _hang_command(seconds: int = 30) -> str:
    """argv를 run_training이 shlex.split으로 되살릴 수 있는 셸 명령 문자열로 직렬화한다."""
    return " ".join(shlex.quote(part) for part in _hang_argv(seconds))


class TestSuperviseCommand:
    def test_normal_completion_returns_output(self) -> None:
        outcome = supervise_command([sys.executable, "-c", "print('hello'); print('world')"])
        assert outcome.reason == "completed"
        assert outcome.success is True
        assert outcome.return_code == 0
        assert outcome.output == ["hello", "world"]

    def test_timeout_kills_hung_process_within_grace(self) -> None:
        started = time.monotonic()
        outcome = supervise_command(_hang_argv(), timeout_sec=0.5)
        elapsed = time.monotonic() - started
        assert outcome.reason == "timeout"
        assert outcome.success is False
        assert outcome.return_code != 0
        assert elapsed < 10  # 허용 오차: grace(5s) + watchdog 폴링
        assert "timeout" in outcome.detail

    def test_no_output_hang_detected(self) -> None:
        started = time.monotonic()
        outcome = supervise_command(_hang_argv(), no_output_timeout_sec=0.5)
        elapsed = time.monotonic() - started
        assert outcome.reason == "no_output_hang"
        assert outcome.success is False
        assert elapsed < 10
        assert "무출력" in outcome.detail

    def test_cancel_event_terminates_group(self) -> None:
        cancel = threading.Event()

        def _later() -> None:
            time.sleep(0.3)
            cancel.set()

        threading.Thread(target=_later, daemon=True).start()
        outcome = supervise_command(_hang_argv(), cancel_event=cancel)
        assert outcome.reason == "cancelled"
        assert outcome.success is False

    def test_cancel_before_launch_is_idempotent(self) -> None:
        """이미 set된 cancel_event로 시작해도 안전하게 즉시 종료된다."""
        cancel = threading.Event()
        cancel.set()
        outcome = supervise_command(_hang_argv(), cancel_event=cancel)
        assert outcome.reason == "cancelled"

    def test_kills_parent_and_descendant_together(self) -> None:
        """셸이 자식을 스폰한 경우에도 그룹 전체가 함께 종료된다."""
        marker = Path(f"/tmp/trn02_child_{os.getpid()}.pid")
        marker.unlink(missing_ok=True)
        cmd = [
            sys.executable,
            "-c",
            (
                f"import subprocess, sys, time, pathlib;"
                f"child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']);"
                f"pathlib.Path('{marker}').write_text(str(child.pid));"
                f"time.sleep(30)"
            ),
        ]
        outcome = supervise_command(cmd, timeout_sec=1.0)
        assert outcome.reason == "timeout"
        # 자식 PID가 남아 있으면 안 된다 (그룹 종료 검증)
        if marker.exists():
            child_pid = int(marker.read_text().strip())
            try:
                os.kill(child_pid, 0)
                alive = True
            except ProcessLookupError:
                alive = False
            assert not alive, "descendant process survived group termination"
        marker.unlink(missing_ok=True)

    def test_terminate_process_group_is_idempotent(self) -> None:
        proc = subprocess.Popen(_hang_argv(), start_new_session=True)
        terminate_process_group(proc, grace_sec=1.0)
        terminate_process_group(proc, grace_sec=1.0)  # 두 번째 호출은 no-op
        assert proc.poll() is not None


class TestCancelClassificationIsNotRaceDependent:
    """F-15 — 취소가 **watchdog 의 관측**에 의존하면 안 된다.

    `task_process_supervisor.cancel_task`/API cancel 은 event set 과 **동시에** 그룹을
    종료한다. watchdog 은 0.2초 폴링이라, 프로세스가 먼저 죽으면 `fired_reason` 이 비어
    있고 사유가 `completed` 로 남는다(exit_code 는 -15). 여기서는 폴링 간격을 늘려
    **경주를 확정으로** 만들어 고정한다.
    """

    def test_cancel_wins_even_before_watchdog_polls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.finetune import training_supervision as ts

        monkeypatch.setattr(ts, "WATCHDOG_POLL_SEC", 3.0)
        cancel_event = threading.Event()
        captured: list[subprocess.Popen[str]] = []
        results: list[Any] = []

        def _run() -> None:
            results.append(supervise_command(_hang_argv(), cancel_event=cancel_event, on_proc_start=captured.append))

        worker = threading.Thread(target=_run, name="f15-supervise")
        worker.start()
        deadline = time.monotonic() + 10
        while not captured and time.monotonic() < deadline:
            time.sleep(0.01)
        assert captured, "감독 대상 프로세스가 시작되지 않았다"
        # API cancel 핸들러와 같은 두 동작(순서까지 같게)
        cancel_event.set()
        terminate_process_group(captured[0], grace_sec=0.5)
        worker.join(timeout=20)

        assert results, "supervise_command 가 결과를 내지 않았다"
        outcome = results[0]
        assert outcome.return_code != 0, "취소된 프로세스인데 정상 종료 코드다"
        assert outcome.reason == "cancelled", (
            f"취소로 죽었는데 사유가 {outcome.reason!r} 다 — 관측(watchdog)이 아니라 사실로 분류해야 한다"
        )
        assert outcome.success is False

    def test_cancel_event_after_normal_exit_keeps_completed(self) -> None:
        cancel_event = threading.Event()
        outcome = supervise_command([sys.executable, "-c", "print('done')"], cancel_event=cancel_event)
        cancel_event.set()  # 이미 끝난 뒤의 취소 — 정상 완료를 취소로 바꾸면 안 된다

        assert outcome.return_code == 0
        assert outcome.reason == "completed"
        assert outcome.success is True


class TestRunTrainingSupervision:
    def test_timeout_sec_applies_to_real_process(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        pipe = LoRAPipeline()
        command = _hang_command(seconds=30)
        res = pipe.run_training({"platform": "mlx", "command": command}, timeout_sec=0.5)
        assert res.success is False
        assert res.termination == "timeout"
        assert "timeout" in res.error

    def test_cancel_event_marks_cancelled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        pipe = LoRAPipeline()
        cancel = threading.Event()
        threading.Thread(target=lambda: (time.sleep(0.3), cancel.set()), daemon=True).start()
        res = pipe.run_training(
            {"platform": "mlx", "command": _hang_command(seconds=30)},
            cancel_event=cancel,
        )
        assert res.success is False
        assert res.termination == "cancelled"
        assert "cancelled" in res.error

    def test_on_proc_start_exposes_popen(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        pipe = LoRAPipeline()
        captured: list[object] = []

        def _capture(proc: object) -> None:
            captured.append(proc)

        res = pipe.run_training(
            {"platform": "mlx", "command": " ".join([sys.executable, "-c", shlex.quote("print('ok')")])},
            on_proc_start=_capture,
        )
        assert res.success is True
        assert len(captured) == 1
        assert hasattr(captured[0], "pid")

    def test_no_output_timeout_reported(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        pipe = LoRAPipeline()
        res = pipe.run_training(
            {"platform": "mlx", "command": _hang_command(seconds=30)},
            no_output_timeout_sec=0.5,
        )
        assert res.termination == "no_output_hang"


class TestRunResolvedTrainingSupervision:
    def test_timeout_kills_resolved_training(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.finetune.training_adapter import TrainingRunStatus, run_resolved_training
        from antigravity_k.finetune.training_recipe import ResolvedTrainingRecipe

        resolved = ResolvedTrainingRecipe(
            command=tuple(_hang_argv(seconds=30)),
            dataset_sha256="d" * 64,
            dataset_record_count=1,
            train_path=tmp_path / "train.jsonl",
            valid_path=tmp_path / "valid.jsonl",
            adapter_path=tmp_path / "adapters",
            data_dir=tmp_path / "data",
            iterations=1,
            base_model="/models/base",
            base_revision="sha256:base",
            recipe_sha256="r" * 64,
            environment={"python": "3.13"},
            evaluation_sha256="e" * 64,
        )
        # 감독 계층은 스테이징된 데이터셋을 읽는다 — 더미 파일 선생성
        for p in (resolved.train_path, resolved.valid_path):
            p.parent.mkdir(parents=True, exist_ok=True)
            _ = p.write_text('{"q": "hi", "a": "yo"}\n', encoding="utf-8")
        result = run_resolved_training(resolved, timeout_sec=0.5)
        assert result.status is TrainingRunStatus.FAILED
        assert "timeout" in result.stderr


class TestTrainingJobsApi:
    @pytest.fixture()
    def client(self) -> TestClient:
        return TestClient(_app())

    def test_cancel_sets_termination_cancelled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.api.server import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        with patch.object(LoRAPipeline, "apply_recipe", autospec=True) as mock_apply:
            mock_apply.return_value = {
                "recipe": "chat-sft",
                "records": 1,
                "sufficient": True,
                "dataset_path": "data/ds.jsonl",
                "config_path": "data/cfg.json",
                "config": {"command": _hang_command(seconds=30), "platform": "mlx"},
            }
            client = TestClient(app)
            res = client.post(
                "/api/training-jobs",
                json={
                    "recipe": "chat-sft",
                    "base_model": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
                    "platform": "mlx",
                    "hyperparameters": {"iterations": 5, "batch_size": 2},
                },
            )
            job_id = res.json()["job_id"]
            # 프로세스가 등록되고 첫 로그가 찍힐 때까지 대기
            # (전체 suite 부하 시 프로세스 스폰이 느려질 수 있어 20s 상한 —
            #  조기 조건 충족 시 즉시 탈출하므로 솔로 실행 시간은 불변)
            for _ in range(400):
                view = client.get(f"/api/training-jobs/{job_id}").json()
                if view["status"] == "running" and "iter 1" in "\n".join(view["log_tail"]):
                    break
                time.sleep(0.05)
            cancel = client.post(f"/api/training-jobs/{job_id}/cancel")
            assert cancel.status_code == 200
            assert cancel.json()["ok"] is True
            for _ in range(200):
                view = client.get(f"/api/training-jobs/{job_id}").json()
                if view["status"] != "running":
                    break
                time.sleep(0.05)
            assert view["status"] == "failed"
            assert view["termination"] == "cancelled"
            assert "cancelled" in view["error"]
            # F-15 — **정착한** 상태를 본다. 위 두 단언은 cancel 핸들러가 쓴 값을 읽는 것이고,
            # 잡 스레드가 `run_result.termination` 으로 덮어쓰면 취소가 사라진다(그때는
            # `termination='completed'`, `exit_code=-15`). 그 창을 기다리지 않고 통과시키면
            # 이 테스트는 결함을 못 잡는다 — 실제로 attempt-011 의 전체 suite 에서 이 창이 걸렸다.
            settled = _settled_view(client, job_id)
            assert settled["status"] == "failed"
            assert settled["termination"] == "cancelled", (
                "취소가 잡 스레드의 쓰기로 덮였다 — 사용자는 취소했는데 완료로 기록된다(F-15)"
            )
            assert "cancelled" in settled["error"]

    def test_duplicate_cancel_is_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.api.server import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("antigravity_k.engine.lora_pipeline.mlx_lm_available", lambda: True)
        with patch.object(LoRAPipeline, "apply_recipe", autospec=True) as mock_apply:
            mock_apply.return_value = {
                "recipe": "chat-sft",
                "records": 1,
                "sufficient": True,
                "dataset_path": "data/ds.jsonl",
                "config_path": "data/cfg.json",
                "config": {"command": _hang_command(seconds=30), "platform": "mlx"},
            }
            client = TestClient(app)
            job_id = client.post(
                "/api/training-jobs",
                json={
                    "recipe": "chat-sft",
                    "base_model": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
                    "platform": "mlx",
                    "hyperparameters": {"iterations": 5, "batch_size": 2},
                },
            ).json()["job_id"]
            time.sleep(0.2)
            first = client.post(f"/api/training-jobs/{job_id}/cancel")
            second = client.post(f"/api/training-jobs/{job_id}/cancel")
            assert first.json()["ok"] is True
            assert second.json()["ok"] is False  # idempotent — 이미 취소됨
            assert second.json()["detail"] in ("job is not running", "job already cancelled")

    def test_timeout_sec_passed_to_run_training(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.api.server import app

        monkeypatch.chdir(tmp_path)
        seen: dict[str, Any] = {}

        def fake_run_training(
            self: object, config: dict[str, object], on_log: Any = None, timeout_sec: Any = None, **kwargs: Any
        ) -> TrainingRunResult:
            seen["timeout_sec"] = timeout_sec
            seen["no_output_timeout_sec"] = kwargs.get("no_output_timeout_sec")
            seen["cancel_event"] = kwargs.get("cancel_event")
            return TrainingRunResult(success=True, exit_code=0, elapsed_sec=0.01)

        with (
            patch.object(LoRAPipeline, "apply_recipe", autospec=True) as mock_apply,
            patch.object(LoRAPipeline, "run_training", new=fake_run_training),
        ):
            mock_apply.return_value = {
                "recipe": "chat-sft",
                "records": 1,
                "sufficient": True,
                "dataset_path": "data/ds.jsonl",
                "config_path": "data/cfg.json",
                "config": {"command": "python -m mlx_lm.lora", "platform": "mlx"},
            }
            client = TestClient(app)
            res = client.post(
                "/api/training-jobs",
                json={
                    "recipe": "chat-sft",
                    "base_model": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
                    "platform": "mlx",
                    "hyperparameters": {"iterations": 5, "batch_size": 2},
                    "timeout_sec": 90,
                    "no_output_timeout_sec": 30,
                },
            )
            assert res.status_code == 200
            assert seen["timeout_sec"] == 90
            assert seen["no_output_timeout_sec"] == 30
            assert seen["cancel_event"] is not None


def _settled_view(client: TestClient, job_id: str, *, timeout: float = 15.0) -> dict[str, Any]:
    """잡 뷰가 **더 이상 변하지 않을 때까지** 기다렸다가 마지막 값을 돌려준다.

    잡 뷰는 cancel 핸들러와 잡 스레드가 함께 쓴다 — 한 번 읽고 단언하면 어느 쪽 쓰기를
    보았는지에 따라 결과가 달라진다(F-15 가 그 창에 걸렸다). 두 번 연속 같은 값을 보면
    정착한 것으로 본다.
    """
    previous: dict[str, Any] | None = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = client.get(f"/api/training-jobs/{job_id}").json()
        if previous is not None and current == previous and current["status"] != "running":
            return current
        previous = current
        time.sleep(0.1)
    assert previous is not None, "잡 뷰를 한 번도 읽지 못했다"
    return previous


def _app() -> Any:
    from antigravity_k.api.server import app

    return app
