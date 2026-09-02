from collections.abc import Awaitable, Callable, Mapping
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.agents.browser_surfing_agent import (
    BrowserAction,
    BrowserSurfingAgent,
)


@pytest.fixture
def mock_model_manager() -> MagicMock:
    manager = MagicMock()
    # Mocking the async generate method
    mock_response = MagicMock()
    mock_response.text = '{"action": "extract", "extracted_data": "Found the info"}'
    manager.generate = AsyncMock(return_value=mock_response)
    return manager


@pytest.mark.asyncio
async def test_browser_surfing_agent_init(mock_model_manager: MagicMock) -> None:
    agent = BrowserSurfingAgent(model_manager=mock_model_manager)
    assert agent.vision_model_name == "qwen3.6:latest"


@pytest.mark.asyncio
@patch("antigravity_k.agents.browser_surfing_agent.async_playwright")
async def test_surf_with_mock_playwright(mock_async_playwright: MagicMock, mock_model_manager: MagicMock) -> None:
    # Setup mock playwright
    mock_pw = AsyncMock()
    mock_browser = AsyncMock()
    mock_page = AsyncMock()

    playwright_factory = cast(MagicMock, getattr(mock_async_playwright, "return_value"))
    setattr(playwright_factory, "start", AsyncMock(return_value=mock_pw))
    chromium = cast(MagicMock, getattr(mock_pw, "chromium"))
    setattr(chromium, "launch", AsyncMock(return_value=mock_browser))
    browser = cast(MagicMock, mock_browser)
    setattr(browser, "new_page", AsyncMock(return_value=mock_page))

    # Mock extract elements
    page = cast(MagicMock, mock_page)
    setattr(page, "evaluate", AsyncMock(return_value="[1] button : Click me"))

    # Run surf
    agent = BrowserSurfingAgent(model_manager=mock_model_manager)
    result = await agent.surf("http://example.com", "find info", max_steps=2)

    # Our mock model returns {"action": "extract", "extracted_data": "Found the info"}
    # So it should break on the first step and return the extracted data
    assert result == "Found the info"

    # Verify page navigation
    goto = cast(MagicMock, getattr(page, "goto"))
    goto.assert_called_once_with("http://example.com", wait_until="networkidle", timeout=15000)
    generate = cast(MagicMock, getattr(mock_model_manager, "generate"))
    generate.assert_called_once()


@pytest.mark.asyncio
async def test_decide_next_action_routes_target_and_screenshot_to_manager():
    manager = MagicMock()
    get_target = cast(MagicMock, getattr(manager, "get_target_for_role"))
    setattr(get_target, "return_value", "local-vision")
    generate = cast(MagicMock, getattr(manager, "generate"))
    setattr(generate, "return_value", '{"action":"done","reason":"complete"}')

    agent = BrowserSurfingAgent(model_manager=manager)
    decide = cast(
        Callable[[str, str, bytes], Awaitable[BrowserAction]],
        getattr(agent, "_decide_next_action"),
    )
    action = await decide("find info", "button", b"png-bytes")

    assert action.action == "done"
    call = cast(object, getattr(generate, "call_args"))
    assert isinstance(call, tuple)
    call_tuple = cast(tuple[object, ...], call)
    kwargs = cast(Mapping[str, object], call_tuple[1])
    assert kwargs["target"] == "local-vision"
    raw_messages = cast(list[Mapping[str, object]], kwargs["raw_messages"])
    images = cast(list[object], raw_messages[0]["images"])
    assert images
