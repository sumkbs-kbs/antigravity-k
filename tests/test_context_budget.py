from __future__ import annotations

from antigravity_k.engine.context_budget import context_budget_for_model
from antigravity_k.engine.orchestrator import OrchestratorAgent


def _config(*, context_length: int, configured_limit: int | None = None) -> dict[str, object]:
    router: dict[str, object] = {}
    if configured_limit is not None:
        router["context_token_limit"] = configured_limit
    return {
        "defaults": {"reasoning": "qwen3.6:latest"},
        "models": {
            "reasoning": [
                {
                    "name": "qwen3.6:latest",
                    "context_length": context_length,
                },
            ],
        },
        "router": router,
    }


def test_context_budget_expands_qwen_profile_without_using_its_full_window():
    budget = context_budget_for_model(_config(context_length=262_144), "qwen3.6:latest")

    assert budget.token_limit == 32_768
    assert budget.trajectory_max_messages == 128
    assert budget.trajectory_max_chars == 131_072


def test_context_budget_preserves_legacy_limit_for_an_unknown_model():
    budget = context_budget_for_model(_config(context_length=262_144), "unregistered-model")

    assert budget.token_limit == 8_000
    assert budget.trajectory_max_messages == 40
    assert budget.trajectory_max_chars == 80_000


def test_context_budget_never_exceeds_a_smaller_model_window():
    budget = context_budget_for_model(_config(context_length=16_384, configured_limit=100_000), "qwen3.6:latest")

    assert budget.token_limit == 12_288
    assert budget.trajectory_max_messages == 48
    assert budget.trajectory_max_chars == 80_000


def test_context_budget_honors_a_lower_explicit_operator_limit():
    budget = context_budget_for_model(_config(context_length=262_144, configured_limit=12_000), "qwen3.6:latest")

    assert budget.token_limit == 12_000
    assert budget.trajectory_max_messages == 46


class _Manager:
    def generate(self, **_kwargs: object) -> str:
        return "summary"


def test_orchestrator_builds_target_aware_compressors(tmp_path):
    orchestrator = OrchestratorAgent(model_manager=_Manager(), project_root=str(tmp_path))
    orchestrator.config = _config(context_length=262_144)

    context_compressor = orchestrator.context_compressor_for("qwen3.6:latest")
    trajectory_compressor = orchestrator.trajectory_compressor_for("qwen3.6:latest")

    assert context_compressor is not None
    assert context_compressor.token_limit == 32_768
    assert trajectory_compressor is not None
    assert trajectory_compressor.max_messages == 128
