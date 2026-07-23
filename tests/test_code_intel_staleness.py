"""Tests for StalenessDetector (code_intel/staleness.py)."""

from antigravity_k.engine.code_intel.staleness import StalenessDetector


class TestStalenessDetector:
    def test_check_returns_expected_structure(self):
        detector = StalenessDetector()
        result = detector.check("/some/repo")
        assert isinstance(result, dict)
        assert result["status"] == "UP_TO_DATE"
        assert result["current_commit"] == "abcdef123456"
        assert result["indexed_commit"] == "abcdef123456"
