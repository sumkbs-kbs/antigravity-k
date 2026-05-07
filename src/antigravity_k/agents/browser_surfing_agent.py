#!/usr/bin/env python3
"""
Antigravity-K: Browser Surfing Agent
======================================
Vision-Language 기반 자율 웹 브라우징 에이전트.
Playwright를 제어하며 화면 스크린샷과 DOM 트리를 바탕으로
LLM(qwen3.5-omni)이 상호작용(클릭, 스크롤, 추출)을 판단합니다.
"""

import asyncio
import json
import logging
from typing import Optional
from dataclasses import dataclass

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    async_playwright = None

logger = logging.getLogger("browser_agent")


@dataclass
class BrowserAction:
    action: str  # "click", "scroll_down", "extract", "done"
    target_selector: str = ""
    reason: str = ""
    extracted_data: str = ""


class BrowserSurfingAgent:
    """
    Playwright + Vision LLM 연동 자율 웹 서퍼
    """

    def __init__(self, model_manager=None, vision_model_name: str = "qwen3.5-omni"):
        self.model_manager = model_manager
        self.vision_model_name = vision_model_name
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def _init_browser(self):
        if not async_playwright:
            raise ImportError(
                "playwright is not installed. Run `pip install playwright`"
            )

        if not self._playwright:
            self._playwright = await async_playwright().start()

        if not self._browser:
            self._browser = await self._playwright.chromium.launch(headless=True)

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def surf(self, url: str, goal: str, max_steps: int = 5) -> str:
        """
        주어진 URL로 이동하여 목표(goal)를 달성하기 위해 브라우저를 탐색합니다.

        Args:
            url: 시작 URL
            goal: 에이전트가 찾아야 하는 정보나 달성해야 하는 목표
            max_steps: 최대 행동 횟수

        Returns:
            추출된 텍스트 결과
        """
        await self._init_browser()
        final_result = ""

        try:
            page = await self._browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=15000)

            step = 0
            while step < max_steps:
                step += 1
                logger.info(f"[BrowserSurfing] Step {step}: Analyzing page state...")

                # 1. 페이지 상태 분석 (스크린샷 및 DOM 요약)
                screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
                dom_summary = await self._extract_interactive_elements(page)

                # 2. Vision 모델에 상태 전달 후 다음 행동 결정
                action = await self._decide_next_action(
                    goal, dom_summary, screenshot_bytes
                )
                logger.info(
                    f"[BrowserSurfing] Action decided: {action.action} (Reason: {action.reason})"
                )

                # 3. 행동 실행
                if action.action == "click" and action.target_selector:
                    try:
                        await page.click(action.target_selector, timeout=5000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception as e:
                        logger.warning(f"Click failed on {action.target_selector}: {e}")

                elif action.action == "scroll_down":
                    await page.mouse.wheel(0, 800)
                    await asyncio.sleep(1)

                elif action.action == "extract":
                    final_result = action.extracted_data
                    break

                elif action.action == "done":
                    break

                else:
                    logger.warning(f"Unknown action: {action.action}")

            # 명시적 추출이 없었을 경우 대비 폴백
            if not final_result:
                final_result = await page.evaluate("document.body.innerText")

        except Exception as e:
            logger.error(f"Browser surfing error on {url}: {e}")
            final_result = f"Error during surfing: {e}"
        finally:
            if page:
                await page.close()
            await self._close_browser()

        return final_result

    async def _extract_interactive_elements(self, page: Page) -> str:
        """클릭 가능한 요소들의 CSS 셀렉터와 텍스트를 추출 (DOM 요약)"""
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
            return await page.evaluate(js_code)
        except Exception:
            return "Failed to extract elements"

    async def _decide_next_action(
        self, goal: str, dom_summary: str, screenshot_bytes: bytes
    ) -> BrowserAction:
        """
        Vision 모델을 호출하여 다음 브라우저 액션을 결정합니다.
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
            # 실제 구현에서는 모델 매니저에 스크린샷 이미지도 전달해야 함
            response = await self.model_manager.generate(
                prompt=prompt,
                model=self.vision_model_name,
                system_prompt="You are a JSON-only visual browsing agent.",
            )

            # JSON 파싱 (간단화)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()

            data = json.loads(text)
            return BrowserAction(
                action=data.get("action", "done"),
                target_selector=data.get("target_selector", ""),
                reason=data.get("reason", ""),
                extracted_data=data.get("extracted_data", ""),
            )
        except Exception as e:
            logger.warning(f"Vision model decision failed: {e}")
            return BrowserAction(action="done", reason=f"Model error: {e}")
