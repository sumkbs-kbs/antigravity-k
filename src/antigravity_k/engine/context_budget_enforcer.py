from __future__ import annotations

from collections.abc import Callable
from typing import Final

Message = dict[str, str]
TokenEstimator = Callable[[str], int]

_COMPACTION_MARKER: Final = "\n...[context compacted]...\n"
_MIN_CONTENT_TOKENS: Final = 12


def enforce_context_budget(
    messages: list[Message],
    token_budget: int,
    estimate_tokens: TokenEstimator,
) -> list[Message]:
    fitted = [dict(message) for message in messages]
    total = _total_tokens(fitted, estimate_tokens)
    if total <= token_budget:
        return messages

    while total > token_budget:
        index = _next_trim_index(fitted, estimate_tokens)
        if index is None:
            break
        content = fitted[index].get("content", "")
        current = estimate_tokens(content)
        target = max(_MIN_CONTENT_TOKENS, current - (total - token_budget))
        compacted = compact_text_to_budget(content, target, estimate_tokens)
        if estimate_tokens(compacted) >= current:
            compacted = compact_text_to_budget(content, current - 1, estimate_tokens)
        fitted[index]["content"] = compacted
        total = _total_tokens(fitted, estimate_tokens)

    while total > token_budget and len(fitted) > 1:
        del fitted[_next_drop_index(fitted)]
        total = _total_tokens(fitted, estimate_tokens)

    if total > token_budget and fitted:
        content = fitted[0].get("content", "")
        target = max(1, estimate_tokens(content) - (total - token_budget))
        fitted[0]["content"] = compact_text_to_budget(content, target, estimate_tokens)
    return fitted


def compact_text_to_budget(
    text: str,
    token_budget: int,
    estimate_tokens: TokenEstimator,
) -> str:
    if estimate_tokens(text) <= token_budget:
        return text

    best = ""
    lower = 0
    upper = len(text)
    while lower <= upper:
        retained = (lower + upper) // 2
        candidate = _head_tail(text, retained)
        if estimate_tokens(candidate) <= token_budget:
            best = candidate
            lower = retained + 1
        else:
            upper = retained - 1
    return best


def _head_tail(text: str, retained: int) -> str:
    if retained <= 0:
        return ""
    if retained >= len(text):
        return text
    head_chars = (retained + 1) // 2
    tail_chars = retained // 2
    tail = text[-tail_chars:] if tail_chars else text[-1:]
    return f"{text[:head_chars]}{_COMPACTION_MARKER}{tail}"


def _next_trim_index(messages: list[Message], estimate_tokens: TokenEstimator) -> int | None:
    latest_user = _latest_user_index(messages)
    candidates = [
        index
        for index, message in enumerate(messages)
        if estimate_tokens(message.get("content", "")) > _MIN_CONTENT_TOKENS
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda index: (
            _protection_rank(messages[index], index, latest_user),
            -estimate_tokens(messages[index].get("content", "")),
            index,
        ),
    )


def _next_drop_index(messages: list[Message]) -> int:
    latest_user = _latest_user_index(messages)
    candidates = [index for index in range(len(messages)) if index != latest_user]
    if not candidates:
        return 0
    return min(
        candidates,
        key=lambda index: (_protection_rank(messages[index], index, latest_user), index),
    )


def _latest_user_index(messages: list[Message]) -> int:
    return next(
        (index for index in range(len(messages) - 1, -1, -1) if messages[index].get("role") == "user"),
        len(messages) - 1,
    )


def _protection_rank(message: Message, index: int, latest_user: int) -> int:
    content = message.get("content", "")
    if "[TOOL_EVIDENCE]" in content and "VERIFIED_RESULT=" in content:
        return 5
    if index == latest_user:
        return 4
    role = message.get("role", "")
    return {"assistant": 0, "tool": 1, "user": 2, "system": 3}.get(role, 0)


def _total_tokens(messages: list[Message], estimate_tokens: TokenEstimator) -> int:
    return sum(estimate_tokens(message.get("content", "")) for message in messages)
