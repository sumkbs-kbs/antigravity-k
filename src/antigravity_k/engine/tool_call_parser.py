"""Antigravity-K: 도구 호출 파서 (ToolCallParser).

==============================================
스트리밍 LLM 출력에서 <tool_call>...</tool_call> 블록을
상태머신(State Machine) 방식으로 안정적으로 감지합니다.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Eventtype.

    Bases: Enum
    """

    TEXT = "TEXT"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_COMPLETE = "TOOL_CALL_COMPLETE"
    TOOL_CALL_ERROR = "TOOL_CALL_ERROR"
    TOOL_CALL = "TOOL_CALL"
    DONE = "DONE"
    ERROR = "ERROR"


@dataclass
class ToolCall:
    """Toolcall."""

    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ParseEvent:
    """Parseevent."""

    type: EventType
    data: str = ""
    raw_json: str = ""
    tool_call: ToolCall | None = None


class ToolCallParser:
    """스트리밍 청크를 feed()로 받아 <action_call>...</action_call> 블록을 감지합니다.

    핵심 설계:
        - <thought>...</thought> 블록 내부에서는 <action_call> 감지를 비활성화합니다.
          LLM이 사고 과정에서 태그 이름을 평문으로 언급해도 가짜 도구 호출로 오인하지 않습니다.

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

    OPEN_TAGS = ["<action_call>", "<tool_call>"]
    CLOSE_TAGS = ["</action_call>", "</tool_call>"]
    THOUGHT_OPEN = "<thought>"
    THOUGHT_CLOSE = "</thought>"

    def __init__(self):
        """Initialize the ToolCallParser."""
        self._buffer = ""
        self._in_tool_call = False
        self._current_close_tag = ""
        self._in_thought = False  # <thought> 블록 추적
        self._tool_buffer = ""
        self.tool_responses: list[str] = []  # I-10: 명시적 초기화 (hasattr 패턴 제거)

    def feed(self, chunk: str) -> list[ParseEvent]:
        """청크를 받아 이벤트 리스트를 반환합니다."""
        events: list[ParseEvent] = []
        self._buffer += chunk

        while self._buffer:
            if self._in_tool_call:
                close_idx = self._buffer.find(self._current_close_tag)
                if close_idx == -1:
                    # 종료 태그가 잘려 들어올 수 있으므로 마지막 len(CLOSE_TAG)-1 글자는 보류
                    safe_len = len(self._buffer) - (len(self._current_close_tag) - 1)
                    if safe_len > 0:
                        self._tool_buffer += self._buffer[:safe_len]
                        self._buffer = self._buffer[safe_len:]
                    break
                else:
                    # 종료 태그 발견
                    self._tool_buffer += self._buffer[:close_idx]
                    self._buffer = self._buffer[close_idx + len(self._current_close_tag) :]
                    self._in_tool_call = False

                    # JSON 파싱 시도
                    raw = self._tool_buffer.strip()
                    self._tool_buffer = ""

                    # LLM이 <action_call> 태그 내부에 평문을 섞어 쓸 경우를 대비해 JSON 블록만 추출

                    json_raw = raw
                    json_match = re.search(r"(\{.*\})", raw, re.DOTALL)
                    if json_match:
                        json_raw = json_match.group(1)

                    try:
                        parsed = json.loads(json_raw)
                        tc = ToolCall(
                            name=parsed.get("name", parsed.get("tool", "")),
                            arguments=parsed.get("arguments", parsed.get("params", {})),
                        )
                        events.append(
                            ParseEvent(
                                type=EventType.TOOL_CALL_COMPLETE,
                                raw_json=raw,
                                tool_call=tc,
                            ),
                        )
                    except json.JSONDecodeError as e:
                        events.append(
                            ParseEvent(
                                type=EventType.TOOL_CALL_ERROR,
                                data=f"JSON parse error: {e} | raw: {raw[:200]}",
                            ),
                        )

            elif self._in_thought:
                # ── <thought> 블록 내부: </thought> 만 찾고, <action_call> 은 무시 ──
                thought_close_idx = self._buffer.find(self.THOUGHT_CLOSE)
                if thought_close_idx == -1:
                    # </thought> 가 아직 안 왔음 → 전체를 텍스트로 emit (보류분 제외)
                    safe_len = len(self._buffer) - (len(self.THOUGHT_CLOSE) - 1)
                    if safe_len > 0:
                        events.append(ParseEvent(type=EventType.TEXT, data=self._buffer[:safe_len]))
                        self._buffer = self._buffer[safe_len:]
                    break
                else:
                    # </thought> 발견 → thought 블록 종료
                    end_pos = thought_close_idx + len(self.THOUGHT_CLOSE)
                    events.append(ParseEvent(type=EventType.TEXT, data=self._buffer[:end_pos]))
                    self._buffer = self._buffer[end_pos:]
                    self._in_thought = False

            else:
                # ── 일반 모드: <action_call>, <tool_call> 과 <thought> 중 먼저 오는 것을 탐색 ──
                open_idx = -1
                found_tag = ""
                for tag in self.OPEN_TAGS:
                    idx = self._buffer.find(tag)
                    if idx != -1:
                        if open_idx == -1 or idx < open_idx:
                            open_idx = idx
                            found_tag = tag

                thought_idx = self._buffer.find(self.THOUGHT_OPEN)

                # 둘 다 없는 경우
                if open_idx == -1 and thought_idx == -1:
                    # 평문 JSON 툴콜 시작점 감지
                    bare_start = self._buffer.find('{"name"')

                    if bare_start != -1:
                        # 툴콜 이전의 텍스트는 방출
                        if bare_start > 0:
                            events.append(
                                ParseEvent(type=EventType.TEXT, data=self._buffer[:bare_start]),
                            )
                            self._buffer = self._buffer[bare_start:]

                        # 완전한 툴콜인지 확인
                        bare_json_events, consumed_len = self._detect_bare_tool_call_streaming(
                            self._buffer,
                        )
                        if bare_json_events:
                            events.extend(bare_json_events)
                            self._buffer = self._buffer[consumed_len:]
                            continue  # 처리 후 다시 루프
                        else:
                            # 불완전하면 더 이상 방출하지 않고 보류
                            break

                    # 부분 매치 가능성을 위해 마지막 max(OPEN_TAG, THOUGHT_OPEN)-1 글자는 보류
                    max_tag_len = max(max((len(t) for t in self.OPEN_TAGS)), len(self.THOUGHT_OPEN))
                    # {"name" 도 부분 매치될 수 있으므로 보류 길이에 고려 (7글자)
                    safe_len = len(self._buffer) - max(max_tag_len - 1, 6)
                    if safe_len > 0:
                        events.append(ParseEvent(type=EventType.TEXT, data=self._buffer[:safe_len]))
                        self._buffer = self._buffer[safe_len:]
                    break

                # 어느 것이 먼저인지 결정 (-1은 무한대로 취급)
                effective_open = open_idx if open_idx != -1 else float("inf")
                effective_thought = thought_idx if thought_idx != -1 else float("inf")

                if effective_thought < effective_open:
                    # <thought> 가 먼저 → thought 모드 진입
                    tag_start = thought_idx
                    tag_end = tag_start + len(self.THOUGHT_OPEN)
                    if tag_start > 0:
                        events.append(
                            ParseEvent(type=EventType.TEXT, data=self._buffer[:tag_start]),
                        )
                    # <thought> 태그 자체도 텍스트로 emit (오케스트레이터가 처리)
                    events.append(
                        ParseEvent(type=EventType.TEXT, data=self._buffer[tag_start:tag_end]),
                    )
                    self._buffer = self._buffer[tag_end:]
                    self._in_thought = True
                else:
                    # <action_call> 또는 <tool_call> 이 먼저 → 도구 호출 모드 진입
                    if open_idx > 0:
                        events.append(ParseEvent(type=EventType.TEXT, data=self._buffer[:open_idx]))
                    self._buffer = self._buffer[open_idx + len(found_tag) :]
                    self._in_tool_call = True
                    self._current_close_tag = "</action_call>" if found_tag == "<action_call>" else "</tool_call>"
                    self._tool_buffer = ""
                    events.append(ParseEvent(type=EventType.TOOL_CALL_START))

        return events

    def flush(self) -> list[ParseEvent]:
        """스트림 종료 시 남은 버퍼를 처리합니다."""
        events: list[ParseEvent] = []

        if self._in_tool_call:
            # 닫히지 않은 tool_call 블록
            remaining = self._tool_buffer + self._buffer
            events.append(
                ParseEvent(
                    type=EventType.TOOL_CALL_ERROR,
                    data=f"Unclosed tool_call block: {remaining[:200]}",
                ),
            )
        elif self._buffer:
            # 태그 없이 평문 JSON으로 도구 호출을 출력하는 모델 대응
            bare_json = self._detect_bare_tool_call(self._buffer)
            if bare_json:
                events.extend(bare_json)
            else:
                # 남은 일반 텍스트
                events.append(ParseEvent(type=EventType.TEXT, data=self._buffer))

        self._buffer = ""
        self._tool_buffer = ""
        self._in_tool_call = False
        self._in_thought = False

        return events

    def _detect_bare_tool_call(self, text: str) -> list[ParseEvent] | None:
        """<tool_call> 태그 없이 평문 JSON으로 출력된 도구 호출을 감지합니다.

        일부 모델이 <scratch_pad> 후에 태그 없이 {"name": "...", "arguments": {...}} 형태로
        직접 도구 호출을 출력하는 경우를 처리합니다.
        """
        # 패턴: {"name": "...", "arguments": {...}}
        bare_pattern = re.search(
            r'\{"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{.*\})\s*\}',
            text,
            re.DOTALL,
        )
        if not bare_pattern:
            return None

        try:
            full_match = bare_pattern.group(0)
            parsed = json.loads(full_match)
            if "name" in parsed and "arguments" in parsed:
                logger.info("[ToolCallParser] Bare JSON tool call detected: %s", parsed["name"])

                # 도구 호출 전의 텍스트
                pre_text = text[: bare_pattern.start()].strip()
                events = []
                if pre_text:
                    events.append(ParseEvent(type=EventType.TEXT, data=pre_text))

                events.append(ParseEvent(type=EventType.TOOL_CALL_START))
                events.append(
                    ParseEvent(
                        type=EventType.TOOL_CALL_COMPLETE,
                        tool_call=ToolCall(
                            name=parsed["name"],
                            arguments=(
                                parsed["arguments"]
                                if isinstance(parsed["arguments"], dict)
                                else json.loads(parsed["arguments"])
                            ),
                        ),
                    ),
                )

                # 도구 호출 후의 텍스트
                post_text = text[bare_pattern.end() :].strip()
                if post_text:
                    # 후속 텍스트에도 도구 호출이 있을 수 있음 (재귀)
                    more = self._detect_bare_tool_call(post_text)
                    if more:
                        events.extend(more)
                    else:
                        events.append(ParseEvent(type=EventType.TEXT, data=post_text))

                return events
        except (json.JSONDecodeError, KeyError):
            pass

        return None

    def _detect_bare_tool_call_streaming(self, text: str) -> tuple[list[ParseEvent] | None, int]:
        """스트리밍 중 평문 JSON 도구 호출을 감지합니다.

        Returns:
            (events, consumed_len)

        """
        # 현재 버퍼 시작부터 완전한 형태의 평문 도구 호출이 있는지 검사합니다.
        # 주의: 부분적으로 입력 중인 경우(예: {"name": "write_file", "arguments": ...)는 무시하고 보류해야 함
        bare_pattern = re.search(
            r'^\{"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}',
            text,
            re.DOTALL,
        )
        if not bare_pattern:
            return None, 0

        try:
            full_match = bare_pattern.group(0)
            parsed = json.loads(full_match)
            if "name" in parsed and "arguments" in parsed:
                logger.info(
                    "[ToolCallParser] Streaming Bare JSON tool call detected: %s",
                    parsed["name"],
                )

                events = [
                    ParseEvent(type=EventType.TOOL_CALL_START),
                    ParseEvent(
                        type=EventType.TOOL_CALL_COMPLETE,
                        tool_call=ToolCall(
                            name=parsed["name"],
                            arguments=(
                                parsed["arguments"]
                                if isinstance(parsed["arguments"], dict)
                                else json.loads(parsed["arguments"])
                            ),
                        ),
                    ),
                ]
                return events, bare_pattern.end()
        except (json.JSONDecodeError, KeyError):
            pass

        return None, 0
