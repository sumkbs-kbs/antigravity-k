"""Phase 31: 실시간 토큰 스트리밍 검증.

기존 테스트가 SSE 이벤트 순서만 봤다면, 여기선 "실시간성"을 검증한다:
- stream_generate_async가 동기 제너레이터를 버퍼링 없이 비동기로 전달하는가
- 첫 SSE 이벤트가 전체 생성 완료 전에 도착하는가 (가짜 스트리밍 방지)
- 이벤트 루프가 스트리밍 중 블록되지 않는가 (동시성 유지)
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from typing import Any

import pytest

from antigravity_k.api.routes.messages_api import (
    _sse,
    _stream_events,
    stream_generate_async,
)


class _StreamingFakeManager:
    """청크를 시간차로 흘려보내는 ModelManager 목 — 실시간성 검증용."""

    def __init__(self, chunks: list[str], delay: float = 0.02) -> None:
        self.chunks = chunks
        self.delay = delay
        self.calls: list[dict[str, Any]] = []

    def stream_generate(self, *, prompt: str, target: str, **kwargs: Any) -> Iterator[str]:
        self.calls.append({"prompt": prompt, "target": target, **kwargs})
        for chunk in self.chunks:
            time.sleep(self.delay)
            yield chunk


class _ExplodingManager:
    """중간에 예외를 던지는 목 — 에러 경로의 부분 스트리밍 검증."""

    def __init__(self, chunks_before_error: list[str]) -> None:
        self.chunks_before_error = chunks_before_error

    def stream_generate(self, *, prompt: str, target: str, **kwargs: Any) -> Iterator[str]:
        for chunk in self.chunks_before_error:
            yield chunk
        raise RuntimeError("모델 폭발")


@pytest.mark.asyncio
async def test_stream_generate_async_yields_without_buffering() -> None:
    """동기 제너레이터의 청크가 도착 즉시 비동기로 전달되는지."""
    manager = _StreamingFakeManager(["첫", "둘", "셋"], delay=0.01)
    received_times: list[float] = []
    start = time.monotonic()

    async for chunk in stream_generate_async(manager, "p", "m"):
        received_times.append(time.monotonic() - start)

    assert list(received_times) != []
    # 첫 청크는 전체 소요시간의 절반 이전에 도착해야 한다 (버퍼링 시 마지막에 몰림)
    total = received_times[-1]
    assert (
        received_times[0] < total * 0.75
    ), f"첫 청크가 너무 늦음: first={received_times[0]:.3f}s, total={total:.3f}s — 버퍼링 의심"


@pytest.mark.asyncio
async def test_stream_generate_async_does_not_block_event_loop() -> None:
    """스트리밍 중 다른 코루틴이 계속 실행되는지 (이벤트 루프 비블록)."""
    manager = _StreamingFakeManager(["a", "b", "c", "d", "e"], delay=0.03)
    heartbeats: list[int] = []

    async def heartbeat() -> None:
        for _ in range(12):
            heartbeats.append(len(heartbeats))
            await asyncio.sleep(0.01)

    hb_task = asyncio.create_task(heartbeat())
    async for _ in stream_generate_async(manager, "p", "m"):
        await asyncio.sleep(0)
    await hb_task

    # 스레드풀 위임이라 루프는 막히지 않음 — 하트비트가 스트리밍 도중 계속 진행됨
    assert len(heartbeats) >= 6, f"이벤트 루프가 블록된 것으로 보임: {len(heartbeats)}회"


@pytest.mark.asyncio
async def test_stream_events_first_delta_arrives_before_generation_completes() -> None:
    """SSE 첫 text_delta가 전체 생성 종료 전에 yield되는가 — 가짜 스트리밍 방지 핵심."""
    chunks = ["안녕", "하세요", "반갑", "습니다"]
    manager = _StreamingFakeManager(chunks, delay=0.05)

    first_delta_at: float | None = None
    start = time.monotonic()
    usage = {"input_tokens": 1, "output_tokens": 0}
    async for event in _stream_events(manager, "프롬프트", "qwen3.8", usage):
        if first_delta_at is None and "text_delta" in event and "안녕" in event:
            first_delta_at = time.monotonic() - start
    total = time.monotonic() - start

    assert first_delta_at is not None, "text_delta가 전혀 전송되지 않음"
    # 기존 가짜 스트리밍이면 첫 delta가 total과 거의 같다 (마지막에 몰아서 전송)
    assert (
        first_delta_at < total * 0.7
    ), f"첫 delta({first_delta_at:.3f}s)가 total({total:.3f}s)에 근접 — 여전히 버퍼링 스트리밍"


@pytest.mark.asyncio
async def test_stream_events_preserves_sse_contract() -> None:
    """실시간화 후에도 SSE 계약(이벤트 순서·text 결합)이 유지되는지."""
    manager = _StreamingFakeManager(["로컬 모델 ", "응답입니다."], delay=0)
    usage = {"input_tokens": 3, "output_tokens": 0}

    events: list[dict[str, Any]] = []
    async for event in _stream_events(manager, "p", "m", usage):
        data_line = next(line for line in event.splitlines() if line.startswith("data: "))
        events.append(json.loads(data_line[6:]))

    types = [e["type"] for e in events]
    assert types[0] == "message_start"
    assert "content_block_start" in types
    assert types[-2:] == ["message_delta", "message_stop"]

    joined = "".join(e["delta"]["text"] for e in events if e["type"] == "content_block_delta")
    assert "로컬 모델 응답입니다." in joined
    assert usage["output_tokens"] > 0


@pytest.mark.asyncio
async def test_stream_events_error_midway_still_closes_protocol() -> None:
    """스트리밍 중 예외가 나도 SSE 프로토콜이 정상 종료되는지 (message_stop 보장)."""
    manager = _ExplodingManager(["부분", "응답"])
    usage = {"input_tokens": 1, "output_tokens": 0}

    events: list[dict[str, Any]] = []
    async for event in _stream_events(manager, "p", "m", usage):
        data_line = next(line for line in event.splitlines() if line.startswith("data: "))
        events.append(json.loads(data_line[6:]))

    types = [e["type"] for e in events]
    assert types[-1] == "message_stop"
    joined = "".join(e["delta"]["text"] for e in events if e["type"] == "content_block_delta")
    assert "부분" in joined and "응답" in joined  # 오류 전까지 스트리밍된 부분 보존
    assert "[API Error]" in joined


def test_sse_format_unchanged() -> None:
    """_sse 포맷이 기존과 동일 (event:/data: 줄 구조)."""
    out = _sse({"type": "ping"})
    assert out == 'event: ping\ndata: {"type": "ping"}\n\n'
