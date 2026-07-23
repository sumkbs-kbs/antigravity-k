"""Tests for antigravity_k.tools.self_evolution_tool.

Coverage targets:
  - SelfRewardEvaluator: evaluate(), suggest_improvements(), get_trend(), _score_to_grade()
  - MetacognitiveTracker: record_evolution_cycle(), get_effectiveness_report(),
    detect_failure_patterns(), _save()
  - Edge cases: empty inputs, zero scores, boundary conditions
"""

import json
import os
import tempfile

from antigravity_k.tools.self_evolution_tool import (
    MetacognitiveTracker,
    SelfRewardEvaluator,
)

# ═══════════════════════════════════════════════════════════════════
# SelfRewardEvaluator tests
# ═══════════════════════════════════════════════════════════════════


class TestSelfRewardEvaluatorInit:
    """SelfRewardEvaluator 생성 및 기본 속성."""

    def test_default_threshold(self):
        evaluator = SelfRewardEvaluator()
        assert evaluator.threshold == 7.0

    def test_custom_threshold(self):
        evaluator = SelfRewardEvaluator(threshold=5.0)
        assert evaluator.threshold == 5.0

    def test_empty_history(self):
        evaluator = SelfRewardEvaluator()
        assert evaluator._history == []


class TestSelfRewardEvaluatorEvaluate:
    """evaluate() — 휴리스틱 기반 자가 평가."""

    def test_high_quality_output(self):
        """완전하고 에러 없는 출력 — 높은 점수."""
        evaluator = SelfRewardEvaluator(threshold=5.0)
        output = "This is a detailed and complete response covering all aspects of the user query."
        result = evaluator.evaluate("detailed explanation", output)
        assert result["avg"] >= 7.0
        assert result["grade"] in ("A", "S")
        assert not result["needs_improvement"]

    def test_error_output_lowers_accuracy(self):
        """에러가 포함된 출력 — accuracy 점수 낮음."""
        evaluator = SelfRewardEvaluator()
        output = "Error: something went wrong\nTraceback: ...\nException: failed"
        result = evaluator.evaluate("run command", output)
        assert result["scores"]["accuracy"] <= 6

    def test_very_short_output_low_completeness(self):
        """매우 짧은 출력 — completeness 점수 낮음."""
        evaluator = SelfRewardEvaluator()
        result = evaluator.evaluate("complex task", "OK")
        assert result["scores"]["completeness"] <= 5

    def test_long_output_high_completeness(self):
        """충분히 긴 출력 — completeness 점수 높음."""
        evaluator = SelfRewardEvaluator()
        output = "A" * 600
        result = evaluator.evaluate("long task", output)
        assert result["scores"]["completeness"] >= 7

    def test_duplicate_lines_lower_efficiency(self):
        """중복 라인이 많은 출력 — efficiency 점수 낮음."""
        evaluator = SelfRewardEvaluator()
        output = "same line\n" * 20
        result = evaluator.evaluate("test", output)
        assert result["scores"]["efficiency"] <= 6

    def test_keyword_match_affects_satisfaction(self):
        """태스크 키워드가 출력에 포함되면 satisfaction 점수 증가."""
        evaluator = SelfRewardEvaluator()
        output = "This is about python programming and async patterns"
        result = evaluator.evaluate("python async programming guide", output)
        assert result["scores"]["user_satisfaction"] >= 5

    def test_result_structure(self):
        """결과 딕셔너리에 필요한 모든 키가 포함됨."""
        evaluator = SelfRewardEvaluator()
        result = evaluator.evaluate("test", "some output")
        assert "scores" in result
        assert "avg" in result
        assert "grade" in result
        assert "weaknesses" in result
        assert "needs_improvement" in result
        assert all(c in result["scores"] for c in SelfRewardEvaluator.CRITERIA)

    def test_history_recorded(self):
        """평가 결과가 히스토리에 기록됨."""
        evaluator = SelfRewardEvaluator()
        evaluator.evaluate("task1", "output1")
        evaluator.evaluate("task2", "output2")
        assert len(evaluator._history) == 2
        assert "task1" in evaluator._history[0]["task"]
        assert "task2" in evaluator._history[1]["task"]

    def test_low_score_detects_weaknesses(self):
        """낮은 점수 항목이 weaknesses에 포함됨."""
        evaluator = SelfRewardEvaluator(threshold=9.0)
        result = evaluator.evaluate("complex", "OK")
        assert len(result["weaknesses"]) >= 1

    def test_perfect_score_no_weaknesses(self):
        """만점에 가까우면 weaknesses가 없음."""
        evaluator = SelfRewardEvaluator(threshold=1.0)
        output = "A" * 600 + "\n" + "B" * 600
        result = evaluator.evaluate("python programming", output)
        # threshold가 매우 낮아 모든 점수가 통과
        assert len(result["weaknesses"]) == 0

    def test_empty_task_handling(self):
        """빈 태스크 입력 처리."""
        evaluator = SelfRewardEvaluator()
        result = evaluator.evaluate("", "some output")
        assert result["avg"] > 0

    def test_non_string_output_handling(self):
        """숫자 등 비문자열 출력 처리."""
        evaluator = SelfRewardEvaluator()
        result = evaluator.evaluate("task", str(42))
        assert result["scores"]["completeness"] <= 5


class TestSelfRewardEvaluatorSuggestImprovements:
    """suggest_improvements() — 낮은 점수 항목에 대한 개선 제안."""

    def test_accuracy_improvement(self):
        """accuracy 점수 낮을 때 정확성 개선 제안 포함."""
        evaluator = SelfRewardEvaluator()
        evaluation = {
            "scores": {"accuracy": 3, "completeness": 8, "efficiency": 8, "user_satisfaction": 8},
        }
        suggestions = evaluator.suggest_improvements(evaluation)
        titles = " ".join(suggestions)
        assert "정확성" in titles

    def test_completeness_improvement(self):
        """completeness 점수 낮을 때 완전성 개선 제안."""
        evaluator = SelfRewardEvaluator()
        evaluation = {
            "scores": {"accuracy": 8, "completeness": 4, "efficiency": 8, "user_satisfaction": 8},
        }
        suggestions = evaluator.suggest_improvements(evaluation)
        titles = " ".join(suggestions)
        assert "완전성" in titles

    def test_efficiency_improvement(self):
        """efficiency 점수 낮을 때 효율성 개선 제안."""
        evaluator = SelfRewardEvaluator()
        evaluation = {
            "scores": {"accuracy": 8, "completeness": 8, "efficiency": 3, "user_satisfaction": 8},
        }
        suggestions = evaluator.suggest_improvements(evaluation)
        titles = " ".join(suggestions)
        assert "효율성" in titles

    def test_satisfaction_improvement(self):
        """user_satisfaction 점수 낮을 때 만족도 개선 제안."""
        evaluator = SelfRewardEvaluator()
        evaluation = {
            "scores": {"accuracy": 8, "completeness": 8, "efficiency": 8, "user_satisfaction": 3},
        }
        suggestions = evaluator.suggest_improvements(evaluation)
        titles = " ".join(suggestions)
        assert "만족도" in titles

    def test_all_high_no_suggestions(self):
        """모든 점수가 높으면 빈 리스트."""
        evaluator = SelfRewardEvaluator()
        evaluation = {
            "scores": {"accuracy": 9, "completeness": 9, "efficiency": 9, "user_satisfaction": 9},
        }
        suggestions = evaluator.suggest_improvements(evaluation)
        assert suggestions == []

    def test_multiple_low(self):
        """여러 항목이 낮으면 각각에 대한 제안."""
        evaluator = SelfRewardEvaluator()
        evaluation = {
            "scores": {"accuracy": 3, "completeness": 4, "efficiency": 9, "user_satisfaction": 9},
        }
        suggestions = evaluator.suggest_improvements(evaluation)
        assert len(suggestions) >= 2


class TestSelfRewardEvaluatorScoreToGrade:
    """_score_to_grade() — 점수에 따른 등급."""

    def test_grade_s(self):
        assert SelfRewardEvaluator._score_to_grade(9.5) == "S"
        assert SelfRewardEvaluator._score_to_grade(9.0) == "S"

    def test_grade_a(self):
        assert SelfRewardEvaluator._score_to_grade(8.0) == "A"
        assert SelfRewardEvaluator._score_to_grade(8.9) == "A"

    def test_grade_b(self):
        assert SelfRewardEvaluator._score_to_grade(7.0) == "B"
        assert SelfRewardEvaluator._score_to_grade(7.9) == "B"

    def test_grade_c(self):
        assert SelfRewardEvaluator._score_to_grade(5.0) == "C"
        assert SelfRewardEvaluator._score_to_grade(6.9) == "C"

    def test_grade_f(self):
        assert SelfRewardEvaluator._score_to_grade(4.9) == "F"
        assert SelfRewardEvaluator._score_to_grade(0.0) == "F"

    def test_boundary_values(self):
        """경계값 테스트."""
        assert SelfRewardEvaluator._score_to_grade(8.999) == "A"
        assert SelfRewardEvaluator._score_to_grade(7.001) == "B"
        assert SelfRewardEvaluator._score_to_grade(5.001) == "C"


class TestSelfRewardEvaluatorGetTrend:
    """get_trend() — 최근 평가 트렌드 분석."""

    def test_empty_history(self):
        """히스토리가 없으면 적절한 메시지."""
        evaluator = SelfRewardEvaluator()
        trend = evaluator.get_trend()
        assert trend["improving"] is None
        assert trend["avg_trend"] == []

    def test_single_entry(self):
        """단일 기록에서 트렌드."""
        evaluator = SelfRewardEvaluator()
        evaluator.evaluate("task", "good output that is long enough for testing" * 10)
        trend = evaluator.get_trend(last_n=10)
        assert len(trend["avg_trend"]) == 1
        assert trend["improving"] is None  # 3개 미만이므로 None

    def test_multiple_entries_trend(self):
        """여러 기록에서 개선/악화 트렌드."""
        evaluator = SelfRewardEvaluator()
        # 더 나빠지는 출력
        for i in range(5):
            output = "OK" if i > 2 else "A very long and detailed output that is complete " * 20
            evaluator.evaluate("task", output)
        trend = evaluator.get_trend(last_n=10)
        # 5개 이상 기록이 있으므로 improving은 bool
        assert isinstance(trend["improving"], bool)


# ═══════════════════════════════════════════════════════════════════
# MetacognitiveTracker tests
# ═══════════════════════════════════════════════════════════════════


class TestMetacognitiveTrackerInit:
    """MetacognitiveTracker 생성 및 기본 속성."""

    def test_default_persist_path(self):
        tracker = MetacognitiveTracker()
        assert tracker._persist_path is None
        assert tracker._cycles == []

    def test_custom_persist_path(self):
        tracker = MetacognitiveTracker(persist_path="/tmp/test_meta.json")
        assert tracker._persist_path == "/tmp/test_meta.json"


class TestMetacognitiveTrackerRecord:
    """record_evolution_cycle() — 진화 사이클 기록."""

    def test_single_record(self):
        tracker = MetacognitiveTracker()
        tracker.record_evolution_cycle("fix bug", 5.0, 7.0, True, "improved validation")
        assert len(tracker._cycles) == 1
        cycle = tracker._cycles[0]
        assert cycle["task"] == "fix bug"
        assert cycle["before"] == 5.0
        assert cycle["after"] == 7.0
        assert cycle["delta"] == 2.0
        assert cycle["improved"] is True
        assert cycle["improvement_applied"] is True

    def test_regression_record(self):
        """점수가 하락한 사이클 기록."""
        tracker = MetacognitiveTracker()
        tracker.record_evolution_cycle("bad change", 7.0, 5.0, True, "made things worse")
        cycle = tracker._cycles[0]
        assert cycle["delta"] == -2.0
        assert cycle["improved"] is False

    def test_no_improvement_applied(self):
        """개선이 적용되지 않은 사이클."""
        tracker = MetacognitiveTracker()
        tracker.record_evolution_cycle("test", 5.0, 5.0, False)
        assert tracker._cycles[0]["improvement_applied"] is False

    def test_multiple_records(self):
        tracker = MetacognitiveTracker()
        for i in range(5):
            tracker.record_evolution_cycle(f"task{i}", float(i), float(i + 1), True)
        assert len(tracker._cycles) == 5

    def test_task_truncation(self):
        """긴 태스크 이름은 200자로 제한."""
        tracker = MetacognitiveTracker()
        long_task = "A" * 500
        tracker.record_evolution_cycle(long_task, 5.0, 7.0, True)
        assert len(tracker._cycles[0]["task"]) == 200


class TestMetacognitiveTrackerGetEffectiveness:
    """get_effectiveness_report() — 진화 효과 보고서."""

    def test_no_cycles(self):
        tracker = MetacognitiveTracker()
        report = tracker.get_effectiveness_report()
        assert "message" in report

    def test_all_successful(self):
        tracker = MetacognitiveTracker()
        for i in range(3):
            tracker.record_evolution_cycle(f"task{i}", 5.0, 7.0, True)
        report = tracker.get_effectiveness_report()
        assert report["total_cycles"] == 3
        assert report["improvements_applied"] == 3
        assert report["effective_improvements"] == 3
        assert "100%" in report["effectiveness_rate"]
        assert report["avg_score_change"] > 0

    def test_some_failures(self):
        tracker = MetacognitiveTracker()
        tracker.record_evolution_cycle("good change", 5.0, 8.0, True)
        tracker.record_evolution_cycle("bad change", 7.0, 4.0, True)
        tracker.record_evolution_cycle("no change", 6.0, 6.0, False)
        report = tracker.get_effectiveness_report()
        assert report["total_cycles"] == 3
        assert report["improvements_applied"] == 2
        assert report["effective_improvements"] == 1

    def test_best_and_worst(self):
        """최고/최악의 개선 식별."""
        tracker = MetacognitiveTracker()
        tracker.record_evolution_cycle("small", 5.0, 6.0, True)
        tracker.record_evolution_cycle("big", 3.0, 9.0, True)
        tracker.record_evolution_cycle("regression", 8.0, 3.0, True)
        report = tracker.get_effectiveness_report()
        assert report["best_improvement"] is not None
        assert report["worst_regression"] is not None
        assert report["best_improvement"]["delta"] > report["worst_regression"]["delta"]


class TestMetacognitiveTrackerDetectPatterns:
    """detect_failure_patterns() — 반복 실패 패턴 감지."""

    def test_no_failures(self):
        tracker = MetacognitiveTracker()
        patterns = tracker.detect_failure_patterns()
        assert patterns == []

    def test_recent_failures_detected(self):
        """최근 3개 이상 실패 시 패턴 감지."""
        tracker = MetacognitiveTracker()
        for i in range(5):
            tracker.record_evolution_cycle(f"fail{i}", 5.0, 4.0, True)
        patterns = tracker.detect_failure_patterns()
        assert len(patterns) >= 1

    def test_score_stagnation_detected(self):
        """점수 정체 패턴 감지."""
        tracker = MetacognitiveTracker()
        for i in range(10):
            tracker.record_evolution_cycle(f"task{i}", 5.0, 5.1, True)
        patterns = tracker.detect_failure_patterns()
        stasis_patterns = [p for p in patterns if "정체" in p or "stagnation" in p.lower()]
        assert len(stasis_patterns) >= 1


class TestMetacognitiveTrackerSave:
    """_save() — 디스크 저장."""

    def test_save_and_load(self):
        """저장된 데이터를 다시 로드할 수 있음."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            tracker = MetacognitiveTracker(persist_path=tmp_path)
            tracker.record_evolution_cycle("test task", 5.0, 8.0, True, "improved")
            tracker._save()

            assert os.path.exists(tmp_path)
            with open(tmp_path, encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["task"] == "test task"
            assert data[0]["delta"] == 3.0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_no_persist_path_no_error(self):
        """persist_path가 None이면 저장하지 않고 에러 없음."""
        tracker = MetacognitiveTracker()
        tracker.record_evolution_cycle("test", 5.0, 7.0, True)
        tracker._save()  # should not raise


class TestMetacognitiveTrackerEdgeCases:
    """엣지 케이스."""

    def test_repeated_records_accumulate(self):
        """반복 기록이 누적됨."""
        tracker = MetacognitiveTracker()
        for i in range(100):
            tracker.record_evolution_cycle(f"task-{i}", 5.0, 7.0, True)
        assert len(tracker._cycles) == 100
        report = tracker.get_effectiveness_report()
        assert report["total_cycles"] == 100

    def test_zero_scores(self):
        """0점 처리."""
        tracker = MetacognitiveTracker()
        tracker.record_evolution_cycle("zero test", 0.0, 0.0, True)
        report = tracker.get_effectiveness_report()
        assert report["avg_score_change"] == 0.0

    def test_effectiveness_rate_with_no_applied(self):
        """개선이 하나도 적용되지 않은 경우."""
        tracker = MetacognitiveTracker()
        for i in range(3):
            tracker.record_evolution_cycle(f"task{i}", 5.0, 5.0, False)
        report = tracker.get_effectiveness_report()
        assert report["improvements_applied"] == 0
        # effectiveness_rate는 0으로 나누지 않음 (max(len(applied), 1))
        assert "0%" in report["effectiveness_rate"]
