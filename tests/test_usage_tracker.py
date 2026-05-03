"""
테스트: 사용량 추적기
====================
UsageTracker의 기록/조회/통계/영속화 테스트.
"""
import json
import time
import tempfile
from pathlib import Path

import pytest

from antigravity_k.engine.usage_tracker import (
    UsageRecord,
    UsageStats,
    UsageTracker,
)


# ─── 픽스처 ─────────────────────────────────────────────────────────

@pytest.fixture
def tracker():
    """메모리 전용 추적기 (DB 파일 없음)"""
    return UsageTracker(db_path=None, max_records=100)


@pytest.fixture
def tracker_with_db(tmp_path):
    """임시 DB 파일 사용 추적기"""
    db_path = tmp_path / "test_usage.json"
    return UsageTracker(db_path=str(db_path), auto_save_interval=5)


# ─── 기록 테스트 ─────────────────────────────────────────────────────

class TestRecord:
    """기록 API 테스트"""

    def test_basic_record(self, tracker):
        entry = tracker.record(
            "qwen3-72b", tokens_in=100, tokens_out=500,
            latency_ms=1200, success=True,
        )
        assert entry.model_name == "qwen3-72b"
        assert entry.tokens_in == 100
        assert entry.tokens_out == 500
        assert entry.total_tokens == 600
        assert entry.success is True

    def test_failure_record(self, tracker):
        entry = tracker.record(
            "model-a", success=False, error="OOM",
        )
        assert entry.success is False
        assert entry.error == "OOM"

    def test_combo_record(self, tracker):
        entry = tracker.record(
            "model-b", combo_name="coding-stack", fallback_depth=2,
        )
        assert entry.combo_name == "coding-stack"
        assert entry.fallback_depth == 2

    def test_max_records_limit(self):
        tracker = UsageTracker(db_path=None, max_records=5)
        for i in range(10):
            tracker.record(f"model-{i}")
        assert len(tracker._records) == 5

    def test_timestamp_set(self, tracker):
        before = time.time()
        entry = tracker.record("model-a")
        after = time.time()
        assert before <= entry.timestamp <= after


# ─── 통계 테스트 ─────────────────────────────────────────────────────

class TestStats:
    """통계 조회 테스트"""

    def test_empty_stats(self, tracker):
        stats = tracker.get_stats()
        assert stats == []

    def test_daily_stats(self, tracker):
        for _ in range(5):
            tracker.record("qwen3-72b", tokens_in=10, tokens_out=50,
                           latency_ms=100, success=True)
        tracker.record("qwen3-72b", success=False, error="fail")

        stats = tracker.get_stats("qwen3-72b", period="daily")
        assert len(stats) == 1
        s = stats[0]
        assert s.total_requests == 6
        assert s.success_count == 5
        assert s.failure_count == 1
        assert s.success_rate == pytest.approx(83.3, rel=0.1)

    def test_per_model_stats(self, tracker):
        tracker.record("model-a", tokens_in=10)
        tracker.record("model-b", tokens_in=20)
        tracker.record("model-a", tokens_in=30)

        all_stats = tracker.get_stats(period="total")
        assert len(all_stats) == 2

        a_stats = tracker.get_stats("model-a", period="total")
        assert len(a_stats) == 1
        assert a_stats[0].total_requests == 2

    def test_latency_stats(self, tracker):
        tracker.record("model-a", latency_ms=100, success=True)
        tracker.record("model-a", latency_ms=200, success=True)
        tracker.record("model-a", latency_ms=300, success=True)

        stats = tracker.get_stats("model-a", period="total")
        s = stats[0]
        assert s.avg_latency_ms == pytest.approx(200.0)
        assert s.min_latency_ms == 100
        assert s.max_latency_ms == 300

    def test_fallback_count(self, tracker):
        tracker.record("model-a", fallback_depth=0)
        tracker.record("model-b", fallback_depth=1)
        tracker.record("model-c", fallback_depth=2)

        stats = tracker.get_stats(period="total")
        total_fallback = sum(s.fallback_count for s in stats)
        assert total_fallback == 2  # depth > 0


# ─── 최근 기록 / 모델 목록 ──────────────────────────────────────────

class TestRecent:
    def test_get_recent(self, tracker):
        for i in range(10):
            tracker.record(f"model-{i}")
        recent = tracker.get_recent(5)
        assert len(recent) == 5
        assert recent[0].model_name == "model-9"  # 최근순

    def test_get_model_names(self, tracker):
        tracker.record("a")
        tracker.record("b")
        tracker.record("a")
        names = tracker.get_model_names()
        assert set(names) == {"a", "b"}


# ─── 대시보드 데이터 ─────────────────────────────────────────────────

class TestDashboard:
    def test_dashboard_data_structure(self, tracker):
        tracker.record("model-a", tokens_in=10, tokens_out=50)
        data = tracker.to_dashboard_data()
        assert "daily" in data
        assert "total" in data
        assert "hourly_trend" in data
        assert data["total_records"] == 1
        assert "model-a" in data["models_used"]


# ─── 영속화 테스트 ───────────────────────────────────────────────────

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        db_path = str(tmp_path / "usage.json")

        # 기록 & 저장
        t1 = UsageTracker(db_path=db_path)
        t1.record("model-a", tokens_in=100)
        t1.record("model-b", tokens_in=200)
        t1.save()

        # 새 인스턴스에서 로드
        t2 = UsageTracker(db_path=db_path)
        assert len(t2._records) == 2
        assert t2._records[0].model_name == "model-a"

    def test_auto_save(self, tmp_path):
        db_path = str(tmp_path / "usage.json")
        t = UsageTracker(db_path=db_path, auto_save_interval=3)
        t.record("a")
        t.record("b")
        assert not Path(db_path).exists()  # 아직 3건 미만
        t.record("c")
        assert Path(db_path).exists()  # 3건 도달 → 자동 저장

    def test_corrupt_db(self, tmp_path):
        db_path = tmp_path / "corrupt.json"
        db_path.write_text("NOT JSON", encoding="utf-8")
        t = UsageTracker(db_path=str(db_path))
        assert len(t._records) == 0  # 오류 시 빈 상태로 초기화


# ─── UsageStats 테스트 ───────────────────────────────────────────────

class TestUsageStats:
    def test_success_rate(self):
        s = UsageStats(
            model_name="test", period="daily",
            total_requests=10, success_count=8, failure_count=2,
        )
        assert s.success_rate == 80.0

    def test_zero_requests(self):
        s = UsageStats(model_name="test", period="daily")
        assert s.success_rate == 0.0

    def test_to_dict(self):
        s = UsageStats(
            model_name="test", period="daily",
            total_requests=5, total_tokens_in=100, total_tokens_out=200,
        )
        d = s.to_dict()
        assert d["total_tokens"] == 300
        assert "success_rate" in d

    def test_clear(self, tracker):
        tracker.record("a")
        tracker.record("b")
        tracker.clear()
        assert len(tracker._records) == 0
