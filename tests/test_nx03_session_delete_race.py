"""NX-03: a deleted session must not come back through a stale writer.

Reproduced defect (baseline ffb0ebb, see
``docs/qa/2026-09-16-followup/nx03/before-run-output.json.txt``): ``clear_memory("all")``
unlinked session JSONs with no deletion marker, so an already-loaded writer (B)
found no disk revision and wrote the deleted payload back as revision 1
(``resurrected: true``).

Fixed contract asserted here:

* deletion is durable (tombstone with a session generation) and happens under the
  same per-session lock the writers use,
* a writer whose snapshot predates the deletion cannot recreate that id,
* a file that disappeared without a tombstone is a stale write, not a new session,
* deletions interrupted by an unlink/disk failure are never reported as success and
  their residue is not visible as a session,
* scoped clears (session/working/project/global) do not delete the session.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import multiprocessing as mp
import os
import time
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from antigravity_k.api.error_handler import session_persistence_exception_handler
from antigravity_k.api.routes import system_api
from antigravity_k.engine import session_manager as sm_mod
from antigravity_k.engine.session_manager import (
    SESSION_TOMBSTONE_DIR_NAME,
    SessionDeletedError,
    SessionManager,
    SessionPersistenceError,
    StaleSessionWriteError,
)

MARKER = "SYNTHETIC-DELETED-MARKER"
WORKSPACE_NAME = "workspace"


def _manager(tmp_path: Path, name: str = "sessions") -> SessionManager:
    return SessionManager(base_dir=str(tmp_path / name))


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / WORKSPACE_NAME
    workspace.mkdir(exist_ok=True)
    return workspace


def _session_path(manager: SessionManager, session_id: str) -> Path:
    return Path(manager.base_dir) / f"{session_id}.json"


def _payload(manager: SessionManager, session_id: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_session_path(manager, session_id).read_text(encoding="utf-8")))


def _marker_on_disk(manager: SessionManager) -> bool:
    for path in Path(manager.base_dir).rglob("*.json"):
        if MARKER in path.read_text(encoding="utf-8"):
            return True
    return False


def _start_manager_with_marker(tmp_path: Path, content: str = MARKER) -> tuple[SessionManager, str]:
    manager = _manager(tmp_path)
    session_id = manager.start_session(project_path=str(_workspace(tmp_path)), resume=False)
    manager.add_turn([{"role": "user", "content": content}])
    manager.save()
    return manager, session_id


# ── A. 두 인스턴스 순차 repro ───────────────────────────────────────────


class TestSequentialResurrection:
    def test_stale_writer_cannot_recreate_deleted_session(self, tmp_path: Path) -> None:
        a, session_id = _start_manager_with_marker(tmp_path)
        b = _manager(tmp_path)
        assert b.start_session(project_path=str(_workspace(tmp_path)), resume=True) == session_id

        assert a.clear_memory("all") == 1
        assert not _session_path(a, session_id).exists()

        b.add_turn([{"role": "user", "content": "stale-writer-turn"}])
        with pytest.raises(SessionDeletedError):
            b.save()

        assert not _session_path(b, session_id).exists()
        assert not _marker_on_disk(b)

        restarted = _manager(tmp_path)
        fresh = restarted.start_session(project_path=str(_workspace(tmp_path)), resume=True)
        assert fresh != session_id  # 삭제된 ID는 묵시적으로 재사용하지 않는다
        assert restarted.get_messages() == []
        assert not _marker_on_disk(restarted)

    def test_save_failure_does_not_leave_a_partial_session(self, tmp_path: Path) -> None:
        a, session_id = _start_manager_with_marker(tmp_path)
        b = _manager(tmp_path)
        _ = b.start_session(project_path=str(_workspace(tmp_path)), resume=True)
        _ = a.clear_memory("all")

        for _ in range(3):
            with pytest.raises(SessionDeletedError):
                b.save()
        assert not _session_path(b, session_id).exists()

    def test_missing_file_without_tombstone_is_a_stale_write(self, tmp_path: Path) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        # tombstone 없는 소실(외부 삭제/구버전 삭제) — 신규 생성이 아니라 stale이다.
        _session_path(manager, session_id).unlink()

        with pytest.raises(StaleSessionWriteError):
            manager.save()
        assert not _session_path(manager, session_id).exists()


# ── B. barrier 를 둔 두 프로세스 경쟁 (양 순서) ──────────────────────────


def _child_delete_after_barrier(base_dir: str, barrier: Any, deleted: Any, out: Any) -> None:
    manager = SessionManager(base_dir=base_dir)
    barrier.wait(timeout=30)
    deleted_count = manager.clear_memory("all")
    deleted.set()
    out.put(("deleted", deleted_count))


def _child_stale_save_after_signal(base_dir: str, barrier: Any, deleted: Any, out: Any) -> None:
    manager = SessionManager(base_dir=base_dir)
    loaded = manager.start_session(project_path=os.environ["NX03_WORKSPACE"], resume=True)
    barrier.wait(timeout=30)
    deleted.wait(timeout=30)
    manager.add_turn([{"role": "user", "content": "stale-child-turn"}])
    try:
        manager.save()
        out.put(("saved", loaded))
    except SessionDeletedError:
        out.put(("refused", loaded))


def _child_save_then_wait_then_save(base_dir: str, barrier: Any, deleted: Any, out: Any) -> None:
    manager = SessionManager(base_dir=base_dir)
    loaded = manager.start_session(project_path=os.environ["NX03_WORKSPACE"], resume=True)
    manager.add_turn([{"role": "user", "content": "first-child-turn"}])
    barrier.wait(timeout=30)
    manager.save()
    out.put(("first_saved", loaded))
    deleted.wait(timeout=30)
    manager.add_turn([{"role": "user", "content": "second-child-turn"}])
    try:
        manager.save()
        out.put(("second_saved", loaded))
    except SessionDeletedError:
        out.put(("second_refused", loaded))


class TestMultiprocessRace:
    def test_delete_wins_then_stale_process_save_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        monkeypatch.setenv("NX03_WORKSPACE", str(_workspace(tmp_path)))

        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(2)
        deleted = ctx.Event()
        queue = ctx.Queue()
        child = ctx.Process(
            target=_child_stale_save_after_signal,
            args=(manager.base_dir, barrier, deleted, queue),
        )
        deleter = ctx.Process(
            target=_child_delete_after_barrier,
            args=(manager.base_dir, barrier, deleted, queue),
        )
        child.start()
        deleter.start()
        results = [queue.get(timeout=60) for _ in range(2)]
        for process in (child, deleter):
            process.join(timeout=60)
            assert process.exitcode == 0

        assert ("deleted", 1) in results
        assert ("refused", session_id) in results
        assert not _session_path(manager, session_id).exists()
        assert not _marker_on_disk(manager)

    def test_save_wins_then_delete_still_blocks_the_next_save(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        monkeypatch.setenv("NX03_WORKSPACE", str(_workspace(tmp_path)))

        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(2)
        deleted = ctx.Event()
        queue = ctx.Queue()
        child = ctx.Process(
            target=_child_save_then_wait_then_save,
            args=(manager.base_dir, barrier, deleted, queue),
        )
        child.start()
        barrier.wait(timeout=60)  # 부모도 barrier에 참여해야 자식이 진행한다
        assert queue.get(timeout=60) == ("first_saved", session_id)
        # 자식의 첫 저장이 반영된 뒤 삭제한다(현재 세션은 메모리 스냅샷으로만 집계된다).
        assert manager.clear_memory("all") == 1
        deleted.set()
        assert queue.get(timeout=60) == ("second_refused", session_id)
        child.join(timeout=60)
        assert child.exitcode == 0

        assert not _session_path(manager, session_id).exists()
        assert not _marker_on_disk(manager)


# ── C. 삭제 후 kill9 / restart / 중단 재개 ──────────────────────────────


def _child_delete_then_hard_exit(base_dir: str) -> None:
    manager = SessionManager(base_dir=base_dir)
    manager.clear_memory("all")
    # kill -9 근사: queue flush/정리 없이 즉시 종료(부모는 부작용으로 판정한다).
    os._exit(17)


class TestRestartAndInterruptedDelete:
    def test_hard_exit_after_delete_is_durable_and_not_resumable(self, tmp_path: Path) -> None:
        _manager_, session_id = _start_manager_with_marker(tmp_path)
        base_dir = str(tmp_path / "sessions")

        ctx = mp.get_context("spawn")
        child = ctx.Process(target=_child_delete_then_hard_exit, args=(base_dir,))
        child.start()
        child.join(timeout=60)
        assert child.exitcode == 17
        assert not _session_path(SessionManager(base_dir=base_dir), session_id).exists()
        tombstones = list((Path(base_dir) / SESSION_TOMBSTONE_DIR_NAME).glob("*.json"))
        assert [t.stem for t in tombstones] == [session_id]

        restarted = SessionManager(base_dir=base_dir)
        assert restarted.list_sessions() == []
        fresh = restarted.start_session(project_path=str(_workspace(tmp_path)), resume=True)
        assert fresh != session_id
        assert restarted.get_messages() == []
        assert not _marker_on_disk(restarted)

    def test_unlink_failure_is_not_reported_as_success_and_residue_is_hidden(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        path = _session_path(manager, session_id)

        def failing_unlink(_path: Path) -> None:
            raise OSError(13, "unlink failed (synthetic)")

        with monkeypatch.context() as patch:
            patch.setattr(sm_mod, "_unlink_session_file", failing_unlink)
            with pytest.raises(SessionPersistenceError):
                manager.clear_memory("all")

        # 삭제 성공으로 보고하지 않았고, 파일은 남아 있다(데이터 손실 없음).
        assert path.is_file()
        # 표식이 남아 잔재는 가시 세션이 아니다.
        assert manager.list_sessions() == []
        resumed = _manager(tmp_path)
        assert resumed.start_session(project_path=str(_workspace(tmp_path)), resume=True) != session_id
        assert resumed.get_messages() == []

        # 재시도가 잔재를 제거한다(이 시점 집계는 파일에 남아 있던 항목 수).
        retried = _manager(tmp_path)
        assert retried.clear_memory("all") == 1
        assert not path.exists()
        assert retried.clear_memory("all") == 0

    def test_tombstone_write_failure_keeps_the_file_and_reports_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        before = _session_path(manager, session_id).read_bytes()

        calls = {"count": 0}
        original = sm_mod._fsync_fd

        def failing_directory_fsync(fd: int) -> None:
            calls["count"] += 1
            raise OSError(5, "fsync failed (synthetic)")

        with monkeypatch.context() as patch:
            patch.setattr(sm_mod, "_fsync_fd", failing_directory_fsync)
            with pytest.raises(SessionPersistenceError):
                manager.clear_memory("all")
            _ = original

        assert _session_path(manager, session_id).read_bytes() == before  # 원본 보존


# ── D. 두 번 delete / scope 분리 / legacy ──────────────────────────────


class TestDeleteIdempotenceAndScopes:
    def test_second_delete_is_a_noop(self, tmp_path: Path) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        assert manager.clear_memory("all") == 1
        assert manager.clear_memory("all") == 0  # 두 번 delete
        tombstones = list((Path(manager.base_dir) / SESSION_TOMBSTONE_DIR_NAME).glob("*.json"))
        assert len(tombstones) == 1
        assert not _session_path(manager, session_id).exists()

    def test_scoped_clears_keep_the_session_and_other_memory(self, tmp_path: Path) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path, content="scoped-turn")
        manager.set_memory("keep", "value")

        deleted = manager.clear_memory("working")
        assert deleted == 1
        assert manager.get_messages()[0]["content"] == "scoped-turn"
        assert not (Path(manager.base_dir) / SESSION_TOMBSTONE_DIR_NAME).exists()

        _ = manager.clear_memory("session")
        assert manager.get_messages() == []
        assert _payload(manager, session_id)["working_memory"] == {}
        assert not (Path(manager.base_dir) / SESSION_TOMBSTONE_DIR_NAME).exists()

        assert manager.clear_memory("project") == 0
        assert manager.clear_memory("global") == 0
        assert _session_path(manager, session_id).is_file()

    def test_unknown_scope_is_rejected(self, tmp_path: Path) -> None:
        manager, _session_id = _start_manager_with_marker(tmp_path)
        with pytest.raises(ValueError):
            manager.clear_memory("everything")

    def test_legacy_record_delete_blocks_legacy_writer(self, tmp_path: Path) -> None:
        base = tmp_path / "sessions"
        base.mkdir(parents=True, exist_ok=True)
        workspace = _workspace(tmp_path)
        project_hash = hashlib.sha256(os.path.abspath(str(workspace)).encode()).hexdigest()[:8]
        legacy_id = f"{project_hash}_{int(time.time())}"
        legacy = {
            "id": legacy_id,
            "project_path": str(workspace),
            "project_hash": project_hash,
            "created_at": time.time(),
            "updated_at": time.time(),
            "turn_count": 1,
            "messages": [{"role": "user", "content": MARKER}],
            "working_memory": {},
            "metadata": {"total_tokens_used": 0, "tools_used": [], "files_modified": [], "ended_at": None},
        }
        (base / f"{legacy_id}.json").write_text(json.dumps(legacy), encoding="utf-8")

        legacy_writer = SessionManager(base_dir=str(base))
        assert legacy_writer.start_session(project_path=str(workspace), resume=True) == legacy_id
        assert legacy_writer._base_generation == 0  # 구형 레코드

        deleter = SessionManager(base_dir=str(base))
        assert deleter.clear_memory("all") == 1  # 디스크에 있던 메시지 1건

        legacy_writer.add_turn([{"role": "user", "content": "legacy stale"}])
        with pytest.raises(SessionDeletedError):
            legacy_writer.save()
        assert not (base / f"{legacy_id}.json").exists()

    def test_retention_deletion_also_writes_a_tombstone(self, tmp_path: Path) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        other = SessionManager(base_dir=manager.base_dir)
        old_id = other.start_session(project_path=str(_workspace(tmp_path) / "other"), resume=False)
        other.add_turn([{"role": "user", "content": MARKER}])
        other.save()
        old_path = Path(manager.base_dir) / f"{old_id}.json"
        stale = time.time() - 3 * 86400
        os.utime(old_path, (stale, stale))
        stale_writer = SessionManager(base_dir=manager.base_dir)
        stale_writer.start_session(project_path=str(_workspace(tmp_path) / "other"), resume=True)

        # apply_retention 은 다른 세션만 지운다(현재 세션 보호).
        assert SessionManager(base_dir=manager.base_dir).apply_retention(1) == 1
        assert not old_path.exists()
        assert _session_path(manager, session_id).exists()

        stale_writer.add_turn([{"role": "user", "content": "after retention"}])
        with pytest.raises(SessionDeletedError):
            stale_writer.save()


# ── E. API/UI 의미 전달 ─────────────────────────────────────────────────


class TestApiSurface:
    def test_session_save_maps_delete_to_409(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _DeletedManager:
            def save(self) -> None:
                raise SessionDeletedError("deleted (synthetic)")

        monkeypatch.setattr(system_api, "_get_session_manager", _DeletedManager)
        with pytest.raises(HTTPException) as raised:
            asyncio.run(system_api.session_save())

        assert raised.value.status_code == 409
        assert raised.value.detail == SessionDeletedError.public_detail

    def test_app_handler_maps_session_deleted(self) -> None:
        app = FastAPI()
        app.add_exception_handler(SessionPersistenceError, session_persistence_exception_handler)

        @app.get("/deleted")
        async def deleted(_request: Request) -> None:
            raise SessionDeletedError("deleted (synthetic)")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/deleted")

        assert response.status_code == 409
        assert response.json()["error"] == "session_deleted"
        assert "synthetic" not in response.text  # 내부 메시지 미노출

    def test_tombstone_has_no_session_body_or_secret(self, tmp_path: Path) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path, content="USER-SECRET-CONTENT")
        manager.set_memory("pin", "1234")
        _ = manager.clear_memory("all")

        tombstone = Path(manager.base_dir) / SESSION_TOMBSTONE_DIR_NAME / f"{session_id}.json"
        text = tombstone.read_text(encoding="utf-8")
        assert "USER-SECRET-CONTENT" not in text
        assert "1234" not in text
        data = json.loads(text)
        assert data["schema"] == sm_mod.SESSION_TOMBSTONE_SCHEMA
        assert data["session_id"] == session_id
        assert data["generation"] >= 1

    def test_generation_is_persisted_and_upgraded_from_legacy(self, tmp_path: Path) -> None:
        manager, session_id = _start_manager_with_marker(tmp_path)
        first = _payload(manager, session_id)
        assert first["generation"] == 1
        manager.add_turn([{"role": "user", "content": "second"}])
        manager.save()
        assert _payload(manager, session_id)["generation"] == 1  # 저장해도 세대는 유지
        restarted = _manager(tmp_path)
        assert restarted.start_session(project_path=str(_workspace(tmp_path)), resume=True) == session_id
        assert restarted._base_generation == 1
