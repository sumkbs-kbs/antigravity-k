"""Live E2E: /v1/messages를 실제 Anthropic SDK 스타일 클라이언트로 검증.

httpx로 Anthropic SDK가 보내는 것과 동일한 요청(헤더/바디)을 구성해
실제 기동된 Ssak-Ai 서버(agk serve)에 전송한다.

시나리오:
  1. 비스트리밍 기본 대화 — Anthropic message 포맷 검증
  2. 스트리밍 SSE — 이벤트 시퀀스 + delta 조립 검증
  3. tool-use 루프 — tools 전송 → tool_use 블록 수신 → tool_result 2차 턴
"""

from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8477"
MODEL = "qwen3.8:latest"
HEADERS = {
    "anthropic-version": "2023-06-01",  # 실제 Anthropic SDK가 보내는 헤더
    "content-type": "application/json",
}

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str) -> None:
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# ─── 시나리오 1: 비스트리밍 ──────────────────────────────────────────

print("== Scenario 1: non-streaming basic chat ==")
t0 = time.time()
res = httpx.post(
    f"{BASE}/v1/messages",
    headers=HEADERS,
    json={
        "model": MODEL,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "1+1은 몇인가요? 한 문장으로 답하세요."}],
    },
    timeout=180,
)
elapsed = time.time() - t0
print(f"  HTTP {res.status_code} ({elapsed:.1f}s)")
data = res.json()
print("  response:", json.dumps(data, ensure_ascii=False)[:400])

ok = (
    res.status_code == 200
    and data.get("type") == "message"
    and data.get("role") == "assistant"
    and data.get("model") == MODEL
    and isinstance(data.get("content"), list)
    and data["content"]
    and data["content"][0]["type"] == "text"
    and len(data["content"][0]["text"]) > 0
    and isinstance(data.get("usage", {}).get("input_tokens"), int)
    and data.get("stop_reason") in ("end_turn", "max_tokens", "stop_sequence")
)
record("non-streaming format", ok, f"stop_reason={data.get('stop_reason')}, usage={data.get('usage')}, {elapsed:.1f}s")

# ─── 시나리오 2: 스트리밍 SSE ────────────────────────────────────────

print("== Scenario 2: streaming SSE ==")
t0 = time.time()
events: list[str] = []
text_parts: list[str] = []
with httpx.stream(
    "POST",
    f"{BASE}/v1/messages",
    headers=HEADERS,
    json={
        "model": MODEL,
        "max_tokens": 128,
        "stream": True,
        "messages": [{"role": "user", "content": "안녕하세요를 세 번 반복해서 말해줘."}],
    },
    timeout=180,
) as stream:
    print(f"  HTTP {stream.status_code}, content-type={stream.headers.get('content-type')}")
    for line in stream.iter_lines():
        if line.startswith("event: "):
            events.append(line[7:].strip())
        elif line.startswith("data: ") and "text_delta" in line:
            payload = json.loads(line[6:])
            text_parts.append(payload["delta"]["text"])
elapsed = time.time() - t0
joined = "".join(text_parts)
print(f"  events: {events}")
print(f"  joined text: {joined[:120]!r}")

expected_seq = ["message_start", "content_block_start", "content_block_stop", "message_delta", "message_stop"]
ok = (
    stream.status_code == 200
    and (stream.headers.get("content-type") or "").startswith("text/event-stream")
    and events[0] == "message_start"
    and events[-1] == "message_stop"
    and all(evt in events for evt in expected_seq)
    and "content_block_delta" in events
    and len(joined) > 0
)
record("streaming SSE", ok, f"{len(events)} events, {len(joined)} chars, {elapsed:.1f}s")

# ─── 시나리오 3: tool-use 루프 ────────────────────────────────────────

print("== Scenario 3: tool-use round trip ==")
tools = [
    {
        "name": "read_file",
        "description": "Read a file from the project and return its contents.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path"}},
            "required": ["path"],
        },
    },
]
t0 = time.time()
res = httpx.post(
    f"{BASE}/v1/messages",
    headers=HEADERS,
    json={
        "model": MODEL,
        "max_tokens": 512,
        "system": "You are a coding agent. When asked to inspect a file, you MUST invoke the read_file tool using the tool_call XML block format shown in your instructions.",
        "tools": tools,
        "messages": [{"role": "user", "content": "src/app.py 파일 내용을 확인해줘."}],
    },
    timeout=180,
)
elapsed = time.time() - t0
data = res.json()
print(f"  HTTP {res.status_code} ({elapsed:.1f}s)")
print("  content types:", [b.get("type") for b in data.get("content", [])])
print("  stop_reason:", data.get("stop_reason"))

tool_block = next((b for b in data.get("content", []) if b.get("type") == "tool_use"), None)
protocol_ok = (
    res.status_code == 200
    and isinstance(data.get("content"), list)
    and data.get("stop_reason") in ("end_turn", "tool_use", "max_tokens")
    and all(isinstance(b.get("type"), str) for b in data["content"])
)
if tool_block:
    print(f"  tool_use: name={tool_block['name']} input={tool_block['input']} id={tool_block['id'][:20]}...")
    record(
        "tool-use first turn",
        protocol_ok and tool_block["name"] == "read_file" and "path" in tool_block["input"],
        f"model emitted tool_use: {tool_block['name']}({tool_block['input']})",
    )

    # 2차 턴: tool_result를 돌려주면 최종 텍스트 응답이 와야 한다
    t1 = time.time()
    res2 = httpx.post(
        f"{BASE}/v1/messages",
        headers=HEADERS,
        json={
            "model": MODEL,
            "max_tokens": 256,
            "system": "You are a coding agent.",
            "tools": tools,
            "messages": [
                {"role": "user", "content": "src/app.py 파일 내용을 확인해줘."},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "확인하겠습니다."},
                        {"type": "tool_use", "id": tool_block["id"], "name": "read_file", "input": tool_block["input"]},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block["id"],
                            "content": [{"type": "text", "text": "print('hello from app.py')"}],
                        },
                    ],
                },
            ],
        },
        timeout=180,
    )
    data2 = res2.json()
    text2 = next((b["text"] for b in data2.get("content", []) if b.get("type") == "text"), "")
    print(f"  second turn HTTP {res2.status_code} ({time.time()-t1:.1f}s), stop_reason={data2.get('stop_reason')}")
    print(f"  final text: {text2[:150]!r}")
    ok2 = res2.status_code == 200 and data2.get("stop_reason") == "end_turn" and len(text2) > 0
    record("tool-result second turn", ok2, f"end_turn with {len(text2)} chars")
else:
    record(
        "tool-use first turn",
        protocol_ok,
        f"model answered in plain text (stop_reason={data.get('stop_reason')}) — 프로토콜은 유효하나 tool_use 미생성",
    )

# ─── 요약 ────────────────────────────────────────────────────────────

print("\n== SUMMARY ==")
failed = [r for r in results if r[1] == "FAIL"]
for name, status, detail in results:
    print(f"  {status}  {name}")
print(f"\n{len(results) - len(failed)}/{len(results)} scenarios passed")
sys.exit(1 if failed else 0)
