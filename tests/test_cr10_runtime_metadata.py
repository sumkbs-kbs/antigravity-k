"""CR-10 운영 지표와 빌드 신뢰성 계약 (F06).

정적/실측 결함
--------------
`SystemTelemetricsBar.tsx`가 BUILD `v0.8.0-RC`, UPTIME `14D 08H 12M`을 하드코딩했고,
`/api/system/status`는 wall clock 기반 uptime만 주고 프로세스 식별자·빌드 provenance가
없었다. 그래서 화면은 실제 값을 알 수 없었고 서버 재시작과 호스트 가동 시간을 구분하지
못했다.

고정하는 계약
-------------
- C10-02: UPTIME은 **현재 API 프로세스**의 가동 시간이고 monotonic 경과를 쓴다.
          프로세스가 재시작되면 0에서 다시 시작한다. 벽시계 변경에 영향받지 않는다.
- C10-03: 프로세스 식별자(process_id)로 다중 worker를 구분할 수 있다.
- C10-04: 메모리는 percent 의미가 정직한 키(memory_percent)로도 노출된다.
- C10-05: 실행 중인 빌드의 provenance(version/build_id/built_at/channel)를 API가 보고하며,
          기록되지 않은 값은 추측하지 않고 None이다.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Protocol, cast, final

import psutil
import pytest
from fastapi.testclient import TestClient

from antigravity_k import __version__
from antigravity_k.api.routes import system_api
from antigravity_k.api.server import app
from antigravity_k.build_info import (
    ENV_BUILD_CHANNEL,
    ENV_BUILD_ID,
    ENV_BUILT_AT,
    get_build_info,
)
from antigravity_k.config import config

JsonObject = dict[str, object]


class ResponseLike(Protocol):
    status_code: int

    def json(self) -> object: ...


def _json(response: ResponseLike) -> JsonObject:
    value = response.json()
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object, got {type(value).__name__}")
    return cast(JsonObject, value)


@final
class _Clock:
    """`system_api`가 보는 시계를 고정해 monotonic/wall clock을 분리한다."""

    def __init__(self, monotonic: float, wall: float) -> None:
        self._monotonic = monotonic
        self._wall = wall

    def monotonic(self) -> float:
        return self._monotonic

    def time(self) -> float:
        return self._wall


@pytest.fixture
def client() -> Iterator[TestClient]:
    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        yield test_client


# ─── C10-05: 빌드 provenance ─────────────────────────────────────


class TestBuildProvenance:
    def test_unrecorded_values_are_none_not_guesses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in (ENV_BUILD_ID, ENV_BUILT_AT, ENV_BUILD_CHANNEL):
            monkeypatch.delenv(name, raising=False)

        info = get_build_info()

        assert info["version"] == __version__
        assert info["build_id"] is None
        assert info["built_at"] is None
        assert info["channel"] is None

    def test_blank_env_is_treated_as_unrecorded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_BUILD_ID, "   ")
        monkeypatch.setenv(ENV_BUILT_AT, "")

        info = get_build_info()

        assert info["build_id"] is None
        assert info["built_at"] is None

    def test_recorded_values_are_reported_verbatim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_BUILD_ID, " 0badc0de ")
        monkeypatch.setenv(ENV_BUILT_AT, "2026-09-12T00:00:00+00:00")
        monkeypatch.setenv(ENV_BUILD_CHANNEL, "rc")

        info = get_build_info()

        assert info["build_id"] == "0badc0de"
        assert info["built_at"] == "2026-09-12T00:00:00+00:00"
        assert info["channel"] == "rc"

    def test_health_reports_build(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_BUILD_ID, "cafebabe")

        body = _json(client.get("/health"))

        build = body["build"]
        assert isinstance(build, dict)
        assert cast(JsonObject, build)["version"] == __version__
        assert cast(JsonObject, build)["build_id"] == "cafebabe"


# ─── C10-02/C10-03/C10-04: /api/system/status ────────────────────


class TestSystemStatusRuntimeMetadata:
    def test_process_id_identifies_the_responding_process(self, client: TestClient) -> None:
        body = _json(client.get("/api/system/status"))

        assert body["process_id"] == os.getpid()
        assert system_api.PROCESS_ID == os.getpid()

    def test_uptime_uses_monotonic_elapsed_not_wall_clock(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 벽시계는 1970년, monotonic은 1000초로 고정한다. 프로세스는 50초 전에 시작했다.
        monkeypatch.setattr(system_api, "time", _Clock(monotonic=1000.0, wall=1.0))
        monkeypatch.setattr(system_api, "START_TIME", 950.0)

        body = _json(client.get("/api/system/status"))

        # 벽시계 차이(1.0초)가 아니라 monotonic 경과(50초)가 나와야 한다.
        assert body["uptime_seconds"] == 50

    def test_restart_resets_uptime_to_zero(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        # 프로세스가 방금 시작했다고 가정 — 호스트 uptime과 무관하게 0이다.
        monkeypatch.setattr(system_api, "START_TIME", time.monotonic())

        assert _json(client.get("/api/system/status"))["uptime_seconds"] == 0

    def test_uptime_is_never_negative(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        # 시계가 뒤로 가도 음수 uptime을 내보내지 않는다.
        monkeypatch.setattr(system_api, "time", _Clock(monotonic=100.0, wall=100.0))
        monkeypatch.setattr(system_api, "START_TIME", 200.0)

        assert _json(client.get("/api/system/status"))["uptime_seconds"] == 0

    def test_uptime_started_at_is_iso8601_utc(self, client: TestClient) -> None:
        body = _json(client.get("/api/system/status"))

        started_at = cast(str, body["uptime_started_at"])
        parsed = datetime.fromisoformat(started_at)

        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)
        assert body["uptime_seconds"] is not None

    def test_memory_is_exposed_with_honest_percent_key(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(percent=41.5))

        body = _json(client.get("/api/system/status"))

        # legacy 키(memory_mb)는 실제로 percent다. 정직한 키를 함께 제공한다.
        assert body["memory_mb"] == 41.5
        assert body["memory_percent"] == 41.5

    def test_version_matches_package_version(self, client: TestClient) -> None:
        body = _json(client.get("/api/system/status"))

        assert body["version"] == __version__
        build = cast(JsonObject, body["build"])
        assert build["version"] == __version__
