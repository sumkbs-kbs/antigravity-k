import json
import logging
import base64
from typing import Dict, Any

logger = logging.getLogger("antigravity_k.tools.browser")

class BrowserTool:
    """
    Playwright 기반 브라우저 자동화 도구.
    에이전트가 브라우저를 열고, 클릭하고, 텍스트를 입력하고, 스크린샷을 찍을 수 있도록 합니다.
    """
    name = "browser_tool"
    description = "브라우저를 조작하여 웹 페이지를 테스트하고 스크린샷을 찍습니다."
    
    def __init__(self):
        self.page = None
        self.browser = None
        self.playwright = None
        self.is_running = False

    def execute(self, params: Dict[str, Any]) -> str:
        action = params.get("action")
        
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "오류: playwright가 설치되어 있지 않습니다. 'pip install playwright' 및 'playwright install'을 실행하세요."

        if not self.is_running:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()
            self.is_running = True

        try:
            if action == "goto":
                url = params.get("url")
                self.page.goto(url)
                return f"Moved to {url}. Title: {self.page.title()}"
            
            elif action == "click":
                selector = params.get("selector")
                self.page.click(selector)
                return f"Clicked on {selector}"
                
            elif action == "type":
                selector = params.get("selector")
                text = params.get("text")
                self.page.fill(selector, text)
                return f"Typed '{text}' into {selector}"
                
            elif action == "screenshot":
                path = params.get("path", "screenshot.png")
                self.page.screenshot(path=path)
                return f"Screenshot saved to {path}"
                
            elif action == "close":
                self.browser.close()
                self.playwright.stop()
                self.is_running = False
                return "Browser closed."
                
            else:
                return f"Unknown action: {action}"
                
        except Exception as e:
            logger.error(f"Browser action '{action}' failed: {e}")
            return f"Error: {str(e)}"
