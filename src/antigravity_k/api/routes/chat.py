from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
import json
import logging
import asyncio
from typing import Optional

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.protocol_translator import ProtocolTranslator, APIFormat
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.audit_logger import get_audit_logger

# 이 함수들은 server.py의 의존성 주입 함수들을 참조합니다.
# 순환 참조를 피하기 위해 내부 임포트를 사용하거나 server.py에서 공유 모듈로 분리하는 것이 좋습니다.
# 여기서는 router.dependencies를 사용하지 않고 직접 가져옵니다.
from antigravity_k.api.dependencies import (
    get_model_manager, get_translator, get_vault_engine, get_orchestrator
)

logger = logging.getLogger("antigravity_k.api.chat")

router = APIRouter()

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
            data = {"choices": [{"delta": {"content": f"\n\n[Error: {_active_session.error}]"}}]}
            yield f"data: {json.dumps(data)}\n\n"
        
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    manager: ModelManager = Depends(get_model_manager),
    translator: ProtocolTranslator = Depends(get_translator),
    vault: Optional[VaultEngine] = Depends(get_vault_engine)
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
    
    is_stream = body.get("stream", False)
    is_agent_mode = body.get("agent_mode", True)
    
    audit = get_audit_logger()
    audit.log_event("chat_request", {"model": target_model, "stream": is_stream, "agent": is_agent_mode})
    
    if is_stream and is_agent_mode:
        from starlette.concurrency import iterate_in_threadpool
        orchestrator = get_orchestrator()
        
        # Use a global queue/state for reconnect (basic implementation)
        from .legacy import _active_session, ActiveAgentSession
        global _active_session
        
        # Start new session
        _active_session = ActiveAgentSession()
        _active_session.is_active = True
        
        async def event_generator():
            try:
                async for chunk in iterate_in_threadpool(orchestrator.run_stream(messages, target_model=target_model)):
                    _active_session.history.append(chunk)
                    data = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": target_model,
                        "choices": [{"delta": {"content": chunk}, "index": 0, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                
                _active_session.done = True
                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                # Client disconnected, but the background thread might still continue!
                logger.warning("SSE client disconnected from chat completions.")
                raise
            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                _active_session.error = str(e)
                data = {"choices": [{"delta": {"content": f"\n\n[Error: {str(e)}]"}, "index": 0, "finish_reason": "error"}]}
                yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                _active_session.is_active = False
                
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
            content = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
        prompt += f"{role.capitalize()}: {content}\n"
    prompt += "Assistant: "

    try:
        kwargs = {
            "max_tokens": internal_req.get("max_tokens", 1024),
            "temperature": internal_req.get("temperature", 0.7),
        }
        
        if is_stream:
            def event_generator_native():
                for chunk in manager.stream_generate(prompt=prompt, target=target_model, **kwargs):
                    data = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": target_model,
                        "choices": [{"delta": {"content": chunk}, "index": 0, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(event_generator_native(), media_type="text/event-stream")
        else:
            response_text = manager.generate(prompt=prompt, target=target_model, **kwargs)
            internal_resp = {
                "content": response_text,
                "model": target_model,
                "finish_reason": "stop",
                "tokens_in": len(prompt) // 4,
                "tokens_out": len(response_text) // 4,
            }
            target_format = source_format if source_format != APIFormat.INTERNAL else APIFormat.OPENAI
            return translator.translate_response(internal_resp, target=target_format)
    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
