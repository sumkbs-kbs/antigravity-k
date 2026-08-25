"""Antigravity-K: BenchmarkHarness 단위 테스트.
============================================
mock ModelManager로 BenchmarkHarness 실행 플로우를 검증합니다.
"""

import json
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.benchmark_cases import BUILTIN_CASES, get_suite
from antigravity_k.engine.benchmark_harness import (
    BenchmarkHarness,
    BenchmarkReport,
)
from antigravity_k.engine.slash_commands import SlashCommandRegistry

# ─── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def mock_model_manager():
    """ModelManager를 모킹합니다."""
    manager = MagicMock()
    # generate() 호출 시 항상 유효한 한국어 코드 응답을 반환
    manager.generate.return_value = (
        "### 🔍 분석\n\n피보나치 수열을 구하는 함수입니다.\n\n"
        "### 💻 구현 코드\n\n"
        "```python\n"
        "def fibonacci(n: int) -> int:\n"
        "    if n < 0:\n"
        "        raise ValueError('음수는 허용되지 않습니다')\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    a, b = 0, 1\n"
        "    for _ in range(2, n + 1):\n"
        "        a, b = b, a + b\n"
        "    return b\n"
        "```\n\n"
        "### 📊 설명\n\n"
        "- 반복 방법의 시간복잡도는 O(n)이며, 공간복잡도는 O(1)입니다.\n"
        "- 재귀 방법의 시간복잡도는 O(2^n)이며, 메모이제이션 없이는 비효율적입니다.\n\n"
        "💡 팁: 큰 n에 대해서는 반복 방법을 사용하세요."
    )
    # _registry._raw for _default_targets()
    manager._registry = MagicMock()
    manager._registry._raw = {"combos": {"collective-council": {"models": ["model-a", "model-b", "model-c"]}}}
    return manager


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "test_benchmark.json"


@pytest.fixture
def harness(mock_model_manager, tmp_db_path):
    return BenchmarkHarness(
        model_manager=mock_model_manager,
        db_path=tmp_db_path,
    )


# ─── 벤치마크 과제 테스트 ──────────────────────────────────────────


class TestBenchmarkCases:
    def test_builtin_cases_exist(self):
        assert len(BUILTIN_CASES) >= 8

    def test_get_suite_all(self):
        suite = get_suite("all")
        assert len(suite) == len(BUILTIN_CASES)

    def test_get_suite_by_category(self):
        simple = get_suite("simple")
        assert all(c.category == "simple" for c in simple)
        assert len(simple) >= 2

    def test_frontier_suite_covers_core_agent_capabilities(self):
        frontier = get_suite("frontier")

        assert [case.id for case in frontier] == ["sim-001", "alg-001", "srch-002", "anl-001", "lh-001"]

    def test_search_benchmark_cases_declare_required_tools(self):
        case = get_suite("srch-002")[0]

        assert case.expected_tools == ("web_search",)

    def test_quality_gate_uses_case_category_for_non_coding_tasks(self, harness):
        case = get_suite("srch-002")[0]
        harness._manager.generate.return_value = (
            "- AI 반도체 시장의 최신 동향입니다.\n"
            "- 출처: https://example.com/report\n"
            "- 핵심 변화와 영향을 정리했습니다."
        )

        result = harness.run_case(case, ["test-model"])[0]

        assert "요청된 코드 블록 누락" not in result.issues

    def test_benchmark_prompt_adds_category_contract(self, harness):
        search_prompt = harness._benchmark_prompt(get_suite("srch-002")[0])
        long_horizon_prompt = harness._benchmark_prompt(get_suite("lh-001")[0])
        comparison_prompt = harness._benchmark_prompt(get_suite("sim-002")[0])
        refactor_prompt = harness._benchmark_prompt(get_suite("ref-001")[0])

        assert "출처와 근거" in search_prompt
        assert "충돌하면" in search_prompt
        assert "checkpoint" in long_horizon_prompt
        assert "recovery" in long_horizon_prompt
        assert "rollback" in long_horizon_prompt
        assert "비교 기준과 결론을 마크다운 표" in comparison_prompt
        assert "리팩토링 계획" in refactor_prompt
        assert "전/후 구조 비교" in refactor_prompt
        assert "Markdown 표" in refactor_prompt

    def test_quality_revision_keeps_only_improved_response(self, harness):
        case = get_suite("srch-002")[0]
        harness._quality_gate.max_retries = 1
        harness._manager.generate.side_effect = [
            "최신 동향을 단정합니다.",
            "최신 동향은 출처와 함께 확인해야 합니다.\n출처: https://example.com",
        ]

        result = harness.run_case(case, ["test-model"])[0]

        assert result.quality_revision_count == 1
        assert harness._manager.generate.call_count == 2

    def test_quality_revision_uses_second_attempt_when_first_is_still_weak(self, harness):
        case = get_suite("sim-001")[0]
        valid = harness._manager.generate.return_value
        harness._manager.generate.side_effect = ["응답이 너무 짧습니다.", "여전히 요구사항이 부족합니다.", valid]

        result = harness.run_case(case, ["test-model"])[0]

        assert result.quality_revision_count == 2
        assert harness._manager.generate.call_count == 3
        assert result.quality_revision_applied is True
        assert result.quality_grade == "excellent"

    def test_repeat_quality_revision_discards_anchoring_output(self, harness):
        case = get_suite("sim-001")[0]
        harness._manager.generate.return_value = "새로운 답변"

        harness._quality_revision(case, "반복된 기존 답변", "반복 콘텐츠 탐지 (3회 반복)", "qwen3.6:latest")

        revision_prompt = harness._manager.generate.call_args.kwargs["prompt"]
        assert "반복된 기존 답변" not in revision_prompt
        assert "처음부터 새로 작성" in revision_prompt

    def test_get_suite_by_id(self):
        result = get_suite("sim-001")
        assert len(result) == 1
        assert result[0].id == "sim-001"

    def test_case_has_required_fields(self):
        for case in BUILTIN_CASES:
            assert case.id
            assert case.category
            assert case.prompt
            assert 1 <= case.difficulty <= 5

    def test_unique_ids(self):
        ids = [c.id for c in BUILTIN_CASES]
        assert len(ids) == len(set(ids)), "과제 ID가 중복됩니다"


# ─── BenchmarkHarness 테스트 ──────────────────────────────────────


class TestBenchmarkHarness:
    def test_qwen_generation_uses_stable_local_sampling(self, harness):
        initial = harness._generation_kwargs("qwen3.6:latest", revision=False)
        revision = harness._generation_kwargs("qwen3.6:latest", revision=True)
        remote = harness._generation_kwargs("deepseek-r1:70b", revision=False)

        assert initial["temperature"] == 0.15
        assert initial["min_p"] == 0.0
        assert initial["max_tokens"] == 3072
        assert initial["repeat_penalty"] == 1.1
        assert revision["repeat_penalty"] == 1.15
        assert revision["temperature"] == 0.08
        assert remote == {"max_tokens": 4096, "temperature": 0.4}

    def test_run_single_case(self, harness, mock_model_manager):
        case = get_suite("sim-001")[0]
        results = harness.run_case(case, targets=["test-model"])

        assert len(results) == 1
        assert results[0].case_id == "sim-001"
        assert results[0].target == "test-model"
        assert results[0].quality_score > 0
        assert results[0].benchmark_score > 0
        assert results[0].keyword_coverage > 0
        assert "def fibonacci" in results[0].passed_keywords
        assert results[0].latency_ms >= 0  # mock은 즉시 반환하므로 0.0 가능
        mock_model_manager.generate.assert_called_once()

    def test_run_multiple_targets(self, harness, mock_model_manager):
        case = get_suite("sim-001")[0]
        targets = ["collective-council", "model-a", "model-b"]
        results = harness.run_case(case, targets=targets)

        assert len(results) == 3
        assert [r.target for r in results] == targets
        assert mock_model_manager.generate.call_count == 3

    def test_run_suite(self, harness):
        report = harness.run_suite("simple", targets=["test-model"])

        assert isinstance(report, BenchmarkReport)
        assert report.suite_name == "simple"
        assert len(report.results) >= 2
        assert report.duration_s >= 0

    def test_comparison_table_no_data(self, harness):
        table = harness.comparison_table()
        assert "결과가 없습니다" in table

    def test_comparison_table_with_data(self, harness):
        # 데이터 생성
        harness.run_suite("simple", targets=["test-model"])
        table = harness.comparison_table("simple")

        assert "Benchmark 비교표" in table
        assert "평균 종합점수" in table
        assert "현재 우세 타겟" in table
        assert "test-model" in table
        assert "sim-001" in table

    def test_error_handling(self, harness, mock_model_manager):
        """모델 실행 실패 시에도 결과가 기록됩니다."""
        mock_model_manager.generate.side_effect = RuntimeError("VRAM exhausted")
        case = get_suite("sim-001")[0]
        results = harness.run_case(case, targets=["broken-model"])

        assert len(results) == 1
        assert results[0].quality_grade == "fail"
        assert results[0].error == "VRAM exhausted"

    def test_default_targets(self, harness):
        targets = harness._default_targets()
        assert "collective-council" in targets
        assert len(targets) >= 2  # collective + at least 1 individual


# ─── Slash command integration ─────────────────────────────────────


class TestBenchmarkSlashCommand:
    def test_help_returns_string_not_generator(self, mock_model_manager):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)

        result = registry.execute("/benchmark")

        assert isinstance(result, str)
        assert "Benchmark 명령어" in result

    def test_report_returns_string_not_generator(self, mock_model_manager):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)

        result = registry.execute("/benchmark report")

        assert isinstance(result, str)
        assert "Benchmark 비교표" in result or "벤치마크 결과가 없습니다" in result

    def test_task_report_returns_operational_metrics(self, mock_model_manager):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)
        fake_harness = MagicMock()
        fake_harness.task_comparison_table.return_value = "## Task Benchmark\n| 성공률 | 100% |"

        with patch("antigravity_k.engine.benchmark_harness.BenchmarkHarness", return_value=fake_harness):
            result = registry.execute("/benchmark task-report")

        assert "Task Benchmark" in result
        fake_harness.task_comparison_table.assert_called_once_with()

    def test_task_export_returns_calibration_artifact_path(self, mock_model_manager):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)
        fake_harness = MagicMock()
        fake_harness.export_task_calibration_artifact.return_value = Path("data/benchmarks/qwen-task.json")

        with patch("antigravity_k.engine.benchmark_harness.BenchmarkHarness", return_value=fake_harness):
            result = registry.execute("/benchmark task-export qwen3.6:latest")

        assert "qwen-task.json" in result
        fake_harness.export_task_calibration_artifact.assert_called_once_with("qwen3.6:latest", None)

    def test_run_returns_streaming_generator(self, mock_model_manager):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)
        fake_report = BenchmarkReport(
            suite_name="simple",
            targets=["test-model"],
            results=[],
            started_at=time.time(),
            finished_at=time.time(),
        )

        with patch("antigravity_k.engine.benchmark_harness.BenchmarkHarness") as harness_cls:
            harness = harness_cls.return_value
            harness.run_suite.return_value = fake_report
            harness.comparison_table.return_value = "## mock table"

            result = registry.execute("/benchmark run simple")

        assert isinstance(result, types.GeneratorType)
        rendered = "".join(result)
        assert "벤치마크 실행 시작" in rendered
        assert "벤치마크 완료" in rendered
        assert "## mock table" in rendered

    def test_command_palette_exposes_benchmark_report(self):
        registry = Path("dashboard/src/features/command-palette/commandRegistry.ts").read_text(encoding="utf-8")

        assert "Collective Benchmark Report (/benchmark)" in registry
        assert "text: '/benchmark report'" in registry


# ─── 영속화 테스트 ────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load(self, mock_model_manager, tmp_db_path):
        harness1 = BenchmarkHarness(model_manager=mock_model_manager, db_path=tmp_db_path)
        harness1.run_suite("simple", targets=["test-model"])
        count = len(harness1._history)
        assert count > 0

        # 새 인스턴스에서 로드
        harness2 = BenchmarkHarness(model_manager=mock_model_manager, db_path=tmp_db_path)
        assert len(harness2._history) == count

    def test_clear_history(self, harness, tmp_db_path):
        harness.run_suite("simple", targets=["test-model"])
        assert len(harness._history) > 0

        harness.clear_history()
        assert len(harness._history) == 0

        # JSON도 비어있어야 함
        with open(tmp_db_path) as f:
            data = json.load(f)
        assert data["total_results"] == 0

    def test_json_format(self, harness, tmp_db_path):
        harness.run_suite("simple", targets=["test-model"])

        with open(tmp_db_path) as f:
            data = json.load(f)

        assert data["version"] == 1
        assert "updated_at" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0

        # 각 결과에 필수 필드 확인
        for result in data["results"]:
            assert "case_id" in result
            assert "target" in result
            assert "quality_score" in result
            assert "quality_grade" in result
            assert "benchmark_score" in result
            assert "keyword_coverage" in result
            assert "latency_ms" in result

    def test_loads_legacy_results_without_composite_fields(self, mock_model_manager, tmp_db_path):
        legacy = {
            "version": 1,
            "results": [
                {
                    "case_id": "sim-001",
                    "target": "legacy-model",
                    "quality_score": 0.72,
                    "quality_grade": "good",
                    "latency_ms": 1200,
                    "tokens_in": 10,
                    "tokens_out": 50,
                    "output_preview": "def fibonacci(n): return n",
                    "timestamp": time.time(),
                    "issues": [],
                    "error": "",
                }
            ],
        }
        tmp_db_path.write_text(json.dumps(legacy), encoding="utf-8")

        harness = BenchmarkHarness(
            model_manager=mock_model_manager,
            db_path=tmp_db_path,
        )

        assert harness._history[0].benchmark_score == 0.72
        assert harness._history[0].keyword_coverage == 1.0


class TestVerifiedCodeExecution:
    def test_correct_executed_output_is_verified(self, harness):
        # Given: a model answer whose code, when executed, prints the expected output.
        answer = "```python\ndef sum_to(n):\n    return n * (n + 1) // 2\nprint(sum_to(100))\n```\n"

        # When: the harness verifies the executed output against the expected value.
        passed, actual = harness._verify_executed_code(answer, "5050")

        # Then: execution matches and the actual stdout is captured for the report.
        assert passed is True
        assert actual.strip() == "5050"

    def test_wrong_executed_output_is_not_verified(self, harness):
        # Given: code that prints the wrong value for the expected output.
        answer = "```python\nprint(1234)\n```"

        # When / Then: the verifier rejects it; the mismatched actual output is returned.
        passed, actual = harness._verify_executed_code(answer, "5050")
        assert passed is False
        assert "1234" in actual

    def test_answer_without_code_block_is_not_verified(self, harness):
        # Given: prose only — the model narrated the result without runnable code.
        answer = "결과는 5050입니다."

        # When / Then: no code to execute means the case is not verified.
        passed, actual = harness._verify_executed_code(answer, "5050")
        assert passed is False
        assert "no_code_block" in actual

    def test_execute_single_records_verified_flag_and_adjusts_score(self, harness, mock_model_manager):
        # Given: a verified-code case whose generated answer prints the right value.
        from antigravity_k.engine.benchmark_cases import BenchmarkCase

        case = BenchmarkCase(
            id="verf-test",
            category="verified_code",
            difficulty=1,
            prompt="print 5050",
            expected_output="5050",
        )
        mock_model_manager.generate.return_value = "```python\nprint(5050)\n```\n결과는 5050입니다."

        # When: the harness scores the case.
        result = harness._execute_single(case, "qwen3.6:latest")

        # Then: the executed output is verified and flagged, and a verified case that
        # merely prints the answer is not penalized for missing explanatory keywords.
        assert result.verified is True
        assert result.verified_output.strip() == "5050"
        assert result.benchmark_score > 0.0

    def test_execute_single_self_corrects_when_first_code_runs_wrong(self, harness, mock_model_manager):
        # Given: the model first returns code that runs but prints the wrong value,
        # then (on the verify-driven revision) returns code that prints the right value.
        from antigravity_k.engine.benchmark_cases import BenchmarkCase

        case = BenchmarkCase(
            id="verf-iter",
            category="verified_code",
            difficulty=1,
            prompt="print 5050",
            expected_output="5050",
        )
        mock_model_manager.generate.side_effect = [
            "```python\nprint(1234)\n```",
            "```python\nprint(5050)\n```",
        ]

        # When: the harness executes the first answer, detects the mismatch, and revises.
        result = harness._execute_single(case, "qwen3.6:latest")

        # Then: the agent self-corrected on executable feedback — it iterated to the
        # verified answer rather than accepting the first wrong-but-runnable attempt.
        assert result.verified is True
        assert result.verified_output.strip() == "5050"
        assert result.benchmark_score > 0.0
        assert result.quality_revision_count >= 1
