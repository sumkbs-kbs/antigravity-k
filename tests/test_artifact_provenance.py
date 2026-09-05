from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter
from typer.testing import CliRunner

from antigravity_k.engine.artifact_provenance import (
    ArtifactProvenanceError,
    app,
    create_manifest,
    load_manifest,
    manifest_digest,
    record_manifest_event,
    verify_manifest,
    write_manifest,
)
from antigravity_k.engine.task_state_store import TaskStateStore


def _artifact_tree(root: Path) -> None:
    (root / "nested").mkdir()
    _ = (root / "model.bin").write_bytes(b"weights-v1")
    _ = (root / "nested" / "config.json").write_text('{"layers": 4}\n', encoding="utf-8")


def test_manifest_is_deterministic_and_round_trips(tmp_path: Path) -> None:
    _artifact_tree(tmp_path)
    output = tmp_path / "artifact-provenance.json"

    first = create_manifest(tmp_path, [Path(".")], excluded_paths=[output])
    write_manifest(output, first)
    second = create_manifest(tmp_path, [Path(".")], excluded_paths=[output])

    assert first == second
    assert [record.path for record in first.artifacts] == ["model.bin", "nested/config.json"]
    assert load_manifest(output) == first
    assert verify_manifest(tmp_path, first, excluded_paths=[output]).valid is True


def test_verification_reports_content_tampering(tmp_path: Path) -> None:
    _artifact_tree(tmp_path)
    manifest = create_manifest(tmp_path, [Path(".")])
    _ = (tmp_path / "model.bin").write_bytes(b"weights-v2")

    report = verify_manifest(tmp_path, manifest)

    assert report.valid is False
    assert [(issue.kind, issue.path) for issue in report.issues] == [("sha256_mismatch", "model.bin")]


def test_verification_reports_missing_and_unexpected_files(tmp_path: Path) -> None:
    _artifact_tree(tmp_path)
    manifest = create_manifest(tmp_path, [Path(".")])
    (tmp_path / "model.bin").unlink()
    _ = (tmp_path / "extra.txt").write_text("unexpected", encoding="utf-8")

    report = verify_manifest(tmp_path, manifest)

    assert [(issue.kind, issue.path) for issue in report.issues] == [
        ("unexpected", "extra.txt"),
        ("missing", "model.bin"),
    ]


def test_manifest_rejects_paths_outside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "artifact"
    root.mkdir()
    outside = tmp_path / "outside.bin"
    _ = outside.write_bytes(b"private")

    with pytest.raises(ArtifactProvenanceError, match="outside the artifact root"):
        _ = create_manifest(root, [outside])


def test_manifest_rejects_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "artifact"
    root.mkdir()
    target = root / "target.bin"
    _ = target.write_bytes(b"target")
    (root / "link.bin").symlink_to(target)

    with pytest.raises(ArtifactProvenanceError, match="Symbolic links"):
        _ = create_manifest(root, [Path(".")])


def test_cli_create_then_verify_and_detect_tampering(tmp_path: Path) -> None:
    _artifact_tree(tmp_path)
    runner = CliRunner()
    manifest_path = tmp_path / "provenance.json"

    created = runner.invoke(
        app,
        ["create", ".", "--root", str(tmp_path), "--output", str(manifest_path)],
    )
    assert created.exit_code == 0, created.output
    payload = TypeAdapter(dict[str, JsonValue]).validate_json(created.output)
    assert payload == {"artifact_count": 2, "manifest": str(manifest_path), "status": "created"}

    verified = runner.invoke(app, ["verify", str(manifest_path), "--root", str(tmp_path)])
    assert verified.exit_code == 0, verified.output
    verified_payload = TypeAdapter(dict[str, JsonValue]).validate_json(verified.output)
    assert verified_payload["valid"] is True

    _ = (tmp_path / "model.bin").write_bytes(b"tampered!!")
    tampered = runner.invoke(app, ["verify", str(manifest_path), "--root", str(tmp_path)])
    assert tampered.exit_code == 1
    tampered_payload = TypeAdapter(dict[str, JsonValue]).validate_json(tampered.output)
    assert tampered_payload["valid"] is False


def test_manifest_digest_is_deterministic_and_recorded_in_task_event(tmp_path: Path) -> None:
    # Given
    _artifact_tree(tmp_path)
    manifest = create_manifest(tmp_path, [Path(".")])
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("task-artifact", "prompt", "running", "2026-09-01T00:00:00+00:00")

    # When
    first_digest = manifest_digest(manifest)
    second_digest = manifest_digest(manifest)
    event = record_manifest_event(store, "task-artifact", manifest, source="ui_bundle")

    # Then
    assert first_digest == second_digest
    assert len(first_digest) == 64
    assert event.digest == first_digest
    records = store.list_execution_events("task-artifact")
    assert records[0]["event_type"] == "artifact.provenance.recorded"
    assert first_digest in records[0]["payload_json"]
