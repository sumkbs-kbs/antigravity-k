import os

from antigravity_k.engine.context_artifact_store import ContextArtifactStore


def test_store_chunks_content_and_restores_selected_chunk(tmp_path):
    store = ContextArtifactStore(tmp_path)
    content = "line-1\nline-2\nline-3\nline-4"

    artifact = store.store(content, source="read_file:demo.py", chunk_chars=12)

    assert artifact.ref_id
    assert artifact.source == "read_file:demo.py"
    assert artifact.chunk_count >= 2
    assert store.read(artifact.ref_id) == content
    assert store.read(artifact.ref_id, chunk_index=1)
    assert store.read(artifact.ref_id, chunk_index=artifact.chunk_count) is None


def test_read_chunk_returns_typed_range_metadata(tmp_path):
    store = ContextArtifactStore(tmp_path)
    artifact = store.store("alpha\nbeta\ngamma", source="read_file:demo.py", chunk_chars=7)

    chunk = store.read_chunk(artifact.ref_id, 1)

    assert chunk is not None
    assert chunk.ref_id == artifact.ref_id
    assert chunk.index == 1
    assert chunk.chunk_count == artifact.chunk_count
    assert chunk.content


def test_store_is_content_addressed_and_manifest_is_durable(tmp_path):
    store = ContextArtifactStore(tmp_path)
    content = "same output" * 100

    first = store.store(content, source="tool-a", chunk_chars=32)
    second = store.store(content, source="tool-b", chunk_chars=32)

    assert first.ref_id == second.ref_id
    manifest = store.manifest(first.ref_id)
    assert manifest is not None
    assert manifest.sha256 == first.sha256
    assert manifest.chunk_count == first.chunk_count


def test_store_prunes_oldest_artifacts_to_retention_limit(tmp_path):
    store = ContextArtifactStore(
        tmp_path,
        max_artifacts=2,
        max_total_bytes=1_000_000,
    )
    first = store.store("first")
    os.utime(tmp_path / f"{first.ref_id}.json", (1, 1))
    second = store.store("second")
    os.utime(tmp_path / f"{second.ref_id}.json", (2, 2))

    third = store.store("third")

    assert store.read(first.ref_id) is None
    assert store.read(second.ref_id) == "second"
    assert store.read(third.ref_id) == "third"


def test_store_keeps_current_artifact_when_it_alone_exceeds_byte_limit(tmp_path):
    store = ContextArtifactStore(
        tmp_path,
        max_artifacts=10,
        max_total_bytes=1,
    )
    first = store.store("first")

    second = store.store("second")

    assert store.read(first.ref_id) is None
    assert store.read(second.ref_id) == "second"
