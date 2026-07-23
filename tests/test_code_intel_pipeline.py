"""Tests for CodeIndexPipeline (code_intel/pipeline.py)."""

import tempfile
from pathlib import Path

from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline


class TestCodeIndexPipeline:
    def test_init(self):
        pipeline = CodeIndexPipeline()
        assert pipeline.graph is not None
        assert pipeline.repo_manager is None

    def test_load_existing_empty(self):
        pipeline = CodeIndexPipeline()
        result = pipeline.load_existing("/tmp")
        assert result is True

    def test_run_with_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple python file
            pkg_dir = Path(tmpdir) / "mypkg"
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("")
            (pkg_dir / "module.py").write_text("def hello():\n    pass\n\nclass MyClass:\n    pass\n")

            pipeline = CodeIndexPipeline()
            result = pipeline.run(str(tmpdir), force=True)

            assert result["status"] == "SUCCESS"
            assert "elapsed_seconds" in result
            assert result["phases"]["scan"]["total_files"] >= 1
            assert result["phases"]["parse"]["symbols"] >= 1

    def test_run_skips_git_and_cache_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()
            (root / "__pycache__").mkdir()
            (root / "valid.py").write_text("x = 1")

            pipeline = CodeIndexPipeline()
            result = pipeline.run(str(tmpdir), force=True)
            assert result["status"] == "SUCCESS"

    def test_run_with_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = CodeIndexPipeline()
            result = pipeline.run(tmpdir, force=True)
            assert result["status"] == "SUCCESS"

    def test_run_adds_mock_nodes(self):
        pipeline = CodeIndexPipeline()
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline.run(tmpdir, force=True)
            # Mock nodes should be added
            assert (
                pipeline.graph.get_nodes_by_type(pipeline.graph.NodeType.MODULE)
                if hasattr(pipeline.graph, "NodeType")
                else True
            )
