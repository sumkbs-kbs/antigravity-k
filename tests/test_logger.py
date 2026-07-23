"""Tests for the JSON structured logger module."""

import json
import logging
import os
import tempfile
from datetime import datetime

import pytest

from antigravity_k.engine.logger import JSONFormatter, setup_json_logger


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_basic(self):
        """기본 포맷에 timestamp, level, logger, message가 포함되어야 함."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        assert output["level"] == "INFO"
        assert output["logger"] == "test_logger"
        assert output["message"] == "hello world"
        assert "timestamp" in output
        assert output["timestamp"].endswith("Z")

    def test_format_with_static_fields(self):
        """정적 필드가 로그 데이터에 포함되어야 함."""
        formatter = JSONFormatter(app_name="antigravity-k", version="1.0")
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=5,
            msg="warning message",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        assert output["app_name"] == "antigravity-k"
        assert output["version"] == "1.0"
        assert output["level"] == "WARNING"

    def test_format_with_exception(self):
        """예외 정보가 포함된 레코드에 exc_info와 stack_trace가 추가되어야 함."""
        import sys

        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=15,
                msg="error occurred",
                args=(),
                exc_info=exc_info,
            )
        output = json.loads(formatter.format(record))
        assert output["level"] == "ERROR"
        assert output["message"] == "error occurred"
        assert "exc_info" in output
        assert "stack_trace" in output

    def test_format_with_extra_fields(self):
        """extra로 전달된 추가 필드가 로그 데이터에 포함되어야 함."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=20,
            msg="tool called",
            args=(),
            exc_info=None,
        )
        record.tool = "search"
        record.session_id = "abc-123"
        output = json.loads(formatter.format(record))
        assert output["tool"] == "search"
        assert output["session_id"] == "abc-123"

    def test_format_extra_excludes_internal_keys(self):
        """logging 내부 키는 extra에 포함되지 않아야 함."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=25,
            msg="debug",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        # 내부 키가 출력에 없어야 함
        assert "args" not in output
        assert "exc_info" not in output
        assert "created" not in output
        assert "lineno" not in output

    def test_format_levels(self):
        """각 로그 레벨별로 올바른 levelname이 출력되어야 함."""
        formatter = JSONFormatter()
        for level, name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="test",
                args=(),
                exc_info=None,
            )
            output = json.loads(formatter.format(record))
            assert output["level"] == name

    def test_timestamp_format(self):
        """timestamp가 ISO 8601 형식이어야 함."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        # ISO 8601 형식 검증 (Z suffix)
        assert output["timestamp"].endswith("Z")
        # datetime 파싱 가능해야 함
        parsed = datetime.fromisoformat(output["timestamp"].rstrip("Z"))
        assert parsed is not None

    def test_ensure_ascii_false(self):
        """한글 메시지가 유니코드로 출력되어야 함."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="한글 메시지",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        # 유니코드 이스케이프가 아닌 실제 한글이 JSON에 포함되어야 함
        assert "한글 메시지" in output
        # \\u로 시작하는 이스케이프가 아니어야 함
        assert "\\u" not in output


class TestSetupJsonLogger:
    """Tests for setup_json_logger function."""

    def test_setup_json_logger_creates_file(self):
        """setup_json_logger가 로그 파일을 생성해야 함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test_log.json")
            logger = setup_json_logger(log_file_path=log_path, level=logging.DEBUG)
            assert logger is not None
            logger.info("test message")
            # 핸들러가 플러시되도록 로거 정리
            for h in logger.handlers:
                h.flush()
            assert os.path.exists(log_path)

    def test_setup_json_logger_writes_json(self):
        """setup_json_logger로 기록된 로그가 JSON 형식이어야 함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test.json")
            logger = setup_json_logger(log_file_path=log_path)
            test_msg = "json test message"
            logger.info(test_msg)
            for h in logger.handlers:
                h.flush()
            with open(log_path, encoding="utf-8") as f:
                line = f.readline()
            data = json.loads(line)
            assert data["message"] == test_msg
            assert data["level"] == "INFO"

    def test_avoid_duplicate_handlers(self):
        """중복 호출 시 핸들러가 중복 추가되지 않아야 함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "dup.json")
            logger1 = setup_json_logger(log_file_path=log_path)
            logger2 = setup_json_logger(log_file_path=log_path)
            assert logger1 is logger2
            # 같은 로거에 대해 중복 핸들러 방지
            logger3 = setup_json_logger(log_file_path=log_path)
            assert logger3 is logger1

    def test_setup_json_logger_creates_directory(self):
        """로그 파일의 디렉토리가 없으면 생성해야 함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "nested", "dir", "test.json")
            logger = setup_json_logger(log_file_path=nested_path)
            assert logger is not None
            assert os.path.exists(os.path.dirname(nested_path))

    def test_log_with_extra_fields_via_logger(self):
        """실제 로거를 통해 extra 필드가 JSON에 포함되어야 함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "extra.json")
            logger = setup_json_logger(log_file_path=log_path)
            logger.info("tool executed", extra={"tool_name": "search", "duration_ms": 150})
            for h in logger.handlers:
                h.flush()
            with open(log_path, encoding="utf-8") as f:
                line = f.readline()
            data = json.loads(line)
            assert data["tool_name"] == "search"
            assert data["duration_ms"] == 150

    @pytest.fixture(autouse=True)
    def _cleanup_logger_handlers(self):
        """각 테스트 후 root logger에 추가된 핸들러를 정리."""
        yield
        root = logging.getLogger()
        for h in list(root.handlers):
            if hasattr(h, "baseFilename"):
                root.removeHandler(h)
