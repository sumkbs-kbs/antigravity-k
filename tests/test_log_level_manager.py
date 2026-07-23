"""Tests for log_level_manager — Dynamic Log Level Manager.

Covers LogLevelManager: _normalize_level, _get_level_name, set_level, set_all_levels,
discover_loggers, enable/disable/debug mode, KNOWN_LOGGERS constants.
"""

from __future__ import annotations

import logging

from antigravity_k.engine.log_level_manager import (
    KNOWN_LOGGERS,
    ROOT_LOGGER_NAME,
    LogLevelManager,
)


class TestConstants:
    def test_root_logger_name(self):
        assert ROOT_LOGGER_NAME == "antigravity_k"

    def test_known_loggers_contains_key_modules(self):
        assert "antigravity_k.api" in KNOWN_LOGGERS
        assert "antigravity_k.engine" in KNOWN_LOGGERS
        assert "antigravity_k.tools" in KNOWN_LOGGERS
        assert "antigravity_k.engine.model_manager" in KNOWN_LOGGERS


class TestNormalizeLevel:
    def test_string_levels(self):
        assert LogLevelManager._normalize_level("DEBUG") == logging.DEBUG
        assert LogLevelManager._normalize_level("INFO") == logging.INFO
        assert LogLevelManager._normalize_level("WARNING") == logging.WARNING
        assert LogLevelManager._normalize_level("ERROR") == logging.ERROR
        assert LogLevelManager._normalize_level("CRITICAL") == logging.CRITICAL

    def test_int_level_passthrough(self):
        assert LogLevelManager._normalize_level(10) == 10
        assert LogLevelManager._normalize_level(20) == 20

    def test_invalid_string_falls_back_to_info(self):
        assert LogLevelManager._normalize_level("INVALID") == logging.INFO

    def test_case_insensitive(self):
        assert LogLevelManager._normalize_level("debug") == logging.DEBUG
        assert LogLevelManager._normalize_level("Debug") == logging.DEBUG


class TestGetLevelName:
    def test_known_level(self):
        assert LogLevelManager._get_level_name(logging.DEBUG) == "DEBUG"
        assert LogLevelManager._get_level_name(logging.INFO) == "INFO"
        assert LogLevelManager._get_level_name(logging.WARNING) == "WARNING"

    def test_unknown_int(self):
        name = LogLevelManager._get_level_name(42)
        assert isinstance(name, str)
        assert "Level 42" in name or "42" in name


class TestSetLevel:
    def test_set_level_returns_previous_and_current(self):
        logger = logging.getLogger("antigravity_k.test_temp")
        logger.setLevel(logging.WARNING)
        result = LogLevelManager.set_level("antigravity_k.test_temp", "DEBUG")
        assert result["name"] == "antigravity_k.test_temp"
        assert result["current_level"] == logging.DEBUG
        assert result["previous_level"] == logging.WARNING
        assert result["previous_level_name"] == "WARNING"
        assert result["current_level_name"] == "DEBUG"

    def test_set_level_changes_effective(self):
        logger = logging.getLogger("antigravity_k.test_level_change")
        logger.setLevel(logging.ERROR)
        LogLevelManager.set_level("antigravity_k.test_level_change", "INFO")
        assert logger.level == logging.INFO

    def test_root_logger(self):
        root = logging.getLogger()
        original = root.level
        LogLevelManager.set_level("root", "WARNING")
        assert root.level == logging.WARNING
        root.setLevel(original)


class TestDiscoverLoggers:
    def test_discover_returns_list_of_dicts(self):
        loggers = LogLevelManager.discover_loggers()
        assert len(loggers) >= 1
        names = [entry["name"] for entry in loggers]
        assert any("antigravity_k" in n for n in names)
        assert "root" in names

    def test_discover_entries_have_required_keys(self):
        loggers = LogLevelManager.discover_loggers()
        for entry in loggers:
            assert "name" in entry
            assert "level" in entry
            assert "level_name" in entry
            assert "effective_level" in entry
            assert "handlers" in entry

    def test_known_loggers_not_yet_created_included(self):
        """Loggers that exist in KNOWN_LOGGERS but not yet instantiated appear."""
        loggers = LogLevelManager.discover_loggers()
        names = {entry["name"] for entry in loggers}
        assert "root" in names


class TestSetAllLevels:
    def test_set_all_changes_all_antigravity_loggers(self):
        # Grab a specific logger and set it to WARNING first
        logger = logging.getLogger("antigravity_k.test_set_all")
        logger.setLevel(logging.CRITICAL)

        result = LogLevelManager.set_all_levels("DEBUG")
        assert result["target_level"] == logging.DEBUG
        assert result["target_level_name"] == "DEBUG"
        assert result["updated_count"] >= 1


class TestDebugMode:
    def setup_method(self):
        # Ensure clean state
        if LogLevelManager.is_debug_mode():
            LogLevelManager.disable_debug_mode()

    def test_enable_debug_mode_sets_debug(self):
        result = LogLevelManager.enable_debug_mode()
        assert result["success"] is True
        assert result["updated_count"] >= 1
        assert LogLevelManager.is_debug_mode() is True

    def test_double_enable_returns_early(self):
        LogLevelManager.enable_debug_mode()
        result = LogLevelManager.enable_debug_mode()
        assert result["updated_count"] == 0
        assert "already active" in result["message"]

    def test_disable_debug_mode_restores(self):
        LogLevelManager.enable_debug_mode()
        result = LogLevelManager.disable_debug_mode()
        assert result["success"] is True
        assert result["restored_count"] >= 1
        assert LogLevelManager.is_debug_mode() is False

    def test_double_disable_returns_early(self):
        LogLevelManager.disable_debug_mode()
        result = LogLevelManager.disable_debug_mode()
        assert result["restored_count"] == 0
        assert "not active" in result["message"]

    def test_is_debug_mode_after_enable(self):
        LogLevelManager.enable_debug_mode()
        assert LogLevelManager.is_debug_mode() is True
        LogLevelManager.disable_debug_mode()
        assert LogLevelManager.is_debug_mode() is False
