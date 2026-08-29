"""Tests for StructuralSnapshot module."""

import tempfile
from pathlib import Path

from antigravity_k.engine.structural_snapshot import StructuralSnapshotBuilder


def test_structural_snapshot_build():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "src").mkdir()
        _ = (tmp_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
        _ = (tmp_path / "README.md").write_text("# Test", encoding="utf-8")

        snapshot = StructuralSnapshotBuilder.build(tmp_path)
        pinned = snapshot.format_pinned_block()

        assert "PINNED_STRUCTURAL_CONTEXT" in pinned
        assert "📁 src/" in pinned or "README.md" in pinned
