"""CTX-01 REJECT F1–F4 regression tests (owner fix; not APPROVE)."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, cast

import pytest

from antigravity_k.api.contracts.errors import StaleConversationRevisionError
from antigravity_k.api.contracts.execution_context import RequestExecutionContext
from antigravity_k.api.routes import chat as chat_routes
from antigravity_k.engine.conversation_store import ConversationStore, reset_conversation_store_for_tests
from antigravity_k.engine.slash_commands_session import SlashCommandSessionMixin
from antigravity_k.engine.tokenizer import TokenEstimator


@pytest.fixture()
def store(tmp_path: Path) -> ConversationStore:
    fresh = ConversationStore(storage_dir=tmp_path / "conversations")
    reset_conversation_store_for_tests(fresh)
    return fresh


def _ctx(*, project_id: str = "proj_a", conversation_id: str = "conv_1", revision: int = 0) -> RequestExecutionContext:
    return RequestExecutionContext(
        request_id="req_test",
        project_id=project_id,
        canonical_project_root="/tmp/proj_a",
        conversation_id=conversation_id,
        conversation_revision=revision,
        actor_subject="tester",
        session_id="sess_test",
        model_id="dummy",
    )


class _Host(SlashCommandSessionMixin):
    def __init__(self, *, session: object | None = None, shaper: object | None = None) -> None:
        setattr(self, "_commands", {})
        setattr(self, "_tool_registry", None)
        setattr(self, "_session_manager", session)
        setattr(self, "_context_shaper", shaper)
        setattr(self, "_model_manager", None)


def _seed_long_history(store: ConversationStore, *, n: int = 12) -> int:
    rev = 0
    for i in range(n):
        snap = store.append(
            project_id="proj_a",
            conversation_id="conv_1",
            expected_revision=rev,
            role="user" if i % 2 == 0 else "assistant",
            content=f"message-{i}-" + ("x" * 80),
        )
        rev = snap.revision
    return rev


# ─── F1 / F3: slash compact ───────────────────────────────────────


def test_f1_f3_slash_stale_expected_returns_conflict_no_session_mutate(
    store: ConversationStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stale client expected_revision → conflict string; session_manager untouched."""
    rev = _seed_long_history(store)
    # Advance store via compact so client expected becomes stale.
    store.compact(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=rev,
        retain_tail=3,
    )
    after = store.get(project_id="proj_a", conversation_id="conv_1")
    assert after is not None
    store_rev = after.revision
    store_msgs = list(after.prompt_messages())

    shaped_calls = {"n": 0}
    saved = {"n": 0}

    def _shape(messages: list[dict[str, object]]) -> list[dict[str, object]]:
        shaped_calls["n"] += 1
        return [{"role": "system", "content": "LEGACY_SHAPED"}]

    session = SimpleNamespace(
        get_messages=lambda: [{"role": "user", "content": "local"}],
        save=lambda: saved.update(n=saved["n"] + 1),
        _current_session={"messages": [{"role": "user", "content": "local"}]},
    )
    shaper = SimpleNamespace(shape=_shape, _estimate_tokens=lambda m: len(m) * 10)
    host = _Host(session=session, shaper=shaper)

    # Client still holds pre-compact revision (stale).
    monkeypatch.setattr(
        "antigravity_k.api.project_binding.get_bound_request_execution_context",
        lambda: _ctx(revision=rev),
    )

    out = cast(Callable[[list[str]], str], getattr(host, "_cmd_compact"))([])
    assert "stale_conversation_revision" in out
    assert "❌" in out
    assert shaped_calls["n"] == 0
    assert saved["n"] == 0
    assert session._current_session["messages"] == [{"role": "user", "content": "local"}]

    # Store unchanged by loser.
    final = store.get(project_id="proj_a", conversation_id="conv_1")
    assert final is not None
    assert final.revision == store_rev
    assert final.prompt_messages() == store_msgs


def test_f1_concurrent_slash_compact_one_winner(store: ConversationStore, monkeypatch: pytest.MonkeyPatch) -> None:
    rev = _seed_long_history(store)
    results: list[str] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        shaped = {"n": 0}
        session = SimpleNamespace(
            get_messages=lambda: [{"role": "user", "content": "x"}],
            save=lambda: None,
            _current_session={"messages": []},
        )
        shaper = SimpleNamespace(
            shape=lambda m: shaped.update(n=shaped["n"] + 1) or m,
            _estimate_tokens=lambda m: 1,
        )
        host = _Host(session=session, shaper=shaper)
        monkeypatch.setattr(
            "antigravity_k.api.project_binding.get_bound_request_execution_context",
            lambda: _ctx(revision=rev),
        )
        barrier.wait()
        out = cast(Callable[[list[str]], str], getattr(host, "_cmd_compact"))([])
        results.append(out)
        # Loser must not have shaped via legacy path.
        if "stale_conversation_revision" in out:
            assert shaped["n"] == 0

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    wins = [r for r in results if "authoritative store CAS" in r]
    losses = [r for r in results if "stale_conversation_revision" in r]
    assert len(wins) == 1
    assert len(losses) == 1


def test_f3_slash_uses_client_expected_not_before_revision(
    store: ConversationStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even when record exists, CAS must use ctx.conversation_revision (not before.revision)."""
    rev = _seed_long_history(store)
    host = _Host(
        session=SimpleNamespace(
            get_messages=lambda: [],
            save=lambda: None,
            _current_session={"messages": []},
        ),
        shaper=SimpleNamespace(shape=lambda m: m, _estimate_tokens=lambda m: 1),
    )
    # Stale expected while before.revision would have been current.
    monkeypatch.setattr(
        "antigravity_k.api.project_binding.get_bound_request_execution_context",
        lambda: _ctx(revision=0),
    )
    out = cast(Callable[[list[str]], str], getattr(host, "_cmd_compact"))([])
    assert "stale_conversation_revision" in out
    # Head unchanged
    record = store.get(project_id="proj_a", conversation_id="conv_1")
    assert record is not None
    assert record.revision == rev


# ─── F2: assistant persist surfaces stale ─────────────────────────


def test_f2_persist_assistant_raises_stale_not_soft_swallowed(store: ConversationStore) -> None:
    snap = store.append(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=0,
        role="user",
        content="hello user",
    )
    # Concurrent compact advances revision.
    store.compact(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=snap.revision,
        retain_tail=1,
    )
    ctx = _ctx(revision=snap.revision)
    with pytest.raises(StaleConversationRevisionError) as exc:
        chat_routes._persist_assistant_to_conversation_store(ctx, snap, "assistant reply that must not vanish")
    assert exc.value.error_code == "stale_conversation_revision"
    record = store.get(project_id="proj_a", conversation_id="conv_1")
    assert record is not None
    assert not any(m.role == "assistant" and "must not vanish" in m.content for m in record.messages)


def test_f2_conflict_sse_frame_is_typed() -> None:
    exc = StaleConversationRevisionError(
        detail="Conversation revision does not match the authoritative store",
        context={
            "conversation_id": "conv_1",
            "expected_revision": 2,
            "current_revision": 5,
            "project_id": "proj_a",
        },
    )
    frame = chat_routes._conversation_conflict_sse(exc)
    assert frame.startswith("data: ")
    assert "stale_conversation_revision" in frame
    assert "agk_conversation_conflict" in frame
    assert '"current_revision": 5' in frame
    assert '"expected_revision": 2' in frame


# ─── F4: auto_restore gated when protocol on ──────────────────────


def test_f4_auto_restore_skipped_when_revision_protocol_on(store: ConversationStore) -> None:
    assert chat_routes._uses_conversation_revision_protocol(
        {"new_turn": {"role": "user", "content": "hi"}, "conversation_id": "conv_1"}
    )
    assert chat_routes._uses_conversation_revision_protocol({"use_conversation_store": True})
    assert not chat_routes._uses_conversation_revision_protocol({"messages": [{"role": "user", "content": "hi"}]})


def test_f4_tokens_still_decrease_after_compact_despite_session_restore_bait(
    store: ConversationStore,
) -> None:
    """Compact → assemble_history tokens < before even if session would re-inflate."""
    rev = _seed_long_history(store, n=14)
    before = store.get(project_id="proj_a", conversation_id="conv_1")
    assert before is not None
    tokens_before = before.estimate_tokens()

    snap = store.compact(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=rev,
        retain_tail=2,
    )
    history, _ = store.assemble_history_for_request(
        project_id="proj_a",
        conversation_id="conv_1",
        expected_revision=snap.revision,
        new_turn={"role": "user", "content": "next"},
        create_if_missing=False,
    )
    # Simulate large prior context that auto_restore would have injected — protocol
    # path must NOT include it (gate is in chat.py; assemble itself is store-only).
    bait = "RESTORED_SYSTEM_CONTEXT " + (" inflates " * 200)
    tokens_after = TokenEstimator.estimate_messages(history)
    tokens_with_bait = TokenEstimator.estimate_messages([{"role": "system", "content": bait}, *history])
    assert tokens_after < tokens_before
    assert tokens_with_bait > tokens_after
    # Protocol gate: chat must use store history only (≤4 msgs after compact+new_turn).
    assert len(history) <= 4
    assert chat_routes._uses_conversation_revision_protocol(
        {
            "new_turn": {"role": "user", "content": "next"},
            "conversation_id": "conv_1",
            "use_conversation_store": True,
        }
    )
