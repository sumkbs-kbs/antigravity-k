"""Tests for harness — TestHarness, FeedbackCollector, URL derivation, headers.

Extends existing test_harness_config.py with unit tests for the main
TestHarness class methods and FeedbackCollector.
"""

from __future__ import annotations

from antigravity_k.engine.harness import (
    FeedbackCollector,
    HarnessReport,
    TestHarness,
    TestIntent,
    TestResult,
    TestStatus,
)

# ---------------------------------------------------------------------------
# FeedbackCollector
# ---------------------------------------------------------------------------


class TestFeedbackCollector:
    def test_collect_all_pass(self):
        fc = FeedbackCollector()
        report = HarnessReport()
        report.passed = 5
        report.failed = 0
        report.healed = 0
        report.total = 5
        report.results = [TestResult("t1", TestStatus.PASSED, 100, "ok")]
        msg = fc.collect(report)
        assert "✅" in msg
        assert "5/5" in msg or "5개" in msg
        assert len(fc.history) == 1

    def test_collect_with_failures(self):
        fc = FeedbackCollector()
        report = HarnessReport()
        report.passed = 3
        report.failed = 2
        report.total = 5
        report.results = [
            TestResult("t1", TestStatus.PASSED, 100, "ok"),
            TestResult("t2", TestStatus.FAILED, 200, "connection error"),
            TestResult("t3", TestStatus.FAILED, 300, "timeout"),
        ]
        msg = fc.collect(report)
        assert "⚠️" in msg
        assert "connection error" in msg
        assert "timeout" in msg

    def test_get_trend_no_data(self):
        fc = FeedbackCollector()
        trend = fc.get_trend()
        assert trend["trend"] == "no_data"

    def test_get_trend_with_data(self):
        fc = FeedbackCollector()
        for _ in range(3):
            r = HarnessReport()
            r.passed = 4
            r.failed = 1
            r.total = 5
            fc.collect(r)
        trend = fc.get_trend()
        assert trend["total_runs"] == 3
        assert len(trend["recent_pass_rates"]) == 3


# ---------------------------------------------------------------------------
# TestHarness — init & URL derivation
# ---------------------------------------------------------------------------


class TestHarnessInit:
    def test_default_init(self):
        harness = TestHarness()
        assert harness.base_url == "http://localhost:8000"
        assert harness.dashboard_url == "http://localhost:5173"
        assert "ws://" in harness.ws_url
        assert harness.access_pin is not None

    def test_custom_urls(self):
        harness = TestHarness(
            base_url="http://api.test:8080",
            dashboard_url="http://dashboard.test:3000",
        )
        assert harness.base_url == "http://api.test:8080"
        assert harness.dashboard_url == "http://dashboard.test:3000"

    def test_ws_url_derives_from_base(self):
        harness = TestHarness(base_url="http://api.test:8080")
        assert harness.ws_url == "ws://api.test:8080/ws/terminal"

    def test_ws_url_https_uses_wss(self):
        harness = TestHarness(base_url="https://api.test:443")
        assert harness.ws_url == "wss://api.test:443/ws/terminal"


class TestRequestHeaders:
    def test_without_access_pin_returns_empty(self, monkeypatch):
        monkeypatch.delenv("AGK_HARNESS_ACCESS_PIN", raising=False)
        harness = TestHarness()
        harness.access_pin = ""
        assert harness._request_headers() == {}

    def test_with_access_pin(self, monkeypatch):
        monkeypatch.setenv("AGK_HARNESS_ACCESS_PIN", "test-pin")
        harness = TestHarness()
        assert harness._request_headers()["X-Access-Pin"] == "test-pin"

    def test_with_extra_headers(self, monkeypatch):
        monkeypatch.setenv("AGK_HARNESS_ACCESS_PIN", "pin123")
        harness = TestHarness()
        headers = harness._request_headers({"Content-Type": "application/json"})
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Access-Pin"] == "pin123"


class TestDefaultIntents:
    def test_has_required_intents(self):
        intents = TestHarness.DEFAULT_INTENTS
        ids = {i.id for i in intents}
        assert "health_api" in ids
        assert "models_api" in ids
        assert "dashboard_load" in ids
        assert "chat_send" in ids
        assert "file_explorer" in ids
        assert "terminal_ws" in ids
        assert "vision_analyze" in ids
        assert "external_brain_list" in ids
        assert "autonomous_qa_dry" in ids
        assert "responsive_check" in ids

    def test_intent_priorities(self):
        for intent in TestHarness.DEFAULT_INTENTS:
            assert intent.priority in (1, 2, 3)
            assert intent.category in ("api", "ui", "integration")


class TestAddIntent:
    def test_add_intent_appends(self):
        harness = TestHarness()
        original_count = len(harness.intents)
        new_intent = TestIntent(id="custom_test", intent="Custom test", category="api", priority=3)
        harness.add_intent(new_intent)
        assert len(harness.intents) == original_count + 1

    def test_get_latest_report_empty(self):
        harness = TestHarness()
        assert harness.get_latest_report() is None
