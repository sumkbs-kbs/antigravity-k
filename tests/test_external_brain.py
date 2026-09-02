"""Antigravity-K: External Brain Unit Tests.
==========================================
ExternalBrainRouter 전략 라우팅, 어댑터 가용성 확인, 예외 처리 등
GUI/브라우저 없이 단위 테스트 가능한 모든 코드 경로 검증.
"""

from __future__ import annotations

from typing import Callable, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.engine.external_brain import (
    BrainResponse,
    ChatGPTWebAdapter,
    ExternalBrainAdapter,
    ExternalBrainRouter,
    GeminiAppAdapter,
    GeminiWebAdapter,
)


def _mock_async(adapter: MagicMock, name: str) -> AsyncMock:
    return cast(AsyncMock, getattr(adapter, name))


def _response_side_effect(text: str, source: str, latency_ms: float = 0.0) -> Callable[[str], BrainResponse]:
    def respond(_prompt: str) -> BrainResponse:
        return BrainResponse(text=text, source=source, success=True, latency_ms=latency_ms)

    return respond

# ─── BrainResponse ─────────────────────────────────────────────────


class TestBrainResponse:
    """BrainResponse 데이터클래스 생성 및 기본 동작."""

    def test_create_success(self):
        resp = BrainResponse(text="hello", source="gemini_app", success=True)
        assert resp.text == "hello"
        assert resp.source == "gemini_app"
        assert resp.success is True
        assert resp.error == ""

    def test_create_failure(self):
        resp = BrainResponse(text="", source="chatgpt_web", success=False, error="timeout")
        assert resp.success is False
        assert resp.error == "timeout"
        assert resp.latency_ms == 0.0


# ─── ExternalBrainRouter ──────────────────────────────────────────


@pytest.fixture
def mock_adapter() -> MagicMock:
    """가짜 어댑터 — 실제 브라우저/앱 필요 없음."""
    adapter = MagicMock(spec=ExternalBrainAdapter)
    adapter.name = "mock_brain"
    adapter.timeout_sec = 30.0
    adapter.send = AsyncMock()
    adapter.is_available = AsyncMock()
    return adapter


class TestExternalBrainRouterInit:
    """Router 초기화 테스트."""

    def test_default_adapters(self):
        router = ExternalBrainRouter()
        assert len(router.adapters) == 3
        names = [a.name for a in router.adapters]
        assert "gemini_app" in names
        assert "chatgpt_web" in names
        assert "gemini_web" in names

    def test_custom_adapters(self, mock_adapter: MagicMock):
        router = ExternalBrainRouter(adapters=[mock_adapter])
        assert len(router.adapters) == 1
        assert router.adapters[0].name == "mock_brain"


class TestExternalBrainRouterSendTarget:
    """Router.send() — target 파라미터."""

    @pytest.mark.asyncio
    async def test_target_available(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = True
        _mock_async(mock_adapter, "send").return_value = BrainResponse(text="ok", source="mock_brain", success=True)
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", target="mock_brain")
        assert result.success is True
        assert result.text == "ok"
        _mock_async(mock_adapter, "send").assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_target_not_available(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = False
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", target="mock_brain")
        assert result.success is False
        assert "사용 불가" in result.error

    @pytest.mark.asyncio
    async def test_target_not_found(self, mock_adapter: MagicMock):
        mock_adapter.name = "other_brain"
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", target="nonexistent")
        assert result.success is False
        assert "찾을 수 없" in result.error


class TestExternalBrainRouterFallback:
    """Router.send(strategy='fallback') — 폴백 전략."""

    @pytest.mark.asyncio
    async def test_first_adapter_succeeds(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = True
        _mock_async(mock_adapter, "send").return_value = BrainResponse(text="ok", source="mock_brain", success=True)
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", strategy="fallback")
        assert result.success is True
        assert result.text == "ok"

    @pytest.mark.asyncio
    async def test_all_fail(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = True
        _mock_async(mock_adapter, "send").return_value = BrainResponse(text="", source="mock_brain", success=False, error="fail")
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", strategy="fallback")
        assert result.success is False
        assert "모든" in result.error

    @pytest.mark.asyncio
    async def test_adapter_not_available_skips(self):
        a1 = MagicMock(spec=ExternalBrainAdapter)
        a1.name = "brain_a"
        a1.timeout_sec = 30.0
        _mock_async(a1, "is_available").side_effect = lambda: False
        _mock_async(a1, "send").side_effect = lambda: None

        a2 = MagicMock(spec=ExternalBrainAdapter)
        a2.name = "brain_b"
        a2.timeout_sec = 30.0
        _mock_async(a2, "is_available").side_effect = lambda: True
        _mock_async(a2, "send").side_effect = _response_side_effect("from_b", "brain_b")

        router = ExternalBrainRouter(adapters=[a1, a2])
        result = await router.send("test", strategy="fallback")
        assert result.success is True
        assert result.text == "from_b"
        _mock_async(a1, "send").assert_not_called()


class TestExternalBrainRouterRoundRobin:
    """Router.send(strategy='round-robin') — 순환 전략."""

    @pytest.mark.asyncio
    async def test_single_adapter(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = True
        _mock_async(mock_adapter, "send").return_value = BrainResponse(text="ok", source="mock_brain", success=True)
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", strategy="round-robin")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_rotation(self):
        a1 = MagicMock(spec=ExternalBrainAdapter)
        a1.name = "brain_a"
        a1.timeout_sec = 30.0
        a1.is_available = AsyncMock(return_value=True)
        a1.send = AsyncMock(return_value=BrainResponse(text="a", source="brain_a", success=True))

        a2 = MagicMock(spec=ExternalBrainAdapter)
        a2.name = "brain_b"
        a2.timeout_sec = 30.0
        a2.is_available = AsyncMock(return_value=True)
        a2.send = AsyncMock(return_value=BrainResponse(text="b", source="brain_b", success=True))

        router = ExternalBrainRouter(adapters=[a1, a2])

        r1 = await router.send("test", strategy="round-robin")
        r2 = await router.send("test", strategy="round-robin")
        assert r1.text == "a"
        assert r2.text == "b"

    @pytest.mark.asyncio
    async def test_no_available(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = False
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", strategy="round-robin")
        assert result.success is False
        assert "가용 두뇌 없음" in result.error


class TestExternalBrainRouterCompare:
    """Router.send(strategy='compare') — 비교 전략."""

    @pytest.mark.asyncio
    async def test_all_successful(self):
        a1 = MagicMock(spec=ExternalBrainAdapter)
        a1.name = "brain_a"
        a1.timeout_sec = 30.0
        _mock_async(a1, "is_available").side_effect = lambda: True
        _mock_async(a1, "send").side_effect = _response_side_effect("result_a", "brain_a", 100)

        a2 = MagicMock(spec=ExternalBrainAdapter)
        a2.name = "brain_b"
        a2.timeout_sec = 30.0
        _mock_async(a2, "is_available").side_effect = lambda: True
        _mock_async(a2, "send").side_effect = _response_side_effect("result_b", "brain_b", 200)

        router = ExternalBrainRouter(adapters=[a1, a2])
        result = await router.send("test", strategy="compare")
        assert result.success is True
        assert result.source == "compare"
        assert "brain_a" in result.text
        assert "brain_b" in result.text

    @pytest.mark.asyncio
    async def test_all_fail(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = True
        _mock_async(mock_adapter, "send").return_value = BrainResponse(text="", source="mock_brain", success=False, error="fail")
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", strategy="compare")
        assert result.success is False
        assert "모든 비교 실패" in result.error

    @pytest.mark.asyncio
    async def test_no_available(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = False
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", strategy="compare")
        assert result.success is False
        assert "가용 두뇌 없음" in result.error


class TestExternalBrainRouterUnknownStrategy:
    """Router.send() — 알 수 없는 전략 (기본 fallback)."""

    @pytest.mark.asyncio
    async def test_unknown_strategy_falls_back(self, mock_adapter: MagicMock):
        _mock_async(mock_adapter, "is_available").return_value = True
        _mock_async(mock_adapter, "send").return_value = BrainResponse(text="ok", source="mock_brain", success=True)
        router = ExternalBrainRouter(adapters=[mock_adapter])

        result = await router.send("test", strategy="invalid")
        assert result.success is True


class TestExternalBrainRouterListAvailable:
    """Router.list_available() — 가용 어댑터 목록."""

    @pytest.mark.asyncio
    async def test_returns_dicts(self):
        a1 = MagicMock(spec=ExternalBrainAdapter)
        a1.name = "brain_a"
        a1.timeout_sec = 30.0
        a1.is_available = AsyncMock(return_value=True)

        router = ExternalBrainRouter(adapters=[a1])
        result = await router.list_available()
        assert len(result) == 1
        assert result[0]["name"] == "brain_a"
        assert result[0]["available"] is True
        assert result[0]["timeout_sec"] == 30.0


# ─── GeminiAppAdapter ─────────────────────────────────────────────


class TestGeminiAppAdapter:
    """GeminiAppAdapter — is_available, init."""

    def test_init(self):
        adapter = GeminiAppAdapter(timeout_sec=60.0)
        assert adapter.name == "gemini_app"
        assert adapter.timeout_sec == 60.0

    @pytest.mark.asyncio
    async def test_is_available_no_osascript(self):
        """osascript가 없으면 False 반환."""
        adapter = GeminiAppAdapter()
        with patch("antigravity_k.engine.external_brain.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("osascript not found")
            result = await adapter.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_not_found(self):
        """앱이 실행 중이 아니고 번들도 없으면 False."""
        adapter = GeminiAppAdapter()
        with patch("antigravity_k.engine.external_brain.subprocess.run") as mock_run:
            # 첫 번째 호출(osascript): false → "true" in "false" → False
            # 두 번째 호출(mdfind): 빈 문자열 → bool("") → False
            mock_run.side_effect = [
                MagicMock(stdout="false"),
                MagicMock(stdout=""),
            ]
            result = await adapter.is_available()
        assert result is False


# ─── ChatGPTWebAdapter ────────────────────────────────────────────


class TestChatGPTWebAdapter:
    """ChatGPTWebAdapter — is_available, init."""

    def test_init_defaults(self):
        adapter = ChatGPTWebAdapter()
        assert adapter.name == "chatgpt_web"
        assert adapter.timeout_sec == 120.0
        assert adapter.cookies_path == ""

    def test_init_custom(self):
        adapter = ChatGPTWebAdapter(timeout_sec=60.0, cookies_path="/tmp/cookies.json")
        assert adapter.timeout_sec == 60.0
        assert adapter.cookies_path == "/tmp/cookies.json"

    @pytest.mark.asyncio
    async def test_is_available_no_playwright(self):
        adapter = ChatGPTWebAdapter()
        with patch("antigravity_k.engine.external_brain.importlib.util.find_spec") as mock_find:
            mock_find.return_value = None
            result = await adapter.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_with_playwright(self):
        adapter = ChatGPTWebAdapter()
        with patch("antigravity_k.engine.external_brain.importlib.util.find_spec") as mock_find:
            mock_find.return_value = MagicMock()
            result = await adapter.is_available()
        assert result is True


# ─── GeminiWebAdapter ─────────────────────────────────────────────


class TestGeminiWebAdapter:
    """GeminiWebAdapter — is_available, init."""

    def test_init(self):
        adapter = GeminiWebAdapter(timeout_sec=90.0)
        assert adapter.name == "gemini_web"
        assert adapter.timeout_sec == 90.0

    @pytest.mark.asyncio
    async def test_is_available_no_playwright(self):
        adapter = GeminiWebAdapter()
        with patch("antigravity_k.engine.external_brain.importlib.util.find_spec") as mock_find:
            mock_find.return_value = None
            result = await adapter.is_available()
        assert result is False
