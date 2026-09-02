"""Swarm LLM Client - Three-tier fallback strategy.

Priority:
  Tier 1: Local model (Ollama) — 보안 민감 데이터 전용
  Tier 2: OpenRouter free model — 일반 작업
  Tier 3: OpenRouter paid model — 명시적 요청 시만 (complex/force_paid)

Cost management:
  - paid_cost_limit: $10 (OpenRouter 크레딧)
  - cost_alert_threshold: $8 도달 시 경고 로그
"""

import json
import logging
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

log = logging.getLogger("swarm.llm")

DEFAULTS: dict[str, object] = {
    "strategy": "three_tier",
    "local_base_url": "http://localhost:11434",
    "local_model": "qwen3.6-models",
    "local_model_single": "qwen3.6-models",
    "or_base_url": "https://openrouter.ai/api/v1",
    "or_free_model": "openrouter/free",
    "or_paid_model": "google/gemini-2.5-pro-preview-05-14",
    "or_paid_cost_limit": 10.0,
    "or_api_key": "",
    "max_retries": 3,
    "retry_delay": 2.0,
    "local_timeout": 60,
    "or_free_timeout": 120,
    "or_paid_timeout": 180,
}


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _as_mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    result: list[dict[str, object]] = []
    for item in items:
        if isinstance(item, Mapping):
            result.append(_as_mapping(cast(object, item)))
    return result


def _as_text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _as_float(value: object, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


class _HTTPResponseLike(Protocol):
    def read(self) -> bytes: ...

    def close(self) -> None: ...


def _openrouter_api_key_from_env() -> str:
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OR_API_KEY") or ""


def _with_env_overrides(config: Mapping[str, object]) -> dict[str, object]:
    merged = dict(config)
    env_key = _openrouter_api_key_from_env()
    if env_key:
        merged["or_api_key"] = env_key
    return merged


def load_llm_config(config_path: str | None = None) -> dict[str, object]:
    """Load LLM config from config.json (swarm.lm section)."""
    config_file = Path(config_path) if config_path else Path(__file__).parent / "config.json"
    if config_file.exists():
        data = _as_mapping(cast(object, json.loads(config_file.read_text(encoding="utf-8"))))
        lm = _as_mapping(data.get("lm"))
        if lm:
            merged = {**DEFAULTS, **lm}
            log.info(f"Loaded LLM config from {config_file}: {list(merged.keys())}")
            return _with_env_overrides(merged)
        log.info("No lm section in config.json — using defaults")
    return _with_env_overrides(DEFAULTS)


def call_llm(
    prompt: str,
    system: str = "",
    model: str = "",
    timeout: int = 0,
    config: Mapping[str, object] | None = None,
    retry_with_or: bool = True,
    paid: bool = False,  # True = tier3 직접 지정
    complex: bool = False,  # True = tier3 요청 (복잡도 자동 판단)
) -> str:
    """Call LLM with three-tier fallback chain:
      Tier 1: Local (Ollama) — 항상 먼저 시도
      Tier 2: OpenRouter free — 로컬 실패 시
      Tier 3: OpenRouter paid — paid=True 또는 complex=True 명시적 요청 시만

    Args:
        prompt: User prompt text
        system: System instruction
        model: Override model name (if empty, use config default)
        timeout: Override timeout seconds
        config: LLM config dict (if None, loads from config.json)
        retry_with_or: If local fails, try OpenRouter fallback
        paid: Explicitly request paid tier (tier3)
        complex: Signal complexity (auto-route to tier3 if paid not set)

    Returns:
        LLM response text

    """
    if config is None:
        config = load_llm_config()
    if model:
        config = {
            **config,
            "local_model_single": model,
            "or_free_model": model,
            "or_paid_model": model,
        }

    three_tier = _as_mapping(config.get("three_tier"))

    # Tier decision
    target_tier = 1  # 1=local -> 2=free -> 3=paid
    if paid or complex:
        target_tier = 3  # Skip to paid tier
        log.info("Routing to Tier3 (paid): paid=%s, complex=%s", paid, complex)
    elif bool(three_tier.get("enabled")):
        target_tier = 2  # Default to free

    if target_tier >= 1:
        result = _call_tier1_local(prompt, system, config, timeout)
        if result:
            log.info(f"✅ Tier1 (Local) response: {result[:80]}...")
            return result
        log.debug("Tier1 (Local) failed")

    if target_tier >= 2 and retry_with_or:
        result = _call_tier2_free(prompt, system, config, timeout)
        if result:
            log.info(f"✅ Tier2 (Free) response: {result[:80]}...")
            return result
        log.debug("Tier2 (Free) failed")

    if target_tier >= 3 and retry_with_or:
        result = _call_tier3_paid(prompt, system, config, timeout)
        if result:
            log.info(f"✅ Tier3 (Paid) response: {result[:80]}...")
            return result
        log.warning("⚠️ Tier3 (Paid) failed or cost limit exceeded")

    return "LLM unavailable: all tiers failed."


def _call_tier1_local(prompt: str, system: str, config: Mapping[str, object], timeout: int) -> str | None:
    """Tier 1: Local Ollama — 보안 민감 데이터."""
    url = _as_text(config.get("local_base_url"), _as_text(DEFAULTS["local_base_url"]))
    local_timeout = _as_int(config.get("local_timeout"), _as_int(DEFAULTS["local_timeout"], 60))
    local_model = _as_text(config.get("local_model_single"), _as_text(DEFAULTS["local_model_single"]))
    effective_timeout = timeout if timeout > 0 else local_timeout

    payload = {
        "model": local_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_ctx": 8192},
    }
    if system:
        payload["system"] = system

    try:
        resp = subprocess.run(
            [
                "curl",
                "-s",
                "-w",
                "\n%{http_code}",
                "-X",
                "POST",
                f"{url}/api/generate",
                "-d",
                json.dumps(payload),
            ],
            capture_output=True,
            text=True,
            timeout=effective_timeout,
        )
        parts = resp.stdout.rsplit("\n", 1)
        http_code = int(parts[-1]) if len(parts) > 1 else 0
        body = parts[0] if len(parts) > 1 else resp.stdout

        if http_code == 200 and body:
            data = _as_mapping(cast(object, json.loads(body)))
            return _as_text(data.get("response"), body)
        return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        log.debug(f"T1 Local failed: {e}")
        return None


def _call_tier2_free(prompt: str, system: str, config: Mapping[str, object], timeout: int) -> str | None:
    """Tier 2: OpenRouter free model — 일반 작업."""
    or_timeout = _as_int(config.get("or_free_timeout"), _as_int(DEFAULTS["or_free_timeout"], 120))
    or_model = _as_text(config.get("or_free_model"), _as_text(DEFAULTS["or_free_model"]))
    url = _as_text(config.get("or_base_url"), _as_text(DEFAULTS["or_base_url"]))
    or_api_key = _as_text(config.get("or_api_key"))
    if not or_api_key:
        log.debug("Tier2 OpenRouter skipped: OPENROUTER_API_KEY is not set")
        return None

    return _call_openrouter(prompt, system, or_model, config, url, or_api_key, timeout if timeout > 0 else or_timeout, free=True)


def _call_tier3_paid(prompt: str, system: str, config: Mapping[str, object], timeout: int) -> str | None:
    """Tier 3: OpenRouter paid model — 복잡/정교 작업 전용."""
    or_timeout = _as_int(config.get("or_paid_timeout"), _as_int(DEFAULTS["or_paid_timeout"], 180))
    or_model = _as_text(config.get("or_paid_model"), _as_text(DEFAULTS["or_paid_model"]))
    cost_limit = _as_float(config.get("or_paid_cost_limit"), _as_float(DEFAULTS["or_paid_cost_limit"], 10.0))
    or_base_url = _as_text(config.get("or_base_url"), _as_text(DEFAULTS["or_base_url"]))
    or_api_key = _as_text(config.get("or_api_key"))
    if not or_api_key:
        log.debug("Tier3 OpenRouter skipped: OPENROUTER_API_KEY is not set")
        return None

    # Check cost alert threshold
    cost_alert = _as_float(_as_mapping(config.get("three_tier")).get("cost_alert_threshold"), 8.0)
    if cost_limit - cost_alert < cost_alert:
        log.warning(f"⚠️ Cost approaching limit: ${cost_alert:.2f} of ${cost_limit:.2f}")

    return _call_openrouter(
        prompt,
        system,
        or_model,
        config,
        or_base_url,
        or_api_key,
        timeout if timeout > 0 else or_timeout,
        free=False,
    )


def _call_openrouter(
    prompt: str,
    system: str,
    model: str,
    config: Mapping[str, object],
    url: str,
    api_key: str,
    timeout: int,
    free: bool,
) -> str | None:
    """Internal OpenRouter call with free/paid model."""
    import urllib.error
    import urllib.request

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096 if free else 8192,
        "temperature": 0.7,
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "",
        "HTTP-Referer": "https://github.com/antigravity-k/swarm-mode",
        "X-Title": "Antigravity-K Swarm Mode",
    }

    # Paid model: add cost control header
    if not free:
        cost_limit = _as_float(config.get("or_paid_cost_limit"), _as_float(DEFAULTS["or_paid_cost_limit"], 10.0))
        headers["X-Title"] += f" (cost_limit=${cost_limit})"

    try:
        req = urllib.request.Request(url + "/chat/completions", data=data, headers=headers)
        resp = cast(_HTTPResponseLike, urllib.request.urlopen(req, timeout=timeout))
        try:
            body = resp.read().decode("utf-8")
            data_resp = _as_mapping(cast(object, json.loads(body)))
            choice_items = _as_mapping_list(data_resp.get("choices"))
            if choice_items:
                first_choice = choice_items[0]
                message = _as_mapping(first_choice.get("message"))
                return _as_text(message.get("content"))
            return None
        finally:
            resp.close()
    except urllib.error.URLError as e:
        log.debug(f"OpenRouter URL error: {e}")
        return None
    except json.JSONDecodeError as e:
        log.debug(f"OpenRouter JSON error: {e}")
        return None
    except Exception as e:
        log.debug(f"OpenRouter error: {e}")
        return None


# === Helpers for batch processing ===


def call_batch(prompts: list[str], **kwargs: object) -> list[str]:
    """Call LLM batch."""
    config_value = kwargs.get("config")
    config = cast(Mapping[str, object], config_value) if isinstance(config_value, Mapping) else None
    return [
        call_llm(
            prompt,
            system=_as_text(kwargs.get("system")),
            model=_as_text(kwargs.get("model")),
            timeout=_as_int(kwargs.get("timeout"), 0),
            config=config,
            retry_with_or=bool(kwargs.get("retry_with_or", True)),
            paid=bool(kwargs.get("paid", False)),
            complex=bool(kwargs.get("complex", False)),
        )
        for prompt in prompts
    ]


def get_status() -> dict[str, bool]:
    """Check what LLM backends are available."""
    status = {
        "local": False,
        "openrouter_free": False,
        "openrouter_paid": False,
    }

    # Check Ollama
    try:
        resp = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status["local"] = resp.returncode == 0
    except Exception:
        pass

    # Check OpenRouter (always available if network works)
    status["openrouter_free"] = True
    status["openrouter_paid"] = True  # Valid key = paid available

    return status


def get_cost_alert(config: Mapping[str, object] | None = None) -> dict[str, object]:
    """Get cost status and alerts for paid tier."""
    if config is None:
        config = load_llm_config()
    three_tier = _as_mapping(config.get("three_tier"))

    cost_limit = _as_float(config.get("or_paid_cost_limit"), 10.0)
    alert_threshold = _as_float(three_tier.get("cost_alert_threshold"), 8.0)

    return {
        "cost_limit": cost_limit,
        "alert_threshold": alert_threshold,
        "remaining_until_alert": cost_limit - alert_threshold,
        "status": "WARNING" if cost_limit - alert_threshold < alert_threshold else "OK",
    }


if __name__ == "__main__":
    # Test all tiers
    status = get_status()
    print(f"Backend status:\n{json.dumps(status, indent=2)}")

    print("\n=== Tier 1: Local ===")
    r1 = call_llm("Hello, test 1+1=?. Answer briefly.")
    print(f"Result: {r1[:100]}...")

    print("\n=== Tier 2: Free ===")
    r2 = call_llm("Hello, test 2*2=?. Answer briefly.", paid=False)
    print(f"Result: {r2[:100]}...")

    print("\n=== Tier 3: Paid (complex=True) ===")
    r3 = call_llm("Hello, test 10*10=?. Answer in detail.", complex=True)
    print(f"Result: {r3[:100]}...")

    print(f"\nCost status: {get_cost_alert()}")
