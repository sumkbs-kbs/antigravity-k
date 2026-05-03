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


# ─────────────────── 팩토리 함수 ───────────────────

def get_driver_set(force_stub: bool = False) -> DriverSet:
    """
    현재 OS에 맞는 드라이버 셋을 반환합니다.
    - force_stub=True: 테스트 환경용 Stub 드라이버 반환
    - Windows: PyAutoGUI 기반 드라이버
    - 그 외: Stub 드라이버 (향후 확장)
    """
    if force_stub:
        logger.info("Using STUB drivers (no real desktop interaction)")
        return DriverSet(
            mouse=StubMouseDriver(),
            keyboard=StubKeyboardDriver(),
            screen=StubScreenDriver(),
        )

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

    # macOS / Linux — 향후 구현 예정, 현재 Stub 반환
    logger.warning(f"No native driver for platform '{sys.platform}'. Using Stub drivers.")
    return get_driver_set(force_stub=True)
