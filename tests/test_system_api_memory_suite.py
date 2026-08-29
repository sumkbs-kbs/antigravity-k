"""테스트: System API — 세션/메모리/툴셋/하니스 스위트.
============================================
DI 게터를 패치해 각 엔드포인트의 계약(응답 구조, 감사 로그, 400 검증,
클램프)을 외부 의존 없이 검증한다.
"""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import system_api
from antigravity_k.api.server import app


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
    mm.get_stats.return_value = {"episodic": 3}
    mm.prefetch_all.return_value = ["fact-a"]
    mm.clear.return_value = {"deleted": 5}
    mm.export.return_value = {"items": [1, 2]}
    mm.redact.return_value = {"changed": 2}
    mm.apply_retention.return_value = {"deleted": 7}
    mm.delete_entry.return_value = True
    fact = SimpleNamespace(
        key="db_engine",
        value="postgresql",
        source="user",
        scope="project",
        authority=2,
        observed_at="2026-08-25",
    )
    mm.ranked_facts.return_value = [(fact, 0.91)]
    for name, value in overrides.items():
        setattr(mm, name, value)
    return mm


# ─── Session ─────────────────────────────────────────────────────


class TestSessionEndpoints:
    def test_session_info_empty_when_none(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(system_api, "_get_session_manager", lambda: SimpleNamespace(get_session_info=lambda: None))

        body = client.get("/api/session/info").json()

        assert body == {"ok": True, "session": {}}

    def test_session_save_ok(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        saved = {}
        sm = SimpleNamespace(save=lambda: saved.update(ok=True))
        monkeypatch.setattr(system_api, "_get_session_manager", lambda: sm)

        assert client.post("/api/session/save").json() == {
            "ok": True,
            "message": "Session saved.",
        }
        assert saved["ok"] is True

    def test_session_messages_normalizes_shapes(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
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

        body = client.get("/api/session/messages").json()

        assert body["messages"][0] == {"role": "user", "content": "c"}
        assert body["messages"][1] == {"role": "assistant", "content": "dict"}
        assert body["messages"][2] == {"value": "raw-string"}


# ─── Memory suite ────────────────────────────────────────────────


class TestMemorySuite:
    def test_stats_and_recall(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        calls: dict[str, str] = {}

        def fake_prefetch(query: str):
            calls["q"] = query
            return ["fact-a"]

        mm = _memory_manager(prefetch_all=fake_prefetch)
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: mm)

        assert client.get("/api/memory/stats").json() == {"memory": {"episodic": 3}}
        body = client.get("/api/memory/recall", params={"query": "DB"}).json()
        assert body["recalled"] == ["fact-a"] and body["query"] == "DB"
        assert calls["q"] == "DB"

    def test_purge_logs_audit_event(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock):
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        body = client.request("DELETE", "/api/memory", json={"scope": "project"}).json()

        assert body["ok"] is True and body["scope"] == "project"
        assert audit_spy.log_event.call_args.args[0] == "memory_purge"

    def test_purge_invalid_scope_is_400(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock):
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        response = client.request("DELETE", "/api/memory", json={"scope": "galaxy"})

        assert response.status_code == 400

    def test_export_excludes_vault_by_default(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock):
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())
        monkeypatch.setattr(system_api, "get_vault_engine", lambda: None, raising=False)

        body = client.get("/api/memory/export").json()

        assert body["vault"] == {"included": False, "asset_policy": "excluded_by_default"}

    def test_redact_reports_changed(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock):
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        body = client.post("/api/memory/redact", json={"scope": "all"}).json()

        assert body == {"ok": True, "scope": "all", "changed": {"changed": 2}}

    @pytest.mark.parametrize("payload", [{"max_age_days": True}, {"max_age_days": -1}, {"max_age_days": "3"}])
    def test_retention_rejects_invalid_ages(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, payload: dict[str, object], audit_spy: MagicMock):
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        assert client.post("/api/memory/retention", json=payload).status_code == 400

    def test_retention_valid_path_audits(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock):
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: _memory_manager())

        body = client.post("/api/memory/retention", json={"max_age_days": 30}).json()

        assert body["ok"] is True and body["max_age_days"] == 30
        assert audit_spy.log_event.call_args.args[0] == "memory_retention"

    def test_ranked_facts_maps_fields_and_clamps_top_k(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        captured: dict[str, int] = {}
        mm = _memory_manager()
        mm.ranked_facts = lambda top_k: (
            captured.__setitem__("top_k", top_k)
            or [
                (
                    SimpleNamespace(
                        key="k",
                        value="v",
                        source="user",
                        scope="project",
                        authority=2,
                        observed_at="t",
                    ),
                    0.906,
                )
            ]
        )
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: mm)

        body = client.get("/api/memory/ranked", params={"top_k": 500}).json()

        assert captured["top_k"] == 100  # 상한 클램프
        assert body["facts"][0]["score"] == 0.91
        assert body["facts"][0]["authority"] == 2

    def test_delete_entry_reports_result(self, client: TestClient, monkeypatch: pytest.MonkeyPatch, audit_spy: MagicMock):
        mm = _memory_manager(delete_entry=lambda provider, key: key == "keep")
        monkeypatch.setattr(system_api, "_get_memory_manager", lambda: mm)

        hit = client.request("DELETE", "/api/memory/entries", params={"provider": "project", "key": "keep"}).json()
        miss = client.request("DELETE", "/api/memory/entries", params={"provider": "project", "key": "drop"}).json()

        assert hit["deleted"] is True
        assert miss["deleted"] is False
        assert audit_spy.log_event.call_args.args[0] == "memory_entry_delete"


# ─── Toolsets ────────────────────────────────────────────────────


class TestToolsetEndpoints:
    def _toolset_manager(self):
        ts = SimpleNamespace(
            list_toolsets=lambda: ["full", "minimal"],
            active_toolset="full",
            set_active=lambda name: name == "minimal",
            get_active_tools=lambda: ["read_file"],
            resolve=lambda name: ["read_file", "edit_file"] if name == "full" else [],
        )
        return ts

    def test_list_toolsets(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(system_api, "_get_toolset_manager", self._toolset_manager)

        body = client.get("/api/toolsets").json()

        assert body["active"] == "full"
        assert "minimal" in body["toolsets"]

    def test_activate_success_and_failure(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(system_api, "_get_toolset_manager", self._toolset_manager)

        ok = client.post("/api/toolsets/activate", json={"name": "minimal"}).json()
        fail = client.post("/api/toolsets/activate", json={"name": "ghost"}).json()

        assert ok["success"] is True and ok["tools"] == ["read_file"]
        assert fail["success"] is False and fail["tools"] == []

    def test_toolset_tools_count(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(system_api, "_get_toolset_manager", self._toolset_manager)

        body = client.get("/api/toolsets/full/tools").json()

        assert body["count"] == 2


# ─── Harness ─────────────────────────────────────────────────────


class TestHarnessEndpoints:
    def test_self_test_runs_without_browser_for_api_scope(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        harness = SimpleNamespace(run_all=AsyncMock(return_value=SimpleNamespace(to_dict=lambda: {"passed": 3})))
        monkeypatch.setattr(system_api, "get_harness", lambda: harness)

        body = client.post("/api/harness/self-test", json={"scope": "api_only"}).json()

        assert body["ok"] is True and body["report"]["passed"] == 3
        harness.run_all.assert_called_once_with(use_browser=False)

    def test_results_message_when_never_run(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        harness = SimpleNamespace(get_latest_report=lambda: None, feedback=SimpleNamespace(get_trend=lambda: []))
        monkeypatch.setattr(system_api, "get_harness", lambda: harness)

        body = client.get("/api/harness/results").json()

        assert body["report"] is None and "아직" in body["message"]

    def test_trend_passthrough(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        harness = SimpleNamespace(feedback=SimpleNamespace(get_trend=lambda: [{"pass_rate": 1.0}]))
        monkeypatch.setattr(system_api, "get_harness", lambda: harness)

        assert client.get("/api/harness/trend").json()["trend"] == [{"pass_rate": 1.0}]


# ─── Mode history ────────────────────────────────────────────────


class TestModeHistory:
    def test_history_mapping(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        mgr = SimpleNamespace(
            mode_history=[SimpleNamespace(from_mode="plan", to_mode="build", reason="r", timestamp=1)]
        )

        import antigravity_k.api.dependencies as deps

        monkeypatch.setattr(deps, "get_mode_manager", lambda: mgr)

        body = client.get("/api/system/mode/history").json()

        assert body["ok"] is True
        assert body["history"] == [{"from": "plan", "to": "build", "reason": "r", "timestamp": 1}]

    def test_failure_returns_ok_false_with_empty_history(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        import antigravity_k.api.dependencies as deps

        def boom():
            raise RuntimeError("mode down")

        monkeypatch.setattr(deps, "get_mode_manager", boom)

        body = client.get("/api/system/mode/history").json()

        assert body["ok"] is False and body["history"] == []
