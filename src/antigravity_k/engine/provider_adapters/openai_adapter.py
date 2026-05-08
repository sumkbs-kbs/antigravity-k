from typing import Dict, Any
from .base_adapter import BaseProviderAdapter
import json


class OpenAIAdapter(BaseProviderAdapter):
    """
    OpenRouter, DeepSeek, Ollama 등 OpenAI Chat Completions 형식을
    사용하는 엔드포인트를 위한 범용 어댑터.
    """

    def translate_request(self, anthropic_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Anthropic -> OpenAI 형식 변환 (Tool Use 포함)"""
        openai_payload = {
            "model": anthropic_payload.get("model", ""),
            "messages": [],
            "temperature": anthropic_payload.get("temperature", 0.7),
        }

        # 1. System Prompt 변환
        if "system" in anthropic_payload:
            system_text = anthropic_payload["system"]
            if isinstance(system_text, list):
                system_text = "".join(
                    b["text"] for b in system_text if b["type"] == "text"
                )
            openai_payload["messages"].append(
                {"role": "system", "content": system_text}
            )

        # 2. Messages 변환
        for msg in anthropic_payload.get("messages", []):
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                openai_payload["messages"].append({"role": role, "content": content})
            elif isinstance(content, list):
                # 멀티모달 및 툴 사용 블록 처리
                text_parts = []
                for block in content:
                    if block["type"] == "text":
                        text_parts.append(block["text"])
                    elif block["type"] == "tool_use":
                        # OpenAI tool_calls 변환 로직 (간소화)
                        pass
                    elif block["type"] == "tool_result":
                        # OpenAI tool_response 변환 로직 (간소화)
                        pass
                if text_parts:
                    openai_payload["messages"].append(
                        {"role": role, "content": "".join(text_parts)}
                    )

        # 3. Tools 변환 (Anthropic Tools -> OpenAI Functions/Tools)
        if "tools" in anthropic_payload:
            openai_payload["tools"] = []
            for tool in anthropic_payload["tools"]:
                openai_payload["tools"].append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {}),
                        },
                    }
                )

        return openai_payload

    def translate_response(self, provider_response: Dict[str, Any]) -> Dict[str, Any]:
        """OpenAI -> Anthropic 형식 복구"""
        if "choices" not in provider_response or not provider_response["choices"]:
            return provider_response  # Error or unknown

        choice = provider_response["choices"][0]
        message = choice.get("message", {})

        anthropic_response = {
            "id": provider_response.get("id", "msg_unknown"),
            "type": "message",
            "role": message.get("role", "assistant"),
            "model": provider_response.get("model", "unknown"),
            "content": [],
        }

        # 1. 일반 텍스트 및 <think> 태그 처리
        if message.get("content"):
            text = message["content"]
            anthropic_response["content"].append({"type": "text", "text": text})

        # 2. Tool Calls 복원
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                if tc["type"] == "function":
                    anthropic_response["content"].append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"]),
                        }
                    )

        return anthropic_response

    def translate_stream(self, provider_chunk: Dict[str, Any]) -> Dict[str, Any]:
        # 간소화된 스트리밍 변환
        return provider_chunk
