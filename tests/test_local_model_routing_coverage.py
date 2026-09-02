from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Protocol, cast
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.autonomous_qa import AutonomousQAEngine, UIDefect
from antigravity_k.engine.curriculum_generator import CurriculumGenerator, DatasetIngestor
from antigravity_k.engine.evolution import EvolutionManager
from antigravity_k.engine.tdd_engine import OmniTDDEngine
from antigravity_k.tools.system_tools import NaturalLanguageBashTool


class _CallInfo(Protocol):
    args: tuple[object, ...]
    kwargs: Mapping[str, object]


class _MockMethod(Protocol):
    called: bool
    call_args: _CallInfo | None

    def __call__(self, *args: object, **kwargs: object) -> object: ...

    def assert_called_once(self) -> None: ...

    def assert_called_once_with(self, *args: object, **kwargs: object) -> None: ...


def _mock_method(owner: object, name: str, return_value: object | None = None) -> _MockMethod:
    method = cast(_MockMethod, MagicMock())
    if return_value is not None:
        setattr(method, "return_value", return_value)
    setattr(owner, name, method)
    return method


def _call_kwargs(method: _MockMethod) -> Mapping[str, object]:
    call_args = method.call_args
    assert call_args is not None
    return call_args.kwargs


def _call_first_arg(method: _MockMethod) -> object:
    call_args = method.call_args
    assert call_args is not None
    return call_args.args[0]


def _call_llm(instance: object, prompt: str, model: str) -> str:
    method = cast(Callable[[str, str], str], getattr(instance, "_call_llm"))
    return method(prompt, model)


def _analyze_schema(instance: object, schema: dict[str, str]) -> dict[str, str]:
    method = cast(Callable[[dict[str, str]], dict[str, str]], getattr(instance, "_analyze_schema_with_llm"))
    return method(schema)


def test_curriculum_generation_uses_model_manager(tmp_path: Path) -> None:
    manager = MagicMock()
    target_method = _mock_method(manager, "get_target_for_role", "local-curriculum")
    generate_method = _mock_method(manager, "generate", '{"requirement":"x","pytest_code":"pass"}')

    generator = CurriculumGenerator(project_root=str(tmp_path), model_manager=manager)

    assert _call_llm(generator, "make a challenge", "legacy-model") == '{"requirement":"x","pytest_code":"pass"}'
    generate_method.assert_called_once_with(
        "make a challenge",
        target="local-curriculum",
        max_tokens=1024,
        temperature=0.4,
    )
    target_method.assert_called_once_with("curriculum", default_role="reasoning")


def test_dataset_schema_uses_model_manager(tmp_path: Path) -> None:
    manager = MagicMock()
    _ = _mock_method(manager, "get_target_for_role", "local-schema")
    generate_method = _mock_method(
        manager,
        "generate",
        '{"prompt_col":"question","test_col":"tests","ground_truth_col":"answer"}',
    )

    ingestor = DatasetIngestor(str(tmp_path), "http://ollama", model_manager=manager)

    mapping = _analyze_schema(ingestor, {"question": "x", "tests": "y", "answer": "z"})

    assert mapping == {"prompt_col": "question", "test_col": "tests", "ground_truth_col": "answer"}
    generate_method.assert_called_once()
    assert _call_kwargs(generate_method)["target"] == "local-schema"


def test_natural_language_bash_uses_role_target_and_interpolates_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = MagicMock()
    target_method = _mock_method(manager, "get_target_for_role", "local-coding")
    orchestrator = MagicMock()
    run_sync_method = _mock_method(orchestrator, "run_sync", "printf ok")
    completed = MagicMock(stdout="ok", stderr="")

    def fake_manager(*, registry: object) -> object:
        _ = registry
        return manager

    def fake_registry() -> object:
        return MagicMock()

    def fake_orchestrator(*, model_manager: object) -> object:
        _ = model_manager
        return orchestrator

    def fake_run(*_args: object, **_kwargs: object) -> object:
        return completed

    monkeypatch.setattr("antigravity_k.engine.model_manager.ModelManager", fake_manager)
    monkeypatch.setattr("antigravity_k.engine.model_registry.ModelRegistry", fake_registry)
    monkeypatch.setattr("antigravity_k.engine.orchestrator.OrchestratorAgent", fake_orchestrator)
    monkeypatch.setattr("antigravity_k.tools.system_tools.subprocess.run", fake_run)

    result = NaturalLanguageBashTool().execute(intent="list project files")

    assert "Executed Command" in result
    target_method.assert_called_once_with("natural_language_bash", default_role="coding")
    prompt = cast(str, cast(list[dict[str, object]], _call_first_arg(run_sync_method))[0]["content"])
    assert "list project files" in prompt
    assert _call_kwargs(run_sync_method)["target_model"] == "local-coding"


def test_evolution_resolves_default_target_through_manager():
    manager = MagicMock()
    target_method = _mock_method(manager, "get_target_for_role", "local-reasoning")
    evolution = EvolutionManager.__new__(EvolutionManager)
    evolution.manager = manager

    resolve_target = cast(Callable[[str], str], getattr(evolution, "_resolve_target"))
    assert resolve_target("qwen3.6:latest") == "local-reasoning"
    assert resolve_target("explicit-model") == "explicit-model"
    target_method.assert_called_once_with("evolution", default_role="reasoning")


@pytest.mark.asyncio
async def test_tdd_default_coding_model_resolves_through_manager() -> None:
    manager = MagicMock()
    _ = _mock_method(manager, "get_target_for_role", "local-tdd")
    generate_method = _mock_method(manager, "generate", "generated")
    engine = OmniTDDEngine(model_manager=manager)

    call_llm = cast(Callable[[str, str], Awaitable[object]], getattr(engine, "_call_llm"))
    assert await call_llm("system", "user") == "generated"
    target_method = cast(_MockMethod, getattr(manager, "get_target_for_role"))
    target_method.assert_called_once_with("tdd", default_role="coding")
    assert _call_kwargs(generate_method)["target"] == "local-tdd"


@pytest.mark.asyncio
async def test_autonomous_qa_vision_uses_managed_multimodal_route(tmp_path: Path) -> None:
    manager = MagicMock()
    _ = _mock_method(manager, "get_target_for_role", "local-vision")
    generate_method = _mock_method(manager, "generate", '[{"description":"overlap","severity":"high"}]')

    engine = AutonomousQAEngine(project_root=str(tmp_path), model_manager=manager)
    vision_analyze = cast(Callable[[str], Awaitable[object]], getattr(engine, "_vision_analyze"))
    defects = cast(list[UIDefect], await vision_analyze("image-data"))

    assert len(defects) == 1
    assert defects[0].description == "overlap"
    kwargs = _call_kwargs(generate_method)
    assert kwargs["target"] == "local-vision"
    raw_messages = cast(list[dict[str, object]], kwargs["raw_messages"])
    assert raw_messages[0]["images"] == ["image-data"]


@pytest.mark.asyncio
async def test_autonomous_qa_code_fix_uses_managed_route(tmp_path: Path) -> None:
    manager = MagicMock()
    _ = _mock_method(manager, "get_target_for_role", "local-coding")
    generate_method = _mock_method(manager, "generate", '[{"file":"app.css","search":"old","replace":"new"}]')

    engine = AutonomousQAEngine(project_root=str(tmp_path), model_manager=manager)
    generate_fixes = cast(Callable[[list[object]], Awaitable[object]], getattr(engine, "_generate_code_fixes"))
    patches = await generate_fixes([])

    assert patches == [{"file": "app.css", "search": "old", "replace": "new"}]
    assert _call_kwargs(generate_method)["target"] == "local-coding"
