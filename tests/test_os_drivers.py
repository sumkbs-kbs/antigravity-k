"""Tests for OS driver abstraction layer (os_drivers.py)."""

from __future__ import annotations

from unittest import mock

from antigravity_k.tools.os_drivers import (
    DriverSet,
    StubKeyboardDriver,
    StubMouseDriver,
    StubScreenDriver,
    get_driver_set,
)


class TestStubMouseDriver:
    """StubMouseDriver: no real mouse interaction, just records last_action."""

    def test_move_records_action(self):
        driver = StubMouseDriver()
        driver.move(100, 200, duration=0.5)
        assert driver.last_action == ("move", 100, 200)

    def test_move_default_duration(self):
        driver = StubMouseDriver()
        driver.move(50, 60)
        assert driver.last_action == ("move", 50, 60)

    def test_click_default_button(self):
        driver = StubMouseDriver()
        driver.click(10, 20)
        assert driver.last_action == ("click", 10, 20, "left")

    def test_click_right_button(self):
        driver = StubMouseDriver()
        driver.click(10, 20, button="right")
        assert driver.last_action == ("click", 10, 20, "right")

    def test_double_click(self):
        driver = StubMouseDriver()
        driver.double_click(30, 40)
        assert driver.last_action == ("double_click", 30, 40)

    def test_drag(self):
        driver = StubMouseDriver()
        driver.drag(0, 0, 100, 100, duration=1.0)
        assert driver.last_action == ("drag", 0, 0, 100, 100)

    def test_scroll_default(self):
        driver = StubMouseDriver()
        driver.scroll(50, 50)
        assert driver.last_action == ("scroll", 50, 50, "down", 3)

    def test_scroll_up(self):
        driver = StubMouseDriver()
        driver.scroll(50, 50, direction="up", amount=5)
        assert driver.last_action == ("scroll", 50, 50, "up", 5)

    def test_initial_last_action_is_none(self):
        driver = StubMouseDriver()
        assert driver.last_action is None


class TestStubKeyboardDriver:
    """StubKeyboardDriver: no real keyboard input, just records last_action."""

    def test_type_text(self):
        driver = StubKeyboardDriver()
        driver.type_text("hello", interval=0.1)
        assert driver.last_action == ("type", "hello")

    def test_press_key(self):
        driver = StubKeyboardDriver()
        driver.press_key("enter")
        assert driver.last_action == ("press", "enter")

    def test_hotkey(self):
        driver = StubKeyboardDriver()
        driver.hotkey("ctrl", "c")
        assert driver.last_action == ("hotkey", ("ctrl", "c"))

    def test_hold_key(self):
        driver = StubKeyboardDriver()
        driver.hold_key("shift", duration=2.0)
        assert driver.last_action == ("hold_key", "shift", 2.0)

    def test_initial_last_action_is_none(self):
        driver = StubKeyboardDriver()
        assert driver.last_action is None


class TestStubScreenDriver:
    """StubScreenDriver: returns dummy base64 PNG and fixed screen size."""

    def test_screenshot_returns_png(self):
        driver = StubScreenDriver()
        result = driver.screenshot()
        assert isinstance(result, str)
        assert len(result) > 0
        # Tiny PNG header magic
        assert result.startswith("iVBORw0KGgo")

    def test_screenshot_region_ignored(self):
        driver = StubScreenDriver()
        result = driver.screenshot(region=(0, 0, 100, 100))
        assert isinstance(result, str)
        assert result.startswith("iVBORw0KGgo")

    def test_get_screen_size(self):
        driver = StubScreenDriver()
        w, h = driver.get_screen_size()
        assert w == 1920
        assert h == 1080


class TestDriverSet:
    """DriverSet groups mouse, keyboard, and screen drivers."""

    def test_driver_set_holds_references(self):
        mouse = StubMouseDriver()
        keyboard = StubKeyboardDriver()
        screen = StubScreenDriver()
        ds = DriverSet(mouse=mouse, keyboard=keyboard, screen=screen)
        assert ds.mouse is mouse
        assert ds.keyboard is keyboard
        assert ds.screen is screen

    def test_driver_set_components_work(self):
        ds = DriverSet(
            mouse=StubMouseDriver(),
            keyboard=StubKeyboardDriver(),
            screen=StubScreenDriver(),
        )
        ds.mouse.move(1, 2)
        assert ds.mouse.last_action == ("move", 1, 2)
        ds.keyboard.press_key("tab")
        assert ds.keyboard.last_action == ("press", "tab")
        assert ds.screen.get_screen_size() == (1920, 1080)


class TestGetDriverSet:
    """Factory function get_driver_set()."""

    def test_force_stub_returns_stub_drivers(self):
        ds = get_driver_set(force_stub=True)
        assert isinstance(ds.mouse, StubMouseDriver)
        assert isinstance(ds.keyboard, StubKeyboardDriver)
        assert isinstance(ds.screen, StubScreenDriver)

    def test_stub_drivers_are_functional(self):
        ds = get_driver_set(force_stub=True)
        ds.mouse.click(100, 100)
        assert ds.mouse.last_action[0] == "click"
        ds.keyboard.type_text("test")
        assert ds.keyboard.last_action == ("type", "test")
        assert ds.screen.get_screen_size() == (1920, 1080)

    @mock.patch("antigravity_k.tools.os_drivers.sys.platform", "linux")
    def test_linux_uses_stub(self):
        ds = get_driver_set(force_stub=False)
        assert isinstance(ds.mouse, StubMouseDriver)

    @mock.patch("antigravity_k.tools.os_drivers.WindowsMouseDriver", side_effect=ImportError("mocked"))
    @mock.patch("antigravity_k.tools.os_drivers.WindowsKeyboardDriver", side_effect=ImportError("mocked"))
    @mock.patch("antigravity_k.tools.os_drivers.WindowsScreenDriver", side_effect=ImportError("mocked"))
    @mock.patch("antigravity_k.tools.os_drivers.sys.platform", "win32")
    def test_windows_falls_back_to_stub(self, *_mocks):
        ds = get_driver_set(force_stub=False)
        assert isinstance(ds.mouse, StubMouseDriver)
        assert isinstance(ds.keyboard, StubKeyboardDriver)
        assert isinstance(ds.screen, StubScreenDriver)
