"""Unit tests for SurgicalPatcher."""

from antigravity_k.engine.surgical_patcher import SurgicalPatcher


def test_annotate_file_with_hashes():
    code = "def add(a, b):\n    return a + b\n"
    annotated = SurgicalPatcher.annotate_file_with_hashes(code)
    assert "1:" in annotated
    assert "def add(a, b):" in annotated


def test_surgical_patch_exact():
    orig = "def compute():\n    x = 10\n    return x\n"
    res = SurgicalPatcher.apply_patch(orig, "x = 10", "x = 20")
    assert res.success is True
    assert "x = 20" in res.new_content


def test_surgical_patch_whitespace_tolerant():
    orig = "def compute():\n    x = 10   \n    return x\n"
    res = SurgicalPatcher.apply_patch(orig, "x = 10", "x = 42")
    assert res.success is True
    assert "x = 42" in res.new_content
