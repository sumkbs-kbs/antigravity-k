"""Unit tests for SelfHealingDoctor."""

import tempfile
from pathlib import Path

from antigravity_k.engine.self_healing_doctor import SelfHealingDoctor


def test_self_healing_doctor_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir()
        (root / "src" / "valid.py").write_text("def test(): pass\n", encoding="utf-8")

        doctor = SelfHealingDoctor(root)
        report = doctor.run_health_check(auto_heal=True)

        assert report.total_checks >= 3
        assert report.healthy_count >= 2
