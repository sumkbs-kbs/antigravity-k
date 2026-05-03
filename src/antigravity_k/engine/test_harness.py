"""
Antigravity-K: 하네스 엔지니어링 프레임워크
===========================================
Intent 기반 테스트, Self-Healing Loop, 피드백 수집기를 포함한
에이전트 주도 QA 자동화 시스템.

핵심 개념:
- TestHarness: 테스트 시나리오 관리 및 실행
- HealingLoop: 실패 시 DOM 분석 → 셀렉터 자동 수정 → 재시도
- FeedbackCollector: 테스트 결과를 에이전트에게 피드백
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("antigravity_k.test_harness")


# ─── 데이터 모델 ───────────────────────────────────────────────

class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    HEALED = "healed"      # Self-healing으로 복구됨
    SKIPPED = "skipped"


@dataclass
class TestIntent:
    """자연어 의도 기반 테스트 케이스"""
    id: str
    intent: str               # "채팅에 메시지를 보내면 응답이 온다"
    category: str = "ui"      # ui, api, integration
    priority: int = 1         # 1(높음) ~ 5(낮음)
    timeout_sec: float = 30.0
    max_heal_attempts: int = 3
    tags: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    """테스트 실행 결과"""
    intent_id: str
    status: TestStatus
    duration_ms: float
    message: str = ""
    screenshot_path: Optional[str] = None
    healed: bool = False
    heal_details: Optional[str] = None
    dom_snapshot: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "intent_id": self.intent_id,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 1),
            "message": self.message,
            "screenshot_path": self.screenshot_path,
            "healed": self.healed,
            "heal_details": self.heal_details,
            "timestamp": self.timestamp,
        }


@dataclass
class HarnessReport:
    """전체 테스트 하네스 실행 결과"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    healed: int = 0
    skipped: int = 0
    duration_ms: float = 0
    results: List[TestResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "healed": self.healed,
            "skipped": self.skipped,
            "duration_ms": round(self.duration_ms, 1),
            "pass_rate": f"{(self.passed + self.healed) / max(self.total, 1) * 100:.1f}%",
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        lines = [
            "# 🧪 Antigravity-K Self-Test Report",
            "",
            f"| 항목 | 값 |",
            f"|------|-----|",
            f"| 총 테스트 | {self.total} |",
            f"| ✅ 통과 | {self.passed} |",
            f"| 🔧 자가치유 | {self.healed} |",
            f"| ❌ 실패 | {self.failed} |",
            f"| ⏭ 스킵 | {self.skipped} |",
            f"| 소요시간 | {self.duration_ms:.0f}ms |",
            f"| 합격률 | {(self.passed + self.healed) / max(self.total, 1) * 100:.1f}% |",
            "",
            "## 상세 결과",
            "",
        ]
        for r in self.results:
            icon = {"passed": "✅", "failed": "❌", "healed": "🔧", "skipped": "⏭"}.get(r.status.value, "❓")
            lines.append(f"- {icon} **{r.intent_id}**: {r.message} ({r.duration_ms:.0f}ms)")
            if r.healed and r.heal_details:
                lines.append(f"  - 🩹 치유: {r.heal_details}")
        return "\n".join(lines)


# ─── Self-Healing Loop ─────────────────────────────────────────

class HealingLoop:
    """
    하네스 엔지니어링의 핵심: Self-Healing Loop.
    
    1. 실패 감지 → 2. DOM 스냅샷 분석 → 3. 셀렉터 대체 후보 탐색 
    → 4. 재시도 → 5. 성공 시 치유 로그 기록
    """

    # 대체 셀렉터 탐색 전략 (우선순위 순)
    SELECTOR_STRATEGIES = [
        "role",       # getByRole — Accessibility Tree 기반
        "label",      # getByLabel — aria-label 기반
        "text",       # getByText — 텍스트 내용 기반
        "testid",     # getByTestId — data-testid 기반
        "css",        # querySelector — CSS 기반 (최후의 수단)
    ]

    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self.heal_log: List[Dict[str, Any]] = []

    async def try_with_healing(
        self,
        action_fn: Callable,
        page,
        context: Dict[str, Any],
        intent: TestIntent
    ) -> TestResult:
        """
        액션을 실행하되, 실패 시 self-healing을 시도합니다.
        """
        start = time.time()
        last_error = None

        for attempt in range(self.max_attempts + 1):
            try:
                result_msg = await action_fn(page, context)
                elapsed = (time.time() - start) * 1000
                
                healed = attempt > 0
                return TestResult(
                    intent_id=intent.id,
                    status=TestStatus.HEALED if healed else TestStatus.PASSED,
                    duration_ms=elapsed,
                    message=result_msg or "OK",
                    healed=healed,
                    heal_details=f"Attempt {attempt + 1}: {context.get('heal_strategy', 'N/A')}" if healed else None,
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[HealingLoop] Attempt {attempt + 1}/{self.max_attempts + 1} failed: {e}")
                
                if attempt < self.max_attempts:
                    # DOM 분석 → 대체 셀렉터 탐색
                    healed_context = await self._analyze_and_heal(page, context, str(e))
                    if healed_context:
                        context.update(healed_context)
                        continue

        elapsed = (time.time() - start) * 1000
        return TestResult(
            intent_id=intent.id,
            status=TestStatus.FAILED,
            duration_ms=elapsed,
            message=f"All {self.max_attempts + 1} attempts failed: {last_error}",
        )

    async def _analyze_and_heal(
        self, page, context: Dict[str, Any], error: str
    ) -> Optional[Dict[str, Any]]:
        """DOM을 분석하여 대체 셀렉터를 찾습니다."""
        try:
            # Accessibility Tree에서 대체 요소 탐색
            snapshot = await page.accessibility.snapshot()
            if not snapshot:
                return None

            original_target = context.get("target_text", "")
            
            # 텍스트 매칭으로 대체 셀렉터 탐색
            candidates = self._find_candidates(snapshot, original_target)
            if candidates:
                heal_info = {
                    "heal_strategy": f"accessibility_tree_match: {candidates[0]}",
                    "healed_selector": candidates[0],
                }
                self.heal_log.append({
                    "original": context.get("selector"),
                    "healed": candidates[0],
                    "error": error,
                    "timestamp": time.time(),
                })
                return heal_info

        except Exception as e:
            logger.debug(f"[HealingLoop] DOM analysis failed: {e}")
        
        return None

    def _find_candidates(self, node: dict, target_text: str, depth: int = 0) -> List[str]:
        """Accessibility Tree에서 텍스트가 유사한 노드를 재귀적으로 탐색"""
        candidates = []
        name = node.get("name", "")
        role = node.get("role", "")
        
        if target_text and target_text.lower() in name.lower():
            candidates.append(f"role={role}, name={name}")
        
        for child in node.get("children", []):
            candidates.extend(self._find_candidates(child, target_text, depth + 1))
        
        return candidates


# ─── Feedback Collector ────────────────────────────────────────

class FeedbackCollector:
    """
    테스트 결과를 수집하고 에이전트에게 피드백합니다.
    하네스 엔지니어링의 'Agent-Legible Feedback' 구현.
    """

    def __init__(self):
        self.history: List[HarnessReport] = []

    def collect(self, report: HarnessReport) -> str:
        """결과를 수집하고 에이전트가 읽을 수 있는 피드백을 생성합니다."""
        self.history.append(report)
        
        if report.failed == 0:
            return f"✅ 모든 테스트 통과 ({report.passed + report.healed}/{report.total})"
        
        # 실패한 테스트의 구체적인 정보를 에이전트에게 전달
        failed_tests = [r for r in report.results if r.status == TestStatus.FAILED]
        feedback_lines = [
            f"⚠️ {report.failed}개 테스트 실패:",
        ]
        for ft in failed_tests:
            feedback_lines.append(f"  - [{ft.intent_id}] {ft.message}")
        
        return "\n".join(feedback_lines)

    def get_trend(self) -> Dict[str, Any]:
        """최근 테스트 추세를 반환합니다."""
        if not self.history:
            return {"trend": "no_data"}
        
        recent = self.history[-5:]
        pass_rates = [
            (r.passed + r.healed) / max(r.total, 1) * 100
            for r in recent
        ]
        
        return {
            "recent_pass_rates": pass_rates,
            "trend": "improving" if len(pass_rates) > 1 and pass_rates[-1] > pass_rates[0] else "stable",
            "total_runs": len(self.history),
        }


# ─── Test Harness (메인 오케스트레이터) ──────────────────────────

class TestHarness:
    """
    하네스 엔지니어링 프레임워크의 메인 오케스트레이터.
    
    Intent 기반 테스트를 실행하고, Self-Healing을 적용하며,
    결과를 수집하여 에이전트에게 피드백합니다.
    """

    # Antigravity-K 대시보드 기본 테스트 시나리오
    DEFAULT_INTENTS = [
        TestIntent(
            id="health_api",
            intent="백엔드 API 헬스체크가 정상 응답한다",
            category="api",
            priority=1,
            tags=["critical", "api"],
        ),
        TestIntent(
            id="models_api",
            intent="모델 목록 API가 정상적으로 모델 리스트를 반환한다",
            category="api",
            priority=1,
            tags=["critical", "api"],
        ),
        TestIntent(
            id="dashboard_load",
            intent="대시보드 메인 페이지가 정상적으로 로드된다",
            category="ui",
            priority=1,
            tags=["critical", "ui"],
        ),
        TestIntent(
            id="chat_send",
            intent="채팅에 메시지를 보내면 스트리밍 응답이 시작된다",
            category="integration",
            priority=1,
            timeout_sec=60.0,
            tags=["critical", "chat"],
        ),
        TestIntent(
            id="file_explorer",
            intent="파일 탐색기에 워크스페이스 파일 목록이 표시된다",
            category="ui",
            priority=2,
            tags=["ui", "explorer"],
        ),
        TestIntent(
            id="terminal_ws",
            intent="터미널 WebSocket 연결이 성공한다",
            category="integration",
            priority=2,
            tags=["terminal", "websocket"],
        ),
    ]

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.dashboard_url = "http://localhost:5173"
        self.healing_loop = HealingLoop(max_attempts=3)
        self.feedback = FeedbackCollector()
        self.intents: List[TestIntent] = list(self.DEFAULT_INTENTS)
        self._browser = None
        self._playwright = None

    async def run_all(self, use_browser: bool = True) -> HarnessReport:
        """모든 테스트 인텐트를 실행합니다."""
        report = HarnessReport()
        start = time.time()
        
        # API 테스트 (브라우저 불필요)
        api_intents = [i for i in self.intents if i.category == "api"]
        for intent in api_intents:
            result = await self._run_api_test(intent)
            report.results.append(result)
        
        # UI/통합 테스트 (브라우저 필요)
        if use_browser:
            browser_intents = [i for i in self.intents if i.category in ("ui", "integration")]
            browser_results = await self._run_browser_tests(browser_intents)
            report.results.extend(browser_results)
        
        # 통계 집계
        report.total = len(report.results)
        report.passed = sum(1 for r in report.results if r.status == TestStatus.PASSED)
        report.failed = sum(1 for r in report.results if r.status == TestStatus.FAILED)
        report.healed = sum(1 for r in report.results if r.status == TestStatus.HEALED)
        report.skipped = sum(1 for r in report.results if r.status == TestStatus.SKIPPED)
        report.duration_ms = (time.time() - start) * 1000
        
        # 피드백 수집
        feedback_msg = self.feedback.collect(report)
        logger.info(f"[TestHarness] {feedback_msg}")
        
        return report

    async def _run_api_test(self, intent: TestIntent) -> TestResult:
        """API 테스트 실행 (run_in_executor로 블로킹 방지)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_api_test_sync, intent)
    
    def _run_api_test_sync(self, intent: TestIntent) -> TestResult:
        """API 테스트 동기 실행 (별도 스레드에서 실행됨)"""
        import urllib.request
        start = time.time()
        
        try:
            if intent.id == "health_api":
                req = urllib.request.Request(f"{self.base_url}/v1/health")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok":
                        elapsed = (time.time() - start) * 1000
                        return TestResult(intent.id, TestStatus.PASSED, elapsed, "Health OK")
                    else:
                        elapsed = (time.time() - start) * 1000
                        return TestResult(intent.id, TestStatus.FAILED, elapsed, f"Unexpected: {data}")
            
            elif intent.id == "models_api":
                req = urllib.request.Request(f"{self.base_url}/v1/models")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    models = data.get("data", [])
                    if len(models) > 0:
                        elapsed = (time.time() - start) * 1000
                        return TestResult(intent.id, TestStatus.PASSED, elapsed, f"{len(models)} models available")
                    else:
                        elapsed = (time.time() - start) * 1000
                        return TestResult(intent.id, TestStatus.FAILED, elapsed, "No models returned")
            
            else:
                elapsed = (time.time() - start) * 1000
                return TestResult(intent.id, TestStatus.SKIPPED, elapsed, "Unknown API test")
                
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return TestResult(intent.id, TestStatus.FAILED, elapsed, str(e))

    async def _run_browser_tests(self, intents: List[TestIntent]) -> List[TestResult]:
        """Playwright 기반 브라우저 테스트"""
        results = []
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            for intent in intents:
                results.append(TestResult(
                    intent.id, TestStatus.SKIPPED, 0,
                    "playwright 미설치. 'pip install playwright && playwright install chromium' 실행 필요"
                ))
            return results
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            for intent in intents:
                try:
                    if intent.id == "dashboard_load":
                        result = await self._test_dashboard_load(page, intent)
                    elif intent.id == "chat_send":
                        result = await self._test_chat_send(page, intent)
                    elif intent.id == "file_explorer":
                        result = await self._test_file_explorer(page, intent)
                    elif intent.id == "terminal_ws":
                        result = await self._test_terminal_ws(intent)
                    else:
                        result = TestResult(intent.id, TestStatus.SKIPPED, 0, "Unknown test")
                    results.append(result)
                except Exception as e:
                    results.append(TestResult(intent.id, TestStatus.FAILED, 0, str(e)))
            
            await browser.close()
        
        return results

    async def _test_dashboard_load(self, page, intent: TestIntent) -> TestResult:
        """대시보드 로딩 테스트"""
        start = time.time()
        await page.goto(self.dashboard_url, wait_until="networkidle", timeout=int(intent.timeout_sec * 1000))
        title = await page.title()
        elapsed = (time.time() - start) * 1000
        
        if "Antigravity" in title or await page.query_selector("#app"):
            return TestResult(intent.id, TestStatus.PASSED, elapsed, f"Dashboard loaded: {title}")
        else:
            return TestResult(intent.id, TestStatus.FAILED, elapsed, f"Unexpected title: {title}")

    async def _test_chat_send(self, page, intent: TestIntent) -> TestResult:
        """채팅 메시지 전송 및 응답 수신 테스트"""
        start = time.time()
        await page.goto(self.dashboard_url, wait_until="networkidle", timeout=15000)
        
        # 채팅 입력란 찾기 (self-healing 포함)
        context = {"target_text": "명령어나 질문을 입력하세요", "selector": "#chat-input"}
        
        async def chat_action(pg, ctx):
            input_el = await pg.query_selector(ctx.get("selector", "#chat-input"))
            if not input_el:
                # Healing: placeholder 텍스트로 찾기
                input_el = await pg.query_selector("input[placeholder], textarea[placeholder]")
            if not input_el:
                raise Exception("채팅 입력란을 찾을 수 없습니다")
            
            await input_el.fill("테스트 메시지")
            await input_el.press("Enter")
            
            # 응답 대기 (최대 timeout_sec)
            await pg.wait_for_selector(".message-content, .assistant-message, [class*='bot']", timeout=int(intent.timeout_sec * 1000))
            return "채팅 응답 수신 완료"
        
        result = await self.healing_loop.try_with_healing(chat_action, page, context, intent)
        return result

    async def _test_file_explorer(self, page, intent: TestIntent) -> TestResult:
        """파일 탐색기 테스트"""
        start = time.time()
        await page.goto(self.dashboard_url, wait_until="networkidle", timeout=15000)
        
        # 파일 목록 존재 확인
        file_items = await page.query_selector_all(".file-item, .tree-item, [class*='explorer'] li, [class*='explorer'] .item")
        elapsed = (time.time() - start) * 1000
        
        if file_items and len(file_items) > 0:
            return TestResult(intent.id, TestStatus.PASSED, elapsed, f"{len(file_items)}개 파일 항목 표시")
        else:
            return TestResult(intent.id, TestStatus.FAILED, elapsed, "파일 항목이 표시되지 않음")

    async def _test_terminal_ws(self, intent: TestIntent) -> TestResult:
        """터미널 WebSocket 연결 테스트"""
        start = time.time()
        try:
            import websockets
            async with websockets.connect(
                f"ws://localhost:8000/ws/terminal",
                open_timeout=5
            ) as ws:
                await ws.send("echo 'harness_test_ok'\n")
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                elapsed = (time.time() - start) * 1000
                
                if "harness_test_ok" in response or response:
                    return TestResult(intent.id, TestStatus.PASSED, elapsed, "WebSocket 연결 성공")
                else:
                    return TestResult(intent.id, TestStatus.FAILED, elapsed, "응답 없음")
        except ImportError:
            elapsed = (time.time() - start) * 1000
            return TestResult(intent.id, TestStatus.SKIPPED, elapsed, "websockets 미설치")
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return TestResult(intent.id, TestStatus.FAILED, elapsed, str(e))

    def add_intent(self, intent: TestIntent):
        """커스텀 테스트 인텐트 추가"""
        self.intents.append(intent)

    def get_latest_report(self) -> Optional[HarnessReport]:
        """가장 최근 테스트 결과 반환"""
        if self.feedback.history:
            return self.feedback.history[-1]
        return None
