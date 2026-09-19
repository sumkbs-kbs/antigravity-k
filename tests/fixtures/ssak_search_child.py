"""런타임 수명주기 시험용 stdio MCP child.

관리형 런타임(task 12)의 계약은 **실제 자식 프로세스**에서만 드러난다 — 동시 첫 호출에 child 가
하나인지, crash loop 에서 backoff 가 실제로 걸리는지, host 종료 후 child 가 0 인지는 프로세스 관측으로만
확인된다. 그래서 여기서는 표준 라이브러리만으로 JSON-RPC(줄 단위) stdio 서버를 직접 띄운다.

사용법::

    python ssak_search_child.py <mode>

mode:
  - ``ok``            : 정상 서버
  - ``crash_start``   : ``initialize`` 전에 exit 3 (시작 실패 → backoff/회로 시험)
  - ``die_on_call``   : 첫 ``tools/call`` 응답 직후 exit 7 (exit 관찰 시험)
  - ``die_after_ms``  : ``initialize`` 후 ``SSAK_CHILD_DIE_MS`` 뒤 exit 9 (조용한 죽음 관찰)
  - ``slow``          : ``tools/call`` 마다 ``SSAK_CHILD_SLOW_MS`` 대기 (호출 타임아웃 시험)

기록: ``SSAK_CHILD_RECORD`` 가 가리키는 파일에 다음을 남긴다.
  - ``<record>``        : ``{pid, ppid, cwd, env, argv, started_at}`` (spawn 증거 + env allowlist/cwd 불변 증거)
  - ``<record>.calls``  : 호출마다 한 줄 ``{name, at}`` (호출 횟수 = 재시도 여부 증거)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

CALLS_SUFFIX = ".calls"

TOOLS: list[dict[str, object]] = [
    {
        "name": "ssak_search",
        "description": "테스트 검색 결과를 돌려준다",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "count_calls",
        "description": "지금까지 받은 툴 호출 수를 돌려준다(재시도 관측용)",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "mutating_write",
        "description": "비멱등 작업 표시(재시도 금지 시험용)",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def _record_path() -> str | None:
    return os.environ.get("SSAK_CHILD_RECORD")


def _append_call(name: str) -> None:
    path = _record_path()
    if not path:
        return
    with open(f"{path}{CALLS_SUFFIX}", "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"name": name, "at": time.time()}) + "\n")


def _call_count() -> int:
    path = _record_path()
    if not path or not os.path.exists(f"{path}{CALLS_SUFFIX}"):
        return 0
    with open(f"{path}{CALLS_SUFFIX}", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _write_spawn_record(mode: str) -> None:
    path = _record_path()
    if not path:
        return
    payload = {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "cwd": os.getcwd(),
        "env": dict(os.environ),
        "argv": sys.argv,
        "mode": mode,
        "started_at": time.time(),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def _respond(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result_for(name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name == "count_calls":
        return {"content": [{"type": "text", "text": json.dumps({"calls": _call_count()})}]}
    if name == "mutating_write":
        return {"content": [{"type": "text", "text": json.dumps({"applied": True})}]}
    if name == "ssak_search":
        query = str(arguments.get("query", ""))
        return {
            "content": [
                {"type": "text", "text": json.dumps({"query": query, "results": [{"title": "a"}, {"title": "b"}]})}
            ],
            "structuredContent": {"query": query, "partial": False, "results": [{"title": "a"}, {"title": "b"}]},
        }
    return {"content": [{"type": "text", "text": json.dumps({"error": {"code": "UNKNOWN_TOOL"}})}], "isError": True}


def _arm_death_timer(milliseconds: float) -> None:
    """트래픽과 무관한 조용한 죽음 — exit 관찰이 "요청이 왔을 때만" 동작하면 안 된다."""
    if milliseconds <= 0:
        return
    timer = threading.Timer(milliseconds / 1000.0, lambda: os._exit(9))
    timer.daemon = True
    timer.start()


def _serve(mode: str) -> None:
    slow_ms = float(os.environ.get("SSAK_CHILD_SLOW_MS", "0") or 0)
    die_after_ms = float(os.environ.get("SSAK_CHILD_DIE_MS", "0") or 0)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = message.get("method")
        request_id = message.get("id")

        if method == "initialize":
            params = message.get("params") or {}
            _respond(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "ssak-search-child-fixture", "version": "1.0.0"},
                    },
                }
            )
            # initialize 응답 뒤 타이머를 무장한다(테스트가 짧게 잡을 수 있도록).
            _arm_death_timer(die_after_ms)
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            _respond({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "tools/list":
            _respond({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = message.get("params") or {}
            name = str(params.get("name"))
            _append_call(name)
            if slow_ms > 0:
                time.sleep(slow_ms / 1000.0)
            result = _result_for(name, dict(params.get("arguments") or {}))
            if mode == "die_on_call":
                # 응답이 클라이언트에 전달될 시간을 준 뒤 죽는다: "응답 유실(즉시 사망)" 과
                # "응답 뒤 죽음(exit 관찰)" 은 서로 다른 사건이고, 여기서 잴 것은 후자다.
                _respond({"jsonrpc": "2.0", "id": request_id, "result": result})
                time.sleep(float(os.environ.get("SSAK_CHILD_EXIT_DELAY_MS", "150") or 150) / 1000.0)
                os._exit(7)
            _respond({"jsonrpc": "2.0", "id": request_id, "result": result})
        elif request_id is not None:
            _respond(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
    _write_spawn_record(mode)
    if mode == "crash_start":
        # initialize 를 받기 전에 죽는다 — 시작 실패 경로(backoff/회로)를 만든다.
        sys.stdout.flush()
        os._exit(3)
    _serve(mode)


if __name__ == "__main__":
    main()
