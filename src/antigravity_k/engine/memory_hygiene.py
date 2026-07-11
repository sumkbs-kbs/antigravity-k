"""MemoryHygiene — 메타데이터 기반 자동 클린업.

=============================================
IronClaw hygiene.rs 패턴 이식.

핵심 패턴:
- .config 기반 보존 정책: 디렉토리별 보존 기간/최대 문서 수 설정
- AtomicBool Guard: threading.Lock() 기반 동시 실행 방지 (TOCTOU 방어)
- Atomic State File Writes: 임시 파일 → os.replace() 원자적 교체
- run_if_due(): 주기적 실행 패턴

.config 파일 형식 (YAML):
    retention_days: 30
    max_documents: 1000
    exclude_patterns:
      - "*.important"
      - "HEARTBEAT.md"

사용법:
    hygiene = MemoryHygiene(workspace_root="/path/to/workspace")
    report = hygiene.run_if_due()
    if report.cleaned_count > 0:
        logger.info(f"클린업 완료: {report.cleaned_count}개 파일 제거")
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any

logger = logging.getLogger("antigravity_k.engine.memory_hygiene")


# ── 데이터 클래스 ──


@dataclass(frozen=True)
class RetentionPolicy:
    """디렉토리별 보존 정책."""

    retention_days: int = 30
    max_documents: int = 1000
    exclude_patterns: tuple[str, ...] = ()


@dataclass
class HygieneReport:
    """클린업 보고서."""

    cleaned_count: int = 0
    cleaned_bytes: int = 0
    skipped_count: int = 0
    errors: list[str] = field(default_factory=list)
    directories_scanned: int = 0
    elapsed_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def cleaned_mb(self) -> float:
        """Cleaned Mb.

        Returns:
            float: The float result.

        """
        return round(self.cleaned_bytes / (1024 * 1024), 2)


# ── 메인 MemoryHygiene ──


class MemoryHygiene:
    """메타데이터 기반 자동 클린업.

    IronClaw hygiene.rs 패턴:
    - AtomicBool Guard로 동시 실행 방지
    - 디렉토리별 .config 파일로 보존 정책 로드
    - Atomic State File Writes로 상태 파일 안전 갱신
    """

    _running = threading.Lock()  # IronClaw AtomicBool 대체

    def __init__(
        self,
        workspace_root: str = ".",
        state_file: str = ".hygiene_state.json",
        default_retention_days: int = 30,
        default_max_documents: int = 1000,
        cleanup_interval_hours: float = 24.0,
    ):
        """Initialize the MemoryHygiene.

        Args:
            workspace_root (str): str workspace root.
            state_file (str): str state file.
            default_retention_days (int): int default retention days.
            default_max_documents (int): int default max documents.
            cleanup_interval_hours (float): float cleanup interval hours.

        """
        self.workspace_root = os.path.abspath(workspace_root)
        self._state_file = os.path.join(self.workspace_root, state_file)
        self.default_policy = RetentionPolicy(
            retention_days=default_retention_days,
            max_documents=default_max_documents,
        )
        self.cleanup_interval = cleanup_interval_hours * 3600  # 초 단위
        self._state = self._load_state()

    # ── run_if_due (IronClaw 패턴) ──

    def run_if_due(self) -> HygieneReport | None:
        """클린업 실행 시점이 도래했으면 실행합니다.

        IronClaw 패턴: AtomicBool Guard로 TOCTOU 방지 + 주기 확인.
        """
        # 주기 확인
        last_run = self._state.get("last_run", 0.0)
        if time.time() - last_run < self.cleanup_interval:
            return None

        # AtomicBool Guard: 동시 실행 방지
        acquired = self._running.acquire(blocking=False)
        if not acquired:
            logger.debug("MemoryHygiene: 이미 실행 중 — 스킵")
            return None

        try:
            report = self._execute_cleanup()
            # 상태 저장 (atomic)
            self._state["last_run"] = time.time()
            self._state["last_report"] = {
                "cleaned_count": report.cleaned_count,
                "cleaned_bytes": report.cleaned_bytes,
                "elapsed_ms": report.elapsed_ms,
            }
            self._save_state_atomic(self._state)
            return report
        finally:
            self._running.release()

    def force_cleanup(self) -> HygieneReport:
        """강제 클린업을 실행합니다 (주기 무시)."""
        acquired = self._running.acquire(blocking=False)
        if not acquired:
            return HygieneReport(errors=["이미 실행 중"])

        try:
            report = self._execute_cleanup()
            self._state["last_run"] = time.time()
            self._save_state_atomic(self._state)
            return report
        finally:
            self._running.release()

    # ── 보존 정책 적용 ──

    def apply_retention_policy(self, directory: str) -> int:
        """디렉토리에 보존 정책을 적용합니다.

        Returns:
            제거된 파일 수

        """
        policy = self._load_directory_policy(directory)
        if not os.path.isdir(directory):
            return 0

        now = time.time()
        cutoff = now - (policy.retention_days * 86400)
        removed = 0

        # 파일 목록 수집 (수정 시각 기준 정렬)
        files_with_mtime = []
        for entry in os.scandir(directory):
            if not entry.is_file():
                continue
            if self._is_excluded(entry.name, policy.exclude_patterns):
                continue
            try:
                mtime = entry.stat().st_mtime
                files_with_mtime.append((entry.path, mtime, entry.stat().st_size))
            except OSError:
                continue

        files_with_mtime.sort(key=lambda x: x[1])  # 오래된 것 먼저

        # 보존 기간 초과 파일 제거
        for path, mtime, size in files_with_mtime:
            if mtime < cutoff:
                try:
                    os.remove(path)
                    removed += 1
                    logger.debug("MemoryHygiene: 제거 (기간 초과) %s", path)
                except OSError as e:
                    logger.warning("MemoryHygiene: 제거 실패 %s: %s", path, e)

        # 최대 문서 수 초과 시 오래된 순으로 제거
        remaining = [f for f in files_with_mtime if os.path.exists(f[0])]
        if len(remaining) > policy.max_documents:
            excess = len(remaining) - policy.max_documents
            for path, _, _ in remaining[:excess]:
                try:
                    os.remove(path)
                    removed += 1
                    logger.debug("MemoryHygiene: 제거 (한도 초과) %s", path)
                except OSError as e:
                    logger.warning("MemoryHygiene: 제거 실패 %s: %s", path, e)

        return removed

    # ── Atomic State File Writes (IronClaw 패턴) ──

    def _save_state_atomic(self, state: dict[str, Any]) -> None:
        """상태를 원자적으로 저장합니다.

        IronClaw 패턴: tmpfile → os.replace() 원자적 교체.
        """
        try:
            parent_dir = os.path.dirname(self._state_file)
            fd, tmp_path = tempfile.mkstemp(dir=parent_dir, prefix=".hygiene_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._state_file)
            except Exception:
                # 임시 파일 정리
                try:
                    os.unlink(tmp_path)
                except OSError:
                    logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)
                raise
        except Exception:
            logger.exception("MemoryHygiene: 상태 저장 실패")

    def _load_state(self) -> dict[str, Any]:
        """상태 파일을 로드합니다."""
        if not os.path.isfile(self._state_file):
            return {"last_run": 0.0}
        try:
            with open(self._state_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception("MemoryHygiene: 상태 로드 실패")
            return {"last_run": 0.0}

    # ── 내부 실행 ──

    def _execute_cleanup(self) -> HygieneReport:
        """실제 클린업을 실행합니다."""
        start = time.time()
        report = HygieneReport()

        # 워크스페이스 내 주요 디렉토리 스캔
        scan_dirs = self._get_scan_directories()

        for directory in scan_dirs:
            if not os.path.isdir(directory):
                continue
            report.directories_scanned += 1
            try:
                cleaned = self.apply_retention_policy(directory)
                report.cleaned_count += cleaned
            except Exception as e:
                logger.exception("Unhandled exception")
                report.errors.append(f"{directory}: {e}")

        report.elapsed_ms = round((time.time() - start) * 1000, 1)
        logger.info(
            "MemoryHygiene: 클린업 완료 — %s개 제거, %s개 디렉토리, %sms",
            report.cleaned_count,
            report.directories_scanned,
            report.elapsed_ms,
        )
        return report

    def _get_scan_directories(self) -> list[str]:
        """스캔할 디렉토리 목록을 반환합니다."""
        candidates = [
            os.path.join(self.workspace_root, "data", "logs"),
            os.path.join(self.workspace_root, "data", "cache"),
            os.path.join(self.workspace_root, "data", "temp"),
            os.path.join(self.workspace_root, ".agent", "scratch"),
        ]
        return [d for d in candidates if os.path.isdir(d)]

    def _load_directory_policy(self, directory: str) -> RetentionPolicy:
        """디렉토리의 .config 파일에서 보존 정책을 로드합니다."""
        config_file = os.path.join(directory, ".config")
        if not os.path.isfile(config_file):
            return self.default_policy

        try:
            import yaml

            with open(config_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            return RetentionPolicy(
                retention_days=int(data.get("retention_days", self.default_policy.retention_days)),
                max_documents=int(data.get("max_documents", self.default_policy.max_documents)),
                exclude_patterns=tuple(data.get("exclude_patterns", [])),
            )
        except Exception:
            logger.exception("MemoryHygiene: .config 로드 실패 (%s)", config_file)
            return self.default_policy

    @staticmethod
    def _is_excluded(filename: str, patterns: tuple[str, ...]) -> bool:
        """파일이 제외 패턴에 매칭되는지 확인합니다."""
        for pattern in patterns:
            if fnmatch(filename, pattern):
                return True
        return False

    # ── 상태 보고 ──

    def get_status(self) -> dict[str, Any]:
        """메모리 위생 상태를 반환합니다."""
        last_run = self._state.get("last_run", 0.0)
        next_run = last_run + self.cleanup_interval if last_run > 0 else 0.0
        return {
            "last_run": last_run,
            "next_run": next_run,
            "seconds_until_next": max(0, next_run - time.time()),
            "workspace_root": self.workspace_root,
            "last_report": self._state.get("last_report"),
            "default_retention_days": self.default_policy.retention_days,
            "default_max_documents": self.default_policy.max_documents,
        }
