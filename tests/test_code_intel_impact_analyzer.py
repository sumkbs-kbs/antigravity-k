"""Tests for ImpactAnalyzer (code_intel/impact_analyzer.py)."""

from antigravity_k.engine.code_intel.impact_analyzer import ImpactAnalyzer


class TestImpactAnalyzer:
    def test_analyze_returns_expected_structure(self):
        graph = {}
        analyzer = ImpactAnalyzer(graph)
        result = analyzer.analyze("some_symbol")
        assert isinstance(result, dict)
        assert "upstream" in result
        assert "downstream" in result
        assert "risk_level" in result
        assert result["upstream"] == ["call_a", "call_b"]
        assert result["downstream"] == ["call_c"]
        assert result["risk_level"] == "MEDIUM"
        assert result["blast_radius"] == 3

    def test_analyze_with_max_depth(self):
        graph = {}
        analyzer = ImpactAnalyzer(graph)
        result = analyzer.analyze("symbol", max_depth=3)
        assert result["risk_level"] == "MEDIUM"
