"""Agent Tools module."""

import asyncio
import base64
import hashlib
import inspect
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

from antigravity_k.api.browser_session_state import (
    BrowserSessionLimitError,
    BrowserSessionRegistry,
    BrowserSessionState,
)
from antigravity_k.config import config
from antigravity_k.engine.sandbox import SandboxRunner
from antigravity_k.tools.egress_policy import EgressPolicyError, validate_egress_url, validate_httpx_request_async
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_contracts import ToolInvocation, ToolSpec

logger = logging.getLogger(__name__)
router = APIRouter()


browser_state = BrowserSessionState()
browser_sessions = BrowserSessionRegistry(default_state=browser_state)
_MAX_CONSOLE_ENTRIES = 500
_BROWSER_SESSION_HEADER = "X-AGK-Browser-Session"
_MAX_BROWSER_SESSION_ID_LENGTH = 128


def _append_console_entry(entries: list[dict[str, str]], entry: dict[str, str]) -> None:
    entries.append(entry)
    if len(entries) > _MAX_CONSOLE_ENTRIES:
        del entries[:-_MAX_CONSOLE_ENTRIES]


def _browser_session_id(request: Request | None) -> str:
    if request is None:
        return "default"
    raw_session_id = request.headers.get(_BROWSER_SESSION_HEADER, "").strip()
    if len(raw_session_id) > _MAX_BROWSER_SESSION_ID_LENGTH:
        raise HTTPException(status_code=400, detail="Browser session identifier is too long")
    auth_subject = getattr(request.state, "auth_subject", "anonymous")
    if not isinstance(auth_subject, str) or not auth_subject:
        auth_subject = "anonymous"
    if not raw_session_id:
        raw_session_id = "default"
    session_key = f"{auth_subject}:{raw_session_id}"
    return hashlib.sha256(session_key.encode("utf-8")).hexdigest()


def _browser_state_for(request: Request | None) -> tuple[str, BrowserSessionState]:
    session_id = _browser_session_id(request)
    try:
        return session_id, browser_sessions.get(session_id)
    except BrowserSessionLimitError as exc:
        raise HTTPException(status_code=429, detail="Too many active browser sessions") from exc


def _browser_error_status(error: Exception) -> int:
    message = str(error).lower()
    if "executable doesn't exist" in message or "please run the following command" in message:
        return 503
    return 500


async def _accessibility_tree(page: Any) -> str | None:
    if hasattr(page, "aria_snapshot"):
        result = page.aria_snapshot()
        if not inspect.isawaitable(result):
            return None
        snapshot = await result
        return snapshot if isinstance(snapshot, str) and snapshot else None

    accessibility = getattr(page, "accessibility", None)
    if accessibility is None:
        return None
    snapshot = await accessibility.snapshot()
    return _flatten_a11y_tree(snapshot) if snapshot else None


async def _guard_browser_route(route: Any, request: Any) -> None:
    scheme = request.url.split(":", 1)[0].lower()
    if scheme not in {"http", "https"}:
        await route.abort(error_code="blockedbyclient")
        return
    try:
        validate_egress_url(request.url, allow_local=False)
    except EgressPolicyError:
        await route.abort(error_code="blockedbyclient")
        return
    await route.continue_()


def _permission_gate() -> PermissionGate:
    return PermissionGate(project_root=str(config.paths.project_root), mode="auto-pilot")


def _require_allowed(tool_name: str, args: dict[str, Any], risk_level: str):
    decision = _permission_gate().decide(
        ToolInvocation(ToolSpec(name=tool_name, risk_level=risk_level, category="api"), args),
    )
    if decision.permission != Permission.ALLOW:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied for {tool_name}: {decision.permission.value}",
        )


def _resolve_project_cwd(cwd: str | None) -> str:
    project_root = Path(config.paths.project_root).resolve()
    candidate = (project_root if not cwd else Path(cwd).expanduser()).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Working directory must remain inside the project root") from exc
    if not candidate.is_dir():
        raise HTTPException(status_code=400, detail="Working directory does not exist")
    return str(candidate)


def _resolve_project_path(path: str) -> str:
    project_root = Path(config.paths.project_root).resolve()
    raw_path = Path(path).expanduser()
    candidate = (raw_path if raw_path.is_absolute() else project_root / raw_path).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="File path must remain inside the project root") from exc
    return str(candidate)


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
    path = _resolve_project_path(req.path)
    _require_allowed("read_file", {"path": path}, "safe")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        with open(path, encoding="utf-8") as f:
            return {"ok": True, "content": f.read()}
    except (OSError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/agent/tools/fs/write")
def write_file(req: FileWriteRequest):
    """파일을 생성하거나 덮어씁니다."""
    path = _resolve_project_path(req.path)
    _require_allowed("write_file", {"path": path}, "medium")
    if os.path.exists(path) and not req.overwrite:
        raise HTTPException(status_code=400, detail="File exists, use overwrite=True")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"ok": True, "path": path}
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/agent/tools/shell/run")
def run_shell(req: ShellRunRequest):
    """터미널 명령을 샌드박스에서 실행합니다."""
    cwd = _resolve_project_cwd(req.cwd)
    _require_allowed("run_bash_command", {"command": req.command, "path": cwd}, "high")
    timeout = max(1, min(req.timeout, int(config.security.max_execution_time)))
    try:
        result = SandboxRunner(
            project_root=str(config.paths.project_root),
            enabled=bool(config.security.sandbox_enabled),
            network=str(config.security.sandbox_network),
            timeout=timeout,
            max_output_bytes=int(config.security.max_output_bytes),
            max_memory_mb=int(config.security.max_memory_mb),
            max_processes=int(config.security.max_processes),
        ).execute(
            req.command,
            timeout=timeout,
            cwd=cwd,
        )
        if result.error:
            raise HTTPException(status_code=503, detail=result.error)
        return {
            "ok": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.return_code,
            "sandboxed": result.sandboxed,
            "output_truncated": result.output_truncated,
        }
    except HTTPException:
        raise
    except (OSError, ValueError) as e:
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
async def browser_action(req: BrowserActionRequest, request: Request):
    """Playwright 기반 브라우저 자동화 엔진 API."""
    risk_level = "safe" if req.action in {"snapshot", "console_errors"} else "medium"
    if req.action == "goto":
        risk_level = "high"
    _require_allowed(
        "browser_action",
        {"action": req.action, "url": req.url, "selector": req.selector},
        risk_level,
    )
    session_id, state = _browser_state_for(request)
    try:
        from playwright.async_api import Error, async_playwright
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Browser automation is unavailable; install the dev dependency group to enable Playwright.",
        ) from exc
    try:
        if req.action == "launch":
            if not state.playwright:
                state.playwright = await async_playwright().start()
            assert state.playwright is not None
            if not state.browser:
                state.browser = await state.playwright.chromium.launch(
                    headless=True,
                )
                browser = state.browser
                assert browser is not None
                state.context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                )
                await state.context.route("**/*", _guard_browser_route)
                state.page = await state.context.new_page()
                # Console error/log auto-collection
                state.console_errors = []
                state.console_logs = []
                state.page.on(
                    "console",
                    lambda msg: (
                        _append_console_entry(state.console_errors, {"type": msg.type, "text": msg.text})
                        if msg.type in ("error", "warning")
                        else _append_console_entry(state.console_logs, {"type": msg.type, "text": msg.text})
                    ),
                )
            return {"ok": True, "message": "Browser launched with console capture"}

        elif req.action == "close":
            if state.browser:
                await state.browser.close()
                state.browser = None
                state.context = None
                state.page = None
            if state.playwright:
                await state.playwright.stop()
                state.playwright = None
            if session_id != "default":
                browser_sessions.discard(session_id)
            return {"ok": True, "message": "Browser closed"}

        # For remaining actions, ensure page exists
        if not state.page:
            raise HTTPException(
                status_code=400,
                detail="Browser is not launched. Call 'launch' first.",
            )

        if req.action == "goto":
            if not req.url:
                raise HTTPException(status_code=400, detail="URL is required for goto")
            try:
                validate_egress_url(req.url, allow_local=False)
            except EgressPolicyError as exc:
                raise HTTPException(status_code=403, detail="Browser navigation target is not public.") from exc
            await state.page.goto(req.url, wait_until="networkidle")
            return {"ok": True, "url": req.url}

        elif req.action == "click":
            if not req.selector:
                raise HTTPException(status_code=400, detail="Selector is required for click")
            await state.page.click(req.selector)
            return {"ok": True, "selector": req.selector}

        elif req.action == "type":
            if not req.selector or req.text is None:
                raise HTTPException(
                    status_code=400,
                    detail="Selector and text are required for type",
                )
            await state.page.fill(req.selector, req.text)
            return {"ok": True, "selector": req.selector, "text": req.text}

        elif req.action == "snapshot":
            # Accessibility Tree + Screenshot + Console errors
            screenshot_bytes = await state.page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            # Accessibility Tree (compact text representation for LLM)
            a11y_tree = None
            try:
                a11y_tree = await _accessibility_tree(state.page)
            except (Error, TimeoutError, TypeError) as exc:
                logger.warning("Accessibility snapshot unavailable: %s", exc)

            return {
                "ok": True,
                "screenshot_base64": screenshot_b64,
                "accessibility_tree": a11y_tree,
                "console_errors": state.console_errors[-20:],
                "console_logs_count": len(state.console_logs),
                "url": state.page.url,
            }

        elif req.action == "console_errors":
            return {
                "ok": True,
                "errors": state.console_errors,
                "total": len(state.console_errors),
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    except HTTPException:
        raise
    except (Error, OSError, TimeoutError) as e:
        raise HTTPException(status_code=_browser_error_status(e), detail=str(e))


# ─── Accessibility Tree Flattener ─────────────────────────────
def _flatten_a11y_tree(node: dict[str, Any], depth: int = 0) -> str:
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
    vision_model: str = "qwen3.6:latest"
    coding_model: str = "qwen3.6:latest"


@router.post("/api/agent/tools/browser/autonomous-qa")
async def autonomous_qa_loop(req: AutonomousQARequest):
    """완전 자율 QA 루프: 비전 분석 → 코드 수정 → 자동 적용 → 재테스트 → 검증.

    이 엔드포인트가 호출되면:
    1. Playwright로 대시보드 스크린샷 촬영
    2. qwen3.6:latest가 UI 결함 분석
    3. qwen3.6:latest가 코드 수정 패치 생성
    4. 패치 자동 적용 → 리로드 → 재분석
    5. 결함 해소 확인될 때까지 최대 N회 반복
    6. 반응형 테스트(desktop/tablet/mobile) + 성능 메트릭 수집
    """
    try:
        validate_egress_url(req.url, allow_local=True)
    except EgressPolicyError as exc:
        raise HTTPException(status_code=403, detail="Autonomous QA target must be a valid HTTP(S) URL") from exc
    _require_allowed("autonomous_qa", {"url": req.url}, "critical")
    try:
        from antigravity_k.api.dependencies import get_model_manager
        from antigravity_k.engine.autonomous_qa import AutonomousQAEngine

        engine = AutonomousQAEngine(
            dashboard_url=req.url,
            vision_model=req.vision_model,
            coding_model=req.coding_model,
            max_iterations=req.max_iterations,
            model_manager=get_model_manager(),
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
    model: str = "qwen3.6:latest"


@router.post("/api/agent/tools/browser/vision-analyze")
async def vision_analyze(req: VisionAnalyzeRequest, request: Request):
    """멀티모달 비전 LLM을 활용한 UI 스크린샷 자동 분석.

    1. screenshot_base64가 없으면 현재 브라우저에서 자동 캡처
    2. 비전 모델(qwen3.6:latest)에 이미지+프롬프트 전달
    3. UI 결함 분석 결과 반환
    """
    import httpx

    try:
        _, state = _browser_state_for(request)
        # 스크린샷 자동 캡처 (없으면)
        screenshot_b64 = req.screenshot_base64
        if not screenshot_b64 and state.page:
            try:
                screenshot_bytes = await state.page.screenshot()
            except ModuleNotFoundError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Browser capture is unavailable; install the dev dependency group to enable Playwright.",
                ) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        if not screenshot_b64:
            raise HTTPException(
                status_code=400,
                detail="No screenshot available. Launch browser and navigate first, or provide screenshot_base64.",
            )

        from antigravity_k.api.dependencies import get_model_manager

        model_manager = get_model_manager()
        target = req.model
        if target == "qwen3.6:latest":
            target = model_manager.get_target_for_role("vision", default_role="vision")
        try:
            analysis = await asyncio.to_thread(
                model_manager.generate,
                req.prompt,
                target=target,
                raw_messages=[
                    {"role": "user", "content": req.prompt, "images": [screenshot_b64]},
                ],
                max_tokens=2048,
                temperature=0.2,
            )
            if isinstance(analysis, str) and analysis.strip():
                return {"ok": True, "model": target, "analysis": analysis}
        except Exception:
            logger.warning("Managed vision route failed, HTTP fallback", exc_info=True)

        # Ollama 멀티모달 API 호출
        async with httpx.AsyncClient(
            timeout=120.0,
            event_hooks={"request": [validate_httpx_request_async]},
        ) as client:
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
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
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
    _require_allowed("external_brain_list", {}, "safe")
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
    _require_allowed(
        "external_brain_send",
        {"target": req.target, "strategy": req.strategy},
        "critical",
    )
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
    coding_model: str = "qwen3.6:latest"


@router.post("/api/agent/tools/tdd-generate")
async def tdd_generate(req: TDDGenerateRequest):
    """Test-Driven Generation 자율 루프.

    코드와 테스트를 생성하고, 실패 시 에러 로그를 분석하여 코드를 자동 수정합니다.
    """
    target_file_path = _resolve_project_path(req.target_file_path) if req.target_file_path else None
    _require_allowed(
        "tdd_generate",
        {"path": target_file_path, "max_iterations": req.max_iterations},
        "critical",
    )
    try:
        from antigravity_k.api.dependencies import get_model_manager
        from antigravity_k.engine.tdd_engine import OmniTDDEngine

        engine = OmniTDDEngine(
            model_manager=get_model_manager(),
            coding_model=req.coding_model,
            max_iterations=req.max_iterations,
        )
        report = await engine.run_tdd_loop(req.prompt, target_file_path=target_file_path)
        return {
            "ok": report.status == "passed",
            "report": report.to_dict(),
        }
    except HTTPException:
        raise
    except (ImportError, RuntimeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=str(e))
