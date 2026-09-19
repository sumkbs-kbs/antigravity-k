"""Decision A: ConversationStore auto-compacts when soft-max exceeded."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_k.engine.conversation_store import ConversationStore


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConversationStore:
    monkeypatch.setenv("AGK_CONVERSATION_SOFT_MAX_MESSAGES", "10")
    return ConversationStore(storage_dir=tmp_path / "conversations")


def test_append_auto_compacts_when_over_soft_max(store: ConversationStore) -> None:
    rev = 0
    for i in range(15):
        snap = store.append(
            project_id="p",
            conversation_id="c",
            expected_revision=rev,
            role="user",
            content=f"turn {i} " + ("x" * 20),
        )
        rev = snap.revision
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    assert rev == 15
    assert len(record.messages) <= 10
    assert any(m.provenance == "summary" for m in record.messages)


def test_soft_max_zero_disables_auto_compact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGK_CONVERSATION_SOFT_MAX_MESSAGES", "0")
    store = ConversationStore(storage_dir=tmp_path / "conversations")
    rev = 0
    for i in range(12):
        snap = store.append(
            project_id="p",
            conversation_id="c",
            expected_revision=rev,
            role="user",
            content=f"turn {i}",
        )
        rev = snap.revision
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    assert len(record.messages) == 12
