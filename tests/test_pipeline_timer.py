#!/usr/bin/env python3
"""
Antigravity-K: PipelineTimer 단위 테스트
========================================
PipelineTimer의 record(), get_stats(), measure(), reset() 등을 검증합니다.
"""

import time

import pytest

from antigravity_k.engine.pipeline_timer import (
    PipelineTimer,
    StepStats,
    TimingRecord,
)


@pytest.fixture(autouse=True)
def reset_timer():
    """각 테스트 전 타이머 초기화."""
    PipelineTimer.reset()
    yield
    PipelineTimer.reset()


# ─── TimingRecord 테스트 ─────────────────────────────────────────


class TestTimingRecord:
    """TimingRecord 데이터 모델 검증."""

    def test_default_timestamp(self):
        """timestamp가 없으면 자동 생성."""
        tr = TimingRecord(step="test", duration_ms=100.0)
        assert tr.timestamp, "timestamp should be auto-generated"
        assert "T" in tr.timestamp or " " in tr.timestamp  # ISO format check

    def test_to_dict(self):
        """to_dict() 직렬화."""
        tr = TimingRecord(step="web", duration_ms=150.5, timestamp="2026-01-01T00:00:00")
        d = tr.to_dict()
        assert d["step"] == "web"
        assert d["duration_ms"] == 150.5
        assert d["timestamp"] == "2026-01-01T00:00:00"


# ─── StepStats 테스트 ────────────────────────────────────────────


class TestStepStats:
    """StepStats 누적 통계 검증."""

    def test_single_update(self):
        """단일 업데이트: count=1, min=max=avg=last."""
        ss = StepStats(step="test")
        ss.update(100.0)
        assert ss.count == 1
        assert ss.min_ms == 100.0
        assert ss.max_ms == 100.0
        assert ss.avg_ms == 100.0
        assert ss.last_ms == 100.0

    def test_multiple_updates(self):
        """여러 업데이트: min/max/avg 정확히 계산."""
        ss = StepStats(step="test")
        ss.update(100.0)
        ss.update(200.0)
        ss.update(50.0)
        assert ss.count == 3
        assert ss.min_ms == 50.0
        assert ss.max_ms == 200.0
        assert ss.avg_ms == pytest.approx(116.7, rel=0.01)  # (100+200+50)/3
        assert ss.last_ms == 50.0

    def test_to_dict(self):
        """to_dict() 직렬화."""
        ss = StepStats(step="test")
        ss.update(150.0)
        d = ss.to_dict()
        assert d["step"] == "test"
        assert d["count"] == 1
        assert d["avg_ms"] == 150.0


# ─── PipelineTimer 테스트 ────────────────────────────────────────


class TestPipelineTimer:
    """PipelineTimer 클래스 검증."""

    def test_record_single_step(self):
        """record()로 단일 단계 기록."""
        PipelineTimer.record("web_search", 1500.0)
        stats = PipelineTimer.get_stats()
        assert stats["total_calls"] == 1
        assert "web_search" in stats["steps"]
        assert stats["steps"]["web_search"]["count"] == 1
        assert stats["steps"]["web_search"]["avg_ms"] == 1500.0

    def test_record_multiple_steps(self):
        """여러 단계 기록."""
        PipelineTimer.record("web_search", 1500.0)
        PipelineTimer.record("top1_json", 45.0)
        PipelineTimer.record("extract_all", 89.0)
        stats = PipelineTimer.get_stats()
        assert stats["total_calls"] == 3
        assert len(stats["steps"]) == 3
        assert stats["steps"]["web_search"]["avg_ms"] == 1500.0
        assert stats["steps"]["top1_json"]["avg_ms"] == 45.0

    def test_record_same_step_twice(self):
        """동일 단계 2회 기록 → count=2, avg는 평균."""
        PipelineTimer.record("web_search", 1000.0)
        PipelineTimer.record("web_search", 2000.0)
        stats = PipelineTimer.get_stats()
        assert stats["steps"]["web_search"]["count"] == 2
        assert stats["steps"]["web_search"]["avg_ms"] == 1500.0
        assert stats["steps"]["web_search"]["min_ms"] == 1000.0
        assert stats["steps"]["web_search"]["max_ms"] == 2000.0

    def test_get_stats_empty(self):
        """기록 없이 get_stats() → 빈 결과."""
        stats = PipelineTimer.get_stats()
        assert stats["total_calls"] == 0
        assert stats["steps"] == {}
        assert stats["recent"] == []
        assert stats["pipeline_total_avg_ms"] == 0.0

    def test_recent_records(self):
        """최근 기록 보관 확인."""
        PipelineTimer.record("step1", 100.0)
        PipelineTimer.record("step2", 200.0)
        stats = PipelineTimer.get_stats()
        assert len(stats["recent"]) == 2
        assert stats["recent"][0]["step"] == "step1"
        assert stats["recent"][1]["step"] == "step2"

    def test_recent_records_max_limit(self):
        """최대 보관 수 제한 (200개)."""
        for i in range(250):
            PipelineTimer.record(f"step{i}", float(i))
        stats = PipelineTimer.get_stats()
        assert len(stats["recent"]) == 10  # get_stats는 최근 10개만 반환
        # 내부 보관은 200개
        recent = PipelineTimer.get_recent(300)
        assert len(recent) == 200  # max_recent = 200

    def test_get_step_stats_exists(self):
        """존재하는 단계 조회."""
        PipelineTimer.record("web_search", 1500.0)
        ss = PipelineTimer.get_step_stats("web_search")
        assert ss is not None
        assert ss.count == 1

    def test_get_step_stats_not_exists(self):
        """존재하지 않는 단계 조회 → None."""
        ss = PipelineTimer.get_step_stats("nonexistent")
        assert ss is None

    def test_get_recent(self):
        """get_recent()로 최근 N개 조회."""
        for i in range(5):
            PipelineTimer.record(f"step{i}", float(i * 100))
        recent = PipelineTimer.get_recent(3)
        assert len(recent) == 3
        assert recent[0].step == "step2"

    def test_get_recent_limit_beyond(self):
        """limit이 총 기록보다 커도 안전."""
        PipelineTimer.record("test", 100.0)
        recent = PipelineTimer.get_recent(100)
        assert len(recent) == 1

    def test_reset_clears_all(self):
        """reset()으로 모든 데이터 초기화."""
        PipelineTimer.record("web_search", 1500.0)
        PipelineTimer.reset()
        stats = PipelineTimer.get_stats()
        assert stats["total_calls"] == 0
        assert stats["steps"] == {}

    def test_measure_context_manager(self):
        """with PipelineTimer.measure() 사용."""
        with PipelineTimer.measure("context_test"):
            time.sleep(0.001)  # 1ms 대기
        stats = PipelineTimer.get_stats()
        assert stats["steps"]["context_test"]["count"] == 1
        assert stats["steps"]["context_test"]["avg_ms"] > 0.5

    def test_pipeline_total_avg(self):
        """파이프라인 전체 평균 계산."""
        PipelineTimer.record("web_search", 1500.0)
        PipelineTimer.record("extract_all", 100.0)
        stats = PipelineTimer.get_stats()
        assert stats["pipeline_total_avg_ms"] == pytest.approx(1600.0, rel=0.1)

    def test_record_step_alias(self):
        """record_step() 별칭 동작."""
        PipelineTimer.record_step("test_step", 500.0)
        stats = PipelineTimer.get_step_stats("test_step")
        assert stats is not None
        assert stats.count == 1

    def test_empty_get_recent(self):
        """기록 없이 get_recent() → 빈 리스트."""
        assert PipelineTimer.get_recent() == []
