"""테스트용 stdio MCP 서버 — 구조화 결과·미디어·스키마 위반 계약을 **실제 child** 로 검증한다.

`MCPTool.execute` 는 MCP `CallToolResult` 의 `isError`/`structuredContent`/image·resource
블록을 보존해야 한다. 이 계약은 SDK 를 거친 실제 프로토콜 경계에서만 드러나므로, 여기서
JSON-RPC(줄 단위) stdio 서버를 직접 띄워 쓴다. 표준 라이브러리만 사용한다.

도구 목록(각각 계약의 한 축):
  - ``plain_text``: 평문 텍스트만 — 원문 보존(가공·변형 금지)
  - ``structured``: structuredContent + partial 표시 — 구조 보존 + partial 탐지
  - ``media``: image / embedded resource(text·blob) / resource_link — 비텍스트 보존
  - ``erroring``: isError=true + 오류 봉투 — 성공 변환 금지
  - ``bad_schema``: inputSchema type 이 object 가 아님 — 로더가 등록을 거부해야 한다
  - ``bad_required``: inputSchema 의 required 가 문자열 목록이 아님 — 같은 이유로 거부

(Raw `inputSchema` 누락은 이 child 로 만들 수 없다 — MCP **SDK** 가 `ListToolsResult`
파싱 단계에서 거부해 tools/list 자체가 실패한다. 그 경로는 로더 단위 시험이 담당한다.)
"""

from __future__ import annotations

import json
import sys

# 1x1 투명 PNG (base64) — 미디어 블록 보존 확인용 최소 페이로드
TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

TOOLS: list[dict[str, object]] = [
    {
        "name": "plain_text",
        "description": "평문 텍스트만 돌려준다",
        "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
    },
    {
        "name": "structured",
        "description": "structuredContent 와 partial 표시를 함께 돌려준다",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "media",
        "description": "이미지·임베디드 리소스·리소스 링크를 함께 돌려준다",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "erroring",
        "description": "isError=true 오류 봉투를 돌려준다",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "bad_schema",
        "description": "inputSchema 가 객체가 아닌 도구(스키마 위반)",
        "inputSchema": {"type": "string"},
    },
    {
        "name": "bad_required",
        "description": "required 가 문자열 목록이 아닌 도구(스키마 위반)",
        "inputSchema": {"type": "object", "properties": {}, "required": "q"},
    },
]


def _result_for(name: str) -> dict[str, object]:
    if name == "plain_text":
        return {"content": [{"type": "text", "text": "plain payload — 그대로 보존되어야 한다"}]}

    if name == "structured":
        payload = {"status": "partial", "partial": True, "results": [{"title": "a"}, {"title": "b"}]}
        return {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "structuredContent": payload,
        }

    if name == "media":
        return {
            "content": [
                {"type": "text", "text": "media bundle"},
                {"type": "image", "data": TINY_PNG_B64, "mimeType": "image/png"},
                {
                    "type": "resource",
                    "resource": {"uri": "fixture://note.txt", "mimeType": "text/plain", "text": "임베디드 리소스 본문"},
                },
                {
                    "type": "resource",
                    "resource": {
                        "uri": "fixture://blob.bin",
                        "mimeType": "application/octet-stream",
                        "blob": "AAECAwQ=",
                    },
                },
                {"type": "resource_link", "uri": "fixture://linked.txt", "name": "linked", "mimeType": "text/plain"},
            ]
        }

    if name == "erroring":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": {
                                "code": "INVALID_TOOL_ARGS",
                                "detail": "fixture: 강제 오류",
                                "retryable": True,
                            }
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            "isError": True,
        }

    return {
        "content": [
            {"type": "text", "text": json.dumps({"error": {"code": "UNKNOWN_TOOL", "detail": f"unknown: {name}"}})}
        ],
        "isError": True,
    }


def _respond(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
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
                        "serverInfo": {"name": "ssak-structured-fixture", "version": "1.0.0"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _respond({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = message.get("params") or {}
            _respond({"jsonrpc": "2.0", "id": request_id, "result": _result_for(str(params.get("name")))})
        elif request_id is not None:
            _respond(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )


if __name__ == "__main__":
    main()
