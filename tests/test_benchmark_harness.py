"""
Antigravity-K: BenchmarkHarness 단위 테스트
============================================
mock ModelManager로 BenchmarkHarness 실행 플로우를 검증합니다.
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.benchmark_cases import BenchmarkCase, get_suite, BUILTIN_CASES
from antigravity_k.engine.benchmark_harness import (
    BenchmarkHarness,
    BenchmarkReport,
    BenchmarkResult,
)
from antigravity_k.engine.quality_gate import QualityGate


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
    manager._registry._raw = {
        "combos": {"collective-council": {"models": ["model-a", "model-b", "model-c"]}}
    }
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
    def test_run_single_case(self, harness, mock_model_manager):
        case = get_suite("sim-001")[0]
        results = harness.run_case(case, targets=["test-model"])

        assert len(results) == 1
        assert results[0].case_id == "sim-001"
        assert results[0].target == "test-model"
        assert results[0].quality_score > 0
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


# ─── 영속화 테스트 ────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load(self, mock_model_manager, tmp_db_path):
        harness1 = BenchmarkHarness(
            model_manager=mock_model_manager, db_path=tmp_db_path
        )
        harness1.run_suite("simple", targets=["test-model"])
        count = len(harness1._history)
        assert count > 0

        # 새 인스턴스에서 로드
        harness2 = BenchmarkHarness(
            model_manager=mock_model_manager, db_path=tmp_db_path
        )
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
            assert "latency_ms" in result
