from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright


BrowserConsoleEntry = dict[str, str]


class BrowserSessionLimitError(RuntimeError):
    pass


@final
class BrowserSessionState:
    """Mutable owner of one optional Playwright browser session."""

    def __init__(self) -> None:
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.console_errors: list[BrowserConsoleEntry] = []
        self.console_logs: list[BrowserConsoleEntry] = []


class BrowserSessionRegistry:
    """Owns isolated browser states with a bounded number of custom sessions."""

    def __init__(self, max_sessions: int = 32, default_state: BrowserSessionState | None = None) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        self._max_sessions: int = max_sessions
        self._sessions: OrderedDict[str, BrowserSessionState] = OrderedDict()
        self._sessions["default"] = default_state or BrowserSessionState()

    def get(self, session_id: str) -> BrowserSessionState:
        """Return a session state, creating it unless the custom-session cap is reached."""
        normalized_id = session_id.strip() or "default"
        state = self._sessions.get(normalized_id)
        if state is not None:
            self._sessions.move_to_end(normalized_id)
            return state
        custom_count = len(self._sessions) - 1
        if custom_count >= self._max_sessions:
            raise BrowserSessionLimitError("Too many active browser sessions")
        state = BrowserSessionState()
        self._sessions[normalized_id] = state
        return state

    def discard(self, session_id: str) -> BrowserSessionState | None:
        """Remove a custom session and return its state; keep the legacy default state."""
        normalized_id = session_id.strip() or "default"
        if normalized_id == "default":
            return None
        return self._sessions.pop(normalized_id, None)
