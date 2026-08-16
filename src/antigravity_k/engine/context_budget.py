from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

DEFAULT_CONTEXT_TOKEN_LIMIT: Final = 8_000
MAX_CONTEXT_TOKEN_LIMIT: Final = 32_768
MAX_TRAJECTORY_MESSAGES: Final = 128
LEGACY_TRAJECTORY_MAX_CHARS: Final = 80_000
RESPONSE_RESERVE_TOKENS: Final = 4_096


@dataclass(frozen=True, slots=True)
class ContextBudget:
    token_limit: int
    trajectory_max_messages: int
    trajectory_max_chars: int


def context_budget_for_model(config: Mapping[str, object], model_name: str) -> ContextBudget:
    context_length = _model_context_length(config, model_name)
    return context_budget_for_context_length(context_length, _configured_token_limit(config))


def context_budget_for_context_length(
    context_length: object,
    configured_token_limit: object = None,
) -> ContextBudget:
    resolved_context_length = _positive_int(context_length)
    if resolved_context_length is None:
        return _budget_from_token_limit(DEFAULT_CONTEXT_TOKEN_LIMIT)

    model_limit = _input_limit_for_context(resolved_context_length)
    configured_limit = _positive_int(configured_token_limit)
    token_limit = min(model_limit, configured_limit) if configured_limit is not None else model_limit
    return _budget_from_token_limit(token_limit)


def _model_context_length(config: Mapping[str, object], model_name: str) -> int | None:
    models = config.get("models")
    if not isinstance(models, Mapping):
        return None

    for profiles in models.values():
        if not isinstance(profiles, list):
            continue
        for profile in profiles:
            if not isinstance(profile, Mapping) or profile.get("name") != model_name:
                continue
            return _positive_int(profile.get("context_length"))
    return None


def _configured_token_limit(config: Mapping[str, object]) -> int | None:
    router = config.get("router")
    if not isinstance(router, Mapping):
        return None
    return _positive_int(router.get("context_token_limit"))


def _input_limit_for_context(context_length: int) -> int:
    response_reserve = min(RESPONSE_RESERVE_TOKENS, max(1_024, context_length // 4))
    return min(MAX_CONTEXT_TOKEN_LIMIT, max(1_024, context_length - response_reserve))


def _budget_from_token_limit(token_limit: int) -> ContextBudget:
    return ContextBudget(
        token_limit=token_limit,
        trajectory_max_messages=max(40, min(MAX_TRAJECTORY_MESSAGES, token_limit // 256)),
        trajectory_max_chars=max(LEGACY_TRAJECTORY_MAX_CHARS, token_limit * 4),
    )


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None
