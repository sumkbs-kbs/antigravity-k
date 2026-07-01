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

    def stream_generate(self, loaded, prompt, **kwargs):
        """Stream Generate.

        Args:
            loaded: loaded.
            prompt: prompt.
            **kwargs: Additional keyword arguments.

        """
        from antigravity_k.engine.secure_key import get_api_key

        api_key = get_api_key("openrouter")
        if not api_key:
            yield (
                "[Error] OpenRouter API Key not found. Run: export AGK_OPENROUTER_KEY=..."
                "(or: agk key set openrouter <key>)"
            )
            return

        url = "https://openrouter.ai/api/v1/chat/completions"
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
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.exception("OpenRouter API stream failed")
            yield f"[API Error for {loaded.profile.name}] {e}"


class OllamaProvider(BaseInferenceProvider):
    """Ollamaprovider.

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
        from antigravity_k.config import config
        from antigravity_k.engine.sampling_config import SAMPLING_PROFILES

        base_url = config.model.api_base.rstrip("/")
        url = f"{base_url}/chat/completions"
        api_key = config.model.api_key

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
                if not content and message.get("thinking"):
                    raise RuntimeError("model returned hidden thinking without final content")
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
        from antigravity_k.config import config

        base_url = config.model.api_base.rstrip("/")
        url = f"{base_url.replace('/v1', '')}/api/chat"
        api_key = config.model.api_key

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


class MlxProvider(BaseInferenceProvider):
    """Mlxprovider.

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
    """Retrieve inference provider.

    Args:
        loaded: loaded.

    Returns:
        BaseInferenceProvider: The baseinferenceprovider result.

    """
    import platform

    from antigravity_k.config import config

    if loaded.profile.name.startswith("claude"):
        return AnthropicProvider()
    if loaded.profile.repo.startswith("openrouter/"):
        return OpenRouterProvider()

    if config.model.force_api or platform.system() != "Darwin" or type(loaded.model).__name__ == "_OllamaModel":
        return OllamaProvider()

    return MlxProvider()
