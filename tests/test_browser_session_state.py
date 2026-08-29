import pytest
from starlette.requests import Request

from antigravity_k.api.browser_session_state import BrowserSessionLimitError, BrowserSessionRegistry
from antigravity_k.api.routes.agent_tools import _browser_session_id


def _request_for_subject(subject: str) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    request.state.auth_subject = subject
    return request


def test_browser_sessions_are_isolated_and_bounded() -> None:
    registry = BrowserSessionRegistry(max_sessions=2)

    default_state = registry.get("default")
    first_state = registry.get("first")
    second_state = registry.get("second")

    assert first_state is registry.get("first")
    assert first_state is not second_state
    assert default_state is not first_state

    with pytest.raises(BrowserSessionLimitError):
        registry.get("third")


def test_browser_session_discard_keeps_default_compatibility() -> None:
    registry = BrowserSessionRegistry(max_sessions=2)
    default_state = registry.get("default")
    custom_state = registry.get("custom")

    assert registry.discard("custom") is custom_state
    assert registry.discard("custom") is None
    assert registry.get("default") is default_state


def test_browser_default_session_is_scoped_to_authenticated_subject() -> None:
    first = _browser_session_id(_request_for_subject("first-user"))
    second = _browser_session_id(_request_for_subject("second-user"))
    repeat = _browser_session_id(_request_for_subject("first-user"))

    assert first != second
    assert first == repeat
