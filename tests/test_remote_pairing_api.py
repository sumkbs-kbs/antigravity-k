"""HTTP contract tests for remote pairing bootstrap and relay."""

import base64

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from antigravity_k.api.routes.remote_pairing_api import get_pairing_manager
from antigravity_k.api.server import _is_protected_path, app


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


@pytest.mark.anyio
async def test_public_bootstrap_completes_pairing_and_relays_opaque_envelopes() -> None:
    # Given an advertisement created by the authenticated control plane.
    manager = get_pairing_manager()
    advertisement = manager.create_pairing()
    client_private = X25519PrivateKey.generate()
    client_public = _b64(client_private.public_key().public_bytes_raw())
    transport = httpx.ASGITransport(app=app)

    # When the remote client completes pairing and posts an encrypted envelope.
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        completed = await client.post(
            "/api/remote/pairing/complete",
            json={
                "pairing_id": advertisement.pairing_id,
                "code": advertisement.code,
                "client_public_key": client_public,
            },
        )
        envelope = manager.seal(advertisement.pairing_id, b"from server")
        accepted = await client.post(
            "/api/remote/pairing/relay",
            json={"pairing_id": advertisement.pairing_id, "envelope": envelope.to_dict()},
        )
        polled = await client.post(
            "/api/remote/pairing/relay/poll",
            json={"pairing_id": advertisement.pairing_id, "limit": 10},
        )

    # Then bootstrap and relay responses expose only the authenticated envelope.
    assert completed.status_code == 200
    assert completed.json()["state"] == "paired"
    assert accepted.status_code == 202
    assert accepted.json()["accepted"] is True
    assert polled.status_code == 200
    assert polled.json()["envelopes"] == [envelope.to_dict()]


def test_control_plane_pairing_creation_remains_protected() -> None:
    # Given the server path policy, When control-plane and bootstrap paths are checked.
    # Then only the client bootstrap endpoints are public.
    assert _is_protected_path("/api/remote/pairing") is True
    assert _is_protected_path("/api/remote/pairing/complete") is False
    assert _is_protected_path("/api/remote/pairing/relay") is False
