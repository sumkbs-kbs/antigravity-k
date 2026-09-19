"""검색 증거(출처·부분 수집·상한 초과·오류)를 **실제 child** 로 만드는 stdio MCP fixture.

task 14 의 화면은 번들 응답의 부가 필드를 사용자에게 보여준다(출처 링크·수집시각·부분 수집 경고·
상한 초과). 그 필드들은 **실제 프로토콜 경계**(SDK → `CallToolResult` → 문자열)를 지나야 하므로,
여기서는 표준 라이브러리만으로 JSON-RPC(줄 단위) 서버를 직접 띄우고 W 번들의 `ssak_search` 응답
모양(`AgentSearchResult`)을 그대로 흉내낸다.

시나리오는 env 로 고른다 (``SSAK_EVIDENCE_SCENARIO``):

  - ``ok``        : hits 2건 + ``signal_confidence: HIGH`` + ``took_ms``
  - ``partial``   : ``aborted_backends: ["bing","naver"]`` + ``MEDIUM`` (일부 소스만 수집)
  - ``truncated`` : ``budget`` 동봉(항목 3건 잘림)
  - ``cached``    : ``cached: true`` + ``cache_age_ms`` (수집시각이 과거여야 한다)
  - ``error``     : ``isError: true`` + 오류 봉투(`AUTH_REQUIRED`)
  - ``plain``     : JSON 이 아닌 평문(구조를 못 읽는 응답 → 결과 0건)

사용법::

    python ssak_search_evidence_child.py
"""

from __future__ import annotations

import json
import os
import sys

TOOLS: list[dict[str, object]] = [
    {
        "name": "ssak_search",
        "description": "fixture 검색 — 시나리오별 증거를 돌려준다",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
            "required": ["query"],
        },
    },
]


def _scenario() -> str:
    return os.environ.get("SSAK_EVIDENCE_SCENARIO", "ok").strip() or "ok"


def _hit(title: str, url: str, snippet: str, score: float, source: str) -> dict[str, object]:
    return {"title": title, "url": url, "snippet": snippet, "score": score, "source": source}


def _search_payload() -> dict[str, object]:
    scenario = _scenario()
    if scenario == "partial":
        return {
            "query": "부분 수집",
            "took_ms": 812,
            "hits": [_hit("문서 A", "https://example.test/a", "본문 A", 0.82, "bing")],
            "aborted_backends": ["bing", "naver"],
            "signal_confidence": "MEDIUM",
        }
    if scenario == "truncated":
        return {
            "query": "상한 초과",
            "took_ms": 430,
            "hits": [_hit("문서 B", "https://example.test/b", "본문 B", 0.5, "duckduckgo")],
            "aborted_backends": [],
            "signal_confidence": "HIGH",
            "budget": {"bytes": 262144, "tokens": 9000, "exceeded": "tokens", "trimmed_items": 3},
        }
    if scenario == "cached":
        return {
            "query": "캐시 응답",
            "took_ms": 2,
            "hits": [_hit("문서 C", "https://example.test/c", "본문 C", 0.66, "cache")],
            "aborted_backends": [],
            "signal_confidence": "HIGH",
            "cached": True,
            "cache_age_ms": 900_000,
        }
    return {
        "query": "정상",
        "took_ms": 512,
        "hits": [
            _hit("공식 문서", "https://example.test/official", "공식 본문", 0.93, "searxng"),
            _hit("블로그", "https://blog.example.test/post", "블로그 본문", 0.41, "duckduckgo"),
        ],
        "aborted_backends": [],
        "signal_confidence": "HIGH",
        "decomposed_subqueries": ["정상 하위질의"],
        "phishing_filtered": 1,
    }


def _result_for() -> dict[str, object]:
    scenario = _scenario()
    if scenario == "error":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": {
                                "code": "AUTH_REQUIRED",
                                "detail": "fixture: 검색 백엔드 자격 증명이 필요합니다",
                                "retryable": False,
                            }
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            "isError": True,
        }
    if scenario == "plain":
        return {"content": [{"type": "text", "text": "평문 응답 — 구조를 읽을 수 없다"}]}
    payload = _search_payload()
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


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
                        "serverInfo": {"name": "ssak-evidence-fixture", "version": "1.0.0"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _respond({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            _respond({"jsonrpc": "2.0", "id": request_id, "result": _result_for()})
        elif method == "ping":
            _respond({"jsonrpc": "2.0", "id": request_id, "result": {}})
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
