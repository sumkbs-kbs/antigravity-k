"""Unit tests for DeepCodeIndexer."""

import tempfile
from pathlib import Path

from antigravity_k.engine.deep_code_indexer import DeepCodeIndexer


def test_deep_code_indexing_and_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _ = (root / "service.py").write_text(
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


def test_signature_summary_preserves_positional_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _ = (root / "service.py").write_text(
            "def retry_request(url: str, retries: int = 3) -> bool:\n    return True\n",
            encoding="utf-8",
        )

        summary = DeepCodeIndexer(root).get_signature_summary("retry_request")

        assert "retry_request(url: str, retries: int = 3) -> bool" in summary
