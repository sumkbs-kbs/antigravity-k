from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from antigravity_k.engine.provider_adapters.unsloth_resource_broker import UnslothResourceBroker
from antigravity_k.engine.provider_adapters.unsloth_resource_contracts import (
    ReservationId,
    UnslothAdmissionCode,
    UnslothMemorySnapshot,
    UnslothResourceOperation,
)
from antigravity_k.finetune.resource_admission import (
    FinetuneResourceAdmission,
    FinetuneResourceAdmissionError,
    FinetuneResourceSettings,
    build_merge_admission_request,
    build_training_admission_request,
    reserve_finetune_resource,
)
from antigravity_k.finetune.training_adapter import TrainingRunResult, TrainingRunStatus
from antigravity_k.finetune.training_recipe import ResolvedTrainingRecipe


class _MemoryProbe:
    def snapshot(self) -> UnslothMemorySnapshot:
        return UnslothMemorySnapshot(total_bytes=1_000_000, available_bytes=900_000)


def _broker(tmp_path: Path) -> UnslothResourceBroker:
    return UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())


def _resolved(tmp_path: Path) -> ResolvedTrainingRecipe:
    train_path = tmp_path / "train.jsonl"
    valid_path = tmp_path / "valid.jsonl"
    _ = train_path.write_text('{"text":"train"}\n', encoding="utf-8")
    _ = valid_path.write_text('{"text":"valid"}\n', encoding="utf-8")
    return ResolvedTrainingRecipe(
        command=("python", "-m", "mlx_lm", "lora"),
        dataset_sha256="a" * 64,
        dataset_record_count=2,
        train_path=train_path,
        valid_path=valid_path,
        adapter_path=tmp_path / "run" / "adapters",
        data_dir=tmp_path / "run" / "data",
        iterations=1,
        base_model="/models/base",
        base_revision="sha256:base-revision",
        recipe_sha256="b" * 64,
        environment={"python": "3.13"},
        evaluation_sha256="c" * 64,
    )


def _training_result(resolved: ResolvedTrainingRecipe) -> TrainingRunResult:
    return TrainingRunResult(
        status=TrainingRunStatus.SUCCESS,
        return_code=0,
        dataset_sha256=resolved.dataset_sha256,
        adapter_path=resolved.adapter_path,
        data_dir=resolved.data_dir,
        iterations=resolved.iterations,
        stdout="trained",
        stderr="",
        base_model=resolved.base_model,
        base_revision=resolved.base_revision,
        recipe_sha256=resolved.recipe_sha256,
        environment=resolved.environment,
        evaluation_sha256=resolved.evaluation_sha256,
    )


def test_training_request_binds_file_provenance_and_resource_operation(tmp_path: Path) -> None:
    resolved = _resolved(tmp_path)
    settings = FinetuneResourceSettings(
        database_path=tmp_path / "resources.sqlite3",
        estimated_peak_bytes=100_000,
        idempotency_key="local-training-request-0001",
    )

    request = build_training_admission_request(resolved, settings)

    assert request.operation is UnslothResourceOperation.TRAINING
    assert request.estimated_peak_bytes == 100_000
    assert request.idempotency_key == "local-training-request-0001"
    assert request.artifact.source_uri == resolved.train_path.resolve().as_uri()
    assert request.artifact.revision == resolved.recipe_sha256
    assert request.artifact.sha256 == hashlib.sha256(resolved.train_path.read_bytes()).hexdigest()


def test_merge_request_binds_training_result_file(tmp_path: Path) -> None:
    resolved = _resolved(tmp_path)
    training = _training_result(resolved)
    run_path = tmp_path / "training_result.json"
    _ = run_path.write_text(training.model_dump_json(), encoding="utf-8")
    settings = FinetuneResourceSettings(
        database_path=tmp_path / "resources.sqlite3",
        estimated_peak_bytes=80_000,
        idempotency_key="local-merge-request-0001",
    )

    request = build_merge_admission_request(run_path, training, settings)

    assert request.operation is UnslothResourceOperation.CHECKPOINT_LOAD
    assert request.artifact.source_uri == run_path.resolve().as_uri()
    assert request.artifact.revision == training.recipe_sha256
    assert request.artifact.sha256 == hashlib.sha256(run_path.read_bytes()).hexdigest()


def test_resource_lease_releases_after_success(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    request = build_training_admission_request(
        _resolved(tmp_path),
        FinetuneResourceSettings(
            database_path=tmp_path / "resources.sqlite3",
            estimated_peak_bytes=100_000,
            idempotency_key="local-training-release-0001",
        ),
    )

    with reserve_finetune_resource(FinetuneResourceAdmission(broker=broker, request=request)) as decision:
        assert decision.code is UnslothAdmissionCode.ACCEPTED
        assert len(broker.status().active_reservations) == 1

    assert broker.status().active_reservations == ()


def test_resource_lease_releases_when_operation_raises(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    request = build_training_admission_request(
        _resolved(tmp_path),
        FinetuneResourceSettings(
            database_path=tmp_path / "resources.sqlite3",
            estimated_peak_bytes=100_000,
            idempotency_key="local-training-exception-0001",
        ),
    )

    with pytest.raises(RuntimeError, match="operation failed"):
        with reserve_finetune_resource(FinetuneResourceAdmission(broker=broker, request=request)):
            raise RuntimeError("operation failed")

    assert broker.status().active_reservations == ()


def test_resource_lease_rejects_busy_device_without_running_body(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    resolved = _resolved(tmp_path)
    occupied = build_training_admission_request(
        resolved,
        FinetuneResourceSettings(
            database_path=tmp_path / "resources.sqlite3",
            estimated_peak_bytes=100_000,
            idempotency_key="local-training-occupied-0001",
        ),
    )
    accepted = broker.admit(occupied)
    blocked = occupied.model_copy(update={"idempotency_key": "local-training-blocked-0001"})
    entered = False

    with pytest.raises(FinetuneResourceAdmissionError) as error:
        with reserve_finetune_resource(FinetuneResourceAdmission(broker=broker, request=blocked)):
            entered = True

    assert error.value.code is UnslothAdmissionCode.DEVICE_BUSY
    assert entered is False
    assert accepted.reservation_id is not None
    _ = broker.release(ReservationId(accepted.reservation_id))


def test_resource_lease_rejects_idempotent_replay_without_duplicate_body(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    request = build_training_admission_request(
        _resolved(tmp_path),
        FinetuneResourceSettings(
            database_path=tmp_path / "resources.sqlite3",
            estimated_peak_bytes=100_000,
            idempotency_key="local-training-replay-0001",
        ),
    )
    accepted = broker.admit(request)

    with pytest.raises(FinetuneResourceAdmissionError) as error:
        with reserve_finetune_resource(FinetuneResourceAdmission(broker=broker, request=request)):
            raise AssertionError("replayed admission must not run the operation")

    assert error.value.code is UnslothAdmissionCode.REPLAYED
    assert accepted.reservation_id is not None
    _ = broker.release(ReservationId(accepted.reservation_id))
