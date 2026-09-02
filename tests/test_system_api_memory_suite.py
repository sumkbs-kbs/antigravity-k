"""테스트: System API — 세션/메모리/툴셋/하니스 스위트.
============================================
DI 게터를 패치해 각 엔드포인트의 계약(응답 구조, 감사 로그, 400 검증,
클램프)을 외부 의존 없이 검증한다.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Protocol, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import system_api
from antigravity_k.api.server import app

JsonObject = dict[str, object]


class ResponseLike(Protocol):
    status_code: int

    def json(self) -> object: ...


def _json(response: ResponseLike) -> JsonObject:
    value = response.json()
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object, got {type(value).__name__}")
    return cast(JsonObject, value)


def _as_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise AssertionError(f"expected object, got {type(value).__name__}")
    return cast(JsonObject, value)


def _mock_method(mock: object, name: str) -> MagicMock:
    return cast(MagicMock, getattr(mock, name))


def _set_return(mock: MagicMock, name: str, value: object) -> None:
    _mock_method(mock, name).return_value = value


@pytest.fixture
def client() -> Iterator[TestClient]:
    from antigravity_k.config import config

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        yield test_client


@pytest.fixture
def audit_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    spy = MagicMock()
    monkeypatch.setattr(system_api, "get_audit_logger", lambda: spy)
    return spy


def _memory_manager(**overrides: object) -> MagicMock:
    mm = MagicMock()
    _set_return(mm, "get_stats", {"episodic": 3})
    _set_return(mm, "prefetch_all", ["fact-a"])
    _set_return(mm, "clear", {"deleted": 5})
    _set_return(mm, "export", {"items": [1, 2]})
    _set_return(mm, "redact", {"changed": 2})
    _set_return(mm, "apply_retention", {"deleted": 7})
    _set_return(mm, "delete_entry", True)
    fact = SimpleNamespace(
        key="db_engine",
        value="postgresql",
        source="user",
        scope="project",
        authority=2,
        observed_at="2026-08-25",
    )
    _set_return(mm, "ranked_facts", [(fact, 0.91)])
    for name, value in overrides.items():
        setattr(mm, name, value)
    return mm


# ─── Session ─────────────────────────────────────────────────────


class TestSessionEndpoints:
    def test_session_info_empty_when_none(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(system_api, "_get_session_manager", lambda: SimpleNamespace(get_session_info=lambda: None))

        body = _json(client.get("/api/session/info"))

        assert body == {"ok": True, "session": {}}

    def test_session_save_ok(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        saved: dict[str, bool] = {}
        sm = SimpleNamespace(save=lambda: saved.update(ok=True))
        monkeypatch.setattr(system_api, "_get_session_manager", lambda: sm)

        assert _json(client.post("/api/session/save")) == {
            "ok": True,
            "message": "Session saved.",
        }
        assert saved["ok"] is True

    def test_session_messages_normalizes_shapes(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        class Msg:
            def to_simple_dict(self) -> dict[str, str]:
                return {"role": "user", "content": "c"}

        sm = SimpleNamespace(
            start_session=lambda resume=True: None,
            get_messages=lambda: [
                Msg(),
                {"role": "assistant", "content": "dict"},
                "raw-string",
            ],
        )
        monkeypatch.setattr(system_api, "_get_session_manager", lambda: sm)

        body = _json(client.get("/api/session/messages"))
        messages = cast(list[JsonObject], body["messages"])

        assert messages[0] == {"role": "user", "content": "c"}
        assert messages[1] == {"role": "assistant", "content": "dict"}
        assert messages[2] == {"value": "raw-string"}


# ─── Memory suite ────────────────────────────────────────────────


class TestMemorySuite:
    def test_stats_and_recall(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: dict[str, str] = {}

        def fake_prefetch(query: str):
            calls["q"] = query
            return ["fact-a"]

        mm = _memory_manager(prefetch_all=fake_prefetch)
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: mm)

        assert _json(client.get("/api/memory/stats")) == {"memory": {"episodic": 3}}
        body = _json(client.get("/api/memory/recall", params={"query": "DB"}))
        assert body["recalled"] == ["fact-a"] and body["query"] == "DB"
        assert calls["q"] == "DB"

    def test_purge_logs_audit_event(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock
    ) -> None:
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        body = _json(client.request("DELETE", "/api/memory", json={"scope": "project"}))

        assert body["ok"] is True and body["scope"] == "project"
        assert _mock_method(audit_spy, "log_event").call_args.args[0] == "memory_purge"

    def test_purge_invalid_scope_is_400(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock
    ) -> None:
        del audit_spy
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        response = client.request("DELETE", "/api/memory", json={"scope": "galaxy"})

        assert response.status_code == 400

    def test_export_excludes_vault_by_default(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock
    ) -> None:
        del audit_spy
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())
        monkeypatch.setattr(system_api, "get_vault_engine", lambda: None, raising=False)

        body = _json(client.get("/api/memory/export"))

        assert body["vault"] == {"included": False, "asset_policy": "excluded_by_default"}

    def test_redact_reports_changed(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock
    ) -> None:
        del audit_spy
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        body = _json(client.post("/api/memory/redact", json={"scope": "all"}))

        assert body == {"ok": True, "scope": "all", "changed": {"changed": 2}}

    @pytest.mark.parametrize("payload", [{"max_age_days": True}, {"max_age_days": -1}, {"max_age_days": "3"}])
    def test_retention_rejects_invalid_ages(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        payload: dict[str, object],
        audit_spy: MagicMock,
    ) -> None:
        del audit_spy
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        assert client.post("/api/memory/retention", json=payload).status_code == 400

    def test_retention_valid_path_audits(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock
    ) -> None:
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        body = _json(client.post("/api/memory/retention", json={"max_age_days": 30}))

        assert body["ok"] is True and body["max_age_days"] == 30
        assert _mock_method(audit_spy, "log_event").call_args.args[0] == "memory_retention"

    def test_retention_rejects_malformed_json(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock
    ) -> None:
        del audit_spy
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        response = client.post(
            "/api/memory/retention",
            content=b"{",
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 400

    def test_ranked_facts_maps_fields_and_clamps_top_k(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, int] = {}
        mm = _memory_manager()

        def ranked_facts(top_k: int) -> list[tuple[SimpleNamespace, float]]:
            captured["top_k"] = top_k
            return [
                (
                    SimpleNamespace(key="k", value="v", source="user", scope="project", authority=2, observed_at="t"),
                    0.906,
                )
            ]

        setattr(mm, "ranked_facts", ranked_facts)
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: mm)

        body = _json(client.get("/api/memory/ranked", params={"top_k": 500}))
        facts = cast(list[JsonObject], body["facts"])

        assert captured["top_k"] == 100  # 상한 클램프
        assert facts[0]["score"] == 0.91
        assert facts[0]["authority"] == 2

    def test_delete_entry_reports_result(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock
    ) -> None:
        def delete_entry(_provider: str, key: str) -> bool:
            return key == "keep"

        mm = _memory_manager(delete_entry=delete_entry)
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: mm)

        hit = _json(client.request("DELETE", "/api/memory/entries", params={"provider": "project", "key": "keep"}))
        miss = _json(client.request("DELETE", "/api/memory/entries", params={"provider": "project", "key": "drop"}))

        assert hit["deleted"] is True
        assert miss["deleted"] is False
        assert _mock_method(audit_spy, "log_event").call_args.args[0] == "memory_entry_delete"


# ─── Toolsets ────────────────────────────────────────────────────


class TestToolsetEndpoints:
    def _toolset_manager(self) -> SimpleNamespace:
        def set_active(name: str) -> bool:
            return name == "minimal"

        def resolve(name: str) -> list[str]:
            return ["read_file", "edit_file"] if name == "full" else []

        ts = SimpleNamespace(
            list_toolsets=lambda: ["full", "minimal"],
            active_toolset="full",
            set_active=set_active,
            get_active_tools=lambda: ["read_file"],
            resolve=resolve,
        )
        return ts

    def test_list_toolsets(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(system_api, "_get_toolset_manager", self._toolset_manager)

        body = _json(client.get("/api/toolsets"))

        assert body["active"] == "full"
        assert "minimal" in cast(list[str], body["toolsets"])

    def test_activate_success_and_failure(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(system_api, "_get_toolset_manager", self._toolset_manager)

        ok = _json(client.post("/api/toolsets/activate", json={"name": "minimal"}))
        fail = _json(client.post("/api/toolsets/activate", json={"name": "ghost"}))

        assert ok["success"] is True and ok["tools"] == ["read_file"]
        assert fail["success"] is False and fail["tools"] == []

    def test_activate_rejects_non_string_name(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(system_api, "_get_toolset_manager", self._toolset_manager)

        response = client.post("/api/toolsets/activate", json={"name": 123})

        assert response.status_code == 422

    def test_toolset_tools_count(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(system_api, "_get_toolset_manager", self._toolset_manager)

        body = _json(client.get("/api/toolsets/full/tools"))

        assert body["count"] == 2


# ─── Harness ─────────────────────────────────────────────────────


class TestHarnessEndpoints:
    def test_self_test_runs_without_browser_for_api_scope(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = SimpleNamespace(run_all=AsyncMock(return_value=SimpleNamespace(to_dict=lambda: {"passed": 3})))
        monkeypatch.setattr(system_api, "get_harness", lambda: harness)

        body = _json(client.post("/api/harness/self-test", json={"scope": "api_only"}))
        report = _as_object(body["report"])

        assert body["ok"] is True and report["passed"] == 3
        _mock_method(harness, "run_all").assert_called_once_with(use_browser=False)

    def test_results_message_when_never_run(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        def get_trend() -> list[JsonObject]:
            return []

        harness = SimpleNamespace(get_latest_report=lambda: None, feedback=SimpleNamespace(get_trend=get_trend))
        monkeypatch.setattr(system_api, "get_harness", lambda: harness)

        body = _json(client.get("/api/harness/results"))

        assert body["report"] is None and "아직" in cast(str, body["message"])

    def test_trend_passthrough(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        harness = SimpleNamespace(feedback=SimpleNamespace(get_trend=lambda: [{"pass_rate": 1.0}]))
        monkeypatch.setattr(system_api, "get_harness", lambda: harness)

        body = _json(client.get("/api/harness/trend"))
        assert body["trend"] == [{"pass_rate": 1.0}]


# ─── Mode history ────────────────────────────────────────────────


class TestModeHistory:
    def test_history_mapping(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr = SimpleNamespace(
            mode_history=[SimpleNamespace(from_mode="plan", to_mode="build", reason="r", timestamp=1)]
        )

        import antigravity_k.api.dependencies as deps

        monkeypatch.setattr(deps, "get_mode_manager", lambda: mgr)

        body = _json(client.get("/api/system/mode/history"))

        assert body["ok"] is True
        assert body["history"] == [{"from": "plan", "to": "build", "reason": "r", "timestamp": 1}]

    def test_failure_returns_ok_false_with_empty_history(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import antigravity_k.api.dependencies as deps

        def boom() -> None:
            raise RuntimeError("mode down")

        monkeypatch.setattr(deps, "get_mode_manager", boom)

        body = _json(client.get("/api/system/mode/history"))

        assert body["ok"] is False and body["history"] == []


class TestModeSwitch:
    def test_rejects_non_string_mode(self, client: TestClient) -> None:
        response = client.post("/api/system/mode", json={"mode": 123})

        assert response.status_code == 400

    def test_unknown_mode_preserves_error_contract(self, client: TestClient) -> None:
        body = _json(client.post("/api/system/mode", json={"mode": "paused"}))

        assert body["ok"] is False
        assert "알 수 없는 모드" in cast(str, body["error"])

    def test_switches_mode_with_reason(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr = SimpleNamespace(
            current_mode=SimpleNamespace(value="plan"),
            switch_to_plan=MagicMock(),
            switch_to_build=MagicMock(),
            switch_to_interactive=MagicMock(),
        )
        import antigravity_k.api.dependencies as deps

        monkeypatch.setattr(deps, "get_mode_manager", lambda: mgr)

        body = _json(client.post("/api/system/mode", json={"mode": "plan", "reason": "test"}))

        assert body == {
            "ok": True,
            "mode": "plan",
            "message": "모드가 plan(으)로 전환되었습니다.",
        }
        _mock_method(mgr, "switch_to_plan").assert_called_once_with(reason="test")


class TestLogLevelEndpoints:
    def test_set_rejects_non_string_logger_name(self, client: TestClient) -> None:
        response = client.post("/api/system/log-level", json={"name": 123, "level": "INFO"})

        assert response.status_code == 400

    def test_set_rejects_boolean_level(self, client: TestClient) -> None:
        response = client.post("/api/system/log-level", json={"name": "antigravity_k.test", "level": True})

        assert response.status_code == 400

    def test_set_all_rejects_non_numeric_level(self, client: TestClient) -> None:
        response = client.post("/api/system/log-level/all", json={"level": 1.5})

        assert response.status_code == 400


class TestDebugModeEndpoint:
    def test_rejects_non_string_action(self, client: TestClient) -> None:
        response = client.post("/api/system/debug-mode", json={"action": 123})

        assert response.status_code == 400

    def test_unknown_action_preserves_error_contract(self, client: TestClient) -> None:
        body = _json(client.post("/api/system/debug-mode", json={"action": "pause"}))

        assert body == {"ok": False, "error": "action must be 'enable' or 'disable'"}


class TestCodeIntelEndpoints:
    def test_index_rejects_non_string_repo_path(self, client: TestClient) -> None:
        response = client.post("/api/code-intel/index", json={"repo_path": 123})

        assert response.status_code == 400

    def test_index_rejects_non_boolean_force(self, client: TestClient) -> None:
        response = client.post("/api/code-intel/index", json={"force": 1})

        assert response.status_code == 400

    def test_impact_rejects_non_string_symbol_id(self, client: TestClient) -> None:
        response = client.post("/api/code-intel/impact", json={"symbol_id": 123})

        assert response.status_code == 400

    def test_impact_rejects_boolean_max_depth(self, client: TestClient) -> None:
        response = client.post("/api/code-intel/impact", json={"max_depth": True})

        assert response.status_code == 400


class TestShieldsDownEndpoint:
    def test_rejects_non_integer_timeout(self, client: TestClient) -> None:
        response = client.post("/api/shields/down", json={"timeout_seconds": "30"})

        assert response.status_code == 400

    def test_rejects_non_string_target_toolset(self, client: TestClient) -> None:
        response = client.post("/api/shields/down", json={"target_toolset": 123})

        assert response.status_code == 400

    def test_rejects_non_string_reason(self, client: TestClient) -> None:
        response = client.post("/api/shields/down", json={"reason": 123})

        assert response.status_code == 400


class TestStripConfigEndpoint:
    def test_rejects_non_object_payload(self, client: TestClient) -> None:
        response = client.post("/api/security/strip-config", json=[])

        assert response.status_code == 400

    def test_preserves_json_config_values(self, client: TestClient) -> None:
        body = _json(
            client.post(
                "/api/security/strip-config",
                json={"config": {"port": 8080, "nested": [True, "value"]}},
            )
        )
        sanitized = _as_object(body["sanitized"])

        assert sanitized["port"] == 8080
        assert sanitized["nested"] == [True, "value"]

    def test_strips_credential_fields(self, client: TestClient) -> None:
        body = _json(
            client.post(
                "/api/security/strip-config",
                json={"config": {"api_key": "qa-secret"}},
            )
        )
        sanitized = _as_object(body["sanitized"])

        assert sanitized["api_key"] == "[STRIPPED_BY_SCANNER]"


class TestSecurityScanEndpoint:
    def test_rejects_non_object_payload(self, client: TestClient) -> None:
        response = client.post("/api/security/scan", json=[])

        assert response.status_code == 400

    def test_rejects_non_string_text(self, client: TestClient) -> None:
        response = client.post("/api/security/scan", json={"text": 123})

        assert response.status_code == 400

    def test_rejects_unknown_redact_mode(self, client: TestClient) -> None:
        response = client.post("/api/security/scan", json={"text": "safe", "redact_mode": "unknown"})

        assert response.status_code == 400

    def test_honors_full_redaction_mode(self, client: TestClient) -> None:
        body = _json(
            client.post(
                "/api/security/scan",
                json={"text": "API_KEY=sk-somethinglong123", "redact_mode": "full"},
            )
        )

        assert cast(int, body["secrets_found"]) >= 1
        redacted_text = cast(str, body["redacted_text"])
        assert "sk-somethinglong123" not in redacted_text
        assert "<REDACTED>" in redacted_text


class TestSearchInputEndpoints:
    def test_search_extract_rejects_non_object_payload(self, client: TestClient) -> None:
        response = client.post("/api/search/extract", json=[])

        assert response.status_code == 400

    def test_search_extract_rejects_non_string_query(self, client: TestClient) -> None:
        response = client.post("/api/search/extract", json={"query": 123})

        assert response.status_code == 400

    def test_ab_test_rejects_non_object_payload(self, client: TestClient) -> None:
        response = client.post("/api/search/ab-test/run", json=[])

        assert response.status_code == 400

    def test_ab_test_rejects_non_string_version_label(self, client: TestClient) -> None:
        response = client.post("/api/search/ab-test/run", json={"version_label": 123})

        assert response.status_code == 400


class TestInlineSuggestInput:
    def test_rejects_non_object_payload(self, client: TestClient) -> None:
        response = client.post("/api/code/inline-suggest", json=[])

        assert response.status_code == 400

    def test_rejects_invalid_cursor_line(self, client: TestClient) -> None:
        response = client.post(
            "/api/code/inline-suggest",
            json={"original_code": "x = 1", "instruction": "rename x", "cursor_line": 0},
        )

        assert response.status_code == 400

    def test_preserves_empty_instruction_contract(self, client: TestClient) -> None:
        body = _json(client.post("/api/code/inline-suggest", json={"original_code": "x = 1"}))

        assert body == {"ok": False, "error": "Instruction is required."}


class TestDeepHealthEndpoint:
    def test_uses_model_manager_loaded_names_contract(self) -> None:
        from antigravity_k.engine.runtime_recovery import deep_health_check

        health = deep_health_check(
            model_manager=SimpleNamespace(loaded_names=lambda: ["local-model"]),
            session_manager=SimpleNamespace(get_session_info=lambda: {}),
            memory_manager=SimpleNamespace(get_stats=lambda: {}),
            toolset_manager=SimpleNamespace(get_active_tools=lambda: ["tool"]),
        )

        model_component = next(
            component for component in health.components if component.name == "model_manager"
        )
        assert model_component.status.value == "healthy"

    def test_returns_health_payload_without_runtime_name_error(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from antigravity_k.engine import runtime_recovery

        health = SimpleNamespace(
            status=SimpleNamespace(value="healthy"),
            components=[],
            diagnosis="ok",
            checked_at="2026-08-30T00:00:00Z",
        )
        monkeypatch.setattr(runtime_recovery, "deep_health_check", lambda **_: health)
        monkeypatch.setattr(system_api, "get_model_manager", lambda: object())
        monkeypatch.setattr(system_api, "_get_session_manager", lambda: object())
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: object())
        monkeypatch.setattr(system_api, "_get_toolset_manager", lambda: object())
        monkeypatch.setattr(system_api, "_get_shields_manager", lambda: object())

        response = client.get("/api/health/deep")

        assert response.status_code == 200
        assert _json(response)["status"] == "healthy"
