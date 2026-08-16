"""Unit tests for CallHierarchyGraph."""

import tempfile
from pathlib import Path

from antigravity_k.engine.call_hierarchy_graph import CallHierarchyGraph


def test_call_hierarchy_resolution():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "math_lib.py").write_text(
            """
def calculate_tax(amount):
    return amount * 0.1
""",
            encoding="utf-8",
        )

        (root / "checkout.py").write_text(
            """
from math_lib import calculate_tax

def process_order(price):
    tax = calculate_tax(price)
    return price + tax
""",
            encoding="utf-8",
        )

        graph = CallHierarchyGraph(root)
        report = graph.analyze_impact("calculate_tax", file_path="math_lib.py")

        assert len(report.impacted_callers) == 1
        assert report.impacted_callers[0].caller_file == "checkout.py"
        assert report.impacted_callers[0].caller_function == "process_order"
        assert "checkout.py" in report.impacted_files
        feedback = report.format_for_model()
        assert "Call-Hierarchy Impact Analysis" in feedback
