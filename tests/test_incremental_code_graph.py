"""Unit tests for IncrementalCodeGraph."""

import tempfile
from pathlib import Path

from antigravity_k.engine.incremental_code_graph import IncrementalCodeGraph


def test_incremental_update_and_lookup():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        graph = IncrementalCodeGraph(root)

        code_v1 = """
class DataPipeline:
    def process(self, raw_data):
        pass
"""
        _ = graph.update_file("pipeline.py", content=code_v1)
        syms = graph.lookup_symbol("DataPipeline")
        assert len(syms) == 1
        assert syms[0].file_path == "pipeline.py"
        assert syms[0].kind == "class"

        # Update file to add another function
        code_v2 = """
class DataPipeline:
    def process(self, raw_data):
        pass
    def validate(self, schema):
        pass
"""
        _ = graph.update_file("pipeline.py", content=code_v2)
        val_syms = graph.lookup_symbol("validate")
        assert len(val_syms) == 1
        assert val_syms[0].name == "validate"

        # Remove file
        graph.remove_file("pipeline.py")
        assert len(graph.lookup_symbol("DataPipeline")) == 0
