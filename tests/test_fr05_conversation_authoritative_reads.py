"""FR-05 regression: conversation reads must observe the disk truth.

Covers the authoritative-read contract across two store instances (two
workers) and across two OS processes:

- a cached reader immediately observes another worker's appended revision
- stale get_or_create / compare_and_set are rejected
- concurrent expected-0 create+append across processes yields exactly one
  success and the final message count matches the success count
- append vs compact race: only one CAS wins
- state survives store restart; a lost view is rebuilt from the journal while a
  lost journal+view invalidates the cache (NX-02/ADR-DAT-02)
- corrupt payloads raise ConversationIntegrityError (CR-01) instead of being
  reported as an empty/not-found conversation
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path

import pytest

from antigravity_k.api.contracts.errors import (
    ConversationIntegrityError,
    StaleConversationRevisionError,
)
from antigravity_k.engine.conversation_store import ConversationStore

PID = str(os.getpid())


def _store(storage: Path) -> ConversationStore:
    return ConversationStore(storage_dir=storage)


def _mk_storage(tmp_path: Path, name: str) -> Path:
    storage = tmp_path / name
    storage.mkdir(parents=True)
    return storage


def _seed(storage: Path) -> str:
    """Create rev1 with one user message via a first worker, return conv id."""
    store = _store(storage)
    snap = store.append(
        project_id="p",
        conversation_id="conv",
        expected_revision=0,
        role="user",
        content="first turn",
    )
    assert snap.revision == 1
    return "conv"


def _join_process(process: mp.Process) -> None:
    process.join(timeout=20)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail(f"worker did not exit: pid={process.pid}")
    assert process.exitcode == 0, process.exitcode


def _worker_append_once(storage: str, barrier: Barrier, out: Queue[tuple[str, int]]) -> None:
    store = ConversationStore(storage_dir=storage)
    barrier.wait(timeout=10)
    try:
        snapshot = store.append(
            project_id="p",
            conversation_id="conv",
            expected_revision=1,
            role="assistant",
            content="remote second turn",
        )
        out.put(("ok", snapshot.revision))
    except StaleConversationRevisionError as exc:
        current_revision = exc.context["current_revision"]
        assert isinstance(current_revision, int)
        out.put(("stale", current_revision))


@pytest.mark.parametrize("read_method", ["get", "get_or_create"])
def test_public_record_return_does_not_alias_store_cache(tmp_path: Path, read_method: str) -> None:
    storage = _mk_storage(tmp_path, "copy-safe")
    _seed(storage)
    store = _store(storage)

    if read_method == "get":
        returned = store.get(project_id="p", conversation_id="conv")
        assert returned is not None
    else:
        returned = store.get_or_create(project_id="p", conversation_id="conv", expected_revision=1)

    returned.revision = 99
    returned.messages.clear()
    persisted = json.loads(store._path_for("p", "conv").read_text(encoding="utf-8"))
    authoritative = store.get(project_id="p", conversation_id="conv")
    fresh = _store(storage).get(project_id="p", conversation_id="conv")

    assert persisted["revision"] == 1
    assert len(persisted["messages"]) == 1
    assert authoritative is not None
    assert authoritative.revision == 1
    assert len(authoritative.messages) == 1
    assert fresh is not None
    assert fresh.revision == 1
    assert len(fresh.messages) == 1
    assert returned.revision == 99
    assert returned.messages == []


class TestCrossWorkerReads:
    def test_cached_reader_observes_remote_append(self, tmp_path: Path) -> None:
        storage = _mk_storage(tmp_path, "s")
        _seed(storage)
        reader = _store(storage)
        # reader caches rev1
        assert reader.get_revision(project_id="p", conversation_id="conv") == 1

        writer = _store(storage)
        _ = writer.append(
            project_id="p",
            conversation_id="conv",
            expected_revision=1,
            role="assistant",
            content="second turn",
        )

        assert reader.get_revision(project_id="p", conversation_id="conv") == 2
        got = reader.get(project_id="p", conversation_id="conv")
        assert got is not None and len(got.messages) == 2

    def test_stale_get_or_create_rejected(self, tmp_path: Path) -> None:
        from antigravity_k.api.contracts.errors import StaleConversationRevisionError

        storage = _mk_storage(tmp_path, "s")
        _seed(storage)
        reader = _store(storage)
        _ = reader.get_revision(project_id="p", conversation_id="conv")
        writer = _store(storage)
        _ = writer.append(
            project_id="p",
            conversation_id="conv",
            expected_revision=1,
            role="assistant",
            content="second turn",
        )
        with pytest.raises(StaleConversationRevisionError):
            _ = reader.get_or_create(project_id="p", conversation_id="conv", expected_revision=1)

    def test_stale_cas_rejected(self, tmp_path: Path) -> None:
        storage = _mk_storage(tmp_path, "s")
        _seed(storage)
        reader = _store(storage)
        _ = reader.get_revision(project_id="p", conversation_id="conv")
        writer = _store(storage)
        _ = writer.append(
            project_id="p",
            conversation_id="conv",
            expected_revision=1,
            role="assistant",
            content="second turn",
        )
        assert (
            reader.compare_and_set(
                project_id="p",
                conversation_id="conv",
                expected_revision=1,
                next_revision=2,
            )
            is False
        )

    def test_deleted_file_invalidates_cache(self, tmp_path: Path) -> None:
        """NX-02: view 손실은 journal replay 로 복구되고, 삭제는 명시적이어야 한다.

        이전 계약은 view `.json` 이 없으면 곧 삭제였다. ADR-DAT-02 이후 view 는
        파생물이므로, view 만 사라지면 원본 journal 에서 재생성된다(원문 보존).
        진짜 삭제는 journal 과 view 를 함께 지우는 명시적 경로여야 한다.
        """
        storage = _mk_storage(tmp_path, "s")
        _seed(storage)
        reader = _store(storage)
        assert reader.get_revision(project_id="p", conversation_id="conv") == 1

        # (1) view 만 삭제 → journal 에서 재생성(캐시 무효화 + 원문 유지)
        reader._path_for("p", "conv").unlink()
        assert reader.get_revision(project_id="p", conversation_id="conv") == 1
        restored = reader.get(project_id="p", conversation_id="conv")
        assert restored is not None
        assert [m.content for m in restored.messages] == ["first turn"]

        # (2) journal 까지 사라진 경우 → 캐시를 무효화하고 없는 대화로 본다
        lost = _store(storage)
        lost.journal_path(project_id="p", conversation_id="conv").unlink()
        lost._path_for("p", "conv").unlink()
        assert lost.get_revision(project_id="p", conversation_id="conv") is None
        assert lost.get(project_id="p", conversation_id="conv") is None

    def test_corrupt_payload_does_not_reuse_cached_record(self, tmp_path: Path) -> None:
        """CR-01: corrupt bytes are an integrity failure, never an empty conversation.

        The old contract degraded corruption to ``None`` (i.e. "not found"),
        which hid real data loss behind a normal empty/404 path. CR-01 requires
        an explicit integrity error and no reuse of the cached record.
        """
        storage = _mk_storage(tmp_path, "corrupt")
        _seed(storage)
        reader = _store(storage)
        assert reader.get_revision(project_id="p", conversation_id="conv") == 1
        reader._path_for("p", "conv").write_text("{not json", encoding="utf-8")

        with pytest.raises(ConversationIntegrityError):
            reader.get(project_id="p", conversation_id="conv")
        with pytest.raises(ConversationIntegrityError):
            reader.get_revision(project_id="p", conversation_id="conv")
        with pytest.raises(ConversationIntegrityError):
            reader.snapshot(project_id="p", conversation_id="conv")

    def test_restart_sees_same_state(self, tmp_path: Path) -> None:
        storage = _mk_storage(tmp_path, "s")
        _seed(storage)
        fresh = _store(storage)
        snap = fresh.snapshot(project_id="p", conversation_id="conv")
        assert snap.revision == 1
        assert snap.message_count == 1


# ── Process-level races ────────────────────────────────────────────────


def test_cached_process_reads_remote_append_authoritatively(tmp_path: Path) -> None:
    storage = _mk_storage(tmp_path, "process-read")
    _seed(storage)
    reader = _store(storage)
    assert reader.get_revision(project_id="p", conversation_id="conv") == 1
    barrier = mp.Barrier(2)
    out: Queue[tuple[str, int]] = mp.Queue()
    process = mp.Process(target=_worker_append_once, args=(str(storage), barrier, out))
    process.start()
    barrier.wait(timeout=10)
    _join_process(process)
    assert out.get(timeout=5) == ("ok", 2)

    record = reader.get(project_id="p", conversation_id="conv")
    assert record is not None
    assert record.revision == 2
    assert [message.content for message in record.messages] == ["first turn", "remote second turn"]
    assert reader.get_revision(project_id="p", conversation_id="conv") == 2
    snapshot = reader.snapshot(project_id="p", conversation_id="conv")
    assert (snapshot.revision, snapshot.message_count) == (2, 2)
    out.close()
    out.join_thread()


def test_cached_process_rejects_stale_fork_after_remote_append(tmp_path: Path) -> None:
    storage = _mk_storage(tmp_path, "process-fork")
    _seed(storage)
    reader = _store(storage)
    assert reader.get_revision(project_id="p", conversation_id="conv") == 1
    barrier = mp.Barrier(2)
    out: Queue[tuple[str, int]] = mp.Queue()
    process = mp.Process(target=_worker_append_once, args=(str(storage), barrier, out))
    process.start()
    barrier.wait(timeout=10)
    _join_process(process)
    assert out.get(timeout=5) == ("ok", 2)

    with pytest.raises(StaleConversationRevisionError) as exc_info:
        reader.fork(
            project_id="p",
            source_conversation_id="conv",
            expected_revision=1,
            new_conversation_id="must-not-exist",
        )
    assert exc_info.value.context["current_revision"] == 2
    assert reader.get(project_id="p", conversation_id="must-not-exist") is None
    out.close()
    out.join_thread()


def _worker_create_append(storage: str, barrier: Barrier, out: Queue[tuple[str, int | str]]) -> None:
    store = ConversationStore(storage_dir=storage)
    barrier.wait(timeout=10)
    try:
        snap = store.append(
            project_id="p",
            conversation_id="race",
            expected_revision=0,
            role="user",
            content=f"worker-{PID}",
            create_if_missing=True,
        )
        out.put(("ok", snap.revision))
    except StaleConversationRevisionError as exc:
        current_revision = exc.context["current_revision"]
        assert isinstance(current_revision, int)
        out.put(("stale", current_revision))


def test_concurrent_create_append_single_winner(tmp_path: Path) -> None:
    storage = _mk_storage(tmp_path, "proc")
    barrier = mp.Barrier(2)
    out: Queue[tuple[str, int | str]] = mp.Queue()
    procs = [mp.Process(target=_worker_create_append, args=(str(storage), barrier, out)) for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        _join_process(p)

    results = [out.get(timeout=5), out.get(timeout=5)]
    successes = [r for r in results if r[0] == "ok"]
    stale = [r for r in results if r[0] == "stale"]
    assert len(successes) == 1, results
    assert successes[0][1] == 1
    assert stale == [("stale", 1)]
    final = ConversationStore(storage_dir=storage)
    got = final.get(project_id="p", conversation_id="race")
    assert got is not None
    assert len(got.messages) == len(successes)
    out.close()
    out.join_thread()


def _worker_append_or_compact(
    mode: str,
    storage: str,
    barrier: Barrier,
    out: Queue[tuple[str, int | str]],
) -> None:
    try:
        store = ConversationStore(storage_dir=storage)
        barrier.wait(timeout=10)
        if mode == "append":
            snap = store.append(
                project_id="p",
                conversation_id="race2",
                expected_revision=2,
                role="assistant",
                content="appended",
            )
            out.put(("append-ok", snap.revision))
        else:
            snap = store.compact(
                project_id="p",
                conversation_id="race2",
                expected_revision=2,
                retain_tail=1,
            )
            out.put(("compact-ok", snap.revision))
    except StaleConversationRevisionError as exc:
        current_revision = exc.context["current_revision"]
        assert isinstance(current_revision, int)
        out.put((f"{mode}-stale", current_revision))


def test_append_vs_compact_race_single_cas_winner(tmp_path: Path) -> None:
    storage = _mk_storage(tmp_path, "proc2")
    seed = ConversationStore(storage_dir=storage)
    _ = seed.append(
        project_id="p",
        conversation_id="race2",
        expected_revision=0,
        role="user",
        content="turn one",
    )
    _ = seed.append(
        project_id="p",
        conversation_id="race2",
        expected_revision=1,
        role="assistant",
        content="turn two",
    )
    # both racers start from revision 2
    barrier = mp.Barrier(2)
    out: Queue[tuple[str, int | str]] = mp.Queue()
    procs = [
        mp.Process(target=_worker_append_or_compact, args=("append", str(storage), barrier, out)),
        mp.Process(target=_worker_append_or_compact, args=("compact", str(storage), barrier, out)),
    ]
    for p in procs:
        p.start()
    for p in procs:
        _join_process(p)

    results = [out.get(timeout=5), out.get(timeout=5)]
    oks = [r for r in results if r[0].endswith("-ok")]
    stale = [r for r in results if r[0].endswith("-stale")]
    assert len(oks) == 1, results
    assert oks[0][1] == 3
    assert len(stale) == 1, results
    assert stale[0][1] == 3
    final = ConversationStore(storage_dir=storage)
    got = final.get(project_id="p", conversation_id="race2")
    assert got is not None
    assert got.revision == 3
    out.close()
    out.join_thread()
