"""Antigravity-K: CEO 분석 엔진 (CEOAnalyzer).

==========================================
I-1 리팩터링: Orchestrator에서 분리된 CEO 태스크 분류 로직.
LLM 스트리밍으로 사용자 의도를 분석하고, JSON/키워드 폴백으로 task_type/delegate_to를 결정합니다.
"""

import json
import logging
import re
from collections.abc import Generator
from typing import Union

logger = logging.getLogger(__name__)


def ceo_analyze(
    user_message: str,
    target_model: str,
    ceo_prompt_template: str,
    model_manager,
) -> Generator[Union[str, dict], None, None]:
    """CEO가 사용자 메시지를 분석하여 태스크 유형과 위임 대상을 결정합니다.

    스트리밍으로 분석 과정을 출력하며, 마지막에 결과를 dict로 yield합니다.

    Args:
        user_message: 사용자 입력 메시지
        target_model: 지정된 모델 (없으면 기본 모델 사용)
        ceo_prompt_template: CEO 역할 프롬프트 템플릿
        model_manager: ModelManager 인스턴스

    """
    # orchestrator-swarm 또는 target_model 사용
    ceo_model = target_model if target_model and target_model != "default" else "orchestrator-swarm"

    ceo_prompt = f"{ceo_prompt_template}\n\nUser request: {user_message}"

    # 1. Pre-routing (Short-circuit): 단순 인사나 명확한 키워드는 LLM 호출 없이 즉시 우회
    pre_routing_result = _keyword_fallback(user_message, user_message)
    if pre_routing_result and pre_routing_result.get("task_type") == "simple_chat":
        logger.info("CEO Pre-routing: Short-circuited to simple_chat based on keywords.")
        yield pre_routing_result
        return

    try:
        response_text = ""
        # ModelManager의 stream_generate를 사용하여 콤보/단일 모델 라우팅을 자동 처리
        for chunk in model_manager.stream_generate(
            prompt=ceo_prompt,
            target=ceo_model,
            max_tokens=512,
        ):
            response_text += chunk
            yield chunk

        raw_text = response_text

        # JSON 추출 — 3단계 전략
        parsed = _extract_task_json(raw_text)

        if parsed:
            yield parsed
            return

        # 3차: 키워드 기반 폴백 (JSON 파싱 실패 시에만 도달)
        keyword_result = _keyword_fallback(raw_text, user_message)
        if keyword_result:
            yield keyword_result
            return

        logger.warning("CEO analysis: no JSON found in response")
    except Exception as e:
        logger.error("CEO analysis failed: %s", e, exc_info=True)

    # 최종 폴백: 단순 대화로 처리
    yield {
        "task_type": "simple_chat",
        "delegate_to": "SELF",
        "reasoning": "CEO analysis failed, fallback to direct response",
        "refined_prompt": user_message,
    }


def _extract_task_json(raw_text: str) -> dict | None:
    """Raw 텍스트에서 task_type이 포함된 JSON 객체를 추출합니다."""
    # 1차: JSONDecoder.raw_decode — 중첩 {} 처리 가능
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw_text):
        if ch == "{":
            try:
                obj, end_idx = decoder.raw_decode(raw_text, i)
                if isinstance(obj, dict) and "task_type" in obj:
                    logger.info(
                        "CEO Analysis (raw_decode): type=%s, delegate=%s",
                        obj.get("task_type"),
                        obj.get("delegate_to"),
                    )
                    return obj
            except json.JSONDecodeError:
                continue

    # 2차: 정규식 폴백
    json_match = re.search(r'\{[^{}]*"task_type"\s*:\s*"[^"]*"[^{}]*\}', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError as je:
            logger.warning("CEO JSON decode error: %s", je)

    return None


_KEYWORD_MAP = [
    (
        ["안녕", "소개", "누구", "인사", "대화", "얘기", "어떻게", "뭐야"],
        "simple_chat",
        "SELF",
    ),
    (
        ["coding", "code", "function", "함수", "코드", "작성", "파일", "구현"],
        "coding",
        "WORKER",
    ),
    (["review", "리뷰", "검토", "점검"], "review", "QA"),
    (["design", "디자인", "ui", "ux", "레이아웃"], "design", "DESIGNER"),
    (
        ["분석", "analyze", "추론", "reason", "설명", "explain"],
        "reasoning",
        "ENG_MANAGER",
    ),
]


def _keyword_fallback(raw_text: str, user_message: str) -> dict | None:
    """키워드 기반 의도 감지 — JSON 파싱 실패 시 사용."""
    lower = raw_text.lower()
    for keywords, task_type, delegate in _KEYWORD_MAP:
        if any(kw in lower for kw in keywords):
            logger.info("CEO fallback: detected %s from keywords", task_type)
            return {
                "task_type": task_type,
                "delegate_to": delegate,
                "reasoning": "keyword-based detection",
                "refined_prompt": user_message,
            }
    return None
