"""Tests for external_brain — ExternalBrainRouter, BrainResponse, adapter classes.

Covers BrainResponse dataclass, ExternalBrainAdapter ABC, ExternalBrainRouter
(send with fallback/round-robin/compare/target), list_available, GeminiAppAdapter
is_available/send with mocked subprocess, ChatGPTWebAdapter is_available.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.external_brain import (
    BrainResponse,
    ChatGPTWebAdapter,
    ExternalBrainAdapter,
    ExternalBrainRouter,
    GeminiAppAdapter,
    GeminiWebAdapter,
)

# ---------------------------------------------------------------------------
# BrainResponse dataclass
# ---------------------------------------------------------------------------


class TestBrainResponse:
    def test_defaults(self):
        r = BrainResponse(text="hello", source="test")
        assert r.text == "hello"
        assert r.source == "test"
        assert r.latency_ms == 0.0
        assert r.success is True
        assert r.error == ""

    def test_error_response(self):
        r = BrainResponse(text="", source="gemini_app", success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"

    def test_latency(self):
        r = BrainResponse(text="ok", source="chatgpt_web", latency_ms=1234.5)
        assert r.latency_ms == 1234.5


# ---------------------------------------------------------------------------
# ExternalBrainAdapter base
# ---------------------------------------------------------------------------


class TestExternalBrainAdapter:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ExternalBrainAdapter("test")  # type: ignore[abstract]

    def test_concrete_adapter_inits(self):
        adapter = GeminiAppAdapter()
        assert adapter.name == "gemini_app"
        assert adapter.timeout_sec == 120.0


# ---------------------------------------------------------------------------
# GeminiAppAdapter — is_available (mocked subprocess)
# ---------------------------------------------------------------------------


class TestGeminiAppAdapter:
    def test_is_available_process_running(self):
        from unittest.mock import patch

        adapter = GeminiAppAdapter()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "true"
            import asyncio

            result = asyncio.run(adapter.is_available())
            assert result is True
            assert adapter._available is True

    def test_is_available_app_bundle_found(self):
        from unittest.mock import patch

        adapter = GeminiAppAdapter()
        with patch("subprocess.run") as mock_run:
            # First call (process check) returns false, second (mdfind) returns path
            mock_run.side_effect = [
                type("ProcResult", (), {"stdout": "false"})(),
                type("ProcResult", (), {"stdout": "/Applications/Gemini.app"})(),
            ]
            import asyncio

            result = asyncio.run(adapter.is_available())
            assert result is True

    def test_is_available_not_found(self):
        from unittest.mock import patch

        adapter = GeminiAppAdapter()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                type("ProcResult", (), {"stdout": "false"})(),
                type("ProcResult", (), {"stdout": ""})(),
            ]
            import asyncio

            result = asyncio.run(adapter.is_available())
            assert result is False

    def test_is_available_exception_returns_false(self):
        from unittest.mock import patch

        adapter = GeminiAppAdapter()
        with patch("subprocess.run", side_effect=RuntimeError("osascript failed")):
            import asyncio

            result = asyncio.run(adapter.is_available())
            assert result is False


# ---------------------------------------------------------------------------
# ChatGPTWebAdapter — is_available
# ---------------------------------------------------------------------------


class TestChatGPTWebAdapter:
    def test_is_available_playwright_installed(self):
        adapter = ChatGPTWebAdapter()
        import asyncio

        result = asyncio.run(adapter.is_available())
        # playwright is installed as a dependency, so should be True
        assert result is True

    def test_init_defaults(self):
        adapter = ChatGPTWebAdapter()
        assert adapter.name == "chatgpt_web"
        assert adapter.timeout_sec == 120.0
        assert adapter.cookies_path == ""


# ---------------------------------------------------------------------------
# GeminiWebAdapter
# ---------------------------------------------------------------------------


class TestGeminiWebAdapter:
    def test_init_defaults(self):
        adapter = GeminiWebAdapter()
        assert adapter.name == "gemini_web"
        assert adapter.timeout_sec == 120.0

    def test_is_available_playwright_detected(self):
        adapter = GeminiWebAdapter()
        import asyncio

        result = asyncio.run(adapter.is_available())
        assert result is True


# ---------------------------------------------------------------------------
# ExternalBrainRouter
# ---------------------------------------------------------------------------


class TestExternalBrainRouter:
    def test_init_default_adapters(self):
        router = ExternalBrainRouter()
        assert len(router.adapters) == 3
        assert isinstance(router.adapters[0], GeminiAppAdapter)
        assert isinstance(router.adapters[1], ChatGPTWebAdapter)
        assert isinstance(router.adapters[2], GeminiWebAdapter)

    def test_init_custom_adapters(self):
        adapters = [GeminiAppAdapter()]
        router = ExternalBrainRouter(adapters=adapters)
        assert len(router.adapters) == 1

    def test_list_available(self):
        from unittest.mock import patch

        router = ExternalBrainRouter(adapters=[])
        with patch.object(router, "adapters", []):
            import asyncio

            result = asyncio.run(router.list_available())
            assert result == []

    def test_send_with_target_not_found(self):
        from unittest.mock import patch

        router = ExternalBrainRouter(adapters=[])
        import asyncio

        with patch.object(router, "adapters", []):
            result = asyncio.run(router.send("test", target="nonexistent"))
            assert result.success is False
            assert "찾을 수 없거나" in result.error

    def test_send_fallback_none_available(self):
        from unittest.mock import patch

        router = ExternalBrainRouter(adapters=[])
        import asyncio

        with patch.object(router, "adapters", []):
            result = asyncio.run(router.send("test", strategy="fallback"))
            assert result.success is False
            assert "사용 불가" in result.error

    def test_send_round_robin_none_available(self):
        from unittest.mock import patch

        router = ExternalBrainRouter(adapters=[])
        import asyncio

        with patch.object(router, "adapters", []):
            result = asyncio.run(router.send("test", strategy="round-robin"))
            assert result.success is False
            assert "가용 두뇌 없음" in result.error

    def test_send_compare_none_available(self):
        router = ExternalBrainRouter(adapters=[])
        import asyncio

        result = asyncio.run(router.send("test", strategy="compare"))
        assert result.success is False
