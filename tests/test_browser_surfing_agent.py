from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.agents.browser_surfing_agent import (
    BrowserSurfingAgent,
)


@pytest.fixture
def mock_model_manager():
    manager = MagicMock()
    # Mocking the async generate method
    mock_response = MagicMock()
    mock_response.text = '{"action": "extract", "extracted_data": "Found the info"}'
    manager.generate = AsyncMock(return_value=mock_response)
    return manager


@pytest.mark.asyncio
async def test_browser_surfing_agent_init(mock_model_manager):
    agent = BrowserSurfingAgent(model_manager=mock_model_manager)
    assert agent.vision_model_name == "qwen3.5-omni"


@pytest.mark.asyncio
@patch("antigravity_k.agents.browser_surfing_agent.async_playwright")
async def test_surf_with_mock_playwright(mock_async_playwright, mock_model_manager):
    # Setup mock playwright
    mock_pw = AsyncMock()
    mock_browser = AsyncMock()
    mock_page = AsyncMock()

    mock_async_playwright.return_value.start = AsyncMock(return_value=mock_pw)
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    # Mock extract elements
    mock_page.evaluate = AsyncMock(return_value="[1] button : Click me")

    # Run surf
    agent = BrowserSurfingAgent(model_manager=mock_model_manager)
    result = await agent.surf("http://example.com", "find info", max_steps=2)

    # Our mock model returns {"action": "extract", "extracted_data": "Found the info"}
    # So it should break on the first step and return the extracted data
    assert result == "Found the info"

    # Verify page navigation
    mock_page.goto.assert_called_once_with("http://example.com", wait_until="networkidle", timeout=15000)
    mock_model_manager.generate.assert_called_once()
