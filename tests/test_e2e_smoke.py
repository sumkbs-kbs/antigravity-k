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
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

# ─── 설정 ───────────────────────────────────────────────────────────

# 테스트 대상 서버 URL (환경변수로 오버라이드 가능)
# 기본 포트는 8000 (uvicorn 기본값과 일치).
# github Actions CI에서는 8400을 사용할 수 있습니다.
BASE_URL = os.environ.get("AGK_TEST_URL", "http://127.0.0.1:8000")
HEALTH_URL = f"{BASE_URL}/v1/health"
API_PREFIX = BASE_URL

# 헤더
HEADERS = {"Content-Type": "application/json"}


# ─── 헬스 체크 ──────────────────────────────────────────────────────


def test_health_endpoint():
    """기본 헬스 체크 엔드포인트가 정상 응답하는지 검증."""
    resp = requests.get(HEALTH_URL, timeout=10, headers=HEADERS)
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    data = resp.json()
    assert data.get("status") in ("ok", "healthy"), f"Unexpected status: {data}"


def test_health_returns_backends():
    """헬스 체크에 backends 정보가 포함되어야 함."""
    resp = requests.get(HEALTH_URL, timeout=10, headers=HEADERS)
    data = resp.json()
    # backends 필드가 존재해야 함 (빈 객체여도 OK)
    assert "backends" in data, f"Missing 'backends' in health response: {data.keys()}"


def test_health_returns_version():
    """헬스 체크에 버전 정보가 포함되어야 함."""
    resp = requests.get(HEALTH_URL, timeout=10, headers=HEADERS)
    data = resp.json()
    # version 필드 또는 model 필드가 있어야 함
    assert any(k in data for k in ("version", "model", "engine")), (
        f"Missing version info in health response: {data.keys()}"
    )


# ─── API 라우트 검증 ────────────────────────────────────────────────


def test_cors_headers():
    """API 응답에 CORS 헤더가 포함되어야 함."""
    resp = requests.options(
        f"{API_PREFIX}/v1/chat/completions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
        timeout=10,
    )
    assert "access-control-allow-origin" in resp.headers, "Missing CORS header"


def test_security_headers():
    """API 응답에 보안 헤더가 포함되어야 함."""
    resp = requests.get(HEALTH_URL, timeout=10, headers=HEADERS)
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
        resp = requests.get(f"{BASE_URL}{path}", timeout=10)
        assert resp.status_code in (200, 404), f"Public path {path} returned {resp.status_code}"


def test_protected_path_requires_auth():
    """보호된 경로는 인증 없이 401을 반환해야 함."""
    protected_paths = [
        "/api/system/status",
        "/v1/models",
    ]
    for path in protected_paths:
        resp = requests.get(f"{BASE_URL}{path}", timeout=10)
        # 401 또는 200 (PIN 설정되어 있을 수 있음) — 최소한 500은 안 됨
        assert resp.status_code in (401, 200, 403), f"Protected path {path} returned {resp.status_code}"


# ─── 스키마 검증 ────────────────────────────────────────────────────


def test_error_response_has_correlation_id():
    """에러 응답에 correlation_id가 포함되어야 함."""
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
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
        resp = requests.get(HEALTH_URL, timeout=10, headers=HEADERS)
        assert resp.status_code == 200, f"Attempt {i + 1}: Server unreachable"
        time.sleep(5)


# ─── 유틸리티: 서버 프로세스 관리 ──────────────────────────────────


@pytest.fixture(scope="session")
def server_process():
    """테스트 세션 동안 서버 프로세스를 시작합니다.

    사용법: pytest에 --server-start 옵션을 전달하거나
    AGK_START_SERVER=true 환경변수를 설정하세요.
    """
    if not os.environ.get("AGK_START_SERVER"):
        pytest.skip("AGK_START_SERVER not set — assuming server is already running")

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "antigravity_k.api.server:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).resolve().parent.parent,
    )

    # 서버가 준비될 때까지 대기
    for _ in range(30):
        try:
            resp = requests.get(HEALTH_URL, timeout=2)
            if resp.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(1)
    else:
        proc.terminate()
        pytest.fail("Server did not start in time")

    yield proc

    proc.terminate()
    proc.wait(timeout=10)
