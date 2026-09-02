"""Antigravity-K: BenchmarkHarness 단위 테스트.
============================================
mock ModelManager로 BenchmarkHarness 실행 플로우를 검증합니다.
"""

import json
import time
import types
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.benchmark_cases import BUILTIN_CASES, get_suite
from antigravity_k.engine.benchmark_harness import (
    BenchmarkHarness,
    BenchmarkReport,
    BenchmarkResult,
)
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.slash_commands import SlashCommandRegistry

# ─── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """ModelManager를 모킹합니다."""
    manager = MagicMock(spec=ModelManager)
    # generate() 호출 시 항상 유효한 한국어 코드 응답을 반환
    _set_mock_return(manager, "generate", (
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
    ))
    # _registry._raw for _default_targets()
    registry = MagicMock()
    _ = setattr(registry, "_raw", {"combos": {"collective-council": {"models": ["model-a", "model-b", "model-c"]}}})
    _ = setattr(manager, "_registry", registry)
    return manager


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_benchmark.json"


@pytest.fixture
def harness(mock_model_manager: MagicMock, tmp_db_path: Path) -> BenchmarkHarness:
    return BenchmarkHarness(
        model_manager=mock_model_manager,
        db_path=tmp_db_path,
    )


def _manager_mock(harness: BenchmarkHarness) -> MagicMock:
    return cast(MagicMock, getattr(harness, "_manager"))


def _mock_method(mock: MagicMock, name: str) -> MagicMock:
    return cast(MagicMock, getattr(mock, name))


def _set_mock_return(mock: MagicMock, name: str, value: object) -> None:
    setattr(_mock_method(mock, name), "return_value", value)


def _set_mock_side_effect(mock: MagicMock, name: str, value: object) -> None:
    setattr(_mock_method(mock, name), "side_effect", value)


def _mock_call_count(mock: MagicMock, name: str) -> int:
    return cast(int, getattr(_mock_method(mock, name), "call_count"))


def _assert_mock_called_once(mock: MagicMock, name: str) -> None:
    callback = cast(Callable[[], object], getattr(_mock_method(mock, name), "assert_called_once"))
    _ = callback()


def _assert_mock_called_once_with(mock: MagicMock, name: str, *args: object) -> None:
    callback = cast(Callable[..., object], getattr(_mock_method(mock, name), "assert_called_once_with"))
    _ = callback(*args)


def _mock_prompt_kwargs(mock: MagicMock, name: str) -> str:
    call_args = cast(object, getattr(_mock_method(mock, name), "call_args"))
    kwargs = cast(Mapping[str, object], getattr(call_args, "kwargs"))
    return cast(str, kwargs.get("prompt", ""))


def _benchmark_prompt(harness: BenchmarkHarness, case: object) -> str:
    method = cast(Callable[[object], object], getattr(harness, "_benchmark_prompt"))
    return cast(str, method(case))


def _generation_kwargs(harness: BenchmarkHarness, target: str, revision: bool) -> Mapping[str, object]:
    method = cast(Callable[..., object], getattr(harness, "_generation_kwargs"))
    return cast(Mapping[str, object], method(target, revision=revision))


def _execute_single(harness: BenchmarkHarness, case: object, target: str) -> BenchmarkResult:
    method = cast(Callable[[object, str], object], getattr(harness, "_execute_single"))
    return cast(BenchmarkResult, method(case, target))


def _quality_revision(harness: BenchmarkHarness, *args: object) -> str:
    method = cast(Callable[..., object], getattr(harness, "_quality_revision"))
    return cast(str, method(*args))


def _verify_executed_code(harness: BenchmarkHarness, output: str, expected: str) -> tuple[bool, str]:
    method = cast(Callable[[str, str], object], getattr(harness, "_verify_executed_code"))
    return cast(tuple[bool, str], method(output, expected))


def _default_targets(harness: BenchmarkHarness) -> list[str]:
    method = cast(Callable[[], object], getattr(harness, "_default_targets"))
    return cast(list[str], method())


def _history(harness: BenchmarkHarness) -> list[BenchmarkResult]:
    return cast(list[BenchmarkResult], getattr(harness, "_history"))


def _read_json_mapping(path: Path) -> Mapping[str, object]:
    with path.open(encoding="utf-8") as handle:
        return cast(Mapping[str, object], cast(object, json.load(handle)))


def _result_rows(data: Mapping[str, object]) -> list[Mapping[str, object]]:
    return cast(list[Mapping[str, object]], data.get("results", []))


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

    def test_quality_gate_uses_case_category_for_non_coding_tasks(self, harness: BenchmarkHarness):
        case = get_suite("srch-002")[0]
        _set_mock_return(_manager_mock(harness), "generate", (
            "- AI 반도체 시장의 최신 동향입니다.\n"
            "- 출처: https://example.com/report\n"
            "- 핵심 변화와 영향을 정리했습니다."
        ))

        result = harness.run_case(case, ["test-model"])[0]

        assert "요청된 코드 블록 누락" not in result.issues

    def test_benchmark_prompt_adds_category_contract(self, harness: BenchmarkHarness):
        search_prompt = _benchmark_prompt(harness, get_suite("srch-002")[0])
        long_horizon_prompt = _benchmark_prompt(harness, get_suite("lh-001")[0])
        comparison_prompt = _benchmark_prompt(harness, get_suite("sim-002")[0])
        refactor_prompt = _benchmark_prompt(harness, get_suite("ref-001")[0])

        assert "출처와 근거" in search_prompt
        assert "충돌하면" in search_prompt
        assert "checkpoint" in long_horizon_prompt
        assert "recovery" in long_horizon_prompt
        assert "rollback" in long_horizon_prompt
        assert "비교 기준과 결론을 마크다운 표" in comparison_prompt
        assert "리팩토링 계획" in refactor_prompt
        assert "전/후 구조 비교" in refactor_prompt
        assert "Markdown 표" in refactor_prompt

    def test_quality_revision_keeps_only_improved_response(self, harness: BenchmarkHarness):
        case = get_suite("srch-002")[0]
        quality_gate = cast(object, getattr(harness, "_quality_gate"))
        setattr(quality_gate, "max_retries", 1)
        _set_mock_side_effect(_manager_mock(harness), "generate", [
            "최신 동향을 단정합니다.",
            "최신 동향은 출처와 함께 확인해야 합니다.\n출처: https://example.com",
        ])

        result = harness.run_case(case, ["test-model"])[0]

        assert result.quality_revision_count == 1
        assert _mock_call_count(_manager_mock(harness), "generate") == 2

    def test_quality_revision_uses_second_attempt_when_first_is_still_weak(self, harness: BenchmarkHarness):
        case = get_suite("sim-001")[0]
        valid = cast(object, getattr(_mock_method(_manager_mock(harness), "generate"), "return_value"))
        _set_mock_side_effect(_manager_mock(harness), "generate", ["응답이 너무 짧습니다.", "여전히 요구사항이 부족합니다.", valid])

        result = harness.run_case(case, ["test-model"])[0]

        assert result.quality_revision_count == 2
        assert _mock_call_count(_manager_mock(harness), "generate") == 3
        assert result.quality_revision_applied is True
        assert result.quality_grade == "excellent"

    def test_repeat_quality_revision_discards_anchoring_output(self, harness: BenchmarkHarness):
        case = get_suite("sim-001")[0]
        _set_mock_return(_manager_mock(harness), "generate", "새로운 답변")

        _ = _quality_revision(harness, case, "반복된 기존 답변", "반복 콘텐츠 탐지 (3회 반복)", "qwen3.6:latest")

        revision_prompt = _mock_prompt_kwargs(_manager_mock(harness), "generate")
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
    def test_provider_error_marker_is_recorded_as_failure(
        self, harness: BenchmarkHarness, mock_model_manager: MagicMock
    ) -> None:
        # Given: the provider returned its transport-error marker instead of a model answer.
        from antigravity_k.engine.benchmark_cases import BenchmarkCase

        case = BenchmarkCase(
            id="provider-error",
            category="simple",
            difficulty=1,
            prompt="return a short answer",
        )
        _set_mock_return(mock_model_manager, "generate", "[API Error for qwen3.8:latest] connection refused")

        # When: the harness scores the provider response.
        result = _execute_single(harness, case, "qwen3.8:latest")

        # Then: transport failure is not treated as verified or excellent output.
        assert result.error.startswith("[API Error for qwen3.8:latest]")
        assert result.verified is False
        assert result.benchmark_score == 0.0
        assert result.quality_grade == "fail"

    def test_qwen_generation_uses_stable_local_sampling(self, harness: BenchmarkHarness):
        initial = _generation_kwargs(harness, "qwen3.6:latest", revision=False)
        revision = _generation_kwargs(harness, "qwen3.6:latest", revision=True)
        remote = _generation_kwargs(harness, "deepseek-r1:70b", revision=False)

        assert initial["temperature"] == 0.15
        assert initial["min_p"] == 0.0
        assert initial["max_tokens"] == 3072
        assert initial["repeat_penalty"] == 1.1
        assert revision["repeat_penalty"] == 1.15
        assert revision["temperature"] == 0.08
        assert remote == {"max_tokens": 4096, "temperature": 0.4}

    def test_run_single_case(self, harness: BenchmarkHarness, mock_model_manager: MagicMock) -> None:
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
        _assert_mock_called_once(mock_model_manager, "generate")

    def test_run_multiple_targets(self, harness: BenchmarkHarness, mock_model_manager: MagicMock) -> None:
        case = get_suite("sim-001")[0]
        targets = ["collective-council", "model-a", "model-b"]
        results = harness.run_case(case, targets=targets)

        assert len(results) == 3
        assert [r.target for r in results] == targets
        assert _mock_call_count(mock_model_manager, "generate") == 3

    def test_run_suite(self, harness: BenchmarkHarness) -> None:
        report: BenchmarkReport = harness.run_suite("simple", targets=["test-model"])

        assert isinstance(report, BenchmarkReport)
        assert report.suite_name == "simple"
        assert len(report.results) >= 2
        assert report.duration_s >= 0

    def test_comparison_table_no_data(self, harness: BenchmarkHarness):
        table = harness.comparison_table()
        assert "결과가 없습니다" in table

    def test_comparison_table_with_data(self, harness: BenchmarkHarness):
        # 데이터 생성
        _ = harness.run_suite("simple", targets=["test-model"])
        table = harness.comparison_table("simple")

        assert "Benchmark 비교표" in table
        assert "평균 종합점수" in table
        assert "현재 우세 타겟" in table
        assert "test-model" in table
        assert "sim-001" in table

    def test_error_handling(self, harness: BenchmarkHarness, mock_model_manager: MagicMock):
        """모델 실행 실패 시에도 결과가 기록됩니다."""
        _set_mock_side_effect(mock_model_manager, "generate", RuntimeError("VRAM exhausted"))
        case = get_suite("sim-001")[0]
        results = harness.run_case(case, targets=["broken-model"])

        assert len(results) == 1
        assert results[0].quality_grade == "fail"
        assert results[0].error == "VRAM exhausted"

    def test_default_targets(self, harness: BenchmarkHarness):
        targets = _default_targets(harness)
        assert "collective-council" in targets
        assert len(targets) >= 2  # collective + at least 1 individual


# ─── Slash command integration ─────────────────────────────────────


class TestBenchmarkSlashCommand:
    def test_help_returns_string_not_generator(self, mock_model_manager: MagicMock):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)

        result = registry.execute("/benchmark")

        assert isinstance(result, str)
        assert "Benchmark 명령어" in result

    def test_report_returns_string_not_generator(self, mock_model_manager: MagicMock):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)

        result = registry.execute("/benchmark report")

        assert isinstance(result, str)
        assert "Benchmark 비교표" in result or "벤치마크 결과가 없습니다" in result

    def test_task_report_returns_operational_metrics(self, mock_model_manager: MagicMock):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)
        fake_harness = MagicMock()
        _set_mock_return(fake_harness, "task_comparison_table", "## Task Benchmark\n| 성공률 | 100% |")

        with patch("antigravity_k.engine.benchmark_harness.BenchmarkHarness", return_value=fake_harness):
            result = registry.execute("/benchmark task-report")

        assert "Task Benchmark" in result
        _assert_mock_called_once_with(fake_harness, "task_comparison_table")

    def test_task_export_returns_calibration_artifact_path(self, mock_model_manager: MagicMock):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)
        fake_harness = MagicMock()
        _set_mock_return(fake_harness, "export_task_calibration_artifact", Path("data/benchmarks/qwen-task.json"))

        with patch("antigravity_k.engine.benchmark_harness.BenchmarkHarness", return_value=fake_harness):
            result = registry.execute("/benchmark task-export qwen3.6:latest")

        assert "qwen-task.json" in result
        _assert_mock_called_once_with(fake_harness, "export_task_calibration_artifact", "qwen3.6:latest", None)

    def test_run_returns_streaming_generator(self, mock_model_manager: MagicMock):
        registry = SlashCommandRegistry(model_manager=mock_model_manager)
        fake_report = BenchmarkReport(
            suite_name="simple",
            targets=["test-model"],
            results=[],
            started_at=time.time(),
            finished_at=time.time(),
        )

        with patch("antigravity_k.engine.benchmark_harness.BenchmarkHarness") as harness_cls:
            harness = cast(MagicMock, harness_cls.return_value)
            _set_mock_return(harness, "run_suite", fake_report)
            _set_mock_return(harness, "comparison_table", "## mock table")

            result = registry.execute("/benchmark run simple")

        assert isinstance(result, types.GeneratorType)
        rendered = "".join(cast(Iterator[str], cast(object, result)))
        assert "벤치마크 실행 시작" in rendered
        assert "벤치마크 완료" in rendered
        assert "## mock table" in rendered

    def test_command_palette_exposes_benchmark_report(self):
        registry = Path("dashboard/src/features/command-palette/commandRegistry.ts").read_text(encoding="utf-8")

        assert "Collective Benchmark Report (/benchmark)" in registry
        assert "text: '/benchmark report'" in registry


# ─── 영속화 테스트 ────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load(self, mock_model_manager: MagicMock, tmp_db_path: Path):
        harness1 = BenchmarkHarness(model_manager=mock_model_manager, db_path=tmp_db_path)
        _ = harness1.run_suite("simple", targets=["test-model"])
        count = len(_history(harness1))
        assert count > 0

        # 새 인스턴스에서 로드
        harness2 = BenchmarkHarness(model_manager=mock_model_manager, db_path=tmp_db_path)
        assert len(_history(harness2)) == count

    def test_clear_history(self, harness: BenchmarkHarness, tmp_db_path: Path):
        _ = harness.run_suite("simple", targets=["test-model"])
        assert len(_history(harness)) > 0

        harness.clear_history()
        assert len(_history(harness)) == 0

        # JSON도 비어있어야 함
        data = _read_json_mapping(tmp_db_path)
        assert data["total_results"] == 0

    def test_json_format(self, harness: BenchmarkHarness, tmp_db_path: Path):
        _ = harness.run_suite("simple", targets=["test-model"])

        data = _read_json_mapping(tmp_db_path)

        assert data["version"] == 1
        assert "updated_at" in data
        rows = _result_rows(data)
        assert len(rows) > 0

        # 각 결과에 필수 필드 확인
        for result in rows:
            assert "case_id" in result
            assert "target" in result
            assert "quality_score" in result
            assert "quality_grade" in result
            assert "benchmark_score" in result
            assert "keyword_coverage" in result
            assert "latency_ms" in result

    def test_loads_legacy_results_without_composite_fields(self, mock_model_manager: MagicMock, tmp_db_path: Path):
        legacy: dict[str, object] = {
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
        _ = tmp_db_path.write_text(json.dumps(legacy), encoding="utf-8")

        harness = BenchmarkHarness(
            model_manager=mock_model_manager,
            db_path=tmp_db_path,
        )

        assert _history(harness)[0].benchmark_score == 0.72
        assert _history(harness)[0].keyword_coverage == 1.0


class TestVerifiedCodeExecution:
    def test_correct_executed_output_is_verified(self, harness: BenchmarkHarness):
        # Given: a model answer whose code, when executed, prints the expected output.
        answer = "```python\ndef sum_to(n):\n    return n * (n + 1) // 2\nprint(sum_to(100))\n```\n"

        # When: the harness verifies the executed output against the expected value.
        passed, actual = _verify_executed_code(harness, answer, "5050")

        # Then: execution matches and the actual stdout is captured for the report.
        assert passed is True
        assert actual.strip() == "5050"

    def test_wrong_executed_output_is_not_verified(self, harness: BenchmarkHarness):
        # Given: code that prints the wrong value for the expected output.
        answer = "```python\nprint(1234)\n```"

        # When / Then: the verifier rejects it; the mismatched actual output is returned.
        passed, actual = _verify_executed_code(harness, answer, "5050")
        assert passed is False
        assert "1234" in actual

    def test_answer_without_code_block_is_not_verified(self, harness: BenchmarkHarness):
        # Given: prose only — the model narrated the result without runnable code.
        answer = "결과는 5050입니다."

        # When / Then: no code to execute means the case is not verified.
        passed, actual = _verify_executed_code(harness, answer, "5050")
        assert passed is False
        assert "no_code_block" in actual

    def test_execute_single_records_verified_flag_and_adjusts_score(
        self, harness: BenchmarkHarness, mock_model_manager: MagicMock
    ):
        # Given: a verified-code case whose generated answer prints the right value.
        from antigravity_k.engine.benchmark_cases import BenchmarkCase

        case = BenchmarkCase(
            id="verf-test",
            category="verified_code",
            difficulty=1,
            prompt="print 5050",
            expected_output="5050",
        )
        _set_mock_return(mock_model_manager, "generate", "```python\nprint(5050)\n```\n결과는 5050입니다.")

        # When: the harness scores the case.
        result = _execute_single(harness, case, "qwen3.6:latest")

        # Then: the executed output is verified and flagged, and a verified case that
        # merely prints the answer is not penalized for missing explanatory keywords.
        assert result.verified is True
        assert result.verified_output.strip() == "5050"
        assert result.benchmark_score > 0.0

    def test_execute_single_self_corrects_when_first_code_runs_wrong(
        self, harness: BenchmarkHarness, mock_model_manager: MagicMock
    ):
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
        _set_mock_side_effect(mock_model_manager, "generate", [
            "```python\nprint(1234)\n```",
            "```python\nprint(5050)\n```",
        ])

        # When: the harness executes the first answer, detects the mismatch, and revises.
        result = _execute_single(harness, case, "qwen3.6:latest")

        # Then: the agent self-corrected on executable feedback — it iterated to the
        # verified answer rather than accepting the first wrong-but-runnable attempt.
        assert result.verified is True
        assert result.verified_output.strip() == "5050"
        assert result.benchmark_score > 0.0
        assert result.quality_revision_count >= 1
