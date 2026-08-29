"""Antigravity-K: External Brain E2E Integration Test.
==================================================
ExternalBrainRouter의 엔드투엔드 위임 동작을 검증합니다.
"""

from unittest.mock import AsyncMock, patch

import pytest

from antigravity_k.engine.cognitive_loop import CognitiveLoop
from antigravity_k.engine.external_brain import BrainResponse, ExternalBrainRouter


@pytest.mark.asyncio
async def test_external_brain_e2e_delegation():
    """External Brain 라우터 위임 프로세스의 End-to-End 동작 검증."""
    router = ExternalBrainRouter()

    # Mock adapter response
    mock_response = BrainResponse(text="외부 두뇌에서 해결한 결과입니다.", source="chatgpt_web", success=True)

    with patch(
        "antigravity_k.engine.external_brain.ChatGPTWebAdapter.send",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = mock_response

        _ = CognitiveLoop(
            project_root="/tmp",
            external_brain_router=router,
        )

        result = await router.send("복잡한 문제 해결해주세요", target="chatgpt_web")

        assert result is not None
        assert "외부 두뇌에서 해결한 결과입니다." in result.text
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_external_brain_timeout_handling():
    """External Brain 라우터의 타임아웃 예외 처리 검증."""
    router = ExternalBrainRouter()

    # Adapter itself returns BrainResponse with error on exception
    mock_response = BrainResponse(text="", source="chatgpt_web", success=False, error="Connection timeout")

    with patch(
        "antigravity_k.engine.external_brain.ChatGPTWebAdapter.send",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = mock_response

        result = await router.send("복잡한 문제", target="chatgpt_web")

        assert result is not None
        assert result.success is False
        assert "timeout" in result.error.lower()
