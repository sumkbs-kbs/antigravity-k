"""
Antigravity-K: 도구 호출 파서 (ToolCallParser)
==============================================
스트리밍 LLM 출력에서 <tool_call>...</tool_call> 블록을 
상태머신(State Machine) 방식으로 안정적으로 감지합니다.
"""
import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    TEXT = "TEXT"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_COMPLETE = "TOOL_CALL_COMPLETE"
    TOOL_CALL_ERROR = "TOOL_CALL_ERROR"
    TOOL_CALL = "TOOL_CALL"
    DONE = "DONE"
    ERROR = "ERROR"


@dataclass
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ParseEvent:
    type: EventType
    data: str = ""
    raw_json: str = ""
    tool_call: Optional[ToolCall] = None


class ToolCallParser:
    """
    스트리밍 청크를 feed()로 받아 <tool_call>...</tool_call> 블록을 감지합니다.
    
    사용법:
        parser = ToolCallParser()
        for chunk in stream:
            for event in parser.feed(chunk):
                if event.type == EventType.TEXT:
                    print(event.data)
                elif event.type == EventType.TOOL_CALL_COMPLETE:
                    execute(event.tool_call)
        for event in parser.flush():
            ...
    """

    OPEN_TAG = "<tool_call>"
    CLOSE_TAG = "</tool_call>"

    def __init__(self):
        self._buffer = ""
        self._in_tool_call = False
        self._tool_buffer = ""
        self.tool_responses: List[str] = []  # I-10: 명시적 초기화 (hasattr 패턴 제거)

    def feed(self, chunk: str) -> List[ParseEvent]:
        """청크를 받아 이벤트 리스트를 반환합니다."""
        events: List[ParseEvent] = []
        self._buffer += chunk

        while self._buffer:
            if self._in_tool_call:
                # </tool_call> 종료 태그 탐색
                close_idx = self._buffer.find(self.CLOSE_TAG)
                if close_idx == -1:
                    # 아직 종료 태그가 없으므로 전부 tool_buffer에 축적
                    self._tool_buffer += self._buffer
                    self._buffer = ""
                else:
                    # 종료 태그 발견
                    self._tool_buffer += self._buffer[:close_idx]
                    self._buffer = self._buffer[close_idx + len(self.CLOSE_TAG):]
                    self._in_tool_call = False

                    # JSON 파싱 시도
                    raw = self._tool_buffer.strip()
                    self._tool_buffer = ""

                    try:
                        parsed = json.loads(raw)
                        tc = ToolCall(
                            name=parsed.get("name", parsed.get("tool", "")),
                            arguments=parsed.get("arguments", parsed.get("params", {}))
                        )
                        events.append(ParseEvent(
                            type=EventType.TOOL_CALL_COMPLETE,
                            raw_json=raw,
                            tool_call=tc
                        ))
                    except json.JSONDecodeError as e:
                        events.append(ParseEvent(
                            type=EventType.TOOL_CALL_ERROR,
                            data=f"JSON parse error: {e} | raw: {raw[:200]}"
                        ))
            else:
                # <tool_call> 시작 태그 탐색
                open_idx = self._buffer.find(self.OPEN_TAG)
                if open_idx == -1:
                    # 태그 없음 → 전부 텍스트로 emit
                    # 단, 부분 매치 가능성을 위해 마지막 len(OPEN_TAG)-1 글자는 보류
                    safe_len = len(self._buffer) - (len(self.OPEN_TAG) - 1)
                    if safe_len > 0:
                        events.append(ParseEvent(
                            type=EventType.TEXT,
                            data=self._buffer[:safe_len]
                        ))
                        self._buffer = self._buffer[safe_len:]
                    break  # 더 이상 처리할 것 없음
                else:
                    # 태그 전까지의 텍스트를 emit
                    if open_idx > 0:
                        events.append(ParseEvent(
                            type=EventType.TEXT,
                            data=self._buffer[:open_idx]
                        ))
                    self._buffer = self._buffer[open_idx + len(self.OPEN_TAG):]
                    self._in_tool_call = True
                    self._tool_buffer = ""
                    events.append(ParseEvent(type=EventType.TOOL_CALL_START))

        return events

    def flush(self) -> List[ParseEvent]:
        """스트림 종료 시 남은 버퍼를 처리합니다."""
        events: List[ParseEvent] = []

        if self._in_tool_call:
            # 닫히지 않은 tool_call 블록
            remaining = self._tool_buffer + self._buffer
            events.append(ParseEvent(
                type=EventType.TOOL_CALL_ERROR,
                data=f"Unclosed tool_call block: {remaining[:200]}"
            ))
        elif self._buffer:
            # 남은 일반 텍스트
            events.append(ParseEvent(
                type=EventType.TEXT,
                data=self._buffer
            ))

        self._buffer = ""
        self._tool_buffer = ""
        self._in_tool_call = False

        return events
