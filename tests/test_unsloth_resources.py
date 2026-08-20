from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError

from antigravity_k.engine.provider_adapters.unsloth_resource_broker import (
    UnslothResourceBroker,
)
from antigravity_k.engine.provider_adapters.unsloth_resource_contracts import (
    ReservationId,
    UnslothAdmissionCode,
    UnslothAdmissionDecision,
    UnslothAdmissionRequest,
    UnslothArtifactProvenance,
    UnslothMemorySnapshot,
    UnslothReservationState,
    UnslothResourceOperation,
)


@dataclass(frozen=True, slots=True)
class _MemoryProbe:
    total_bytes: int = 1_000
    available_bytes: int = 900

    def snapshot(self) -> UnslothMemorySnapshot:
        return UnslothMemorySnapshot(
            total_bytes=self.total_bytes,
            available_bytes=self.available_bytes,
        )


def _request(idempotency_key: str, estimated_peak_bytes: int) -> UnslothAdmissionRequest:
    return UnslothAdmissionRequest(
        idempotency_key=idempotency_key,
        operation=UnslothResourceOperation.TRAINING,
        device_id="unified:0",
        estimated_peak_bytes=estimated_peak_bytes,
        artifact=UnslothArtifactProvenance(
            source_uri="hf://unsloth/Qwen3-Coder",
            revision="a" * 40,
            sha256="b" * 64,
        ),
    )


def _admit_after_barrier(
    broker: UnslothResourceBroker,
    request: UnslothAdmissionRequest,
    barrier: Barrier,
) -> UnslothAdmissionDecision:
    _ = barrier.wait()
    return broker.admit(request)


def test_admission_denies_when_minimum_headroom_would_be_violated(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(
        tmp_path / "resources.sqlite3",
        _MemoryProbe(total_bytes=1_000, available_bytes=400),
    )

    decision = broker.admit(_request("memory-denial-0001", estimated_peak_bytes=201))

    assert decision.allowed is False
    assert decision.code is UnslothAdmissionCode.INSUFFICIENT_MEMORY
    assert decision.required_headroom_bytes == 200
    assert decision.projected_available_bytes == 199
    assert broker.status().active_reservations == ()


def test_admission_replays_the_same_idempotent_request(tmp_path: Path) -> None:
    database_path = tmp_path / "resources.sqlite3"
    request = _request("idempotent-run-0001", estimated_peak_bytes=100)
    first = UnslothResourceBroker(database_path, _MemoryProbe()).admit(request)
    reopened_broker = UnslothResourceBroker(database_path, _MemoryProbe())

    replay = reopened_broker.admit(request)

    assert replay.allowed is True
    assert replay.code is UnslothAdmissionCode.REPLAYED
    assert replay.replayed is True
    assert replay.reservation_id == first.reservation_id


def test_admission_rejects_an_idempotency_key_with_different_payload(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    _ = broker.admit(_request("idempotent-run-0002", estimated_peak_bytes=100))

    conflict = broker.admit(_request("idempotent-run-0002", estimated_peak_bytes=101))

    assert conflict.allowed is False
    assert conflict.code is UnslothAdmissionCode.IDEMPOTENCY_CONFLICT
    assert conflict.reservation_id is None


def test_admission_denies_a_second_active_reservation_on_the_same_device(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    _ = broker.admit(_request("device-owner-0001", estimated_peak_bytes=100))

    denied = broker.admit(_request("device-waiter-0001", estimated_peak_bytes=100))

    assert denied.allowed is False
    assert denied.code is UnslothAdmissionCode.DEVICE_BUSY
    assert len(broker.status().active_reservations) == 1


def test_release_is_persistent_and_removes_the_active_reservation(tmp_path: Path) -> None:
    database_path = tmp_path / "resources.sqlite3"
    broker = UnslothResourceBroker(database_path, _MemoryProbe())
    accepted = broker.admit(_request("release-run-00001", estimated_peak_bytes=100))
    reservation_id = ReservationId(accepted.reservation_id or "")

    released = broker.release(reservation_id)

    assert released is not None
    assert released.state is UnslothReservationState.RELEASED
    assert UnslothResourceBroker(database_path, _MemoryProbe()).status().active_reservations == ()


def test_re_admission_after_release_reports_the_released_reservation(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    request = _request("released-replay-001", estimated_peak_bytes=100)
    accepted = broker.admit(request)
    _ = broker.release(ReservationId(accepted.reservation_id or ""))

    replay = broker.admit(request)

    assert replay.allowed is False
    assert replay.code is UnslothAdmissionCode.RESERVATION_RELEASED
    assert replay.reservation_id == accepted.reservation_id
    assert replay.reservation_state is UnslothReservationState.RELEASED
    assert replay.replayed is True


def test_repeat_release_preserves_the_original_release_time(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    accepted = broker.admit(_request("repeat-release-001", estimated_peak_bytes=100))
    reservation_id = ReservationId(accepted.reservation_id or "")
    first_release = broker.release(reservation_id)

    repeated_release = broker.release(reservation_id)

    assert first_release is not None
    assert repeated_release is not None
    assert first_release.released_at is not None
    assert repeated_release.released_at == first_release.released_at


def test_release_frees_the_device_for_a_new_reservation(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    accepted = broker.admit(_request("device-release-001", estimated_peak_bytes=100))
    _ = broker.release(ReservationId(accepted.reservation_id or ""))

    replacement = broker.admit(_request("device-replace-001", estimated_peak_bytes=100))

    assert replacement.allowed is True
    assert replacement.code is UnslothAdmissionCode.ACCEPTED
    assert len(broker.status().active_reservations) == 1


def test_concurrent_distinct_keys_allow_one_active_reservation(tmp_path: Path) -> None:
    database_path = tmp_path / "resources.sqlite3"
    brokers = (
        UnslothResourceBroker(database_path, _MemoryProbe()),
        UnslothResourceBroker(database_path, _MemoryProbe()),
    )
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(
            executor.submit(
                _admit_after_barrier,
                brokers[index],
                _request(f"concurrent-device-{index:04d}", estimated_peak_bytes=100),
                barrier,
            )
            for index in range(2)
        )
        decisions = tuple(future.result() for future in futures)

    assert Counter(decision.code for decision in decisions) == Counter(
        (UnslothAdmissionCode.ACCEPTED, UnslothAdmissionCode.DEVICE_BUSY),
    )
    assert len(brokers[0].status().active_reservations) == 1


def test_concurrent_same_key_accepts_once_and_replays_once(tmp_path: Path) -> None:
    database_path = tmp_path / "resources.sqlite3"
    brokers = (
        UnslothResourceBroker(database_path, _MemoryProbe()),
        UnslothResourceBroker(database_path, _MemoryProbe()),
    )
    request = _request("concurrent-replay-001", estimated_peak_bytes=100)
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(executor.submit(_admit_after_barrier, broker, request, barrier) for broker in brokers)
        decisions = tuple(future.result() for future in futures)

    assert Counter(decision.code for decision in decisions) == Counter(
        (UnslothAdmissionCode.ACCEPTED, UnslothAdmissionCode.REPLAYED),
    )
    assert len({decision.reservation_id for decision in decisions}) == 1
    assert len(brokers[0].status().active_reservations) == 1


def test_provenance_rejects_mutable_or_unverifiable_artifacts() -> None:
    with pytest.raises(ValidationError):
        _ = UnslothArtifactProvenance(
            source_uri="https://huggingface.co/unsloth/model?token=secret",
            revision="main",
            sha256="unknown",
        )


def test_admission_request_rejects_an_unprobed_device() -> None:
    payload = _request("unsupported-device-01", estimated_peak_bytes=100).model_dump(mode="json")
    payload["device_id"] = "cuda:0"

    with pytest.raises(ValidationError):
        _ = UnslothAdmissionRequest.model_validate(payload)
