"""
Antigravity-K: CEO 분석 엔진 (CEOAnalyzer)
==========================================
I-1 리팩터링: Orchestrator에서 분리된 CEO 태스크 분류 로직.
LLM 스트리밍으로 사용자 의도를 분석하고, JSON/키워드 폴백으로 task_type/delegate_to를 결정합니다.
"""

import json
import re
import logging
import urllib.request
from typing import Generator, Union

logger = logging.getLogger(__name__)


def ceo_analyze(
    user_message: str,
    target_model: str,
    ceo_prompt_template: str,
    get_model_for_role_fn,
) -> Generator[Union[str, dict], None, None]:
    """
    CEO가 사용자 메시지를 분석하여 태스크 유형과 위임 대상을 결정합니다.
    스트리밍으로 분석 과정을 출력하며, 마지막에 결과를 dict로 yield합니다.

    Args:
        user_message: 사용자 입력 메시지
        target_model: 지정된 모델 (없으면 기본 모델 사용)
        ceo_prompt_template: CEO 역할 프롬프트 템플릿
        get_model_for_role_fn: 역할명 → 모델명 매핑 함수

    Yields:
        str: 스트리밍 텍스트 청크
        dict: 최종 분석 결과 (마지막 yield)
    """
    if target_model and target_model != "default":
        ceo_model = target_model
    else:
        ceo_model = get_model_for_role_fn("default")
        if not ceo_model:
            ceo_model = "qwen3.6:latest"

    ceo_prompt = f"{ceo_prompt_template}\n\nUser request: {user_message}"

    try:
        base_url = "http://localhost:11434"
        url = f"{base_url}/api/generate"

        data = {
            "model": ceo_model,
            "prompt": ceo_prompt,
            "stream": True,
            "keep_alive": "30m",
            "options": {"num_predict": 512, "num_ctx": 4096},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        response_text = ""
        with urllib.request.urlopen(req, timeout=300) as resp:
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        delta = chunk["response"]
                        response_text += delta
                        yield delta
                    elif "message" in chunk and "content" in chunk["message"]:
                        delta = chunk["message"]["content"]
                        response_text += delta
                        yield delta
                except json.JSONDecodeError:
                    continue

        raw_text = response_text
        logger.info(
            f"CEO analysis: response({len(response_text)}), combined({len(raw_text)})"
        )

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
        logger.error(f"CEO analysis failed: {e}", exc_info=True)

    # 최종 폴백: 단순 대화로 처리
    yield {
        "task_type": "simple_chat",
        "delegate_to": "SELF",
        "reasoning": "CEO analysis failed, fallback to direct response",
        "refined_prompt": user_message,
    }


def _extract_task_json(raw_text: str) -> dict | None:
    """raw 텍스트에서 task_type이 포함된 JSON 객체를 추출합니다."""
    # 1차: JSONDecoder.raw_decode — 중첩 {} 처리 가능
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw_text):
        if ch == "{":
            try:
                obj, end_idx = decoder.raw_decode(raw_text, i)
                if isinstance(obj, dict) and "task_type" in obj:
                    logger.info(
                        f"CEO Analysis (raw_decode): type={obj.get('task_type')}, delegate={obj.get('delegate_to')}"
                    )
                    return obj
            except json.JSONDecodeError:
                continue

    # 2차: 정규식 폴백
    json_match = re.search(
        r'\{[^{}]*"task_type"\s*:\s*"[^"]*"[^{}]*\}', raw_text, re.DOTALL
    )
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError as je:
            logger.warning(f"CEO JSON decode error: {je}")

    return None


_KEYWORD_MAP = [
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
            logger.info(f"CEO fallback: detected {task_type} from keywords")
            return {
                "task_type": task_type,
                "delegate_to": delegate,
                "reasoning": "keyword-based detection",
                "refined_prompt": user_message,
            }
    return None
