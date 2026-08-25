"""테스트: 프롬프트 진화기와 메타 아키텍트.
==================================
OPRO 기반 진화 루프(후보 생성→평가→선택→기록)와
아키텍처 제안 분석의 LLM 격리 계약을 검증한다.
"""

import json
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.meta_architect import MetaArchitect
from antigravity_k.engine.prompt_evolver import PromptEvolver


@pytest.fixture
def evolver(tmp_path):
    ev = PromptEvolver(persist_dir=str(tmp_path / "evo"))
    ev._call_optimizer = MagicMock(return_value="x" * 80)
    return ev


# ─── PromptEvolver ───────────────────────────────────────────────


class TestEvolveSystemPrompt:
    def test_best_candidate_wins_and_history_records(self, evolver):
        prompts = {"rephrase": "A" * 60, "expand": "B" * 60}
        evolver._call_optimizer.side_effect = lambda prompt: next(
            content for op, content in prompts.items() if f"**{op}**" in prompt
        )

        best, score = evolver.evolve_system_prompt(
            "base prompt", {"weaknesses": ["w"]}, eval_fn=lambda p: 0.9 if "B" in p else 0.1
        )

        assert best == "B" * 60
        assert score == 0.9
        assert len(evolver._history) == 1
        assert evolver._history[0].candidates_tested == 3  # baseline + 2 후보

    def test_short_optimizer_output_is_discarded(self, evolver):
        evolver._call_optimizer.return_value = "짧음"

        best, _ = evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.5)

        # 후보가 모두 필터링되어 baseline만 남는다
        assert best == "base"

    def test_think_tags_stripped_from_candidates(self, evolver):
        evolver._call_optimizer.return_value = "<think>비밀 추론</think>" + "정제된 프롬프트 본문입니다. " * 5

        # 동점 시 baseline이 이기는 계약 → 정제본에만 높은 점수를 부여해 구분
        best, _ = evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.9 if "정제된" in p else 0.2)

        assert "비밀 추론" not in best
        assert "정제된 프롬프트" in best

    def test_without_eval_fn_baseline_score_is_half(self, evolver):
        best, score = evolver.evolve_system_prompt("base prompt", {})

        assert best == "base prompt"
        assert score == 0.5

    def test_eval_exception_scores_zero(self, evolver):
        def flaky(prompt):
            if prompt.startswith("A"):
                raise RuntimeError("eval down")
            return 0.4

        evolver._call_optimizer.side_effect = lambda prompt: ("A" * 60 if "**rephrase**" in prompt else "C" * 60)

        _, score = evolver.evolve_system_prompt("base", {}, eval_fn=flaky)

        assert score == 0.4  # 실패한 A는 0점, C가 채택

    def test_version_file_saved_to_persist_dir(self, evolver):
        evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.7)

        versions = list(evolver._persist_dir.glob("*.md")) or list(evolver._persist_dir.rglob("*"))
        assert any(p.is_file() for p in versions)

    def test_trend_reflects_generations(self, evolver):
        evolver.evolve_system_prompt("base", {}, eval_fn=lambda p: 0.6)
        trend = evolver.get_evolution_trend()

        assert trend["generations"] == 1
        assert trend["latest_score"] == 0.6


class TestExtractJsonArray:
    def test_plain_array(self, evolver):
        assert evolver._extract_json_array('[{"a": 1}, {"b": 2}]') == [{"a": 1}, {"b": 2}]

    def test_array_after_prose_and_think_block(self, evolver):
        text = '사고 과정입니다 <think>숨김 [가짜]</think> 결과: [{"ok": true}]'

        assert evolver._extract_json_array(text) == [{"ok": True}]

    def test_no_array_returns_none(self, evolver):
        assert evolver._extract_json_array("배열 없는 텍스트") is None


# ─── MetaArchitect ───────────────────────────────────────────────


@pytest.fixture
def architect(tmp_path):
    arch = MetaArchitect(project_root=str(tmp_path))
    return arch


class TestAnalyzeAndPropose:
    def test_valid_llm_json_builds_proposal(self, architect, tmp_path):
        llm_json = json.dumps(
            {
                "title": "캐시 레이어 도입",
                "description": "응답 캐싱으로 지연 감소",
                "target_files": ["cache.py"],
                "expected_benefit": "latency -30%",
            }
        )
        architect._call_llm = MagicMock(return_value=llm_json)
        (tmp_path / "ARCHITECTURE.md").write_text("# Arch\n", encoding="utf-8")
        (tmp_path / "src" / "antigravity_k" / "engine").mkdir(parents=True)  # mtime 참조 대비

        proposal = architect.analyze_and_propose({"latency_ms": 900})

        assert proposal is not None
        assert proposal.title == "캐시 레이어 도입"
        assert proposal.target_files == ["cache.py"]
        # 컨텍스트 수집 확인: 프롬프트에 ARCHITECTURE.md 내용이 들어간다
        prompt_arg = architect._call_llm.call_args.args[0]
        assert "# Arch" in prompt_arg

    def test_invalid_json_returns_none(self, architect):
        architect._call_llm = MagicMock(return_value="JSON이 아닌 텍스트")

        assert architect.analyze_and_propose({}) is None

    def test_missing_title_returns_none(self, architect):
        architect._call_llm = MagicMock(return_value=json.dumps({"description": "no title"}))

        assert architect.analyze_and_propose({}) is None

    def test_evolution_history_rendering(self, architect, tmp_path):
        archive_path = tmp_path / "data" / "arch_archive.json"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(
            json.dumps(
                [
                    {"title": "T1", "description": "d1", "passed": True},
                    {"title": "T2", "description": "d2", "passed": False},
                ]
            ),
            encoding="utf-8",
        )

        rendered = architect._get_evolution_history()

        assert "SUCCESS" in rendered and "FAILED" in rendered

    def test_engine_context_lists_core_modules(self, architect, tmp_path):
        engine_dir = tmp_path / "src" / "antigravity_k" / "engine"
        engine_dir.mkdir(parents=True)
        (engine_dir / "sample.py").write_text("x = 1\n", encoding="utf-8")

        context = architect._get_architecture_context()

        assert "sample.py" in context and "bytes" in context
