"""Tests for autonomous_qa — Autonomous QA loop engine.

Covers data models (FixStatus, UIDefect, FixAttempt, AutonomousQAReport),
report serialization, _compare_screenshots, and _apply_patch.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.autonomous_qa import (
    AutonomousQAEngine,
    AutonomousQAReport,
    FixAttempt,
    FixStatus,
    UIDefect,
)

# ---------------------------------------------------------------------------
# FixStatus enum
# ---------------------------------------------------------------------------


class TestFixStatus:
    def test_pending_value(self):
        assert FixStatus.PENDING.value == "pending"

    def test_fixed_value(self):
        assert FixStatus.FIXED.value == "fixed"

    def test_failed_value(self):
        assert FixStatus.FAILED.value == "failed"

    def test_no_issues_value(self):
        assert FixStatus.NO_ISSUES.value == "no_issues"

    def test_analyzing_verifying_values(self):
        assert FixStatus.ANALYZING.value == "analyzing"
        assert FixStatus.FIXING.value == "fixing"
        assert FixStatus.VERIFYING.value == "verifying"


# ---------------------------------------------------------------------------
# UIDefect dataclass
# ---------------------------------------------------------------------------


class TestUIDefect:
    def test_default_severity_is_medium(self):
        d = UIDefect(description="broken layout")
        assert d.severity == "medium"

    def test_all_fields(self):
        d = UIDefect(
            description="text overflow",
            severity="high",
            suggested_fix="add overflow hidden",
            file_path="dashboard/src/styles/index.css",
            code_patch=".text { overflow: hidden; }",
        )
        assert d.description == "text overflow"
        assert d.severity == "high"
        assert d.code_patch == ".text { overflow: hidden; }"


# ---------------------------------------------------------------------------
# FixAttempt dataclass
# ---------------------------------------------------------------------------


class TestFixAttempt:
    def test_defaults(self):
        attempt = FixAttempt(iteration=1, defects_found=[], patches_applied=[])
        assert attempt.iteration == 1
        assert attempt.resolved is False
        assert attempt.visual_diff_score == 0.0
        assert attempt.duration_ms == 0


# ---------------------------------------------------------------------------
# AutonomousQAReport — serialization
# ---------------------------------------------------------------------------


class TestAutonomousQAReport:
    def test_default_values(self):
        report = AutonomousQAReport()
        assert report.status == FixStatus.PENDING
        assert report.total_iterations == 0
        assert report.to_dict()["status"] == "pending"

    def test_to_dict_contains_attempts(self):
        report = AutonomousQAReport()
        attempt = FixAttempt(iteration=1, defects_found=[], patches_applied=[])
        report.attempts.append(attempt)
        d = report.to_dict()
        assert len(d["attempts"]) == 1
        assert d["attempts"][0]["iteration"] == 1
        assert d["attempts"][0]["resolved"] is False

    def test_to_dict_has_performance_metrics(self):
        report = AutonomousQAReport()
        report.performance_metrics = {"dom_content_loaded_ms": 450}
        d = report.to_dict()
        assert d["performance"]["dom_content_loaded_ms"] == 450

    def test_to_dict_has_viewport_results(self):
        report = AutonomousQAReport()
        report.viewport_results = {"desktop": {"pass": True, "summary": "OK"}}
        d = report.to_dict()
        assert d["viewport_results"]["desktop"]["pass"] is True

    def test_to_dict_console_errors_count(self):
        report = AutonomousQAReport()
        report.console_errors = [{"type": "error", "text": "fail"}]
        assert report.to_dict()["console_errors_count"] == 1

    def test_to_dict_duration_ms(self):
        report = AutonomousQAReport()
        report.duration_ms = 1234.5
        assert report.to_dict()["duration_ms"] == 1234.5

    def test_to_markdown_contains_url(self):
        report = AutonomousQAReport(url="http://test.local")
        md = report.to_markdown()
        assert "http://test.local" in md

    def test_to_markdown_fixed_status_shows_checkmark(self):
        report = AutonomousQAReport(status=FixStatus.FIXED)
        md = report.to_markdown()
        assert "✅" in md

    def test_to_markdown_failed_status_shows_cross(self):
        report = AutonomousQAReport(status=FixStatus.FAILED)
        md = report.to_markdown()
        assert "❌" in md

    def test_to_markdown_with_viewport_results(self):
        report = AutonomousQAReport()
        report.viewport_results = {"mobile": {"pass": True, "summary": "OK"}}
        md = report.to_markdown()
        assert "반응형 테스트" in md

    def test_to_markdown_with_attempts(self):
        report = AutonomousQAReport()
        defect = UIDefect(description="overlap", severity="high", file_path="test.css")
        attempt = FixAttempt(iteration=1, defects_found=[defect], patches_applied=[])
        attempt.resolved = True
        attempt.visual_diff_score = 0.05
        report.attempts.append(attempt)
        md = report.to_markdown()
        assert "반복 1" in md
        assert "overlap" in md
        assert "test.css" in md
        assert "0.05" in md

    def test_to_markdown_with_performance(self):
        report = AutonomousQAReport()
        report.performance_metrics = {"dom_content_loaded_ms": 350}
        md = report.to_markdown()
        assert "성능 메트릭" in md
        assert "350" in md

    def test_autonomous_qa_report_to_dict_preserves_status_fixed(self):
        report = AutonomousQAReport(status=FixStatus.FIXED)
        d = report.to_dict()
        assert d["status"] == "fixed"

    def test_autonomous_qa_report_to_dict_with_empty_attempts(self):
        report = AutonomousQAReport()
        d = report.to_dict()
        assert d["attempts"] == []


# ---------------------------------------------------------------------------
# AutonomousQAEngine — _compare_screenshots
# ---------------------------------------------------------------------------


class TestCompareScreenshots:
    def test_identical_screenshots_score_zero(self):
        engine = AutonomousQAEngine()
        data = b"screenshot data"
        assert engine._compare_screenshots(data, data) == 0.0

    def test_different_screenshots_score_positive(self):
        engine = AutonomousQAEngine()
        assert engine._compare_screenshots(b"before", b"after") > 0.0

    def test_both_empty(self):
        engine = AutonomousQAEngine()
        assert engine._compare_screenshots(b"", b"") == 0.0

    def test_one_empty(self):
        engine = AutonomousQAEngine()
        assert engine._compare_screenshots(b"data", b"") == 1.0


# ---------------------------------------------------------------------------
# AutonomousQAEngine — _apply_patch
# ---------------------------------------------------------------------------


class TestApplyPatch:
    def test_patch_success(self, tmp_path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        target = tmp_path / "test.py"
        target.write_text("old content", encoding="utf-8")
        result = engine._apply_patch({"file": "test.py", "search": "old content", "replace": "new content"})
        assert result is True
        assert target.read_text(encoding="utf-8") == "new content"

    def test_patch_file_not_found_returns_false(self, tmp_path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        result = engine._apply_patch({"file": "nonexistent.py", "search": "x", "replace": "y"})
        assert result is False

    def test_patch_search_not_found_returns_false(self, tmp_path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        target = tmp_path / "test.py"
        target.write_text("original", encoding="utf-8")
        result = engine._apply_patch({"file": "test.py", "search": "not found", "replace": "y"})
        assert result is False
        assert target.read_text(encoding="utf-8") == "original"

    def test_patch_empty_search_returns_false(self, tmp_path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        target = tmp_path / "test.py"
        target.write_text("content", encoding="utf-8")
        result = engine._apply_patch({"file": "test.py", "search": "", "replace": "y"})
        assert result is False


# ---------------------------------------------------------------------------
# AutonomousQAEngine — __init__
# ---------------------------------------------------------------------------


class TestEngineInit:
    def test_default_params(self):
        engine = AutonomousQAEngine()
        assert engine.dashboard_url == "http://localhost:5173"
        assert engine.vision_model == "qwen2.5vl:32b"
        assert engine.coding_model == "qwen2.5-coder:32b"
        assert engine.max_iterations == 3

    def test_custom_params(self):
        engine = AutonomousQAEngine(
            dashboard_url="http://test:3000",
            ollama_url="http://ollama:11434",
            vision_model="llava",
            coding_model="codellama",
            max_iterations=5,
        )
        assert engine.dashboard_url == "http://test:3000"
        assert engine.ollama_url == "http://ollama:11434"
        assert engine.max_iterations == 5

    def test_viewports_defined(self):
        engine = AutonomousQAEngine()
        assert "desktop" in engine.VIEWPORTS
        assert "tablet" in engine.VIEWPORTS
        assert "mobile" in engine.VIEWPORTS
        assert engine.VIEWPORTS["desktop"]["width"] == 1280
        assert engine.VIEWPORTS["mobile"]["width"] == 375


# ---------------------------------------------------------------------------
# AutonomousQAEngine — async methods (mocked)
# ---------------------------------------------------------------------------


class TestVisionAnalyze:
    """_vision_analyze with mocked httpx."""

    @pytest.mark.asyncio
    async def test_vision_analyze_returns_defects(self):
        from unittest.mock import MagicMock, patch

        engine = AutonomousQAEngine()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": '[{"description": "overlapping text", "severity": "high", "suggested_fix": "fix css"}]',
            },
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            defects = await engine._vision_analyze("fake_base64")
            assert len(defects) == 1
            assert defects[0].description == "overlapping text"
            assert defects[0].severity == "high"

    @pytest.mark.asyncio
    async def test_vision_analyze_no_defects_returns_empty(self):
        from unittest.mock import MagicMock, patch

        engine = AutonomousQAEngine()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "[]"}}

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            defects = await engine._vision_analyze("fake_base64")
            assert defects == []

    @pytest.mark.asyncio
    async def test_vision_analyze_non_200_returns_empty(self):
        from unittest.mock import MagicMock, patch

        engine = AutonomousQAEngine()
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            defects = await engine._vision_analyze("fake_base64")
            assert defects == []

    @pytest.mark.asyncio
    async def test_vision_analyze_httpx_error_returns_empty(self):
        from unittest.mock import patch

        import httpx

        engine = AutonomousQAEngine()
        with patch("httpx.AsyncClient.post", side_effect=httpx.RequestError("connection failed")):
            defects = await engine._vision_analyze("fake_base64")
            assert defects == []


class TestGenerateCodeFixes:
    """_generate_code_fixes with mocked httpx."""

    @pytest.mark.asyncio
    async def test_generates_patches(self):
        from unittest.mock import MagicMock, patch

        engine = AutonomousQAEngine()
        defects = [UIDefect(description="bug", severity="high", suggested_fix="fix it")]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": '[{"file": "test.css", "search": "old", "replace": "new"}]',
            },
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            patches = await engine._generate_code_fixes(defects)
            assert len(patches) == 1
            assert patches[0]["file"] == "test.css"

    @pytest.mark.asyncio
    async def test_generate_non_200_returns_empty(self):
        from unittest.mock import MagicMock, patch

        engine = AutonomousQAEngine()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            patches = await engine._generate_code_fixes([])
            assert patches == []


class TestCollectPerformance:
    """_collect_performance with mocked page."""

    @pytest.mark.asyncio
    async def test_returns_metrics(self):
        from unittest.mock import AsyncMock

        engine = AutonomousQAEngine()
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = {
            "dom_content_loaded_ms": 350,
            "load_complete_ms": 800,
            "first_contentful_paint_ms": 200,
            "dom_nodes": 123,
            "js_heap_mb": 45,
        }

        metrics = await engine._collect_performance(mock_page)
        assert metrics["dom_content_loaded_ms"] == 350
        assert metrics["dom_nodes"] == 123

    @pytest.mark.asyncio
    async def test_evaluate_error_returns_empty(self):
        from unittest.mock import AsyncMock

        engine = AutonomousQAEngine()
        mock_page = AsyncMock()
        mock_page.evaluate.side_effect = TimeoutError("timeout")

        metrics = await engine._collect_performance(mock_page)
        assert metrics == {}


class TestTestViewports:
    """_test_viewports with mocked page."""

    @pytest.mark.asyncio
    async def test_all_viewports_pass(self):
        from unittest.mock import AsyncMock

        engine = AutonomousQAEngine()
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = False  # no horizontal overflow
        mock_page.query_selector.return_value = AsyncMock()  # element found
        mock_page.goto = AsyncMock()
        mock_page.set_viewport_size = AsyncMock()

        results = await engine._test_viewports(mock_page, "http://test:3000")
        assert len(results) == 3
        assert results["desktop"]["pass"] is True
        assert results["tablet"]["pass"] is True
        assert results["mobile"]["pass"] is True

    @pytest.mark.asyncio
    async def test_overflow_detected(self):
        from unittest.mock import AsyncMock

        engine = AutonomousQAEngine()
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = True  # horizontal overflow detected
        mock_page.query_selector.return_value = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.set_viewport_size = AsyncMock()

        results = await engine._test_viewports(mock_page, "http://test:3000")
        assert results["desktop"]["pass"] is False
        assert "Overflow" in results["desktop"]["summary"]
