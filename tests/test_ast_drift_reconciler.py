"""Unit tests for ASTDriftReconciler."""

from antigravity_k.engine.ast_drift_reconciler import ASTDriftReconciler, HunkEdit


def test_multi_hunk_bottom_to_top_application():
    orig_code = """line 1: import os
line 2: import sys
line 3: def f1():
line 4:     return 1
line 5: def f2():
line 6:     return 2
"""
    # Hunk 1 touches lines 3-4 (middle)
    # Hunk 2 touches lines 5-6 (bottom)
    hunk1 = HunkEdit(
        start_line=3,
        end_line=4,
        target_text="def f1():\n    return 1\n",
        replacement_text="def f1_new():\n    # expanded\n    return 100\n",
    )
    hunk2 = HunkEdit(
        start_line=5,
        end_line=6,
        target_text="def f2():\n    return 2\n",
        replacement_text="def f2_new():\n    return 200\n",
    )

    res = ASTDriftReconciler.apply_multi_hunks(orig_code, [hunk1, hunk2])
    assert res.success is True
    assert res.applied_hunks_count == 2
    assert "def f1_new()" in res.reconciled_content
    assert "def f2_new()" in res.reconciled_content
    assert "return 100" in res.reconciled_content
    assert "return 200" in res.reconciled_content
