"""
JSON 구조화 로깅 유틸리티 — 프로덕션 등급 로깅을 위해 표준 Python logging에
JSON 형식 포맷터를 제공합니다.

사용법:
    from antigravity_k.engine.json_logger import setup_json_logging

    # 기본 설정 (콘솔에 JSON 출력)
    setup_json_logging()

    # 파일 출력
    setup_json_logging(output_path="logs/app.jsonl")

    logger = logging.getLogger(__name__)
    logger.info("User action", extra={"user_id": "abc", "action": "login"})
    # → {"ts":"2026-07-18T10:30:00Z","level":"INFO","logger":"__main__","message":"User action","user_id":"abc","action":"login"}
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON 구조화 로그 포맷터.

    표준 logging 레코드를 JSON 객체로 변환하며, extra kwargs는 최상위 키로 병합됩니다.
    타임스탬프는 ISO 8601 형식입니다.
    """

    def __init__(
        self,
        include_stack: bool = False,
        pretty: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.include_stack = include_stack
        self.pretty = pretty

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
            }
            if self.include_stack:
                import traceback

                log_entry["traceback"] = traceback.format_exception(*record.exc_info)

        # Add correlation ID if available (from ContextVar)
        try:
            from antigravity_k.api.error_handler import correlation_id_var

            cid = correlation_id_var.get("")
            if cid:
                log_entry["correlation_id"] = cid
        except (ImportError, LookupError):
            pass

        # Merge extra fields from the record
        # logging.LogRecord has some reserved attrs we need to skip
        reserved = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "id",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in reserved and not key.startswith("_"):
                try:
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        indent = 2 if self.pretty else None
        return json.dumps(log_entry, ensure_ascii=False, default=str, indent=indent)


class JSONFileHandler(logging.Handler):
    """JSON 구조화 로그를 파일에 기록하는 핸들러.

    각 로그 레코드는 JSON Lines (.jsonl) 형식으로 파일에追加 기록됩니다.
    """

    def __init__(
        self,
        output_path: str,
        include_stack: bool = False,
        max_bytes: int = 50 * 1024 * 1024,  # 50MB
        backup_count: int = 5,
    ) -> None:
        super().__init__()
        self.output_path = output_path
        self.include_stack = include_stack
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._formatter = JSONFormatter(include_stack=include_stack)

        # Create directory if needed
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        self._open_file()

    def _open_file(self) -> None:
        self._file = open(self.output_path, "a", encoding="utf-8")  # noqa: SIM115

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max_bytes."""
        try:
            if os.path.getsize(self.output_path) > self.max_bytes:
                self._file.close()
                for i in range(self.backup_count - 1, 0, -1):
                    src = f"{self.output_path}.{i}"
                    dst = f"{self.output_path}.{i + 1}"
                    if os.path.exists(src):
                        os.rename(src, dst)
                os.rename(self.output_path, f"{self.output_path}.1")
                self._open_file()
        except OSError:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self._formatter.format(record)
            self._file.write(msg + "\n")
            self._file.flush()
            self._rotate_if_needed()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()
        super().close()


def setup_json_logging(
    level: int | str = logging.INFO,
    output_path: str | None = None,
    include_stack: bool = False,
    pretty: bool = False,
    merge_stdout: bool = True,
    reset: bool = False,
) -> None:
    """JSON 구조화 로깅을 전역 설정합니다.

    Args:
        level: 로그 레벨 (기본: INFO)
        output_path: JSON 로그 파일 경로 (None=콘솔 전용)
        include_stack: 예외 발생 시 traceback 포함 여부
        pretty: JSON 출력을 pretty-print할지 여부 (개발용)
        merge_stdout: 콘솔 핸들러를 추가할지 여부
    """
    root_logger = logging.getLogger()

    # 기존 JSON/파일 핸들러만 제거 (다른 라이브러리의 핸들러는 보존)
    if reset:
        for handler in root_logger.handlers[:]:
            if isinstance(handler, (logging.StreamHandler, JSONFileHandler, logging.FileHandler)):
                # 우리가 추가한 핸들러인지 확인 (formatter 타입으로 식별)
                if isinstance(handler.formatter, JSONFormatter):
                    root_logger.removeHandler(handler)

    # Console handler with JSON format
    if merge_stdout or not output_path:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(JSONFormatter(include_stack=include_stack, pretty=pretty))
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)

    # File handler
    if output_path:
        file_handler = JSONFileHandler(output_path=output_path, include_stack=include_stack)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(level)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_json_logger(name: str, **extra_fields: Any) -> logging.LoggerAdapter:
    """편리한 JSON 로거 어댑터 생성 — extra 필드가 자동으로 포함됩니다.

    사용법:
        logger = get_json_logger(__name__, service="chat", version="1.0")
        logger.info("Request processed", extra={"latency_ms": 42})
    """
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, extra=extra_fields)
