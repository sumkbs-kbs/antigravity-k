import pytest
from starlette.requests import Request

from antigravity_k.api.browser_session_state import BrowserSessionLimitError, BrowserSessionRegistry
from antigravity_k.api.routes import agent_tools
from antigravity_k.api.routes.agent_tools import _MAX_CONSOLE_ENTRIES, _append_console_entry


def test_console_capture_is_bounded() -> None:
    entries: list[dict[str, str]] = []
    for index in range(_MAX_CONSOLE_ENTRIES + 25):
        _append_console_entry(entries, {"type": "log", "text": str(index)})

    assert len(entries) == _MAX_CONSOLE_ENTRIES
    assert entries[0]["text"] == "25"


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


def test_browser_route_session_header_selects_isolated_state(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = BrowserSessionRegistry(max_sessions=2)
    monkeypatch.setattr(agent_tools, "browser_sessions", registry)

    first_request = Request({"type": "http", "headers": [(b"x-agk-browser-session", b"first")]})
    second_request = Request({"type": "http", "headers": [(b"x-agk-browser-session", b"second")]})

    first_id, first_state = agent_tools._browser_state_for(first_request)
    second_id, second_state = agent_tools._browser_state_for(second_request)

    assert first_id != second_id
    assert first_state is not second_state
    assert agent_tools._browser_state_for(first_request)[1] is first_state


def test_browser_session_header_is_scoped_to_authenticated_subject() -> None:
    first_request = Request({"type": "http", "headers": [(b"x-agk-browser-session", b"shared")]})
    second_request = Request({"type": "http", "headers": [(b"x-agk-browser-session", b"shared")]})
    first_request.state.auth_subject = "user-a"
    second_request.state.auth_subject = "user-b"

    assert agent_tools._browser_session_id(first_request) != agent_tools._browser_session_id(second_request)
