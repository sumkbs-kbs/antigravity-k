"""Deterministic conversation summaries with structured tool-evidence retention."""

from __future__ import annotations

import logging
from collections.abc import Callable

from antigravity_k.engine.tool_evidence_compactor import compact_structured_tool_response

Message = dict[str, str]
Summarizer = Callable[[str], str]

logger = logging.getLogger("antigravity_k.context_summary")


def summarize_messages(old_messages: list[Message], summarize_fn: Summarizer | None) -> str:
    """Summarize old messages without replacing verifiable tool evidence with prose."""
    if not old_messages:
        return ""

    preserved_evidence = [
        compacted
        for message in old_messages
        if (compacted := compact_structured_tool_response(message.get("content", ""))) is not None
    ][-5:]
    if summarize_fn is not None:
        prompt = _summary_prompt(old_messages)
        try:
            summary = summarize_fn(prompt)
            if summary and len(summary.strip()) > 20:
                sections = [f"[대화 요약 — {len(old_messages)}개 메시지 압축]", summary.strip()]
                sections.extend(preserved_evidence)
                return "\n".join(sections)
        except Exception:
            logger.exception("[Compressor] LLM summarization failed")

    key_messages = [
        f"[{message.get('role', '')}]: {message.get('content', '')[:100]}"
        for message in old_messages
        if message.get("role") in ("user", "tool")
        and message.get("content", "")
        and compact_structured_tool_response(message.get("content", "")) is None
    ]
    if preserved_evidence:
        return "\n".join(preserved_evidence)
    if key_messages:
        return "\n".join([f"[대화 요약 — {len(old_messages)}개 메시지 압축]", *key_messages[:5]])
    return f"[System Note: {len(old_messages)} older messages were pruned for context efficiency. The agent has already explored previous steps.]"


def _summary_prompt(messages: list[Message]) -> str:
    combined = "\n".join(f"[{message.get('role', '?')}]: {message.get('content', '')[:200]}" for message in messages)
    instruction = "아래 대화 기록을 3줄 이내로 핵심만 요약해주세요. "
    instruction += "특히 사용자의 결정사항, 아키텍처 선택, 변경된 파일을 포함하세요.\n\n"
    return instruction + combined[:2000]
