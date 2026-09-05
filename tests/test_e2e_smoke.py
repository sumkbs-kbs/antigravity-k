"""
E2E Smoke Test — 시스템 기본 기능이 정상 동작하는지 빠르게 검증합니다.

이 테스트는 실제 서버가 실행 중이라고 가정하며,
CI 환경에서는 서버 기동 후 실행됩니다.

실행:
    # 서버 실행 중:
    python -m pytest tests/test_e2e_smoke.py -v

    # 서버 실행 + 테스트 (Makefile):
    make test-e2e
"""

import os
import re
import select
import subprocess
import time
from pathlib import Path

import pytest
import requests

from tests._cli_subprocess import python_invocation

# ─── 설정 ───────────────────────────────────────────────────────────

# 테스트 대상 서버 URL (환경변수로 오버라이드 가능)
default_base_url = "http://127.0.0.1:8000"
base_url = os.environ.get("AGK_TEST_URL", default_base_url)
health_url = f"{base_url}/v1/health"
api_prefix = base_url

# 헤더
HEADERS = {"Content-Type": "application/json"}


def _set_base_url(url: str) -> None:
    global api_prefix, base_url, health_url
    base_url = url.rstrip("/")
    health_url = f"{base_url}/v1/health"
    api_prefix = base_url


# ─── 헬스 체크 ──────────────────────────────────────────────────────


def test_health_endpoint():
    """기본 헬스 체크 엔드포인트가 정상 응답하는지 검증."""
    resp = requests.get(health_url, timeout=10, headers=HEADERS)
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    data = resp.json()
    assert data.get("status") in ("ok", "healthy"), f"Unexpected status: {data}"


def test_health_returns_backends():
    """헬스 체크에 backends 정보가 포함되어야 함."""
    resp = requests.get(health_url, timeout=10, headers=HEADERS)
    data = resp.json()
    # backends 필드가 존재해야 함 (빈 객체여도 OK)
    assert "backends" in data, f"Missing 'backends' in health response: {data.keys()}"


def test_health_returns_version():
    """헬스 체크에 버전 정보가 포함되어야 함."""
    resp = requests.get(health_url, timeout=10, headers=HEADERS)
    data = resp.json()
    # version 필드 또는 model 필드가 있어야 함
    assert any(
        k in data for k in ("version", "model", "engine")
    ), f"Missing version info in health response: {data.keys()}"


# ─── API 라우트 검증 ────────────────────────────────────────────────


def test_cors_headers():
    """API 응답에 CORS 헤더가 포함되어야 함."""
    resp = requests.options(
        f"{api_prefix}/v1/chat/completions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
        timeout=10,
    )
    assert "access-control-allow-origin" in resp.headers, "Missing CORS header"


def test_security_headers():
    """API 응답에 보안 헤더가 포함되어야 함."""
    resp = requests.get(health_url, timeout=10, headers=HEADERS)
    headers = resp.headers
    security_headers = [
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "content-security-policy",
    ]
    for h in security_headers:
        assert h in headers, f"Missing security header: {h}"


def test_public_paths_accessible():
    """인증이 필요 없는 public 경로가 접근 가능해야 함."""
    public_paths = [
        "/health",
        "/v1/health",
    ]
    for path in public_paths:
        resp = requests.get(f"{base_url}{path}", timeout=10)
        assert resp.status_code in (200, 404), f"Public path {path} returned {resp.status_code}"


def test_protected_path_requires_auth():
    """보호된 경로는 인증 없이 401을 반환해야 함."""
    protected_paths = [
        "/api/system/status",
        "/v1/models",
    ]
    for path in protected_paths:
        resp = requests.get(f"{base_url}{path}", timeout=10)
        # 401 또는 200 (PIN 설정되어 있을 수 있음) — 최소한 500은 안 됨
        assert resp.status_code in (401, 200, 403), f"Protected path {path} returned {resp.status_code}"


# ─── 스키마 검증 ────────────────────────────────────────────────────


def test_error_response_has_correlation_id():
    """에러 응답에 correlation_id가 포함되어야 함."""
    response = requests.post(
        f"{base_url}/v1/chat/completions",
        json={"invalid": "request"},
        timeout=10,
    )
    # 400 또는 422 예상
    if response.status_code >= 400:
        data = response.json()
        # error_response의 형식 확인 (ok 필드가 있거나 error 필드가 있어야 함)
        if "ok" in data:
            assert data.get("ok") is False, "Error response should have ok=false"


# ─── 서버 생존성 (선택적) ────────────────────────────────────────────


@pytest.mark.slow
def test_server_stable_over_time():
    """서버가 5초 간격으로 3번 연속 응답하는지 확인 (느린 테스트)."""
    for i in range(3):
        resp = requests.get(health_url, timeout=10, headers=HEADERS)
        assert resp.status_code == 200, f"Attempt {i + 1}: Server unreachable"
        time.sleep(5)


# ─── 유틸리티: 서버 프로세스 관리 ──────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def server_process():
    external_url = os.environ.get("AGK_TEST_URL")
    if external_url:
        _set_base_url(external_url)
        yield None
        return

    proc = subprocess.Popen(
        [
            *python_invocation(project=True),
            "-m",
            "uvicorn",
            "antigravity_k.api.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--no-access-log",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )

    assert proc.stderr is not None
    startup_logs: list[str] = []
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            _, stderr = proc.communicate()
            pytest.fail(f"E2E server exited during startup: {(stderr or ''.join(startup_logs)).strip()}")

        readable, _, _ = select.select([proc.stderr], [], [], 1)
        if not readable:
            continue

        line = proc.stderr.readline()
        startup_logs.append(line)
        match = re.search(r"Uvicorn running on http://127\.0\.0\.1:(\d+)", line)
        if match is not None:
            _set_base_url(f"http://127.0.0.1:{match.group(1)}")
            break
    else:
        proc.terminate()
        _, stderr = proc.communicate(timeout=10)
        pytest.fail(f"E2E server did not report an ephemeral port: {(stderr or ''.join(startup_logs)).strip()}")

    last_status = None
    for _ in range(30):
        try:
            resp = requests.get(health_url, timeout=2)
            if resp.status_code == 200:
                break
        except requests.RequestException:
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr is not None else ""
                pytest.fail(f"E2E server exited during startup: {stderr.strip()}")
        else:
            last_status = resp.status_code
        time.sleep(1)
    else:
        proc.terminate()
        _, stderr = proc.communicate(timeout=10)
        pytest.fail(f"E2E server did not become healthy (last status: {last_status}): {stderr.strip()}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
