"""Unit tests for AtomicTransactionEngine."""

import tempfile
from pathlib import Path

from antigravity_k.engine.atomic_transaction_engine import AtomicTransactionEngine


def test_atomic_transaction_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        engine = AtomicTransactionEngine(root)

        engine.stage_file_patch("mod1.py", "def f1(): return 1\n")
        engine.stage_file_patch("mod2.py", "def f2(): return 2\n")

        res = engine.commit_transaction()
        assert res.committed is True
        assert len(res.touched_files) == 2
        assert (root / "mod1.py").exists()
        assert (root / "mod2.py").exists()


def test_atomic_transaction_abort_on_syntax_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        engine = AtomicTransactionEngine(root)

        engine.stage_file_patch("good.py", "def ok(): return True\n")
        engine.stage_file_patch("bad.py", "def broken(\n")

        res = engine.commit_transaction()
        assert res.committed is False
        assert "Syntax error" in res.error_message
        assert not (root / "good.py").exists()  # Atomic: good file is NOT written
        assert not (root / "bad.py").exists()
