"""Unit tests for SymbolNavigator."""

import tempfile
from pathlib import Path

from antigravity_k.engine.symbol_navigator import SymbolNavigator


def test_symbol_navigator_indexing():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        py_file = root / "calculator.py"
        _ = py_file.write_text(
            """
class Calculator:
    def add(self, a, b):
        return a + b

def multiply(x, y):
    return x * y
""",
            encoding="utf-8",
        )

        nav = SymbolNavigator(root)
        matches = nav.find_symbol("Calculator")
        assert len(matches) >= 1
        assert matches[0].name == "Calculator"
        assert matches[0].kind == "class"

        fn_matches = nav.find_symbol("multiply")
        assert len(fn_matches) >= 1
        assert fn_matches[0].name == "multiply"
        assert fn_matches[0].kind == "function"
