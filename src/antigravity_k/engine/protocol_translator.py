"""Antigravity-K: 프로토콜 변환기.

==============================
9Router의 formats.js 패턴 이식 — OpenAI / Anthropic / 내부 포맷 간 자동 변환.

핵심 기능:
- translate_request(): 외부 API 포맷 → 내부 포맷 변환
- translate_response(): 내부 포맷 → 외부 API 포맷 변환
- detect_format(): 요청 포맷 자동 감지
"""

from __future__ import annotations

import logging
import time
import uuid
from enum import Enum
from typing import Any, Union

logger = logging.getLogger("antigravity_k.protocol_translator")


class APIFormat(Enum):
    """지원하는 API 포맷."""

    OPENAI = "openai"  # OpenAI Chat Completion API
    ANTHROPIC = "anthropic"  # Anthropic Messages API
    INTERNAL = "internal"  # Antigravity-K 내부 포맷


class ProtocolTranslator:
    """API 요청/응답 포맷 자동 변환기.

    9Router 패턴: formats.js의 translateBody() 구현을 Python으로 이식.
    OpenAI ↔ Anthropic ↔ 내부 포맷 간 양방향 변환 지원.

    사용 예시:
        translator = ProtocolTranslator()

        # OpenAI 포맷 → 내부 포맷
        internal = translator.translate_request(openai_body, APIFormat.OPENAI)

        # 내부 포맷 → OpenAI 포맷
        openai_resp = translator.translate_response(internal_resp, APIFormat.OPENAI)
    """

    # ─── 요청 변환 ───────────────────────────────────────────────────

    def translate_request(
        self,
        body: dict,
        source: APIFormat,
        target: APIFormat = APIFormat.INTERNAL,
    ) -> dict:
        """요청 포맷을 변환합니다.

        Args:
            body: 원본 요청 바디
            source: 원본 포맷
            target: 목표 포맷

        Returns:
            변환된 요청 바디

        """
        if source == target:
            return body.copy()

        # 먼저 내부 포맷으로 변환
        if source != APIFormat.INTERNAL:
            internal = self._to_internal_request(body, source)
        else:
            internal = body.copy()

        # 목표 포맷으로 변환
        if target != APIFormat.INTERNAL:
            return self._from_internal_request(internal, target)

        return internal

    def translate_response(
        self,
        body: dict,
        target: APIFormat,
        source: APIFormat = APIFormat.INTERNAL,
    ) -> dict:
        """응답 포맷을 변환합니다.

        Args:
            body: 원본 응답 바디
            target: 목표 포맷
            source: 원본 포맷

        Returns:
            변환된 응답 바디

        """
        if source == target:
            return body.copy()

        # 먼저 내부 포맷으로 변환
        if source != APIFormat.INTERNAL:
            internal = self._to_internal_response(body, source)
        else:
            internal = body.copy()

        # 목표 포맷으로 변환
        if target != APIFormat.INTERNAL:
            return self._from_internal_response(internal, target)

        return internal

    # ─── 포맷 감지 ───────────────────────────────────────────────────

    @staticmethod
    def detect_format(body: dict) -> APIFormat:
        """요청 바디에서 API 포맷을 자동 감지합니다.

        - "messages" + "model" → OpenAI
        - "messages" + "max_tokens" (no "model") → Anthropic (드문 케이스)
        - "prompt" → 내부 포맷
        """
        if "messages" in body:
            # Anthropic은 anthropic_version 헤더를 사용하지만,
            # 바디 기반으로는 구분이 어려움 → 기본 OpenAI로 처리
            if body.get("anthropic_version"):
                return APIFormat.ANTHROPIC
            return APIFormat.OPENAI
        elif "prompt" in body:
            return APIFormat.INTERNAL
        else:
            return APIFormat.OPENAI  # 기본값

    # ─── 내부 포맷 정의 ──────────────────────────────────────────────
    #
    # Antigravity-K 내부 포맷:
    # {
    #     "prompt": str,                      # 최종 프롬프트 텍스트
    #     "system": str,                      # 시스템 메시지
    #     "messages": [{"role": str, "content": str}],  # 대화 이력
    #     "model": str,                       # 모델 이름
    #     "max_tokens": int,
    #     "temperature": float,
    #     "top_p": float,
    #     "stream": bool,
    #     "stop": List[str],
    # }

    # ─── OpenAI → 내부 ──────────────────────────────────────────────

    def _openai_to_internal_request(self, body: dict) -> dict:
        """OpenAI Chat Completion 요청 → 내부 포맷."""
        messages = body.get("messages", [])
        system_msg = ""
        chat_messages = []

        for msg in messages:
            role = msg.get("role", "")
            content = self._extract_content(msg.get("content", ""))  # type: ignore[assignment]
            if role == "system":
                system_msg = content  # type: ignore[assignment]
            else:
                chat_messages.append({"role": role, "content": content})

        return {
            "messages": chat_messages,
            "system": system_msg,
            "model": body.get("model", ""),
            "max_tokens": body.get("max_tokens", 4096),
            "temperature": body.get("temperature", 0.7),
            "top_p": body.get("top_p", 0.9),
            "stream": body.get("stream", False),
            "stop": body.get("stop", []),
        }

    # ─── Anthropic → 내부 ───────────────────────────────────────────

    def _anthropic_to_internal_request(self, body: dict) -> dict:
        """Anthropic Messages API 요청 → 내부 포맷."""
        messages = body.get("messages", [])
        system_msg = body.get("system", "")

        # Anthropic의 system은 최상위 필드
        chat_messages = []
        for msg in messages:
            role = msg.get("role", "")
            content = self._extract_content(msg.get("content", ""))  # type: ignore[assignment]
            chat_messages.append({"role": role, "content": content})

        return {
            "messages": chat_messages,
            "system": system_msg,
            "model": body.get("model", ""),
            "max_tokens": body.get("max_tokens", 4096),
            "temperature": body.get("temperature", 0.7),
            "top_p": body.get("top_p", 0.9),
            "stream": body.get("stream", False),
            "stop": body.get("stop_sequences", []),
        }

    # ─── 내부 → OpenAI ──────────────────────────────────────────────

    def _internal_to_openai_response(self, body: dict) -> dict:
        """내부 응답 → OpenAI Chat Completion 응답."""
        content = body.get("content", "")
        model = body.get("model", "antigravity-k")

        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": body.get("finish_reason", "stop"),
                },
            ],
            "usage": {
                "prompt_tokens": body.get("tokens_in", 0),
                "completion_tokens": body.get("tokens_out", 0),
                "total_tokens": (body.get("tokens_in", 0) + body.get("tokens_out", 0)),
            },
        }

    # ─── 내부 → Anthropic ───────────────────────────────────────────

    def _internal_to_anthropic_response(self, body: dict) -> dict:
        """내부 응답 → Anthropic Messages API 응답."""
        content = body.get("content", "")
        model = body.get("model", "antigravity-k")

        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": content,
                },
            ],
            "model": model,
            "stop_reason": body.get("finish_reason", "end_turn"),
            "usage": {
                "input_tokens": body.get("tokens_in", 0),
                "output_tokens": body.get("tokens_out", 0),
            },
        }

    # ─── 라우팅 메서드 ──────────────────────────────────────────────

    def _to_internal_request(self, body: dict, source: APIFormat) -> dict:
        """외부 포맷 → 내부 포맷 변환 라우팅."""
        if source == APIFormat.OPENAI:
            return self._openai_to_internal_request(body)
        elif source == APIFormat.ANTHROPIC:
            return self._anthropic_to_internal_request(body)
        else:
            return body.copy()

    def _from_internal_request(self, body: dict, target: APIFormat) -> dict:
        """내부 포맷 → 외부 포맷 변환 라우팅."""
        if target == APIFormat.OPENAI:
            return self._internal_to_openai_request(body)
        elif target == APIFormat.ANTHROPIC:
            return self._internal_to_anthropic_request(body)
        else:
            return body.copy()

    def _to_internal_response(self, body: dict, source: APIFormat) -> dict:
        """외부 응답 → 내부 응답 변환 라우팅."""
        if source == APIFormat.OPENAI:
            return self._openai_to_internal_response(body)
        elif source == APIFormat.ANTHROPIC:
            return self._anthropic_to_internal_response(body)
        else:
            return body.copy()

    def _from_internal_response(self, body: dict, target: APIFormat) -> dict:
        """내부 응답 → 외부 응답 변환 라우팅."""
        if target == APIFormat.OPENAI:
            return self._internal_to_openai_response(body)
        elif target == APIFormat.ANTHROPIC:
            return self._internal_to_anthropic_response(body)
        else:
            return body.copy()

    # ─── 추가 변환 헬퍼 ─────────────────────────────────────────────

    def _internal_to_openai_request(self, body: dict) -> dict:
        """내부 포맷 → OpenAI 요청."""
        messages = []
        if body.get("system"):
            messages.append({"role": "system", "content": body["system"]})
        messages.extend(body.get("messages", []))

        result = {
            "model": body.get("model", ""),
            "messages": messages,
            "max_tokens": body.get("max_tokens", 4096),
            "temperature": body.get("temperature", 0.7),
            "stream": body.get("stream", False),
        }
        if body.get("stop"):
            result["stop"] = body["stop"]
        return result

    def _internal_to_anthropic_request(self, body: dict) -> dict:
        """내부 포맷 → Anthropic 요청."""
        result: dict[str, Any] = {
            "model": body.get("model", ""),
            "messages": body.get("messages", []),
            "max_tokens": body.get("max_tokens", 4096),
        }
        if body.get("system"):
            result["system"] = body["system"]
        if body.get("temperature") is not None:
            result["temperature"] = body["temperature"]
        if body.get("stop"):
            result["stop_sequences"] = body["stop"]
        if body.get("stream"):
            result["stream"] = True
        return result

    def _openai_to_internal_response(self, body: dict) -> dict:
        """OpenAI 응답 → 내부 포맷."""
        choices = body.get("choices", [])
        content = ""
        finish_reason = "stop"
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            finish_reason = choices[0].get("finish_reason", "stop")

        usage = body.get("usage", {})
        return {
            "content": content,
            "model": body.get("model", ""),
            "finish_reason": finish_reason,
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
        }

    def _anthropic_to_internal_response(self, body: dict) -> dict:
        """Anthropic 응답 → 내부 포맷."""
        content_blocks = body.get("content", [])
        content = ""
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "")

        usage = body.get("usage", {})
        return {
            "content": content,
            "model": body.get("model", ""),
            "finish_reason": body.get("stop_reason", "stop"),
            "tokens_in": usage.get("input_tokens", 0),
            "tokens_out": usage.get("output_tokens", 0),
        }

    # ─── 유틸 ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_content(content: Any) -> Union[str, list[dict]]:
        """메시지 content 필드 정규화.

        OpenAI는 str 또는 List[dict] (멀티모달) 형식을 지원.
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Check if there are any non-text items (e.g. image_url)
            has_multimodal = any(isinstance(item, dict) and item.get("type") != "text" for item in content)
            if has_multimodal:
                return content  # Preserve the entire list for VLM processing

            # If it's just text blocks, combine them
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(parts)
        return str(content) if content else ""
