"""Phase 59: 학습 잡 API 테스트 — apply_recipe + run_training 백그라운드 실행.

StudioPage Start Training의 실제 백엔드 계약을 잠근다:
시작 → 폴링 → 완료/실패 상태 전환, 하이퍼파라미터 전달, 404/취소.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.server import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "recipe": "chat-sft",
        "base_model": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        "source": "",
        "platform": "mlx",
        "hyperparameters": {"iterations": 5, "epochs": 2},
    }
    base.update(overrides)
    return base


def test_unknown_job_returns_404(client: TestClient) -> None:
    res = client.get("/api/training-jobs/train_does_not_exist")
    assert res.status_code == 404


def test_start_and_poll_completed_job(client: TestClient, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """레시피→config→가짜 학습 실행까지 완료 상태로 도달한다."""
    from antigravity_k.engine.lora_pipeline import TrainingRunResult

    monkeypatch.chdir(tmp_path)

    def fake_run_training(
        self: object, config: dict[str, object], on_log: Any = None, timeout_sec: Any = None
    ) -> TrainingRunResult:
        if on_log is not None:
            on_log("iter 1: loss=2.0")
            on_log("iter 4: loss=1.1")
        return TrainingRunResult(success=True, exit_code=0, elapsed_sec=0.1, log_tail=[], command="x")

    from antigravity_k.engine.lora_pipeline import LoRAPipeline

    with (
        patch.object(LoRAPipeline, "apply_recipe", autospec=True) as mock_apply,
        patch.object(LoRAPipeline, "run_training", new=fake_run_training),
    ):
        mock_apply.return_value = {
            "recipe": "chat-sft",
            "records": 3,
            "sufficient": True,
            "dataset_path": "data/ds.jsonl",
            "config_path": "data/cfg.json",
            "config": {"command": "python -m mlx_lm.lora", "platform": "mlx"},
        }
        res = client.post("/api/training-jobs", json=_body())
        assert res.status_code == 200, res.text
        job_id = res.json()["job_id"]

        import time

        for _ in range(50):
            view = client.get(f"/api/training-jobs/{job_id}").json()
            if view["status"] != "running":
                break
            time.sleep(0.05)
        assert view["status"] == "completed"
        assert view["records"] == 3
        assert view["sufficient"] is True
        assert view["progress"] == 100
        assert view["loss"] == 1.1  # 마지막 파싱된 실제 loss
        assert any("iter 4" in line for line in view["log_tail"])


def test_apply_recipe_failure_marks_job_failed(
    client: TestClient, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    from antigravity_k.engine.lora_pipeline import LoRAPipeline

    def boom(*_a: object, **_k: object) -> dict[str, object]:
        raise FileNotFoundError("source file missing")

    with patch.object(LoRAPipeline, "apply_recipe", side_effect=boom):
        res = client.post("/api/training-jobs", json=_body())
        job_id = res.json()["job_id"]

        import time

        for _ in range(50):
            view = client.get(f"/api/training-jobs/{job_id}").json()
            if view["status"] != "running":
                break
            time.sleep(0.05)
        assert view["status"] == "failed"
        assert "source file missing" in view["error"]


def test_cancel_non_running_job_is_rejected(client: TestClient) -> None:
    res = client.post("/api/training-jobs/train_nothing/cancel")
    assert res.status_code == 404
