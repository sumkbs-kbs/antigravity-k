"""CR-02: session durability — atomic save, unique ids, stale-write rejection.

Covers the fixed contract of plan CR-02:

- C02-01 new session ids are UUID-based (unique within one second) while legacy
  ``{project_hash}_{epoch}`` files still resume/list.
- C02-02 serialization/write/fsync/replace failures before the atomic replace
  keep the last good bytes; a directory-fsync failure after the replace reports
  durability uncertainty with the new complete file already visible.
- C02-03 persistence failures reach the caller (no false success) — including
  the HTTP mapping of ``POST /api/session/save``.
- C02-04 a second writer's save is rejected by revision comparison, not silently
  overwritten; legacy records are read at revision 0 inside the lock.
- C02-05 restart/list/revision still work, temporary residue is cleaned, and
  damaged files are quarantined instead of deleted.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import multiprocessing as mp
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from antigravity_k.api.error_handler import session_persistence_exception_handler
from antigravity_k.api.routes import system_api
from antigravity_k.engine import session_manager as sm_mod
from antigravity_k.engine.session_manager import (
    SessionDurabilityUncertainError,
    SessionManager,
    SessionPersistenceError,
    StaleSessionWriteError,
)

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
    return json.loads(_session_path(manager, session_id).read_text(encoding="utf-8"))


def _start(manager: SessionManager, tmp_path: Path) -> str:
    return manager.start_session(project_path=str(_workspace(tmp_path)), resume=False)


def _temp_residue(manager: SessionManager) -> list[str]:
    return sorted(p.name for p in Path(manager.base_dir).glob("*.tmp"))


def _legacy_project_hash(project_path: Path) -> str:
    return hashlib.sha256(os.path.abspath(str(project_path)).encode()).hexdigest()[:8]


def _write_legacy_session(base_dir: Path, session: dict[str, Any]) -> Path:
    path = base_dir / f"{session['id']}.json"
    base_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _legacy_session_file(project_path: Path, *, project_hash: str | None = None) -> dict[str, Any]:
    now = time.time()
    return {
        "id": f"{project_hash or _legacy_project_hash(project_path)}_{int(now)}",
        "project_path": os.path.abspath(str(project_path)),
        "project_hash": project_hash or _legacy_project_hash(project_path),
        "created_at": now,
        "updated_at": now,
        "turn_count": 2,
        "messages": [{"role": "user", "content": "legacy turn"}],
        "working_memory": {},
        "metadata": {"total_tokens_used": 0, "tools_used": [], "files_modified": [], "ended_at": None},
    }


# ── C02-01: id uniqueness + legacy resume ───────────────────────────────


class TestSessionIdentity:
    def test_ids_are_unique_within_one_second(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fixed = 1_800_000_000.0
        monkeypatch.setattr(sm_mod.time, "time", lambda: fixed)
        manager = _manager(tmp_path)
        ids = [_start(manager, tmp_path) for _ in range(100)]

        assert len(set(ids)) == 100
        for session_id in ids:
            assert _session_path(manager, session_id).is_file()
        # 시간은 metadata일 뿐 식별자가 아니다.
        assert all(not session_id.endswith(str(int(fixed))) for session_id in ids)
        assert len(list(Path(manager.base_dir).glob("*.json"))) == 100

    def test_legacy_ids_still_resume_and_list(self, tmp_path: Path) -> None:
        manager = _manager(tmp_path)
        workspace = _workspace(tmp_path)
        legacy = _legacy_session_file(workspace)
        _write_legacy_session(Path(manager.base_dir), legacy)

        resumed = manager.start_session(project_path=str(workspace), resume=True)

        assert resumed == legacy["id"]
        assert manager.get_messages() == [{"role": "user", "content": "legacy turn"}]
        listed = {entry["id"]: entry for entry in manager.list_sessions()}
        assert legacy["id"] in listed
        assert listed[legacy["id"]]["revision"] == 0  # 구형 레코드는 revision 0

        # 구형 파일을 이어쓰면 revision이 1로 승격된다.
        manager.set_memory("k", "v")
        manager.save()
        assert _payload(manager, legacy["id"])["revision"] == 1

    def test_latest_session_uses_record_metadata_not_filename(self, tmp_path: Path) -> None:
        base = tmp_path / "sessions"
        workspace = _workspace(tmp_path)
        project_hash = _legacy_project_hash(workspace)

        older = _legacy_session_file(workspace, project_hash=project_hash)
        older["id"] = f"{project_hash}_1000000000"  # 시간으로 해석하면 이기는 suffix
        older["updated_at"] = time.time() - 3600
        newer = _legacy_session_file(workspace, project_hash=project_hash)
        newer["id"] = f"{project_hash}_{uuid.uuid4().hex}"
        newer["updated_at"] = time.time()
        _write_legacy_session(base, older)
        _write_legacy_session(base, newer)
        # 파일 mtime을 반대로 만들어도(구형 latest 구현이 보는 값) 메타데이터가 이긴다.
        now = time.time()
        os.utime(base / f"{older['id']}.json", (now, now))
        os.utime(base / f"{newer['id']}.json", (now - 7200, now - 7200))

        manager = SessionManager(base_dir=str(base))

        assert manager.start_session(project_path=str(workspace), resume=True) == newer["id"]
        assert manager._base_revision == 0
        assert manager.get_messages() == [{"role": "user", "content": "legacy turn"}]

    def test_latest_session_ignores_record_from_other_project(self, tmp_path: Path) -> None:
        base = tmp_path / "sessions"
        workspace = _workspace(tmp_path)
        project_hash = _legacy_project_hash(workspace)
        foreign = _legacy_session_file(workspace, project_hash="deadbeef")
        foreign["id"] = f"{project_hash}_{int(time.time())}"  # 파일명은 이 프로젝트
        foreign_path = _write_legacy_session(base, foreign)

        manager = SessionManager(base_dir=str(base))
        fresh = manager.start_session(project_path=str(workspace), resume=True)

        assert fresh != foreign["id"]  # 레코드의 실제 식별자가 다른 파일은 resume 대상이 아니다
        assert manager.get_messages() == []
        assert foreign_path.read_text(encoding="utf-8")  # 남의 파일은 손대지 않는다

    def test_legacy_and_new_ids_coexist_in_list(self, tmp_path: Path) -> None:
        manager = _manager(tmp_path)
        workspace = _workspace(tmp_path)
        legacy = _legacy_session_file(workspace)
        _write_legacy_session(Path(manager.base_dir), legacy)
        fresh = _start(manager, tmp_path)

        ids = {entry["id"] for entry in manager.list_sessions()}
        assert {legacy["id"], fresh} <= ids


# ── C02-02: atomic save + failure preservation ──────────────────────────


class TestAtomicSave:
    def test_serialize_write_replace_and_file_fsync_failures_preserve_last_good_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager = _manager(tmp_path)
        session_id = _start(manager, tmp_path)
        manager.add_turn([{"role": "user", "content": "first"}])
        manager.save()
        before = _session_path(manager, session_id).read_bytes()

        def failing_serialize(_payload: Any) -> str:
            raise RuntimeError("serialize failed (synthetic)")

        def failing_write(_fd: int, _text: str) -> None:
            raise OSError(28, "No space left on device (synthetic)")

        def failing_replace(_source: Path, _destination: Path) -> None:
            raise OSError(5, "replace failed (synthetic)")

        def failing_file_fsync(fd: int) -> None:
            raise OSError(5, "file fsync failed (synthetic)")

        scenarios: list[tuple[str, str, object]] = [
            ("serialize", "_serialize_session", failing_serialize),
            ("write", "_write_session_text", failing_write),
            ("replace", "_replace_file", failing_replace),
            ("file_fsync", "_fsync_fd", failing_file_fsync),
        ]
        for label, target, replacement in scenarios:
            # 자동 저장(5턴)이 루프 밖으로 예외를 흘리지 않도록 턴 수를 고정한다.
            assert manager._current_session is not None
            manager._current_session["turn_count"] = 0
            with monkeypatch.context() as patch:
                patch.setattr(sm_mod, target, replacement)
                with pytest.raises((SessionPersistenceError, RuntimeError, OSError)) as exc:
                    manager.save()
                assert not isinstance(exc.value, StaleSessionWriteError), label
            assert _session_path(manager, session_id).read_bytes() == before, label
            assert _temp_residue(manager) == [], label

    def test_directory_fsync_failure_keeps_new_file_and_reports_uncertainty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager = _manager(tmp_path)
        session_id = _start(manager, tmp_path)
        manager.add_turn([{"role": "user", "content": "first"}])
        manager.save()
        revision_before = _payload(manager, session_id)["revision"]

        calls = {"count": 0}
        original = sm_mod._fsync_fd

        def fsync_fails_on_directory(fd: int) -> None:
            calls["count"] += 1
            if calls["count"] >= 2:  # 1번째는 파일, 2번째는 디렉터리 fsync
                raise OSError(5, "directory fsync failed (synthetic)")
            original(fd)

        with monkeypatch.context() as patch:
            patch.setattr(sm_mod, "_fsync_fd", fsync_fails_on_directory)
            manager.add_turn([{"role": "user", "content": "second"}])
            with pytest.raises(SessionDurabilityUncertainError):
                manager.save()

        # 되돌리지 않는다: 새 완전한 JSON이 이미 보인다.
        payload = _payload(manager, session_id)
        assert payload["revision"] == revision_before + 1
        assert [m["content"] for m in payload["messages"]] == ["first", "second"]
        assert _temp_residue(manager) == []

        # 재조회한 실제 저장 상태를 반영해 다음 저장이 자기 자신과 충돌하지 않는다.
        manager.add_turn([{"role": "user", "content": "third"}])
        manager.save()
        assert _payload(manager, session_id)["revision"] == revision_before + 2

    def test_temp_file_permissions_and_cleanup(self, tmp_path: Path) -> None:
        manager = _manager(tmp_path)
        session_id = _start(manager, tmp_path)
        mode = os.stat(_session_path(manager, session_id)).st_mode & 0o777
        assert mode == 0o600
        assert _temp_residue(manager) == []

    def test_damaged_file_is_quarantined_not_deleted(self, tmp_path: Path) -> None:
        manager = _manager(tmp_path)
        session_id = _start(manager, tmp_path)
        path = _session_path(manager, session_id)
        path.write_bytes(b"")  # 과거 truncate-dump 중단 재현

        manager.add_turn([{"role": "user", "content": "after damage"}])
        manager.save()

        assert _payload(manager, session_id)["revision"] >= 1
        quarantined = list(Path(manager.base_dir).glob("*.corrupt-*"))
        assert len(quarantined) == 1
        assert quarantined[0].read_bytes() == b""
        # 격리 파일은 세션 목록에 나타나지 않는다.
        assert all(entry["id"] != quarantined[0].name for entry in manager.list_sessions())


# ── C02-03: failure propagation ─────────────────────────────────────────


class TestFailurePropagation:
    def test_start_save_end_and_autosave_propagate(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        manager = _manager(tmp_path)

        def failing_replace(_source: Path, _destination: Path) -> None:
            raise OSError(5, "replace failed (synthetic)")

        with monkeypatch.context() as patch:
            patch.setattr(sm_mod, "_replace_file", failing_replace)
            with pytest.raises(SessionPersistenceError):
                _start(manager, tmp_path)
            assert list(Path(manager.base_dir).glob("*.json")) == []

        session_id = _start(manager, tmp_path)
        manager.add_turn([{"role": "user", "content": "1"}])
        manager.save()

        with monkeypatch.context() as patch:
            patch.setattr(sm_mod, "_replace_file", failing_replace)
            with pytest.raises(SessionPersistenceError):
                manager.save()
            with pytest.raises(SessionPersistenceError):
                manager.end_session()
            # 5턴 자동 저장도 실패를 숨기지 않는다(5번 중 어느 턴에서든 경계를 지난다).
            with pytest.raises(SessionPersistenceError):
                for i in range(5):
                    manager.add_turn([{"role": "user", "content": f"auto-{i}"}])

        assert manager._session_id == session_id  # 세션을 비워 재생성하지 않는다
        assert _payload(manager, session_id)["messages"][0]["content"] == "1"

    def test_api_session_save_detail_does_not_leak_internal_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _PathLeakingManager:
            def save(self) -> None:
                raise SessionPersistenceError(f"Session bytes could not be persisted: {tmp_path}/sessions/abc.json")

        monkeypatch.setattr(system_api, "_get_session_manager", _PathLeakingManager)
        with pytest.raises(HTTPException) as raised:
            asyncio.run(system_api.session_save())

        assert raised.value.status_code == 503
        assert raised.value.detail == SessionPersistenceError.public_detail
        assert str(tmp_path) not in str(raised.value.detail)

    def test_api_session_save_maps_stale_and_persistence_failures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _FailingManager:
            def __init__(self, exc: Exception) -> None:
                self._exc = exc

            def save(self) -> None:
                raise self._exc

        for exc, expected in (
            (StaleSessionWriteError("stale (synthetic)"), 409),
            (SessionDurabilityUncertainError("uncertain (synthetic)"), 503),
            (SessionPersistenceError("failed (synthetic)"), 503),
        ):
            monkeypatch.setattr(system_api, "_get_session_manager", lambda exc=exc: _FailingManager(exc))
            with pytest.raises(HTTPException) as raised:
                asyncio.run(system_api.session_save())
            assert raised.value.status_code == expected, exc

    def test_app_handler_maps_session_errors(self) -> None:
        app = FastAPI()
        app.add_exception_handler(SessionPersistenceError, session_persistence_exception_handler)

        @app.get("/stale")
        async def stale() -> None:
            raise StaleSessionWriteError("stale (synthetic)")

        @app.get("/broken")
        async def broken() -> None:
            raise SessionDurabilityUncertainError("uncertain (synthetic)")

        client = TestClient(app, raise_server_exceptions=False)
        stale_response = client.get("/stale")
        broken_response = client.get("/broken")

        assert stale_response.status_code == 409
        assert stale_response.json()["error"] == "stale_session_write"
        assert broken_response.status_code == 503
        assert broken_response.json()["error"] == "session_durability_uncertain"
        assert "synthetic" not in broken_response.text  # 내부 메시지 미노출


# ── C02-04: stale write rejection ───────────────────────────────────────


def _child_save(base_dir: str, project_path: str, content: str, out: Any) -> None:
    manager = SessionManager(base_dir=base_dir)
    session_id = manager.start_session(project_path=project_path, resume=True)
    manager.add_turn([{"role": "user", "content": content}])
    manager.save()
    out.put((session_id, "ok"))


class TestStaleWrites:
    def test_second_writer_in_one_process_is_rejected(self, tmp_path: Path) -> None:
        first = _manager(tmp_path)
        session_id = _start(first, tmp_path)
        first.add_turn([{"role": "user", "content": "first"}])
        first.save()

        second = _manager(tmp_path)
        assert second.start_session(project_path=str(_workspace(tmp_path)), resume=True) == session_id
        second.add_turn([{"role": "user", "content": "second"}])
        second.save()

        first.add_turn([{"role": "user", "content": "stale"}])
        with pytest.raises(StaleSessionWriteError):
            first.save()

        # 승자 내용이 보존되고 stale 쓰기는 반영되지 않는다.
        messages = [m["content"] for m in _payload(first, session_id)["messages"]]
        assert messages == ["first", "second"]

    def test_legacy_record_starts_at_revision_zero(self, tmp_path: Path) -> None:
        workspace = _workspace(tmp_path)
        base = tmp_path / "sessions"
        legacy = _legacy_session_file(workspace)
        _write_legacy_session(base, legacy)

        first = SessionManager(base_dir=str(base))
        second = SessionManager(base_dir=str(base))
        assert first.start_session(project_path=str(workspace), resume=True) == legacy["id"]
        assert second.start_session(project_path=str(workspace), resume=True) == legacy["id"]
        assert first._base_revision == 0 and second._base_revision == 0

        first.set_memory("a", 1)
        first.save()
        second.set_memory("b", 2)
        with pytest.raises(StaleSessionWriteError):
            second.save()

    def test_multiprocess_stale_save_is_rejected(self, tmp_path: Path) -> None:
        manager = _manager(tmp_path)
        session_id = _start(manager, tmp_path)
        manager.add_turn([{"role": "user", "content": "parent"}])
        manager.save()

        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
        child = ctx.Process(
            target=_child_save,
            args=(manager.base_dir, str(_workspace(tmp_path)), "child", queue),
        )
        child.start()
        child.join(timeout=60)
        assert child.exitcode == 0
        assert queue.get(timeout=5) == (session_id, "ok")

        manager.add_turn([{"role": "user", "content": "stale-parent"}])
        with pytest.raises(StaleSessionWriteError):
            manager.save()

        payload = _payload(manager, session_id)
        assert [m["content"] for m in payload["messages"]] == ["parent", "child"]


# ── C02-05: restart / list / residue ────────────────────────────────────


class TestRestartAndListing:
    def test_restart_resumes_latest_revision_and_lists_without_residue(self, tmp_path: Path) -> None:
        manager = _manager(tmp_path)
        session_id = _start(manager, tmp_path)
        manager.add_turn([{"role": "user", "content": "turn"}])
        manager.save()
        revision = _payload(manager, session_id)["revision"]

        restarted = _manager(tmp_path)
        assert restarted.start_session(project_path=str(_workspace(tmp_path)), resume=True) == session_id
        assert restarted._base_revision == revision
        assert restarted.get_messages()[0]["content"] == "turn"

        listed = {entry["id"]: entry for entry in restarted.list_sessions()}
        assert listed[session_id]["revision"] == revision
        assert _temp_residue(restarted) == []
        # 잠금 디렉터리는 세션 JSON으로 취급되지 않는다.
        assert all(not entry["id"].startswith(".locks") for entry in restarted.list_sessions())
        assert (Path(restarted.base_dir) / ".locks").is_dir()

    def test_save_after_restart_continues_revision(self, tmp_path: Path) -> None:
        manager = _manager(tmp_path)
        session_id = _start(manager, tmp_path)
        manager.save()
        first_revision = _payload(manager, session_id)["revision"]

        restarted = _manager(tmp_path)
        restarted.start_session(project_path=str(_workspace(tmp_path)), resume=True)
        restarted.add_turn([{"role": "user", "content": "after restart"}])
        restarted.save()

        assert _payload(restarted, session_id)["revision"] == first_revision + 1
        assert _temp_residue(restarted) == []
