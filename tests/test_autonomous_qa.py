"""Tests for autonomous_qa — Autonomous QA loop engine.

Covers data models (FixStatus, UIDefect, FixAttempt, AutonomousQAReport),
report serialization, _compare_screenshots, and _apply_patch.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import pytest

from antigravity_k.engine.autonomous_qa import (
    AutonomousQAEngine,
    AutonomousQAReport,
    FixAttempt,
    FixStatus,
    UIDefect,
)


class _FakeHTTPResponse:
    def __init__(self, status_code: int, payload: object | None = None) -> None:
        self.status_code: int = status_code
        self.payload: object = payload if payload is not None else {}

    def json(self) -> object:
        return self.payload


class _FakeAsyncClient:
    response: _FakeHTTPResponse | None = None
    error: Exception | None = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        _ = (args, kwargs)

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        _ = args

    async def post(self, *args: object, **kwargs: object) -> _FakeHTTPResponse:
        _ = (args, kwargs)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


class _FakePage:
    def __init__(self, evaluate_result: object, *, query_result: object | None = None) -> None:
        self.evaluate_result: object = evaluate_result
        self.query_result: object | None = query_result if query_result is not None else object()
        self.evaluate_error: Exception | None = None

    async def evaluate(self, expression: str) -> object:
        _ = expression
        if self.evaluate_error is not None:
            raise self.evaluate_error
        return self.evaluate_result

    async def query_selector(self, selector: str) -> object | None:
        _ = selector
        return self.query_result

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> object:
        _ = (url, wait_until, timeout)
        return object()

    async def set_viewport_size(self, size: object) -> None:
        _ = size


def _compare(engine: AutonomousQAEngine, before: bytes, after: bytes) -> float:
    method = cast(Callable[[bytes, bytes], float], getattr(engine, "_compare_screenshots"))
    return method(before, after)


def _apply_patch(engine: AutonomousQAEngine, patch: dict[str, str]) -> bool:
    method = cast(Callable[[dict[str, str]], bool], getattr(engine, "_apply_patch"))
    return method(patch)


async def _vision_analyze(engine: AutonomousQAEngine, image: str) -> list[UIDefect]:
    method = cast(Callable[[str], Awaitable[list[UIDefect]]], getattr(engine, "_vision_analyze"))
    return await method(image)


async def _generate_fixes(engine: AutonomousQAEngine, defects: list[UIDefect]) -> list[dict[str, str]]:
    method = cast(Callable[[list[UIDefect]], Awaitable[list[dict[str, str]]]], getattr(engine, "_generate_code_fixes"))
    return await method(defects)


async def _collect_performance(engine: AutonomousQAEngine, page: object) -> dict[str, object]:
    method = cast(Callable[[object], Awaitable[dict[str, object]]], getattr(engine, "_collect_performance"))
    return await method(page)


async def _test_viewports(engine: AutonomousQAEngine, page: object, url: str) -> dict[str, object]:
    method = cast(Callable[[object, str], Awaitable[dict[str, object]]], getattr(engine, "_test_viewports"))
    return await method(page, url)


def _install_httpx(
    monkeypatch: pytest.MonkeyPatch,
    response: _FakeHTTPResponse | None = None,
    error: Exception | None = None,
) -> None:
    import httpx

    _FakeAsyncClient.response = response
    _FakeAsyncClient.error = error
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

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
        assert _compare(engine, data, data) == 0.0

    def test_different_screenshots_score_positive(self):
        engine = AutonomousQAEngine()
        assert _compare(engine, b"before", b"after") > 0.0

    def test_both_empty(self):
        engine = AutonomousQAEngine()
        assert _compare(engine, b"", b"") == 0.0

    def test_one_empty(self):
        engine = AutonomousQAEngine()
        assert _compare(engine, b"data", b"") == 1.0


# ---------------------------------------------------------------------------
# AutonomousQAEngine — _apply_patch
# ---------------------------------------------------------------------------


class TestApplyPatch:
    def test_patch_success(self, tmp_path: Path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        target = tmp_path / "test.py"
        _ = target.write_text("old content", encoding="utf-8")
        result = _apply_patch(engine, {"file": "test.py", "search": "old content", "replace": "new content"})
        assert result is True
        assert target.read_text(encoding="utf-8") == "new content"

    def test_patch_file_not_found_returns_false(self, tmp_path: Path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        result = _apply_patch(engine, {"file": "nonexistent.py", "search": "x", "replace": "y"})
        assert result is False

    def test_patch_search_not_found_returns_false(self, tmp_path: Path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        target = tmp_path / "test.py"
        _ = target.write_text("original", encoding="utf-8")
        result = _apply_patch(engine, {"file": "test.py", "search": "not found", "replace": "y"})
        assert result is False
        assert target.read_text(encoding="utf-8") == "original"

    def test_patch_empty_search_returns_false(self, tmp_path: Path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        target = tmp_path / "test.py"
        _ = target.write_text("content", encoding="utf-8")
        result = _apply_patch(engine, {"file": "test.py", "search": "", "replace": "y"})
        assert result is False

    def test_patch_rejects_path_escape(self, tmp_path: Path):
        engine = AutonomousQAEngine(project_root=str(tmp_path))
        outside = tmp_path.parent / "outside.py"
        _ = outside.write_text("original", encoding="utf-8")

        result = _apply_patch(engine, {"file": "../outside.py", "search": "original", "replace": "changed"})

        assert result is False
        assert outside.read_text(encoding="utf-8") == "original"


# ---------------------------------------------------------------------------
# AutonomousQAEngine — __init__
# ---------------------------------------------------------------------------


class TestEngineInit:
    def test_default_params(self):
        engine = AutonomousQAEngine()
        assert engine.dashboard_url == "http://localhost:5173"
        assert engine.vision_model == "qwen3.6:latest"
        assert engine.coding_model == "qwen3.6:latest"
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
    async def test_vision_analyze_returns_defects(self, monkeypatch: pytest.MonkeyPatch):
        engine = AutonomousQAEngine()
        _install_httpx(
            monkeypatch,
            _FakeHTTPResponse(
                200,
                {
                    "message": {
                        "content": '[{"description": "overlapping text", "severity": "high", "suggested_fix": "fix css"}]',
                    },
                },
            ),
        )
        defects = await _vision_analyze(engine, "fake_base64")
        assert len(defects) == 1
        assert defects[0].description == "overlapping text"
        assert defects[0].severity == "high"

    @pytest.mark.asyncio
    async def test_vision_analyze_no_defects_returns_empty(self, monkeypatch: pytest.MonkeyPatch):
        engine = AutonomousQAEngine()
        _install_httpx(monkeypatch, _FakeHTTPResponse(200, {"message": {"content": "[]"}}))
        defects = await _vision_analyze(engine, "fake_base64")
        assert defects == []

    @pytest.mark.asyncio
    async def test_vision_analyze_non_200_returns_empty(self, monkeypatch: pytest.MonkeyPatch):
        engine = AutonomousQAEngine()
        _install_httpx(monkeypatch, _FakeHTTPResponse(500))
        defects = await _vision_analyze(engine, "fake_base64")
        assert defects == []

    @pytest.mark.asyncio
    async def test_vision_analyze_httpx_error_returns_empty(self, monkeypatch: pytest.MonkeyPatch):
        import httpx

        engine = AutonomousQAEngine()
        _install_httpx(monkeypatch, error=httpx.RequestError("connection failed"))
        defects = await _vision_analyze(engine, "fake_base64")
        assert defects == []


class TestGenerateCodeFixes:
    """_generate_code_fixes with mocked httpx."""

    @pytest.mark.asyncio
    async def test_generates_patches(self, monkeypatch: pytest.MonkeyPatch):
        engine = AutonomousQAEngine()
        defects = [UIDefect(description="bug", severity="high", suggested_fix="fix it")]
        _install_httpx(
            monkeypatch,
            _FakeHTTPResponse(
                200,
                {"message": {"content": '[{"file": "test.css", "search": "old", "replace": "new"}]'}},
            ),
        )
        patches = await _generate_fixes(engine, defects)
        assert len(patches) == 1
        assert patches[0]["file"] == "test.css"

    @pytest.mark.asyncio
    async def test_generate_non_200_returns_empty(self, monkeypatch: pytest.MonkeyPatch):
        engine = AutonomousQAEngine()
        _install_httpx(monkeypatch, _FakeHTTPResponse(500))
        patches = await _generate_fixes(engine, [])
        assert patches == []


class TestCollectPerformance:
    """_collect_performance with mocked page."""

    @pytest.mark.asyncio
    async def test_returns_metrics(self):
        engine = AutonomousQAEngine()
        page = _FakePage(
            {
            "dom_content_loaded_ms": 350,
            "load_complete_ms": 800,
            "first_contentful_paint_ms": 200,
            "dom_nodes": 123,
            "js_heap_mb": 45,
            }
        )

        metrics = await _collect_performance(engine, page)
        assert metrics["dom_content_loaded_ms"] == 350
        assert metrics["dom_nodes"] == 123

    @pytest.mark.asyncio
    async def test_evaluate_error_returns_empty(self):
        engine = AutonomousQAEngine()
        page = _FakePage({})
        page.evaluate_error = TimeoutError("timeout")

        metrics = await _collect_performance(engine, page)
        assert metrics == {}


class TestTestViewports:
    """_test_viewports with mocked page."""

    @pytest.mark.asyncio
    async def test_all_viewports_pass(self):
        engine = AutonomousQAEngine()
        page = _FakePage(False)

        results = await _test_viewports(engine, page, "http://test:3000")
        assert len(results) == 3
        assert cast(bool, cast(dict[str, object], results["desktop"])["pass"]) is True
        assert cast(bool, cast(dict[str, object], results["tablet"])["pass"]) is True
        assert cast(bool, cast(dict[str, object], results["mobile"])["pass"]) is True

    @pytest.mark.asyncio
    async def test_overflow_detected(self):
        engine = AutonomousQAEngine()
        page = _FakePage(True)

        results = await _test_viewports(engine, page, "http://test:3000")
        desktop = cast(dict[str, object], results["desktop"])
        assert desktop["pass"] is False
        assert "Overflow" in cast(str, desktop["summary"])
