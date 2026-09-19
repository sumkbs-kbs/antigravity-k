"""Ssak-Ai ↔ Ssak-Search MCP 어댑터 계약 시험 (task 9).

`MCPTool.execute` 는 MCP `CallToolResult` 의 `isError`/`structuredContent`/image·resource
블록을 보존해야 하고, 서버가 보고한 오류가 호스트에서 *성공*으로 바뀌면 안 된다. 그 계약은
SDK 를 지난 실제 프로토콜 경계에서만 드러나므로 이 시험은 실제 child 프로세스를 띄운다.

1. **실제 W child** — 형제 저장소의 `bin/ssak-mcp`(Bun 컴파일 바이너리). 아티팩트가
   없으면 skip 하며, 경로는 `SSAK_MCP_BIN` 로 덮어쓸 수 있다.
2. **고정 fixture child** — `tests/fixtures/mcp_structured_server.py` 가 structuredContent·
   image/resource/partial/스키마 위반을 만든다. W 서버는 텍스트+isError 만 보내므로
   (task 3 실측) 그 축은 이 child 가 담당한다.

두 경우 모두 child 는 테스트가 띄우고 테스트가 거둔다 — 운영자 데몬(8765)이나 사용자의
Chrome 에는 손대지 않는다.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import psutil
import pytest

from antigravity_k.engine.tool_executor import result_indicates_failure
from antigravity_k.engine.tool_policy import ToolPolicy, reset_tool_policy, set_tool_policy
from antigravity_k.tools.base_tool import BaseTool
from antigravity_k.tools.mcp_tool_loader import MCPTool, MCPToolLoader
from antigravity_k.tools.mcp_tool_result import MCPToolOutcome

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SERVER = PROJECT_ROOT / "tests" / "fixtures" / "mcp_structured_server.py"


def _w_binary() -> Path | None:
    """형제 W 저장소의 컴파일된 stdio MCP 바이너리를 찾는다."""
    candidates: list[Path] = []
    override = os.environ.get("SSAK_MCP_BIN")
    if override:
        candidates.append(Path(override))
    candidates.extend(
        [
            Path.home() / "Downloads" / "webapp" / "bin" / "ssak-mcp",
            PROJECT_ROOT.parent / "webapp" / "bin" / "ssak-mcp",
            Path.home() / "program" / "coding" / "ssak_comp" / "webapp" / "bin" / "ssak-mcp",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


W_BINARY = _w_binary()
requires_w_child = pytest.mark.skipif(
    W_BINARY is None,
    reason="W bin/ssak-mcp 를 찾지 못했습니다 — SSAK_MCP_BIN 로 경로를 지정하세요.",
)


def _children_for(command: list[str]) -> list[psutil.Process]:
    """이 테스트가 띄운 child 만 고른다.

    전체 suite 로 돌리면 같은 프로세스 트리에 **다른 시험의 자식들**이 함께 있다 —
    필터 없이 `children()` 을 쓰면 남의 프로세스를 보고 실패한다(실측: 전체 suite 에서
    이 시험만 빨개졌다). command 문자열이 cmdline 에 들어 있는 것만 우리 child 다.
    """
    marker = " ".join(command)
    if not marker:
        return []
    me = psutil.Process(os.getpid())
    mine: list[psutil.Process] = []
    for child in me.children(recursive=True):
        try:
            cmdline = " ".join(child.cmdline())
        except psutil.Error:
            continue
        if marker in cmdline and child.is_running():
            mine.append(child)
    return mine


def _terminate_children(command: list[str]) -> list[str]:
    """이 테스트가 띄운 child 가 남아 있으면 거두고 이름을 돌려준다."""
    survivors = _children_for(command)
    names = [child.name() for child in survivors]
    for child in survivors:
        try:
            child.terminate()
        except psutil.Error:
            continue
    if survivors:
        _ = psutil.wait_procs(survivors, timeout=5)
    return names


@contextmanager
def _mcp_tools(command: list[str], *, server_name: str = "ssak") -> Iterator[tuple[MCPToolLoader, list[BaseTool]]]:
    """로더로 실제 child 를 띄우고, 끝나면 세션과 child 를 정리한다.

    로더는 세션을 **현재 스레드의 이벤트 루프**에 만든다(운영 경로와 동일). 종료 시 같은
    루프로 정리를 시도하되, SDK 의 cancel-scope 제약(`attempted to exit cancel scope in a
    different task`)으로 실패해도 child 는 직접 거둔다 — 테스트가 프로세스를 흘리지 않게.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / ".mcp.json"
        config_path.write_text(
            json.dumps({"mcpServers": {server_name: {"command": command[0], "args": command[1:]}}}),
            encoding="utf-8",
        )
        loader = MCPToolLoader(config_path=str(config_path), include_system_tools=False, load_skill_servers=False)
        try:
            yield loader, loader.load_tools()
        finally:
            try:
                loop.run_until_complete(loader.session_manager.cleanup())
            except RuntimeError:
                pass  # 로더 teardown 제약 — child 회수는 아래에서 보장한다(task 12 입력)
            loop.close()
            asyncio.set_event_loop(None)
            _ = _terminate_children(command)


def _tool(tools: list[BaseTool], name: str) -> MCPTool:
    for candidate in tools:
        if candidate.name == name:
            assert isinstance(candidate, MCPTool)
            return candidate
    raise AssertionError(f"도구 '{name}' 가 로드되지 않았다: {[t.name for t in tools]}")


def _fixture_command() -> list[str]:
    return [sys.executable, str(FIXTURE_SERVER)]


# ─────────────────────────── 실제 W child 계약 ───────────────────────────


@requires_w_child
def test_real_w_stdio_handshake_loads_typed_tools() -> None:
    """실제 W child 와 handshake·tools/list 가 성립하고 스키마·세션 루프가 배선된다."""
    assert W_BINARY is not None
    with _mcp_tools([str(W_BINARY)]) as (loader, tools):
        names = {tool.name for tool in tools}
        assert {"ssak_search", "ssak_extract", "ssak_deep_research"} <= names, names
        assert loader.schema_errors == [], "W 서버 도구 스키마가 계약을 위반했다"

        search = _tool(tools, "ssak_search")
        schema = cast(dict[str, object], search.parameters_schema)
        assert schema.get("type") == "object"
        assert "query" in cast(dict[str, object], schema["properties"])
        assert search.to_metadata()["mcp"] == {
            "server": "ssak",
            "transport": "stdio",
            "annotations": {},
            "trust_level": "experimental",
            "remote": False,
            "authenticated": False,
            "timeout_ms": None,
        }

        # 세션을 만든 루프가 도구에 전달돼야 한다 — 이 배선이 없으면 워커 스레드 호출이
        # 응답 없는 hang 이 된다(아래 워커 스레드 시험이 그 회귀를 잡는다).
        assert search._session_loop is asyncio.get_event_loop()


@requires_w_child
def test_real_w_invalid_args_is_not_agent_success() -> None:
    """W 가 isError=true 로 거절한 호출은 typed 실패로 남고 원문 payload 도 보존된다."""
    assert W_BINARY is not None
    with _mcp_tools([str(W_BINARY)]) as (_loader, tools):
        outcome = _tool(tools, "ssak_extract").execute(url=123)

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True
        assert outcome.error_code == "INVALID_TOOL_ARGS"
        assert outcome.server_name == "ssak"
        assert result_indicates_failure(outcome) is True, "isError 가 성공으로 집계됐다"
        text = str(outcome)
        assert text.startswith("Error:"), text[:120]
        # 손실 없음: 서버가 준 원문(오류 봉투)이 그대로 남아 있어야 한다.
        assert '"code":"INVALID_TOOL_ARGS"' in text
        assert "retryable" in text


@requires_w_child
def test_real_w_unknown_tool_becomes_typed_error() -> None:
    """존재하지 않는 도구 호출도 typed 오류로 보존된다(성공 변환 금지)."""
    assert W_BINARY is not None
    with _mcp_tools([str(W_BINARY)]) as (loader, tools):
        registered = _tool(tools, "ssak_search")
        ghost = MCPTool(
            name="no_such_tool",
            description="",
            schema={},
            mcp_client=registered._mcp_client,
            server_name="ssak",
            transport="stdio",
            session_loop=loader.session_manager.session_loops.get("ssak"),
        )
        outcome = ghost.execute()

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True
        assert outcome.error_code == "UNKNOWN_TOOL"
        assert "Error:" in str(outcome)


@requires_w_child
def test_real_w_call_from_worker_thread_does_not_hang() -> None:
    """운영 경로(작업 스레드)에서 부른 MCP 호출이 멈추지 않는다.

    `ToolExecutor.execute_async` 는 `asyncio.to_thread(self.execute, ...)` 다. 세션이 다른
    루프에 묶여 있는데 이 스레드에서 새 루프를 만들어 부르면 응답이 영원히 오지 않는다 —
    실측 hang(60초+). 그래서 호출은 세션을 만든 루프로 돌아가야 한다.
    """
    assert W_BINARY is not None
    with _mcp_tools([str(W_BINARY)]) as (_loader, tools):
        extract = _tool(tools, "ssak_extract")
        results: list[object] = []

        def worker() -> None:
            results.append(extract.execute(url=123))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=60)
        assert not thread.is_alive(), "MCP 호출이 워커 스레드에서 멈췄다(세션 루프 교차 hang)"
        assert results, "워커 스레드가 결과를 내지 않았다"
        outcome = results[0]
        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True


@requires_w_child
def test_real_w_request_policy_denial_is_typed_and_blocks_the_server() -> None:
    """허용 서버 목록에 없는 서버의 도구는 도구 수준에서 즉시 거절된다."""
    assert W_BINARY is not None
    with _mcp_tools([str(W_BINARY)]) as (_loader, tools):
        search = _tool(tools, "ssak_search")
        token = set_tool_policy(ToolPolicy(allowed_mcp_servers=frozenset({"other-server"})))
        try:
            outcome = search.execute(query="anything")
        finally:
            reset_tool_policy(token)

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True
        assert outcome.error_code == "POLICY_DENIED"
        assert "[BLOCKED]" in str(outcome)
        assert "ssak" in str(outcome)


@pytest.mark.skipif(
    os.environ.get("SSAK_MCP_NETWORK") != "1",
    reason="실제 검색은 네트워크가 필요하다 — SSAK_MCP_NETWORK=1 로 켠다.",
)
@requires_w_child
def test_real_w_search_success_path_is_not_an_error() -> None:
    """정상 경로(실제 검색)는 오류로 뒤집히지 않는다 — 네트워크 게이트."""
    assert W_BINARY is not None
    with _mcp_tools([str(W_BINARY)]) as (_loader, tools):
        outcome = _tool(tools, "ssak_search").execute(query="python asyncio", max_results=2)

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is False, str(outcome)[:400]
        assert result_indicates_failure(outcome) is False
        assert "results" in str(outcome)


# ─────────────────────────── 고정 fixture child 계약 ───────────────────────────


def test_fixture_child_preserves_plain_text_verbatim() -> None:
    """평문 MCP 결과는 가공 없이 원문 그대로 전달된다."""
    with _mcp_tools(_fixture_command(), server_name="fixture") as (_loader, tools):
        outcome = _tool(tools, "plain_text").execute(q="x")

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is False
        assert str(outcome) == "plain payload — 그대로 보존되어야 한다"
        assert outcome.structured_content is None
        assert [block["type"] for block in outcome.blocks] == ["text"]


def test_fixture_child_preserves_structured_content_and_partial() -> None:
    """structuredContent 와 partial 표시가 typed 결과로 보존된다."""
    with _mcp_tools(_fixture_command(), server_name="fixture") as (_loader, tools):
        outcome = _tool(tools, "structured").execute()

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is False
        structured = cast(dict[str, object], outcome.structured_content)
        assert structured["status"] == "partial"
        assert structured["partial"] is True
        assert outcome.partial is True, "partial 표시가 호스트로 전달되지 않았다"
        # 모델이 보는 본문에도 구조가 실린다(구조를 버리지 않는다).
        assert "[structuredContent]" in str(outcome)
        assert '"results"' in str(outcome)


def test_fixture_child_preserves_media_blocks() -> None:
    """image/embedded resource(text·blob)/resource_link 가 손실 없이 보존된다."""
    with _mcp_tools(_fixture_command(), server_name="fixture") as (_loader, tools):
        outcome = _tool(tools, "media").execute()

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is False
        kinds = [block["type"] for block in outcome.blocks]
        assert kinds == ["text", "image", "resource", "resource", "resource_link"], kinds

        image = outcome.blocks[1]
        assert image["mimeType"] == "image/png"
        assert isinstance(image["data"], str) and len(image["data"]) > 50, "이미지 페이로드가 버려졌다"

        text_resource = outcome.blocks[2]
        assert text_resource["text"] == "임베디드 리소스 본문"
        blob_resource = outcome.blocks[3]
        assert blob_resource["blob"] == "AAECAwQ="
        link = outcome.blocks[4]
        assert link["uri"] == "fixture://linked.txt"

        text = str(outcome)
        assert "media bundle" in text
        assert "[image: image/png" in text
        assert "임베디드 리소스 본문" in text
        assert "[resource: fixture://blob.bin" in text
        assert "fixture://linked.txt" in text


def test_fixture_child_is_error_is_typed_failure() -> None:
    """fixture 의 isError 응답도 typed 실패 + 텍스트 마커를 함께 갖는다."""
    with _mcp_tools(_fixture_command(), server_name="fixture") as (_loader, tools):
        outcome = _tool(tools, "erroring").execute()

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True
        assert outcome.error_code == "INVALID_TOOL_ARGS"
        assert result_indicates_failure(outcome) is True
        degraded = str(outcome)  # host 가 str() 로 감싸는 경로(str-기반 분류)도 실패로 남아야 한다
        assert degraded.startswith("Error:")
        assert result_indicates_failure(degraded) is True


def test_fixture_child_schema_violations_are_refused_at_load() -> None:
    """inputSchema 계약 위반 도구는 등록되지 않고 이유가 기록된다."""
    with _mcp_tools(_fixture_command(), server_name="fixture") as (loader, tools):
        names = {tool.name for tool in tools}

        assert "bad_schema" not in names, "type!=object 스키마 도구가 등록됐다"
        assert "bad_required" not in names, "required 형식이 틀린 도구가 등록됐다"
        assert "plain_text" in names and "structured" in names  # 정상 도구는 그대로

        recorded = {entry["tool"]: entry["reason"] for entry in loader.schema_errors}
        assert set(recorded) == {"bad_schema", "bad_required"}
        assert all(entry["server"] == "fixture" for entry in loader.schema_errors)


def test_fixture_child_leaves_no_process_behind() -> None:
    """계약 시험이 child 를 흘리지 않는다(운영자 프로세스 보호)."""
    command = _fixture_command()
    with _mcp_tools(command, server_name="fixture") as (_loader, tools):
        assert _tool(tools, "plain_text").execute(q="x")

    assert _terminate_children(command) == [], "테스트가 MCP child 를 남겼다"


def test_leftover_check_ignores_other_tests_children() -> None:
    """잔여 확인은 **우리 child 만** 본다 — 전체 suite 에서 남의 프로세스를 보고 실패하면 안 된다.

    (실측 동기: 이 시험 없이 전체 suite 를 돌리니 다른 시험이 띄운 자식 때문에 이 파일만 빨개졌다.)
    """
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert _children_for([sys.executable, str(pathlib.Path("__nonexistent_marker__"))]) == []
        seen = _terminate_children(_fixture_command())
        assert unrelated.poll() is None, "무관한 프로세스를 거둬버렸다"
        assert seen == [], f"무관한 자식을 우리 child 로 셌다: {seen}"
    finally:
        unrelated.terminate()
        _ = unrelated.wait(timeout=10)
