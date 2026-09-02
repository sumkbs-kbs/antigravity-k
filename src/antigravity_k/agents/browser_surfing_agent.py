"""Antigravity-K: Browser Surfing Agent.

======================================
Vision-Language 기반 자율 웹 브라우징 에이전트.
Playwright를 제어하며 화면 스크린샷과 DOM 트리를 바탕으로
LLM(qwen3.6:latest)이 상호작용(클릭, 스크롤, 추출)을 판단합니다.
"""

import asyncio
import base64
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast, final


class _MouseLike(Protocol):
    async def wheel(self, delta_x: float, delta_y: float) -> object: ...


class _PageLike(Protocol):
    mouse: _MouseLike

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> object: ...

    async def screenshot(self, *, type: str, quality: int) -> object: ...

    async def click(self, selector: str, *, timeout: int) -> object: ...

    async def wait_for_load_state(self, state: str, *, timeout: int) -> object: ...

    async def evaluate(self, expression: str) -> object: ...

    async def close(self) -> object: ...


class _BrowserLike(Protocol):
    async def new_page(self) -> _PageLike: ...

    async def close(self) -> object: ...


class _ChromiumLike(Protocol):
    async def launch(self, *, headless: bool) -> _BrowserLike: ...


class _PlaywrightLike(Protocol):
    chromium: _ChromiumLike

    async def stop(self) -> object: ...


class _PlaywrightController(Protocol):
    async def start(self) -> _PlaywrightLike: ...


class _ModelManagerLike(Protocol):
    def get_target_for_role(self, role: str, *, default_role: str) -> str: ...

    def generate(self, **kwargs: object) -> object: ...


async_playwright: Callable[[], _PlaywrightController] | None
try:
    from playwright.async_api import async_playwright as _async_playwright
except ImportError:
    async_playwright = None
else:
    async_playwright = cast(Callable[[], _PlaywrightController], _async_playwright)

logger = logging.getLogger("browser_agent")


def _as_text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_action_data(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


async def _resolve_response(value: object) -> object:
    if inspect.isawaitable(value):
        return await cast(Awaitable[object], value)
    return value


def _response_text(value: object) -> str:
    if isinstance(value, str):
        return value
    text_value = getattr(value, "text", None)
    return text_value if isinstance(text_value, str) else str(value)


@dataclass
class BrowserAction:
    """Represents a single browser navigation or interaction action."""

    action: str  # "click", "scroll_down", "extract", "done"
    target_selector: str = ""
    reason: str = ""
    extracted_data: str = ""


@final
class BrowserSurfingAgent:
    """Playwright + Vision LLM 연동 자율 웹 서퍼."""

    def __init__(
        self,
        model_manager: _ModelManagerLike | None = None,
        vision_model_name: str = "qwen3.6:latest",
    ):
        """Initialize the BrowserSurfingAgent.

        Args:
            model_manager: model manager.
            vision_model_name (str): str vision model name.

        """
        self.model_manager: _ModelManagerLike | None = model_manager
        self.vision_model_name: str = vision_model_name
        self._browser: _BrowserLike | None = None
        self._playwright: _PlaywrightLike | None = None

    async def _init_browser(self) -> None:
        if async_playwright is None:
            raise ImportError("playwright is not installed. Run `pip install playwright`")

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None:
            assert self._playwright is not None
            self._browser = await self._playwright.chromium.launch(headless=True)

    async def _close_browser(self) -> None:
        if self._browser:
            _ = await self._browser.close()
            self._browser = None
        if self._playwright:
            _ = await self._playwright.stop()
            self._playwright = None

    async def surf(self, url: str, goal: str, max_steps: int = 5) -> str:
        """주어진 URL로 이동하여 목표(goal)를 달성하기 위해 브라우저를 탐색합니다.

        Args:
            url: 시작 URL
            goal: 에이전트가 찾아야 하는 정보나 달성해야 하는 목표
            max_steps: 최대 행동 횟수

        Returns:
            추출된 텍스트 결과

        """
        await self._init_browser()
        final_result = ""

        page = None
        try:
            if self._browser is None:
                return "Error: Browser not initialized"
            page = await self._browser.new_page()
            assert page is not None
            _ = await page.goto(url, wait_until="networkidle", timeout=15000)

            step = 0
            while step < max_steps:
                step += 1
                logger.info("[BrowserSurfing] Step %s: Analyzing page state...", step)

                # 1. 페이지 상태 분석 (스크린샷 및 DOM 요약)
                screenshot_value = await page.screenshot(type="jpeg", quality=60)
                screenshot_bytes = screenshot_value if isinstance(screenshot_value, bytes) else b""
                dom_summary = await self._extract_interactive_elements(page)

                # 2. Vision 모델에 상태 전달 후 다음 행동 결정
                action = await self._decide_next_action(goal, dom_summary, screenshot_bytes)
                logger.info(
                    "[BrowserSurfing] Action decided: %s (Reason: %s)",
                    action.action,
                    action.reason,
                )

                # 3. 행동 실행
                if action.action == "click" and action.target_selector:
                    try:
                        _ = await page.click(action.target_selector, timeout=5000)
                        _ = await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        logger.exception("Click failed on %s", action.target_selector)

                elif action.action == "scroll_down":
                    _ = await page.mouse.wheel(0, 800)
                    await asyncio.sleep(1)

                elif action.action == "extract":
                    final_result = action.extracted_data
                    break

                elif action.action == "done":
                    break

                else:
                    logger.warning("Unknown action: %s", action.action)

            # 명시적 추출이 없었을 경우 대비 폴백
            if not final_result:
                evaluated = await page.evaluate("document.body.innerText")
                final_result = evaluated if isinstance(evaluated, str) else str(evaluated)

        except Exception as e:
            logger.exception("Browser surfing error on %s", url)
            final_result = f"Error during surfing: {e}"
        finally:
            if page is not None:
                _ = await page.close()
            await self._close_browser()

        return final_result

    async def _extract_interactive_elements(self, page: _PageLike) -> str:
        """클릭 가능한 요소들의 CSS 셀렉터와 텍스트를 추출 (DOM 요약)."""
        js_code = """
        () => {

            const elements = document.querySelectorAll('a, button, [role="button"]');
            const result = [];
            for (let i=0; i<Math.min(elements.length, 50); i++) {
                const el = elements[i];
                if (el.innerText && el.innerText.trim() !== '') {
                    // 간단한 셀렉터 생성
                    let selector = el.tagName.toLowerCase();
                    if (el.id) selector += '#' + el.id;
                    if (el.className && typeof el.className === 'string') {
                        selector += '.' + el.className.split(' ').join('.');
                    }
                    result.push(`[${i}] ${selector} : ${el.innerText.trim()}`);
                }
            }
            return result.join('\\n');
        }
        """
        try:
            result = await page.evaluate(js_code)
            return result if isinstance(result, str) else str(result)
        except Exception:
            logger.exception("Unhandled exception")
            return "Failed to extract elements"

    async def _decide_next_action(
        self,
        goal: str,
        dom_summary: str,
        screenshot_bytes: bytes,
    ) -> BrowserAction:
        """Vision 모델을 호출하여 다음 브라우저 액션을 결정합니다.

        실제 환경에서는 self.model_manager.generate()에 이미지를 첨부합니다.
        """
        if not self.model_manager:
            # Mock behavior if model manager is not injected
            return BrowserAction(action="extract", extracted_data="[Mock Data] " + goal)

        prompt = f"""
        당신은 자율 웹 서핑 에이전트입니다.

        현재 목표: {goal}

        아래는 현재 화면의 상호작용 가능한 요소 목록입니다:
        {dom_summary}

        다음 중 하나의 액션을 JSON 형식으로 선택하세요:
        1. {{"action": "click", "target_selector": "<selector>", "reason": "..."}}
        2. {{"action": "scroll_down", "reason": "..."}}
        3. {{"action": "extract", "extracted_data": "<최종 텍스트 요약>", "reason": "..."}}
        4. {{"action": "done", "reason": "더 이상 진행할 수 없거나 목표 달성"}}

        JSON 포맷으로만 응답하세요.
        """

        try:
            target = self.vision_model_name
            if target == "qwen3.6:latest":
                target = self.model_manager.get_target_for_role("vision", default_role="vision")
            raw_response = await asyncio.to_thread(
                self.model_manager.generate,
                prompt=prompt,
                target=target,
                system_prompt="You are a JSON-only visual browsing agent.",
                raw_messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [base64.b64encode(screenshot_bytes).decode("ascii")],
                    },
                ],
                max_tokens=512,
                temperature=0.2,
            )
            response = await _resolve_response(raw_response)

            # JSON 파싱 (간단화)
            text = _response_text(response)
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()

            decoded = cast(object, json.loads(text))
            data = _as_action_data(decoded)
            return BrowserAction(
                action=_as_text(data.get("action"), "done"),
                target_selector=_as_text(data.get("target_selector")),
                reason=_as_text(data.get("reason")),
                extracted_data=_as_text(data.get("extracted_data")),
            )
        except Exception as e:
            logger.exception("Vision model decision failed")
            return BrowserAction(action="done", reason=f"Model error: {e}")
