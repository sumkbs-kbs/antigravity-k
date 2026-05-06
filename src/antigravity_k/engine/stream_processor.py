"""
Antigravity-K: 스트림 후처리 엔진 (StreamProcessor)
=====================================================
LLM 스트리밍 출력의 실시간 정제를 담당합니다.

책임:
  1. <thought>...</thought> 블록 감지 → UI 렌더링 변환
  2. 내부 태그 (%%THINK_END%%, <algorithm>) 필터링
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
    r"%%THINK_END%%|</?algorithm>|📋 Copy|</?scratch_pad>|</?output_code>",
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

        # Step 0: <scratch_pad> 블록 억제 (내부 계획 유출 방지)
        output_parts = []
        remaining = text
        while remaining:
            if self._state.in_scratch_pad:
                end_idx = remaining.lower().find("</scratch_pad>")
                if end_idx != -1:
                    # 블록 종료 — 내용 전체 버림
                    remaining = remaining[end_idx + len("</scratch_pad>") :]
                    self._state.in_scratch_pad = False
                else:
                    # 아직 블록 안에 있음 — 전부 버림
                    remaining = ""
            else:
                start_idx = remaining.lower().find("<scratch_pad>")
                if start_idx != -1:
                    # 블록 시작 전 텍스트는 보존
                    output_parts.append(remaining[:start_idx])
                    remaining = remaining[start_idx + len("<scratch_pad>") :]
                    self._state.in_scratch_pad = True
                else:
                    output_parts.append(remaining)
                    remaining = ""
        text = "".join(output_parts)
        if not text:
            return "", False

        # Step 1: <thought>/<think> 블록 변환
        output = self._process_thought_blocks(text)

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
        """<thought>/<think> 블록을 UI-friendly 형태로 변환합니다."""
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
                    output += text[i:end_idx] + "\n\n--- *End of Thinking* ---\n\n"
                    i = end_idx + tag_len
                    self._state.in_think_block = False
                else:
                    output += text[i:]
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
                    output += text[i:start_idx] + "\n\n--- *Thinking Process* ---\n\n"
                    i = start_idx + tag_len
                    self._state.in_think_block = True
                else:
                    output += text[i:]
                    break
        return output

    def process_flush_text(self, text: str) -> str:
        """flush 시점의 텍스트를 정제합니다 (thought 블록 제거 + 태그 정제)."""
        # thought 블록 완전 제거 (flush 시점에는 보여줄 필요 없음)
        cleaned = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
        if "<thought>" in cleaned:
            cleaned = cleaned[: cleaned.index("<thought>")]

        cleaned = _INTERNAL_TAG_RE.sub("", cleaned)
        cleaned = _CJK_CLEANUP_RE.sub("", cleaned)

        return cleaned if cleaned.strip() else ""

    def reset(self):
        """새 step을 위해 상태를 리셋합니다."""
        self._state = StreamState()

    @property
    def is_in_think_block(self) -> bool:
        return self._state.in_think_block

    @property
    def repetition_detected(self) -> bool:
        return self._state.repetition_detected
