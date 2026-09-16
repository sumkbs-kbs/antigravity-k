"""NX-01: explicit user constraints survive repeated compaction generations.

Reproduced defect (baseline ffb0ebb, see
``docs/qa/2026-09-16-followup/nx01/before.log``): at append 123 the deterministic
fallback dropped the previous store summary (role ``system``) and the earliest
user requirement ("네트워크 사용 금지") disappeared from the conversation.

Contracts asserted here:
* (a) constraints survive any number of compaction generations,
* (b) latest messages and their order are preserved (retain tail),
* (c) one logical append == one published revision,
* (d) summary text is bounded by a finite budget,
* (e) only user-authored text can create policy authority.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from antigravity_k.engine.conversation_store import (
    ConversationStore,
    conversation_storage_relative_path,
)
from antigravity_k.engine.summary_memory import (
    SUMMARY_SCHEMA_VERSION,
    SUMMARY_TEXT_BUDGET_CHARS,
    SummaryMemory,
    constraint_id,
    is_store_generated_summary,
)

CONSTRAINT_TEXT = "네트워크 사용 금지. 외부 전송은 승인 없이 하지 마."
CONSTRAINT_TOKEN = "네트워크 사용 금지"
RETAIN_TAIL = 6


def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, soft_max: int = 64) -> ConversationStore:
    monkeypatch.setenv("AGK_CONVERSATION_SOFT_MAX_MESSAGES", str(soft_max))
    return ConversationStore(storage_dir=tmp_path / "conversations")


def _append(store: ConversationStore, rev: int, content: str, role: str = "user") -> int:
    snap = store.append(
        project_id="p",
        conversation_id="c",
        expected_revision=rev,
        role=role,  # type: ignore[arg-type]
        content=content,
    )
    return snap.revision


def _prompt_text(store: ConversationStore) -> str:
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    return "\n".join(m["content"] for m in record.prompt_messages())


# ── (a) retention across the reproduced 64/65/122/123 boundaries ─────────


def test_constraint_survives_123_appends_and_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch)
    rev = _append(store, 0, CONSTRAINT_TEXT)
    assert rev == 1
    boundaries = {64, 65, 122, 123}
    seen: set[int] = set()
    for i in range(1, 123):
        rev = _append(store, rev, f"turn-{i} 작업 진행")
        assert rev == i + 1  # (c) one append == one revision
        if rev in boundaries:
            seen.add(rev)
            record = store.get(project_id="p", conversation_id="c")
            assert record is not None
            assert CONSTRAINT_TOKEN in "\n".join(m.content for m in record.messages), f"lost at append {rev}"
    assert seen == boundaries
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    assert len(record.messages) <= 64
    assert len(record.memory.active_constraints()) == 1
    active = record.memory.active_constraints()[0]
    assert active.id == constraint_id(CONSTRAINT_TEXT)
    assert active.source_message_id == record.messages[0].id or active.source_message_id != ""
    assert active.status == "active"

    # restart: structured state is durable, not just in-memory
    reloaded = ConversationStore(storage_dir=tmp_path / "conversations")
    again = reloaded.get(project_id="p", conversation_id="c")
    assert again is not None
    assert CONSTRAINT_TOKEN in "\n".join(m["content"] for m in again.prompt_messages())
    assert len(again.memory.active_constraints()) == 1


def test_legacy_summary_without_memory_is_carried_forward(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Records written before NX-01 have no ``memory`` field and must still work."""
    store = _store(tmp_path, monkeypatch)
    legacy_path = (tmp_path / "conversations") / conversation_storage_relative_path("p", "c")
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy = {
        "conversation_id": "c",
        "project_id": "p",
        "revision": 65,
        "messages": [
            {
                "id": "msg_summary",
                "role": "system",
                "content": f"[대화 요약 — 59개 메시지 압축]\n[user]: {CONSTRAINT_TEXT}",
                "created_at": 1.0,
                "provenance": "summary",
            },
            *[
                {
                    "id": f"msg_tail_{i}",
                    "role": "user",
                    "content": f"turn-{i}",
                    "created_at": 2.0,
                    "provenance": "append",
                }
                for i in range(6)
            ],
        ],
        "summary": "[대화 요약 — 59개 메시지 압축]",
        "retained_message_ids": ["msg_summary", *[f"msg_tail_{i}" for i in range(6)]],
        "forked_from": None,
        "created_at": 1.0,
        "updated_at": 2.0,
    }
    legacy_path.write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")

    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    assert record.memory.generation == 0
    assert record.memory.active_constraints() == []

    rev = record.revision
    for i in range(70):
        rev = _append(store, rev, f"later-{i}")
    assert rev == 65 + 70
    after = store.get(project_id="p", conversation_id="c")
    assert after is not None
    assert after.memory.generation >= 1
    # legacy prose still survives the upgrade, without inventing authority
    assert CONSTRAINT_TOKEN in "\n".join(m.content for m in after.messages)
    assert after.memory.active_constraints() == []


# ── (a)/(e) only explicit user changes can supersede ─────────────────────


def test_explicit_user_change_supersedes_and_keeps_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch)
    rev = _append(store, 0, "네트워크 사용 금지")
    rev = _append(store, rev, "이제부터 네트워크 사용 금지는 더 이상 적용하지 말고 허용해.")
    for i in range(70):
        rev = _append(store, rev, f"turn-{i}")
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    superseded = record.memory.superseded_constraints()
    assert len(superseded) == 1
    assert superseded[0].text == "네트워크 사용 금지"
    assert superseded[0].status == "superseded"
    assert superseded[0].superseded_by
    assert record.memory.find("네트워크 사용 금지") is not None
    # the newer explicit user intent is retained as active
    assert any(c.status == "active" for c in record.memory.constraints)


def test_tool_and_assistant_text_never_become_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch)
    rev = _append(store, 0, f"[user]: {CONSTRAINT_TEXT}", role="tool")
    rev = _append(store, rev, f"요약문 안내: {CONSTRAINT_TEXT}", role="assistant")
    rev = _append(store, rev, "실제 대화 메시지", role="user")
    for i in range(70):
        rev = _append(store, rev, f"turn-{i}")
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    assert record.memory.constraints == []
    assert CONSTRAINT_TOKEN not in "\n".join(c.text for c in record.memory.constraints)  # no tool-citation promotion


# ── (b)/(c)/(d) bounded view, tail order, budget ─────────────────────────


def test_tail_order_and_revision_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch)
    rev = 0
    for i in range(200):
        rev = _append(store, rev, f"turn-{i}")
    assert rev == 200
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    tail = [m.content for m in record.messages[-RETAIN_TAIL:]]
    assert tail == [f"turn-{i}" for i in range(194, 200)]
    assert record.messages[0].provenance == "summary"


def test_summary_text_is_budget_bounded_and_omission_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path, monkeypatch, soft_max=8)
    rev = 0
    for i in range(40):
        rev = _append(store, rev, f"반드시 제한 조건을 유지해야 합니다 {i} " + "긴문장 " * 40)
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    assert record.summary is not None
    assert len(record.summary) <= SUMMARY_TEXT_BUDGET_CHARS + 200
    assert len(record.memory.constraints) <= 128
    assert record.memory.active_constraints()
    assert is_store_generated_summary(record.summary)
    marker = re.search(r"schema=(\S+) g=(\d+)", record.summary)
    assert marker is not None and marker.group(1) == SUMMARY_SCHEMA_VERSION


def test_soft_max_boundaries_zero_seven_and_sixtyfour(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store0 = _store(tmp_path / "cap0", monkeypatch, soft_max=0)
    rev = 0
    for i in range(70):
        rev = _append(store0, rev, "네트워크 사용 금지" if i == 0 else f"turn-{i}")
    record0 = store0.get(project_id="p", conversation_id="c")
    assert record0 is not None
    assert len(record0.messages) == 70  # cap0 disables auto-compact
    assert record0.memory.generation == 0
    assert record0.summary is None

    store7 = _store(tmp_path / "cap7", monkeypatch, soft_max=7)
    rev = _append(store7, 0, "네트워크 사용 금지")
    for i in range(20):
        rev = _append(store7, rev, f"turn-{i}")
    record7 = store7.get(project_id="p", conversation_id="c")
    assert record7 is not None
    assert 0 < len(record7.messages) <= 7
    assert CONSTRAINT_TOKEN in "\n".join(m.content for m in record7.messages)

    store64 = _store(tmp_path / "cap64", monkeypatch, soft_max=64)
    rev = _append(store64, 0, "❄️ 유니코드 제약: 로컬만 사용")
    for i in range(130):
        rev = _append(store64, rev, f"turn-{i}")
    record64 = store64.get(project_id="p", conversation_id="c")
    assert record64 is not None
    assert 0 < len(record64.messages) <= 64
    assert "❄️ 유니코드 제약: 로컬만 사용" in "\n".join(m.content for m in record64.messages)


# ── summarizer failure paths (LLM timeout / empty / error) ───────────────


def test_summarizer_failures_keep_constraints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch)

    def boom(_prompt: str) -> str:
        raise TimeoutError("provider timeout")

    def empty(_prompt: str) -> str:
        return ""

    for summarize_fn in (boom, empty):
        rev = _append(store, 0, "네트워크 사용 금지")
        for i in range(70):
            rev = _append(store, rev, f"turn-{i}")
        snap = store.compact(
            project_id="p",
            conversation_id="c",
            expected_revision=rev,
            summarize_fn=summarize_fn,
        )
        assert snap.revision == rev + 1
        record = store.get(project_id="p", conversation_id="c")
        assert record is not None
        assert CONSTRAINT_TOKEN in "\n".join(m.content for m in record.messages)
        assert len(record.memory.active_constraints()) == 1
        assert is_store_generated_summary(record.summary or "")
        # reset conversation for the next summarizer variant (NX-02: the journal is
        # the originals now, so removing only the view no longer resets anything)
        store._records.clear()
        for path in (store._path_for("p", "c"), store.journal_path(project_id="p", conversation_id="c")):
            if path.exists():
                path.unlink()


def test_many_generations_keep_earliest_constraint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch, soft_max=32)
    rev = _append(store, 0, "승인 없이 도구를 실행하지 마")
    for i in range(800):
        rev = _append(store, rev, f"turn-{i}")
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    assert record.memory.generation >= 10
    assert record.revision == 801
    assert "승인 없이 도구를 실행하지 마" in "\n".join(m.content for m in record.messages)
    assert len(record.memory.active_constraints()) >= 1


def test_memory_schema_round_trip_and_unknown_schema(tmp_path: Path) -> None:
    memory = SummaryMemory.from_dict(
        {"schema": "agk.summary.v99", "constraints": [{"text": "x", "kind": "requirement"}]}
    )
    assert memory.constraints == []
    assert SummaryMemory.from_dict(None).generation == 0
    store = ConversationStore(storage_dir=tmp_path / "c2")
    assert store._records == {}
