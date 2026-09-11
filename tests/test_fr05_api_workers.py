"""FR-05 API workers verification: authoritative read/CAS across real server processes.

Validates:
- Two separate uvicorn API worker processes sharing the same conversation store
- Remote append immediately observed by reader (authoritative read)
- Stale expected_revision rejected with HTTP 409 Conflict
- State survives worker restart (cold process readback)
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_ready(url: str, timeout_sec: float = 12.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False


def _http_request(
    url: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            return resp.status, resp_body
    except urllib.error.HTTPError as exc:
        try:
            resp_body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            resp_body = {"raw_error": str(exc)}
        return exc.code, resp_body


@pytest.mark.slow
def test_two_api_workers_authoritative_read_cas_and_restart(tmp_path: Path) -> None:
    store_dir = tmp_path / "conversations"
    store_dir.mkdir(parents=True)

    port_a = _find_free_port()
    port_b = _find_free_port()
    while port_b == port_a:
        port_b = _find_free_port()

    repo_root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["AGK_CONVERSATION_STORE_DIR"] = str(store_dir)
    env["AGK_SEC_DEV_NO_PIN_ALLOW"] = "1"
    env["PYTHONPATH"] = str(repo_root / "src")

    cmd_a = [
        sys.executable,
        "-m",
        "uvicorn",
        "antigravity_k.api.server:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port_a),
        "--log-level",
        "warning",
    ]
    cmd_b = [
        sys.executable,
        "-m",
        "uvicorn",
        "antigravity_k.api.server:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port_b),
        "--log-level",
        "warning",
    ]

    proc_a = subprocess.Popen(cmd_a, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc_b = subprocess.Popen(cmd_b, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        assert _wait_for_ready(f"http://127.0.0.1:{port_a}/v1/health"), "Worker A not healthy"
        assert _wait_for_ready(f"http://127.0.0.1:{port_b}/v1/health"), "Worker B not healthy"

        from antigravity_k.api.auth_routes import get_token_service

        token = get_token_service().issue_token("test_api_workers")
        headers = {"Authorization": f"Bearer {token}"}

        conv_id = f"conv_test_{int(time.time())}"
        project_id = "default"

        # Worker A appends Turn 1
        status, body = _http_request(
            f"http://127.0.0.1:{port_a}/v1/conversations/append",
            method="POST",
            body={
                "project_id": project_id,
                "conversation_id": conv_id,
                "expected_revision": 0,
                "role": "user",
                "content": "Turn 1",
            },
            headers=headers,
        )
        assert status == 200
        assert body["revision"] == 1

        # Worker B reads & caches rev 1
        status, body = _http_request(
            f"http://127.0.0.1:{port_b}/v1/conversations/{conv_id}?project_id={project_id}",
            method="GET",
            headers=headers,
        )
        assert status == 200
        assert body["snapshot"]["revision"] == 1

        # Worker A appends Turn 2
        status, body = _http_request(
            f"http://127.0.0.1:{port_a}/v1/conversations/append",
            method="POST",
            body={
                "project_id": project_id,
                "conversation_id": conv_id,
                "expected_revision": 1,
                "role": "assistant",
                "content": "Turn 2",
            },
            headers=headers,
        )
        assert status == 200
        assert body["revision"] == 2

        # Worker B reads -> must observe rev 2 immediately from disk
        status, body = _http_request(
            f"http://127.0.0.1:{port_b}/v1/conversations/{conv_id}?project_id={project_id}",
            method="GET",
            headers=headers,
        )
        assert status == 200
        assert body["snapshot"]["revision"] == 2
        assert len(body["messages"]) == 2

        # Worker B attempts stale append with expected_revision=1 -> 409 Conflict
        status, body = _http_request(
            f"http://127.0.0.1:{port_b}/v1/conversations/append",
            method="POST",
            body={
                "project_id": project_id,
                "conversation_id": conv_id,
                "expected_revision": 1,
                "role": "user",
                "content": "Turn 3 stale",
            },
            headers=headers,
        )
        assert status == 409
        assert body.get("error") == "stale_conversation_revision"
    finally:
        for p in (proc_a, proc_b):
            try:
                p.send_signal(signal.SIGTERM)
                p.wait(timeout=5)
            except Exception:
                p.kill()

    # Restart verification: Worker C on port_c
    port_c = _find_free_port()
    cmd_c = [
        sys.executable,
        "-m",
        "uvicorn",
        "antigravity_k.api.server:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port_c),
        "--log-level",
        "warning",
    ]
    proc_c = subprocess.Popen(cmd_c, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert _wait_for_ready(f"http://127.0.0.1:{port_c}/v1/health"), "Worker C not healthy"
        status, body = _http_request(
            f"http://127.0.0.1:{port_c}/v1/conversations/{conv_id}?project_id={project_id}",
            method="GET",
            headers=headers,
        )
        assert status == 200
        assert body["snapshot"]["revision"] == 2
        assert len(body["messages"]) == 2
    finally:
        try:
            proc_c.send_signal(signal.SIGTERM)
            proc_c.wait(timeout=5)
        except Exception:
            proc_c.kill()
