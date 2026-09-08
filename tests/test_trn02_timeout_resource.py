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
            # 프로세스가 등록되고 첫 로그가 찍힐 때까지 대기 (전체 스위트 부하 감안 여유)
            for _ in range(120):
                view = client.get(f"/api/training-jobs/{job_id}").json()
                if view["status"] == "running" and "iter 1" in "\n".join(view["log_tail"]):
                    break
                time.sleep(0.05)
            cancel = client.post(f"/api/training-jobs/{job_id}/cancel")
            assert cancel.status_code == 200
            assert cancel.json()["ok"] is True
            for _ in range(50):
                view = client.get(f"/api/training-jobs/{job_id}").json()
                if view["status"] != "running":
                    break
                time.sleep(0.05)
            assert view["status"] == "failed"
            assert view["termination"] == "cancelled"
            assert "cancelled" in view["error"]

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


def _app() -> Any:
    from antigravity_k.api.server import app

    return app
