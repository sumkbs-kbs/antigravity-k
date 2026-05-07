"""
Antigravity-K: 스트림 후처리 엔진 (StreamProcessor)
=====================================================
LLM 스트리밍 출력의 실시간 정제를 담당합니다.

책임:
  1. <thought>/<think> 내부 추론 블록 감지 → 사용자 출력에서 제거
  2. 내부 태그 (%%THINK_START%%/%%THINK_END%%, <algorithm>) 필터링
  3. CJK(중국어) 혼입 제거
  4. 반복 루프 감지 (동일 블록 3회 반복 시 중단)

설계 원칙:
  - orchestrator.py의 460~498줄 로직을 독립 모듈로 추출
  - 순수 함수 + 상태 객체 패턴 → 단위 테스트 가능
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# 사전 컴파일된 정규식 (모듈 수준 — 매 인스턴스 재생성 방지)
_INTERNAL_TAG_RE = re.compile(
    r"%%THINK_START%%|%%THINK_END%%|</?algorithm>|📋 Copy|</?scratch_pad>|</?output_code>",
    re.IGNORECASE,
)
# <scratch_pad>...</scratch_pad> 전체 블록 제거용 (flush 시)
_SCRATCH_PAD_BLOCK_RE = re.compile(
    r"<scratch_pad>.*?</scratch_pad>", re.DOTALL | re.IGNORECASE
)
_CJK_CLEANUP_RE = re.compile(r"[\u4e00-\u9fff]+")


@dataclass
class StreamState:
    """스트리밍 처리의 현재 상태를 캡슐화합니다."""

    in_think_block: bool = False
    in_scratch_pad: bool = False
    seen_blocks: Dict[str, int] = field(default_factory=dict)
    repetition_detected: bool = False


class StreamProcessor:
    """LLM 스트리밍 출력의 실시간 정제 엔진.

    사용법:
        processor = StreamProcessor()
        for chunk in llm_stream:
            output, is_repeat = processor.process_text(chunk)
            if is_repeat:
                break
            if output:
                yield output
    """

    def __init__(self, repetition_threshold: int = 3):
        self._state = StreamState()
        self._repetition_threshold = repetition_threshold
        self._buffer = ""

    def process_text(self, text: str) -> Tuple[str, bool]:
        """텍스트 청크를 정제합니다.

        Args:
            text: LLM에서 온 raw 텍스트 청크

        Returns:
            (processed_output, is_repetition_detected)
            - processed_output: 사용자에게 보여줄 정제된 텍스트
            - is_repetition_detected: True이면 반복 루프 감지 → 루프 중단 필요
        """
        if not text:
            return "", False

        self._buffer += text
        output_parts = []

        while True:
            if self._state.in_scratch_pad:
                end_idx = self._buffer.lower().find("</scratch_pad>")
                if end_idx != -1:
                    # 블록 종료 — 이전 내용은 모두 버림
                    self._buffer = self._buffer[end_idx + len("</scratch_pad>") :]
                    self._state.in_scratch_pad = False
                else:
                    # 아직 종료 안됨. 버퍼의 뒷부분(태그 조각)만 유지
                    last_lt = self._buffer.rfind("<")
                    if last_lt != -1:
                        self._buffer = self._buffer[last_lt:]
                    else:
                        self._buffer = ""
                    break
            else:
                start_idx = self._buffer.lower().find("<scratch_pad>")
                if start_idx != -1:
                    # 시작 태그 앞부분은 방출
                    output_parts.append(self._buffer[:start_idx])
                    self._buffer = self._buffer[start_idx + len("<scratch_pad>") :]
                    self._state.in_scratch_pad = True
                else:
                    # 태그가 잘려있을 수 있으므로 끝에 '<'가 있으면 보류
                    last_lt = self._buffer.rfind("<")
                    tail = self._buffer[last_lt:] if last_lt != -1 else ""
                    if last_lt != -1 and ">" not in tail and len(tail) < 15:
                        # '<' 뒤에 문자가 너무 짧으면 잘린 태그일 수 있음
                        output_parts.append(self._buffer[:last_lt])
                        self._buffer = self._buffer[last_lt:]
                        break
                    else:
                        output_parts.append(self._buffer)
                        self._buffer = ""
                        break

        output_text = "".join(output_parts)
        if not output_text:
            return "", False

        # Step 1: <thought>/<think> 내부 추론 블록 제거
        output = self._process_thought_blocks(output_text)

        if not output:
            return "", False

        # Step 2: 내부 태그 필터링
        output = _INTERNAL_TAG_RE.sub("", output)

        # Step 3: 중국어 혼입 제거
        output = _CJK_CLEANUP_RE.sub("", output)

        # Step 4: 반복 루프 감지
        stripped = output.strip()
        if len(stripped) > 50:
            self._state.seen_blocks[stripped] = (
                self._state.seen_blocks.get(stripped, 0) + 1
            )
            if self._state.seen_blocks[stripped] >= self._repetition_threshold:
                self._state.repetition_detected = True
                logger.warning("Repetition loop detected by StreamProcessor")
                return output, True

        return output if output.strip() else "", False

    def _process_thought_blocks(self, text: str) -> str:
        """<thought>/<think> 블록을 사용자 출력에서 제거합니다."""
        output = ""
        i = 0
        lower_text = text.lower()
        while i < len(text):
            if self._state.in_think_block:
                # </thought> 또는 </think> 종료 태그 탐색
                end_thought = lower_text.find("</thought>", i)
                end_think = lower_text.find("</think>", i)
                # 가장 빠른 종료 태그 선택
                candidates = [
                    (end_thought, len("</thought>")),
                    (end_think, len("</think>")),
                ]
                candidates = [(pos, length) for pos, length in candidates if pos != -1]
                if candidates:
                    end_idx, tag_len = min(candidates, key=lambda x: x[0])
                    i = end_idx + tag_len
                    self._state.in_think_block = False
                else:
                    # 닫는 태그가 올 때까지 내부 추론 내용은 모두 숨깁니다.
                    break
            else:
                # <thought> 또는 <think> 시작 태그 탐색
                start_thought = lower_text.find("<thought>", i)
                start_think = lower_text.find("<think>", i)
                candidates = [
                    (start_thought, len("<thought>")),
                    (start_think, len("<think>")),
                ]
                candidates = [(pos, length) for pos, length in candidates if pos != -1]
                if candidates:
                    start_idx, tag_len = min(candidates, key=lambda x: x[0])
                    output += text[i:start_idx]
                    i = start_idx + tag_len
                    self._state.in_think_block = True
                else:
                    output += text[i:]
                    break
        return output

    def process_flush_text(self, text: str) -> str:
        """flush 시점의 텍스트를 정제합니다 (thought/think 블록 제거 + 태그 정제)."""
        flush_text = self._buffer + text
        self._buffer = ""

        # thought/think 블록 완전 제거 (flush 시점에도 사용자에게 보여주지 않음)
        cleaned = re.sub(
            r"<(?:thought|think)>.*?</(?:thought|think)>",
            "",
            flush_text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        open_match = re.search(r"<(?:thought|think)>", cleaned, flags=re.IGNORECASE)
        if open_match:
            cleaned = cleaned[: open_match.start()]

        cleaned = _INTERNAL_TAG_RE.sub("", cleaned)
        cleaned = _CJK_CLEANUP_RE.sub("", cleaned)

        return cleaned if cleaned.strip() else ""

    def reset(self):
        """새 step을 위해 상태를 리셋합니다."""
        self._state = StreamState()
        self._buffer = ""

    @property
    def is_in_think_block(self) -> bool:
        return self._state.in_think_block

    @property
    def repetition_detected(self) -> bool:
        return self._state.repetition_detected
