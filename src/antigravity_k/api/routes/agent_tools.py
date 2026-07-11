"""Agent Tools module."""

import base64
import logging
import os
import subprocess
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from playwright.async_api import Browser, BrowserContext, Error, Page, async_playwright
from pydantic import BaseModel

from antigravity_k.config import config
from antigravity_k.tools.permission_gate import Permission, PermissionGate

logger = logging.getLogger(__name__)
router = APIRouter()


class BrowserState:
    """Tracks browser session state (active page, URL, cookies)."""

    playwright: Any = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    console_errors: list = []
    console_logs: list = []


browser_state = BrowserState()


def _permission_gate() -> PermissionGate:
    return PermissionGate(project_root=str(config.paths.project_root), mode="auto-pilot")


def _require_allowed(tool_name: str, args: dict, risk_level: str):
    decision = _permission_gate().check(tool_name, args, risk_level=risk_level)
    if decision != Permission.ALLOW:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied for {tool_name}: {decision.value}",
        )


class FileReadRequest(BaseModel):
    """Filereadrequest.

    Bases: BaseModel
    """

    path: str


class FileWriteRequest(BaseModel):
    """Filewriterequest.

    Bases: BaseModel
    """

    path: str
    content: str
    overwrite: bool = False


class ShellRunRequest(BaseModel):
    """Shellrunrequest.

    Bases: BaseModel
    """

    command: str
    cwd: str | None = None
    timeout: int = 30


@router.post("/api/agent/tools/fs/read")
def read_file(req: FileReadRequest):
    """지정된 파일의 내용을 읽어옵니다."""
    _require_allowed("read_file", {"path": req.path}, "safe")
    if not os.path.exists(req.path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        with open(req.path, encoding="utf-8") as f:
            return {"ok": True, "content": f.read()}
    except (OSError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/agent/tools/fs/write")
def write_file(req: FileWriteRequest):
    """파일을 생성하거나 덮어씁니다."""
    _require_allowed("write_file", {"path": req.path}, "medium")
    if os.path.exists(req.path) and not req.overwrite:
        raise HTTPException(status_code=400, detail="File exists, use overwrite=True")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(req.path)), exist_ok=True)
        with open(req.path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"ok": True, "path": req.path}
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/agent/tools/shell/run")
def run_shell(req: ShellRunRequest):
    """터미널 명령을 샌드박스에서 실행합니다."""
    _require_allowed("run_bash_command", {"command": req.command}, "high")
    if req.cwd:
        _require_allowed("write_file", {"path": req.cwd}, "medium")
    try:
        result = subprocess.run(
            req.command,
            shell=True,
            cwd=req.cwd,
            capture_output=True,
            text=True,
            timeout=req.timeout,
        )
        return {
            "ok": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command execution timed out")
    except HTTPException:
        raise
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))


class BrowserActionRequest(BaseModel):
    """Browseractionrequest.

    Bases: BaseModel
    """

    action: str  # "launch", "goto", "click", "type", "snapshot", "close"
    url: str | None = None
    selector: str | None = None
    text: str | None = None


@router.post("/api/agent/tools/browser/action")
async def browser_action(req: BrowserActionRequest):
    """Playwright 기반 브라우저 자동화 엔진 API."""
    try:
        if req.action == "launch":
            if not browser_state.playwright:
                browser_state.playwright = await async_playwright().start()
            assert browser_state.playwright is not None
            if not browser_state.browser:
                browser_state.browser = await browser_state.playwright.chromium.launch(
                    headless=True,
                )
                browser_state.context = await browser_state.browser.new_context(
                    viewport={"width": 1280, "height": 800},
                )
                browser_state.page = await browser_state.context.new_page()
                # Console error/log auto-collection
                browser_state.console_errors = []
                browser_state.console_logs = []
                browser_state.page.on(
                    "console",
                    lambda msg: (
                        browser_state.console_errors.append({"type": msg.type, "text": msg.text})
                        if msg.type in ("error", "warning")
                        else browser_state.console_logs.append({"type": msg.type, "text": msg.text})
                    ),
                )
            return {"ok": True, "message": "Browser launched with console capture"}

        elif req.action == "close":
            if browser_state.browser:
                await browser_state.browser.close()
                browser_state.browser = None
                browser_state.context = None
                browser_state.page = None
            if browser_state.playwright:
                await browser_state.playwright.stop()
                browser_state.playwright = None
            return {"ok": True, "message": "Browser closed"}

        # For remaining actions, ensure page exists
        if not browser_state.page:
            raise HTTPException(
                status_code=400,
                detail="Browser is not launched. Call 'launch' first.",
            )

        if req.action == "goto":
            if not req.url:
                raise HTTPException(status_code=400, detail="URL is required for goto")
            await browser_state.page.goto(req.url, wait_until="networkidle")
            return {"ok": True, "url": req.url}

        elif req.action == "click":
            if not req.selector:
                raise HTTPException(status_code=400, detail="Selector is required for click")
            await browser_state.page.click(req.selector)
            return {"ok": True, "selector": req.selector}

        elif req.action == "type":
            if not req.selector or req.text is None:
                raise HTTPException(
                    status_code=400,
                    detail="Selector and text are required for type",
                )
            await browser_state.page.fill(req.selector, req.text)
            return {"ok": True, "selector": req.selector, "text": req.text}

        elif req.action == "snapshot":
            # Accessibility Tree + Screenshot + Console errors
            screenshot_bytes = await browser_state.page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            # Accessibility Tree (compact text representation for LLM)
            a11y_tree = None
            try:
                a11y_snapshot = await browser_state.page.accessibility.snapshot()  # type: ignore[attr-defined]
                a11y_tree = _flatten_a11y_tree(a11y_snapshot) if a11y_snapshot else None
            except Exception:
                logger.exception("Unhandled exception")
                pass

            return {
                "ok": True,
                "screenshot_base64": screenshot_b64,
                "accessibility_tree": a11y_tree,
                "console_errors": browser_state.console_errors[-20:],
                "console_logs_count": len(browser_state.console_logs),
                "url": browser_state.page.url,
            }

        elif req.action == "console_errors":
            return {
                "ok": True,
                "errors": browser_state.console_errors,
                "total": len(browser_state.console_errors),
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    except HTTPException:
        raise
    except (Error, OSError, TimeoutError) as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Accessibility Tree Flattener ─────────────────────────────
def _flatten_a11y_tree(node: dict, depth: int = 0) -> str:
    """Playwright의 Accessibility Tree를 LLM이 이해할 수 있는.

    컴팩트한 텍스트 표현으로 변환합니다.

    예시 출력:
      [button] "Send" focused
        [img] "send icon"
      [textbox] "채팅 입력" value="hello"
    """
    lines = []
    role = node.get("role", "unknown")
    name = node.get("name", "")
    value = node.get("value", "")
    focused = " focused" if node.get("focused") else ""
    checked = " checked" if node.get("checked") else ""
    disabled = " disabled" if node.get("disabled") else ""

    indent = "  " * depth
    label = f"[{role}]"
    if name:
        label += f' "{name}"'
    if value:
        label += f' value="{value[:50]}"'
    label += focused + checked + disabled

    lines.append(f"{indent}{label}")

    for child in node.get("children", []):
        lines.extend(_flatten_a11y_tree(child, depth + 1).split("\n"))

    return "\n".join(lines)


# ─── Self-Test Orchestration ──────────────────────────────────
class BrowserSelfTestRequest(BaseModel):
    """Browserselftestrequest.

    Bases: BaseModel
    """

    scope: str = "all"
    base_url: str | None = None
    dashboard_url: str | None = None
    ws_url: str | None = None


@router.post("/api/agent/tools/browser/self-test")
async def browser_self_test(
    request: Request,
    req: BrowserSelfTestRequest = Body(default_factory=BrowserSelfTestRequest),
):
    """기존 TestHarness 프레임워크를 활용하여.

    Antigravity-K가 스스로를 테스트하는 멀티스텝 오케스트레이션 루프.

    실행 흐름:
    1. TestHarness가 API 테스트 실행 (health, models)
    2. Playwright로 UI 테스트 실행 (dashboard, chat, explorer)
    3. Self-Healing Loop 적용 (실패 시 자동 재시도)
    4. 결과를 마크다운 리포트로 반환
    """
    try:
        from antigravity_k.engine.harness import TestHarness

        request_base_url = str(request.base_url).rstrip("/")
        base_url = req.base_url or request_base_url
        harness = TestHarness(
            base_url=base_url,
            dashboard_url=req.dashboard_url or base_url,
            ws_url=req.ws_url,
        )
        use_browser = req.scope not in ("api", "api_only")
        report = await harness.run_all(use_browser=use_browser)
        return {
            "ok": True,
            "report": report.to_dict(),
            "markdown": report.to_markdown(),
            "feedback": ("✅ 모든 테스트 통과" if report.failed == 0 else f"⚠️ {report.failed}개 테스트 실패"),
            "trend": harness.feedback.get_trend(),
        }
    except HTTPException:
        raise
    except (ImportError, RuntimeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Autonomous QA Full Loop ─────────────────────────────────
class AutonomousQARequest(BaseModel):
    """Autonomousqarequest.

    Bases: BaseModel
    """

    url: str = "http://localhost:5173"
    max_iterations: int = 3
    vision_model: str = "qwen2.5vl:32b"
    coding_model: str = "qwen2.5-coder:32b"


@router.post("/api/agent/tools/browser/autonomous-qa")
async def autonomous_qa_loop(req: AutonomousQARequest):
    """완전 자율 QA 루프: 비전 분석 → 코드 수정 → 자동 적용 → 재테스트 → 검증.

    이 엔드포인트가 호출되면:
    1. Playwright로 대시보드 스크린샷 촬영
    2. qwen2.5vl:32b가 UI 결함 분석
    3. qwen2.5-coder:32b가 코드 수정 패치 생성
    4. 패치 자동 적용 → 리로드 → 재분석
    5. 결함 해소 확인될 때까지 최대 N회 반복
    6. 반응형 테스트(desktop/tablet/mobile) + 성능 메트릭 수집
    """
    try:
        from antigravity_k.engine.autonomous_qa import AutonomousQAEngine

        engine = AutonomousQAEngine(
            dashboard_url=req.url,
            vision_model=req.vision_model,
            coding_model=req.coding_model,
            max_iterations=req.max_iterations,
        )
        report = await engine.run_full_loop(req.url)
        return {
            "ok": True,
            "report": report.to_dict(),
            "markdown": report.to_markdown(),
        }
    except HTTPException:
        raise
    except (ImportError, RuntimeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Vision Analysis (멀티모달 LLM 연동) ─────────────────────
class VisionAnalyzeRequest(BaseModel):
    """Visionanalyzerequest.

    Bases: BaseModel
    """

    screenshot_base64: str | None = None
    prompt: str = "이 UI 스크린샷을 분석하세요. 레이아웃 문제, 겹침, 잘림, 정렬 오류가 있으면 모두 지적하고 수정 방법을 제안하세요."  # noqa: E501
    model: str = "qwen2.5vl:32b"


@router.post("/api/agent/tools/browser/vision-analyze")
async def vision_analyze(req: VisionAnalyzeRequest):
    """멀티모달 비전 LLM을 활용한 UI 스크린샷 자동 분석.

    1. screenshot_base64가 없으면 현재 브라우저에서 자동 캡처
    2. 비전 모델(qwen2.5vl:32b)에 이미지+프롬프트 전달
    3. UI 결함 분석 결과 반환
    """
    import httpx

    try:
        # 스크린샷 자동 캡처 (없으면)
        screenshot_b64 = req.screenshot_base64
        if not screenshot_b64 and browser_state.page:
            screenshot_bytes = await browser_state.page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        if not screenshot_b64:
            raise HTTPException(
                status_code=400,
                detail="No screenshot available. Launch browser and navigate first, or provide screenshot_base64.",
            )

        # Ollama 멀티모달 API 호출
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": req.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": req.prompt,
                            "images": [screenshot_b64],
                        },
                    ],
                    "stream": False,
                },
            )

            if response.status_code == 200:
                data = response.json()
                analysis = data.get("message", {}).get("content", "분석 결과 없음")
                return {
                    "ok": True,
                    "model": req.model,
                    "analysis": analysis,
                }
            else:
                return {
                    "ok": False,
                    "error": f"Ollama returned {response.status_code}: {response.text}",
                }

    except HTTPException:
        raise
    except (httpx.RequestError, httpx.HTTPStatusError, Error) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"Response parse error: {e}")


# ─── External Brain (외부 AI 두뇌 간접 연동) ─────────────────
class ExternalBrainRequest(BaseModel):
    """Externalbrainrequest.

    Bases: BaseModel
    """

    prompt: str
    target: str = ""  # "gemini_app", "chatgpt_web", "gemini_web", or "" for auto
    strategy: str = "fallback"  # "fallback", "round-robin", "compare"


@router.get("/api/agent/tools/external-brain/list")
async def external_brain_list():
    """사용 가능한 외부 AI 두뇌 목록을 반환합니다."""
    from antigravity_k.engine.external_brain import ExternalBrainRouter

    router_instance = ExternalBrainRouter()
    brains = await router_instance.list_available()
    return {"ok": True, "brains": brains}


@router.post("/api/agent/tools/external-brain/send")
async def external_brain_send(req: ExternalBrainRequest):
    """외부 AI 두뇌에 프롬프트를 전송합니다.

    Antigravity-K가 설치된 Gemini 앱이나 ChatGPT 웹의 채팅 UI를
    GUI 자동화로 제어하여 API 없이 추론 결과를 획득합니다.

    전략:
    - fallback: 첫 번째 가용 두뇌 사용, 실패 시 다음으로
    - round-robin: 순환 사용
    - compare: 여러 두뇌에 동시 전송하여 결과 비교
    """
    from antigravity_k.engine.external_brain import ExternalBrainRouter

    router_instance = ExternalBrainRouter()

    response = await router_instance.send(
        prompt=req.prompt,
        strategy=req.strategy,
        target=req.target,
    )

    return {
        "ok": response.success,
        "source": response.source,
        "text": response.text,
        "latency_ms": round(response.latency_ms, 1),
        "error": response.error,
    }


# ─── TDD Loop Engine ─────────────────────────────────────────
class TDDGenerateRequest(BaseModel):
    """Tddgeneraterequest.

    Bases: BaseModel
    """

    prompt: str
    target_file_path: str | None = None
    max_iterations: int = 3
    coding_model: str = "deepseek-r1:70b"


@router.post("/api/agent/tools/tdd-generate")
async def tdd_generate(req: TDDGenerateRequest):
    """Test-Driven Generation 자율 루프.

    코드와 테스트를 생성하고, 실패 시 에러 로그를 분석하여 코드를 자동 수정합니다.
    """
    try:
        from antigravity_k.api.dependencies import get_model_manager
        from antigravity_k.engine.tdd_engine import OmniTDDEngine

        engine = OmniTDDEngine(
            model_manager=get_model_manager(),
            coding_model=req.coding_model,
            max_iterations=req.max_iterations,
        )
        report = await engine.run_tdd_loop(req.prompt, target_file_path=req.target_file_path)
        return {
            "ok": report.status == "passed",
            "report": report.to_dict(),
        }
    except HTTPException:
        raise
    except (ImportError, RuntimeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))
