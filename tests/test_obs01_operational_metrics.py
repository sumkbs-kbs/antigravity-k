"""OBS-01 테스트 — 운영 관측·readiness·correlation.

GA-100 plan §OBS-01 수용기준:
  AC-1  구조화 로그에서 한 operation의 project/task/tool/model 흐름을 추적할 수 있다.
  AC-2  핵심 운영 metric(compaction/auth lockout/registry write/vault commit/
        task terminal conflict/provider failure)이 계열별 outcome으로 기록된다.
  AC-3  readiness가 DB, registry, writable storage, model/provider 필수 조건을
        반영한다 (ready/degraded/not_ready + 503/200 계약).
  AC-4  correlation ID 미들웨어가 요청 시작/종료를 구조화 로그로 남긴다.

도메인 metric은 프로세스 전역 prometheus registry를 쓰므로 각 테스트는
고유한 outcome/시나리오 조합을 사용하거나 상대 증가만 검증한다.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.contracts.execution_context import RequestExecutionContext
from antigravity_k.api.error_handler import correlation_id_var
from antigravity_k.api.project_binding import (
    reset_bound_request_execution_context,
    set_bound_request_execution_context,
)
from antigravity_k.engine import operational_metrics as om

# ---------------------------------------------------------------------------
# AC-2 — 도메인 metric
# ---------------------------------------------------------------------------


def test_domain_counters_snapshot_and_increment() -> None:
    before = om.snapshot_domain_counters()

    om.record_compaction("success")
    om.record_auth_event("lockout")
    om.record_registry_write("save_error")
    om.record_vault_commit("commit_error")
    om.record_task_transition_conflict("conflict")
    om.record_provider_failure("timeout")

    after = om.snapshot_domain_counters()
    assert (
        after["ssak_context_compactions_total"].get("success", 0)
        == before["ssak_context_compactions_total"].get("success", 0) + 1
    )
    assert after["ssak_auth_events_total"].get("lockout", 0) >= 1
    assert after["ssak_registry_writes_total"].get("save_error", 0) >= 1
    assert after["ssak_vault_commits_total"].get("commit_error", 0) >= 1
    assert after["ssak_task_transition_conflicts_total"].get("conflict", 0) >= 1
    assert after["ssak_provider_failures_total"].get("timeout", 0) >= 1


def test_domain_counters_render_in_prometheus_exposition() -> None:
    om.record_compaction("degraded")
    from antigravity_k.engine.metrics import render_metrics

    body = render_metrics().decode()
    assert "ssak_context_compactions_total" in body
    assert 'outcome="degraded"' in body


def test_conversation_compaction_records_metric(tmp_path: Any) -> None:
    """실제 conversation_store.compact() 호출이 metric을 올린다 (연동)."""
    from antigravity_k.engine.conversation_store import ConversationStore

    before = om.snapshot_domain_counters()["ssak_context_compactions_total"].get("success", 0)

    store = ConversationStore(storage_dir=tmp_path)
    store.get_or_create(project_id="obs-proj", conversation_id="obs-conv")
    for i in range(6):
        store.append(
            project_id="obs-proj",
            conversation_id="obs-conv",
            expected_revision=i,
            role="user",
            content=f"m{i}",
        )
    store.compact(project_id="obs-proj", conversation_id="obs-conv", expected_revision=6, retain_tail=2)

    after = om.snapshot_domain_counters()["ssak_context_compactions_total"].get("success", 0)
    assert after >= before + 1


def test_task_transition_conflict_records_metric(tmp_path: Any) -> None:
    """실제 TaskStateStore CAS 충돌이 metric을 올린다 (연동)."""
    from antigravity_k.engine.task_state_store import TaskStateStore
    from antigravity_k.engine.task_state_types import TaskTransitionConflictError

    before = om.snapshot_domain_counters()["ssak_task_transition_conflicts_total"].get("conflict", 0)

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.initialize()
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    store.create_task(task_id, prompt="obs", status="running", created_at="2026-09-09T00:00:00Z")
    # stale expected_status CAS → 매칭 실패 → TaskTransitionConflictError (conflict metric)
    with pytest.raises(TaskTransitionConflictError):
        store.transition(task_id, "done", expected_status="paused")

    after = om.snapshot_domain_counters()["ssak_task_transition_conflicts_total"].get("conflict", 0)
    assert after >= before + 1


def test_task_invalid_status_records_rejected_metric(tmp_path: Any) -> None:
    """허용 전이 밖 상태 거절이 rejected metric을 올린다."""
    from antigravity_k.engine.task_state_store import TaskStateStore
    from antigravity_k.engine.task_state_types import InvalidTaskStatusError

    before = om.snapshot_domain_counters()["ssak_task_transition_conflicts_total"].get("rejected", 0)

    store = TaskStateStore(str(tmp_path / "tasks-reject.db"))
    store.initialize()
    with pytest.raises(InvalidTaskStatusError):
        store.transition(f"task-{uuid.uuid4().hex[:8]}", "bogus-status")  # type: ignore[arg-value]

    after = om.snapshot_domain_counters()["ssak_task_transition_conflicts_total"].get("rejected", 0)
    assert after >= before + 1


# ---------------------------------------------------------------------------
# AC-1 — operation correlation 로그
# ---------------------------------------------------------------------------


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.formatted: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.formatted.append(record.getMessage())


@pytest.fixture()
def json_capture() -> list[dict[str, Any]]:
    """JSONFormatter가 장착된 antigravity_k.ops 캡처를 제공하고 복구한다."""
    import io

    from antigravity_k.engine.logger import JSONFormatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter(source="obs-test"))
    lg = logging.getLogger("antigravity_k.ops")
    old_level = lg.level
    lg.addHandler(handler)
    lg.setLevel(logging.INFO)
    yield stream  # type: ignore[misc]
    lg.removeHandler(handler)
    lg.setLevel(old_level)


def test_operation_log_includes_correlation_and_bound_context(json_capture: Any) -> None:
    token = correlation_id_var.set("cid-obs-1")
    ctx = RequestExecutionContext(
        request_id="req-obs-1",
        project_id="proj-obs",
        canonical_project_root="/tmp/obs-proj",
        conversation_id="conv-obs",
        conversation_revision=3,
        actor_subject="actor-obs",
        session_id="sess-obs",
        model_id="model-obs",
        task_id="task-obs-9",
    )
    bound = set_bound_request_execution_context(ctx)
    try:
        om.log_operation_event("tool.invoked", tool="search", status=200)
    finally:
        reset_bound_request_execution_context(bound)
        correlation_id_var.reset(token)

    parsed = json.loads(json_capture.getvalue().strip().splitlines()[-1])
    assert parsed["event"] == "tool.invoked"
    assert parsed["correlation_id"] == "cid-obs-1"
    assert parsed["project_id"] == "proj-obs"
    assert parsed["task_id"] == "task-obs-9"
    assert parsed["conversation_id"] == "conv-obs"
    assert parsed["session_id"] == "sess-obs"
    assert parsed["model_id"] == "model-obs"
    assert parsed["tool"] == "search"


def test_operation_log_without_context_is_safe(json_capture: Any) -> None:
    om.log_operation_event("standalone.event", outcome="error", error_code="boom")
    parsed = json.loads(json_capture.getvalue().strip().splitlines()[-1])
    assert parsed["event"] == "standalone.event"
    assert parsed["outcome"] == "error"
    assert parsed["error_code"] == "boom"
    assert parsed["project_id"] is None


# ---------------------------------------------------------------------------
# AC-3 — readiness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    from antigravity_k.api.server import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_readiness_endpoint_public_and_200(client: TestClient) -> None:
    resp = client.get("/api/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ready", "degraded", "not_ready")
    names = {c["name"] for c in body["checks"]}
    assert names == {"task_db", "registry", "writable_storage", "model_manager"}
    for check in body["checks"]:
        assert check["status"] in ("ready", "degraded", "not_ready")
        assert check["detail"]


def test_readiness_contract_not_ready_is_503(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """task_db 검사가 실패하면 not_ready + 503이어야 한다."""
    from antigravity_k.engine import operational_metrics as om_mod

    def _broken() -> tuple[str, str]:
        raise RuntimeError("db exploded")

    monkeypatch.setattr(om_mod, "_check_task_db", _broken)
    resp = client.get("/api/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    task_check = next(c for c in body["checks"] if c["name"] == "task_db")
    assert "RuntimeError" in task_check["detail"]


def test_compute_readiness_individual_check_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """한 검사의 크래시가 다른 검사를 오염하지 않는다."""

    def _boom() -> tuple[str, str]:
        raise RuntimeError("boom")

    monkeypatch.setattr(om, "_check_registry", _boom)
    report = om.compute_readiness()
    by_name = {c["name"]: c["status"] for c in report["checks"]}
    assert by_name["registry"] == "not_ready"
    assert by_name["task_db"] in ("ready", "degraded", "not_ready")
    assert by_name["writable_storage"] in ("ready", "degraded", "not_ready")
    assert report["status"] == "not_ready"


# ---------------------------------------------------------------------------
# AC-4 — correlation 미들웨어 요청 로그
# ---------------------------------------------------------------------------


def test_middleware_logs_request_lifecycle(client: TestClient, json_capture: Any) -> None:
    cid = f"obs-{uuid.uuid4().hex[:8]}"
    resp = client.get("/health", headers={"X-Request-Id": cid})
    assert resp.status_code == 200
    assert resp.headers["X-Request-Id"] == cid

    lines = [json.loads(ln) for ln in json_capture.getvalue().splitlines() if ln.strip()]
    started = [ln for ln in lines if ln.get("event") == "http.request.started"]
    completed = [ln for ln in lines if ln.get("event") == "http.request.completed"]
    assert started and completed
    assert all(ln["correlation_id"] == cid for ln in started + completed)
    done = completed[-1]
    assert done["path"] == "/health"
    assert done["status"] == 200
    assert "duration_ms" in done
