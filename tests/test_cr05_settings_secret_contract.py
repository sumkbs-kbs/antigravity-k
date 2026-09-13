"""CR-05 — 설정 API의 비밀 계약 (계획 카드 CR-05).

발견 F01은 대시보드가 API 키를 localStorage에 원문 저장하던 문제(클라이언트 소관,
`dashboard/src/pages/SettingsPage.test.tsx` + e2e)이고, 이 파일은 그 **서버 절반**을
고정한다:

- GET은 키 원문/부분값 대신 provider별 `configured` 상태만 반환한다(C05-01/C05-04).
- POST는 누락=유지 / 빈 값=전송 안 함 / 새 값=교체, 삭제는 별도 명시 경로(C05-03).
- allowlist 밖 키, 개행 주입, 제어문자 값은 파일에 닿기 전에 거부된다(C05-03/C05-04).
- 저장은 원자적이고 결과 파일 권한이 0600이며, 응답/로그에 원문 canary가 없다(C05-04).
"""

from __future__ import annotations

import logging
import os
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import system_api
from antigravity_k.api.server import app
from antigravity_k.engine import secret_settings

CANARY = "cr05-canary-6f19ba-should-never-appear"
CANARY_LONG = "cr05-canary-b7d3e1-0123456789abcdef-should-never-appear"


@pytest.fixture()
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """서버 설정 API가 쓰는 `.env`/config 경로를 임시 디렉터리로 고정한다."""
    env_path = tmp_path / "isolated.env"
    monkeypatch.setattr(system_api, "_settings_project_root", lambda: str(tmp_path))
    # config 로더와 같은 규칙 — 실제 사용자 `.env`가 아니라 격리 파일을 쓴다.
    monkeypatch.setenv("AGK_ENV_FILE", str(env_path))
    yield env_path


@pytest.fixture()
def client(env_file: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """ALLOW 게이트 + 격리된 .env를 쓰는 실제 앱."""
    from antigravity_k.api import dependencies
    from antigravity_k.engine.model_manager import ModelManager

    manager = cast(Any, MagicMock(spec=ModelManager))
    manager.generate.return_value = "mock"
    manager.status.return_value = {"loaded_models": []}
    manager.router = MagicMock()

    app.dependency_overrides[dependencies.get_model_manager] = lambda: manager
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _write_env(env_file: Path, text: str) -> None:
    env_file.write_text(text, encoding="utf-8")


def _read_env(env_file: Path) -> str:
    return env_file.read_text(encoding="utf-8") if env_file.exists() else ""


# ── C05-04: GET은 원문/부분값을 노출하지 않는다 ────────────────────────────


class TestGetNeverLeaksKeyMaterial:
    def test_partial_key_values_are_not_returned(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", CANARY_LONG)
        monkeypatch.setenv("GEMINI_API_KEY", "ab")

        response = client.get("/api/settings")

        assert response.status_code == 200, response.text
        body = response.text
        # 원문도, 앞 4자/마스킹 형태도 응답 어디에도 없다.
        assert CANARY_LONG not in body
        assert CANARY_LONG[:4] not in body
        assert "****" not in body
        settings = response.json()["settings"]
        assert "api_keys" not in settings
        assert settings["api_keys_configured"]["OPENAI_API_KEY"] is True
        assert settings["api_keys_configured"]["GEMINI_API_KEY"] is True
        assert settings["api_keys_configured"]["ANTHROPIC_API_KEY"] is False

    def test_config_yaml_secret_paths_are_scrubbed(self, client: TestClient, env_file: Path, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text(
            "api_keys:\n  anthropic: real-secret-from-config\n"
            "security:\n  access_pin: 'cr05-pin-canary-9d2f'\n"
            "model:\n  api_engine: openrouter\n",
            encoding="utf-8",
        )

        response = client.get("/api/settings")

        assert response.status_code == 200, response.text
        text = response.text
        assert "real-secret-from-config" not in text
        assert "cr05-pin-canary-9d2f" not in text
        settings = response.json()["settings"]
        assert "api_keys" not in settings
        assert "access_pin" not in settings.get("security", {})

    def test_read_failure_returns_fixed_code_without_exception_text(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "config.yaml").write_text("model: {}\n", encoding="utf-8")

        def _boom(*_args: object, **_kwargs: object) -> Any:
            raise RuntimeError(f"internal path /Users/secret-place/{CANARY}")

        monkeypatch.setattr(system_api.yaml, "safe_load", _boom)

        response = client.get("/api/settings")

        assert response.status_code == 200, response.text
        assert CANARY not in response.text
        assert "/Users/secret-place" not in response.text
        assert response.json()["settings"] == {"error": "settings_unavailable"}


# ── C05-03: keep / replace / explicit-delete ─────────────────────────────


class TestKeepReplaceDeleteContract:
    def test_missing_key_is_kept_and_new_value_replaces(self, client: TestClient, env_file: Path) -> None:
        _write_env(env_file, "OPENAI_API_KEY=old-openai\nGEMINI_API_KEY=old-gemini\n# comment\n")

        response = client.post("/api/settings/env", json={"OPENAI_API_KEY": "new-openai"})

        assert response.status_code == 200, response.text
        assert response.json()["updated"] == 1
        text = _read_env(env_file)
        assert "OPENAI_API_KEY=new-openai" in text
        assert "GEMINI_API_KEY=old-gemini" in text
        assert "# comment" in text

    def test_empty_value_does_not_delete_existing_key(self, client: TestClient, env_file: Path) -> None:
        _write_env(env_file, "OPENAI_API_KEY=keep-me\n")
        before = _read_env(env_file)

        response = client.post("/api/settings/env", json={"OPENAI_API_KEY": ""})

        assert response.status_code == 200, response.text
        assert response.json()["updated"] == 0
        assert _read_env(env_file) == before

    def test_explicit_delete_removes_only_requested_keys(self, client: TestClient, env_file: Path) -> None:
        _write_env(
            env_file,
            "OPENAI_API_KEY=openai-secret\nGEMINI_API_KEY=gemini-secret\nAGK_DAILY_BUDGET_USD=50\n",
        )

        response = client.post("/api/settings/env/delete", json=["GEMINI_API_KEY"])

        assert response.status_code == 200, response.text
        assert response.json()["deleted"] == 1
        text = _read_env(env_file)
        assert "GEMINI_API_KEY" not in text
        assert "OPENAI_API_KEY=openai-secret" in text
        assert "AGK_DAILY_BUDGET_USD=50" in text

    def test_explicit_delete_is_idempotent_for_absent_key(self, client: TestClient, env_file: Path) -> None:
        _write_env(env_file, "OPENAI_API_KEY=openai-secret\n")

        first = client.post("/api/settings/env/delete", json=["GEMINI_API_KEY"])
        second = client.post("/api/settings/env/delete", json=["GEMINI_API_KEY"])

        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["deleted"] == 0
        assert second.json()["deleted"] == 0
        assert "OPENAI_API_KEY=openai-secret" in _read_env(env_file)

    def test_configured_status_tracks_save_and_delete(
        self, client: TestClient, env_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """설정 API가 쓴 상태를 같은 API가 즉시 보고한다(방금 저장한 키가 '미설정'으로 보이지 않는다)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        def status() -> Any:
            return client.get("/api/settings").json()["settings"]["api_keys_configured"]

        assert status()["OPENAI_API_KEY"] is False

        assert client.post("/api/settings/env", json={"OPENAI_API_KEY": CANARY}).status_code == 200
        assert status()["OPENAI_API_KEY"] is True

        assert client.post("/api/settings/env/delete", json=["OPENAI_API_KEY"]).status_code == 200
        assert status()["OPENAI_API_KEY"] is False

    def test_non_secret_preference_keys_are_allowed(self, client: TestClient, env_file: Path) -> None:
        response = client.post(
            "/api/settings/env",
            json={"AGK_DAILY_BUDGET_USD": "12.5", "AGK_HOURLY_ACTION_LIMIT": "7"},
        )

        assert response.status_code == 200, response.text
        text = _read_env(env_file)
        assert "AGK_DAILY_BUDGET_USD=12.5" in text
        assert "AGK_HOURLY_ACTION_LIMIT=7" in text


# ── C05-03/C05-04: 거부되는 입력 ──────────────────────────────────────────


class TestRejectedInputsStopBeforeFileWrite:
    @pytest.mark.parametrize(
        ("payload", "label"),
        [
            ({"EVIL_API_KEY": "x"}, "arbitrary *_API_KEY"),
            ({"AGK_SEC_ACCESS_PIN": "1234"}, "server PIN via settings"),
            ({"PATH": "/tmp"}, "non-allowlisted env"),
        ],
    )
    def test_non_allowlisted_keys_are_rejected(
        self, client: TestClient, env_file: Path, payload: dict[str, str], label: str
    ) -> None:
        _write_env(env_file, "OPENAI_API_KEY=untouched\n")
        before = _read_env(env_file)

        response = client.post("/api/settings/env", json=payload)

        assert response.status_code == 400, f"{label}: {response.text}"
        assert _read_env(env_file) == before

    def test_newline_injection_is_rejected(self, client: TestClient, env_file: Path) -> None:
        _write_env(env_file, "OPENAI_API_KEY=untouched\n")
        before = _read_env(env_file)

        response = client.post(
            "/api/settings/env",
            json={"OPENAI_API_KEY": f"{CANARY}\nAGK_SEC_ACCESS_PIN=1234"},
        )

        assert response.status_code == 400, response.text
        assert CANARY not in response.text
        assert _read_env(env_file) == before
        assert "AGK_SEC_ACCESS_PIN" not in _read_env(env_file)

    def test_deletion_of_non_allowlisted_key_is_rejected(self, client: TestClient, env_file: Path) -> None:
        _write_env(env_file, "AGK_SEC_ACCESS_PIN=1234\n")

        response = client.post("/api/settings/env/delete", json=["AGK_SEC_ACCESS_PIN"])

        assert response.status_code == 400, response.text
        assert "AGK_SEC_ACCESS_PIN=1234" in _read_env(env_file)


# ── C05-04: 저장 안전성·권한·로그 비노출 ─────────────────────────────────


class TestWriteSafetyAndLogHygiene:
    def test_saved_file_is_owner_only_and_leaves_no_tempfile(self, client: TestClient, env_file: Path) -> None:
        response = client.post("/api/settings/env", json={"OPENAI_API_KEY": CANARY})

        assert response.status_code == 200, response.text
        mode = stat.S_IMODE(os.stat(env_file).st_mode)
        assert mode == 0o600, oct(mode)
        leftovers = [p.name for p in env_file.parent.iterdir() if p.name.startswith(".env.")]
        assert leftovers == []

    def test_response_and_logs_never_contain_the_raw_value(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            response = client.post("/api/settings/env", json={"OPENAI_API_KEY": CANARY})

        assert response.status_code == 200, response.text
        assert CANARY not in response.text
        assert CANARY not in caplog.text
        # 응답에는 갱신 개수와 고정 메시지만 온다.
        assert response.json()["updated"] == 1

    def test_existing_file_survives_a_write_failure(
        self, client: TestClient, env_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_env(env_file, "OPENAI_API_KEY=keep-on-failure\n")

        def _explode(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(secret_settings, "write_env_file_atomic", _explode)

        with pytest.raises(OSError):
            client.post("/api/settings/env", json={"OPENAI_API_KEY": CANARY})

        assert _read_env(env_file) == "OPENAI_API_KEY=keep-on-failure\n"

    def test_permission_gate_is_checked_before_any_write(
        self, client: TestClient, env_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from antigravity_k.tools.tool_contracts import Permission

        _write_env(env_file, "OPENAI_API_KEY=untouched\n")
        before = _read_env(env_file)
        gate = cast(Any, MagicMock())
        gate.decide.return_value = type("Decision", (), {"permission": Permission.DENY, "reason": "test-deny"})()
        monkeypatch.setattr(system_api, "_permission_gate", lambda: gate)

        response = client.post("/api/settings/env", json={"OPENAI_API_KEY": CANARY})

        assert response.status_code == 403
        assert _read_env(env_file) == before
        assert gate.decide.call_count == 1
        (invocation,) = gate.decide.call_args.args
        # 감사 인자에는 키 이름만 온다(값 금지).
        assert CANARY not in str(invocation)

    def test_write_honors_agk_env_file_and_never_touches_project_root_dotenv(
        self, client: TestClient, env_file: Path, tmp_path: Path
    ) -> None:
        """격리 경로(AGK_ENV_FILE)가 있으면 그 파일에만 쓴다 — 테스트는 사용자 .env를 건드리지 않는다."""
        root_env = tmp_path / ".env"
        root_env.write_text("OPENAI_API_KEY=root-owned-value\n", encoding="utf-8")

        response = client.post("/api/settings/env", json={"OPENAI_API_KEY": CANARY})

        assert response.status_code == 200, response.text
        assert f"OPENAI_API_KEY={CANARY}" in _read_env(env_file)
        assert root_env.read_text(encoding="utf-8") == "OPENAI_API_KEY=root-owned-value\n"

    def test_comment_lines_and_order_are_preserved(self, client: TestClient, env_file: Path) -> None:
        _write_env(
            env_file,
            "# provider keys\nOPENAI_API_KEY=old\n\n# budget\nAGK_DAILY_BUDGET_USD=10\n",
        )

        response = client.post("/api/settings/env", json={"OPENAI_API_KEY": "new"})

        assert response.status_code == 200
        lines = _read_env(env_file).splitlines()
        assert lines[0] == "# provider keys"
        assert lines[1] == "OPENAI_API_KEY=new"
        assert lines[2] == ""
        assert lines[3] == "# budget"
        assert lines[4] == "AGK_DAILY_BUDGET_USD=10"
