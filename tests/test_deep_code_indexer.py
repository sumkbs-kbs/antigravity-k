"""Unit tests for DeepCodeIndexer."""

import tempfile
from pathlib import Path

from antigravity_k.engine.deep_code_indexer import DeepCodeIndexer


def test_deep_code_indexing_and_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "service.py").write_text(
            """
def process_payment(account_id: str, amount: float) -> bool:
    \"\"\"Process payment via gateway.\"\"\"
    return True
""",
            encoding="utf-8",
        )

        indexer = DeepCodeIndexer(root)
        summary = indexer.get_signature_summary("process_payment")

        assert "process_payment(account_id: str, amount: float) -> bool" in summary
        assert "Process payment via gateway" in summary
