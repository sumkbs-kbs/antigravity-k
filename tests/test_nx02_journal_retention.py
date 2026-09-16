"""NX-02 후속: journal retention/quota 결정과 집행(ADR-DAT-02 Context 8).

결정의 핵심은 **무엇을 하지 않는가**다 — 조용한 prune 은 ADR 이 금지하므로 자동 삭제를 넣지
않는다. 대신 한계를 byte 로 명시하고, 넘으면 **쓰기를 거절**하며(507), 기존 데이터는 그대로
둔다. 이 시험이 그 계약을 고정한다:

* 정책 기본값/경계/환경변수(포함: `0` = 그 단계 비활성, 잘못된 값은 기본값),
* hard cap 초과 시 append 거절 — 저널 byte·revision·이력이 **변하지 않는다**(손실 0),
* 한계를 올리면 다시 쓸 수 있다(회복 경로),
* soft cap 경고는 대화당 **한 번**이고 쓰기는 계속된다,
* `store_usage()` 가 전체/개별 사용량을 보고한다(O(대화 수) 스캔은 요청 시에만),
* 새 오류 코드가 wire 계약(Python 맵 + dashboard 스키마 + 두 fixture)에 **동시에** 있다,
* HTTP 표면에서 507 과 코드가 실제로 보인다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from antigravity_k.api.contracts.errors import (
    CONTEXT_ERROR_HTTP_STATUS,
    ConversationHistoryQuotaExceededError,
    execution_context_error_from_code,
)
from antigravity_k.api.routes import conversation_api
from antigravity_k.engine.conversation_journal import JOURNAL_SUFFIX
from antigravity_k.engine.conversation_retention import (
    DEFAULT_HARD_CAP_MB,
    DEFAULT_SOFT_CAP_MB,
    HARD_CAP_ENV,
    SOFT_CAP_ENV,
    JournalRetentionPolicy,
    format_mb,
    resolve_policy,
)
from antigravity_k.engine.conversation_store import (
    ConversationStore,
    conversation_storage_relative_path,
    reset_conversation_store_for_tests,
)
from antigravity_k.engine.project_registry import ProjectRegistry

PROJECT = "p"
CONV = "conv"
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (
    REPO_ROOT / "tests" / "fixtures" / "commercial_ga" / "arc01_request_execution_context.json",
    REPO_ROOT / "dashboard" / "src" / "api" / "fixtures" / "arc01_request_execution_context.json",
)
DASHBOARD_SCHEMA = REPO_ROOT / "dashboard" / "src" / "api" / "clientSchema.ts"


def _store(tmp_path: Path) -> ConversationStore:
    return ConversationStore(storage_dir=tmp_path / "conversations")


def _append(store: ConversationStore, revision: int, content: str = "turn") -> int:
    snap = store.append(
        project_id=PROJECT,
        conversation_id=CONV,
        expected_revision=revision,
        role="user",
        content=content,
    )
    return int(snap.revision)


def _journal_bytes(store: ConversationStore) -> int:
    path = store.journal_path(project_id=PROJECT, conversation_id=CONV)
    return path.stat().st_size if path.is_file() else 0


def _set_caps(monkeypatch: pytest.MonkeyPatch, *, soft_mb: float | None, hard_mb: float | None) -> None:
    for env_name, value in ((SOFT_CAP_ENV, soft_mb), (HARD_CAP_ENV, hard_mb)):
        if value is None:
            monkeypatch.delenv(env_name, raising=False)
        else:
            monkeypatch.setenv(env_name, f"{value:.6f}")


# ── 정책 ────────────────────────────────────────────────────────────────


def test_policy_defaults_and_verdict_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SOFT_CAP_ENV, raising=False)
    monkeypatch.delenv(HARD_CAP_ENV, raising=False)
    policy = resolve_policy()

    assert policy.soft_cap_bytes == int(DEFAULT_SOFT_CAP_MB * 1024 * 1024)
    assert policy.hard_cap_bytes == int(DEFAULT_HARD_CAP_MB * 1024 * 1024)
    assert policy.enforced is True
    assert policy.verdict(0) == "ok"
    assert policy.verdict(policy.soft_cap_bytes - 1) == "ok"
    assert policy.verdict(policy.soft_cap_bytes) == "soft_exceeded"
    assert policy.verdict(policy.hard_cap_bytes) == "hard_exceeded"
    assert policy.to_dict() == {
        "soft_cap_bytes": policy.soft_cap_bytes,
        "hard_cap_bytes": policy.hard_cap_bytes,
        "enforced": True,
    }


def test_policy_env_override_invalid_values_and_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SOFT_CAP_ENV, "1.5")
    monkeypatch.setenv(HARD_CAP_ENV, "3")
    policy = resolve_policy()
    assert policy.soft_cap_bytes == int(1.5 * 1024 * 1024)
    assert policy.hard_cap_bytes == 3 * 1024 * 1024
    assert policy.verdict(policy.soft_cap_bytes) == "soft_exceeded"
    assert policy.verdict(policy.hard_cap_bytes) == "hard_exceeded"

    # 잘못된 값/음수는 기본값으로 돌아간다(경고만 남기고 조용히 이상 동작하지 않는다).
    for bad in ("", "   ", "abc", "-1"):
        monkeypatch.setenv(HARD_CAP_ENV, bad)
        assert resolve_policy().hard_cap_bytes == int(DEFAULT_HARD_CAP_MB * 1024 * 1024)

    # `0` = 그 단계 비활성. hard 가 꺼지면 거절하지 않는다.
    monkeypatch.setenv(SOFT_CAP_ENV, "0")
    monkeypatch.setenv(HARD_CAP_ENV, "0")
    disabled = resolve_policy()
    assert disabled.enforced is False
    assert disabled.verdict(10**12) == "ok"

    # hard < soft 역전: 거절(hard)이 이긴다 — 설정 실수가 안전 측으로 기운다.
    reversed_policy = JournalRetentionPolicy(soft_cap_bytes=1000, hard_cap_bytes=10)
    assert reversed_policy.verdict(11) == "hard_exceeded"


def test_format_mb_is_used_for_messages() -> None:
    assert format_mb(1024 * 1024) == "1.00 MB"
    assert format_mb(0) == "0.00 MB"


# ── 집행: hard cap 은 쓰기를 거절하고 데이터를 건드리지 않는다 ─────────────


def test_hard_cap_refuses_append_without_touching_existing_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SOFT_CAP_ENV, raising=False)
    monkeypatch.delenv(HARD_CAP_ENV, raising=False)
    store = _store(tmp_path)

    assert _append(store, 0, "turn-0") == 1
    assert _append(store, 1, "turn-1") == 2
    size_before = _journal_bytes(store)
    assert size_before > 0
    history_before = store.original_history(project_id=PROJECT, conversation_id=CONV)

    # 지금 크기를 hard cap 으로 삼는다(다음 append 는 반드시 거절돼야 한다).
    _set_caps(monkeypatch, soft_mb=size_before / (2 * 1024 * 1024), hard_mb=size_before / (1024 * 1024))

    with pytest.raises(ConversationHistoryQuotaExceededError) as excinfo:
        _append(store, 2, "turn-2")

    error = excinfo.value
    assert error.status_code == 507
    assert error.error_code == "conversation_history_quota_exceeded"
    assert error.context["journal_bytes"] == size_before
    # env 는 MB 단위 실수라 정수 byte 와 1 byte 이내에서만 같다(반올림 비유일).
    assert abs(int(error.context["hard_cap_bytes"]) - size_before) <= 1
    assert "nothing was deleted" in str(error.context["remedy"])

    # 손실 0: 저널 byte·revision·이력이 그대로다.
    assert _journal_bytes(store) == size_before
    assert store.get_revision(project_id=PROJECT, conversation_id=CONV) == 2
    assert store.original_history(project_id=PROJECT, conversation_id=CONV) == history_before
    assert [message["content"] for message in store.original_history(project_id=PROJECT, conversation_id=CONV)][
        -1
    ] == "turn-1"

    # 회복 경로: 한계를 올리면 다시 쓸 수 있다.
    _set_caps(monkeypatch, soft_mb=None, hard_mb=None)
    assert _append(store, 2, "turn-2") == 3
    assert _journal_bytes(store) > size_before


def test_disabled_caps_never_refuse_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_caps(monkeypatch, soft_mb=0, hard_mb=0)
    store = _store(tmp_path)
    for revision in range(5):
        assert _append(store, revision, "turn" * 40) == revision + 1


def test_soft_cap_warns_once_per_conversation_and_keeps_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    store = _store(tmp_path)
    assert _append(store, 0, "turn-0") == 1
    size = _journal_bytes(store)

    # soft 만 낮춘다 — hard 는 손대지 않으니 거절되면 안 된다.
    _set_caps(monkeypatch, soft_mb=size / (2 * 1024 * 1024), hard_mb=DEFAULT_HARD_CAP_MB)

    with caplog.at_level(logging.WARNING, logger="antigravity_k.engine.conversation_store"):
        assert _append(store, 1, "turn-1") == 2
        assert _append(store, 2, "turn-2") == 3

    warnings = [record for record in caplog.records if "above soft cap" in record.getMessage()]
    assert len(warnings) == 1, [record.getMessage() for record in caplog.records]
    message = warnings[0].getMessage()
    assert f"project={PROJECT}" in message
    assert f"conversation={CONV}" in message
    assert "no automatic pruning" in message
    assert _journal_bytes(store) > size


# ── 관측 ────────────────────────────────────────────────────────────────


def test_store_usage_reports_totals_and_largest_journals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SOFT_CAP_ENV, raising=False)
    monkeypatch.delenv(HARD_CAP_ENV, raising=False)
    store = _store(tmp_path)
    _append(store, 0, "short")
    store.append(
        project_id=PROJECT,
        conversation_id="conv_big",
        expected_revision=0,
        role="user",
        content="x" * 2000,
    )

    usage = store.store_usage()
    assert usage["storage_dir"] == str(tmp_path / "conversations")
    assert usage["journal_count"] == 2
    assert usage["total_bytes"] > 2000
    largest = usage["largest_journals"]
    assert isinstance(largest, list) and len(largest) == 2
    assert largest[0]["bytes"] >= largest[1]["bytes"]
    assert str(largest[0]["path"]).endswith(JOURNAL_SUFFIX)

    # hard cap 을 넘긴 대화를 운영자가 바로 찾을 수 있어야 한다.
    _set_caps(monkeypatch, soft_mb=0.0005, hard_mb=0.001)
    over = store.store_usage()
    assert over["journals_over_hard_cap"] >= 1
    # soft 는 hard 를 포함한다(같거나 많다) — 큰 쪽 journal 이 먼저 걸린다.
    assert over["journals_over_soft_cap"] >= over["journals_over_hard_cap"] >= 1
    assert over["policy"]["hard_cap_bytes"] == int(0.001 * 1024 * 1024)


# ── wire 계약 ───────────────────────────────────────────────────────────


def test_quota_error_code_is_frozen_in_the_wire_contract() -> None:
    assert CONTEXT_ERROR_HTTP_STATUS["conversation_history_quota_exceeded"] == 507

    error = execution_context_error_from_code("conversation_history_quota_exceeded")
    assert isinstance(error, ConversationHistoryQuotaExceededError)
    assert error.status_code == 507
    assert error.error_code == "conversation_history_quota_exceeded"

    for fixture in FIXTURES:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        assert payload["error_http_status"]["conversation_history_quota_exceeded"] == 507, fixture

    schema = DASHBOARD_SCHEMA.read_text(encoding="utf-8")
    assert '"conversation_history_quota_exceeded"' in schema
    assert "conversation_history_quota_exceeded: 507" in schema


def test_append_over_http_reports_507_with_the_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """사용자에게 보이는 표면: 한계 초과는 507 + 안정된 코드로 온다."""

    fresh = ConversationStore(storage_dir=tmp_path / "conversations")
    reset_conversation_store_for_tests(fresh)

    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    root = tmp_path / "proj"
    root.mkdir()
    record = registry.add_project(name="NX02", path=str(root))
    monkeypatch.setattr("antigravity_k.api.project_binding.get_project_registry", lambda: registry)
    monkeypatch.setattr("antigravity_k.engine.request_execution_context.get_project_registry", lambda: registry)
    monkeypatch.setenv("AGK_ALLOWED_ROOTS", str(tmp_path.resolve()))

    app = FastAPI()
    from antigravity_k.api.error_handler import APIError, global_exception_handler

    app.add_exception_handler(APIError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(conversation_api.router)
    client = TestClient(app, raise_server_exceptions=False)

    body = {
        "project_id": record.id,
        "conversation_id": "conv_quota",
        "expected_revision": 0,
        "role": "user",
        "content": "turn",
    }
    first = client.post("/v1/conversations/append", json=body)
    assert first.status_code == 200, first.text

    journal = (
        tmp_path
        / "conversations"
        / conversation_storage_relative_path(record.id, "conv_quota").with_suffix(JOURNAL_SUFFIX)
    )
    size = journal.stat().st_size
    monkeypatch.delenv(SOFT_CAP_ENV, raising=False)
    monkeypatch.setenv(HARD_CAP_ENV, f"{size / (1024 * 1024):.6f}")

    second = client.post("/v1/conversations/append", json={**body, "expected_revision": 1})
    assert second.status_code == 507, second.text
    payload = second.json()
    assert payload["error"] == "conversation_history_quota_exceeded"
    assert payload["ok"] is False
    assert "nothing was deleted" in str(payload["remedy"])
    # 거절은 데이터 손실이 아니다 — 이력은 그대로 읽힌다.
    assert journal.stat().st_size == size
    history = client.get(f"/v1/conversations/conv_quota/history?project_id={record.id}")
    assert history.status_code == 200, history.text
