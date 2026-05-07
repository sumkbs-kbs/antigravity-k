from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
import json
import logging
import asyncio

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.protocol_translator import ProtocolTranslator, APIFormat
from antigravity_k.engine.audit_logger import get_audit_logger

# 이 함수들은 server.py의 의존성 주입 함수들을 참조합니다.
# 순환 참조를 피하기 위해 내부 임포트를 사용하거나 server.py에서 공유 모듈로 분리하는 것이 좋습니다.
# 여기서는 router.dependencies를 사용하지 않고 직접 가져옵니다.
from antigravity_k.api.dependencies import (
    get_model_manager,
    get_translator,
    get_orchestrator,
)

logger = logging.getLogger("antigravity_k.api.chat")

router = APIRouter()


def _latest_user_text(messages: list[dict]) -> str:
    """Return the latest text-only user message for slash-command routing."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            return " ".join(parts).strip()
    return ""


def _stream_text_response(text: str, model: str):
    async def event_generator():
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


@router.get("/v1/chat/completions/reconnect")
async def chat_reconnect():
    from .legacy import _active_session
    import asyncio

    async def event_generator():
        if not _active_session.is_active:
            yield "data: [DONE]\n\n"
            return

        # Yield history first
        for chunk in _active_session.history:
            data = {"choices": [{"delta": {"content": chunk}}]}
            yield f"data: {json.dumps(data)}\n\n"

        # Poll for new chunks
        last_idx = len(_active_session.history)
        while _active_session.is_active:
            if len(_active_session.history) > last_idx:
                for chunk in _active_session.history[last_idx:]:
                    data = {"choices": [{"delta": {"content": chunk}}]}
                    yield f"data: {json.dumps(data)}\n\n"
                last_idx = len(_active_session.history)
            await asyncio.sleep(0.5)

        if _active_session.error:
            data = {
                "choices": [
                    {"delta": {"content": f"\n\n[Error: {_active_session.error}]"}}
                ]
            }
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    manager: ModelManager = Depends(get_model_manager),
    translator: ProtocolTranslator = Depends(get_translator),
):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    source_format = translator.detect_format(body)
    internal_req = translator.translate_request(body, source=source_format)

    target_model = internal_req.get("model", "")
    if not target_model:
        raise HTTPException(status_code=400, detail="Model is required")

    messages = internal_req.get("messages", [])

    from antigravity_k.api.dependencies import _get_session_manager

    session_manager = _get_session_manager()
    session_manager.start_session(resume=True)

    # Auto-restore context for new conversations (UI sends few messages)
    if len(messages) <= 2:
        restored_context = session_manager.auto_restore()
        if restored_context:
            messages.insert(0, {"role": "system", "content": restored_context})

    is_stream = body.get("stream", False)
    is_agent_mode = body.get("agent_mode", True)
    is_plan_mode = body.get("plan_mode", False)

    # [AUTONOMY] 사용자의 TDD 모드 자동 판단 요구사항 반영
    is_tdd_mode = body.get("tdd_mode", False)
    slash_text = _latest_user_text(messages)

    if is_tdd_mode:
        # TDD가 켜져 있어도, 단순 작업(폴더 생성, 스크립트 실행, 진행 요청)이면 자동으로 끕니다.
        simple_indicators = [
            "폴더",
            "파일 생성",
            "출력",
            "실행",
            "진행해줘",
            "만들어줘",
            "테스트 폴더",
        ]
        if (
            len(slash_text) < 150
            and any(k in slash_text for k in simple_indicators)
            and "알고리즘" not in slash_text
            and "리팩토링" not in slash_text
        ):
            import logging

            logging.getLogger(__name__).info(
                f"Auto-TDD: Disabling TDD mode for simple task: {slash_text[:50]}"
            )
            is_tdd_mode = False
    else:
        # TDD가 꺼져 있어도, 복잡한 알고리즘이나 리팩토링 요청이면 자동으로 켭니다.
        complex_indicators = ["알고리즘", "리팩토링", "최적화", "병렬 처리", "TDD로"]
        if any(k in slash_text for k in complex_indicators):
            import logging

            logging.getLogger(__name__).info(
                f"Auto-TDD: Enabling TDD mode for complex task: {slash_text[:50]}"
            )
            is_tdd_mode = True

    from antigravity_k.engine.self_capability import (
        SelfCapabilityEngine,
        is_self_capability_request,
    )

    if is_self_capability_request(slash_text):
        from antigravity_k.api.dependencies import (
            __get_skill_loader,
            __get_tool_registry,
        )
        from . import legacy as legacy_routes

        registry = legacy_routes._get_slash_registry()
        engine = SelfCapabilityEngine()
        snapshot = engine.build(
            tool_registry=__get_tool_registry(),
            skill_loader=__get_skill_loader(),
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
            "tokens_in": len(slash_text) // 4,
            "tokens_out": len(result) // 4,
        }
        target_format = (
            source_format if source_format != APIFormat.INTERNAL else APIFormat.OPENAI
        )
        return translator.translate_response(internal_resp, target=target_format)

    if slash_text.startswith("/"):
        from . import legacy as legacy_routes

        registry = legacy_routes._get_slash_registry()
        # 등록된 슬래시 명령어인 경우에만 라우팅 (파일 경로 등 오인 방지)
        if registry.is_command(slash_text):
            result = registry.execute(slash_text)

            import types

            if isinstance(result, types.GeneratorType):
                if is_stream:

                    async def _gen_stream():
                        for chunk in result:
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

                    return StreamingResponse(
                        _gen_stream(), media_type="text/event-stream"
                    )
                else:
                    result = "".join(list(result))

            if is_stream:
                return _stream_text_response(result, target_model)

            internal_resp = {
                "content": result,
                "model": target_model,
                "finish_reason": "stop",
                "tokens_in": len(slash_text) // 4,
                "tokens_out": len(result) // 4,
            }
            target_format = (
                source_format
                if source_format != APIFormat.INTERNAL
                else APIFormat.OPENAI
            )
            return translator.translate_response(internal_resp, target=target_format)

    # TDD Mode: OmniTDDEngine 비동기 실행 및 실시간 스트리밍 반환
    if is_tdd_mode:
        from antigravity_k.engine.tdd_engine import OmniTDDEngine

        prompt = ""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        [c.get("text", "") for c in content if c.get("type") == "text"]
                    )
                prompt += content + "\n"

        # 간단한 정규식으로 타겟 파일 경로 추출 시도 (예: 파일명.py)
        import re

        target_path_match = re.search(r"([a-zA-Z0-9_\-\./]+\.py)", prompt)
        target_file_path = target_path_match.group(1) if target_path_match else None
        if target_file_path and not target_file_path.startswith("/"):
            # 기본 작업 공간 기준 경로
            import os

            target_file_path = os.path.join(
                "/Users/mr.k/program/coding/ssak_comp/antigravity-k", target_file_path
            )

        async def tdd_event_generator():
            def yield_chunk(text):
                data = {
                    "id": "chatcmpl-stream",
                    "object": "chat.completion.chunk",
                    "model": target_model,
                    "choices": [
                        {"delta": {"content": text}, "index": 0, "finish_reason": None}
                    ],
                }
                return f"data: {json.dumps(data)}\n\n"

            try:
                yield yield_chunk(
                    "🧪 **Omni-TDD Mode Activated**\n\nStarting multi-model racing engine...\n\n"
                )
                yield yield_chunk(
                    "⏳ Sandboxed generation and testing in progress... (This may take 1-2 minutes)\n\n"
                )

                engine = OmniTDDEngine(coding_model=target_model)
                report = await engine.run_tdd_loop(
                    prompt, target_file_path=target_file_path
                )

                if report.status == "passed":
                    meta = f"✅ **TDD Completed Successfully**\n\n- **Winner:** `{report.winner_source}`\n- **Iterations:** {report.total_iterations}\n- **Duration:** {report.duration_ms/1000:.1f}s\n"
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
                    res = f"❌ **TDD Failed**\n\n- **Iterations:** {report.total_iterations}\n- **Error:** {report.error}\n"

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
                logger.error(f"TDD Stream error: {e}", exc_info=True)
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
        messages = [plan_system_msg] + messages

    # Vision Auto-Routing: 이미지가 포함된 메시지 감지 시 비전 모델로 자동 전환
    has_image = False
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
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
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                    )
                ),
                "config.yaml",
            )
            with open(config_path, "r") as f:
                cfg = yaml.safe_load(f)
            vision_model = cfg.get("defaults", {}).get("vision")
            if vision_model:
                logger.info(
                    f"[Vision Auto-Routing] 이미지 감지 → 모델 전환: {target_model} → {vision_model}"
                )
                target_model = vision_model
        except Exception as e:
            logger.warning(f"Vision auto-routing config read failed: {e}")

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
        from starlette.concurrency import iterate_in_threadpool

        orchestrator = get_orchestrator()

        # Use legacy session state for reconnect (basic implementation)
        from . import legacy as legacy_routes

        # Start new session
        legacy_routes._active_session = legacy_routes.ActiveAgentSession()
        active_session = legacy_routes._active_session
        active_session.is_active = True

        async def event_generator():
            full_response = ""
            try:
                async for chunk in iterate_in_threadpool(
                    orchestrator.run_stream(messages, target_model=target_model)
                ):
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
                # Client disconnected, but the background thread might still continue!
                logger.warning("SSE client disconnected from chat completions.")
                raise
            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
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
                active_session.is_active = False

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Non-streaming or non-agent mode (fallback to original logic)
    system_msg = internal_req.get("system", "")
    prompt = ""
    if system_msg:
        prompt += f"System: {system_msg}\n\n"
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                [c.get("text", "") for c in content if c.get("type") == "text"]
            )
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
                for chunk in manager.stream_generate(
                    prompt=prompt, target=target_model, **kwargs
                ):
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

            return StreamingResponse(
                event_generator_native(), media_type="text/event-stream"
            )
        else:
            response_text = manager.generate(
                prompt=prompt, target=target_model, **kwargs
            )

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
                "tokens_in": len(prompt) // 4,
                "tokens_out": len(response_text) // 4,
            }
            target_format = (
                source_format
                if source_format != APIFormat.INTERNAL
                else APIFormat.OPENAI
            )
            return translator.translate_response(internal_resp, target=target_format)
    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
