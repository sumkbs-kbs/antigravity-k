import asyncio
import contextvars
import json
import logging
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Annotated, Callable, TypeAlias, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

# 이 함수들은 server.py의 의존성 주입 함수들을 참조합니다.
# 순환 참조를 피하기 위해 내부 임포트를 사용하거나 server.py에서 공유 모듈로 분리하는 것이 좋습니다.
# 여기서는 router.dependencies를 사용하지 않고 직접 가져옵니다.
from antigravity_k.api.dependencies import (
    get_agent_runtime,
    get_model_manager,
    get_translator,
)
from antigravity_k.engine.audit_logger import get_audit_logger
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.protocol_translator import APIFormat, ProtocolTranslator
from antigravity_k.engine.tokenizer import TokenEstimator

logger = logging.getLogger("antigravity_k.api.chat")

router = APIRouter()

JsonMap: TypeAlias = dict[str, object]
ChatMessage: TypeAlias = JsonMap


def _string_value(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _bool_value(value: object, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in cast(list[object], content):
            if not isinstance(item, dict):
                continue
            part = cast(JsonMap, item)
            if part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return " ".join(parts)
    return ""


def _messages_value(value: object) -> list[ChatMessage]:
    if not isinstance(value, list):
        return []
    return [cast(ChatMessage, item) for item in cast(list[object], value) if isinstance(item, dict)]


def _latest_user_text(messages: list[ChatMessage]) -> str:
    """Return the latest text-only user message for slash-command routing."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        return _content_text(msg.get("content", "")).strip()
    return ""


# P0 환각 방지: LLM intent 분류 실패 시 한국어/영어 키워드 기반 폴백
# rate limit 등으로 SEARCH 분류가 안 되면 모델이 날씨/주가 데이터를 지어내는 것을 방지
#
# 설계 원칙: 키워드는 "명확한 도메인"만 등록 (날씨, 주가, 뉴스).
# 광범위한 단어("현재", "알려", "오늘")는 false positive를 만들므로 제외.
# 자가 인식 질문("모델이 뭐야", "능력")은 is_self_capability_request()가
# 정규식으로 처리하므로 여기서 다룰 필요 없음.
_SEARCH_KEYWORDS = [
    # 날씨 (명확)
    "날씨",
    "기온",
    "비 오",
    "맑음",
    "흐림",
    "눈 오",
    "태풍",
    "미세먼지",
    "weather",
    "temperature",
    "forecast",
    # 주가/경제 (명확)
    "주가",
    "주식",
    "시세",
    "코스피",
    "코스닥",
    "상장",
    "공시",
    "환율",
    "stock",
    "price",
    "market",
    # 뉴스/실시간 (명확)
    "뉴스",
    "속보",
    "실시간",
    "news",
    "latest",
    # 검색 명확 (동사)
    "검색",
    "찾아줘",
    "조회해",
]

# TDD 트리거 — 명확한 "작성/수정" 동사 + 코딩 명사 조합만 매칭
# 단순히 "코드", "함수"가 포함되었다고 TDD가 되지 않도록 조합 패턴 사용
_TDD_ACTION_KEYWORDS = [
    "작성",
    "구현",
    "수정",
    "만들",
    "생성",
    "개발",
    "코딩",
    "프로그래밍",
    "write",
    "create",
    "implement",
    "fix",
    "build",
    "develop",
    "code",
]
_TDD_TARGET_KEYWORDS = [
    "함수",
    "클래스",
    "메서드",
    "모듈",
    "스크립트",
    "알고리즘",
    "버그",
    "에러",
    "오류",
    "리팩토링",
    "function",
    "class",
    "method",
    "script",
    "bug",
    "error",
    "refactor",
]


def _has_code_write_signal(text: str) -> bool:
    """LLM TDD 판정을 존중할 '코드 쓰기' 신호가 있는지.

    변경 동사(작성/구현/수정/만들/...)가 있어야 한다 — 파일 경로나 코드
    명사만 언급된 읽기·요약·제안 요청까지 TDD 레이싱(고비용 멀티모델
    생성-테스트 루프)으로 보내는 것을 막는다. 소형 모델의 10토큰 인텐트
    분류는 이런 오판이 잦다.
    """
    text_lower = text.lower()
    return any(kw in text_lower for kw in _TDD_ACTION_KEYWORDS)


def _keyword_intent_fallback(text: str) -> str:
    """LLM intent 분류 실패 시 키워드 기반으로 SEARCH/TDD/GENERAL을 판별.

    환각 방지 핵심: "거제도 날씨", "한화 주가" 등의 질문이
    LLM 없이도 SEARCH로 분류되어 실제 웹검색을 수행하도록 보장.

    TDD 판별 원칙: 동사(작성/구현/수정) + 명사(함수/클래스/버그) 조합으로
    실제 코드 생성 의도가 있을 때만 TDD로 분류.
    "코드 설명해줘", "이 함수가 뭐야?" 같은 질문은 GENERAL로 처리.

    주의: 자가 인식 질문("모델이 뭐야", "니가 할 수 있는 것")은
    is_self_capability_request()가 chat_completions() 상단에서 먼저 처리하므로
    이 함수까지 도달하지 않음. 여기서는 순수 SEARCH/TDD만 판별.
    """
    text_lower = text.lower()

    # SEARCH 키워드 매칭 (환각 방지)
    for kw in _SEARCH_KEYWORDS:
        if kw in text_lower:
            return "SEARCH"

    # TDD: 동사 + 명사 조합이 있을 때만 (단일 키워드로는 TDD 아님)
    has_action = any(kw in text_lower for kw in _TDD_ACTION_KEYWORDS)
    has_target = any(kw in text_lower for kw in _TDD_TARGET_KEYWORDS)
    # 파일 확장자가 있으면 강제 TDD
    has_file_ext = any(ext in text_lower for ext in [".py", ".js", ".ts", ".java", ".go", ".rs"])
    if (has_action and has_target) or (has_action and has_file_ext):
        return "TDD"

    return "GENERAL"


def _stream_text_response(text: str, model: str) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        data = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [
                {
                    "delta": {"content": text},
                    "index": 0,
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _validate_chat_request_body(body: object) -> JsonMap:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    body_map = cast(JsonMap, body)
    model = body_map.get("model")
    if model is not None and not isinstance(model, str):
        raise HTTPException(status_code=400, detail="'model' must be a string")

    messages = body_map.get("messages")
    if messages is not None:
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="'messages' must be an array")
        for index, message in enumerate(cast(list[object], messages)):
            if not isinstance(message, dict):
                raise HTTPException(status_code=400, detail=f"'messages[{index}]' must be an object")
            message_map = cast(JsonMap, message)

            role = message_map.get("role")
            if role is not None and not isinstance(role, str):
                raise HTTPException(status_code=400, detail=f"'messages[{index}].role' must be a string")

            content = message_map.get("content")
            if content is not None and not isinstance(content, (str, list)):
                raise HTTPException(
                    status_code=400,
                    detail=f"'messages[{index}].content' must be a string or array",
                )
            if isinstance(content, list):
                for part_index, part in enumerate(cast(list[object], content)):
                    if not isinstance(part, dict):
                        raise HTTPException(
                            status_code=400,
                            detail=f"'messages[{index}].content[{part_index}]' must be an object",
                        )

    for flag in ("stream", "agent_mode", "plan_mode", "tdd_mode"):
        value = body_map.get(flag)
        if value is not None and not isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"'{flag}' must be a boolean")

    return body_map


@router.get("/v1/chat/completions/reconnect")
async def chat_reconnect() -> StreamingResponse:
    import asyncio

    from antigravity_k.api.routes.session_state import get_active_session

    active_session = get_active_session()

    async def event_generator() -> AsyncIterator[str]:
        if not active_session.is_active:
            yield "data: [DONE]\n\n"
            return

        # Yield history first
        for chunk in active_session.history:
            data = {"choices": [{"delta": {"content": chunk}}]}
            yield f"data: {json.dumps(data)}\n\n"

        # Poll for new chunks
        last_idx = len(active_session.history)
        while active_session.is_active:
            if len(active_session.history) > last_idx:
                for chunk in active_session.history[last_idx:]:
                    data = {"choices": [{"delta": {"content": chunk}}]}
                    yield f"data: {json.dumps(data)}\n\n"
                last_idx = len(active_session.history)
            await asyncio.sleep(0.5)

        if active_session.error:
            data = {"choices": [{"delta": {"content": f"\n\n[Error: {active_session.error}]"}}]}
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    manager: Annotated[ModelManager, Depends(get_model_manager)],
    translator: Annotated[ProtocolTranslator, Depends(get_translator)],
) -> object:
    try:
        body = _validate_chat_request_body(cast(object, await request.json()))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    source_format = translator.detect_format(body)
    internal_req = translator.translate_request(body, source=source_format)

    target_model = _string_value(internal_req.get("model"))
    if not target_model:
        raise HTTPException(status_code=400, detail="Model is required")

    messages = _messages_value(internal_req.get("messages", []))

    # P0 인젝션 방어: HIGH 패턴 감지 시 시스템 경고 삽입
    from antigravity_k.engine.prompt_injection_guard import PromptInjectionGuard

    guarded_messages = PromptInjectionGuard().augment_user_input(cast(list[dict[str, str]], messages))
    messages = _messages_value(guarded_messages)

    from antigravity_k.api import dependencies as api_dependencies
    from antigravity_k.engine.session_manager import SessionManager

    get_session_manager = cast(
        "Callable[[], SessionManager]",
        getattr(api_dependencies, "_get_session_manager"),
    )
    session_manager = get_session_manager()
    _ = session_manager.start_session(resume=True)

    # Auto-restore context for new conversations (UI sends few messages)
    # 작업 2: 임계값 완화 (<= 4) — 더 많은 새 대화에서 이전 기억 복원
    if len(messages) <= 4:
        restored_context = session_manager.auto_restore()
        if restored_context:
            messages.insert(0, cast(ChatMessage, {"role": "system", "content": restored_context}))

    is_stream = _bool_value(body.get("stream"))
    is_agent_mode = _bool_value(body.get("agent_mode"), default=True)
    is_plan_mode = _bool_value(body.get("plan_mode"))

    # [AUTONOMY] 사용자의 TDD 모드 자동 판단 요구사항 반영
    is_tdd_mode = _bool_value(body.get("tdd_mode"))
    slash_text = _latest_user_text(messages)

    # 작업 4: 모든 경로에서 사용자 학습 — UserIntentModeler.observe() 호출
    try:
        from antigravity_k.engine.user_model import UserIntentModeler

        _user_model = UserIntentModeler()
        if slash_text:
            _user_model.observe(slash_text, "general")
    except Exception:
        logger.warning("UserIntentModeler.observe 실패 (non-critical)", exc_info=True)

    import logging

    logger_auto = logging.getLogger(__name__)

    # Self-capability 및 슬래시 명령어는 Intent 분류 생략 (LLM 호출 절약)
    from antigravity_k.engine.self_capability import is_self_capability_request

    is_fast_search = False

    if not is_tdd_mode and slash_text:
        _skip_intent_classification = False
        if slash_text.startswith("/") or is_self_capability_request(slash_text):
            _skip_intent_classification = True
        else:
            # 매우 단순한 인사말 등은 LLM 호출 없이 빠른 패스
            fast_bypass = ["안녕", "고마워", "누구야", "뭐해"]
            if len(slash_text) < 15 and any(k in slash_text for k in fast_bypass):
                _skip_intent_classification = True

        if not _skip_intent_classification:
            # P0 환각 방지: LLM 호출 전에 키워드 기반 사전 분류
            # 날씨/주가/뉴스 등 명확한 검색 의도는 LLM 없이 SEARCH로 확정 — 환각 방지
            _pre_intent = _keyword_intent_fallback(slash_text)

            logger_auto.info("[DEBUG] slash_text=%s pre_intent=%s", repr(slash_text[:60]), _pre_intent)

            if _pre_intent == "SEARCH":
                # 키워드로 SEARCH가 확정되면 LLM 호출 생략
                logger_auto.info("Auto-Intent (키워드): SEARCH 모드 — '%s'", slash_text[:40])
                is_fast_search = True

            elif _pre_intent == "TDD":
                logger_auto.info("Auto-Intent (키워드): TDD 모드 — '%s'", slash_text[:40])
                is_tdd_mode = True
            else:
                # 키워드로 판별 불가한 경우에만 LLM 분류 사용

                def _classify_intent():
                    prompt = (
                        "You are an autonomous intent router. Analyze the user request and categorize it into ONE of these exactly:\n"  # noqa: E501
                        "1. 'TDD' - requires writing new code, fixing bugs, or implementing software features.\n"
                        "2. 'SEARCH' - simple web search for information (e.g. stock price, weather, news).\n"
                        "3. 'GENERAL' - simple question, explanation, general chat.\n\n"
                        "Reply EXACTLY with the category name.\n\n"
                        f"User Request: {slash_text[:500]}"
                    )
                    try:
                        # 최대한 빠르고 결정론적인 판단을 위해 온도(temperature) 0.0 설정
                        res = manager.generate(
                            prompt=prompt,
                            target=target_model,
                            max_tokens=10,
                            temperature=0.0,
                        )
                        r = res.lower()
                        if "tdd" in r:
                            return "TDD"
                        if "search" in r:
                            return "SEARCH"
                        return "GENERAL"
                    except Exception as e:
                        logger_auto.warning("Auto-Intent LLM classification failed: %s", e)
                        return _keyword_intent_fallback(slash_text)

                from starlette.concurrency import run_in_threadpool

                intent = await run_in_threadpool(_classify_intent)

                if intent == "TDD":
                    # 이중 확인 — 코드 '쓰기' 동사 없는 요청의 TDD 오판은 무시한다
                    if _has_code_write_signal(slash_text):
                        logger_auto.info("Auto-Intent: LLM autonomously enabled TDD mode for: %s", slash_text[:50])
                        is_tdd_mode = True
                    else:
                        logger_auto.info(
                            "Auto-Intent: LLM TDD 판정 무시 (코드 신호 없음): %s",
                            slash_text[:50],
                        )
                elif intent == "SEARCH":
                    logger_auto.info("Auto-Intent: LLM autonomously enabled FAST SEARCH mode for: %s", slash_text[:50])
                    is_fast_search = True

    if is_fast_search:
        try:
            from antigravity_k.engine.prompt_builder import PromptBuilder
            from antigravity_k.engine.stock_code_validator import (
                format_code_correction,
                validate_query_stock_codes,
            )
            from antigravity_k.tools.web_search import WebSearchTool

            tool = WebSearchTool()

            # 종목코드 검증 및 쿼리 보강
            stock_validation = validate_query_stock_codes(slash_text)
            search_query = slash_text
            stock_correction_note = ""
            if stock_validation.needs_correction:
                search_query = stock_validation.corrected_query
                stock_correction_note = format_code_correction(stock_validation)
                logger_auto.info(
                    "종목코드 교정: '%s' → '%s' (잘못된 코드: %s)",
                    slash_text,
                    search_query,
                    [v.original_code for v in stock_validation.codes_found if v.needs_correction],
                )

            search_res = tool.execute(query=search_query)

            # 계층형 프롬프트 + Few-Shot 예시 + 적응형 샘플링
            from datetime import datetime as _dt
            from datetime import timedelta as _td

            now = _dt.now()
            today_str = now.strftime("%Y년 %m월 %d일")
            yesterday_str = (now - _td(days=1)).strftime("%Y년 %m월 %d일")
            pb = PromptBuilder()

            # 종목코드 교정 노트를 컨텍스트에 추가 (있을 경우에만)
            context_with_correction = search_res
            if stock_correction_note:
                context_with_correction = f"[종목코드 자동 교정 정보]\n{stock_correction_note}\n\n{search_res}"

            # ─── 구조화 데이터 추출 (검색 결과에서 숫자/가격/날짜 자동 추출) ───
            try:
                from antigravity_k.engine.data_extractor import extract_structured_data

                # search_res에서 구조화 데이터 추출
                structured = extract_structured_data([search_res], query=slash_text)
                if structured:
                    context_with_correction = (
                        f"{context_with_correction}\n\n"
                        f"📊 **[구조화 데이터 추출] (검색 결과에서 자동 추출된 정확한 수치):**\n"
                        f"{structured}\n\n"
                        f"[중요] 위 데이터는 검색 결과에서 자동 추출된 값입니다. "
                        f"답변 시 반드시 이 값을 우선적으로 사용하고 [N] 출처 번호도 함께 표기하세요."
                    )
            except Exception:
                logger_auto.debug("구조화 데이터 추출 실패 (non-critical)", exc_info=True)
            # ────────────────────────────────────────────────────────────────

            fast_prompt = pb.structured_prompt(
                role="정보 조회 전문가 — 검증된 데이터만 인용하고 추측을 절대 금지",
                task=f"사용자의 질문에 가장 간결하고 정확하게 한국어로 답변하세요.\n질문: {slash_text}",
                context=context_with_correction,
                constraints=[
                    f"현재 날짜는 {today_str}입니다. '어제'는 {yesterday_str}을 의미합니다.",
                    "반드시 한국어로 답변하세요.",
                    "",
                    "[필수 규칙]",
                    "1. 검색 결과 본문의 모든 구체적 수치(종가, 시가, 고가, 저가, 거래량, 변동률, 기온 등)를 반드시 답변에 포함하세요. 검색 결과 [TOP 1 심층 분석] 데이터를 최우선으로 신뢰하세요.",
                    "2. 검색 결과에 없는 수치는 절대 생성하지 마세요. 모르는 값은 '해당 정보는 검색 결과에 없습니다'라고만 답변하세요.",
                    "3. 모든 수치 데이터 뒤에 반드시 출처 번호를 [N] 형식으로 표기하세요 (예: '종가 943,000원 [1]').",
                    "4. 검색 결과에 명시된 기업명, 종목코드, 지명 등 고유명사를 원문 그대로 사용하세요. 사용자가 짧은 이름(예: '한화')을 써도 검색 결과의 공식 명칭('한화에어로스페이스')을 사용하세요.",
                    "",
                    "[금지 사항]",
                    "5. '~할 수 있습니다', '~것으로 보입니다', '~예상됩니다', '~추정됩니다' 등 추측 표현을 절대 사용하지 마세요.",
                    "6. '약', '대략', '정도', '가량' 등 불확실한 수치 표현을 절대 사용하지 마세요.",
                    "7. 불필요한 서론, 일반적 맥락 설명 없이 핵심 데이터부터 즉시 시작하세요. 첫 문장은 반드시 가장 중요한 수치로 시작하세요.",
                ],
                output_format="""
**첫 줄:** 가장 중요한 수치를 굵게 + 출처 [N]
**표:** 관련 데이터를 마크다운 테이블로 제시
**설명:** 1-2줄 (필요시만)

예: **한화에어로스페이스: 943,000원** (+1.51%) [1]

| 구분 | 금액 |
| :--- | :--- |
| **종가** | **943,000원** [1] |
| 시가 | 930,000원 [1] |
| 고가 | 970,000원 [1] |
| 저가 | 905,000원 [1] |
| 거래량 | 142,859주 [1] |
""",
                few_shot=pb.get_task_few_shots("SEARCH"),
            )

            if is_stream:

                async def _fast_stream() -> AsyncIterator[str]:
                    yield f"data: {json.dumps({'id': 'chatcmpl-stream', 'object': 'chat.completion.chunk', 'model': target_model, 'choices': [{'delta': {'content': '🔍 **빠른 웹 검색 모드 실행 중...**\\n\\n'}, 'index': 0, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"  # noqa: E501
                    # SEARCH 샘플링 프로파일 (low temp=0.15, min_p=0.05)
                    gen = manager.stream_generate(
                        prompt=fast_prompt,
                        target=target_model,
                        task_type="SEARCH",
                    )
                    for chunk in gen:
                        data = {
                            "id": "chatcmpl-stream",
                            "object": "chat.completion.chunk",
                            "model": target_model,
                            "choices": [
                                {
                                    "delta": {"content": chunk},
                                    "index": 0,
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"

                # 빠른 검색도 세션 컨텍스트에 저장
                session_manager.add_turn(
                    [
                        {"role": "user", "content": slash_text},
                        {"role": "assistant", "content": "(빠른 검색 모드 실행됨)"},
                    ]
                )
                return StreamingResponse(_fast_stream(), media_type="text/event-stream")
            else:
                fast_res = manager.generate(prompt=fast_prompt, target=target_model)
                internal_resp = {
                    "content": f"🔍 **빠른 웹 검색 모드 실행 중...**\n\n{fast_res}",
                    "model": target_model,
                    "finish_reason": "stop",
                    "tokens_in": TokenEstimator.estimate_text(slash_text),
                    "tokens_out": TokenEstimator.estimate_text(fast_res),
                }
                session_manager.add_turn(
                    [
                        {"role": "user", "content": slash_text},
                        {"role": "assistant", "content": fast_res},
                    ]
                )
                target_format = source_format if source_format != APIFormat.INTERNAL else APIFormat.OPENAI
                return translator.translate_response(internal_resp, target=target_format)
        except Exception as e:
            logger.exception("Unhandled exception")
            logger_auto.error("Fast search failed: %s. Falling back to normal mode.", e)

            is_fast_search = False

    from antigravity_k.engine.self_capability import (
        SelfCapabilityEngine,
        is_self_capability_request,
    )

    if is_self_capability_request(slash_text):
        from antigravity_k.api.dependencies import get_slash_registry
        from antigravity_k.engine.skill_loader import SkillLoader
        from antigravity_k.tools.tool_registry import ToolRegistry

        registry = get_slash_registry()
        engine = SelfCapabilityEngine()
        get_skill_loader = cast(
            "Callable[[], SkillLoader]",
            getattr(api_dependencies, "__get_skill_loader"),
        )
        get_tool_registry = cast(
            "Callable[[], ToolRegistry]",
            getattr(api_dependencies, "__get_tool_registry"),
        )
        snapshot = engine.build(
            tool_registry=get_tool_registry(),
            skill_loader=get_skill_loader(),
            model_manager=manager,
            slash_commands=getattr(registry, "_commands", {}),
        )
        result = engine.render_markdown(snapshot)
        session_manager.add_turn(
            [
                {"role": "user", "content": slash_text},
                {"role": "assistant", "content": result},
            ]
        )
        if is_stream:
            return _stream_text_response(result, target_model)

        internal_resp = {
            "content": result,
            "model": target_model,
            "finish_reason": "stop",
            "tokens_in": TokenEstimator.estimate_text(slash_text),
            "tokens_out": TokenEstimator.estimate_text(result),
        }
        target_format = source_format if source_format != APIFormat.INTERNAL else APIFormat.OPENAI
        return translator.translate_response(internal_resp, target=target_format)

    if slash_text.startswith("/"):
        from antigravity_k.api.dependencies import get_slash_registry

        registry = get_slash_registry()
        # 등록된 슬래시 명령어인 경우에만 라우팅 (파일 경로 등 오인 방지)
        if registry.is_command(slash_text):
            result = registry.execute(slash_text)
            if result is None:  # 일부 커맨드 구현이 None을 반환할 수 있다
                result = ""

            if isinstance(result, Iterator):
                if is_stream:
                    stream_result = result

                    async def _gen_stream():
                        for chunk in stream_result:
                            data = {
                                "id": "chatcmpl-stream",
                                "object": "chat.completion.chunk",
                                "model": target_model,
                                "choices": [
                                    {
                                        "delta": {"content": chunk},
                                        "index": 0,
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.01)
                        yield "data: [DONE]\n\n"

                    return StreamingResponse(_gen_stream(), media_type="text/event-stream")
                else:
                    result = "".join(str(chunk) for chunk in result)

            result_text = result
            if is_stream:
                return _stream_text_response(result_text, target_model)

            internal_resp = {
                "content": result_text,
                "model": target_model,
                "finish_reason": "stop",
                "tokens_in": TokenEstimator.estimate_text(slash_text),
                "tokens_out": TokenEstimator.estimate_text(result_text),
            }
            target_format = source_format if source_format != APIFormat.INTERNAL else APIFormat.OPENAI
            return translator.translate_response(internal_resp, target=target_format)

    # TDD Mode: OmniTDDEngine 비동기 실행 및 실시간 스트리밍 반환
    if is_tdd_mode:
        from antigravity_k.engine.tdd_engine import OmniTDDEngine

        prompt = ""
        for msg in messages:
            if msg.get("role") == "user":
                prompt += _content_text(msg.get("content", "")) + "\n"

        # 간단한 정규식으로 타겟 파일 경로 추출 시도 (예: 파일명.py)
        import re

        target_path_match = re.search(r"([a-zA-Z0-9_\-\./]+\.py)", prompt)
        target_file_path = target_path_match.group(1) if target_path_match else None
        if target_file_path and not target_file_path.startswith("/"):
            # 동적 프로젝트 루트 기준 경로 (하드코딩 제거)
            import os

            _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            target_file_path = os.path.join(_project_root, target_file_path)

        async def tdd_event_generator():
            def yield_chunk(text: str) -> str:
                data: dict[str, object] = {
                    "id": "chatcmpl-stream",
                    "object": "chat.completion.chunk",
                    "model": target_model,
                    "choices": [{"delta": {"content": text}, "index": 0, "finish_reason": None}],
                }
                return f"data: {json.dumps(data)}\n\n"

            try:
                yield yield_chunk("🧪 **Omni-TDD Mode Activated**\n\nStarting multi-model racing engine...\n\n")
                yield yield_chunk("⏳ Sandboxed generation and testing in progress... (This may take 1-2 minutes)\n\n")

                engine = OmniTDDEngine(model_manager=manager, coding_model=target_model)
                report = await engine.run_tdd_loop(prompt, target_file_path=target_file_path)

                if report.status == "passed":
                    meta = f"✅ **TDD Completed Successfully**\n\n- **Winner:** `{report.winner_source}`\n- **Iterations:** {report.total_iterations}\n- **Duration:** {report.duration_ms / 1000:.1f}s\n"  # noqa: E501
                    if report.skipped_racing:
                        meta += "- **Mode:** Adaptive (local-only, racing skipped)\n"
                    if target_file_path:
                        meta += f"- **Target Path:** `{target_file_path}` (Saved)\n"
                    meta += "\n---\n\n"
                    # Response Reconstructor 결과 포함 (한국어 설명 + 코드)
                    if report.explanation:
                        res = meta + report.explanation
                    else:
                        res = meta + f"```python\n{report.final_code}\n```\n"
                else:
                    res = f"❌ **TDD Failed**\n\n- **Iterations:** {report.total_iterations}\n- **Error:** {report.error}\n"  # noqa: E501

                yield yield_chunk(res)
                yield "data: [DONE]\n\n"

                # 세션에 기록 저장 (프로젝트 단위 컨텍스트 영속성)
                user_msg = _latest_user_text(messages)
                session_manager.add_turn(
                    [
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": res},
                    ]
                )

            except Exception as e:
                logger.error("TDD Stream error: %s", e, exc_info=True)
                yield yield_chunk(f"\n\n[Error: {str(e)}]")
                yield "data: [DONE]\n\n"

        return StreamingResponse(tdd_event_generator(), media_type="text/event-stream")

    # Plan Mode: 시스템 프롬프트에 계획 수립 지시문 주입
    if is_plan_mode:
        plan_system_msg = {
            "role": "system",
            "content": (
                "You are in Plan Mode. Before executing any code or making changes, "
                "you MUST first create a detailed implementation plan. "
                "Structure your plan with: 1) Problem Analysis, 2) Proposed Changes (file by file), "
                "3) Potential Risks, 4) Verification Steps. "
                "Present the plan clearly and ask for user approval before proceeding with implementation. "
                "Do NOT write any code until the user explicitly approves the plan."
            ),
        }
        messages = [cast(ChatMessage, plan_system_msg)] + messages

    # Vision Auto-Routing: 이미지가 포함된 메시지 감지 시 비전 모델로 자동 전환
    has_image = False
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in cast(list[object], content):
                if isinstance(part, dict) and cast(JsonMap, part).get("type") == "image_url":
                    has_image = True
                    break
        elif isinstance(content, str) and content.startswith("data:image/"):
            has_image = True
        if has_image:
            break

    if has_image:
        # config.yaml의 defaults.vision 모델로 자동 전환
        import yaml

        try:
            import os

            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                "config.yaml",
            )
            with open(config_path, "r") as f:
                cfg = cast(JsonMap, yaml.safe_load(f) or {})
            defaults = cfg.get("defaults")
            vision_model = _string_value(cast(JsonMap, defaults).get("vision")) if isinstance(defaults, dict) else ""
            if vision_model:
                logger.info("[Vision Auto-Routing] 이미지 감지 → 모델 전환: %s → %s", target_model, vision_model)
                target_model = vision_model
        except Exception:
            logger.exception("Vision auto-routing config read failed")

    audit = get_audit_logger()
    audit.log_event(
        "chat_request",
        {
            "model": target_model,
            "stream": is_stream,
            "agent": is_agent_mode,
            "plan": is_plan_mode,
            "vision": has_image,
        },
    )

    if is_stream and is_agent_mode:
        from starlette.concurrency import run_in_threadpool

        runtime = get_agent_runtime()

        from antigravity_k.api.routes.session_state import reset_active_session

        # Start new session — shared singleton을 리셋해 사용한다
        active_session = reset_active_session()
        active_session.is_active = True

        async def event_generator():
            full_response = ""
            stream_aiter = None
            try:
                stream_iterator = runtime.stream(cast(Sequence[Mapping[str, str]], messages), target_model=target_model)
                stream_context = contextvars.copy_context()

                async def iterate_stream() -> AsyncIterator[str]:
                    def next_chunk() -> tuple[bool, str | None]:
                        try:
                            return False, next(stream_iterator)
                        except StopIteration:
                            return True, None

                    while True:
                        done, chunk = await run_in_threadpool(stream_context.run, next_chunk)
                        if done:
                            return
                        if chunk is not None:
                            yield chunk

                stream_aiter = iterate_stream()
                async for chunk in stream_aiter:
                    full_response += chunk
                    active_session.history.append(chunk)
                    data = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": target_model,
                        "choices": [
                            {
                                "delta": {"content": chunk},
                                "index": 0,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(data)}\n\n"

                # 세션에 기록 저장 (프로젝트 단위 컨텍스트 영속성)
                user_msg = _latest_user_text(messages)
                session_manager.add_turn(
                    [
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": full_response},
                    ]
                )

                active_session.done = True
                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                # 클라이언트 단절 — 백그라운드 LLM 스트림을 명시적으로 취소하여
                # 좀비 작업과 불필요한 토큰 비용을 방지 (작업 C).
                logger.warning(
                    "SSE 클라이언트 단절 — 백그라운드 스트림 취소 중 (부분 응답 %d chars)",
                    len(full_response),
                )
                # 부분 응답이라도 세션에 저장 (재연결 시 복구 가능)
                if full_response:
                    user_msg = _latest_user_text(messages)
                    session_manager.add_turn(
                        [
                            {"role": "user", "content": user_msg},
                            {"role": "assistant", "content": full_response + "\n\n[클라이언트 단절로 중단]"},
                        ]
                    )
                raise
            except Exception as e:
                logger.error("Stream error: %s", e, exc_info=True)
                active_session.error = str(e)
                data = {
                    "choices": [
                        {
                            "delta": {"content": f"\n\n[Error: {str(e)}]"},
                            "index": 0,
                            "finish_reason": "error",
                        }
                    ]
                }
                yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                # 백그라운드 이터레이터 명시적 종료 (스레드 풀 작업 정리)
                if stream_aiter is not None:
                    aclose = getattr(stream_aiter, "aclose", None)
                    if aclose:
                        try:
                            await aclose()
                        except Exception:
                            logger.debug("Stream iterator cleanup failed", exc_info=True)
                active_session.is_active = False

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Non-streaming or non-agent mode (fallback to original logic)
    system_msg = internal_req.get("system", "")
    prompt = ""
    if system_msg:
        prompt += f"System: {system_msg}\n\n"
    for msg in messages:
        role = _string_value(msg.get("role"), default="user")
        content = _content_text(msg.get("content", ""))
        prompt += f"{role.capitalize()}: {content}\n"
    prompt += "Assistant: "

    try:
        kwargs = {
            "max_tokens": internal_req.get("max_tokens", 1024),
            "temperature": internal_req.get("temperature", 0.7),
        }

        if is_stream:

            def event_generator_native():
                full_response = ""
                for chunk in manager.stream_generate(prompt=prompt, target=target_model, **kwargs):
                    full_response += chunk
                    data = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": target_model,
                        "choices": [
                            {
                                "delta": {"content": chunk},
                                "index": 0,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(data)}\n\n"

                user_msg = _latest_user_text(messages)
                session_manager.add_turn(
                    [
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": full_response},
                    ]
                )
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator_native(), media_type="text/event-stream")
        else:
            response_text = manager.generate(prompt=prompt, target=target_model, **kwargs)

            user_msg = _latest_user_text(messages)
            session_manager.add_turn(
                [
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": response_text},
                ]
            )

            internal_resp = {
                "content": response_text,
                "model": target_model,
                "finish_reason": "stop",
                "tokens_in": TokenEstimator.estimate_text(prompt),
                "tokens_out": TokenEstimator.estimate_text(response_text),
            }
            target_format = source_format if source_format != APIFormat.INTERNAL else APIFormat.OPENAI
            return translator.translate_response(internal_resp, target=target_format)
    except Exception as e:
        logger.error("Generation error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
