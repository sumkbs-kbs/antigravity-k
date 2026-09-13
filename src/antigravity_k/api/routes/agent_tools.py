"""Agent Tools module."""

import asyncio
import base64
import hashlib
import inspect
import logging
import os
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

from antigravity_k.api.browser_session_state import (
    BrowserSessionLimitError,
    BrowserSessionRegistry,
    BrowserSessionState,
)
from antigravity_k.api.contracts.shell import (
    ShellApprovalRequiredError,
    ShellPolicyDeniedError,
    ShellSandboxUnavailableError,
    ShellTimeoutError,
)
from antigravity_k.config import config
from antigravity_k.engine.access_mode import AccessMode, get_access_mode
from antigravity_k.engine.sandbox import SandboxRunner, _minimal_child_env, _python_runtime_read_paths
from antigravity_k.tools.egress_policy import EgressPolicyError, validate_egress_url, validate_httpx_request_async
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.tool_contracts import Permission, PermissionDecision, ToolInvocation, ToolSpec

logger = logging.getLogger(__name__)
router = APIRouter()


browser_state = BrowserSessionState()
browser_sessions = BrowserSessionRegistry(default_state=browser_state)
_MAX_CONSOLE_ENTRIES = 500
_BROWSER_SESSION_HEADER = "X-AGK-Browser-Session"
_MAX_BROWSER_SESSION_ID_LENGTH = 128


class _AccessibilityLike(Protocol):
    async def snapshot(self) -> object: ...


class _PageLike(Protocol):
    accessibility: _AccessibilityLike
    url: str

    def aria_snapshot(self) -> Awaitable[object]: ...

    async def screenshot(self) -> bytes: ...

    async def goto(self, url: str, *, wait_until: str) -> object: ...

    async def click(self, selector: str) -> object: ...

    async def fill(self, selector: str, text: str) -> object: ...

    def on(self, event: str, handler: Callable[[object], object]) -> object: ...


class _RouteLike(Protocol):
    async def abort(self, *, error_code: str) -> object: ...

    async def continue_(self) -> object: ...


class _RequestLike(Protocol):
    url: str


def _as_text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


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


async def _accessibility_tree(page: object) -> str | None:
    page_obj = cast(_PageLike, page)
    if hasattr(page_obj, "aria_snapshot"):
        result = page_obj.aria_snapshot()
        if not inspect.isawaitable(result):
            return None
        snapshot = await result
        return snapshot if isinstance(snapshot, str) and snapshot else None

    accessibility = getattr(page_obj, "accessibility", None)
    if accessibility is None:
        return None
    snapshot_value = await cast(_AccessibilityLike, accessibility).snapshot()
    snapshot = _as_mapping(snapshot_value)
    return _flatten_a11y_tree(snapshot) if snapshot else None


async def _guard_browser_route(route: object, request: object) -> None:
    route_obj = cast(_RouteLike, route)
    request_obj = cast(_RequestLike, request)
    scheme = request_obj.url.split(":", 1)[0].lower()
    if scheme not in {"http", "https"}:
        _ = await route_obj.abort(error_code="blockedbyclient")
        return
    try:
        _ = validate_egress_url(request_obj.url, allow_local=False)
    except EgressPolicyError:
        _ = await route_obj.abort(error_code="blockedbyclient")
        return
    _ = await route_obj.continue_()


# ─── CR-04: 실행 경계 — 권한 모드와 요청 root 스냅샷 ────────────────────
#
# 이전 구현은 `mode="auto-pilot"`을 상수로 고정해, 사용자가 대시보드에서 선택한
# 실행 권한 모드(전체 액세스 / 읽기 전용)를 무시하고 high-risk 도구(셸 실행)를
# 항상 자동 승인했다. 이제는 현재 요청의 기존 권한 모드에서 모드를 도출한다:
#  - FULL_ACCESS(사용자가 명시적으로 허용)  → auto-pilot: high-risk 도구 자동 승인
#  - READ_ONLY(읽기 전용)                   → balanced: high-risk 도구는 ASK(prompt)
# 별도 승인 workflow가 없는 동기 API이므로 ASK는 실행 없이 403을 반환한다
# (allow로 승격하지 않는다). DENY도 실행 0회다.
_PERMISSION_MODE_BY_ACCESS_MODE: dict[AccessMode, str] = {
    AccessMode.FULL_ACCESS: "auto-pilot",
    AccessMode.READ_ONLY: "balanced",
}
_SHELL_TOOL_NAME = "run_bash_command"


def _permission_mode() -> str:
    """현재 요청의 기존 권한 모드 → PermissionGate 모드."""
    return _PERMISSION_MODE_BY_ACCESS_MODE.get(get_access_mode(), "balanced")


def _shell_request_root(req: "ShellRunRequest", request: Request) -> str:
    """셸 실행 root를 요청 시작 시점에 1회 확정한다(재조회·재바인딩 없음).

    우선순위:
    1. 이미 바인딩된 ARC-01 요청 실행 컨텍스트(chat/task가 실행한 경우)
    2. 클라이언트가 명시한 ``project_id``(ARC-01 resolution)
    3. ``X-AGK-Session-Id``로 명시된 session active-project binding
    4. 그 외 구형 클라이언트는 서버 기본 root(기존 동작)

    """
    from antigravity_k.api.project_binding import (
        SESSION_ID_HEADER,
        get_request_project_root,
        get_session_active_project,
        resolve_project_execution_context,
    )
    from antigravity_k.engine.project_registry import get_project_registry

    bound = get_request_project_root()
    if bound:
        return os.path.realpath(bound)

    project_id = (req.project_id or "").strip()
    if not project_id:
        header_session = request.headers.get(SESSION_ID_HEADER)
        binding = get_session_active_project(header_session) if header_session else None
        if binding is None:
            return os.path.realpath(str(config.paths.project_root))
        project_id = binding.project_id

    context = resolve_project_execution_context(
        payload=None,
        project_id=project_id,
        registry=get_project_registry(),
        bind=False,
    )
    return os.path.realpath(context.canonical_project_root)


def _permission_gate(root: str | None = None) -> PermissionGate:
    return PermissionGate(project_root=root or str(config.paths.project_root), mode=_permission_mode())


def _decide_shell_permission(*, root: str, command: str, cwd: str) -> PermissionDecision:
    """셸 실행 전 권한 결정 — 검사 경로와 실행 경로를 같은 root로 고정한다."""
    return _permission_gate(root).decide(
        ToolInvocation(
            ToolSpec(name=_SHELL_TOOL_NAME, risk_level="high", category="api"),
            {"command": command, "cwd": cwd},
        ),
    )


def _enforce_shell_permission(*, root: str, command: str, cwd: str) -> None:
    """ASK/DENY는 실행 0회로 끝낸다. 승인 workflow 없이 allow로 승격하지 않는다."""
    # 실행 모드(Plan/Build/Interactive)가 도구를 막으면 권한 gate 이전에 거부한다.
    from antigravity_k.api.dependencies import get_mode_manager

    execution_mode = get_mode_manager().current_mode
    if not execution_mode.tool_is_allowed(_SHELL_TOOL_NAME):
        raise ShellPolicyDeniedError(
            detail=execution_mode.get_block_reason(_SHELL_TOOL_NAME),
            context={"tool": _SHELL_TOOL_NAME, "execution_mode": execution_mode.value},
        )

    decision = _decide_shell_permission(root=root, command=command, cwd=cwd)
    access_mode = get_access_mode().value
    if decision.permission is Permission.PROMPT:
        raise ShellApprovalRequiredError(
            detail=(
                "Shell execution requires explicit approval in the current permission mode "
                "(ASK); no approval workflow is attached to this endpoint"
            ),
            context={"tool": _SHELL_TOOL_NAME, "access_mode": access_mode, "permission_mode": _permission_mode()},
        )
    if decision.permission is not Permission.ALLOW:
        raise ShellPolicyDeniedError(
            detail="Shell execution was denied by policy (DENY)",
            context={"tool": _SHELL_TOOL_NAME, "access_mode": access_mode, "reason": decision.reason},
        )


def _require_allowed(tool_name: str, args: dict[str, object], risk_level: str) -> None:
    decision = _permission_gate().decide(
        ToolInvocation(ToolSpec(name=tool_name, risk_level=risk_level, category="api"), args),
    )
    if decision.permission != Permission.ALLOW:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied for {tool_name}: {decision.permission.value}",
        )


def _resolve_project_cwd(cwd: str | None, *, root: str | None = None) -> str:
    project_root = Path(root or config.paths.project_root).resolve()
    candidate = (project_root if not cwd else Path(cwd).expanduser()).resolve()
    try:
        _ = candidate.relative_to(project_root)
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
        _ = candidate.relative_to(project_root)
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
    # CR-04: ARC-01 프로젝트를 명시한 요청은 그 프로젝트 root에서만 실행한다.
    project_id: str | None = None


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
            _ = f.write(req.content)
        return {"ok": True, "path": path}
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/agent/tools/shell/run")
def run_shell(req: ShellRunRequest, request: Request):
    """터미널 명령을 OS 샌드박스에서 실행합니다 (CR-04 실행·승인 경계).

    실행 권한 모드(전체 액세스/읽기 전용)와 요청 root는 요청 시작 시점에 확정한다.
    - ASK → 실행 없이 403 ``shell_approval_required``
    - DENY → 실행 0회, 403 ``shell_policy_denied``
    - ALLOW → CR-03 제한 읽기 + 최소 env의 sandbox 실행(폴백 없음)
    """
    root = _shell_request_root(req, request)
    cwd = _resolve_project_cwd(req.cwd, root=root)
    _enforce_shell_permission(root=root, command=req.command, cwd=cwd)
    timeout = max(1, min(req.timeout, int(config.security.max_execution_time)))
    try:
        runner = SandboxRunner(
            project_root=root,
            enabled=bool(config.security.sandbox_enabled),
            network=str(config.security.sandbox_network),
            timeout=timeout,
            max_output_bytes=int(config.security.max_output_bytes),
            max_memory_mb=int(config.security.max_memory_mb),
            max_processes=int(config.security.max_processes),
            # CR-03 경계 재사용: 민감 트리 deny + 작업 디렉토리/런타임만 재허용.
            restrict_reads=True,
            # 설정으로 꺼졌거나 backend가 없으면 raw host 실행으로 대체하지 않는다.
            require_sandbox=True,
            read_allow_paths=[cwd, *_python_runtime_read_paths()],
        )
        result = runner.execute(
            req.command,
            timeout=timeout,
            # 부모 os.environ(모델 provider 키·서버 PIN/token secret) 상속 금지.
            env=_minimal_child_env(cwd),
            cwd=cwd,
        )
        if result.timed_out:
            raise ShellTimeoutError(
                detail=f"Shell command exceeded the {timeout}s execution time limit",
                context={"tool": _SHELL_TOOL_NAME, "timeout_seconds": timeout},
            )
        if result.error:
            # 내부 오류 문자열(경로·환경)은 응답에 넣지 않고 로그에만 남긴다.
            logger.warning("sandboxed shell failed to start: %s", result.error)
            raise ShellSandboxUnavailableError(
                detail=(
                    "OS sandbox could not run this command; raw host execution is disabled. "
                    "Check security.sandbox_enabled and the sandbox backend."
                ),
                context={"tool": _SHELL_TOOL_NAME},
            )
        return {
            "ok": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.return_code,
            "sandboxed": result.sandboxed,
            "output_truncated": result.output_truncated,
            "timed_out": result.timed_out,
        }
    except (ShellApprovalRequiredError, ShellPolicyDeniedError, ShellSandboxUnavailableError, ShellTimeoutError):
        raise
    except (OSError, ValueError) as e:
        # 실행 환경 전체(경로·env)를 노출하지 않는다.
        logger.warning("shell execution failed: %s", e)
        raise HTTPException(status_code=500, detail="Shell execution failed") from e


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
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                )
                state.context = context
                _ = await context.route("**/*", _guard_browser_route)
                page = await context.new_page()
                state.page = page
                # Console error/log auto-collection
                state.console_errors = []
                state.console_logs = []
                page.on(
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
                _ = browser_sessions.discard(session_id)
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
                _ = validate_egress_url(req.url, allow_local=False)
            except EgressPolicyError as exc:
                raise HTTPException(status_code=403, detail="Browser navigation target is not public.") from exc
            _ = await state.page.goto(req.url, wait_until="networkidle")
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
def _flatten_a11y_tree(node: Mapping[str, object], depth: int = 0) -> str:
    """Playwright의 Accessibility Tree를 LLM이 이해할 수 있는.

    컴팩트한 텍스트 표현으로 변환합니다.

    예시 출력:
      [button] "Send" focused
        [img] "send icon"
      [textbox] "채팅 입력" value="hello"
    """
    lines: list[str] = []
    role = _as_text(node.get("role"), "unknown")
    name = _as_text(node.get("name"))
    value = _as_text(node.get("value"))
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

    children = node.get("children", [])
    if isinstance(children, list):
        for child in cast(list[object], children):
            if isinstance(child, Mapping):
                lines.extend(_flatten_a11y_tree(cast(Mapping[str, object], child), depth + 1).split("\n"))

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


_DEFAULT_BROWSER_SELF_TEST_REQUEST = BrowserSelfTestRequest()


@router.post("/api/agent/tools/browser/self-test")
async def browser_self_test(
    request: Request,
    req: Annotated[BrowserSelfTestRequest, Body()] = _DEFAULT_BROWSER_SELF_TEST_REQUEST,
):
    """기존 TestHarness 프레임워크를 활용하여.

    Ssak-Ai가 스스로를 테스트하는 멀티스텝 오케스트레이션 루프.

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
    max_iterations: int = Field(default=3, ge=1, le=10)
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
        _ = validate_egress_url(req.url, allow_local=True)
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
            if analysis.strip():
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
                data = _as_mapping(cast(object, response.json()))
                analysis = _as_text(_as_mapping(data.get("message")).get("content"), "분석 결과 없음")
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

    Ssak-Ai가 설치된 Gemini 앱이나 ChatGPT 웹의 채팅 UI를
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
    max_iterations: int = Field(default=3, ge=1, le=10)
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
