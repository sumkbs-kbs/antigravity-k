"""NX-02: append-only journal (originals) vs bounded prompt view.

ADR: ``docs/adr/ADR-DAT-02-conversation-history-journal.md``.

Acceptance list (docs/19 … NX-02 → nx02/handoff.md §4):

1. 1,000+ message exact id/order round-trip through the originals read surface.
2. the prompt view stays bounded (soft max) while originals stay lossless.
3. journal backfill in the storage migration is idempotent, dry-run clean and
   reports what it would create.
4. crash injection after the journal commit (view write fails) → the view is
   rebuilt from the journal, no original is lost.
5. journal write failure (disk full / permission) preserves the previous state
   and is reported as an explicit 503-class error.
6. two-process races (append/append, append/delete) keep CAS and journal order.
7. after deletion the originals and the export are gone (no resurrection).
8. a torn final line is reported as an uncommitted tail, never as a turn.
9. a corrupt committed line is a hard error carrying line + byte offset.
10. a legacy view that already carries a summary backfills as
    ``history_incomplete`` rather than pretending the originals exist.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import subprocess
import sys
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from antigravity_k.api.contracts.errors import (
    ConversationHistoryCorruptError,
    ConversationHistoryUnavailableError,
    ConversationNotFoundError,
)
from antigravity_k.api.error_handler import APIError, global_exception_handler
from antigravity_k.api.routes import conversation_api
from antigravity_k.engine import conversation_journal as journal_module
from antigravity_k.engine.conversation_journal import (
    JOURNAL_SCHEMA_VERSION,
    JOURNAL_SUFFIX,
    ConversationJournal,
    ConversationJournalCorruptError,
    read_deletion_marker,
)
from antigravity_k.engine.conversation_store import (
    ConversationStore,
    conversation_storage_relative_path,
    reset_conversation_store_for_tests,
)
from antigravity_k.engine.project_registry import ProjectRegistry
from antigravity_k.engine.summary_memory import SummaryMemory

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_conversation_storage.py"
PROJECT = "p"
CONV = "conv"

# ── helpers ─────────────────────────────────────────────────────────────


def _store(tmp_path: Path, name: str = "conversations") -> ConversationStore:
    return ConversationStore(storage_dir=tmp_path / name)


def _append(store: ConversationStore, revision: int, content: str, *, conversation_id: str = CONV) -> str:
    snap = store.append(
        project_id=PROJECT,
        conversation_id=conversation_id,
        expected_revision=revision,
        role="user" if revision % 2 == 0 else "assistant",
        content=content,
    )
    assert snap.revision == revision + 1
    return snap.conversation_id


def _view_path(store: ConversationStore, conversation_id: str = CONV) -> Path:
    return store._path_for(PROJECT, conversation_id)


def _journal_path(storage: Path, conversation_id: str = CONV) -> Path:
    return storage / conversation_storage_relative_path(PROJECT, conversation_id).with_suffix(JOURNAL_SUFFIX)


def _legacy_record_v2(
    conversation_id: str, *, content: str = "legacy turn", summary: str | None = None
) -> dict[str, Any]:
    """A v2 view record as an older build would have written it (no journal)."""
    messages: list[dict[str, Any]] = []
    if summary is not None:
        messages.append(
            {
                "id": "msg_summary",
                "role": "system",
                "content": summary,
                "created_at": 1.0,
                "provenance": "summary",
            }
        )
    messages.append({"id": "msg_legacy", "role": "user", "content": content, "created_at": 2.0, "provenance": "append"})
    return {
        "conversation_id": conversation_id,
        "project_id": PROJECT,
        "revision": 7,
        "messages": messages,
        "summary": summary,
        "retained_message_ids": [m["id"] for m in messages],
        "forked_from": None,
        "created_at": 1.0,
        "updated_at": 2.0,
        "memory": SummaryMemory().to_dict(),
        "journal_seq": 0,
        "history_incomplete": False,
        "view_schema": "agk.conv-view.v1",
    }


def _write_view(storage: Path, payload: dict[str, Any]) -> Path:
    path = storage / conversation_storage_relative_path(PROJECT, str(payload["conversation_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ── 1 / 2: round-trip + bounded view ────────────────────────────────────


def test_round_trip_1000_originals_with_bounded_view(tmp_path: Path) -> None:
    store = _store(tmp_path)
    expected_ids: list[str] = []
    for i in range(1001):
        _append(store, i, f"turn-{i}")
        expected_ids.append(store.original_history(project_id=PROJECT, conversation_id=CONV)[-1]["id"])

    originals = store.original_history(project_id=PROJECT, conversation_id=CONV)
    assert len(originals) == 1001
    assert [m["id"] for m in originals] == expected_ids
    assert [m["content"] for m in originals] == [f"turn-{i}" for i in range(1001)]
    # Compacted summaries are part of the view, never presented as original turns.
    assert {m["provenance"] for m in originals} == {"append"}

    # 2) the prompt view stays bounded while originals keep every turn.
    view = store.get(project_id=PROJECT, conversation_id=CONV)
    assert view is not None
    assert len(view.messages) <= 64
    assert view.revision == 1001

    # A fresh process sees the same originals (replay, not the in-memory cache).
    fresh = _store(tmp_path)
    replayed = fresh.original_history(project_id=PROJECT, conversation_id=CONV)
    assert [m["id"] for m in replayed] == expected_ids
    state = fresh.history_state(project_id=PROJECT, conversation_id=CONV)
    assert state["journal_seq"] == 1001
    assert state["history_incomplete"] is False


def test_compaction_keeps_originals_and_view_is_rebuilt_from_journal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for i in range(12):
        _append(store, i, f"turn-{i}")
    snap = store.compact(project_id=PROJECT, conversation_id=CONV, expected_revision=12, retain_tail=4)
    assert snap.revision == 13
    assert len(snap.retained_message_ids) <= 5

    originals = store.original_history(project_id=PROJECT, conversation_id=CONV)
    assert [m["content"] for m in originals if m["provenance"] == "append"] == [f"turn-{i}" for i in range(12)]

    # Losing the materialized view is not data loss: it is replayed.
    _view_path(store).unlink()
    restored = _store(tmp_path).get(project_id=PROJECT, conversation_id=CONV)
    assert restored is not None
    assert restored.summary == snap.summary


# ── 3: migration backfill ───────────────────────────────────────────────


def _run_migration(storage: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    report_path = storage.parent / f"nx02-report-{len(list(storage.parent.glob('nx02-report-*.json')))}.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--storage-dir", str(storage), "--report", str(report_path), *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return completed.returncode, report


def _legacy_record(conversation_id: str, content: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "project_id": PROJECT,
        "revision": 1,
        "messages": [
            {
                "id": f"msg_{conversation_id}",
                "role": "user",
                "content": content,
                "created_at": 1.0,
                "provenance": "append",
            }
        ],
        "summary": None,
        "retained_message_ids": [f"msg_{conversation_id}"],
    }


def test_migration_backfills_journals_idempotently(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    (storage / "legacy_proj").mkdir(parents=True)
    (storage / "legacy_proj" / "conv.json").write_text(
        json.dumps(_legacy_record(CONV, "legacy turn"), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    code, report = _run_migration(storage)
    assert code == 0, report
    assert report["state"] == "dry_run"
    assert not _journal_path(storage).exists()
    assert [item["action"] for item in report["journal_plan"]] == ["would_create"]

    code, report = _run_migration(storage, "--apply")
    assert code == 0, report
    assert report["state"] == "applied"
    assert report["journal_backfilled"] == 1
    assert _journal_path(storage).exists()

    first = _journal_path(storage).read_bytes()
    events, truncated = ConversationJournal(_journal_path(storage)).read()
    assert truncated is False
    assert [e.event_type for e in events] == ["base"]
    assert events[0].revision == 1

    code, report = _run_migration(storage, "--apply")
    assert code == 0, report
    assert report["state"] == "already_migrated"
    assert report["journal_backfilled"] == 0
    assert _journal_path(storage).read_bytes() == first  # idempotent, no rewrite

    code, report = _run_migration(storage, "--verify-only")
    assert code == 0, report
    assert report["state"] == "verified"
    assert report["journal_verification_failures"] == []

    # The migrated conversation serves reads from the journal-backed store.
    store = ConversationStore(storage_dir=storage)
    originals = store.original_history(project_id=PROJECT, conversation_id=CONV)
    assert [m["content"] for m in originals] == ["legacy turn"]


def test_verify_only_reports_missing_journal_without_rewriting(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    view = _write_view(storage, _legacy_record_v2(CONV))
    store = ConversationStore(storage_dir=storage)
    store.migration_marker_path().write_text(json.dumps({"layout": "v2", "completed": True}), encoding="utf-8")

    code, report = _run_migration(storage, "--verify-only")
    assert code == 2
    assert report["state"] == "not_verified"
    assert [f["reason"] for f in report["journal_verification_failures"]] == ["journal_missing"]
    assert view.is_file()
    assert not _journal_path(storage).exists()


# ── 4 / 5: crash + write failure ────────────────────────────────────────


def test_crash_after_journal_commit_recovers_view(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = tmp_path / "conversations"
    store = ConversationStore(storage_dir=storage)
    _append(store, 0, "first")

    def _boom(_record: Any) -> None:
        raise OSError("simulated crash while writing the view")

    monkeypatch.setattr(store, "_persist", _boom)
    with pytest.raises(OSError):
        _append(store, 1, "second")

    # The journal line is the commit point: the turn survives the failed view write.
    events, _truncated = ConversationJournal(_journal_path(storage)).read()
    assert [e.content for e in events if e.event_type == "append"] == ["first", "second"]

    monkeypatch.undo()
    recovered = ConversationStore(storage_dir=storage)
    view = recovered.get(project_id=PROJECT, conversation_id=CONV)
    assert view is not None
    assert [m.content for m in view.messages] == ["first", "second"]
    assert view.revision == 2
    assert [m["content"] for m in recovered.original_history(project_id=PROJECT, conversation_id=CONV)] == [
        "first",
        "second",
    ]


def test_journal_write_failure_preserves_state_and_is_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = tmp_path / "conversations"
    store = ConversationStore(storage_dir=storage)
    _append(store, 0, "first")
    before = _journal_path(storage).read_bytes()

    def _disk_full(_path: Path, _payload: bytes) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(journal_module, "_append_bytes", _disk_full)
    with pytest.raises(ConversationHistoryUnavailableError) as excinfo:
        _append(store, 1, "second")
    assert excinfo.value.status_code == 503

    assert _journal_path(storage).read_bytes() == before
    assert [m["content"] for m in store.original_history(project_id=PROJECT, conversation_id=CONV)] == ["first"]
    view = store.get(project_id=PROJECT, conversation_id=CONV)
    assert view is not None and view.revision == 1


# ── 7 / 8 / 9 / 10: deletion, torn tail, corruption, legacy summary ─────


def test_delete_removes_originals_and_export(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    store = ConversationStore(storage_dir=storage)
    for i in range(3):
        _append(store, i, f"turn-{i}")

    assert store.delete_conversation(project_id=PROJECT, conversation_id=CONV) is True
    assert not _journal_path(storage).exists()
    assert not _view_path(store).is_file()
    assert read_deletion_marker(_view_path(store)) is not None

    assert store.original_history(project_id=PROJECT, conversation_id=CONV) == []
    assert store.get(project_id=PROJECT, conversation_id=CONV) is None
    export = store.export_original_history(project_id=PROJECT, conversation_id=CONV)
    assert export["deleted"] is True and export["messages"] == []
    state = store.history_state(project_id=PROJECT, conversation_id=CONV)
    assert state["deleted"] is True and state["content_erased"] is True

    # Deleted ids are not reused, and deleting twice is an honest no-op.
    assert store.delete_conversation(project_id=PROJECT, conversation_id=CONV) is False
    with pytest.raises(ConversationNotFoundError):
        _append(store, 0, "resurrect")


def test_torn_tail_is_uncommitted_and_moved_aside(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    store = ConversationStore(storage_dir=storage)
    for i in range(2):
        _append(store, i, f"turn-{i}")

    journal_path = _journal_path(storage)
    with journal_path.open("ab") as handle:  # torn final line: no newline, bad JSON
        handle.write(b'{"event_type": "append", "schema": "agk.conv-')

    fresh = ConversationStore(storage_dir=storage)
    state = fresh.history_state(project_id=PROJECT, conversation_id=CONV)
    assert state["truncated_tail"] is True
    assert [m["content"] for m in fresh.original_history(project_id=PROJECT, conversation_id=CONV)] == [
        "turn-0",
        "turn-1",
    ]

    recoveries = sorted(storage.rglob("*.tail-recovery-*.bin"))
    assert len(recoveries) == 1
    assert b"agk.conv-" in recoveries[0].read_bytes()
    assert fresh.history_state(project_id=PROJECT, conversation_id=CONV)["truncated_tail"] is False


def test_corrupt_committed_line_reports_offset_and_is_not_skipped(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    store = ConversationStore(storage_dir=storage)
    for i in range(3):
        _append(store, i, f"turn-{i}")

    journal_path = _journal_path(storage)
    lines = journal_path.read_bytes().split(b"\n")
    good = journal_path.read_bytes()
    lines[1] = b"{not json"
    journal_path.write_bytes(b"\n".join(lines))
    assert good != journal_path.read_bytes()

    fresh = ConversationStore(storage_dir=storage)
    with pytest.raises(ConversationHistoryCorruptError) as excinfo:
        fresh.original_history(project_id=PROJECT, conversation_id=CONV)
    assert excinfo.value.status_code == 409
    assert excinfo.value.context["journal_line"] == 2
    assert int(excinfo.value.context["journal_offset"]) > 0

    raw = ConversationJournal(journal_path)
    with pytest.raises(ConversationJournalCorruptError) as raw_exc:
        raw.read()
    assert raw_exc.value.line_no == 2

    # Committed-but-unreadable is never silently downgraded to "no originals".
    with pytest.raises(ConversationHistoryCorruptError):
        fresh.history_state(project_id=PROJECT, conversation_id=CONV)


def test_legacy_view_with_summary_backfills_history_incomplete(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    _write_view(storage, _legacy_record_v2(CONV, content="early turn", summary="[대화 요약] 요구사항 X"))

    store = ConversationStore(storage_dir=storage)
    plan = store.backfill_journal(project_id=PROJECT, conversation_id=CONV, dry_run=True)
    assert plan["action"] == "would_create"
    assert plan["history_incomplete"] is True
    assert not _journal_path(storage, CONV).exists()  # dry-run writes nothing

    applied = store.backfill_journal(project_id=PROJECT, conversation_id=CONV, dry_run=False)
    assert applied["action"] == "created" and applied["journal_seq"] == 1
    assert store.backfill_journal(project_id=PROJECT, conversation_id=CONV, dry_run=False)["action"] == (
        "already_present"
    )

    record = store.get(project_id=PROJECT, conversation_id=CONV)
    assert record is not None
    assert record.history_incomplete is True
    assert record.revision == 7
    # Originals cannot be invented from a summary: the summary message stays in the
    # view, and the only original here is the turn that really was stored.
    assert [m["provenance"] for m in store.original_history(project_id=PROJECT, conversation_id=CONV)] == ["append"]
    state = store.history_state(project_id=PROJECT, conversation_id=CONV)
    assert state["history_incomplete"] is True


# ── 6: two-process races ────────────────────────────────────────────────


def _worker_append(
    storage: str, conversation_id: str, expected_revision: int, barrier: Barrier, out: Queue[tuple[str, int]]
) -> None:
    store = ConversationStore(storage_dir=storage)
    barrier.wait(timeout=10)
    try:
        snap = store.append(
            project_id=PROJECT,
            conversation_id=conversation_id,
            expected_revision=expected_revision,
            role="assistant",
            content="race-append",
        )
        out.put(("ok", snap.revision))
    except APIError as exc:
        out.put((exc.error_code, exc.status_code))


def _worker_delete(storage: str, conversation_id: str, barrier: Barrier, out: Queue[tuple[str, int]]) -> None:
    store = ConversationStore(storage_dir=storage)
    barrier.wait(timeout=10)
    try:
        out.put(
            ("deleted" if store.delete_conversation(project_id=PROJECT, conversation_id=conversation_id) else "noop", 0)
        )
    except APIError as exc:
        out.put((exc.error_code, exc.status_code))


def _join(process: mp.Process) -> None:
    process.join(timeout=20)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail(f"worker did not exit: pid={process.pid}")
    assert process.exitcode == 0, process.exitcode


def test_two_process_append_race_keeps_journal_order(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    store = ConversationStore(storage_dir=storage)
    _append(store, 0, "first")

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    out: Queue[tuple[str, int]] = ctx.Queue()
    workers = [
        ctx.Process(target=_worker_append, args=(str(storage), CONV, 1, barrier, out)),
        ctx.Process(target=_worker_append, args=(str(storage), CONV, 1, barrier, out)),
    ]
    for worker in workers:
        worker.start()
    results = [out.get(timeout=30) for _ in workers]
    for worker in workers:
        _join(worker)

    assert sorted(r[0] for r in results) == ["ok", "stale_conversation_revision"]
    assert [r[1] for r in results if r[0] == "ok"] == [2]

    # Only the CAS winner commits: one append = one journal line = one revision.
    events, _truncated = ConversationJournal(_journal_path(storage)).read()
    assert [e.seq for e in events] == [1, 2]
    assert [e.revision for e in events] == [1, 2]
    assert [e.event_type for e in events] == ["append", "append"]
    originals = store.original_history(project_id=PROJECT, conversation_id=CONV)
    assert [m["content"] for m in originals] == ["first", "race-append"]


def test_two_process_append_delete_race_never_resurrects(tmp_path: Path) -> None:
    for round_no in range(3):
        storage = tmp_path / f"conversations-{round_no}"
        store = ConversationStore(storage_dir=storage)
        _append(store, 0, "first")

        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(2)
        out: Queue[tuple[str, int]] = ctx.Queue()
        workers = [
            ctx.Process(target=_worker_append, args=(str(storage), CONV, 1, barrier, out)),
            ctx.Process(target=_worker_delete, args=(str(storage), CONV, barrier, out)),
        ]
        for worker in workers:
            worker.start()
        results = [out.get(timeout=30) for _ in workers]
        for worker in workers:
            _join(worker)

        assert "deleted" in {r[0] for r in results}, results
        # Either order: the delete is durable and the id is not reusable.
        assert store.get(project_id=PROJECT, conversation_id=CONV) is None
        assert store.original_history(project_id=PROJECT, conversation_id=CONV) == []
        assert store.history_state(project_id=PROJECT, conversation_id=CONV)["deleted"] is True
        with pytest.raises(ConversationNotFoundError):
            store.append(
                project_id=PROJECT,
                conversation_id=CONV,
                expected_revision=0,
                role="user",
                content="after delete",
            )
        assert store.delete_conversation(project_id=PROJECT, conversation_id=CONV) is False


# ── API surface: view vs originals vs export vs delete ──────────────────


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from antigravity_k.engine import conversation_store as cs

    reset_conversation_store_for_tests(cs.ConversationStore(storage_dir=tmp_path / "conversations"))

    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    root = tmp_path / "proj"
    root.mkdir()
    record = registry.add_project(name="NX02", path=str(root))
    monkeypatch.setattr("antigravity_k.api.project_binding.get_project_registry", lambda: registry)
    monkeypatch.setattr("antigravity_k.engine.request_execution_context.get_project_registry", lambda: registry)
    monkeypatch.setattr("antigravity_k.config.config.paths.project_root", tmp_path.resolve())
    monkeypatch.setenv("AGK_ALLOWED_ROOTS", str(tmp_path.resolve()))

    app = FastAPI()
    app.add_exception_handler(APIError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(conversation_api.router)
    test = TestClient(app, raise_server_exceptions=False)
    test.project_id = record.id  # type: ignore[attr-defined]
    test.store_dir = tmp_path / "conversations"  # type: ignore[attr-defined]
    return test


def _seed_api(client: TestClient, count: int = 5, conversation_id: str = "conv_api") -> list[str]:
    project_id = client.project_id  # type: ignore[attr-defined]
    ids: list[str] = []
    for i in range(count):
        response = client.post(
            "/v1/conversations/append",
            json={
                "project_id": project_id,
                "conversation_id": conversation_id,
                "expected_revision": i,
                "role": "user",
                "content": f"turn-{i}",
            },
        )
        assert response.status_code == 200, response.text
        snapshot = client.get("/v1/conversations/" + conversation_id, params={"project_id": project_id}).json()
        ids.append(snapshot["messages"][-1]["id"])
    return ids


def test_api_history_export_and_delete_surface(client: TestClient) -> None:
    project_id = client.project_id  # type: ignore[attr-defined]
    ids = _seed_api(client)

    history = client.get(
        "/v1/conversations/conv_api/history", params={"project_id": project_id, "offset": 1, "limit": 2}
    )
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["total"] == 5
    assert [m["id"] for m in body["messages"]] == ids[1:3]
    assert body["history_incomplete"] is False
    assert body["journal_seq"] == 5

    exported = client.get("/v1/conversations/conv_api/export", params={"project_id": project_id})
    assert exported.status_code == 200, exported.text
    export_body = exported.json()
    assert export_body["journal_schema"] == JOURNAL_SCHEMA_VERSION
    assert len(export_body["journal_sha256"]) == 64
    assert export_body["message_count"] == 5
    assert [m["content"] for m in export_body["messages"]] == [f"turn-{i}" for i in range(5)]

    # The prompt view keeps its old shape (compat) but is not the originals surface.
    view = client.get("/v1/conversations/conv_api", params={"project_id": project_id}).json()
    assert len(view["messages"]) == 5

    stale = client.delete("/v1/conversations/conv_api", params={"project_id": project_id, "expected_revision": 3})
    assert stale.status_code == 409
    assert stale.json()["error"] == "stale_conversation_revision"

    deleted = client.delete("/v1/conversations/conv_api", params={"project_id": project_id, "expected_revision": 5})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert deleted.json()["erased_scope"] == "journal_and_view"

    gone = client.get("/v1/conversations/conv_api/history", params={"project_id": project_id})
    assert gone.status_code == 404
    assert gone.json()["reason"] == "deleted"
    assert client.get("/v1/conversations/conv_api/export", params={"project_id": project_id}).status_code == 404
    assert client.get("/v1/conversations/conv_api", params={"project_id": project_id}).status_code == 404

    missing = client.delete("/v1/conversations/never-seen", params={"project_id": project_id})
    assert missing.status_code == 200
    assert missing.json() == {
        "conversation_id": "never-seen",
        "project_id": project_id,
        "deleted": False,
        "erased_scope": "nothing",
        "revision": 0,
        "note": (
            "Deleted from the local conversation store. Copies outside this store "
            "(backups, forks, exported files) are not claimed to be erased."
        ),
    }


def test_api_history_rejects_bad_paging_and_reports_corruption(client: TestClient) -> None:
    project_id = client.project_id  # type: ignore[attr-defined]
    _seed_api(client, count=3)

    bad = client.get("/v1/conversations/conv_api/history", params={"project_id": project_id, "offset": "-1"})
    assert bad.status_code == 400
    assert bad.json()["error"] == "validation_error"

    store_dir = Path(client.store_dir)  # type: ignore[attr-defined]
    view = store_dir / conversation_storage_relative_path(project_id, "conv_api")
    journal_path = view.with_suffix(JOURNAL_SUFFIX)
    lines = journal_path.read_bytes().split(b"\n")
    lines[1] = b"not json at all"
    journal_path.write_bytes(b"\n".join(lines))

    corrupt = client.get("/v1/conversations/conv_api/history", params={"project_id": project_id})
    assert corrupt.status_code == 409
    assert corrupt.json()["error"] == "conversation_history_corrupt"
    assert corrupt.json()["journal_line"] == 2
