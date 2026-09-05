"""Remote pairing and encrypted relay contract tests."""

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from antigravity_k.engine.remote_pairing import (
    PairingManager,
    PairingState,
    RemotePairingError,
)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _tamper(value: str) -> str:
    raw = bytearray(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    raw[0] ^= 1
    return _b64(bytes(raw))


def _client_key() -> tuple[X25519PrivateKey, str]:
    private = X25519PrivateKey.generate()
    return private, _b64(private.public_key().public_bytes_raw())


def _paired_manager() -> tuple[PairingManager, str, X25519PrivateKey]:
    manager = PairingManager()
    advertisement = manager.create_pairing()
    client_private, client_public = _client_key()
    manager.complete_pairing(advertisement.pairing_id, advertisement.code, client_public)
    return manager, advertisement.pairing_id, client_private


def test_create_pairing_returns_public_qr_advertisement() -> None:
    # Given a fresh pairing manager, When an advertisement is created.
    manager = PairingManager()
    advertisement = manager.create_pairing(ttl_seconds=120)

    # Then the QR payload contains only the public bootstrap contract.
    payload = json.loads(advertisement.qr_payload)
    assert payload["pairing_id"] == advertisement.pairing_id
    assert payload["code"] == advertisement.code
    assert payload["server_public_key"] == advertisement.server_public_key
    assert payload["expires_at"] == advertisement.expires_at
    assert len(advertisement.code) == 8


def test_pairing_seals_and_opens_authenticated_envelope() -> None:
    # Given a completed X25519 pairing, When data is sealed and opened.
    manager, pairing_id, _ = _paired_manager()
    envelope = manager.seal(pairing_id, b"hello remote")

    # Then the relay preserves confidentiality and integrity.
    assert manager.open(pairing_id, envelope) == b"hello remote"
    tampered = envelope.__class__(envelope.version, envelope.nonce, _tamper(envelope.ciphertext))
    with pytest.raises(RemotePairingError, match="invalid_envelope"):
        manager.open(pairing_id, tampered)


def test_pairing_rejects_replay_and_supports_rotation_and_revocation() -> None:
    # Given a pending pairing, When the one-time code is consumed.
    manager = PairingManager()
    advertisement = manager.create_pairing()
    _, client_public = _client_key()
    info = manager.complete_pairing(advertisement.pairing_id, advertisement.code, client_public)

    # Then replay is rejected, rotation advances the epoch, and revoke closes access.
    assert info.state is PairingState.PAIRED
    with pytest.raises(RemotePairingError, match="already_completed"):
        manager.complete_pairing(advertisement.pairing_id, advertisement.code, client_public)
    rotated = manager.rotate(advertisement.pairing_id)
    assert rotated.key_epoch == info.key_epoch + 1
    manager.revoke(advertisement.pairing_id)
    assert manager.get_info(advertisement.pairing_id).state is PairingState.REVOKED
    with pytest.raises(RemotePairingError, match="revoked"):
        manager.seal(advertisement.pairing_id, b"closed")


def test_relay_queue_verifies_envelope_before_enqueue_and_drains_fifo() -> None:
    # Given two authenticated relay envelopes, When they are queued and drained.
    manager, pairing_id, _ = _paired_manager()
    first = manager.seal(pairing_id, b"one")
    second = manager.seal(pairing_id, b"two")
    manager.enqueue(pairing_id, first)
    manager.enqueue(pairing_id, second)

    # Then only verified envelopes are returned in insertion order.
    assert manager.drain(pairing_id, limit=1) == (first,)
    assert manager.drain(pairing_id) == (second,)
    with pytest.raises(RemotePairingError, match="replayed_envelope"):
        manager.enqueue(pairing_id, first)
    with pytest.raises(RemotePairingError, match="invalid_envelope"):
        manager.enqueue(pairing_id, first.__class__(first.version, "bad", first.ciphertext))
