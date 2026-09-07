"""TRN-01: 학습 recipe 단일 source와 실행 인자 일치 (Red 테스트).

GA-100 plan §TRN-01 수용기준:
1. 요청 recipe, dry-run argv, 실제 child argv, progress denominator, 결과 record가 일치한다.
2. 0/음수/과대 값, backend 미지원 option은 실행 전에 거절된다.
3. MLX와 Unsloth 지원 차이가 capability schema에 정확히 표시된다.
4. deterministic recipe digest와 재실행 provenance가 있다.

Red 상태(구현 전): 아래 테스트는 존재하지 않는 모듈/필드를 참조해 실패한다.
구현 후 전부 green이어야 한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ─── 2. validation: 0/음수/과대 값 사전 거절 ──────────────────────────


class TestHyperparameterValidation:
    def test_zero_iterations_rejected(self) -> None:
        from antigravity_k.finetune.hyperparameters import HyperparameterValidationError, validate_hyperparameters

        with pytest.raises(HyperparameterValidationError, match="iterations"):
            validate_hyperparameters({"iterations": 0})

    def test_negative_learning_rate_rejected(self) -> None:
        from antigravity_k.finetune.hyperparameters import HyperparameterValidationError, validate_hyperparameters

        with pytest.raises(HyperparameterValidationError, match="learning_rate"):
            validate_hyperparameters({"learning_rate": "-1e-5"})

    def test_oversized_batch_rejected(self) -> None:
        from antigravity_k.finetune.hyperparameters import HyperparameterValidationError, validate_hyperparameters

        with pytest.raises(HyperparameterValidationError, match="batch_size"):
            validate_hyperparameters({"batch_size": 100_000})

    def test_unknown_key_rejected(self) -> None:
        from antigravity_k.finetune.hyperparameters import HyperparameterValidationError, validate_hyperparameters

        with pytest.raises(HyperparameterValidationError, match="free_lr"):
            validate_hyperparameters({"free_lr": 1})

    def test_valid_overrides_pass_and_normalize(self) -> None:
        from antigravity_k.finetune.hyperparameters import validate_hyperparameters

        normalized = validate_hyperparameters({"iterations": 600, "learning_rate": "1e-5", "batch_size": 4})
        assert normalized["iterations"] == 600
        assert normalized["batch_size"] == 4
        assert float(normalized["learning_rate"]) == 1e-5

    def test_validation_blocks_apply_recipe_before_any_file_io(self, tmp_path: Path) -> None:
        """잘못된 값은 apply_recipe 입출력이 일어나기 전에 거절된다."""
        from antigravity_k.engine.lora_pipeline import LoRAPipeline

        pipeline = LoRAPipeline(harvest_dir=str(tmp_path / "harvest"))
        with pytest.raises(Exception, match="learning_rate"):
            pipeline.apply_recipe(
                "chat-sft",
                base_model="test/model",
                output_dir=str(tmp_path / "out"),
                platform="mlx",
                hyperparameter_overrides={"learning_rate": "-5"},
            )
        assert not (tmp_path / "out").exists()  # 파일 IO 없음


# ─── 3. capability schema: MLX vs Unsloth 지원 차이 ──────────────────


class TestBackendCapabilities:
    def test_capabilities_exposed_for_both_backends(self) -> None:
        from antigravity_k.finetune.hyperparameters import backend_capabilities

        mlx = backend_capabilities("mlx")
        unsloth = backend_capabilities("unsloth")
        assert mlx["backend"] == "mlx"
        assert unsloth["backend"] == "unsloth"
        for cap in (mlx, unsloth):
            assert "supported_keys" in cap and isinstance(cap["supported_keys"], list)
            assert "executable" in cap and isinstance(cap["executable"], bool)
            assert "reason" in cap

    def test_mlx_executable_unsloth_not_local(self) -> None:
        from antigravity_k.finetune.hyperparameters import backend_capabilities

        assert backend_capabilities("mlx")["executable"] is True
        assert backend_capabilities("unsloth")["executable"] is False

    def test_capability_keys_match_validation_keys(self) -> None:
        from antigravity_k.finetune.hyperparameters import backend_capabilities, known_hyperparameter_keys

        for backend in ("mlx", "unsloth"):
            assert set(known_hyperparameter_keys()) == set(backend_capabilities(backend)["supported_keys"])

    def test_unsloth_only_option_rejected_for_mlx(self) -> None:
        from antigravity_k.finetune.hyperparameters import (
            HyperparameterValidationError,
            validate_hyperparameters,
        )

        with pytest.raises(HyperparameterValidationError, match="mlx"):
            validate_hyperparameters({"num_train_epochs": 3}, backend="mlx")

    def test_recipes_api_exposes_capabilities(self) -> None:
        from fastapi.testclient import TestClient

        from antigravity_k.api.server import app

        client = TestClient(app)
        res = client.get("/api/recipes/capabilities")
        assert res.status_code == 200
        caps = res.json()["capabilities"]
        assert {c["backend"] for c in caps} == {"mlx", "unsloth"}


# ─── 1. 단일 resolve 경로: apply_recipe config argv == typed recipe argv ──


class TestSingleResolvePath:
    @pytest.fixture()
    def harvest_pipeline(self, tmp_path: Path) -> object:
        from antigravity_k.engine.lora_pipeline import LoRAPipeline

        pipeline = LoRAPipeline(harvest_dir=str(tmp_path / "harvest"))
        for i in range(12):
            assert pipeline.harvest(f"q{i}", f"a{i}", quality_score=0.9) is True
        return pipeline

    def test_apply_recipe_config_uses_validated_overrides_in_argv(
        self, harvest_pipeline: object, tmp_path: Path
    ) -> None:
        """단일 resolve 경로: 검증·정규화된 오버라이드 dict가 argv에 그대로 반영된다.

        요청(pinned iterations/batch/lr) → validate → argv. progress denominator와
        provenance도 같은 dict에서 나온다 (잡 API 테스트가 그 일치를 잠근다).
        """
        result = harvest_pipeline.apply_recipe(  # type: ignore[attr-defined]
            "chat-sft",
            base_model="/models/base",
            output_dir=str(tmp_path / "out"),
            platform="mlx",
            hyperparameter_overrides={"iterations": 10, "batch_size": 2, "learning_rate": "2e-5"},
        )
        config = result["config"]
        assert isinstance(config, dict)

        cmd = str(config["command"])

        def _flag_value(flag: str) -> str | None:
            tokens = cmd.split()
            for i, tok in enumerate(tokens):
                if tok == flag and i + 1 < len(tokens):
                    return tokens[i + 1]
            return None

        assert _flag_value("--iters") == "10"  # 요청 값이 argv에 그대로
        assert _flag_value("--batch-size") == "2"
        assert float(_flag_value("--learning-rate") or "0") == 2e-5

    def test_config_carries_recipe_digest(self, harvest_pipeline: object, tmp_path: Path) -> None:
        result = harvest_pipeline.apply_recipe(  # type: ignore[attr-defined]
            "chat-sft",
            base_model="/models/base",
            output_dir=str(tmp_path / "out"),
            platform="mlx",
            hyperparameter_overrides={"iterations": 10},
        )
        config = result["config"]
        assert isinstance(config.get("recipe_sha256"), str) and len(config["recipe_sha256"]) == 64


# ─── 4. deterministic digest + 재실행 provenance ─────────────────────


class TestRecipeDigest:
    def test_digest_deterministic_across_calls_and_processes(self, tmp_path: Path) -> None:
        from antigravity_k.finetune.hyperparameters import compute_recipe_digest

        d1 = compute_recipe_digest(recipe="chat-sft", base_model="m", platform="mlx", overrides={"iterations": 10})
        d2 = compute_recipe_digest(recipe="chat-sft", base_model="m", platform="mlx", overrides={"iterations": 10})
        assert d1 == d2
        assert len(d1) == 64

    def test_digest_changes_with_inputs(self, tmp_path: Path) -> None:
        from antigravity_k.finetune.hyperparameters import compute_recipe_digest

        base = dict(recipe="chat-sft", base_model="m", platform="mlx")
        d1 = compute_recipe_digest(overrides={"iterations": 10}, **base)
        d2 = compute_recipe_digest(overrides={"iterations": 11}, **base)
        d3 = compute_recipe_digest(
            overrides={"iterations": 10}, base_model="other", **{k: v for k, v in base.items() if k != "base_model"}
        )
        assert d1 != d2
        assert d1 != d3

    def test_apply_recipe_records_provenance_on_disk(self, tmp_path: Path) -> None:
        """apply_recipe가 recipe digest/provenance를 디스크에 기록해 재실행 추적이 가능해야 한다."""
        from antigravity_k.engine.lora_pipeline import LoRAPipeline

        pipeline = LoRAPipeline(harvest_dir=str(tmp_path / "harvest"))
        for i in range(12):
            assert pipeline.harvest(f"q{i}", f"a{i}", quality_score=0.9) is True
        result = pipeline.apply_recipe(
            "chat-sft",
            base_model="/models/base",
            output_dir=str(tmp_path / "out"),
            platform="mlx",
            hyperparameter_overrides={"iterations": 10},
        )
        provenance_path = Path(str(result["config_path"])).parent / "recipe_provenance.json"
        assert provenance_path.exists()
        prov = json.loads(provenance_path.read_text(encoding="utf-8"))
        assert prov["recipe"] == "chat-sft"
        assert len(prov["recipe_sha256"]) == 64
        assert prov["records"] == result["records"]
        assert prov["platform"] == "mlx"


# ─── 5. 잡 API: digest 노출 + progress denominator 일치 ───────────────


class TestTrainingJobsApiTrn01:
    def test_job_view_exposes_recipe_digest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from antigravity_k.api.server import app
        from antigravity_k.engine.lora_pipeline import LoRAPipeline, TrainingRunResult

        monkeypatch.chdir(tmp_path)
        with (
            patch.object(LoRAPipeline, "apply_recipe", autospec=True) as mock_apply,
            patch.object(
                LoRAPipeline,
                "run_training",
                new=lambda self, config, on_log=None, timeout_sec=None: TrainingRunResult(
                    success=True, exit_code=0, elapsed_sec=0.01
                ),
            ),
        ):
            mock_apply.return_value = {
                "recipe": "chat-sft",
                "records": 5,
                "sufficient": True,
                "dataset_path": "data/ds",
                "config_path": "data/cfg.json",
                "recipe_sha256": "a" * 64,
                "config": {"command": "python -m mlx_lm.lora --iters 7", "platform": "mlx"},
            }
            client = TestClient(app)
            res = client.post(
                "/api/training-jobs",
                json={
                    "recipe": "chat-sft",
                    "base_model": "m",
                    "source": "",
                    "platform": "mlx",
                    "hyperparameters": {"iterations": 7},
                },
            )
            assert res.status_code == 200
            job_id = res.json()["job_id"]
            import time

            view: dict = {}
            for _ in range(50):
                view = client.get(f"/api/training-jobs/{job_id}").json()
                if view["status"] != "running":
                    break
                time.sleep(0.05)
            assert view["status"] == "completed"
            assert view["recipe_sha256"] == "a" * 64
            # progress denominator == child argv의 --iters (여기선 7)
            assert view["iterations"] == 7

    def test_invalid_hyperparameters_fail_fast_with_400(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """시작 요청 단계에서 잘못된 하이퍼파라미터가 400으로 거절된다 (잡 생성 전)."""
        from fastapi.testclient import TestClient

        from antigravity_k.api.server import app

        monkeypatch.chdir(tmp_path)
        client = TestClient(app)
        res = client.post(
            "/api/training-jobs",
            json={
                "recipe": "chat-sft",
                "base_model": "m",
                "source": "",
                "platform": "mlx",
                "hyperparameters": {"iterations": -3},
            },
        )
        assert res.status_code == 400
        assert "iterations" in res.json()["detail"]
