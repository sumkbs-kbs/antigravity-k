"""테스트: 프롬프트 진화기와 메타 아키텍트.
==================================
OPRO 기반 진화 루프(후보 생성→평가→선택→기록)와
아키텍처 제안 분석의 LLM 격리 계약을 검증한다.
"""

import json
from pathlib import Path
from typing import Callable, cast
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.meta_architect import MetaArchitect
from antigravity_k.engine.prompt_evolver import PromptEvolver


def _optimizer_call(evolver: PromptEvolver, prompt: str) -> str:
    call = cast(Callable[[str], str], getattr(evolver, "_call_optimizer"))
    return call(prompt)


def _extract_json_array(evolver: PromptEvolver, text: str) -> list[object] | None:
    extract = cast(Callable[[str], list[object] | None], getattr(evolver, "_extract_json_array"))
    return extract(text)


def _llm_call(architect: MetaArchitect, prompt: str, model: str, num_predict: int) -> str:
    call = cast(Callable[[str, str, int], str], getattr(architect, "_call_llm"))
    return call(prompt, model, num_predict)


def _history(evolver: PromptEvolver) -> list[object]:
    return cast(list[object], getattr(evolver, "_history"))


def _persist_dir(evolver: PromptEvolver) -> Path:
    return cast(Path, getattr(evolver, "_persist_dir"))


def _mock_call_arg(mock: MagicMock) -> str:
    call = cast(object, mock.call_args)
    if isinstance(call, tuple) and call:
        args = cast(tuple[object, ...], call[0])
        if not args:
            return ""
        value: object = args[0]
        return value if isinstance(value, str) else ""
    return ""


def _mock_kwargs(mock: MagicMock) -> dict[str, object]:
    call = cast(object, mock.call_args)
    if isinstance(call, tuple):
        call_tuple = cast(tuple[object, ...], call)
        if len(call_tuple) > 1:
            return cast(dict[str, object], call_tuple[1])
    return {}


@pytest.fixture
def evolver(tmp_path: Path) -> PromptEvolver:
    ev = PromptEvolver(persist_dir=str(tmp_path / "evo"))
    setattr(ev, "_call_optimizer", MagicMock(return_value="x" * 80))
    return ev


def _optimizer_mock(evolver: PromptEvolver) -> MagicMock:
    return cast(MagicMock, getattr(evolver, "_call_optimizer"))


# ─── PromptEvolver ───────────────────────────────────────────────


class TestEvolveSystemPrompt:
    def test_optimizer_uses_managed_model_target(self, tmp_path: Path):
        manager = MagicMock()
        get_target_for_role = cast(MagicMock, getattr(manager, "get_target_for_role"))
        generate = cast(MagicMock, getattr(manager, "generate"))
        get_target_for_role.return_value = "detected-local-prompt-model"
        generate.return_value = "managed optimizer output"
        ev = PromptEvolver(persist_dir=str(tmp_path / "evo"), model_manager=manager)

        assert _optimizer_call(ev, "optimize") == "managed optimizer output"
        get_target_for_role.assert_called_once_with("prompt_evolver", default_role="reasoning")
        generate.assert_called_once()
        assert _mock_call_arg(generate) == "optimize"
        assert _mock_kwargs(generate) == {"max_tokens": 2048, "temperature": 0.4}

    def test_best_candidate_wins_and_history_records(self, evolver: PromptEvolver):
        prompts = {"rephrase": "A" * 60, "expand": "B" * 60}

        def optimizer_response(prompt: str) -> str:
            return next(content for op, content in prompts.items() if f"**{op}**" in prompt)

        _optimizer_mock(evolver).side_effect = optimizer_response

        best, score = evolver.evolve_system_prompt(
            "base prompt", {"weaknesses": ["w"]}, eval_fn=lambda p: 0.9 if "B" in p else 0.1
        )

        assert best == "B" * 60
        assert score == 0.9
        history = _history(evolver)
        assert len(history) == 1
        assert cast(int, getattr(history[0], "candidates_tested")) == 3  # baseline + 2 후보

    def test_short_optimizer_output_is_discarded(self, evolver: PromptEvolver):
        _optimizer_mock(evolver).return_value = "짧음"

        best, _ = evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.5)

        # 후보가 모두 필터링되어 baseline만 남는다
        assert best == "base"

    def test_think_tags_stripped_from_candidates(self, evolver: PromptEvolver):
        _optimizer_mock(evolver).return_value = "<think>비밀 추론</think>" + "정제된 프롬프트 본문입니다. " * 5

        # 동점 시 baseline이 이기는 계약 → 정제본에만 높은 점수를 부여해 구분
        best, _ = evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.9 if "정제된" in p else 0.2)

        assert "비밀 추론" not in best
        assert "정제된 프롬프트" in best

    def test_without_eval_fn_baseline_score_is_half(self, evolver: PromptEvolver):
        best, score = evolver.evolve_system_prompt("base prompt", {})

        assert best == "base prompt"
        assert score == 0.5

    def test_eval_exception_scores_zero(self, evolver: PromptEvolver):
        def flaky(prompt: str) -> float:
            if prompt.startswith("A"):
                raise RuntimeError("eval down")
            return 0.4

        def optimizer_response(prompt: str) -> str:
            return "A" * 60 if "**rephrase**" in prompt else "C" * 60

        _optimizer_mock(evolver).side_effect = optimizer_response

        _, score = evolver.evolve_system_prompt("base", {}, eval_fn=flaky)

        assert score == 0.4  # 실패한 A는 0점, C가 채택

    def test_version_file_saved_to_persist_dir(self, evolver: PromptEvolver):
        _ = evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.7)

        persist_dir = _persist_dir(evolver)
        versions = list(persist_dir.glob("*.md")) or list(persist_dir.rglob("*"))
        assert any(p.is_file() for p in versions)

    def test_trend_reflects_generations(self, evolver: PromptEvolver):
        _ = evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.6)
        trend = evolver.get_evolution_trend()

        assert trend["generations"] == 1
        assert trend["latest_score"] == 0.6


class TestExtractJsonArray:
    def test_plain_array(self, evolver: PromptEvolver):
        assert _extract_json_array(evolver, '[{"a": 1}, {"b": 2}]') == [{"a": 1}, {"b": 2}]

    def test_array_after_prose_and_think_block(self, evolver: PromptEvolver):
        text = '사고 과정입니다 <think>숨김 [가짜]</think> 결과: [{"ok": true}]'

        assert _extract_json_array(evolver, text) == [{"ok": True}]

    def test_no_array_returns_none(self, evolver: PromptEvolver):
        assert _extract_json_array(evolver, "배열 없는 텍스트") is None


# ─── MetaArchitect ───────────────────────────────────────────────


@pytest.fixture
def architect(tmp_path: Path) -> MetaArchitect:
    arch = MetaArchitect(project_root=str(tmp_path))
    return arch


class TestAnalyzeAndPropose:
    def test_meta_architect_uses_managed_model_target(self, tmp_path: Path):
        manager = MagicMock()
        get_target_for_role = cast(MagicMock, getattr(manager, "get_target_for_role"))
        generate = cast(MagicMock, getattr(manager, "generate"))
        get_target_for_role.return_value = "detected-local-architect"
        generate.return_value = "managed response"
        arch = MetaArchitect(project_root=str(tmp_path), model_manager=manager)

        assert _llm_call(arch, "prompt", "legacy-model", 128) == "managed response"
        get_target_for_role.assert_called_once_with("meta_architect", default_role="reasoning")
        generate.assert_called_once()
        assert _mock_call_arg(generate) == "prompt"
        assert _mock_kwargs(generate) == {"max_tokens": 128, "temperature": 0.2}

    def test_valid_llm_json_builds_proposal(self, architect: MetaArchitect, tmp_path: Path):
        llm_json = json.dumps(
            {
                "title": "캐시 레이어 도입",
                "description": "응답 캐싱으로 지연 감소",
                "target_files": ["cache.py"],
                "expected_benefit": "latency -30%",
            }
        )
        llm_mock = MagicMock(return_value=llm_json)
        setattr(architect, "_call_llm", llm_mock)
        _ = (tmp_path / "ARCHITECTURE.md").write_text("# Arch\n", encoding="utf-8")
        (tmp_path / "src" / "antigravity_k" / "engine").mkdir(parents=True)  # mtime 참조 대비

        proposal = architect.analyze_and_propose({"latency_ms": 900})

        assert proposal is not None
        assert proposal.title == "캐시 레이어 도입"
        assert proposal.target_files == ["cache.py"]
        # 컨텍스트 수집 확인: 프롬프트에 ARCHITECTURE.md 내용이 들어간다
        prompt_arg = _mock_call_arg(llm_mock)
        assert "# Arch" in prompt_arg

    def test_invalid_json_returns_none(self, architect: MetaArchitect):
        setattr(architect, "_call_llm", MagicMock(return_value="JSON이 아닌 텍스트"))

        assert architect.analyze_and_propose({}) is None

    def test_missing_title_returns_none(self, architect: MetaArchitect):
        setattr(architect, "_call_llm", MagicMock(return_value=json.dumps({"description": "no title"})))

        assert architect.analyze_and_propose({}) is None

    def test_evolution_history_rendering(self, architect: MetaArchitect, tmp_path: Path):
        archive_path = tmp_path / "data" / "arch_archive.json"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        _ = archive_path.write_text(
            json.dumps(
                [
                    {"title": "T1", "description": "d1", "passed": True},
                    {"title": "T2", "description": "d2", "passed": False},
                ]
            ),
            encoding="utf-8",
        )

        rendered = cast(Callable[[], str], getattr(architect, "_get_evolution_history"))()

        assert "SUCCESS" in rendered and "FAILED" in rendered

    def test_engine_context_lists_core_modules(self, architect: MetaArchitect, tmp_path: Path):
        engine_dir = tmp_path / "src" / "antigravity_k" / "engine"
        engine_dir.mkdir(parents=True)
        _ = (engine_dir / "sample.py").write_text("x = 1\n", encoding="utf-8")

        context = cast(Callable[[], str], getattr(architect, "_get_architecture_context"))()

        assert "sample.py" in context and "bytes" in context
