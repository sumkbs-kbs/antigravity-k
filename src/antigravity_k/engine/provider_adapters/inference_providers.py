"""Inference Providers module."""

import json
import logging
import time
import urllib.request
from abc import ABC, abstractmethod

logger = logging.getLogger("antigravity_k.inference_providers")


class BaseInferenceProvider(ABC):
    """Baseinferenceprovider.

    Bases: ABC
    """

    @abstractmethod
    def generate(self, loaded, prompt, **kwargs) -> str:
        """Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The str result.

        """
        pass

    @abstractmethod
    def stream_generate(self, loaded, prompt, **kwargs):
        """Stream Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        """
        pass

    def _suppress_model_thinking(self, model_name: str, messages: list[dict]) -> list[dict]:
        if "qwen3" not in model_name.lower():
            return messages

        directive = (
            "/no_think\nAnswer directly. Do not output hidden reasoning, thinking traces, <think>, or <thought> blocks."
        )
        prepared = [dict(message) for message in messages]
        if prepared and prepared[0].get("role") == "system":
            content = str(prepared[0].get("content", ""))
            if "/no_think" not in content:
                prepared[0]["content"] = f"{directive}\n{content}".strip()
            return prepared

        return [{"role": "system", "content": directive}, *prepared]

    def _apply_dynamic_inference_config(self, loaded_profile, prompt_or_messages, kwargs):
        import hashlib

        model_name = loaded_profile.name
        thinking_config = None
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 8192)

        if ":" in model_name:
            base_model, spec = model_name.split(":", 1)
            budget = None

            if spec.isdigit():
                budget = max(int(spec), 1024)
            else:
                ratios = {"high": 0.8, "medium": 0.5, "low": 0.2}
                ratio = ratios.get(spec.lower())
                if ratio:
                    budget = max(int(max_tokens * ratio), 1024)

            if budget:
                thinking_config = {"type": "enabled", "budget_tokens": budget}
                temperature = 1.0
                model_name = base_model

        if isinstance(prompt_or_messages, list) and len(prompt_or_messages) > 0:
            first_user_text = str(prompt_or_messages[0].get("content", ""))
        else:
            first_user_text = str(prompt_or_messages)

        fingerprint_input = f"antigravity_k_59cf53e54c78_{first_user_text[:30]}"
        fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:6]
        attribution = f"\nx-antigravity-k-agent: id={fingerprint}; cch=00000;"

        return model_name, temperature, thinking_config, attribution


class AnthropicProvider(BaseInferenceProvider):
    """Anthropicprovider.

    Bases: BaseInferenceProvider
    """

    def generate(self, loaded, prompt, **kwargs) -> str:
        """Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The str result.

        """
        result = ""
        for chunk in self.stream_generate(loaded, prompt, **kwargs):
            result += chunk
        return result

    def stream_generate(self, loaded, prompt, **kwargs):
        """Stream Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        """
        import anthropic

        from antigravity_k.engine.secure_key import get_api_key

        api_key = get_api_key("anthropic")
        if not api_key:
            yield "[Error] Anthropic API Key not found. Run: export AGK_ANTHROPIC_KEY=sk-ant-... (or: agk key set anthropic <key>)"  # noqa: E501
            return

        client = anthropic.Anthropic(api_key=api_key)
        system_prompt = kwargs.get("system_prompt", "")
        raw_messages = kwargs.get("raw_messages", [{"role": "user", "content": prompt}])
        model_name, temperature, thinking_config, attribution = self._apply_dynamic_inference_config(
            loaded.profile, raw_messages, kwargs
        )

        anthropic_msgs = []
        for msg in raw_messages:
            if msg["role"] in ["user", "assistant"]:
                anthropic_msgs.append({"role": msg["role"], "content": msg["content"]})

        cache_blocks = []
        system_blocks = []
        if system_prompt:
            system_blocks.append(
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
            )
            cache_blocks.append(system_blocks[0])

        for msg in anthropic_msgs:
            if isinstance(msg["content"], list):
                for block in msg["content"]:
                    if isinstance(block, dict) and "cache_control" in block:
                        cache_blocks.append(block)

        if len(cache_blocks) > 4:
            keep_first = cache_blocks[0]
            keep_last = cache_blocks[-3:]
            to_keep = set([id(keep_first)] + [id(b) for b in keep_last])
            for block in cache_blocks:
                if id(block) not in to_keep:
                    del block["cache_control"]

        if system_blocks:
            system_blocks[0]["text"] += attribution
        else:
            system_blocks.append(
                {"type": "text", "text": attribution, "cache_control": {"type": "ephemeral"}},
            )

        request_params = {
            "max_tokens": kwargs.get("max_tokens", 8192),
            "system": system_blocks if system_blocks else system_prompt,
            "messages": anthropic_msgs,
            "model": model_name,
            "temperature": temperature,
        }

        if thinking_config:
            request_params["thinking"] = thinking_config

        try:
            with client.messages.stream(**request_params) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.exception("Anthropic API generation failed")
            yield f"[API Error for {model_name}] {e}"


class OpenRouterProvider(BaseInferenceProvider):
    """Openrouterprovider.

    Bases: BaseInferenceProvider
    """

    def generate(self, loaded, prompt, **kwargs) -> str:
        """Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The str result.

        """
        result = ""
        for chunk in self.stream_generate(loaded, prompt, **kwargs):
            result += chunk
        return result

    def _resolve_endpoint(self, loaded):
        """loaded.profile에서 per-model 엔드포인트와 키를 해석 (멀티 프로바이더)."""
        import os

        from antigravity_k.engine.secure_key import get_api_key

        profile = loaded.profile
        # per-model api_base 오버라이드 → OpenRouter 기본값
        base_url = getattr(profile, "api_base", "") or "https://openrouter.ai/api/v1"
        base_url = base_url.rstrip("/")

        # API 키: profile.api_key_env → OPENROUTER_API_KEY → AGK_OPENROUTER_KEY → secure_key
        key_env = getattr(profile, "api_key_env", "") or "OPENROUTER_API_KEY"
        api_key = os.environ.get(key_env) or os.environ.get("AGK_OPENROUTER_KEY") or ""
        if not api_key:
            api_key = get_api_key("openrouter") or ""
        return base_url, api_key

    def stream_generate(self, loaded, prompt, **kwargs):
        """Stream Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        """
        api_key = None
        base_url, api_key = self._resolve_endpoint(loaded)
        if not api_key:
            yield (
                "[Error] OpenRouter API Key not found. Run: export AGK_OPENROUTER_KEY=..."
                "(or: agk key set openrouter <key>)"
            )
            return

        url = f"{base_url}/chat/completions"
        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            api_msgs = (
                [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"] if sys_msg else kwargs["raw_messages"]
            )
        else:
            api_msgs = [{"role": "user", "content": prompt}]

        model_name, temperature, _, _ = self._apply_dynamic_inference_config(
            loaded.profile,
            api_msgs,
            kwargs,
        )
        model_id = getattr(loaded.profile, "repo", "") or model_name
        if model_id.startswith("openrouter/"):
            model_id = model_id[len("openrouter/") :]

        data = {
            "model": model_id,
            "messages": api_msgs,
            "stream": True,
            "temperature": temperature,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        # 네이티브 function calling 지원 (P1-1): tools 스키마가 제공되면 전송
        tools_schema = kwargs.get("tools")
        if tools_schema and isinstance(tools_schema, list):
            data["tools"] = tools_schema
            # tool_choice: "auto" (모델이 자동 판단)
            data["tool_choice"] = kwargs.get("tool_choice", "auto")

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/ssak-comp/antigravity-k",
                "X-Title": "Antigravity-K",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                # 네이티브 tool_call 누적 버퍼 (스트리밍 tool_calls 조립용)
                pending_tool_calls: dict[int, dict] = {}
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0].get("delta", {})
                            # 1. 일반 텍스트 content
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                            # 2. 네이티브 tool_calls 누적 (P1-1)
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in pending_tool_calls:
                                        pending_tool_calls[idx] = {
                                            "id": tc.get("id", ""),
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    func = tc.get("function", {})
                                    if func.get("name"):
                                        pending_tool_calls[idx]["function"]["name"] += func["name"]
                                    if func.get("arguments"):
                                        pending_tool_calls[idx]["function"]["arguments"] += func["arguments"]
                            # 3. finish_reason이 tool_calls면 조립된 tool_call을 이벤트로 yield
                            finish_reason = chunk["choices"][0].get("finish_reason")
                            if finish_reason == "tool_calls" and pending_tool_calls:
                                for idx in sorted(pending_tool_calls):
                                    tc = pending_tool_calls[idx]
                                    # 표준 XML 도구 호출 포맷으로 변환하여 ToolCallParser가 처리하도록
                                    tool_event = (
                                        f"\n<tool_call>\n"
                                        f"{json.dumps({'name': tc['function']['name'], 'arguments': json.loads(tc['function']['arguments'] or '{}')}, ensure_ascii=False)}\n"
                                        f"</tool_call>\n"
                                    )
                                    yield tool_event
                                pending_tool_calls.clear()
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.exception("OpenRouter API stream failed")
            yield f"[API Error for {loaded.profile.name}] {e}"


class OllamaProvider(BaseInferenceProvider):
    """Ollamaprovider.

    Bases: BaseInferenceProvider
    """

    def _resolve_endpoint(self, loaded):
        """loaded.profile에서 per-model Ollama 엔드포인트와 키를 해석 (멀티 프로바이더)."""
        import os

        from antigravity_k.config import config

        profile = loaded.profile
        # per-model api_base → registry providers 섹션 → 전역 config 폴백
        base_url = getattr(profile, "api_base", "") or ""
        api_key = ""
        if base_url:
            key_env = getattr(profile, "api_key_env", "") or "OLLAMA_API_KEY"
            api_key = os.environ.get(key_env, "") or "ollama"
        else:
            # registry에서 provider 기본 base_url 조회
            try:
                base_url = self._registry_provider_base("ollama") or config.model.api_base
            except Exception:
                base_url = config.model.api_base
            api_key = os.environ.get("OLLAMA_API_KEY", "") or config.model.api_key or "ollama"

        # Ollama OpenAI 호환 엔드포인트는 /v1 접미사 필수 — 누락 시 자동 추가
        # (registry providers 섹션의 base_url이 http://localhost:11434 형태일 수 있음)
        base_url = base_url.rstrip("/")
        if "/v1" not in base_url and ":11434" in base_url:
            base_url = base_url + "/v1"

        return base_url, api_key

    @staticmethod
    def _registry_provider_base(provider: str) -> str:
        """ModelRegistry의 providers 섹션에서 base_url을 조회합니다."""
        try:
            from antigravity_k.engine.model_registry import ModelRegistry

            registry = ModelRegistry()
            prov_cfg = registry.get_provider_config(provider)
            return prov_cfg.get("base_url", "")
        except Exception:
            return ""

    def generate(self, loaded, prompt, **kwargs) -> str:
        """Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The str result.

        """
        from antigravity_k.engine.sampling_config import SAMPLING_PROFILES

        base_url, api_key = self._resolve_endpoint(loaded)
        url = f"{base_url}/chat/completions"

        task_type = kwargs.get("task_type", "GENERAL")
        profile = SAMPLING_PROFILES.get(task_type, SAMPLING_PROFILES["GENERAL"])
        temperature = kwargs.get("temperature", profile.temperature)
        min_p = kwargs.get("min_p", profile.min_p)
        repeat_penalty = kwargs.get("repeat_penalty", profile.repeat_penalty)

        data = {
            "model": loaded.profile.name,
            "stream": False,
            "temperature": temperature,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "repeat_penalty": repeat_penalty,
            "options": {"min_p": min_p},
        }

        json_schema = kwargs.get("response_format")
        if json_schema:
            data["format"] = json_schema

        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            if sys_msg:
                api_msgs = [{"role": "system", "content": sys_msg}] + list(kwargs["raw_messages"])
            else:
                api_msgs = list(kwargs["raw_messages"])
        else:
            api_msgs = [{"role": "user", "content": prompt}]

        api_msgs = self._suppress_model_thinking(loaded.profile.name, api_msgs)
        data["messages"] = api_msgs

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
                message = result["choices"][0]["message"]
                content = message.get("content", "")
                # qwen3.6 등 thinking 모델은 content가 비고 reasoning/thinking에 담길 수 있음
                # — reasoning을 content로 승격 (비어 있을 때만)
                if not content:
                    reasoning = message.get("reasoning") or message.get("thinking") or ""
                    if reasoning:
                        # reasoning이 아직 진행 중이면 (완결된 content가 없음) 빈 응답 방지
                        content = reasoning.strip()
                return content
        except Exception as e:
            logger.exception("Local API generation failed")
            return f"[API Error for {loaded.profile.name}] {e}"

    def stream_generate(self, loaded, prompt, **kwargs):
        """Stream Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        """
        base_url, api_key = self._resolve_endpoint(loaded)
        # Ollama Native API (/api/chat) — /v1 접미사 정규화
        import re

        native_base = re.sub(r"/v\d+$", "", base_url)
        url = f"{native_base}/api/chat"

        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            if sys_msg:
                api_msgs = [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"]
            else:
                api_msgs = kwargs["raw_messages"]
        else:
            if isinstance(prompt, list):
                api_msgs = prompt
            else:
                api_msgs = [{"role": "user", "content": prompt}]

        normalized_msgs = []
        for msg in api_msgs:
            content = msg.get("content", "")
            if isinstance(content, list):
                str_content = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        str_content.append(part.get("text", ""))
                    elif isinstance(part, str):
                        str_content.append(part)
                content = " ".join(str_content)
            normalized_msgs.append({**msg, "content": content})
        api_msgs = normalized_msgs

        api_msgs = self._suppress_model_thinking(loaded.profile.name, api_msgs)
        model_name, temperature, _, attribution = self._apply_dynamic_inference_config(
            loaded.profile,
            api_msgs,
            kwargs,
        )

        if api_msgs and isinstance(api_msgs[0].get("content"), str):
            api_msgs = list(api_msgs)
            api_msgs[0] = {**api_msgs[0], "content": api_msgs[0]["content"] + f"\n{attribution}"}

        data = {
            "model": model_name,
            "stream": True,
            "keep_alive": "30m",
            "think": False,  # qwen3.6 등 thinking 모델의 빈 content 스트리밍 방지
            "options": {
                "num_ctx": 32768,
                "num_predict": kwargs.get("max_tokens", 4096),
                "temperature": temperature,
                "repeat_penalty": 1.3,
            },
            "messages": api_msgs,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        try:
            in_reasoning = False
            with urllib.request.urlopen(req, timeout=300) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk:
                            msg = chunk["message"]
                            if "content" in msg and msg["content"]:
                                if in_reasoning:
                                    in_reasoning = False
                                yield msg["content"]
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.exception("Local API stream failed")
            yield f"[API Error for {loaded.profile.name}] {e}"


class NimProvider(BaseInferenceProvider):
    """NVIDIA NIM (build.nvidia.com) 프로바이더.

    OpenAI 호환 엔드포인트(https://integrate.api.nvidia.com/v1)를 사용하므로
    OpenRouterProvider와 유사한 SSE 스트리밍 로직을 사용하지만,
    NIM 고유의 설정(무료 rate limit 40rpm, 별도 헤더)을 갖습니다.
    """

    # NIM 무료 티어 rate limit: 분당 40 요청 (초당 약 0.67)
    _RATE_LIMIT_RPM = 40
    _RATE_LIMIT_WINDOW_SEC = 60.0

    def __init__(self):
        """Initialize the NimProvider — 분당 rate 카운터 초기화."""
        self._request_timestamps: list[float] = []

    def _check_rate_limit(self) -> bool:
        """분당 rate limit 내인지 확인. 초과 시 False 반환.

        호출 시마다 타임스탬프를 기록하고, 최근 60초 창의 요청 수가
        _RATE_LIMIT_RPM을 초과하면 False 반환 (라우터가 다른 폴백으로 전환 유도).
        """
        now = time.time()
        cutoff = now - self._RATE_LIMIT_WINDOW_SEC
        self._request_timestamps = [t for t in self._request_timestamps if t > cutoff]
        if len(self._request_timestamps) >= self._RATE_LIMIT_RPM:
            return False
        self._request_timestamps.append(now)
        return True

    def _resolve_endpoint(self, loaded):
        """loaded.profile과 registry에서 NIM 엔드포인트와 API 키를 해석합니다."""
        import os

        profile = loaded.profile
        # per-model 오버라이드 → registry providers 섹션 → 환경변수 순서
        base_url = getattr(profile, "api_base", "") or "https://integrate.api.nvidia.com/v1"
        base_url = base_url.rstrip("/")

        # API 키: profile.api_key_env → NVIDIA_API_KEY 환경변수
        key_env = getattr(profile, "api_key_env", "") or "NVIDIA_API_KEY"
        api_key = os.environ.get(key_env, "")
        if not api_key:
            # secure_key vault 폴백
            try:
                from antigravity_k.engine.secure_key import get_api_key

                api_key = get_api_key("nim") or get_api_key("nvidia") or ""
            except Exception:
                api_key = ""

        return base_url, api_key

    def generate(self, loaded, prompt, **kwargs) -> str:
        """Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The str result.

        """
        if not self._check_rate_limit():
            return "[API Error for NIM] rate limit(40rpm) 초과 — 잠시 후 재시도하거나 다른 모델로 폴백하세요."
        result = ""
        for chunk in self.stream_generate(loaded, prompt, **kwargs):
            result += chunk
        return result

    def stream_generate(self, loaded, prompt, **kwargs):
        """Stream Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        """
        base_url, api_key = self._resolve_endpoint(loaded)
        if not api_key:
            yield (
                "[Error] NVIDIA NIM API Key not found. "
                "build.nvidia.com에서 무료 키를 발급받아 NVIDIA_API_KEY 환경변수로 설정하세요."
            )
            return

        if not self._check_rate_limit():
            yield "[API Error for NIM] rate limit(40rpm) 초과 — 다른 폴백 모델로 전환 권장."
            return

        url = f"{base_url}/chat/completions"

        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            api_msgs = (
                [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"] if sys_msg else kwargs["raw_messages"]
            )
        else:
            if isinstance(prompt, list):
                api_msgs = prompt
            else:
                api_msgs = [{"role": "user", "content": prompt}]

        # 메시지 정규화 (string content 보장)
        normalized = []
        for msg in api_msgs:
            content = msg.get("content", "")
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        parts.append(part)
                content = " ".join(parts)
            normalized.append({**msg, "content": content})
        api_msgs = self._suppress_model_thinking(loaded.profile.name, normalized)

        model_name, temperature, _, _ = self._apply_dynamic_inference_config(loaded.profile, api_msgs, kwargs)
        # NIM 모델명은 이미 "nvidia/..." 또는 "meta/..." 형태 — 그대로 사용

        data = {
            "model": model_name,
            "messages": api_msgs,
            "stream": True,
            "temperature": temperature,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        # 네이티브 function calling 지원 (P1-1)
        tools_schema = kwargs.get("tools")
        if tools_schema and isinstance(tools_schema, list):
            data["tools"] = tools_schema
            data["tool_choice"] = kwargs.get("tool_choice", "auto")

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Accept": "text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                pending_tool_calls: dict[int, dict] = {}
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                            # 네이티브 tool_calls 누적 (P1-1)
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in pending_tool_calls:
                                        pending_tool_calls[idx] = {
                                            "id": tc.get("id", ""),
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    func = tc.get("function", {})
                                    if func.get("name"):
                                        pending_tool_calls[idx]["function"]["name"] += func["name"]
                                    if func.get("arguments"):
                                        pending_tool_calls[idx]["function"]["arguments"] += func["arguments"]
                            finish_reason = chunk["choices"][0].get("finish_reason")
                            if finish_reason == "tool_calls" and pending_tool_calls:
                                for idx in sorted(pending_tool_calls):
                                    tc = pending_tool_calls[idx]
                                    tool_event = (
                                        f"\n<tool_call>\n"
                                        f"{json.dumps({'name': tc['function']['name'], 'arguments': json.loads(tc['function']['arguments'] or '{}')}, ensure_ascii=False)}\n"
                                        f"</tool_call>\n"
                                    )
                                    yield tool_event
                                pending_tool_calls.clear()
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.exception("NVIDIA NIM API stream failed")
            yield f"[API Error for {loaded.profile.name}] {e}"


class OpenAIDirectProvider(OpenRouterProvider):
    """OpenAI 직접 API provider (api.openai.com).

    OpenRouterProvider와 동일한 OpenAI 호환 프로토콜을 사용하지만,
    base_url이 https://api.openai.com/v1 이고 OPENAI_API_KEY를 사용.
    HTTP-Referer/X-Title 헤더 없음.
    """

    def _resolve_endpoint(self, loaded):
        """OpenAI 직접 엔드포인트와 키를 해석."""
        import os

        profile = loaded.profile
        base_url = getattr(profile, "api_base", "") or "https://api.openai.com/v1"
        base_url = base_url.rstrip("/")

        key_env = getattr(profile, "api_key_env", "") or "OPENAI_API_KEY"
        api_key = os.environ.get(key_env, "")
        if not api_key:
            try:
                from antigravity_k.engine.secure_key import get_api_key

                api_key = get_api_key("openai") or ""
            except Exception:
                api_key = ""
        return base_url, api_key

    def stream_generate(self, loaded, prompt, **kwargs):
        """OpenAI 직접 스트리밍 (HTTP-Referer 헤더 없음)."""
        base_url, api_key = self._resolve_endpoint(loaded)
        if not api_key:
            # provider별 적절한 키 환경변수명 표시
            provider_name = getattr(loaded.profile, "provider", "openai")
            key_hints = {
                "openai": "OPENAI_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "zai": "ZAI_API_KEY",
            }
            key_hint = key_hints.get(provider_name, "OPENAI_API_KEY")
            yield f"[Error] {provider_name.upper()} API Key not found. {key_hint} 환경변수를 설정하세요."
            return

        # 부모의 stream_generate를 사용하되 endpoint만 오버라이드
        # OpenRouterProvider는 _resolve_endpoint를 호출하므로 상속으로 충분
        # 단 헤더에서 HTTP-Referer 제거를 위해 직접 처리
        import json
        import urllib.request

        if "raw_messages" in kwargs:
            sys_msg = kwargs.get("system_prompt", "")
            api_msgs = (
                [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"] if sys_msg else kwargs["raw_messages"]
            )
        else:
            api_msgs = [{"role": "user", "content": prompt}] if not isinstance(prompt, list) else prompt

        model_name, temperature, _, _ = self._apply_dynamic_inference_config(loaded.profile, api_msgs, kwargs)

        data = {
            "model": model_name,
            "messages": api_msgs,
            "stream": True,
            "temperature": temperature,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        tools_schema = kwargs.get("tools")
        if tools_schema and isinstance(tools_schema, list):
            data["tools"] = tools_schema
            data["tool_choice"] = kwargs.get("tool_choice", "auto")

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                pending_tool_calls: dict[int, dict] = {}
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in pending_tool_calls:
                                        pending_tool_calls[idx] = {
                                            "id": tc.get("id", ""),
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    func = tc.get("function", {})
                                    if func.get("name"):
                                        pending_tool_calls[idx]["function"]["name"] += func["name"]
                                    if func.get("arguments"):
                                        pending_tool_calls[idx]["function"]["arguments"] += func["arguments"]
                            finish_reason = chunk["choices"][0].get("finish_reason")
                            if finish_reason == "tool_calls" and pending_tool_calls:
                                for idx in sorted(pending_tool_calls):
                                    tc = pending_tool_calls[idx]
                                    yield f"\n<tool_call>\n{json.dumps({'name': tc['function']['name'], 'arguments': json.loads(tc['function']['arguments'] or '{}')}, ensure_ascii=False)}\n</tool_call>\n"
                                pending_tool_calls.clear()
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.exception("OpenAI direct API stream failed")
            yield f"[API Error for {loaded.profile.name}] {e}"


class GeminiProvider(OpenAIDirectProvider):
    """Google Gemini 직접 API provider (OpenAI 호환 엔드포인트).

    Google는 OpenAI 호환 엔드포인트를 제공하므로 OpenAIDirectProvider와 유사.
    base_url: https://generativelanguage.googleapis.com/v1beta/openai
    """

    def _resolve_endpoint(self, loaded):
        import os

        profile = loaded.profile
        base_url = getattr(profile, "api_base", "") or "https://generativelanguage.googleapis.com/v1beta/openai"
        base_url = base_url.rstrip("/")
        key_env = getattr(profile, "api_key_env", "") or "GEMINI_API_KEY"
        api_key = os.environ.get(key_env, "")
        if not api_key:
            try:
                from antigravity_k.engine.secure_key import get_api_key

                api_key = get_api_key("gemini") or ""
            except Exception:
                api_key = ""
        return base_url, api_key


class ZaiProvider(OpenAIDirectProvider):
    """ZAI/Zhipu GLM 직접 API provider.

    Zhipu BigModel은 OpenAI 호환 API를 제공.
    base_url: https://open.bigmodel.cn/api/paas/v4
    """

    def _resolve_endpoint(self, loaded):
        import os

        profile = loaded.profile
        base_url = getattr(profile, "api_base", "") or "https://open.bigmodel.cn/api/paas/v4"
        base_url = base_url.rstrip("/")
        key_env = getattr(profile, "api_key_env", "") or "ZAI_API_KEY"
        api_key = os.environ.get(key_env, "")
        if not api_key:
            try:
                from antigravity_k.engine.secure_key import get_api_key

                api_key = get_api_key("zai") or ""
            except Exception:
                api_key = ""
        return base_url, api_key


class MlxProvider(BaseInferenceProvider):
    def generate(self, loaded, prompt, **kwargs) -> str:
        """Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The str result.

        """
        try:
            from mlx_lm import generate as mlx_generate

            max_tokens = kwargs.get("max_tokens", 1024)
            return mlx_generate(
                model=loaded.model,
                tokenizer=loaded.tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
            )
        except ImportError:
            return f"[Simulated MLX] {loaded.profile.name} processed: {prompt[:30]}"

    def stream_generate(self, loaded, prompt, **kwargs):
        """Stream Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        """
        try:
            from mlx_lm import stream_generate as mlx_stream_generate

            max_tokens = kwargs.get("max_tokens", 1024)
            yield from mlx_stream_generate(
                model=loaded.model,
                tokenizer=loaded.tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
            )
        except ImportError:
            words = f"[Simulated MLX Stream] {loaded.profile.name} processed: {prompt[:30]}".split()
            for word in words:
                time.sleep(0.05)
                yield word + " "


def get_inference_provider(loaded) -> BaseInferenceProvider:
    """loaded.profile.provider 기반으로 적절한 추론 프로바이더를 반환합니다.

    우선순위 (작업 2):
      1. profile.provider 명시적 값 (ollama/openrouter/nim/anthropic/mlx)
      2. 취약한 이름 휴리스틱 폴백 (레거시 호환)
      3. 전역 config.model.api_engine

    Args:
        loaded: LoadedModel 인스턴스 (profile, model, tokenizer 포함).

    Returns:
        BaseInferenceProvider: 해당 모델을 처리할 프로바이더.
    """
    import platform

    from antigravity_k.config import config

    profile = loaded.profile
    provider = (getattr(profile, "provider", "") or "").lower()

    # 1. 명시적 provider 필드 우선 (멀티 프로바이더 핵심)
    if provider == "nim":
        return NimProvider()
    if provider == "openrouter":
        return OpenRouterProvider()
    if provider == "ollama":
        return OllamaProvider()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "openai":
        return OpenAIDirectProvider()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "zai":
        return ZaiProvider()
    if provider == "mlx":
        return MlxProvider()

    # 2. 레거시 휴리스틱 폴백 (provider 필드가 빈 경우)
    if profile.name.startswith("claude") and "anthropic/" not in (profile.repo or "").lower():
        return AnthropicProvider()
    if (profile.repo or "").startswith("openrouter/"):
        return OpenRouterProvider()
    # NIM 카탈로그 식별자 휴리스틱
    name_lower = (profile.name or "").lower()
    if name_lower.startswith("nvidia/") or name_lower.startswith("deepseek-ai/"):
        return NimProvider()

    # 3. 전역 config 기반 폴백
    engine = (config.model.api_engine or "").lower()
    if engine == "openrouter":
        return OpenRouterProvider()
    if engine == "nim":
        return NimProvider()

    if config.model.force_api or platform.system() != "Darwin" or type(loaded.model).__name__ == "_OllamaModel":
        return OllamaProvider()

    return MlxProvider()
