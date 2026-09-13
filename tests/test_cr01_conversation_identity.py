"""CR-01: conversation identity collisions, integrity errors, v2 migration.

Covers the fixed contract of plan CR-01:

- C01-01 raw ids that used to collide (``a.b``/``a_b``, spaces, 64-char prefix,
  case-insensitive filesystems) are separate conversations.
- C01-02 the real API keeps per-identity revisions, and corrupt/mismatched
  bytes surface as ``conversation_integrity_error`` instead of an empty read.
- C01-03 the one-time migration is a no-write dry-run, preserves originals, and
  is idempotent when re-run.
- C01-04 conflicting/corrupt sources are refused without a completion marker.
- C01-05 multi-process CAS still holds on the v2 layout across a restart.
- C01-06 the documented backup can restore the previous state.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from antigravity_k.api.contracts.errors import (
    ConversationIntegrityError,
    ConversationStorageMigrationRequiredError,
    StaleConversationRevisionError,
)
from antigravity_k.api.routes import conversation_api
from antigravity_k.engine import conversation_store as cs
from antigravity_k.engine.conversation_store import (
    ConversationStore,
    conversation_identity_digest,
    reset_conversation_store_for_tests,
)
from antigravity_k.engine.project_registry import ProjectRegistry

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_conversation_storage.py"

COLLISION_PAIRS: list[tuple[str, str, str]] = [
    ("dot vs underscore", "a.b", "a_b"),
    ("space vs underscore", "a b", "a_b"),
    ("64-char prefix truncation", "x" * 64 + "A", "x" * 64 + "B"),
    ("case-insensitive filesystem", "Conv", "conv"),
]


def _legacy_record(project_id: str, conversation_id: str, content: str, revision: int = 1) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "project_id": project_id,
        "revision": revision,
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
        "forked_from": None,
        "created_at": 1.0,
        "updated_at": 1.0,
    }


def _write_legacy(storage: Path, project_dir: str, file_name: str, record: dict[str, Any]) -> Path:
    path = storage / project_dir / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_migration(storage: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    report_path = storage.parent / f"report-{len(list(storage.parent.glob('report-*.json')))}.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--storage-dir",
            str(storage),
            "--report",
            str(report_path),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return completed.returncode, report


def _dir_fingerprint(root: Path) -> dict[str, str]:
    fingerprint: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            fingerprint[str(path.relative_to(root))] = f"{path.stat().st_size}:{path.stat().st_mtime_ns}"
    return fingerprint


# ── C01-01: distinct identities ─────────────────────────────────────────


class TestIdentitySeparation:
    @pytest.mark.parametrize(("label", "first_id", "second_id"), COLLISION_PAIRS)
    def test_colliding_ids_stay_separate(self, tmp_path: Path, label: str, first_id: str, second_id: str) -> None:
        store = ConversationStore(storage_dir=tmp_path / "conversations")
        store.append(
            project_id="p",
            conversation_id=first_id,
            expected_revision=0,
            role="user",
            content=f"content-for::{first_id}",
        )

        assert store._path_for("p", first_id) != store._path_for("p", second_id), label
        assert store.get(project_id="p", conversation_id=second_id) is None, label

        store.append(
            project_id="p",
            conversation_id=second_id,
            expected_revision=0,
            role="user",
            content=f"content-for::{second_id}",
        )
        first = store.get(project_id="p", conversation_id=first_id)
        second = store.get(project_id="p", conversation_id=second_id)
        assert first is not None and second is not None
        assert first.messages[0].content == f"content-for::{first_id}"
        assert second.messages[0].content == f"content-for::{second_id}"

    def test_korean_ids_are_hashed_not_mangled(self, tmp_path: Path) -> None:
        store = ConversationStore(storage_dir=tmp_path / "conversations")
        store.append(project_id="한글", conversation_id="대화", expected_revision=0, role="user", content="안녕")
        record = store.get(project_id="한글", conversation_id="대화")
        assert record is not None
        assert record.project_id == "한글"
        assert record.conversation_id == "대화"
        assert store.get(project_id="한글", conversation_id="대화_") is None

    def test_storage_path_is_full_sha256_of_raw_ids(self, tmp_path: Path) -> None:
        store = ConversationStore(storage_dir=tmp_path / "conversations")
        store.append(project_id="p", conversation_id="a.b", expected_revision=0, role="user", content="x")
        expected = (
            tmp_path
            / "conversations"
            / "v2"
            / conversation_identity_digest("p")
            / f"{conversation_identity_digest('a.b')}.json"
        )
        assert store._path_for("p", "a.b") == expected
        assert expected.is_file()

    def test_identity_mismatch_raises_integrity_error(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        store = ConversationStore(storage_dir=storage)
        store.append(project_id="p", conversation_id="conv", expected_revision=0, role="user", content="mine")

        # Simulate a record written under the wrong identity (old-format bug).
        target = store._path_for("p", "other")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(_legacy_record("p", "conv", "stolen")), encoding="utf-8")

        with pytest.raises(ConversationIntegrityError) as exc:
            _ = store.get(project_id="p", conversation_id="other")
        assert exc.value.error_code == "conversation_integrity_error"
        assert exc.value.context["reason"] == "identity_mismatch"

    def test_corrupt_bytes_raise_integrity_error(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        store = ConversationStore(storage_dir=storage)
        store.append(project_id="p", conversation_id="conv", expected_revision=0, role="user", content="mine")
        store._path_for("p", "conv").write_text("{ not json", encoding="utf-8")

        with pytest.raises(ConversationIntegrityError):
            _ = store.get(project_id="p", conversation_id="conv")


# ── C01-02: real API identity / revision / integrity ────────────────────


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    fresh = cs.ConversationStore(storage_dir=tmp_path / "conversations")
    reset_conversation_store_for_tests(fresh)

    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    root = tmp_path / "proj"
    root.mkdir()
    record = registry.add_project(name="CR01", path=str(root))
    monkeypatch.setattr("antigravity_k.api.project_binding.get_project_registry", lambda: registry)
    monkeypatch.setattr("antigravity_k.engine.request_execution_context.get_project_registry", lambda: registry)
    monkeypatch.setattr("antigravity_k.config.config.paths.project_root", tmp_path.resolve())
    monkeypatch.setenv("AGK_ALLOWED_ROOTS", str(tmp_path.resolve()))

    app = FastAPI()
    from antigravity_k.api.error_handler import APIError, global_exception_handler

    app.add_exception_handler(APIError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(conversation_api.router)
    test = TestClient(app, raise_server_exceptions=False)
    test.project_id = record.id  # type: ignore[attr-defined]
    return test


def test_api_keeps_colliding_conversations_isolated(client: TestClient) -> None:
    pid = client.project_id  # type: ignore[attr-defined]
    append = client.post(
        "/v1/conversations/append",
        json={
            "project_id": pid,
            "conversation_id": "a.b",
            "expected_revision": 0,
            "role": "user",
            "content": "first",
        },
    )
    assert append.status_code == 200, append.text
    assert append.json()["revision"] == 1

    other = client.get(f"/v1/conversations/a_b?project_id={pid}")
    assert other.status_code == 404
    assert other.json()["error"] == "conversation_not_found"

    second = client.post(
        "/v1/conversations/append",
        json={"project_id": pid, "conversation_id": "a_b", "expected_revision": 0, "role": "user", "content": "second"},
    )
    assert second.status_code == 200
    assert second.json()["revision"] == 1

    fetched = client.get(f"/v1/conversations/a.b?project_id={pid}")
    assert fetched.status_code == 200
    assert fetched.json()["snapshot"]["conversation_id"] == "a.b"
    assert fetched.json()["messages"][0]["content"] == "first"

    # Case-only difference also stays separate through the API.
    upper = client.post(
        "/v1/conversations/append",
        json={"project_id": pid, "conversation_id": "Conv", "expected_revision": 0, "role": "user", "content": "upper"},
    )
    lower = client.post(
        "/v1/conversations/append",
        json={"project_id": pid, "conversation_id": "conv", "expected_revision": 0, "role": "user", "content": "lower"},
    )
    assert upper.status_code == 200 and lower.status_code == 200
    assert client.get(f"/v1/conversations/conv?project_id={pid}").json()["messages"][0]["content"] == "lower"


def test_api_compact_and_revision_isolation(client: TestClient) -> None:
    pid = client.project_id  # type: ignore[attr-defined]
    payload = {"project_id": pid, "conversation_id": "a.b", "expected_revision": 0, "role": "user", "content": "seed"}
    assert client.post("/v1/conversations/append", json=payload).status_code == 200
    other = dict(payload, conversation_id="a_b", expected_revision=0, content="seed-other")
    assert client.post("/v1/conversations/append", json=other).status_code == 200

    compact = client.post(
        "/v1/conversations/compact",
        json={"project_id": pid, "conversation_id": "a.b", "expected_revision": 1, "retain_tail": 0},
    )
    assert compact.status_code == 200, compact.text
    assert compact.json()["conversation_id"] == "a.b"
    assert compact.json()["revision"] == 2

    untouched = client.get(f"/v1/conversations/a_b?project_id={pid}")
    assert untouched.status_code == 200
    assert untouched.json()["snapshot"]["revision"] == 1
    assert untouched.json()["messages"][0]["content"] == "seed-other"

    stale = client.post(
        "/v1/conversations/append",
        json={"project_id": pid, "conversation_id": "a.b", "expected_revision": 1, "role": "user", "content": "stale"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == "stale_conversation_revision"


def test_api_surfaces_integrity_error_instead_of_empty_conversation(client: TestClient) -> None:
    pid = client.project_id  # type: ignore[attr-defined]
    payload = {"project_id": pid, "conversation_id": "a.b", "expected_revision": 0, "role": "user", "content": "seed"}
    assert client.post("/v1/conversations/append", json=payload).status_code == 200

    store = cs.get_conversation_store()
    store._path_for(pid, "a.b").write_text("{ corrupted", encoding="utf-8")

    response = client.get(f"/v1/conversations/a.b?project_id={pid}")
    assert response.status_code == 409
    assert response.json()["error"] == "conversation_integrity_error"


# ── C01-03 / C01-04: one-time migration ─────────────────────────────────


class TestMigration:
    def test_dry_run_writes_nothing_and_apply_is_idempotent(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        storage.mkdir()
        _write_legacy(storage, "proj_a", "a_b.json", _legacy_record("p", "a.b", "legacy-a"))
        _write_legacy(storage, "proj_a", "other.json", _legacy_record("p", "other", "legacy-b"))

        before = _dir_fingerprint(storage)
        code, report = _run_migration(storage)
        assert code == 0
        assert report["state"] == "dry_run"
        assert report["marker_written"] is False
        assert _dir_fingerprint(storage) == before

        code, report = _run_migration(storage, "--apply")
        assert code == 0, report
        assert report["state"] == "applied"
        assert report["marker_written"] is True
        assert (storage / "v2").is_dir()
        assert (storage / "migration_v2.json").is_file()
        # originals preserved
        assert (storage / "proj_a" / "a_b.json").is_file()
        assert (storage / "proj_a" / "other.json").is_file()

        store = ConversationStore(storage_dir=storage)
        record = store.get(project_id="p", conversation_id="a.b")
        assert record is not None and record.messages[0].content == "legacy-a"

        migrated = _dir_fingerprint(storage)
        code, report = _run_migration(storage, "--apply")
        assert code == 0
        assert report["state"] == "already_migrated"
        assert report["marker_written"] is False
        assert _dir_fingerprint(storage) == migrated

    def test_apply_without_marker_does_not_rewrite_identical_targets(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        storage.mkdir()
        _write_legacy(storage, "proj_a", "conv.json", _legacy_record("p", "conv", "legacy"))
        code, _ = _run_migration(storage, "--apply")
        assert code == 0
        target = storage / "v2" / conversation_identity_digest("p") / f"{conversation_identity_digest('conv')}.json"
        stamp = target.stat().st_mtime_ns

        (storage / "migration_v2.json").unlink()  # simulate an interrupted apply
        code, report = _run_migration(storage, "--apply")
        assert code == 0, report
        assert report["state"] == "applied"
        assert report["planned"][0]["action"] == "already_present"
        assert target.stat().st_mtime_ns == stamp

    def test_conflicting_sources_are_refused_without_marker(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        storage.mkdir()
        _write_legacy(storage, "proj_a", "first.json", _legacy_record("p", "conv", "one", revision=1))
        _write_legacy(storage, "proj_b", "second.json", _legacy_record("p", "conv", "two", revision=2))

        before = _dir_fingerprint(storage)
        code, report = _run_migration(storage, "--apply")
        assert code == 2
        assert report["state"] == "blocked_conflicts"
        assert report["conflicts"][0]["kind"] == "identity_duplicate"
        assert not (storage / "migration_v2.json").exists()
        assert not (storage / "v2").exists()
        assert _dir_fingerprint(storage) == before

    def test_corrupt_source_is_refused_without_marker(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        storage.mkdir()
        _write_legacy(storage, "proj_a", "conv.json", _legacy_record("p", "conv", "ok"))
        (storage / "proj_a" / "broken.json").write_text("{ nope", encoding="utf-8")

        code, report = _run_migration(storage, "--apply")
        assert code == 2
        assert [c["kind"] for c in report["conflicts"]] == ["corrupt"]
        assert not (storage / "migration_v2.json").exists()

    def test_store_refuses_reads_and_writes_until_migrated(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        storage.mkdir()
        _write_legacy(storage, "proj_a", "conv.json", _legacy_record("p", "conv", "legacy"))
        store = ConversationStore(storage_dir=storage)

        assert store.storage_layout_state() == "legacy_requires_migration"
        with pytest.raises(ConversationStorageMigrationRequiredError) as exc:
            _ = store.get(project_id="p", conversation_id="conv")
        assert exc.value.error_code == "conversation_storage_migration_required"
        with pytest.raises(ConversationStorageMigrationRequiredError):
            _ = store.append(project_id="p", conversation_id="conv", expected_revision=0, role="user", content="new")
        assert not (storage / "v2").exists()

        code, _ = _run_migration(storage, "--apply")
        assert code == 0
        store.refresh_storage_layout()
        assert store.storage_layout_state() == "v2"
        record = store.get(project_id="p", conversation_id="conv")
        assert record is not None and record.revision == 1

    def test_verify_only_reports_completed_state(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        storage.mkdir()
        _write_legacy(storage, "proj_a", "conv.json", _legacy_record("p", "conv", "legacy"))

        code, report = _run_migration(storage, "--verify-only")
        assert code == 2
        assert report["state"] == "not_verified"

        assert _run_migration(storage, "--apply")[0] == 0
        code, report = _run_migration(storage, "--verify-only")
        assert code == 0, report
        assert report["state"] == "verified"

    def test_backup_restore_returns_to_previous_state(self, tmp_path: Path) -> None:
        storage = tmp_path / "conversations"
        storage.mkdir()
        original = _write_legacy(storage, "proj_a", "conv.json", _legacy_record("p", "conv", "legacy"))
        original_bytes = original.read_bytes()
        backup = tmp_path / "backup"

        code, report = _run_migration(storage, "--apply", "--backup-dir", str(backup))
        assert code == 0, report
        assert report["backup_dir"] == str(backup.resolve())

        # Rollback rehearsal: drop the migrated layout and restore the backup.
        import shutil

        shutil.rmtree(storage / "v2")
        (storage / "migration_v2.json").unlink()
        shutil.copy2(backup / "proj_a" / "conv.json", original)
        assert original.read_bytes() == original_bytes
        assert ConversationStore(storage_dir=storage).storage_layout_state() == "legacy_requires_migration"


# ── C01-05: multi-process CAS on the v2 layout ──────────────────────────


def _append_worker(storage_dir: str, expected_revision: int, content: str, out: Any) -> None:
    store = ConversationStore(storage_dir=storage_dir)
    try:
        snapshot = store.append(
            project_id="p",
            conversation_id="a.b",
            expected_revision=expected_revision,
            role="assistant",
            content=content,
        )
        out.put(("ok", snapshot.revision))
    except StaleConversationRevisionError:
        out.put(("stale", -1))


def test_multiprocess_cas_survives_restart_on_v2(tmp_path: Path) -> None:
    storage = tmp_path / "conversations"
    seed = ConversationStore(storage_dir=storage)
    seed.append(project_id="p", conversation_id="a.b", expected_revision=0, role="user", content="seed")

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_append_worker, args=(str(storage), 1, f"worker-{i}", queue)) for i in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    results = sorted(queue.get(timeout=5) for _ in processes)
    assert [status for status, _ in results] == ["ok", "stale"]

    fresh = ConversationStore(storage_dir=storage)
    record = fresh.get(project_id="p", conversation_id="a.b")
    assert record is not None
    assert record.revision == 2
    assert len(record.messages) == 2
    assert sum(1 for m in record.messages if m.content.startswith("worker-")) == 1
