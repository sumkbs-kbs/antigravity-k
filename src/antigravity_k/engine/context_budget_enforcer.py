from __future__ import annotations

import re
from collections.abc import Callable
from typing import Final

Message = dict[str, str]
TokenEstimator = Callable[[str], int]

_COMPACTION_MARKER: Final = "\n...[context compacted]...\n"
_MIN_CONTENT_TOKENS: Final = 12
# 도구 호출 블록 — 가운데 자르면 깨진 JSON이 히스토리로 재주입되어
# 파서를 오염시킨다. 압축 시 블록 단위로만 제거한다.
_TOOL_CALL_BLOCK_RE: Final[re.Pattern[str]] = re.compile(
    r"<(tool_call|action_call)>.*?</\1>",
    re.DOTALL,
)


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
        drop_index = _next_drop_index(fitted)
        dropped = fitted[drop_index]
        del fitted[drop_index]
        # 페어링 인식 드롭 — assistant의 <tool_call>과 그 결과는 함께
        # 사라져야 한다. 한쪽만 남으면 고아 호출/고아 결과가 히스토리로
        # 재주입되어 모델과 파서를 오염시킨다.
        pair: int | None = None
        if _is_tool_result_message(dropped):
            # 결과를 버렸다 → 직전 assistant 도구 호출도 버린다
            if drop_index > 0 and _contains_tool_call(fitted[drop_index - 1]):
                pair = drop_index - 1
        elif _contains_tool_call(dropped):
            # 호출을 버렸다 → 직후 결과 메시지도 버린다
            if drop_index < len(fitted) and _is_tool_result_message(fitted[drop_index]):
                pair = drop_index
        if pair is not None and len(fitted) > 1:
            del fitted[pair]
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

    # 도구 호출 블록을 먼저 통째로 제거한다 — 이진 탐색 head/tail 절단은
    # <tool_call> JSON 중간을 자를 수 있고, 깨진 호출 마크업은 다음
    # 스텝에서 모델/파서를 오염시킨다.
    while True:
        match = _TOOL_CALL_BLOCK_RE.search(text)
        if match is None:
            break
        text = text[: match.start()] + text[match.end():]
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
        # 순수 도구 호출 래퍼는 trim 대상에서 제외한다 — 블록 제거가 유일한
        # 축소 경로라 호출이 빈 껍데기가 되어 고아 결과를 남긴다.
        # 페어 통째 드롭이 drop 단계에서 처리한다.
        and not _is_pure_tool_call_wrapper(message)
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
    # [TOOL_EVIDENCE]는 tool_loop가 실제로 생성하는 증거 봉투 마커다.
    # (이전 버전은 존재하지 않는 "VERIFIED_RESULT=" 마커를 검사해
    # 최상위 보호가 사실상 데드 코드였다.)
    if "[TOOL_EVIDENCE]" in content:
        return 5
    if index == latest_user:
        return 4
    role = message.get("role", "")
    return {"assistant": 0, "tool": 1, "user": 2, "system": 3}.get(role, 0)


def _total_tokens(messages: list[Message], estimate_tokens: TokenEstimator) -> int:
    return sum(estimate_tokens(message.get("content", "")) for message in messages)


_TOOL_CALL_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<(tool_call|action_call)>")
_TOOL_RESULT_RE: Final[re.Pattern[str]] = re.compile(r"<tool_response>|<tool_result>|\[TOOL_EVIDENCE\]")


def _contains_tool_call(message: Message) -> bool:
    """assistant 메시지가 도구 호출 마크업을 포함하는지."""
    return bool(_TOOL_CALL_TAG_RE.search(message.get("content", "")))


def _is_tool_result_message(message: Message) -> bool:
    """메시지가 도구 실행 결과(페어링된 호출의 응답)인지."""
    role = message.get("role", "")
    if role in ("tool", "function", "tool_result"):
        return True
    return bool(_TOOL_RESULT_RE.search(message.get("content", "")))


def _is_pure_tool_call_wrapper(message: Message) -> bool:
    """메시지가 (거의) 도구 호출 블록만으로 구성됐는지.

    호출 블록 제거 시 남는 텍스트가 절반 미만이면 순수 래퍼로 본다 —
    trim이 이런 메시지를 빈 껍데기로 만들지 못하게 한다.
    """
    content = message.get("content", "")
    if not _contains_tool_call(message):
        return False
    stripped = _TOOL_CALL_BLOCK_RE.sub("", content)
    return len(stripped.strip()) < len(content) * 0.5
