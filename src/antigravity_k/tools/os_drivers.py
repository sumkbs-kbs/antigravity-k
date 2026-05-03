"""
OS 드라이버 추상화 계층 (os-ai-computer-use의 DriverSet 패턴 차용)
========================================================================
마우스, 키보드, 화면 조작을 OS 독립적인 인터페이스로 추상화합니다.
현재는 Windows(PyAutoGUI) 드라이버만 구현되어 있으며,
향후 macOS(Quartz), Linux(X11)를 추가할 수 있습니다.
"""

import sys
import logging
import base64
import io
from abc import ABC, abstractmethod
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ───────────────────────── 추상 인터페이스 ──────────────────────────

class MouseDriver(ABC):
    """마우스 조작 추상 인터페이스."""

    @abstractmethod
    def move(self, x: int, y: int, duration: float = 0.3) -> None:
        """지정 좌표로 마우스를 이동합니다."""

    @abstractmethod
    def click(self, x: int, y: int, button: str = "left") -> None:
        """지정 좌표를 클릭합니다. button: 'left', 'right', 'middle'"""

    @abstractmethod
    def double_click(self, x: int, y: int) -> None:
        """더블 클릭합니다."""

    @abstractmethod
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> None:
        """드래그합니다."""

    @abstractmethod
    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> None:
        """스크롤합니다. direction: 'up', 'down', 'left', 'right'"""


class KeyboardDriver(ABC):
    """키보드 조작 추상 인터페이스."""

    @abstractmethod
    def type_text(self, text: str, interval: float = 0.02) -> None:
        """텍스트를 타이핑합니다."""

    @abstractmethod
    def press_key(self, key: str) -> None:
        """단일 키를 누릅니다 (예: 'enter', 'tab', 'escape')."""

    @abstractmethod
    def hotkey(self, *keys: str) -> None:
        """키 조합을 실행합니다 (예: 'ctrl', 'c')."""

    @abstractmethod
    def hold_key(self, key: str, duration: float = 1.0) -> None:
        """특정 키를 지정된 시간(초) 동안 길게 누릅니다."""


class ScreenDriver(ABC):
    """화면 캡처 추상 인터페이스."""

    @abstractmethod
    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """화면을 캡처하여 base64 PNG 문자열로 반환합니다."""

    @abstractmethod
    def get_screen_size(self) -> Tuple[int, int]:
        """(width, height) 형태로 화면 크기를 반환합니다."""


class DriverSet:
    """OS별 드라이버 묶음."""

    def __init__(self, mouse: MouseDriver, keyboard: KeyboardDriver, screen: ScreenDriver):
        self.mouse = mouse
        self.keyboard = keyboard
        self.screen = screen


# ───────────────────── Windows 구현 (PyAutoGUI) ─────────────────────

class WindowsMouseDriver(MouseDriver):
    """Windows PyAutoGUI 기반 마우스 드라이버."""

    def __init__(self):
        import pyautogui
        pyautogui.FAILSAFE = True  # 좌상단 이동 시 비상 중지
        pyautogui.PAUSE = 0.05
        self._pag = pyautogui

    def move(self, x: int, y: int, duration: float = 0.3) -> None:
        self._pag.moveTo(x, y, duration=duration)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self._pag.click(x, y, button=button)

    def double_click(self, x: int, y: int) -> None:
        self._pag.doubleClick(x, y)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> None:
        self._pag.moveTo(start_x, start_y)
        self._pag.drag(end_x - start_x, end_y - start_y, duration=duration)

    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> None:
        self._pag.moveTo(x, y)
        scroll_amount = -amount if direction == "down" else amount
        if direction in ("left", "right"):
            self._pag.hscroll(amount if direction == "right" else -amount)
        else:
            self._pag.scroll(scroll_amount)


class WindowsKeyboardDriver(KeyboardDriver):
    """Windows PyAutoGUI 기반 키보드 드라이버."""

    def __init__(self):
        import pyautogui
        self._pag = pyautogui

    def type_text(self, text: str, interval: float = 0.02) -> None:
        self._pag.write(text, interval=interval)

    def press_key(self, key: str) -> None:
        self._pag.press(key)

    def hotkey(self, *keys: str) -> None:
        self._pag.hotkey(*keys)

    def hold_key(self, key: str, duration: float = 1.0) -> None:
        import time
        self._pag.keyDown(key)
        time.sleep(duration)
        self._pag.keyUp(key)


class WindowsScreenDriver(ScreenDriver):
    """Windows PyAutoGUI 기반 화면 캡처 드라이버."""

    def __init__(self):
        import pyautogui
        self._pag = pyautogui

    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """화면 캡처 → base64 PNG 문자열 반환."""
        img = self._pag.screenshot(region=region)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def get_screen_size(self) -> Tuple[int, int]:
        return self._pag.size()


# ─────────────────────── Stub 구현 (테스트/비대화 환경용) ────────────

class StubMouseDriver(MouseDriver):
    """테스트용 마우스 드라이버 (실제 조작 없음)."""

    def __init__(self):
        self.last_action = None

    def move(self, x: int, y: int, duration: float = 0.3) -> None:
        self.last_action = ("move", x, y)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self.last_action = ("click", x, y, button)

    def double_click(self, x: int, y: int) -> None:
        self.last_action = ("double_click", x, y)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> None:
        self.last_action = ("drag", start_x, start_y, end_x, end_y)

    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> None:
        self.last_action = ("scroll", x, y, direction, amount)


class StubKeyboardDriver(KeyboardDriver):
    """테스트용 키보드 드라이버 (실제 입력 없음)."""

    def __init__(self):
        self.last_action = None

    def type_text(self, text: str, interval: float = 0.02) -> None:
        self.last_action = ("type", text)

    def press_key(self, key: str) -> None:
        self.last_action = ("press", key)

    def hotkey(self, *keys: str) -> None:
        self.last_action = ("hotkey", keys)

    def hold_key(self, key: str, duration: float = 1.0) -> None:
        self.last_action = ("hold_key", key, duration)


class StubScreenDriver(ScreenDriver):
    """테스트용 화면 드라이버 (1x1 투명 PNG 반환)."""

    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        # 최소 1x1 투명 PNG (base64)
        _TINY_PNG = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12Ng"
            "AAIABQABNjN9GQAAAABJRUEFAAUYAAEAAAABAAAABwAAAA=="
        )
        return _TINY_PNG

    def get_screen_size(self) -> Tuple[int, int]:
        return (1920, 1080)


# ───────────────────── macOS 구현 (Quartz / CoreGraphics) ──────────

class MacOSMouseDriver(MouseDriver):
    """macOS Quartz 기반 마우스 드라이버."""

    def move(self, x: int, y: int, duration: float = 0.3) -> None:
        import Quartz
        event = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved,
            Quartz.CGPointMake(x, y), Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def click(self, x: int, y: int, button: str = "left") -> None:
        import Quartz
        btn = Quartz.kCGMouseButtonLeft if button == "left" else Quartz.kCGMouseButtonRight
        down_type = Quartz.kCGEventLeftMouseDown if button == "left" else Quartz.kCGEventRightMouseDown
        up_type = Quartz.kCGEventLeftMouseUp if button == "left" else Quartz.kCGEventRightMouseUp
        point = Quartz.CGPointMake(x, y)

        down = Quartz.CGEventCreateMouseEvent(None, down_type, point, btn)
        up = Quartz.CGEventCreateMouseEvent(None, up_type, point, btn)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        import time; time.sleep(0.05)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def double_click(self, x: int, y: int) -> None:
        import Quartz, time
        point = Quartz.CGPointMake(x, y)
        btn = Quartz.kCGMouseButtonLeft
        for click_count in (1, 2):
            down = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventLeftMouseDown, point, btn
            )
            up = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventLeftMouseUp, point, btn
            )
            Quartz.CGEventSetIntegerValueField(down, Quartz.kCGMouseEventClickState, click_count)
            Quartz.CGEventSetIntegerValueField(up, Quartz.kCGMouseEventClickState, click_count)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
            time.sleep(0.02)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
            time.sleep(0.05)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> None:
        import Quartz, time
        btn = Quartz.kCGMouseButtonLeft
        start = Quartz.CGPointMake(start_x, start_y)
        end = Quartz.CGPointMake(end_x, end_y)

        down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, start, btn)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)

        steps = max(10, int(duration * 60))
        for i in range(1, steps + 1):
            t = i / steps
            cx = start_x + (end_x - start_x) * t
            cy = start_y + (end_y - start_y) * t
            drag_ev = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventLeftMouseDragged,
                Quartz.CGPointMake(cx, cy), btn
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, drag_ev)
            time.sleep(duration / steps)

        up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, end, btn)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> None:
        import Quartz
        self.move(x, y, duration=0)
        dy = -amount if direction == "down" else amount if direction == "up" else 0
        dx = amount if direction == "right" else -amount if direction == "left" else 0
        event = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 2, dy, dx)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


class MacOSKeyboardDriver(KeyboardDriver):
    """macOS Quartz 기반 키보드 드라이버."""

    # macOS 가상 키코드 매핑 (주요 키만)
    _KEY_MAP = {
        "return": 0x24, "enter": 0x24, "tab": 0x30, "space": 0x31,
        "delete": 0x33, "backspace": 0x33, "escape": 0x35, "esc": 0x35,
        "command": 0x37, "cmd": 0x37, "shift": 0x38, "capslock": 0x39,
        "option": 0x3A, "alt": 0x3A, "control": 0x3B, "ctrl": 0x3B,
        "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
        "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76,
        "f5": 0x60, "f6": 0x61, "f7": 0x62, "f8": 0x64,
        "home": 0x73, "end": 0x77, "pageup": 0x74, "pagedown": 0x79,
    }

    # 수정 키(modifier) 플래그 매핑
    _MOD_FLAGS = {
        "command": 0x100000, "cmd": 0x100000,
        "shift": 0x20000,
        "option": 0x80000, "alt": 0x80000,
        "control": 0x40000, "ctrl": 0x40000,
    }

    def _get_keycode(self, key: str) -> int:
        key_lower = key.lower()
        if key_lower in self._KEY_MAP:
            return self._KEY_MAP[key_lower]
        # 단일 문자 → 유니코드 기반 keycode (근사)
        if len(key) == 1:
            return ord(key.lower())  # CGEventKeyboardSetUnicodeString 사용 시
        return 0

    def type_text(self, text: str, interval: float = 0.02) -> None:
        import Quartz, time
        for char in text:
            event_down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            event_up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
            # 유니코드 문자 직접 주입
            Quartz.CGEventKeyboardSetUnicodeString(event_down, len(char), char)
            Quartz.CGEventKeyboardSetUnicodeString(event_up, len(char), char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)
            time.sleep(interval)

    def press_key(self, key: str) -> None:
        import Quartz
        keycode = self._get_keycode(key)
        down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
        up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def hotkey(self, *keys: str) -> None:
        import Quartz, time
        # 수정 키와 일반 키 분리
        mod_flags = 0
        normal_keys = []
        for k in keys:
            k_lower = k.lower()
            if k_lower in self._MOD_FLAGS:
                mod_flags |= self._MOD_FLAGS[k_lower]
            else:
                normal_keys.append(k)

        for nk in normal_keys:
            keycode = self._get_keycode(nk)
            down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
            up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
            if mod_flags:
                Quartz.CGEventSetFlags(down, mod_flags)
                Quartz.CGEventSetFlags(up, mod_flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
            time.sleep(0.02)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def hold_key(self, key: str, duration: float = 1.0) -> None:
        import Quartz, time
        keycode = self._get_keycode(key)
        down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
        up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        time.sleep(duration)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


class MacOSScreenDriver(ScreenDriver):
    """macOS Quartz 기반 화면 캡처 드라이버."""

    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """CGWindowListCreateImage로 화면을 캡처하고 base64 PNG로 반환합니다."""
        import Quartz
        import CoreFoundation

        if region:
            rect = Quartz.CGRectMake(*region)
        else:
            rect = Quartz.CGRectInfinite

        image = Quartz.CGWindowListCreateImage(
            rect,
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageDefault
        )

        if image is None:
            # subprocess 폴백
            return self._screenshot_subprocess(region)

        # CGImage → PNG data → base64
        bitmap = Quartz.NSBitmapImageRep.alloc().initWithCGImage_(image)
        png_data = bitmap.representationUsingType_properties_(
            Quartz.NSPNGFileType if hasattr(Quartz, 'NSPNGFileType') else 4, None
        )
        return base64.b64encode(bytes(png_data)).decode("utf-8")

    def _screenshot_subprocess(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """screencapture CLI 폴백."""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = ["screencapture", "-x"]
            if region:
                x, y, w, h = region
                cmd.extend(["-R", f"{x},{y},{w},{h}"])
            cmd.append(tmp_path)
            subprocess.run(cmd, check=True, timeout=10)

            with open(tmp_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        finally:
            import os as _os
            _os.unlink(tmp_path)

    def get_screen_size(self) -> Tuple[int, int]:
        try:
            import Quartz
            main_display = Quartz.CGMainDisplayID()
            w = Quartz.CGDisplayPixelsWide(main_display)
            h = Quartz.CGDisplayPixelsHigh(main_display)
            return (w, h)
        except Exception:
            # subprocess 폴백
            import subprocess
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5
                )
                import re as _re
                match = _re.search(r'Resolution:\s+(\d+)\s*x\s*(\d+)', result.stdout)
                if match:
                    return (int(match.group(1)), int(match.group(2)))
            except Exception:
                pass
            return (1920, 1080)


# ─────────────────── 팩토리 함수 ───────────────────

def get_driver_set(force_stub: bool = False) -> DriverSet:
    """
    현재 OS에 맞는 드라이버 셋을 반환합니다.
    - force_stub=True: 테스트 환경용 Stub 드라이버 반환
    - macOS: Quartz 네이티브 드라이버 (PyAutoGUI 폴백)
    - Windows: PyAutoGUI 기반 드라이버
    - 그 외: Stub 드라이버
    """
    if force_stub:
        logger.info("Using STUB drivers (no real desktop interaction)")
        return DriverSet(
            mouse=StubMouseDriver(),
            keyboard=StubKeyboardDriver(),
            screen=StubScreenDriver(),
        )

    if sys.platform == "darwin":
        # macOS: Quartz 네이티브 드라이버 시도
        try:
            import Quartz  # noqa: F401
            logger.info("Using macOS Quartz native drivers")
            return DriverSet(
                mouse=MacOSMouseDriver(),
                keyboard=MacOSKeyboardDriver(),
                screen=MacOSScreenDriver(),
            )
        except ImportError:
            logger.warning("Quartz (pyobjc-framework-Quartz) not available. Trying PyAutoGUI...")
            # PyAutoGUI 폴백
            try:
                return DriverSet(
                    mouse=WindowsMouseDriver(),  # PyAutoGUI는 크로스플랫폼
                    keyboard=WindowsKeyboardDriver(),
                    screen=WindowsScreenDriver(),
                )
            except ImportError:
                logger.warning("PyAutoGUI not installed. Falling back to Stub drivers.")
                return get_driver_set(force_stub=True)

    if sys.platform == "win32":
        try:
            return DriverSet(
                mouse=WindowsMouseDriver(),
                keyboard=WindowsKeyboardDriver(),
                screen=WindowsScreenDriver(),
            )
        except ImportError:
            logger.warning("PyAutoGUI not installed. Falling back to Stub drivers.")
            return get_driver_set(force_stub=True)

    # Linux 등 — Stub 반환
    logger.warning(f"No native driver for platform '{sys.platform}'. Using Stub drivers.")
    return get_driver_set(force_stub=True)

