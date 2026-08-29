from __future__ import annotations

import importlib.util
from collections.abc import Iterator, Mapping
from typing import Any

from .inference_providers import BaseInferenceProvider, Prompt


class TransformersProvider(BaseInferenceProvider):
    def generate(self, loaded: Any, prompt: Prompt, **kwargs: Any) -> str:
        tokenizer = loaded.tokenizer
        model = loaded.model
        encoded = tokenizer(prompt, return_tensors="pt")
        encoded = _move_inputs_to_model_device(encoded, model)
        input_ids = encoded["input_ids"]
        generation: dict[str, Any] = {
            "max_new_tokens": int(kwargs.get("max_tokens", 8192)),
            "do_sample": float(kwargs.get("temperature", 0.7)) > 0,
        }
        execution_plan = kwargs.get("execution_plan")
        if isinstance(execution_plan, Mapping) and execution_plan.get("native_attention_enabled") is True:
            generation["use_cache"] = True
            if execution_plan.get("kv_cache_compression_enabled") is True and _quantized_cache_is_available(model):
                generation["cache_implementation"] = "quantized"
        if generation["do_sample"]:
            generation["temperature"] = float(kwargs.get("temperature", 0.7))
        generated = model.generate(**encoded, **generation)
        prompt_length = _sequence_length(input_ids)
        return str(tokenizer.decode(generated[0][prompt_length:], skip_special_tokens=True))

    def stream_generate(self, loaded: Any, prompt: Prompt, **kwargs: Any) -> Iterator[str]:
        text = self.generate(loaded, prompt, **kwargs)
        chunk_size = max(1, int(kwargs.get("stream_chunk_size", 256)))
        for start in range(0, len(text), chunk_size):
            yield text[start : start + chunk_size]


def _sequence_length(input_ids: Any) -> int:
    if hasattr(input_ids, "shape"):
        return int(input_ids.shape[-1])
    return len(input_ids[0])


def _move_inputs_to_model_device(encoded: Any, model: Any) -> Any:
    try:
        device = next(model.parameters()).device
    except (AttributeError, StopIteration):
        return encoded

    if not hasattr(encoded, "items"):
        return encoded
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in encoded.items()}


def _quantized_cache_is_available(model: Any) -> bool:
    generation_config = getattr(model, "generation_config", None)
    if generation_config is None or not hasattr(generation_config, "cache_implementation"):
        return False
    return any(_module_is_available(module) for module in ("optimum.quanto", "hqq"))


def _module_is_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False
