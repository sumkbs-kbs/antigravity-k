"""CTX-01 authoritative conversation store + revision CAS."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from antigravity_k.api.contracts.errors import StaleConversationRevisionError
from antigravity_k.engine.conversation_store import ConversationStore
from antigravity_k.engine.tokenizer import TokenEstimator


@pytest.fixture()
def store(tmp_path: Path) -> ConversationStore:
    return ConversationStore(storage_dir=tmp_path / "conversations")


def test_append_cas_advances_revision(store: ConversationStore) -> None:
    snap0 = store.append(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=0,
        role="user",
        content="hello",
    )
    assert snap0.revision == 1
    assert snap0.message_count == 1

    snap1 = store.append(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=1,
        role="assistant",
        content="world",
    )
    assert snap1.revision == 2
    assert snap1.message_count == 2


def test_stale_append_raises_conflict(store: ConversationStore) -> None:
    store.append(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=0,
        role="user",
        content="first",
    )
    with pytest.raises(StaleConversationRevisionError) as exc:
        store.append(
            project_id="proj_a",
            conversation_id="conv_1",
            expected_revision=0,
            role="user",
            content="stale",
        )
    assert exc.value.error_code == "stale_conversation_revision"
    assert exc.value.context["current_revision"] == 1
    # Winner content preserved — no silent overwrite
    record = store.get(project_id="proj_a", conversation_id="conv_1")
    assert record is not None
    assert record.messages[0].content == "first"
    assert len(record.messages) == 1


def test_two_tab_race_one_winner(store: ConversationStore) -> None:
    store.append(
        project_id="proj_a",
        conversation_id="conv_race",
        expected_revision=0,
        role="user",
        content="seed",
    )
    results: list[str] = []
    barrier = threading.Barrier(2)

    def worker(label: str) -> None:
        barrier.wait()
        try:
            store.append(
                project_id="proj_a",
                conversation_id="conv_race",
                expected_revision=1,
                role="user",
                content=label,
            )
            results.append(f"ok:{label}")
        except StaleConversationRevisionError:
            results.append(f"conflict:{label}")

    t1 = threading.Thread(target=worker, args=("tab-a",))
    t2 = threading.Thread(target=worker, args=("tab-b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert sorted(results)[0].startswith("conflict:")
    assert sorted(results)[1].startswith("ok:")
    record = store.get(project_id="proj_a", conversation_id="conv_race")
    assert record is not None
    assert record.revision == 2
    assert len(record.messages) == 2


def test_compact_returns_summary_retained_ids_and_new_revision(store: ConversationStore) -> None:
    rev = 0
    for i in range(10):
        snap = store.append(
            project_id="proj_a",
            conversation_id="conv_c",
            expected_revision=rev,
            role="user" if i % 2 == 0 else "assistant",
            content=f"message-{i} " + ("detail " * 40),
        )
        rev = snap.revision

    before = store.get(project_id="proj_a", conversation_id="conv_c")
    assert before is not None
    tokens_before = before.estimate_tokens()

    snap = store.compact(
        project_id="proj_a",
        conversation_id="conv_c",
        expected_revision=rev,
        retain_tail=4,
    )
    assert snap.revision == rev + 1
    assert snap.summary
    assert len(snap.retained_message_ids) >= 1
    assert snap.message_count < 10

    after = store.get(project_id="proj_a", conversation_id="conv_c")
    assert after is not None
    tokens_after = after.estimate_tokens()
    assert tokens_after < tokens_before


def test_next_request_tokens_decrease_after_compact(store: ConversationStore) -> None:
    rev = 0
    for i in range(12):
        snap = store.append(
            project_id="proj_a",
            conversation_id="conv_tok",
            expected_revision=rev,
            role="user" if i % 2 == 0 else "assistant",
            content=("긴 대화 내용입니다. " * 30) + f"#{i}",
        )
        rev = snap.revision

    before_msgs, _ = store.assemble_history_for_request(
        project_id="proj_a",
        conversation_id="conv_tok",
        expected_revision=rev,
        new_turn=None,
    )
    tokens_before = TokenEstimator.estimate_messages(before_msgs)

    snap = store.compact(
        project_id="proj_a",
        conversation_id="conv_tok",
        expected_revision=rev,
        retain_tail=4,
    )
    after_msgs, _ = store.assemble_history_for_request(
        project_id="proj_a",
        conversation_id="conv_tok",
        expected_revision=snap.revision,
        new_turn=None,
    )
    tokens_after = TokenEstimator.estimate_messages(after_msgs)
    assert tokens_after < tokens_before


def test_refresh_reconnect_revision_consistent(store: ConversationStore, tmp_path: Path) -> None:
    snap = store.append(
        project_id="proj_a",
        conversation_id="conv_r",
        expected_revision=0,
        role="user",
        content="persist-me",
    )
    # Simulate reconnect with a fresh store instance pointing at same disk
    store2 = ConversationStore(storage_dir=tmp_path / "conversations")
    loaded = store2.get(project_id="proj_a", conversation_id="conv_r")
    assert loaded is not None
    assert loaded.revision == snap.revision
    assert loaded.messages[0].content == "persist-me"


def test_fork_keeps_revision_consistent(store: ConversationStore) -> None:
    rev = 0
    for i in range(3):
        snap = store.append(
            project_id="proj_a",
            conversation_id="conv_src",
            expected_revision=rev,
            role="user",
            content=f"turn-{i}",
        )
        rev = snap.revision

    forked = store.fork(
        project_id="proj_a",
        source_conversation_id="conv_src",
        expected_revision=rev,
    )
    assert forked.revision == 0
    assert forked.message_count == 3
    assert forked.conversation_id != "conv_src"

    # Source unchanged
    source = store.get(project_id="proj_a", conversation_id="conv_src")
    assert source is not None
    assert source.revision == rev

    # Stale fork expectation conflicts
    with pytest.raises(StaleConversationRevisionError):
        store.fork(
            project_id="proj_a",
            source_conversation_id="conv_src",
            expected_revision=0,
        )


def test_client_sends_new_turn_not_full_array_as_sot(store: ConversationStore) -> None:
    """Server ignores client full history and uses store + new_turn."""
    store.append(
        project_id="proj_a",
        conversation_id="conv_nt",
        expected_revision=0,
        role="user",
        content="server-owned-1",
    )
    store.append(
        project_id="proj_a",
        conversation_id="conv_nt",
        expected_revision=1,
        role="assistant",
        content="server-owned-2",
    )
    history, snap = store.assemble_history_for_request(
        project_id="proj_a",
        conversation_id="conv_nt",
        expected_revision=2,
        new_turn={"role": "user", "content": "only-new-turn"},
    )
    assert snap.revision == 3
    assert [m["content"] for m in history] == [
        "server-owned-1",
        "server-owned-2",
        "only-new-turn",
    ]


def test_compact_cas_conflict(store: ConversationStore) -> None:
    store.append(
        project_id="proj_a",
        conversation_id="conv_cc",
        expected_revision=0,
        role="user",
        content="a " * 200,
    )
    store.append(
        project_id="proj_a",
        conversation_id="conv_cc",
        expected_revision=1,
        role="assistant",
        content="b " * 200,
    )
    with pytest.raises(StaleConversationRevisionError):
        store.compact(
            project_id="proj_a",
            conversation_id="conv_cc",
            expected_revision=0,
            retain_tail=1,
        )
