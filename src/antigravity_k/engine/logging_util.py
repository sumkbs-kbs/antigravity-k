"""Antigravity-K: 구조화 로깅 유틸리티 (Structured Logging).

=========================================================
ad-hoc logger.info 호출을 JSON-lines 형식의 구조화 로그로 대체합니다.
downstream 분석과 대시보드 연동을 위해 timestamp, level, component, message,
metadata를 포함하는 표준 포맷을 제공합니다.

사용법:
    from antigravity_k.engine.logging_util import structured_log, MetricsCollector

    structured_log("orchestrator", "info", "Turn started", {"trace_id": "abc123"})

    metrics = MetricsCollector()
    metrics.start_turn()
    metrics.record_tool_call("read_file", latency_ms=42.5, success=True)
    metrics.end_turn(tokens_in=500, tokens_out=200)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("antigravity_k.logging_util")


def structured_log(
    component: str,
    level: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    """구조화된 JSON-line 로그를 생성하고 파일에 기록합니다.

    Args:
        component: 로그를 발생시킨 컴포넌트 이름
        level: 로그 레벨 (debug, info, warning, error)
        message: 로그 메시지
        metadata: 추가 메타데이터 딕셔너리
        log_dir: 로그 파일 디렉토리 (기본: logs/)

    Returns:
        생성된 로그 엔트리 딕셔너리

    """
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ts_epoch": time.time(),
        "level": level.upper(),
        "component": component,
        "message": message,
    }
    if metadata:
        entry["metadata"] = metadata

    # 표준 Python 로거에도 전달
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(f"[{component}] {message}")

    # JSON-lines 파일 기록
    if log_dir is None:
        log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "structured.jsonl")

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to write structured log")

    return entry


@dataclass
class TurnMetrics:
    """단일 턴의 성능 메트릭."""

    turn_id: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    tool_failures: int = 0
    guardrail_violations: int = 0
    tool_details: list[dict[str, Any]] = field(default_factory=list)


class MetricsCollector:
    """턴별 성능 메트릭을 수집하고 JSON-lines로 기록하는 싱글턴.

    Thread-safe하며 동시에 여러 턴이 진행되는 상황에서도 안전합니다.
    """

    _instance: MetricsCollector | None = None
    _initialized: bool = False
    _lock = threading.Lock()

    def __new__(cls, log_dir: str | None = None) -> MetricsCollector:
        """Create a new instance.

        Args:
            log_dir (str | None): str | None log dir.

        Returns:
            MetricsCollector: The metricscollector result.

        """
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                cls._instance = instance
            return cls._instance

    def __init__(self, log_dir: str | None = None):
        """Initialize the MetricsCollector.

        Args:
            log_dir (str | None): str | None log dir.

        """
        if self._initialized:
            return
        self._initialized = True
        self._log_dir = log_dir or os.path.join(os.getcwd(), "logs")
        self._turn_counter = 0
        self._current: TurnMetrics | None = None
        self._history: list[TurnMetrics] = []
        self._data_lock = threading.Lock()

    def start_turn(self) -> int:
        """새 턴의 메트릭 수집을 시작합니다. 턴 ID를 반환합니다."""
        with self._data_lock:
            self._turn_counter += 1
            self._current = TurnMetrics(
                turn_id=self._turn_counter,
                start_time=time.time(),
            )
            return self._turn_counter

    def record_tool_call(
        self,
        tool_name: str,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """도구 호출 메트릭을 기록합니다."""
        with self._data_lock:
            if not self._current:
                return
            self._current.tool_calls += 1
            if not success:
                self._current.tool_failures += 1
            self._current.tool_details.append(
                {
                    "name": tool_name,
                    "latency_ms": latency_ms,
                    "success": success,
                    "timestamp": time.time(),
                },
            )

    def record_guardrail_violation(self, code: str = "") -> None:
        """가드레일 위반을 기록합니다."""
        with self._data_lock:
            if not self._current:
                return
            self._current.guardrail_violations += 1

    def end_turn(self, tokens_in: int = 0, tokens_out: int = 0) -> TurnMetrics | None:
        """턴을 종료하고 메트릭을 JSON-lines 파일에 기록합니다."""
        with self._data_lock:
            if not self._current:
                return None

            self._current.end_time = time.time()
            self._current.latency_ms = (self._current.end_time - self._current.start_time) * 1000
            self._current.tokens_in = tokens_in
            self._current.tokens_out = tokens_out

            completed = self._current
            self._history.append(completed)
            self._current = None

        # 파일 기록 (lock 밖에서)
        self._write_metrics(completed)
        return completed

    def _write_metrics(self, metrics: TurnMetrics) -> None:
        """메트릭을 JSON-lines 파일에 기록합니다."""
        os.makedirs(self._log_dir, exist_ok=True)
        metrics_file = os.path.join(self._log_dir, "metrics.jsonl")

        entry = asdict(metrics)
        entry["type"] = "turn_metrics"

        try:
            with open(metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write metrics")

    def get_summary(self) -> dict[str, Any]:
        """수집된 모든 턴의 요약 통계를 반환합니다."""
        with self._data_lock:
            if not self._history:
                return {"total_turns": 0}

            latencies = [t.latency_ms for t in self._history]
            return {
                "total_turns": len(self._history),
                "avg_latency_ms": sum(latencies) / len(latencies),
                "max_latency_ms": max(latencies),
                "total_tool_calls": sum(t.tool_calls for t in self._history),
                "total_tool_failures": sum(t.tool_failures for t in self._history),
                "total_guardrail_violations": sum(t.guardrail_violations for t in self._history),
                "total_tokens_in": sum(t.tokens_in for t in self._history),
                "total_tokens_out": sum(t.tokens_out for t in self._history),
            }
