"""Unit tests for FastPathKernel."""

import tempfile
from pathlib import Path

from antigravity_k.engine.fast_path_kernel import FastPathKernel


def test_fast_path_symbol_lookup():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "model.py").write_text("class RocketEngine:\n    def ignite(self): pass\n", encoding="utf-8")

        kernel = FastPathKernel(root)
        res = kernel.try_execute("where is RocketEngine")

        assert res.handled is True
        assert res.source == "SymbolNavigator"
        assert "RocketEngine" in res.response
        assert res.latency_ms < 50.0  # sub-50ms deterministic


def test_fast_path_direct_file_view():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "specs.md").write_text("# Starship Specs\nPayload: 150t\n", encoding="utf-8")

        kernel = FastPathKernel(root)
        res = kernel.try_execute("view specs.md")

        assert res.handled is True
        assert res.source == "DirectFileRead"
        assert "Starship Specs" in res.response
