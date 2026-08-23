from __future__ import annotations

from threading import Event

import pytest
from textual.widgets import Button

from antigravity_k.tui.app import AgkTUI, ChatScreen, HelpScreen


@pytest.mark.asyncio
async def test_workbench_focuses_input_on_startup() -> None:
    app = AgkTUI()

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChatScreen)

        assert screen.input.has_focus


@pytest.mark.asyncio
async def test_workbench_renders_one_welcome_message() -> None:
    app = AgkTUI()

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChatScreen)
        title_lines = [line for line in screen.chat_log.lines if "Antigravity-K TUI" in str(line)]

        assert len(title_lines) == 1


@pytest.mark.asyncio
async def test_help_content_and_close_control_fit_standard_terminal() -> None:
    app = AgkTUI()

    async with app.run_test(size=(100, 34)) as pilot:
        screen = app.screen
        assert isinstance(screen, ChatScreen)
        screen.action_open_help()
        await pilot.pause()
        help_screen = app.screen
        assert isinstance(help_screen, HelpScreen)
        close_button = help_screen.query_one("#help-close", Button)

        assert close_button.region.height > 0
        assert close_button.region.bottom <= app.size.height


@pytest.mark.asyncio
async def test_ctrl_c_clears_draft_before_any_destructive_action() -> None:
    app = AgkTUI()

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, ChatScreen)
        screen.input.value = "보존하지 않을 초안"
        screen.input.focus()

        await pilot.press("ctrl+c")
        await pilot.pause()

        assert screen.input.value == ""
        assert app.is_running


@pytest.mark.asyncio
async def test_ctrl_c_cancels_active_task_when_input_is_empty() -> None:
    app = AgkTUI()
    release_worker = Event()

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, ChatScreen)
        worker = screen.run_worker(
            lambda: release_worker.wait(timeout=2),
            group="task",
            thread=True,
        )
        screen._processing = True
        screen._update_input_state(True)

        await pilot.press("ctrl+c")
        await pilot.pause()

        assert worker.is_cancelled
        assert not screen._processing
        assert screen.input.placeholder.startswith("Type a message")
        assert app.is_running
        release_worker.set()


@pytest.mark.asyncio
async def test_ctrl_c_exits_when_input_and_task_are_idle() -> None:
    app = AgkTUI()

    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, ChatScreen)
        assert screen.input.value == ""
        assert not screen._processing

        await pilot.press("ctrl+c")
        await pilot.pause()

        assert not app.is_running
